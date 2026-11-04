import os
import re
import json
import time
import threading
import urllib.request
import urllib.parse
from enum import Enum, auto
from dataclasses import dataclass, asdict
from typing import Optional, Callable, Dict, Any, Tuple, List


class GateSource(Enum):
    STANDALONE_GF     = "GateFinder (Airline Match)"
    VATSIM_CLEAN      = "GateFinder (VATSIM Conflict-Free)"
    VATSIM_REASSIGNED = "GateFinder (Pre-TOD VATSIM Reassigned)"
    BEYOND_ATC        = "BeyondATC"
    SAY_INTENTIONS    = "SayIntentions.AI"
    GSX_LIVE          = "GSX Pro"
    USER_MANUAL       = "User Manual Selection"


class HubState(Enum):
    IDLE                 = "IDLE"
    GATE_COMPUTED        = "GATE_COMPUTED"
    ATC_CONFLICT_PENDING = "ATC_CONFLICT_PENDING"
    GATE_LOCKED          = "GATE_LOCKED"
    GSX_INJECTING        = "GSX_INJECTING"
    GSX_SYNCED           = "GSX_SYNCED"


@dataclass
class GateDecision:
    phase: str                  # "departure" | "arrival"
    icao: str                   # e.g. "LEPA"
    gate_id: str                # e.g. "D 92"
    source: GateSource
    lat: Optional[float] = None
    lon: Optional[float] = None
    gsx_synced: bool = False
    batc_handles_gsx: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "icao": self.icao,
            "gate_id": self.gate_id,
            "source": self.source.value,
            "source_key": self.source.name,
            "lat": self.lat,
            "lon": self.lon,
            "gsx_synced": self.gsx_synced,
            "batc_handles_gsx": self.batc_handles_gsx,
        }


def clean_gate_token(raw_gate: str) -> str:
    """
    Normalizes any raw gate string ('Gate F 37', 'STAND_D92_NONE', 'Parking 10', 'F37', 'A01')
    into a canonical comparison token (e.g., 'F37', 'D92', '10', 'A1').
    """
    if not raw_gate:
        return ""
    s = str(raw_gate).upper().strip()
    # Strip parenthetical or hyphenated annotations
    s = re.sub(r'\s*\(.*$', '', s).strip()
    s = re.sub(r'\s+-\s+.*$', '', s).strip()
    # Strip common prefixes
    s = re.sub(r'^(GATE|STAND|PARKING|RAMP|DOCK|SPOT|BAY)[\s_\-]*', '', s)
    # Strip trailing NONE suffix from BATC/BGL identifiers
    s = re.sub(r'[\s_\-]+NONE$', '', s)
    # Collapse all spaces, underscores, and hyphens
    s = re.sub(r'[\s_\-]+', '', s)
    m = re.match(r'^([A-Z]{0,3})0+(\d+[A-Z]?)$', s)
    if m:
        s = f"{m.group(1)}{m.group(2)}"
    return s


def strip_redundant_gate_suffix(tok: str) -> str:
    """
    In MSFS 2020/2024 default BGL files (e.g. LFKC), parking records often store
    Name=GATE_P, Number=8, Suffix=GATE_P, which BeyondATC/GSX render as 'Ramp P8P'
    or 'Gate P 8P' ('P8P'), whereas charts/OSM/GateFinder name the stand 'P8'.
    Strips the trailing letter when it duplicates the leading prefix letter.
    """
    if not tok:
        return ""
    m = re.match(r'^([A-Z]+)(\d+)\1$', tok)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return tok


def gate_tokens_match(raw_a: Optional[str], raw_b: Optional[str]) -> bool:
    """
    Returns True if two gate strings refer to the same stand, accounting for
    duplicated BGL prefix-as-suffix tokens (e.g. 'P8' <-> 'P8P' / 'Gate P 8P' / 'Ramp P8P').
    """
    a = clean_gate_token(raw_a or "")
    b = clean_gate_token(raw_b or "")
    if not a or not b:
        return False
    if a == b:
        return True
    return strip_redundant_gate_suffix(a) == strip_redundant_gate_suffix(b)


def parse_gsx_gate_tokens(gate_str: str) -> Dict[str, str]:
    """
    Splits a gate label (e.g. 'F 37', 'Gate D 92L', '42', 'F33R') into
    prefix ('F'), number ('37'), and suffix ('', 'L', 'R') for GSX menu matching.
    """
    if not gate_str:
        return {"prefix": "", "number": "", "suffix": "", "search_query": ""}
    s = str(gate_str).upper().strip()
    s = re.sub(r'^(GATE|STAND|PARKING|RAMP|DOCK|SPOT)[\s_\-]*', '', s)
    s = re.sub(r'[\s_\-]+NONE$', '', s).strip()

    m = re.match(r'^([A-Z]{0,3})[\s_\-]*(\d+)[\s_\-]*([A-Z]?)$', s)
    if m:
        prefix, num, suffix = m.group(1), m.group(2), m.group(3)
        search_q = f"{prefix} {num}{suffix}".strip()
        return {
            "prefix": prefix,
            "number": num,
            "suffix": suffix,
            "search_query": search_q
        }
    return {"prefix": "", "number": s, "suffix": "", "search_query": s}


class GSXArrivalAutomator:
    """
    Automates GSX Pro v3 Arrival Gate Selection + Default Handler Selection + FollowMe=No:
      1. Opens GSX Menu via SimConnect LVars (`L:FSDT_GSX_MENU_OPEN` 0->1 pulse, `L:FSDT_GSX_MENU_CHOICE = -2`).
      2. Navigates from Main Menu ("Select another parking" / "Change parking") if needed.
      3. Selects the assigned Arrival Gate using both GSX Pro v3 Live Gate Search
         (`L:FSDT_GSX_SEARCH_*` + `L:FSDT_GSX_SEARCH_GEN` -> `./menu_live.html`)
         and hierarchical Terminal / Prefix / Numeric-Range navigation (`./menu`).
      4. Automatically selects the `(default)` Handling / Catering Operator when prompted.
      5. Automatically selects `"No"` when GSX prompts `"Request FollowMe?"`.
    """
    def __init__(self, hub: "InteroperabilityHub"):
        self.hub = hub
        self._lock = threading.Lock()
        self._seq_exec_lock = threading.Lock()
        self._active_run_id = 0
        self._running = False
        self._last_start_ts = 0.0
        self._last_finish_ts = 0.0
        self.state = "IDLE"          # IDLE | ARMED | INJECTING | SYNCED | FAILED | DELEGATED_BATC | DISABLED
        self.status_label = "GSX PRO: STANDBY"
        self.status_color = "#64748B"
        self.synced_gate: Optional[str] = None
        self.synced_icao: Optional[str] = None
        self._panel_dir_cache: Optional[str] = None
        self._re_live_btn = re.compile(
            r'<button[^>]*\bdata-c="(\d+)"[^>]*>.*?<span\s+class="gl">(.*?)</span>',
            re.IGNORECASE | re.DOTALL
        )
        self._re_range = re.compile(
            r'(?:GATES?|STANDS?|PARKINGS?|RAMPS?|DOCKS?)?\s*\b([A-Z]{0,3})\s*(\d+)\s*(?:\-|to|\.\.)\s*([A-Z]{0,3})\s*(\d+)\b',
            re.IGNORECASE
        )

    def _log(self, msg: str):
        try:
            sc = getattr(self.hub.backend, "simconnect_manager", None)
            if sc and hasattr(sc, "_log"):
                sc._log(f"[GSXAutomator] {msg}")
        except Exception:
            pass
        print(f"[GSXAutomator] {msg}")

    def _find_gsx_panel_dir(self) -> Optional[str]:
        if self._panel_dir_cache and os.path.isdir(self._panel_dir_cache):
            return self._panel_dir_cache

        candidates = []
        rel_sub = os.path.join("fsdreamteam-gsx-pro", "html_ui", "InGamePanels", "FSDT_GSX_Panel")

        # 1. Registry HKCU\Software\Fsdreamteam -> root
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Fsdreamteam") as k:
                root_val, _ = winreg.QueryValueEx(k, "root")
                if root_val and isinstance(root_val, str):
                    candidates.append(os.path.join(root_val, "MSFS", rel_sub))
        except Exception:
            pass

        # 2. Standard Addon Manager path
        candidates.append(os.path.join(r"C:\Program Files (x86)\Addon Manager\MSFS", rel_sub))
        candidates.append(os.path.join(r"C:\Addon Manager\MSFS", rel_sub))

        # 3. Configured & auto-detected MSFS Community folders
        try:
            comm20 = self.hub.config.settings.get("msfs_community_path", "")
            comm24 = self.hub.config.settings.get("msfs_community2024_path", "")
            if comm20:
                candidates.append(os.path.join(comm20, rel_sub))
            if comm24:
                candidates.append(os.path.join(comm24, rel_sub))
            from config import find_all_possible_community_folders
            for cf in find_all_possible_community_folders():
                candidates.append(os.path.join(cf, rel_sub))
        except Exception:
            pass

        valid_dirs = []
        seen = set()
        for c in candidates:
            norm = os.path.normpath(c)
            if norm in seen:
                continue
            seen.add(norm)
            if os.path.isdir(norm):
                menu_f = os.path.join(norm, "menu")
                mtime = os.path.getmtime(menu_f) if os.path.exists(menu_f) else 0.0
                valid_dirs.append((mtime, norm))

        if valid_dirs:
            valid_dirs.sort(key=lambda x: x[0], reverse=True)
            self._panel_dir_cache = valid_dirs[0][1]
            return self._panel_dir_cache
        return None

    def is_gsx_installed(self) -> bool:
        """Returns True if the GSX Pro InGamePanel directory is installed on this PC."""
        return self._find_gsx_panel_dir() is not None

    def is_running_or_synced_for(self, icao: str, gate: str) -> bool:
        """Returns True if an arrival sync is currently running or already completed for this exact (icao, gate)."""
        target_tok = clean_gate_token(gate)
        if not target_tok:
            return False
        with self._lock:
            if not self.synced_icao or not self.synced_gate:
                return False
            if self.synced_icao.upper() != (icao or "").upper():
                return False
            if not gate_tokens_match(self.synced_gate, target_tok):
                return False
            return self._running or self.state == "SYNCED"

    def _read_menu_state(self, panel_dir: str) -> Dict[str, Any]:
        menu_file = os.path.join(panel_dir, "menu")
        live_file = os.path.join(panel_dir, "menu_live.html")
        is_open = False
        title = ""
        options: List[str] = []
        menu_mtime = 0.0
        live_options: List[Tuple[int, str]] = []
        live_mtime = 0.0

        try:
            if os.path.exists(menu_file):
                menu_mtime = os.path.getmtime(menu_file)
                with open(menu_file, "r", encoding="utf-8", errors="ignore") as f:
                    raw = f.read()
                if raw.strip():
                    lines = [ln.strip() for ln in raw.splitlines()]
                    if lines:
                        is_open = True
                        title = lines[0]
                        options = lines[1:11]
        except Exception:
            pass

        try:
            if os.path.exists(live_file):
                live_mtime = os.path.getmtime(live_file)
                if live_mtime >= (menu_mtime - 0.25) and (time.time() - live_mtime < 3.0):
                    with open(live_file, "r", encoding="utf-8", errors="ignore") as f:
                        html_raw = f.read()
                    for m in self._re_live_btn.finditer(html_raw):
                        c_idx = int(m.group(1))
                        lbl = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                        if 0 <= c_idx <= 9 and lbl:
                            live_options.append((c_idx, lbl))
        except Exception:
            pass

        return {
            "is_open": is_open,
            "title": title,
            "options": options,
            "menu_mtime": menu_mtime,
            "live_options": live_options,
            "live_mtime": live_mtime,
        }

    def _extract_gsx_gate_label(self, raw_lbl: str) -> str:
        """
        Strips GSX menu metadata from an individual gate option so that e.g.:
          'Gate 4 - Medium  No Push' -> 'Gate 4'
          'Gate M 1 - Ramp GA Small  - WALK IN, No Bus No Push (too small)' -> 'Gate M 1'
          'Gate T 31 with SafedockD - Small - T.o./2' -> 'Gate T 31'
          'Stand E 44 (Jetway)' -> 'Stand E 44'
        """
        if not raw_lbl:
            return ""
        s = raw_lbl.split("\t")[0].strip()
        s = re.sub(r'[\(\[].*?[\)\]]', '', s).strip()
        if not self._re_range.search(s):
            s = re.split(r'\s+-\s+', s, maxsplit=1)[0].strip()
            s = re.sub(r'\s+with\s+.*$', '', s, flags=re.IGNORECASE).strip()
        return s

    @staticmethod
    def _extract_change_facility_gate(opt: str) -> Optional[str]:
        """
        Extracts the currently active gate token from a 'Change Facility [...]' option, e.g.:
          'Change Facility [Gate M  Gate M 1]' -> 'M 1'
          'Change Facility [Gate  Gate 4]' -> '4'
          'Change Facility [Terminal 2E  Stand E 44]' -> 'E 44'
        """
        m = re.search(r'change\s+facility\s*\[([^\]]+)\]', opt or "", re.IGNORECASE)
        if not m:
            return None
        inside = m.group(1).strip()
        if not inside:
            return None
        explicit = re.findall(
            r'\b(?:Gate|Stand|Parking|Ramp|Dock)s?\s+([A-Z]{0,3}\s*\d+[A-Z]?)\b',
            inside,
            re.IGNORECASE
        )
        if explicit:
            return explicit[-1].strip()
        parts = [p.strip() for p in re.split(r'\s{2,}', inside) if p.strip()]
        return parts[-1] if parts else inside

    def _is_individual_gate_option(self, label: str) -> bool:
        """
        Returns True if `label` is an individual selectable gate/stand option
        (e.g. 'Gate 4 - Medium  No Push', 'Gate M 1 - Ramp GA Small...') rather than
        a group/folder header ('Gate \\t(11 suitable parkings)', 'Terminal 2A', 'Gates 1 - 10').
        """
        s = (label or "").strip()
        if not s:
            return False
        sl = s.lower()
        if "suitable parking" in sl or "change facility" in sl:
            return False
        if re.search(r'\b(?:next\s*page|previous|more|request\s+|revoke\s+|free\s+this|just\s+warp|show\s+me)\b', sl):
            return False
        if self._re_range.search(s):
            return False
        base = self._extract_gsx_gate_label(s)
        u = base.upper()
        if re.match(r'^(GATES|STANDS|PARKINGS|RAMPS|DOCKS|TERMINAL|APRON|CONCOURSE|PIER|SECTOR|AREA|CARGO|NORTH|SOUTH|EAST|WEST|MAIN|ALL)\b', u):
            return False
        if " - " in s:
            t = parse_gsx_gate_tokens(base)
            if t.get("number"):
                return True
        if re.match(r'^(?:GATE|STAND|PARKING|RAMP|DOCK)\s+[A-Z]{0,3}\s*\d+[A-Z]?$', u):
            return True
        return False

    def _is_group_or_range_label(self, label: str) -> bool:
        s = (label or "").strip()
        if not s:
            return True
        sl = s.lower()
        if "suitable parking" in sl or "change facility" in sl:
            return True
        if re.search(r'\b(?:next\s*page|previous|more|request\s+|revoke\s+|free\s+this|just\s+warp|show\s+me)\b', sl):
            return True
        u = s.upper()
        if re.search(r'\d+\s*(?:\-|TO|\.\.)\s*[A-Z0-9]*\d+', u):
            return True
        base_u = self._extract_gsx_gate_label(s).upper()
        if re.match(r'^(GATES|STANDS|PARKINGS|RAMPS|DOCKS|TERMINAL|APRON|CONCOURSE|PIER|SECTOR|AREA|CARGO|NORTH|SOUTH|EAST|WEST|MAIN|ALL\b|NEXT\b|MORE\b|PREVIOUS\b)', base_u):
            return True
        return False

    def _find_exact_gate_option(self, indexed_opts: List[Tuple[int, str]], target_gate: str, tokens: Dict[str, str]) -> Optional[int]:
        target_tok = clean_gate_token(target_gate)
        if not target_tok:
            return None

        # 1. Primary pass: exact token match OR BGL duplicated prefix-as-suffix match (e.g. 'P8' <-> 'Gate P 8P' / 'P8P')
        for idx, raw_lbl in indexed_opts:
            if not raw_lbl or self._is_group_or_range_label(raw_lbl):
                continue
            base_lbl = self._extract_gsx_gate_label(raw_lbl)
            cand_tok = clean_gate_token(base_lbl)
            if cand_tok and gate_tokens_match(cand_tok, target_tok):
                return idx

        # 2. Secondary pass: if target_gate has no distinct suffix (e.g. 'P8' or 'P8P' where suffix==prefix),
        # OR if target_gate has an OSM sub-stand letter suffix (e.g. 'P2A' / 'P2B' at LFKC) while GSX BGL only
        # defines a single base stand for that prefix+number (e.g. 'Gate P 2P' / 'Gate P 2' / 'Gate P 8G')
        want_pre = (tokens.get("prefix") or "").upper()
        want_num = (tokens.get("number") or "").upper()
        want_suf = (tokens.get("suffix") or "").upper()
        if want_num:
            pre_num_matches = []
            for idx, raw_lbl in indexed_opts:
                if not raw_lbl or self._is_group_or_range_label(raw_lbl):
                    continue
                base_lbl = self._extract_gsx_gate_label(raw_lbl)
                t = parse_gsx_gate_tokens(base_lbl)
                if (t.get("prefix") or "").upper() == want_pre and (t.get("number") or "").upper() == want_num:
                    pre_num_matches.append((idx, (t.get("suffix") or "").upper()))
            if len(pre_num_matches) == 1:
                return pre_num_matches[0][0]
            elif len(pre_num_matches) > 1 and (not want_suf or want_suf == want_pre):
                for idx_m, suf_m in pre_num_matches:
                    if not suf_m or suf_m == want_pre:
                        return idx_m

        # 3. Tertiary check: if target_gate is purely numeric (e.g. '42') and GSX lists 'Gate A 42' when only 1 gate 42 exists on screen
        if not tokens.get("prefix") and tokens.get("number"):
            want_num_suf = f"{tokens['number']}{tokens.get('suffix', '')}".upper()
            matches = []
            for idx, raw_lbl in indexed_opts:
                if not raw_lbl or self._is_group_or_range_label(raw_lbl):
                    continue
                base_lbl = self._extract_gsx_gate_label(raw_lbl)
                t = parse_gsx_gate_tokens(base_lbl)
                if f"{t['number']}{t['suffix']}".upper() == want_num_suf:
                    matches.append(idx)
            if len(matches) == 1:
                return matches[0]
        return None

    def _find_group_or_range_option(
        self,
        options: List[str],
        tokens: Dict[str, str],
        terminal_hint: str,
        visited_labels: set,
        cur_sig: Any = None
    ) -> Optional[Tuple[int, str]]:
        want_prefix = (tokens.get("prefix") or "").upper()
        want_num_str = tokens.get("number") or ""
        want_num = int(want_num_str) if want_num_str.isdigit() else None

        def _is_visited(opt_str: str, is_pagination: bool = False) -> bool:
            if not opt_str:
                return True
            if is_pagination and cur_sig is not None:
                return (cur_sig, opt_str) in visited_labels
            return (opt_str in visited_labels) or (cur_sig is not None and (cur_sig, opt_str) in visited_labels)

        def _is_candidate_group(opt_str: str) -> bool:
            if not opt_str or _is_visited(opt_str, is_pagination=False):
                return False
            if self._is_individual_gate_option(opt_str):
                return False
            ol = opt_str.lower()
            if "change facility" in ol or re.search(r'\b(?:request\s+|revoke\s+|free\s+this|just\s+warp|show\s+me|previous\s*page|back)\b', ol):
                return False
            return True

        def _clean_group_title(opt_str: str) -> str:
            return re.sub(r'[\(\[].*?[\)\]]', '', opt_str.split("\t")[0]).strip()

        def _find_generic_unprefixed() -> Optional[Tuple[int, str]]:
            # Generic unprefixed "Gate" / "Gates" / "Stand" / "Stands" / "Parking" / "All Gates" group
            # Strictly requires no trailing letter prefix so 'Gate H' or 'Gate M' is NEVER matched when want_prefix == ""
            for allow_zero_suitable in (False, True):
                for idx, opt in enumerate(options):
                    if not _is_candidate_group(opt):
                        continue
                    if self._re_range.search(opt):
                        continue
                    if not allow_zero_suitable and "(0 suitable parking" in opt.lower():
                        continue
                    grp_title = _clean_group_title(opt)
                    if re.match(r'^(?:ALL\s+)?(?:GATES?|STANDS?|PARKINGS?|RAMPS?|DOCKS?)$', grp_title, re.IGNORECASE):
                        return idx, opt
            return None

        def _find_next_page() -> Optional[Tuple[int, str]]:
            for idx, opt in enumerate(options):
                if not opt or _is_visited(opt, is_pagination=True):
                    continue
                if re.search(r'\b(?:NEXT\s*PAGE|MORE|NEXT)\b', opt, re.IGNORECASE):
                    return idx, opt
            return None

        # 0. "Show all positions" inside an airline-filtered terminal submenu
        # (e.g. "Gate T positions for your airline (CCM)" -> [0] "Show all positions")
        # Since Step 7A (_find_exact_gate_option) runs before _find_group_or_range_option,
        # reaching here means the target gate was not in the airline-filtered subset.
        for idx, opt in enumerate(options):
            if not opt or _is_visited(opt, is_pagination=True):
                continue
            if re.search(r'\bshow\s+all\s+positions\b', opt, re.IGNORECASE):
                return idx, opt

        # 1. Numeric range match (e.g. "Gates E 1 - E 67", "Gates 40 - 49", "Stands 1 - 50")
        if want_num is not None:
            for idx, opt in enumerate(options):
                if not _is_candidate_group(opt):
                    continue
                m = self._re_range.search(opt)
                if m:
                    p1 = (m.group(1) or "").upper()
                    n1 = int(m.group(2))
                    p2 = (m.group(3) or p1).upper()
                    n2 = int(m.group(4))
                    if p1 in ("GATE", "GATES", "STAND", "STANDS", "PARKING", "RAMP", "DOCK"):
                        p1 = ""
                    if p2 in ("GATE", "GATES", "STAND", "STANDS", "PARKING", "RAMP", "DOCK"):
                        p2 = p1
                    if want_prefix:
                        if p1 and p1 != want_prefix and p2 != want_prefix:
                            continue
                    else:
                        if p1 and not re.match(r'^(GATE|STAND|PARKING|RAMP|DOCK)S?$', p1):
                            continue
                    if min(n1, n2) <= want_num <= max(n1, n2):
                        return idx, opt

        # 2. Explicit Prefix group match (e.g. "Gate E", "Gates E", "Stand E", "Pier E", "Concourse E", "Terminal E")
        if want_prefix:
            pat = re.compile(
                rf'^(?:GATES?|STANDS?|PARKINGS?|RAMPS?|DOCKS?|PIER|CONCOURSE|TERMINAL|APRON|SECTOR|AREA)\s+{re.escape(want_prefix)}$'
                rf'|^{re.escape(want_prefix)}\s+(?:GATES?|STANDS?|PARKINGS?|PIER|CONCOURSE|APRON)$'
                rf'|^{re.escape(want_prefix)}$',
                re.IGNORECASE
            )
            for idx, opt in enumerate(options):
                if not _is_candidate_group(opt):
                    continue
                grp_title = _clean_group_title(opt)
                if pat.search(grp_title):
                    return idx, opt

        # 3. Terminal hint match from GateFinder airport DB (e.g. "Terminal 2A", "Terminal 1")
        if terminal_hint:
            t_clean = re.sub(r'\(.*?\)', '', terminal_hint).strip().upper()
            if t_clean and t_clean not in ("MAIN APRON", "APRON", "GATE", "GATES", "STAND", "STANDS", "PARKING", "RAMP", "RAMPS"):
                other_prefix_re = re.compile(
                    r'^(?:GATES?|STANDS?|PARKINGS?|RAMPS?|DOCKS?|APRON)\s+([A-Z]{1,3})$',
                    re.IGNORECASE
                )
                for idx, opt in enumerate(options):
                    if not _is_candidate_group(opt):
                        continue
                    grp_u = _clean_group_title(opt).upper()
                    if not grp_u or grp_u in ("MAIN APRON", "APRON", "GATE", "GATES", "STAND", "STANDS", "PARKING", "RAMP", "RAMPS"):
                        continue
                    m_op = other_prefix_re.match(grp_u)
                    if m_op and want_prefix and m_op.group(1).upper() != want_prefix:
                        continue
                    if t_clean == grp_u or (len(grp_u) >= 5 and (t_clean in grp_u or grp_u in t_clean)):
                        return idx, opt

        # 4 & 5. When looking for a letter-prefixed gate (e.g. "U 3" -> want_prefix="U"),
        # paginate via "Next Page ►" FIRST so we reach Page 2 / Page 3 where "Gate U" lives,
        # before falling back to generic unprefixed "Gate" / "Parking" / "Ramp" folders.
        if want_prefix:
            nxt = _find_next_page()
            if nxt is not None:
                return nxt
            gen = _find_generic_unprefixed()
            if gen is not None:
                return gen
        else:
            gen = _find_generic_unprefixed()
            if gen is not None:
                return gen
            nxt = _find_next_page()
            if nxt is not None:
                return nxt

        return None

    def set_armed(self, icao: str, gate: str, note: Optional[str] = None):
        with self._lock:
            self._active_run_id += 1
            self._running = False
            self.state = "ARMED"
            self.synced_icao = icao
            self.synced_gate = gate
            self.status_label = note if note else f"GSX PRO: ARMED FOR TOUCHDOWN ({gate})"
            self.status_color = "#38BDF8"

    def set_delegated_batc(self, icao: str, gate: str):
        with self._lock:
            self._active_run_id += 1
            self._running = False
            self.state = "DELEGATED_BATC"
            self.synced_icao = icao
            self.synced_gate = gate
            self.status_label = "GSX PRO: MANAGED BY BEYONDATC"
            self.status_color = "#38BDF8"

    def set_disabled(self):
        with self._lock:
            self._active_run_id += 1
            self._running = False
            self.state = "DISABLED"
            self.status_label = "GSX PRO: AUTO-SYNC OFF"
            self.status_color = "#64748B"

    def set_not_installed(self):
        with self._lock:
            self._active_run_id += 1
            self._running = False
            self.state = "NOT_INSTALLED"
            self.status_label = "GSX PRO: NOT INSTALLED"
            self.status_color = "#64748B"

    def get_status_dict(self) -> Dict[str, Any]:
        installed = self.is_gsx_installed()
        auto_enabled = bool(self.hub.config.settings.get("auto_inject_gsx", True))
        with self._lock:
            if not installed:
                return {
                    "state": "NOT_INSTALLED",
                    "label": "GSX PRO: NOT INSTALLED",
                    "color": "#64748B",
                    "synced": False,
                    "running": False,
                    "gate": self.synced_gate,
                    "icao": self.synced_icao,
                    "installed": False,
                    "visible": False,
                }
            if not auto_enabled and not self._running:
                return {
                    "state": "DISABLED",
                    "label": "GSX PRO: AUTO-SYNC OFF",
                    "color": "#64748B",
                    "synced": False,
                    "running": False,
                    "gate": self.synced_gate,
                    "icao": self.synced_icao,
                    "installed": True,
                    "visible": False,
                }
            return {
                "state": self.state,
                "label": self.status_label,
                "color": self.status_color,
                "synced": (self.state == "SYNCED"),
                "running": self._running,
                "gate": self.synced_gate,
                "icao": self.synced_icao,
                "installed": True,
                "visible": True,
            }

    def start_arrival_sync(
        self,
        icao: str,
        target_gate: str,
        terminal_hint: str = "",
        manual: bool = False,
        initial_delay_sec: float = 0.0,
        wait_for_batc_gsx: bool = False,
        warp: bool = False
    ):
        if not target_gate or target_gate in ("N/A", "No Gate Found", "No Suitable Stand"):
            return
        if not self.is_gsx_installed():
            self.set_not_installed()
            return
        now_t = time.time()
        with self._lock:
            # Debounce rapid duplicate clicks (< 2.0s) for the exact same (icao, gate) while already running
            if (
                not warp
                and self._running
                and self.synced_icao
                and self.synced_gate
                and self.synced_icao.upper() == (icao or "").upper()
                and gate_tokens_match(self.synced_gate, target_gate)
                and (now_t - self._last_start_ts) < 2.0
            ):
                return
            self._active_run_id += 1
            run_id = self._active_run_id
            self._running = True
            self._last_start_ts = now_t
            self.state = "INJECTING"
            self.synced_icao = icao
            self.synced_gate = target_gate
            self.status_label = (
                f"GSX PRO: REPOSITIONING TO {target_gate}..."
                if warp
                else f"GSX PRO: SELECTING STAND {target_gate}..."
            )
            self.status_color = "#38BDF8" if warp else "#F59E0B"

        t = threading.Thread(
            target=self._run_sequence,
            args=(run_id, icao, target_gate, terminal_hint, manual, initial_delay_sec, wait_for_batc_gsx, warp),
            daemon=True
        )
        t.start()

    def _finish(self, run_id: int, success: bool, label: str, color: str):
        with self._lock:
            if run_id != self._active_run_id:
                return
            self._running = False
            self._last_finish_ts = time.time()
            self.state = "SYNCED" if success else "FAILED"
            self.status_label = label
            self.status_color = color
            task = self.hub.gsx_injection_task
            task_id = task.get("task_id") if isinstance(task, dict) else None

        if task_id is not None:
            self.hub.acknowledge_gsx_injection(task_id, success)

    def _run_sequence(
        self,
        run_id: int,
        icao: str,
        target_gate: str,
        terminal_hint: str,
        manual: bool,
        initial_delay_sec: float = 0.0,
        wait_for_batc_gsx: bool = False,
        warp: bool = False
    ):
        if wait_for_batc_gsx:
            with self._lock:
                if run_id != self._active_run_id:
                    return
                self.status_label = f"GSX PRO: SYNCING WITH BEYONDATC ({target_gate})..."
            # Stage 1: Wait up to 5.0s for BeyondATC to start '[GSX] Execute Gate Assignment Flow'
            # (BeyondATC triggers this right after pilot readback, ~3.5s after the taxi clearance).
            start_deadline = time.time() + 5.0
            while time.time() < start_deadline:
                with self._lock:
                    if run_id != self._active_run_id:
                        return
                if getattr(self.hub, "batc_gsx_flow_started_event", None) and self.hub.batc_gsx_flow_started_event.is_set():
                    break
                if self.hub.batc_gsx_flow_done_event.is_set():
                    break
                time.sleep(0.05)

            # Stage 2: If BeyondATC started its GSX flow, wait up to 9.0s for '[GSX] Completed Gate Assignment Flow'
            if getattr(self.hub, "batc_gsx_flow_started_event", None) and self.hub.batc_gsx_flow_started_event.is_set():
                done_deadline = time.time() + 9.0
                while time.time() < done_deadline:
                    with self._lock:
                        if run_id != self._active_run_id:
                            return
                    if self.hub.batc_gsx_flow_done_event.is_set():
                        break
                    time.sleep(0.05)

            # Fast-Path Check: Did BeyondATC already select the exact matching stand and 'No' for FollowMe?
            batc_sel = getattr(self.hub.batc_watcher, "batc_gsx_selected_gate", "")
            batc_fm_no = getattr(self.hub.batc_watcher, "batc_gsx_followme_no", False)
            if batc_sel and gate_tokens_match(batc_sel, target_gate) and batc_fm_no:
                self._log(
                    f"BeyondATC GSX flow already selected matching gate '{batc_sel}' (FollowMe=No) "
                    f"for {icao} Stand '{target_gate}'; instant sync complete!"
                )
                self._finish(run_id, True, f"GSX PRO: STAND {target_gate} SYNCED ✓", "#10B981")
                return

            # Fast 0.30s settle (critical for short-taxi airports like LFKC) before overriding GSX
            settle_end = time.time() + 0.30
            while time.time() < settle_end:
                with self._lock:
                    if run_id != self._active_run_id:
                        return
                time.sleep(0.05)
        elif initial_delay_sec > 0.0:
            end_wait = time.time() + initial_delay_sec
            while time.time() < end_wait:
                with self._lock:
                    if run_id != self._active_run_id:
                        return
                time.sleep(0.05)

        with self._seq_exec_lock:
            with self._lock:
                if run_id != self._active_run_id:
                    return
            self._run_sequence_locked(run_id, icao, target_gate, terminal_hint, manual, warp=warp)

    def _run_sequence_locked(
        self,
        run_id: int,
        icao: str,
        target_gate: str,
        terminal_hint: str,
        manual: bool,
        warp: bool = False
    ):
        sc = getattr(self.hub.backend, "simconnect_manager", None)
        if not sc or not sc.connected:
            self._log(f"Cannot sync GSX for {icao} Stand {target_gate}: SimConnect not connected.")
            self._finish(run_id, False, "GSX PRO: SIMCONNECT STANDBY (CLICK SYNC)", "#F59E0B")
            return

        panel_dir = self._find_gsx_panel_dir()
        if not panel_dir:
            self._log("GSX Panel directory not found on this PC.")
            self._finish(run_id, False, "GSX PRO: ADDON NOT FOUND", "#EF4444")
            return

        tokens = parse_gsx_gate_tokens(target_gate)
        target_tok = clean_gate_token(target_gate)
        if not tokens.get("number") or not target_tok:
            self._finish(run_id, False, f"GSX PRO: INVALID STAND ({target_gate})", "#EF4444")
            return

        self._log(
            f"Starting GSX sync (run={run_id}, manual={manual}, warp={warp}) for {icao} Stand '{target_gate}' "
            f"(token='{target_tok}', panel_dir='{panel_dir}')"
        )

        start_ts = time.time()
        timeout_sec = 26.0
        last_open_attempt_ts = 0.0
        last_action_ts = 0.0
        last_clicked_sig = None
        last_observed_sig = None

        gate_clicked = False
        warp_clicked = False
        handler_answered = False
        followme_answered = False
        visited_groups = set()
        pending_group_lbl: Optional[str] = None
        pending_group_sig: Any = None
        pending_group_tries: int = 0

        # Track the last `./menu` file modification timestamp so we NEVER click on a stale
        # `./menu` file left on disk from an earlier menu session or previous submenu page.
        init_st = self._read_menu_state(panel_dir)
        init_mtime = init_st["menu_mtime"]
        wait_for_mtime_after: Optional[float] = None
        if not init_st["is_open"] or (time.time() - init_mtime) >= 2.0:
            wait_for_mtime_after = init_mtime
        open_pulse_count = 0

        def open_gsx_menu(cur_mtime: float):
            nonlocal last_open_attempt_ts, last_action_ts, wait_for_mtime_after, open_pulse_count
            with self._lock:
                if run_id != self._active_run_id:
                    return
            open_pulse_count += 1
            self._log(
                f"Opening GSX Menu via L:FSDT_GSX_MENU_OPEN pulse #{open_pulse_count} (CHOICE_REQUEST_MENU = -2)..."
            )
            sc.set_lvar("L:FSDT_GSX_MENU_OPEN", 0.0)
            time.sleep(0.15)
            sc.set_lvars_batch([
                ("L:FSDT_GSX_MENU_CHOICE", -2.0),
                ("L:FSDT_GSX_MENU_OPEN", 1.0),
            ])
            last_open_attempt_ts = time.time()
            last_action_ts = last_open_attempt_ts
            wait_for_mtime_after = cur_mtime

        def select_menu_choice(choice_idx: int, reason: str, sig: Any, cur_mtime: float):
            nonlocal last_action_ts, last_clicked_sig, wait_for_mtime_after
            with self._lock:
                if run_id != self._active_run_id:
                    return
            self._log(f"Selecting menu choice [{choice_idx}] ({reason})")
            # IMPORTANT: Never send -1.0 before choice_idx! In GSX Pro (FSDT_GSX_Panel.js),
            # -1 is CHOICE_CANCEL which immediately dismisses the active menu in Couatl!
            sc.set_lvar("L:FSDT_GSX_MENU_CHOICE", float(choice_idx))
            last_action_ts = time.time()
            last_clicked_sig = sig
            wait_for_mtime_after = cur_mtime

        def close_gsx_menu_window(cancel_choice: bool = False, post_warp: bool = False):
            with self._lock:
                if run_id != self._active_run_id:
                    return
                self._last_finish_ts = time.time()
            if hasattr(sc, "close_gsx_panel"):
                sc.close_gsx_panel(cancel_choice=cancel_choice)
            else:
                if cancel_choice:
                    sc.set_lvar("L:FSDT_GSX_MENU_CHOICE", -1.0)
                sc.set_lvar("L:FSDT_GSX_MENU_OPEN", 0.0)
            if post_warp:
                mf_watch = os.path.join(panel_dir, "menu") if panel_dir else None
                last_mf_mtime = 0.0
                if mf_watch and os.path.exists(mf_watch):
                    try:
                        last_mf_mtime = os.path.getmtime(mf_watch)
                    except Exception:
                        pass
                pw_start = time.time()
                next_pulse_idx = 0
                pulse_times = (0.45, 0.95, 1.55, 2.25, 3.05)
                while (time.time() - pw_start) < 3.25:
                    time.sleep(0.12)
                    with self._lock:
                        if run_id != self._active_run_id:
                            return
                        self._last_finish_ts = time.time()
                    elapsed_pw = time.time() - pw_start
                    menu_reopened = False
                    if mf_watch and os.path.exists(mf_watch):
                        try:
                            cur_m = os.path.getmtime(mf_watch)
                            if cur_m > last_mf_mtime:
                                last_mf_mtime = cur_m
                                menu_reopened = True
                        except Exception:
                            pass
                    gsx_lv = getattr(sc, "gsx_lvars", {}) or {}
                    if gsx_lv.get("menu_open") == 1.0:
                        menu_reopened = True
                    fire_scheduled = (
                        next_pulse_idx < len(pulse_times)
                        and elapsed_pw >= pulse_times[next_pulse_idx]
                    )
                    if fire_scheduled:
                        next_pulse_idx += 1
                    if menu_reopened or fire_scheduled:
                        if hasattr(sc, "close_gsx_panel"):
                            sc.close_gsx_panel(cancel_choice=True)
                        else:
                            sc.set_lvar("L:FSDT_GSX_MENU_CHOICE", -1.0)
                            sc.set_lvar("L:FSDT_GSX_MENU_OPEN", 0.0)

        while time.time() - start_ts < timeout_sec:
            with self._lock:
                if run_id != self._active_run_id:
                    return

            if not sc.connected:
                self._finish(run_id, False, "GSX PRO: SIMCONNECT DISCONNECTED", "#EF4444")
                return

            now = time.time()
            st = self._read_menu_state(panel_dir)
            is_open = st["is_open"]
            title = st["title"]
            title_l = title.lower()
            options = st["options"]
            menu_mtime = st["menu_mtime"]
            non_empty_opts = [(i, o) for i, o in enumerate(options) if o]
            live_opts = st["live_options"]

            # --------------------------------------------------------------
            # 1. MENU CLOSED OR AWAITING FRESH `./menu` UPDATE FROM COUATL
            # --------------------------------------------------------------
            if wait_for_mtime_after is not None:
                if is_open and non_empty_opts and menu_mtime > wait_for_mtime_after:
                    # Couatl just wrote a fresh `./menu` page!
                    wait_for_mtime_after = None
                else:
                    if warp and warp_clicked:
                        if now - last_action_ts >= 0.35:
                            close_gsx_menu_window(cancel_choice=False, post_warp=True)
                            self._log(f"GSX Reposition (warp) sequence complete for {icao} Stand {target_gate}.")
                            self._finish(run_id, True, f"GSX PRO: REPOSITIONED TO {target_gate} ✓", "#10B981")
                            return
                    elif gate_clicked and not warp:
                        # We already clicked the target gate (and any handler / follow-me prompt).
                        # If Couatl hasn't written a new `./menu` page within `closed_wait`, the menu
                        # closed because the arrival stand activation sequence is complete!
                        closed_wait = 0.38 if followme_answered else (0.75 if handler_answered else 1.2)
                        if now - last_action_ts >= closed_wait:
                            close_gsx_menu_window(cancel_choice=False, post_warp=False)
                            self._log(
                                f"GSX Arrival sequence complete for {icao} Stand {target_gate} "
                                f"(handler={handler_answered}, followme_no={followme_answered})."
                            )
                            self._finish(run_id, True, f"GSX PRO: STAND {target_gate} SYNCED ✓", "#10B981")
                            return
                    else:
                        if open_pulse_count >= 4 and (now - start_ts) >= 8.0 and (now - last_open_attempt_ts) >= 1.4:
                            gsx_lv = getattr(sc, "gsx_lvars", {}) or {}
                            couatl_val = gsx_lv.get("couatl_started")
                            if couatl_val is not None and float(couatl_val) == 0.0 and menu_mtime <= 0.0:
                                self._log("Couatl engine is not running in MSFS (L:FSDT_GSX_COUATL_STARTED == 0); aborting sync.")
                                self._finish(run_id, False, "GSX PRO: COUATL NOT RUNNING", "#64748B")
                                return
                        if (now - last_action_ts) >= 1.0 and (now - last_open_attempt_ts) >= 1.2:
                            open_gsx_menu(menu_mtime)
                    time.sleep(0.04)
                    continue

            if not is_open or not non_empty_opts:
                if warp and warp_clicked:
                    if now - last_action_ts >= 0.35:
                        close_gsx_menu_window(cancel_choice=False, post_warp=True)
                        self._log(f"GSX Reposition (warp) sequence complete for {icao} Stand {target_gate}.")
                        self._finish(run_id, True, f"GSX PRO: REPOSITIONED TO {target_gate} ✓", "#10B981")
                        return
                elif gate_clicked and not warp:
                    closed_wait = 0.38 if followme_answered else (0.75 if handler_answered else 1.2)
                    if now - last_action_ts >= closed_wait:
                        close_gsx_menu_window(cancel_choice=False, post_warp=False)
                        self._log(
                            f"GSX Arrival sequence complete for {icao} Stand {target_gate} "
                            f"(handler={handler_answered}, followme_no={followme_answered})."
                        )
                        self._finish(run_id, True, f"GSX PRO: STAND {target_gate} SYNCED ✓", "#10B981")
                        return
                else:
                    if now - last_open_attempt_ts >= 1.2:
                        open_gsx_menu(menu_mtime)
                time.sleep(0.04)
                continue

            cur_sig = (title, tuple(options))
            if cur_sig != last_observed_sig:
                # Menu page just transitioned; if we had clicked a group folder on the previous menu,
                # mark that group as visited now that its submenu has opened.
                # IMPORTANT: For pagination options ("Next Page ►" / "More"), only record
                # (pending_group_sig, pending_group_lbl) so subsequent pages can also paginate!
                if pending_group_lbl and pending_group_sig is not None and cur_sig != pending_group_sig:
                    visited_groups.add((pending_group_sig, pending_group_lbl))
                    if not re.search(r'\b(?:NEXT\s*PAGE|MORE|NEXT)\b', pending_group_lbl, re.IGNORECASE):
                        visited_groups.add(pending_group_lbl)
                    pending_group_lbl = None
                    pending_group_sig = None
                    pending_group_tries = 0
                last_observed_sig = cur_sig
                time.sleep(0.03)
                now = time.time()

            # --------------------------------------------------------------
            # 1B. WARP MODE ("Just warp me there") AFTER GATE SELECTION
            # --------------------------------------------------------------
            # In GSX Pro, the flow is:
            #   Main Menu -> [0] "Reposition Aircraft" -> Gate selection ->
            #   "Request FollowMe?" menu -> [7] "Just warp me there"
            # Because "Just warp me there" lives inside the "Request FollowMe?" menu,
            # we must intercept and click it BEFORE the Follow-Me "No" handler below!
            if warp and gate_clicked:
                warp_idx = None
                for idx, opt in non_empty_opts:
                    if re.search(r'just\s+warp|warp\s+me', opt, re.IGNORECASE):
                        warp_idx = idx
                        break
                if warp_idx is not None:
                    warp_clicked = True
                    with self._lock:
                        if run_id == self._active_run_id:
                            self.status_label = f"GSX PRO: WARPING TO {target_gate}..."
                    select_menu_choice(warp_idx, f"Warp Aircraft -> '{options[warp_idx]}'", cur_sig, menu_mtime)
                    time.sleep(0.22)
                    self._finish(run_id, True, f"GSX PRO: REPOSITIONED TO {target_gate} ✓", "#10B981")
                    close_gsx_menu_window(cancel_choice=False, post_warp=True)
                    return

            # --------------------------------------------------------------
            # 2. FOLLOW-ME CAR PROMPT -> SELECT "Just warp me there" (IF WARP) OR "NO"
            # --------------------------------------------------------------
            is_followme_prompt = (
                "followme" in title_l
                or "follow me" in title_l
                or "follow-me" in title_l
                or (
                    len(non_empty_opts) == 2
                    and re.match(r'^yes\b', non_empty_opts[0][1], re.IGNORECASE)
                    and re.match(r'^no\b', non_empty_opts[1][1], re.IGNORECASE)
                )
            )
            if is_followme_prompt:
                if warp:
                    warp_idx = None
                    for idx, opt in non_empty_opts:
                        if re.search(r'just\s+warp|warp\s+me', opt, re.IGNORECASE):
                            warp_idx = idx
                            break
                    if warp_idx is not None:
                        warp_clicked = True
                        with self._lock:
                            if run_id == self._active_run_id:
                                self.status_label = f"GSX PRO: WARPING TO {target_gate}..."
                        select_menu_choice(warp_idx, f"FollowMe Menu Warp -> '{options[warp_idx]}'", cur_sig, menu_mtime)
                        time.sleep(0.22)
                        self._finish(run_id, True, f"GSX PRO: REPOSITIONED TO {target_gate} ✓", "#10B981")
                        close_gsx_menu_window(cancel_choice=False, post_warp=True)
                        return
                no_idx = None
                for idx, opt in non_empty_opts:
                    if re.match(r'^no\b', opt.strip(), re.IGNORECASE):
                        no_idx = idx
                        break
                if no_idx is None:
                    no_idx = 1 if len(options) > 1 else 0
                followme_answered = True
                with self._lock:
                    if run_id == self._active_run_id:
                        self.status_label = f"GSX PRO: SKIPPING FOLLOW-ME ({target_gate})..."
                select_menu_choice(no_idx, "FollowMe -> No", cur_sig, menu_mtime)
                time.sleep(0.06)
                continue

            # --------------------------------------------------------------
            # 3. HANDLER / OPERATOR SELECTION PROMPT -> SELECT "[GSX choice]" / "(default)"
            # --------------------------------------------------------------
            default_handler_re = re.compile(
                r'\[\s*gsx\s+choice\s*\]|\bgsx\s+choice\b|\(\s*default\s*\)|\bdefault\b',
                re.IGNORECASE
            )
            has_default_tag = any(default_handler_re.search(opt) for _, opt in non_empty_opts)
            is_operator_prompt = (
                "operator" in title_l
                or "handler" in title_l
                or "handling" in title_l
                or "catering" in title_l
                or (has_default_tag and "parking" not in title_l and "desired service" not in title_l)
            )
            if is_operator_prompt:
                chosen_idx = None
                chosen_lbl = ""
                for idx, opt in non_empty_opts:
                    if default_handler_re.search(opt):
                        chosen_idx = idx
                        chosen_lbl = opt
                        break
                if chosen_idx is None:
                    chosen_idx, chosen_lbl = non_empty_opts[0]
                handler_answered = True
                with self._lock:
                    if run_id == self._active_run_id:
                        self.status_label = f"GSX PRO: DEFAULT HANDLER SELECTED ({target_gate})..."
                select_menu_choice(chosen_idx, f"Handler -> '{chosen_lbl}'", cur_sig, menu_mtime)
                time.sleep(0.06)
                continue

            # --------------------------------------------------------------
            # 4. "CHANGE PARKING OR SERVICE" SUBMENU ("Change Facility [...]")
            # --------------------------------------------------------------
            cf_idx = None
            cf_opt = ""
            for idx, opt in non_empty_opts:
                if "change facility" in opt.lower():
                    cf_idx = idx
                    cf_opt = opt
                    break

            if cf_idx is not None:
                active_fac_gate = self._extract_change_facility_gate(cf_opt)
                active_fac_tok = clean_gate_token(active_fac_gate) if active_fac_gate else ""
                fac_matches = bool(active_fac_tok and gate_tokens_match(active_fac_tok, target_tok))
                if not fac_matches and active_fac_gate and tokens.get("number"):
                    af_t = parse_gsx_gate_tokens(active_fac_gate)
                    if (
                        (af_t.get("prefix") or "").upper() == (tokens.get("prefix") or "").upper()
                        and (af_t.get("number") or "").upper() == (tokens.get("number") or "").upper()
                        and (not af_t.get("suffix") or af_t.get("suffix", "").upper() in ((tokens.get("prefix") or "").upper(), "P", "G"))
                    ):
                        fac_matches = True

                if gate_clicked or fac_matches:
                    if warp:
                        warp_idx = None
                        for idx, opt in non_empty_opts:
                            if re.search(r'just\s+warp|warp\s+me', opt, re.IGNORECASE):
                                warp_idx = idx
                                break
                        if warp_idx is not None:
                            warp_clicked = True
                            with self._lock:
                                if run_id == self._active_run_id:
                                    self.status_label = f"GSX PRO: WARPING TO {target_gate}..."
                            select_menu_choice(warp_idx, f"Warp Aircraft -> '{options[warp_idx]}'", cur_sig, menu_mtime)
                            time.sleep(0.25)
                            close_gsx_menu_window(cancel_choice=False, post_warp=True)
                            self._finish(run_id, True, f"GSX PRO: REPOSITIONED TO {target_gate} ✓", "#10B981")
                            return
                    else:
                        # Target gate is already selected and active in GSX! Close menu and finish.
                        close_gsx_menu_window(cancel_choice=True, post_warp=False)
                        self._log(
                            f"GSX already has target Stand '{target_gate}' active in '{cf_opt}'; closing menu."
                        )
                        self._finish(run_id, True, f"GSX PRO: STAND {target_gate} SYNCED ✓", "#10B981")
                        return
                if not gate_clicked:
                    select_menu_choice(cf_idx, f"Change Facility -> '{cf_opt}'", cur_sig, menu_mtime)
                    time.sleep(0.06)
                    continue
                else:
                    close_gsx_menu_window(cancel_choice=True, post_warp=False)
                    self._finish(run_id, True, f"GSX PRO: STAND {target_gate} SYNCED ✓", "#10B981")
                    return

            # --------------------------------------------------------------
            # 5. MAIN GSX SERVICE MENU
            # --------------------------------------------------------------
            is_main_menu = (
                "select desired service" in title_l
                or any(
                    re.search(
                        r'request\s+(?:deboarding|boarding|catering|pushback|refuel)|select\s+another\s+parking|change\s+parking|activate\s+services|reposition\s+aircraft',
                        opt,
                        re.IGNORECASE
                    )
                    for _, opt in non_empty_opts
                )
            )
            if is_main_menu:
                if gate_clicked and not warp:
                    # Returned to main service menu after gate + handler + follow-me selection -> close menu & finish!
                    close_gsx_menu_window(cancel_choice=True, post_warp=False)
                    self._log(f"Returned to main GSX menu after selecting Stand {target_gate}; closing menu.")
                    self._finish(run_id, True, f"GSX PRO: STAND {target_gate} SYNCED ✓", "#10B981")
                    return

                # Check if GSX main menu already says "Activate Services at <target_gate>" while parked at the gate
                if not warp:
                    for idx, opt in non_empty_opts:
                        m_act = re.search(r'activate\s+services\s+at\s+(.+)$', opt, re.IGNORECASE)
                        if m_act:
                            act_tok = clean_gate_token(m_act.group(1))
                            if act_tok and gate_tokens_match(act_tok, target_tok):
                                close_gsx_menu_window(cancel_choice=True, post_warp=False)
                                self._log(f"GSX Main Menu already active at '{opt}'; closing menu.")
                                self._finish(run_id, True, f"GSX PRO: STAND {target_gate} SYNCED ✓", "#10B981")
                                return

                # Find the "Reposition Aircraft" (button 0 on Main Menu) or "Change parking" / "Select another parking" entry.
                # NEVER match "Customize this Parking position" or "Customize Airport positions" (button 9), which launches
                # the external Windows desktop GSX Customization editor!
                parking_idx = None
                if warp:
                    for idx, opt in non_empty_opts:
                        if re.search(r'reposition\s+aircraft', opt, re.IGNORECASE):
                            parking_idx = idx
                            break
                if parking_idx is None:
                    for idx, opt in non_empty_opts:
                        if re.search(
                            r'customize|warp|revoke|free\s+this|towing|progressive|show\s+me|reset\s+position',
                            opt,
                            re.IGNORECASE
                        ):
                            continue
                        if re.search(
                            r'change\s+parking|select\s+another\s+parking|another\s+gate|change\s+gate|arrival\s+gate|select\s+gate|activate\s+services|change\s+facility|reposition\s+aircraft|\bparking\s+or\s+service\b',
                            opt,
                            re.IGNORECASE
                        ):
                            parking_idx = idx
                            break
                if parking_idx is not None:
                    select_menu_choice(parking_idx, f"Main Menu -> '{options[parking_idx]}'", cur_sig, menu_mtime)
                    time.sleep(0.06)
                    continue

            # --------------------------------------------------------------
            # 6. SAFETY GUARD AGAINST "CUSTOMIZE AIRPORT" SUBMENU
            # --------------------------------------------------------------
            if not is_main_menu and any(re.search(r'customize\s+airport', opt, re.IGNORECASE) for _, opt in non_empty_opts):
                safe_idx = None
                for idx, opt in non_empty_opts:
                    if not re.search(r'customize', opt, re.IGNORECASE):
                        safe_idx = idx
                        break
                if safe_idx is not None and not gate_clicked:
                    gate_clicked = True
                    select_menu_choice(safe_idx, f"Confirm Gate Action -> '{options[safe_idx]}'", cur_sig, menu_mtime)
                    time.sleep(0.06)
                    continue
                else:
                    close_gsx_menu_window(cancel_choice=True, post_warp=False)
                    self._finish(run_id, True, f"GSX PRO: STAND {target_gate} SYNCED ✓", "#10B981")
                    return

            # --------------------------------------------------------------
            # 7. PARKING / TERMINAL / GATE SELECTION MENU
            # --------------------------------------------------------------
            if not gate_clicked:
                # 7A. Check if target gate is directly in `./menu` options
                direct_idx = self._find_exact_gate_option(non_empty_opts, target_gate, tokens)
                if direct_idx is not None:
                    gate_clicked = True
                    with self._lock:
                        if run_id == self._active_run_id:
                            self.status_label = f"GSX PRO: STAND {target_gate} SELECTED..."
                    select_menu_choice(direct_idx, f"Direct Menu Gate Match -> '{options[direct_idx]}'", cur_sig, menu_mtime)
                    time.sleep(0.06)
                    continue

                # 7B. Check if target gate is in `./menu_live.html`
                if live_opts:
                    live_idx = self._find_exact_gate_option(live_opts, target_gate, tokens)
                    if live_idx is not None:
                        gate_clicked = True
                        with self._lock:
                            if run_id == self._active_run_id:
                                self.status_label = f"GSX PRO: STAND {target_gate} SELECTED..."
                        select_menu_choice(live_idx, f"Live Search Gate Match -> choice {live_idx}", cur_sig, menu_mtime)
                        time.sleep(0.06)
                        continue

                # 7C. Hierarchical Terminal / Prefix / Numeric Range Navigation in `./menu`
                if pending_group_lbl and pending_group_sig == cur_sig:
                    if pending_group_tries >= 2:
                        visited_groups.add((cur_sig, pending_group_lbl))
                        if not re.search(r'\b(?:NEXT\s*PAGE|MORE|NEXT)\b', pending_group_lbl, re.IGNORECASE):
                            visited_groups.add(pending_group_lbl)
                        pending_group_lbl = None
                        pending_group_sig = None
                        pending_group_tries = 0

                grp = self._find_group_or_range_option(options, tokens, terminal_hint, visited_groups, cur_sig=cur_sig)
                if grp is not None:
                    g_idx, g_lbl = grp
                    if pending_group_lbl == g_lbl and pending_group_sig == cur_sig:
                        pending_group_tries += 1
                    else:
                        pending_group_lbl = g_lbl
                        pending_group_sig = cur_sig
                        pending_group_tries = 1
                    select_menu_choice(g_idx, f"Group/Range Drilldown -> '{g_lbl}' (try {pending_group_tries})", cur_sig, menu_mtime)
                    time.sleep(0.06)
                    continue

            time.sleep(0.05)

        close_gsx_menu_window(cancel_choice=True, post_warp=False)
        self._log(f"GSX Arrival sync timed out after {timeout_sec:.0f}s for {icao} Stand {target_gate}.")
        self._finish(run_id, False, f"GSX PRO: RETRY SYNC ({target_gate})", "#F59E0B")


class BeyondATCWatcher:
    """
    Real-time incremental tail watcher on BeyondATC's Player.log:
      %USERPROFILE%\\AppData\\LocalLow\\Skirmish Mode Games, Inc\\BeyondATC\\Player.log
    """
    def __init__(self, hub: "InteroperabilityHub"):
        self.hub = hub
        self.log_path = os.path.join(
            os.environ.get("USERPROFILE", ""),
            "AppData", "LocalLow", "Skirmish Mode Games, Inc", "BeyondATC", "Player.log"
        )
        self._last_size = -1
        self._last_mtime = 0.0
        self._file_offset = 0
        self._pending_gsx_block: List[str] = []
        self._expecting_taxi_instruction = False
        self._expecting_dep_taxi_instruction = False
        self.gsx_departure_handling = False
        self.gsx_arrival_handling = False
        self.is_active = False

        # Current BATC flight session state
        self.player_callsign: str = ""
        self.batc_dep_icao: str = ""
        self.batc_arr_icao: str = ""
        self.batc_dep_rwy: str = ""
        self.batc_arr_rwy: str = ""
        self.batc_dep_gate: str = ""
        self.batc_arr_gate: str = ""
        self.batc_dep_via: List[str] = []
        self.batc_arr_via: List[str] = []
        self.batc_gsx_awaiting_stand_choice: bool = False
        self.batc_gsx_selected_gate: str = ""
        self.batc_gsx_followme_no: bool = False
        self._re_gsx_menu_choice = re.compile(
            r'\[GSX\]\s*Setting menu choice to:\s*\d+\s*\(Title:\s*(.*?)\s*\)',
            re.IGNORECASE
        )

        # Pre-compiled regex patterns matching real BeyondATC Player.log output
        self._re_gsx_cfg = re.compile(
            r'\[GSX\]\s*Integration enabled\.\.\s*Departure Handling:\s*(True|False)\s*\|\s*Arrival Handling:\s*(True|False)',
            re.IGNORECASE
        )
        self._re_gsx_alloc_cfg = re.compile(
            r'Allocate Gates with GSX:\s*(True|False)',
            re.IGNORECASE
        )
        self._re_callsign = re.compile(r'^Player Callsign:\s*(\S+)$', re.IGNORECASE)
        self._re_dep_apt = re.compile(r'^Departure Airport:\s*([A-Z0-9]{4})$', re.IGNORECASE)
        self._re_arr_apt = re.compile(r'^Destination Airport:\s*([A-Z0-9]{4})$', re.IGNORECASE)
        self._re_dep_rwy = re.compile(r'^Departure Runway:\s*(\d{2}[LRC]?)$', re.IGNORECASE)
        self._re_arr_rwy = re.compile(r'^Arrival Runway:\s*(\d{2}[LRC]?)$', re.IGNORECASE)
        self._re_sid_rwy = re.compile(r'\[Procedures\]\s*SID is \S+.*?using runway\s+(\d{2}[LRC]?)\b', re.IGNORECASE)
        self._re_star_rwy = re.compile(r'\[Procedures\]\s*(?:STAR|Approach) is .*?runway\s+(\d{2}[LRC]?)\b', re.IGNORECASE)
        self._re_rwy_alloc = re.compile(r'\[RunwayAlloc\]\s*(\S+)\s+.*?result=(\d{2}[LRC]?)\b', re.IGNORECASE)

        self._re_cpdlc_stand = re.compile(r'^\s*Stand Number:\s*([A-Z0-9\s\-_]+)$', re.IGNORECASE)
        self._re_clearance_req_stand = re.compile(
            r'\[Instruction\].*?\b(?:(?:Gate|Stand|Ramp|Parking|Dock)\s+)+([A-Z]{0,4}\s*\d+[A-Z]?)\s*,\s*request\s+(?:IFR\s+clearance|pushback|startup|taxi)',
            re.IGNORECASE
        )
        self._re_instruction_gate = re.compile(
            r'\[Instruction\].*?\b(?:(?:Gate|Stand|Ramp|Parking|Dock)\s+)+([A-Z]{0,4}\s*\d+[A-Z]?)\b.*?\btaxi\b',
            re.IGNORECASE
        )
        self._re_taxi_to_gate = re.compile(
            r'\[Instruction\].*?\btaxi\s+(?:to\s+)?(?:(?:Gate|Stand|Ramp|Parking|Dock)\s+)+([A-Z]{0,4}\s*\d+[A-Z]?)\b',
            re.IGNORECASE
        )
        self._re_instruction_rwy = re.compile(
            r'\[Instruction\].*?\brunway\s+(\d{2}[LRC]?)\b',
            re.IGNORECASE
        )
        self._re_taxi_via = re.compile(
            r'\[Instruction\].*?\btaxi\b.*?\bvia\s+([^.]+)',
            re.IGNORECASE
        )
        self._re_twy_token = re.compile(
            r'^(?:INNER|OUTER|NORTH|SOUTH|EAST|WEST|MAIN|LOOP|LINK\s*[A-Z0-9]+|[A-Z]{1,3}\d{0,2}[A-Z]?)$',
            re.IGNORECASE
        )

    def poll(self):
        if not os.path.exists(self.log_path):
            self.is_active = False
            return

        try:
            st = os.stat(self.log_path)
            age_sec = time.time() - st.st_mtime
            # Consider BATC active if Player.log was modified within the last 3 hours
            self.is_active = (age_sec < 10800)

            # Handle initial attach or file truncation (new BATC launch)
            if st.st_size < self._file_offset or self._last_size == -1:
                self._pending_gsx_block.clear()
                with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                    full_text = f.read()
                    self._file_offset = f.tell()
                    self._last_size = st.st_size
                    self._last_mtime = st.st_mtime

                # 1. Check GSX integration flags from startup header
                for m in self._re_gsx_cfg.finditer(full_text):
                    self.gsx_departure_handling = (m.group(1).lower() == "true")
                    self.gsx_arrival_handling = (m.group(2).lower() == "true")
                    self.hub.set_batc_gsx_flags(self.gsx_departure_handling, self.gsx_arrival_handling)
                for m2 in self._re_gsx_alloc_cfg.finditer(full_text):
                    alloc_on = (m2.group(1).lower() == "true")
                    self.gsx_arrival_handling = alloc_on
                    self.hub.set_batc_gsx_flags(self.gsx_departure_handling, self.gsx_arrival_handling)

                # 2. Process from the latest "**********FLIGHT STARTS BELOW***********" marker
                marker = "**********FLIGHT STARTS BELOW***********"
                idx = full_text.rfind(marker)
                session_text = full_text[idx:] if idx != -1 else full_text[-65536:]
                for raw_line in session_text.splitlines():
                    self._process_line(raw_line.strip())
                return

            if st.st_size == self._file_offset:
                return

            with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(self._file_offset)
                new_text = f.read()
                self._file_offset = f.tell()
                self._last_size = st.st_size
                self._last_mtime = st.st_mtime

            for raw_line in new_text.splitlines():
                self._process_line(raw_line.strip())

        except Exception as exc:
            print(f"[BeyondATCWatcher] Poll warning: {exc}")

    def _is_matching_active_flight(self) -> bool:
        """Returns True only if the current Player.log session matches GateFinder's loaded departure & arrival ICAOs."""
        gf_dep = self.hub.get_phase_icao("departure")
        gf_arr = self.hub.get_phase_icao("arrival")
        if not gf_dep or not gf_arr:
            return False
        if not self.batc_dep_icao or not self.batc_arr_icao:
            return False
        return self.batc_dep_icao == gf_dep and self.batc_arr_icao == gf_arr

    def _extract_taxi_via_tokens(self, line: str) -> List[str]:
        if not line or not re.search(r'\b(?:taxi|hold\s+short|holding\s+point)\b', line, re.IGNORECASE):
            return []
        if re.search(r'\b(?:cleared\s+to\b.*?\bdeparture|climb\s+via\s+sid|descend\s+via\s+star)\b', line, re.IGNORECASE):
            return []

        tokens: List[str] = []
        stop_words = {
            "TAXI", "HOLD", "HOLDING", "RUNWAY", "RWY", "RAMP", "GATE", "STAND", "DOCK",
            "PARKING", "TO", "VIA", "CROSS", "CONTACT", "MONITOR", "WHEN", "READY",
            "DEPARTURE", "ARRIVAL", "SID", "STAR", "CONTINUE", "SHORT", "OF"
        }
        cs_norm = self.player_callsign.replace(" ", "").upper() if self.player_callsign else ""

        for m in re.finditer(r'\bvia\s+([^.]+)', line, re.IGNORECASE):
            raw_tail = m.group(1).strip()
            for raw_part in re.split(r'[,;]+|\band\b', raw_tail, flags=re.IGNORECASE):
                part = re.split(
                    r'\b(?:taxi|hold\s+short|holding\s+point|cross\s+runway|runway|rwy|to\s+holding|to\s+gate|to\s+stand|to\s+ramp|to\s+parking|contact|when\s+ready)\b',
                    raw_part,
                    maxsplit=1,
                    flags=re.IGNORECASE
                )[0].strip()
                tok = re.sub(r'\s+', ' ', part).upper()
                if not tok:
                    if raw_part.strip():
                        break
                    continue
                if cs_norm and tok.replace(" ", "") == cs_norm:
                    break
                first_word = tok.split()[0]
                if first_word in stop_words:
                    break
                if self._re_twy_token.match(tok):
                    m_lnk = re.match(r'^LINK\s*([A-Z0-9]+)$', tok)
                    if m_lnk:
                        tok = f"LINK {m_lnk.group(1)}"
                    if not tokens or tokens[-1] != tok:
                        tokens.append(tok)
                else:
                    break

        m_hp = re.search(r'\bholding\s+point\s+([A-Z]{1,3}\d{0,2}[A-Z]?)\b', line, re.IGNORECASE)
        if m_hp:
            hp_tok = m_hp.group(1).strip().upper()
            if hp_tok not in stop_words and self._re_twy_token.match(hp_tok):
                if not tokens or tokens[-1] != hp_tok:
                    tokens.append(hp_tok)

        return tokens

    def resync_current_flight(self):
        """Re-applies cached BATC runway and gate ONLY if BATC's active flight matches the loaded flight plan."""
        if not self._is_matching_active_flight():
            return
        dep_icao = self.hub.get_phase_icao("departure")
        arr_icao = self.hub.get_phase_icao("arrival")
        if dep_icao and self.batc_dep_icao == dep_icao:
            if self.batc_dep_rwy:
                self.hub.on_external_atc_runway_detected("departure", dep_icao, self.batc_dep_rwy, GateSource.BEYOND_ATC)
            if self.batc_dep_via:
                self.hub.on_external_atc_taxi_via_detected("departure", dep_icao, self.batc_dep_via, GateSource.BEYOND_ATC)
            dep_dec = self.hub.active_decision.get("departure")
            if self.batc_dep_gate and not (dep_dec and dep_dec.source == GateSource.USER_MANUAL):
                self.hub.on_external_atc_gate_detected("departure", dep_icao, self.batc_dep_gate, GateSource.BEYOND_ATC)
        if arr_icao and self.batc_arr_icao == arr_icao:
            if self.batc_arr_rwy:
                self.hub.on_external_atc_runway_detected("arrival", arr_icao, self.batc_arr_rwy, GateSource.BEYOND_ATC)
            if self.batc_arr_via:
                self.hub.on_external_atc_taxi_via_detected("arrival", arr_icao, self.batc_arr_via, GateSource.BEYOND_ATC)
            if self.batc_arr_gate:
                self.hub.on_external_atc_gate_detected("arrival", arr_icao, self.batc_arr_gate, GateSource.BEYOND_ATC)

    def _process_line(self, line: str):
        if not line:
            return

        if "**********FLIGHT STARTS BELOW***********" in line or "--------------------FLIGHT INFORMATION--------------------" in line:
            self.player_callsign = ""
            self.batc_dep_icao = ""
            self.batc_arr_icao = ""
            self.batc_dep_rwy = ""
            self.batc_arr_rwy = ""
            self.batc_dep_gate = ""
            self.batc_arr_gate = ""
            self.batc_dep_via = []
            self.batc_arr_via = []
            self._pending_gsx_block.clear()
            return

        # 1. Detect BATC's internal GSX integration setting
        m_cfg = self._re_gsx_cfg.search(line)
        if m_cfg:
            self.gsx_departure_handling = (m_cfg.group(1).lower() == "true")
            self.gsx_arrival_handling = (m_cfg.group(2).lower() == "true")
            self.hub.set_batc_gsx_flags(self.gsx_departure_handling, self.gsx_arrival_handling)
            return

        m_alloc_cfg = self._re_gsx_alloc_cfg.search(line)
        if m_alloc_cfg:
            self.gsx_arrival_handling = (m_alloc_cfg.group(1).lower() == "true")
            self.hub.set_batc_gsx_flags(self.gsx_departure_handling, self.gsx_arrival_handling)
            return

        # 1b. Flight Information Header & Procedure Runways
        m_cs = self._re_callsign.match(line)
        if m_cs:
            self.player_callsign = m_cs.group(1).strip().upper()
            return

        m_da = self._re_dep_apt.match(line)
        if m_da:
            self.batc_dep_icao = m_da.group(1).strip().upper()
            return

        m_aa = self._re_arr_apt.match(line)
        if m_aa:
            self.batc_arr_icao = m_aa.group(1).strip().upper()
            return

        # NOTE: We intentionally do NOT trigger on_external_atc_runway_detected on BATC's
        # internal startup header ("Departure Runway:", "Arrival Runway:", "[Procedures]", "[RunwayAlloc]")
        # so that GateFinder stays on SimBrief's predicted runway until the exact moment
        # the ATC controller actually issues the clearance via [Instruction] or CPDLC!
        if "Departure Clearance" in line:
            self._in_cpdlc_pdc = True
            return
        if getattr(self, "_in_cpdlc_pdc", False):
            m_cpdlc_rwy = self._re_dep_rwy.match(line)
            if m_cpdlc_rwy:
                rwy = m_cpdlc_rwy.group(1).strip().upper()
                self.batc_dep_rwy = rwy
                if self._is_matching_active_flight() and self.batc_dep_icao:
                    self.hub.on_external_atc_runway_detected("departure", self.batc_dep_icao, rwy, GateSource.BEYOND_ATC)
                self._in_cpdlc_pdc = False
                return

        # 2. Multi-line block:
        #    [GSX] Execute Gate Assignment Flow for gate:
        #    Name:F
        #    Number:37
        #    Suffix:NONE
        if "[GSX] Execute Gate Assignment Flow for gate:" in line:
            self._pending_gsx_block = ["START"]
            self.batc_gsx_awaiting_stand_choice = False
            self.batc_gsx_selected_gate = ""
            self.batc_gsx_followme_no = False
            if hasattr(self.hub, "batc_gsx_flow_started_event"):
                self.hub.batc_gsx_flow_started_event.set()
            if hasattr(self.hub, "batc_gsx_flow_done_event"):
                self.hub.batc_gsx_flow_done_event.clear()
            return

        if "[GSX] Found gate menu." in line:
            self.batc_gsx_awaiting_stand_choice = True
            return

        if "[GSX] Setting menu choice to:" in line:
            m_gsx_ch = self._re_gsx_menu_choice.search(line)
            if m_gsx_ch:
                ch_title = m_gsx_ch.group(1).strip()
                if self.batc_gsx_awaiting_stand_choice:
                    self.batc_gsx_awaiting_stand_choice = False
                    self.batc_gsx_selected_gate = re.split(r'\s+-\s+', ch_title, maxsplit=1)[0].strip()
                elif ch_title.lower() == "no":
                    self.batc_gsx_followme_no = True
            return

        if any(k in line for k in (
            "[GSX] Completed Gate Assignment Flow",
            "[GSX] Gate not found",
            "[GSX] Failed",
            "[GSX] Aborting",
        )):
            if "[GSX] Gate not found" in line:
                self.batc_gsx_awaiting_stand_choice = False
            if hasattr(self.hub, "batc_gsx_flow_done_event"):
                self.hub.batc_gsx_flow_done_event.set()
            return

        if self._pending_gsx_block:
            if line.startswith(("Name:", "Number:", "Suffix:")):
                self._pending_gsx_block.append(line)
                if len(self._pending_gsx_block) >= 4:
                    self._finalize_gsx_block()
                return
            else:
                self._pending_gsx_block.clear()

        # 3. Detect arrival or departure taxi clearance script trigger
        if "AICommunicationSystem.IFR.TaxiToGateInstructionFinal" in line:
            self._expecting_taxi_instruction = True
            self._expecting_dep_taxi_instruction = False
            return
        if "TaxiToRunwayInstruction" in line or "RunwayCrossingScript" in line:
            self._expecting_dep_taxi_instruction = True
            self._expecting_taxi_instruction = False
            return

        if "[Instruction]" in line:
            # 3a. Check if player is requesting IFR clearance from a specific stand
            m_req_stand = self._re_clearance_req_stand.search(line)
            if m_req_stand:
                gate_raw = m_req_stand.group(1).strip()
                self.batc_dep_gate = gate_raw
                if self._is_matching_active_flight() and self.batc_dep_icao and gate_raw:
                    self.hub.on_external_atc_gate_detected(
                        phase="departure",
                        icao=self.batc_dep_icao,
                        raw_gate=gate_raw,
                        source=GateSource.BEYOND_ATC
                    )

            # 3b. Check if ATC is giving a Runway instruction (Clearance, Taxi to Runway, Approach, Landing)
            m_rwy = self._re_instruction_rwy.search(line)
            if m_rwy:
                rwy = m_rwy.group(1).strip().upper()
                line_low = line.lower()
                if any(k in line_low for k in ("departure", "holding point", "hold short", "backtrack", "line up", "takeoff", "squawk")) or getattr(self, "_expecting_dep_taxi_instruction", False):
                    rwy_phase = "departure"
                elif any(k in line_low for k in ("approach", "arrival", "expect", "vectors", "descend", "cleared to land", "landing")):
                    rwy_phase = "arrival"
                else:
                    rwy_phase = self.hub.infer_active_phase()
                if rwy_phase == "departure":
                    self.batc_dep_rwy = rwy
                    rwy_icao = self.batc_dep_icao
                else:
                    self.batc_arr_rwy = rwy
                    rwy_icao = self.batc_arr_icao
                if self._is_matching_active_flight() and rwy_icao:
                    self.hub.on_external_atc_runway_detected(rwy_phase, rwy_icao, rwy, GateSource.BEYOND_ATC)

            # 3c. Check if ATC is giving a Taxi instruction with explicit 'via ...' routing or Gate assignment
            via_tokens = self._extract_taxi_via_tokens(line)
            m_taxi = self._re_taxi_to_gate.search(line) or self._re_instruction_gate.search(line)
            if via_tokens and not m_taxi:
                line_low = line.lower()
                if any(k in line_low for k in ("holding point", "hold short", "runway", "line up", "backtrack")) or getattr(self, "_expecting_dep_taxi_instruction", False):
                    via_phase = "departure"
                elif self._expecting_taxi_instruction:
                    via_phase = "arrival"
                else:
                    via_phase = self.hub.infer_active_phase()
                self._expecting_dep_taxi_instruction = False
                via_icao = self.batc_dep_icao if via_phase == "departure" else self.batc_arr_icao
                if via_phase == "departure":
                    self.batc_dep_via = via_tokens
                else:
                    self.batc_arr_via = via_tokens
                if self._is_matching_active_flight() and via_icao:
                    self.hub.on_external_atc_taxi_via_detected(via_phase, via_icao, via_tokens, GateSource.BEYOND_ATC)

            if m_taxi:
                gate_raw = m_taxi.group(1).strip()
                # If preceded by TaxiToGateInstructionFinal or aircraft is near arrival, treat as arrival
                phase = "arrival" if self._expecting_taxi_instruction else self.hub.infer_active_phase()
                self._expecting_taxi_instruction = False
                if phase == "arrival":
                    self.batc_arr_gate = gate_raw
                    if via_tokens:
                        self.batc_arr_via = via_tokens
                    icao = self.batc_arr_icao
                    if self.gsx_arrival_handling and hasattr(self.hub, "batc_gsx_flow_done_event"):
                        # BeyondATC initiates [GSX] Execute Gate Assignment Flow ~3-4s after issuing the taxi instruction
                        self.batc_gsx_awaiting_stand_choice = False
                        self.batc_gsx_selected_gate = ""
                        self.batc_gsx_followme_no = False
                        if hasattr(self.hub, "batc_gsx_flow_started_event"):
                            self.hub.batc_gsx_flow_started_event.clear()
                        self.hub.batc_gsx_flow_done_event.clear()
                else:
                    self.batc_dep_gate = gate_raw
                    if via_tokens:
                        self.batc_dep_via = via_tokens
                    icao = self.batc_dep_icao
                if self._is_matching_active_flight() and icao:
                    if via_tokens:
                        self.hub.on_external_atc_taxi_via_detected(phase, icao, via_tokens, GateSource.BEYOND_ATC)
                    if gate_raw:
                        self.hub.on_external_atc_gate_detected(
                            phase=phase,
                            icao=icao,
                            raw_gate=gate_raw,
                            source=GateSource.BEYOND_ATC
                        )
                return

        # 4. Detect CPDLC Pre-Departure Clearance Stand confirmation
        m_cpdlc = self._re_cpdlc_stand.match(line)
        if m_cpdlc:
            gate_raw = m_cpdlc.group(1).strip()
            self.batc_dep_gate = gate_raw
            if self._is_matching_active_flight() and self.batc_dep_icao and gate_raw:
                self.hub.on_external_atc_gate_detected(
                    phase="departure",
                    icao=self.batc_dep_icao,
                    raw_gate=gate_raw,
                    source=GateSource.BEYOND_ATC
                )

    def _finalize_gsx_block(self):
        name_val, num_val, suf_val = "", "", ""
        for item in self._pending_gsx_block[1:]:
            if item.startswith("Name:"):
                name_val = item.split(":", 1)[1].strip()
            elif item.startswith("Number:"):
                num_val = item.split(":", 1)[1].strip()
            elif item.startswith("Suffix:"):
                suf_val = item.split(":", 1)[1].strip()
        self._pending_gsx_block.clear()

        if name_val.upper() in ("NONE", "PARKING", "GATE", "STAND"):
            name_val = ""
        if suf_val.upper() == "NONE":
            suf_val = ""

        gate_str = f"{name_val} {num_val}{suf_val}".strip()
        if gate_str:
            self.batc_arr_gate = gate_str
            if self._is_matching_active_flight() and self.batc_arr_icao:
                self.hub.on_external_atc_gate_detected(
                    phase="arrival",
                    icao=self.batc_arr_icao,
                    raw_gate=gate_str,
                    source=GateSource.BEYOND_ATC
                )


class SayIntentionsWatcher:
    """
    Watches %LOCALAPPDATA%\\SayIntentionsAI\\flight.json for:
      - `flight_details.api_key` (used for outbound SAPI `assignGate` calls)
      - `flight_details.current_flight.assigned_gate` (+ lat/lon)
      - `flight_details.current_flight.flight_plan_arriving_runway` / `flight_plan_departing_runway`
    """
    def __init__(self, hub: "InteroperabilityHub"):
        self.hub = hub
        self.json_path = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "SayIntentionsAI", "flight.json"
        )
        self._last_mtime = 0.0
        self.api_key: str = ""
        self.is_active: bool = False
        self._last_observed_gate: Dict[str, str] = {"departure": "", "arrival": ""}
        self._last_observed_rwy: Dict[str, str] = {"departure": "", "arrival": ""}
        self._last_sapi_pushed: Dict[str, str] = {"departure": "", "arrival": ""}

    def record_outbound_sapi_gate(self, phase: str, icao: str, raw_gate: str):
        if phase in ("departure", "arrival") and icao and raw_gate:
            tok = clean_gate_token(raw_gate)
            if tok:
                self._last_sapi_pushed[phase] = f"{icao.strip().upper()}:{tok}"

    def get_api_key(self) -> str:
        cfg_key = str(self.hub.config.settings.get("sayintentions_api_key") or "").strip()
        if cfg_key:
            self.api_key = cfg_key
            return self.api_key
        if self.api_key:
            return self.api_key
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                fd = data.get("flight_details") or {}
                self.api_key = str(fd.get("api_key") or "").strip()
            except Exception:
                pass
        return self.api_key

    def resync_current_flight(self):
        """Force re-read of flight.json when a new flight is loaded in GateFinder."""
        self._last_mtime = 0.0
        self._last_observed_gate = {"departure": "", "arrival": ""}
        self._last_observed_rwy = {"departure": "", "arrival": ""}
        self.poll()

    def _resolve_gate_phase_and_icao(
        self,
        assigned_gate: str,
        gate_lat: Optional[float],
        gate_lon: Optional[float],
        cur_apt: str,
        dep_icao: str,
        arr_icao: str,
        dest_icao: str
    ) -> Tuple[str, str]:
        gate_tok = clean_gate_token(assigned_gate)
        # 1. If SayIntentions provides non-zero GPS coordinates for assigned_gate, match against airport centers
        if gate_lat is not None and gate_lon is not None and (abs(gate_lat) > 0.01 or abs(gate_lon) > 0.01):
            try:
                from network import haversine
                fd = self.hub.backend.current_flight_data or {}
                dep_d = fd.get("departure") or {}
                arr_d = fd.get("arrival") or {}
                dep_c = (dep_d.get("chart_data") or {})
                arr_c = (arr_d.get("chart_data") or {})
                d_lat = dep_c.get("center_lat") if dep_c.get("center_lat") is not None else dep_d.get("lat")
                d_lon = dep_c.get("center_lon") if dep_c.get("center_lon") is not None else dep_d.get("lon")
                a_lat = arr_c.get("center_lat") if arr_c.get("center_lat") is not None else arr_d.get("lat")
                a_lon = arr_c.get("center_lon") if arr_c.get("center_lon") is not None else arr_d.get("lon")
                if d_lat is not None and d_lon is not None and dep_icao:
                    if haversine(gate_lat, gate_lon, float(d_lat), float(d_lon)) < 25000.0:
                        return "departure", dep_icao
                if a_lat is not None and a_lon is not None and arr_icao:
                    if haversine(gate_lat, gate_lon, float(a_lat), float(a_lon)) < 25000.0:
                        return "arrival", arr_icao
            except Exception:
                pass

        # 2. Check if this gate matches an outbound SAPI push from GateFinder
        if arr_icao and self._last_sapi_pushed.get("arrival") == f"{arr_icao}:{gate_tok}":
            if not dep_icao or self._last_sapi_pushed.get("departure") != f"{dep_icao}:{gate_tok}":
                return "arrival", arr_icao
        if dep_icao and self._last_sapi_pushed.get("departure") == f"{dep_icao}:{gate_tok}":
            if not arr_icao or self._last_sapi_pushed.get("arrival") != f"{arr_icao}:{gate_tok}":
                return "departure", dep_icao

        # 3. Use current_airport and live aircraft phase inference
        inferred = self.hub.infer_active_phase()
        if inferred == "arrival" or (arr_icao and cur_apt == arr_icao):
            return "arrival", (arr_icao or dest_icao)
        if dep_icao and cur_apt == dep_icao:
            return "departure", dep_icao

        return "arrival", (arr_icao or dest_icao)

    def poll(self):
        if not os.path.exists(self.json_path):
            self.is_active = False
            return

        try:
            st = os.stat(self.json_path)
            age_sec = time.time() - st.st_mtime
            self.is_active = (age_sec < 10800)
            if st.st_mtime <= self._last_mtime:
                return
            self._last_mtime = st.st_mtime

            with open(self.json_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)

            fd = data.get("flight_details") or {}
            ak = str(fd.get("api_key") or "").strip()
            if ak:
                self.api_key = ak

            cf = fd.get("current_flight") or {}
            dest_icao = str(cf.get("flight_destination") or "").strip().upper()
            orig_icao = str(cf.get("flight_origin") or cf.get("flight_plan_origin") or "").strip().upper()
            cur_apt = str(fd.get("current_airport") or "").strip().upper()

            arr_icao = self.hub.get_phase_icao("arrival")
            dep_icao = self.hub.get_phase_icao("departure")

            # Ignore SayIntentions flight.json if it still belongs to a different flight plan
            if orig_icao and dep_icao and orig_icao != dep_icao:
                return
            if dest_icao and arr_icao and dest_icao != arr_icao:
                return

            # 1. Check SayIntentions Runways (Departure & Arrival)
            si_dep_rwy = str(cf.get("flight_plan_departing_runway") or "").strip().upper()
            if si_dep_rwy and dep_icao and (not orig_icao or orig_icao == dep_icao):
                rwy_key = f"{dep_icao}:{si_dep_rwy}"
                if self._last_observed_rwy.get("departure") != rwy_key:
                    self._last_observed_rwy["departure"] = rwy_key
                    self.hub.on_external_atc_runway_detected("departure", dep_icao, si_dep_rwy, GateSource.SAY_INTENTIONS)

            si_arr_rwy = str(cf.get("flight_plan_arriving_runway") or "").strip().upper()
            if si_arr_rwy and arr_icao and (not dest_icao or dest_icao == arr_icao):
                rwy_key = f"{arr_icao}:{si_arr_rwy}"
                if self._last_observed_rwy.get("arrival") != rwy_key:
                    self._last_observed_rwy["arrival"] = rwy_key
                    self.hub.on_external_atc_runway_detected("arrival", arr_icao, si_arr_rwy, GateSource.SAY_INTENTIONS)

            # 2. Check SayIntentions Assigned Gate
            assigned_gate = str(cf.get("assigned_gate") or "").strip()
            if not assigned_gate:
                return

            # Parse optional GPS coordinates provided by SayIntentions
            gate_lat, gate_lon = None, None
            try:
                if cf.get("assigned_gate_lat"):
                    gate_lat = float(cf["assigned_gate_lat"])
                if cf.get("assigned_gate_lon"):
                    gate_lon = float(cf["assigned_gate_lon"])
            except (ValueError, TypeError):
                gate_lat, gate_lon = None, None

            target_phase, target_icao = self._resolve_gate_phase_and_icao(
                assigned_gate=assigned_gate,
                gate_lat=gate_lat,
                gate_lon=gate_lon,
                cur_apt=cur_apt,
                dep_icao=dep_icao,
                arr_icao=arr_icao,
                dest_icao=dest_icao
            )

            if not target_icao:
                return

            obs_key = f"{target_icao}:{clean_gate_token(assigned_gate)}"
            if self._last_observed_gate.get(target_phase) == obs_key:
                return
            self._last_observed_gate[target_phase] = obs_key

            self.hub.on_external_atc_gate_detected(
                phase=target_phase,
                icao=target_icao,
                raw_gate=assigned_gate,
                source=GateSource.SAY_INTENTIONS,
                lat=gate_lat,
                lon=gate_lon
            )

        except Exception as exc:
            print(f"[SayIntentionsWatcher] Poll warning: {exc}")


class InteroperabilityHub:
    """
    Central Event-Driven Interoperability Hub for GateFinder V2.0:
      - Scenario 1: Standalone GateFinder matching
      - Scenario 2: Silent GSX Pro Gate Auto-Injection (with menu-hash wait states & Follow-Me setting)
      - Scenario 3: BeyondATC & SayIntentions AI ATC Gate Interception + Conflict Arbitrator
      - Scenario 4: Live VATSIM pre-filtering + 150-200 NM Pre-TOD Refresh & UI Alert
      - Global Event Bus: ON_GATE_CHANGED -> SayIntentions SAPI & GSX Auto-Injector
    """
    def __init__(self, backend, config):
        self.backend = backend
        self.config = config
        self.lock = threading.RLock()

        self.state: Dict[str, HubState] = {
            "departure": HubState.IDLE,
            "arrival": HubState.IDLE
        }
        self.active_decision: Dict[str, Optional[GateDecision]] = {
            "departure": None,
            "arrival": None
        }

        self.pending_conflict: Optional[Dict[str, Any]] = None
        self.midflight_alert: Optional[Dict[str, Any]] = None
        self.gsx_injection_task: Optional[Dict[str, Any]] = None
        self.last_sapi_sync_status: Optional[Dict[str, Any]] = None

        self._pre_tod_vatsim_checked: bool = False
        self._approach_vatsim_checked: bool = False
        self._vatsim_refresh_in_progress: bool = False
        self._batc_gsx_dep: bool = False
        self._batc_gsx_arr: bool = False
        self.batc_gsx_flow_started_event = threading.Event()
        self.batc_gsx_flow_done_event = threading.Event()
        self.batc_gsx_flow_done_event.set()
        self._user_overridden_rwy: Dict[str, Optional[str]] = {"departure": None, "arrival": None}
        self._sapi_lock = threading.Lock()
        self._last_sapi_call_ts: float = 0.0
        self._gsx_watch_menu_mtime: float = 0.0
        self._couatl_err_offset: Optional[int] = None
        self._last_gsx_warp_ts: float = 0.0
        self._last_user_manual_gate_ts: float = 0.0
        self._last_ground_gps: Optional[Tuple[float, float]] = None
        self._was_airborne_for_arrival: bool = False

        # Watchers & GSX Arrival Automator
        self.batc_watcher = BeyondATCWatcher(self)
        self.si_watcher = SayIntentionsWatcher(self)
        self.gsx_automator = GSXArrivalAutomator(self)

        # Global ON_GATE_CHANGED Event Subscribers
        self._on_gate_changed_listeners: List[Callable[[GateDecision, Optional[str]], None]] = [
            self._sync_gate_to_sayintentions_on_change,
            self._queue_gsx_injection_on_change,
        ]

        # Start background watcher daemon thread (polls BATC at 5 Hz / 0.20s for short-taxi reactivity)
        self._stop_event = threading.Event()
        self._watcher_thread = threading.Thread(target=self._watcher_loop, daemon=True)
        self._watcher_thread.start()

    def _watcher_loop(self):
        tick = 0
        while not self._stop_event.is_set():
            try:
                if self.backend.current_flight_data:
                    self.batc_watcher.poll()
                    if tick % 2 == 0:
                        self._poll_gsx_live_gate_changes()
                    if tick % 5 == 0:
                        self.si_watcher.poll()
                    tick += 1
            except Exception as e:
                print(f"[InteroperabilityHub] Watcher loop error: {e}")
            time.sleep(0.20)

    # ------------------------------------------------------------------
    # HELPER METHODS & PHASE RESOLUTION
    # ------------------------------------------------------------------
    def set_batc_gsx_flags(self, dep_handling: bool, arr_handling: bool):
        with self.lock:
            self._batc_gsx_dep = dep_handling
            self._batc_gsx_arr = arr_handling
            if self.active_decision.get("departure") and self.active_decision["departure"].source == GateSource.BEYOND_ATC:
                self.active_decision["departure"].batc_handles_gsx = dep_handling
            if self.active_decision.get("arrival") and self.active_decision["arrival"].source == GateSource.BEYOND_ATC:
                self.active_decision["arrival"].batc_handles_gsx = arr_handling

    def get_phase_icao(self, phase: str) -> str:
        fd = self.backend.current_flight_data
        if not fd or phase not in fd or not fd[phase]:
            return ""
        return str(fd[phase].get("icao") or "").strip().upper()

    def infer_active_phase(self) -> str:
        fd = self.backend.current_flight_data
        if not fd:
            return "departure"
        sc = getattr(self.backend, "simconnect_manager", None)
        if sc and sc.connected and sc.user_lat is not None and sc.user_lon is not None:
            arr = fd.get("arrival") or {}
            if arr.get("lat") is not None and arr.get("lon") is not None:
                from network import haversine
                if haversine(sc.user_lat, sc.user_lon, arr["lat"], arr["lon"]) < 15000.0:
                    return "arrival"
        return "departure"

    # ------------------------------------------------------------------
    # GLOBAL EVENT BUS: ON_GATE_CHANGED
    # ------------------------------------------------------------------
    def subscribe_on_gate_changed(self, callback: Callable[[GateDecision, Optional[str]], None]):
        if callback not in self._on_gate_changed_listeners:
            self._on_gate_changed_listeners.append(callback)

    def _emit_on_gate_changed(self, decision: GateDecision, previous_gate: Optional[str]):
        for listener in list(self._on_gate_changed_listeners):
            try:
                listener(decision, previous_gate)
            except Exception as exc:
                print(f"[InteroperabilityHub] ON_GATE_CHANGED listener exception: {exc}")

    # ------------------------------------------------------------------
    # FLIGHT REGISTRATION (SCENARIO 1 & 4 INITIALIZATION)
    # ------------------------------------------------------------------
    def on_flight_loaded(self, flight_data: Dict[str, Any]):
        """
        Called by GateFinderBackend.get_flight_data() right after departure and arrival
        gates have been computed (with VATSIM occupied gates filtered out).
        """
        with self.lock:
            self._pre_tod_vatsim_checked = False
            self._approach_vatsim_checked = False
            self._vatsim_refresh_in_progress = False
            self._user_overridden_rwy = {"departure": None, "arrival": None}
            self.pending_conflict = None
            self.midflight_alert = None

            vatsim_checked = bool(self.config.settings.get("check_online_traffic", True))
            default_source = GateSource.VATSIM_CLEAN if vatsim_checked else GateSource.STANDALONE_GF

            for phase in ("departure", "arrival"):
                apt = flight_data.get(phase)
                if apt and apt.get("icao") and apt.get("gate") and apt.get("gate") != "N/A":
                    batc_handles = self._batc_gsx_arr if phase == "arrival" else self._batc_gsx_dep
                    user_new = bool(apt.get("user_requested_new_stand"))
                    init_source = GateSource.USER_MANUAL if user_new else default_source
                    dec = GateDecision(
                        phase=phase,
                        icao=apt["icao"],
                        gate_id=apt["gate"],
                        source=init_source,
                        lat=apt.get("lat"),
                        lon=apt.get("lon"),
                        gsx_synced=False,
                        batc_handles_gsx=batc_handles
                    )
                    self.active_decision[phase] = dec
                    self.state[phase] = HubState.GATE_LOCKED if user_new else HubState.GATE_COMPUTED
                    if user_new:
                        apt["gate_source"] = GateSource.USER_MANUAL.value
                    elif apt.get("turnaround_locked"):
                        if apt.get("turnaround_reason") == "msfs_live":
                            apt["gate_source"] = "MSFS Live (Parked Stand)"
                        else:
                            apt["gate_source"] = "GateFinder (Turnaround Stand)"
                    elif apt.get("fallback_tier"):
                        apt["gate_source"] = f"GateFinder ({apt['fallback_tier']})"
                    else:
                        apt["gate_source"] = dec.source.value
                    apt["gate_source_key"] = dec.source.name
                    apt["gsx_synced"] = False
                    self._emit_on_gate_changed(dec, previous_gate=None)
                else:
                    self.active_decision[phase] = None
                    self.state[phase] = HubState.IDLE

            # Immediately sync with BeyondATC or SayIntentions if already active for this flight
            try:
                self.batc_watcher.poll()
                self.batc_watcher.resync_current_flight()
                self.si_watcher.resync_current_flight()
            except Exception as exc:
                print(f"[InteroperabilityHub] Initial ATC resync warning: {exc}")

    # ------------------------------------------------------------------
    # EDGE CASE 2: SAYINTENTIONS SAPI HOOKED TO GLOBAL ON_GATE_CHANGED
    # ------------------------------------------------------------------
    def _sync_gate_to_sayintentions_on_change(self, decision: GateDecision, previous_gate: Optional[str]):
        """
        Whenever a gate changes in GateFinder (initial load, manual gate change,
        Pre-TOD VATSIM reassignment, or conflict resolution keeping GateFinder's gate),
        push the gate to SayIntentions via SAPI (`assignGate`) if an API key is available.
        """
        if decision.source == GateSource.SAY_INTENTIONS:
            # Avoid echoing back a gate that came from SayIntentions itself
            return

        api_key = self.si_watcher.get_api_key()
        if not api_key or not decision.icao or not decision.gate_id:
            return

        # Clean gate identifier for SayIntentions SAPI (e.g. "D 92" -> "D92" or "42")
        gate_param = re.sub(r'^(GATE|STAND|PARKING|RAMP)\s*', '', str(decision.gate_id), flags=re.IGNORECASE).strip()
        self.si_watcher.record_outbound_sapi_gate(decision.phase, decision.icao, gate_param)

        def _sapi_push():
            with self._sapi_lock:
                elapsed = time.time() - self._last_sapi_call_ts
                if elapsed < 0.35:
                    time.sleep(0.35 - elapsed)
                try:
                    query = urllib.parse.urlencode({
                        "api_key": api_key,
                        "airport": decision.icao,
                        "gate": gate_param
                    })
                    url = f"https://apipri.sayintentions.ai/sapi/assignGate?{query}"
                    req = urllib.request.Request(url, headers={"User-Agent": "GateFinder/2.0"})
                    with urllib.request.urlopen(req, timeout=5.0) as resp:
                        body = resp.read().decode("utf-8", errors="ignore")
                    self._last_sapi_call_ts = time.time()
                    with self.lock:
                        self.last_sapi_sync_status = {
                            "timestamp": int(time.time()),
                            "phase": decision.phase,
                            "icao": decision.icao,
                            "gate": decision.gate_id,
                            "ok": True,
                            "response": body[:120]
                        }
                except Exception as exc:
                    self._last_sapi_call_ts = time.time()
                    with self.lock:
                        self.last_sapi_sync_status = {
                            "timestamp": int(time.time()),
                            "phase": decision.phase,
                            "icao": decision.icao,
                            "gate": decision.gate_id,
                            "ok": False,
                            "error": str(exc)
                        }

        threading.Thread(target=_sapi_push, daemon=True).start()

    # ------------------------------------------------------------------
    # SCENARIO 2: QUEUE GSX AUTO-INJECTION ON GATE CHANGE & LIVE GSX SYNC
    # ------------------------------------------------------------------
    def _is_aircraft_on_ground_at_phase(self, phase: str) -> bool:
        sc = getattr(self.backend, "simconnect_manager", None)
        if not sc or not sc.connected or getattr(sc, "in_menu", False):
            return False
        if sc.user_on_ground is not True or sc.user_lat is None or sc.user_lon is None:
            return False
        if float(sc.user_gs or 0.0) >= 65.0:
            return False
        fd = self.backend.current_flight_data or {}
        apt = fd.get(phase) or {}
        if apt.get("lat") is None or apt.get("lon") is None:
            return False
        from network import haversine
        dist_m = haversine(sc.user_lat, sc.user_lon, apt["lat"], apt["lon"])
        return dist_m < 12000.0

    def _is_aircraft_on_ground_at_arrival(self) -> bool:
        return self._is_aircraft_on_ground_at_phase("arrival")

    def _get_current_ground_phase(self) -> Optional[str]:
        sc = getattr(self.backend, "simconnect_manager", None)
        if not sc or not sc.connected or getattr(sc, "in_menu", False):
            return None
        if sc.user_on_ground is not True or sc.user_lat is None or sc.user_lon is None:
            return None
        fd = self.backend.current_flight_data or {}
        dep = fd.get("departure") or {}
        arr = fd.get("arrival") or {}
        from network import haversine
        d_dep = (
            haversine(sc.user_lat, sc.user_lon, dep["lat"], dep["lon"])
            if (dep.get("lat") is not None and dep.get("lon") is not None)
            else None
        )
        d_arr = (
            haversine(sc.user_lat, sc.user_lon, arr["lat"], arr["lon"])
            if (arr.get("lat") is not None and arr.get("lon") is not None)
            else None
        )
        if d_arr is not None and d_arr < 12000.0 and (d_dep is None or d_arr < d_dep):
            return "arrival"
        if d_dep is not None and d_dep < 12000.0:
            return "departure"
        return None

    def _poll_gsx_live_gate_changes(self):
        """
        Watches GSX Pro (`FSDT_GSX_Panel/menu`, `%APPDATA%\\virtuali\\Couatl.err`, and live ground
        reposition/warp events) so that whenever the user changes stand or repositions the aircraft
        via GSX Pro, GateFinder automatically updates its stand and taxi route to match.
        """
        panel_dir = self.gsx_automator._find_gsx_panel_dir()
        couatl_err = os.path.expandvars(r"%APPDATA%\virtuali\Couatl.err")

        # While GateFinder's own GSX automator is running (or within 6.0s of finishing),
        # keep file cursors and GPS baseline synced so we never mistake our own automation/warp for an external change.
        if self.gsx_automator._running or (time.time() - getattr(self.gsx_automator, "_last_finish_ts", 0.0)) < 6.0:
            if panel_dir:
                mf = os.path.join(panel_dir, "menu")
                if os.path.exists(mf):
                    try:
                        self._gsx_watch_menu_mtime = os.path.getmtime(mf)
                    except Exception:
                        pass
            if os.path.isfile(couatl_err):
                try:
                    self._couatl_err_offset = os.path.getsize(couatl_err)
                except Exception:
                    pass
            self._last_gsx_warp_ts = 0.0
            sc_cur = getattr(self.backend, "simconnect_manager", None)
            if sc_cur and sc_cur.connected and sc_cur.user_lat is not None and sc_cur.user_lon is not None:
                self._last_ground_gps = (sc_cur.user_lat, sc_cur.user_lon)
            return

        ground_phase = self._get_current_ground_phase()
        if not ground_phase:
            return
        icao = self.get_phase_icao(ground_phase)
        if not icao:
            return

        detected_gate_raw: Optional[str] = None

        # 1. Watch FSDT_GSX_Panel/menu for user-selected facility ('Change Facility [...]' or 'Activate Services at ...')
        if panel_dir:
            mf = os.path.join(panel_dir, "menu")
            if os.path.exists(mf):
                try:
                    mtime = os.path.getmtime(mf)
                    if self._gsx_watch_menu_mtime == 0.0:
                        self._gsx_watch_menu_mtime = mtime
                    elif mtime > self._gsx_watch_menu_mtime:
                        self._gsx_watch_menu_mtime = mtime
                        st = self.gsx_automator._read_menu_state(panel_dir)
                        if st["is_open"]:
                            for opt in st["options"]:
                                if not opt:
                                    continue
                                if "change facility" in opt.lower():
                                    fac_g = self.gsx_automator._extract_change_facility_gate(opt)
                                    if fac_g:
                                        detected_gate_raw = fac_g
                                        break
                                m_act = re.search(r'activate\s+services\s+at\s+(.+)$', opt, re.IGNORECASE)
                                if m_act:
                                    detected_gate_raw = m_act.group(1).strip()
                                    break
                except Exception:
                    pass

        # 2. Watch %APPDATA%\virtuali\Couatl.err for 'Requested assistance services at ...' and warp events
        if os.path.isfile(couatl_err):
            try:
                sz = os.path.getsize(couatl_err)
                if self._couatl_err_offset is None:
                    self._couatl_err_offset = sz
                else:
                    if sz < self._couatl_err_offset:
                        self._couatl_err_offset = 0
                    if sz > self._couatl_err_offset:
                        with open(couatl_err, "r", encoding="utf-8", errors="ignore") as f:
                            f.seek(self._couatl_err_offset)
                            chunk = f.read(sz - self._couatl_err_offset)
                        self._couatl_err_offset = sz
                        for ln in chunk.splitlines():
                            m_srv = re.search(r'Requested\s+assistance\s+services\s+at\s+(.+)$', ln, re.IGNORECASE)
                            if m_srv:
                                detected_gate_raw = m_srv.group(1).strip()
                            if "aircraftDisengaged" in ln or "aircraftEngaged" in ln:
                                self._last_gsx_warp_ts = time.time()
            except Exception:
                pass

        # 3. Detect GPS warp/reposition on the ground (> 12m instant jump or recent Couatl aircraftDisengaged/Engaged)
        sc = getattr(self.backend, "simconnect_manager", None)
        if sc and sc.connected and sc.user_on_ground is True and sc.user_lat is not None and sc.user_lon is not None:
            from network import haversine
            if self._last_ground_gps is not None:
                jump_m = haversine(self._last_ground_gps[0], self._last_ground_gps[1], sc.user_lat, sc.user_lon)
                if jump_m > 12.0 and float(sc.user_gs or 0.0) < 5.0:
                    self._last_gsx_warp_ts = time.time()
            self._last_ground_gps = (sc.user_lat, sc.user_lon)

            if (
                not detected_gate_raw
                and self._last_gsx_warp_ts > 0.0
                and (time.time() - self._last_gsx_warp_ts) < 10.0
                and float(sc.user_gs or 0.0) < 2.5
            ):
                fd = self.backend.current_flight_data or {}
                apt = fd.get(ground_phase) or {}
                live_info = self.backend.detect_live_msfs_parked_stand(
                    icao,
                    default_lat=apt.get("lat"),
                    default_lon=apt.get("lon"),
                    extra_chart_data=apt.get("chart_data")
                )
                live_g = live_info.get("gate") if isinstance(live_info, dict) else live_info
                if live_g:
                    detected_gate_raw = str(live_g).strip()
                    self._last_gsx_warp_ts = 0.0

        if not detected_gate_raw:
            return

        with self.lock:
            fd = self.backend.current_flight_data or {}
            apt = fd.get(ground_phase) or {}
            cur_gate = str(apt.get("gate") or "").strip()
            canon_g, coords, meta = self.backend.resolve_stand_in_airport_db(icao, detected_gate_raw)
            if not canon_g:
                return

            if gate_tokens_match(canon_g, cur_gate):
                return

            # If the user manually selected an OSM sub-stand (e.g. 'P2A' or 'P2B') recently and GSX reports
            # the shared BGL base stand ('Gate P 2P' -> 'P2'), preserve the user's sub-stand selection.
            cur_t = parse_gsx_gate_tokens(cur_gate)
            det_t = parse_gsx_gate_tokens(detected_gate_raw)
            if (
                (time.time() - self._last_user_manual_gate_ts) < 25.0
                and cur_t.get("number")
                and (cur_t.get("prefix") or "").upper() == (det_t.get("prefix") or "").upper()
                and (cur_t.get("number") or "").upper() == (det_t.get("number") or "").upper()
            ):
                return

            self.gsx_automator._log(
                f"Detected live GSX stand change at {icao} ({ground_phase}): '{detected_gate_raw}' -> Stand '{canon_g}'"
            )
            with self.gsx_automator._lock:
                self.gsx_automator.state = "SYNCED"
                self.gsx_automator.synced_icao = icao
                self.gsx_automator.synced_gate = canon_g
                self.gsx_automator.status_label = f"GSX PRO: STAND {canon_g} SYNCED ✓"
                self.gsx_automator.status_color = "#10B981"

            dec = self._apply_gate_decision(
                phase=ground_phase,
                icao=icao,
                gate_id=canon_g,
                source=GateSource.GSX_LIVE,
                coords=coords,
                gate_meta=meta,
                batc_handles_gsx=False
            )
            dec.gsx_synced = True
            if self.backend.current_flight_data and self.backend.current_flight_data.get(ground_phase):
                self.backend.current_flight_data[ground_phase]["gsx_synced"] = True

    def _is_waiting_for_batc_arrival_gate(self, dec: Optional[GateDecision]) -> bool:
        """
        Returns True if BeyondATC is actively managing the current flight and
        prioritize_ai_atc is enabled, but BeyondATC has not yet issued the arrival gate
        (which BeyondATC assigns upon vacating the landing runway).
        """
        if not dec or dec.phase != "arrival":
            return False
        if dec.source in (GateSource.BEYOND_ATC, GateSource.SAY_INTENTIONS, GateSource.USER_MANUAL):
            return False
        if not bool(self.config.settings.get("prioritize_ai_atc", True)):
            return False
        if self.batc_watcher.is_active and self.batc_watcher._is_matching_active_flight():
            if not self.batc_watcher.batc_arr_gate:
                return True
        return False

    def _queue_gsx_injection_on_change(self, decision: GateDecision, previous_gate: Optional[str]):
        # Never echo back a gate change that originated from GSX itself
        if decision.source == GateSource.GSX_LIVE:
            return

        if not self.gsx_automator.is_gsx_installed():
            self.gsx_automator.set_not_installed()
            return

        if not self.config.settings.get("auto_inject_gsx", True):
            self.gsx_automator.set_disabled()
            return

        # On Departure: do not auto-open the GSX window on passive stand selection ('Select Stand Only');
        # the user triggers GSX reposition explicitly via 'Reposition Aircraft to ...' or the GSX Pro button.
        if decision.phase == "departure":
            return

        if decision.phase != "arrival":
            return

        # Do not abort an in-progress or already-completed GSX sync for the exact same (icao, gate)
        # (e.g. when BeyondATC logs the pilot's readback 8s after the controller instruction).
        if self.gsx_automator.is_running_or_synced_for(decision.icao, decision.gate_id):
            return

        tokens = parse_gsx_gate_tokens(decision.gate_id)
        if not tokens["number"]:
            return

        fd = self.backend.current_flight_data or {}
        arr_apt = fd.get("arrival") or {}
        term_hint = str(arr_apt.get("terminal") or "")

        with self.lock:
            self.gsx_injection_task = {
                "task_id": int(time.time() * 1000),
                "phase": "arrival",
                "icao": decision.icao,
                "target_gate": decision.gate_id,
                "terminal_hint": term_hint,
                "prefix": tokens["prefix"],
                "number": tokens["number"],
                "suffix": tokens["suffix"],
                "search_query": tokens["search_query"],
                "request_follow_me": False,
                "status": "ARMED"
            }

        if self._is_aircraft_on_ground_at_arrival() and self._was_airborne_for_arrival:
            if self._is_waiting_for_batc_arrival_gate(decision):
                self.gsx_automator.set_armed(
                    decision.icao,
                    decision.gate_id,
                    note="GSX PRO: WAITING FOR BEYONDATC GATE..."
                )
                return

            with self.lock:
                self._was_airborne_for_arrival = False
                self.state["arrival"] = HubState.GSX_INJECTING
                if self.gsx_injection_task:
                    self.gsx_injection_task["status"] = "INJECTING"
            wait_batc = bool(decision.source == GateSource.BEYOND_ATC and (decision.batc_handles_gsx or self._batc_gsx_arr))
            self.gsx_automator.start_arrival_sync(
                icao=decision.icao,
                target_gate=decision.gate_id,
                terminal_hint=term_hint,
                manual=False,
                initial_delay_sec=0.0,
                wait_for_batc_gsx=wait_batc
            )
        else:
            self.gsx_automator.set_armed(decision.icao, decision.gate_id)

    def _get_distance_to_arrival_m(self) -> Optional[float]:
        sc = getattr(self.backend, "simconnect_manager", None)
        if not sc or not sc.connected or getattr(sc, "in_menu", False):
            return None
        if sc.user_lat is None or sc.user_lon is None:
            return None
        fd = self.backend.current_flight_data or {}
        arr = fd.get("arrival") or {}
        if arr.get("lat") is None or arr.get("lon") is None:
            return None
        from network import haversine
        return haversine(sc.user_lat, sc.user_lon, arr["lat"], arr["lon"])

    def check_arrival_gsx_auto_trigger(
        self,
        d_arr_m: Optional[float],
        on_ground: Optional[bool],
        gs_kt: Optional[float],
        in_menu: bool,
        sc_connected: bool
    ):
        """
        Automatically triggers the armed Arrival GSX Gate & Default Handler sequence
        as soon as the aircraft touches down and decelerates (< 65 kt) at the arrival airport.
        If BeyondATC is actively managing the flight, waits for BeyondATC to issue the arrival stand
        on runway vacation so GSX is not prematurely locked onto the pre-landing predicted stand.
        """
        if not self.gsx_automator.is_gsx_installed():
            self.gsx_automator.set_not_installed()
            return
        if not self.config.settings.get("auto_inject_gsx", True):
            return
        if not sc_connected or in_menu:
            return

        is_truly_airborne = (on_ground is False and gs_kt is not None and float(gs_kt) >= 65.0)
        if is_truly_airborne:
            self._was_airborne_for_arrival = True

        # While still far from the arrival airport (> 15 km) or genuinely airborne, ensure any IDLE/FAILED state re-arms
        if (d_arr_m is not None and d_arr_m >= 15000.0) or is_truly_airborne:
            with self.lock:
                task = self.gsx_injection_task
                if task and task.get("phase") == "arrival" and task.get("status") in ("IDLE", "FAILED"):
                    task["status"] = "ARMED"
                    task.pop("touchdown_wait_ts", None)
                    self.gsx_automator.set_armed(task.get("icao", ""), task.get("target_gate", ""))
            return

        if on_ground is not True:
            return
        if not self._was_airborne_for_arrival:
            return
        if d_arr_m is None or d_arr_m >= 12000.0:
            return
        if gs_kt is not None and float(gs_kt) >= 65.0:
            return

        with self.lock:
            task = self.gsx_injection_task
            if not task or task.get("phase") != "arrival" or task.get("status") != "ARMED":
                return
            dec = self.active_decision.get("arrival")
            if self._is_waiting_for_batc_arrival_gate(dec):
                wait_start = task.get("touchdown_wait_ts")
                if wait_start is None:
                    wait_start = time.time()
                    task["touchdown_wait_ts"] = wait_start
                    self.gsx_automator.set_armed(
                        task.get("icao", ""),
                        task.get("target_gate", ""),
                        note="GSX PRO: WAITING FOR BEYONDATC GATE..."
                    )
                # Wait up to 240s after touchdown deceleration for the pilot to roll out, vacate the runway,
                # switch to Ground frequency, and receive BeyondATC's stand assignment before falling back to GateFinder's stand.
                if (time.time() - wait_start) < 240.0:
                    return

            self._was_airborne_for_arrival = False
            task["status"] = "INJECTING"
            self.state["arrival"] = HubState.GSX_INJECTING
            icao = task.get("icao", "")
            target_gate = task.get("target_gate", "")
            term_hint = task.get("terminal_hint", "")
            wait_batc = bool(dec and dec.source == GateSource.BEYOND_ATC and (dec.batc_handles_gsx or self._batc_gsx_arr))

        if icao and target_gate:
            self.gsx_automator.start_arrival_sync(
                icao=icao,
                target_gate=target_gate,
                terminal_hint=term_hint,
                manual=False,
                initial_delay_sec=0.0,
                wait_for_batc_gsx=wait_batc
            )

    def trigger_manual_gsx_sync(self, phase: str = "arrival") -> Dict[str, Any]:
        """
        Manually triggers (or re-triggers) GSX Pro Gate + Default Handler + FollowMe=No selection.
        Works on both Departure (when on the ground at departure) and Arrival.
        If the aircraft is still far from the arrival airport (> 20 km), GSX Pro in MSFS has not loaded
        the destination airport yet, so we arm/re-arm it for landing instead of failing on the departure menu.
        """
        if phase not in ("departure", "arrival"):
            phase = "arrival"
        if not self.gsx_automator.is_gsx_installed():
            self.gsx_automator.set_not_installed()
            return {"status": "gsx_not_installed"}
        fd = self.backend.current_flight_data or {}
        apt = fd.get(phase) or {}
        icao = str(apt.get("icao") or "").strip().upper()
        gate_id = str(apt.get("gate") or "").strip()
        term_hint = str(apt.get("terminal") or "")
        if not icao or not gate_id or gate_id in ("N/A", "No Gate Found", "No Suitable Stand"):
            return {"status": "no_gate"}

        if phase == "departure":
            if not self._is_aircraft_on_ground_at_phase("departure"):
                return {"status": "not_at_departure"}
            self.gsx_automator.start_arrival_sync(
                icao=icao,
                target_gate=gate_id,
                terminal_hint=term_hint,
                manual=True,
                warp=False
            )
            return {"status": "started", "icao": icao, "gate": gate_id}

        tokens = parse_gsx_gate_tokens(gate_id)
        dist_m = self._get_distance_to_arrival_m()
        if dist_m is not None and dist_m > 20000.0:
            with self.lock:
                self.gsx_injection_task = {
                    "task_id": int(time.time() * 1000),
                    "phase": "arrival",
                    "icao": icao,
                    "target_gate": gate_id,
                    "terminal_hint": term_hint,
                    "prefix": tokens["prefix"],
                    "number": tokens["number"],
                    "suffix": tokens["suffix"],
                    "search_query": tokens["search_query"],
                    "request_follow_me": False,
                    "status": "ARMED"
                }
            self.gsx_automator.set_armed(
                icao,
                gate_id,
                note=f"GSX PRO: ARMED — WAIT FOR {icao} (<10 NM)"
            )
            return {"status": "armed_waiting_for_arrival", "icao": icao, "gate": gate_id, "dist_km": round(dist_m / 1000.0, 1)}

        with self.lock:
            self.state["arrival"] = HubState.GSX_INJECTING
            self.gsx_injection_task = {
                "task_id": int(time.time() * 1000),
                "phase": "arrival",
                "icao": icao,
                "target_gate": gate_id,
                "terminal_hint": term_hint,
                "prefix": tokens["prefix"],
                "number": tokens["number"],
                "suffix": tokens["suffix"],
                "search_query": tokens["search_query"],
                "request_follow_me": False,
                "status": "INJECTING"
            }

        self.gsx_automator.start_arrival_sync(
            icao=icao,
            target_gate=gate_id,
            terminal_hint=term_hint,
            manual=True,
            warp=False
        )
        return {"status": "started", "icao": icao, "gate": gate_id}

    def get_arrival_gsx_status(self) -> Dict[str, Any]:
        return self.gsx_automator.get_status_dict()

    def on_gsx_setting_changed(self):
        """Synchronizes GSXArrivalAutomator immediately when the user toggles auto_inject_gsx in Settings."""
        if not self.gsx_automator.is_gsx_installed():
            self.gsx_automator.set_not_installed()
            return
        if not bool(self.config.settings.get("auto_inject_gsx", True)):
            self.gsx_automator.set_disabled()
            return
        if self.gsx_automator.state in ("DISABLED", "IDLE", "NOT_INSTALLED"):
            arr_dec = self.active_decision.get("arrival")
            if arr_dec and arr_dec.gate_id:
                self._queue_gsx_injection_on_change(arr_dec, previous_gate=arr_dec.gate_id)

    def acknowledge_gsx_injection(self, task_id: int, success: bool):
        with self.lock:
            if self.gsx_injection_task and self.gsx_injection_task.get("task_id") == task_id:
                phase = self.gsx_injection_task.get("phase", "arrival")
                self.gsx_injection_task["status"] = "DONE" if success else "FAILED"
                if success:
                    self.state[phase] = HubState.GSX_SYNCED
                    dec = self.active_decision.get(phase)
                    if dec:
                        dec.gsx_synced = True
                    fd = self.backend.current_flight_data
                    if fd and fd.get(phase):
                        fd[phase]["gsx_synced"] = True

    # ------------------------------------------------------------------
    # SCENARIO 3: AI ATC INTERCEPTION & ARBITRATION
    # ------------------------------------------------------------------
    def on_user_runway_selected(self, phase: str, rwy_id: str):
        """
        Records when the user manually selects a runway so the 1s ATC watcher loop
        respects the user's manual override unless ATC later issues a new runway.
        """
        if phase not in ("departure", "arrival") or not rwy_id:
            return
        rwy_clean = str(rwy_id).strip().upper()
        with self.lock:
            fd = self.backend.current_flight_data
            if not fd or not fd.get(phase):
                return
            apt = fd[phase]
            icao = str(apt.get("icao") or "").strip().upper()
            atc_rwy = str(apt.get("atc_runway") or "").strip().upper()
            if atc_rwy and rwy_clean != atc_rwy:
                self._user_overridden_rwy[phase] = f"{icao}:{atc_rwy}"
                apt["runway_manual_override"] = True
            else:
                self._user_overridden_rwy[phase] = None
                apt["runway_manual_override"] = False

    def on_external_atc_runway_detected(self, phase: str, icao: str, raw_rwy: str, source: GateSource):
        """
        Invoked when BeyondATC or SayIntentions assigns or changes the active runway
        (at Flight Plan init, IFR Clearance, Taxi, or Approach). AI ATC always wins
        unless the user explicitly confirmed a manual override for this exact ATC runway.
        """
        if not raw_rwy or phase not in ("departure", "arrival"):
            return
        rwy_clean = str(raw_rwy).strip().upper()
        if rwy_clean.startswith("RWY"):
            rwy_clean = rwy_clean[3:].strip()
        if not rwy_clean:
            return

        with self.lock:
            fd = self.backend.current_flight_data
            if not fd or not fd.get(phase):
                return
            apt = fd[phase]
            icao_u = str(apt.get("icao") or "").strip().upper()
            if icao and icao_u != icao.strip().upper():
                return

            apt["atc_runway"] = rwy_clean
            apt["atc_runway_source"] = source.value
            apt["runway_source"] = source.value

            # If user explicitly overrode this exact ATC runway, keep atc_runway metadata but don't revert their choice
            if self._user_overridden_rwy.get(phase) == f"{icao_u}:{rwy_clean}":
                return

            self._user_overridden_rwy[phase] = None
            apt["runway_manual_override"] = False
            cur_rwy = str(apt.get("selected_runway") or "").strip().upper()
            if cur_rwy != rwy_clean:
                self.backend.set_active_runway(phase, rwy_clean, manual=False)

    def on_external_atc_taxi_via_detected(self, phase: str, icao: str, via_tokens: List[str], source: GateSource):
        """
        Invoked when BeyondATC issues a ground taxi clearance with explicit 'via ...' taxiways/links
        (e.g. 'via B, A, OUTER, LINK4, INNER'). Updates apt['atc_taxi_via'] and recomputes A* taxi route.
        """
        if not via_tokens or phase not in ("departure", "arrival"):
            return
        with self.lock:
            fd = self.backend.current_flight_data
            if not fd or not fd.get(phase):
                return
            apt = fd[phase]
            icao_u = str(apt.get("icao") or "").strip().upper()
            if icao and icao_u != icao.strip().upper():
                return
            if apt.get("atc_taxi_via") == via_tokens:
                return
            apt["atc_taxi_via"] = list(via_tokens)
            self.backend.set_active_runway(phase, apt.get("selected_runway"), manual=False)

    def on_external_atc_gate_detected(self, phase: str, icao: str, raw_gate: str,
                                      source: GateSource,
                                      lat: Optional[float] = None,
                                      lon: Optional[float] = None):
        """
        Invoked when BeyondATC or SayIntentions assigns a gate.
        """
        with self.lock:
            fd = self.backend.current_flight_data
            if not fd or not fd.get(phase):
                return
            apt = fd[phase]
            icao_u = str(apt.get("icao") or "").strip().upper()
            if icao and icao_u != icao.strip().upper():
                return

            resolved_gate, resolved_coords, gate_meta = self.backend.resolve_stand_in_airport_db(
                icao_u, raw_gate, fallback_lat=lat, fallback_lon=lon
            )
            # Safety guard: never override a valid stand with a stand whose coordinates could not be resolved
            # at this airport (or are more than 25 km away from the airport center)
            if not resolved_coords or resolved_coords[0] is None or resolved_coords[1] is None:
                return
            chart = apt.get("chart_data") or {}
            c_lat = chart.get("center_lat")
            c_lon = chart.get("center_lon")
            if c_lat is not None and c_lon is not None:
                if abs(float(resolved_coords[0]) - float(c_lat)) > 0.25 or abs(float(resolved_coords[1]) - float(c_lon)) > 0.35:
                    return

            current = self.active_decision.get(phase)

            batc_handles = False
            if source == GateSource.BEYOND_ATC:
                batc_handles = self._batc_gsx_arr if phase == "arrival" else self._batc_gsx_dep

            # Check if the ATC gate is already identical to GateFinder's active gate
            if current and gate_tokens_match(current.gate_id, resolved_gate):
                current.source = source
                current.batc_handles_gsx = batc_handles
                self.state[phase] = HubState.GATE_LOCKED
                fd = self.backend.current_flight_data
                if fd and fd.get(phase):
                    fd[phase]["gate_source"] = source.value
                    fd[phase]["gate_source_key"] = source.name
                if phase == "arrival" and not current.gsx_synced:
                    self._queue_gsx_injection_on_change(current, previous_gate=current.gate_id)
                return

            prioritize_atc = bool(self.config.settings.get("prioritize_ai_atc", True))

            if prioritize_atc or current is None:
                self._apply_gate_decision(
                    phase=phase,
                    icao=icao,
                    gate_id=resolved_gate,
                    source=source,
                    coords=resolved_coords,
                    gate_meta=gate_meta,
                    batc_handles_gsx=batc_handles
                )
            else:
                # Prioritize_AI_ATC is False -> Prompt user to choose!
                self.state[phase] = HubState.ATC_CONFLICT_PENDING
                self.pending_conflict = {
                    "id": int(time.time() * 1000),
                    "phase": phase,
                    "icao": icao,
                    "gf_gate": current.gate_id,
                    "atc_gate": resolved_gate,
                    "atc_source": source.value,
                    "atc_source_key": source.name,
                    "atc_lat": resolved_coords[0] if resolved_coords else lat,
                    "atc_lon": resolved_coords[1] if resolved_coords else lon,
                    "batc_handles_gsx": batc_handles
                }

    def resolve_conflict(self, choice: str) -> Dict[str, Any]:
        """
        Resolves a pending AI ATC vs GateFinder gate conflict.
        `choice`: 'atc' (accept AI ATC gate) or 'gf' (keep GateFinder gate).
        """
        with self.lock:
            if not self.pending_conflict:
                return {"status": "no_conflict"}

            c = self.pending_conflict
            self.pending_conflict = None
            phase = c["phase"]
            icao = c["icao"]

            if choice.lower() == "atc":
                source = GateSource[c["atc_source_key"]]
                resolved_gate, resolved_coords, gate_meta = self.backend.resolve_stand_in_airport_db(
                    icao, c["atc_gate"], fallback_lat=c.get("atc_lat"), fallback_lon=c.get("atc_lon")
                )
                self._apply_gate_decision(
                    phase=phase,
                    icao=icao,
                    gate_id=resolved_gate,
                    source=source,
                    coords=resolved_coords,
                    gate_meta=gate_meta,
                    batc_handles_gsx=bool(c.get("batc_handles_gsx", False))
                )
                return {"status": "accepted_atc", "gate": resolved_gate}
            else:
                # Keep GateFinder gate and fire ON_GATE_CHANGED so SayIntentions SAPI & GSX sync to it
                current = self.active_decision.get(phase)
                self.state[phase] = HubState.GATE_LOCKED
                if current:
                    self._emit_on_gate_changed(current, previous_gate=c["atc_gate"])
                return {"status": "kept_gf", "gate": current.gate_id if current else ""}

    # ------------------------------------------------------------------
    # SCENARIO 4: LIVE VATSIM / IVAO PRE-TOD (~180 NM) & APPROACH (~19 NM) REFRESH
    # ------------------------------------------------------------------
    def check_vatsim_arrival_refresh(self, d_arr_m: Optional[float], is_airborne: bool):
        """
        Automatically triggers a non-blocking background VATSIM/IVAO stand occupancy check
        for the arrival airport at two key in-flight checkpoints:
          1. Pre-TOD (~180 NM / 330 km from destination)
          2. Approach (~19 NM / 35 km from destination)
        """
        if not is_airborne or d_arr_m is None:
            return
        if not bool(self.config.settings.get("check_online_traffic", True)):
            return

        checkpoint_to_run = None
        with self.lock:
            if self._vatsim_refresh_in_progress:
                return
            if 40000.0 <= float(d_arr_m) <= 330000.0 and not self._pre_tod_vatsim_checked:
                self._pre_tod_vatsim_checked = True
                self._vatsim_refresh_in_progress = True
                checkpoint_to_run = "Pre-TOD"
            elif 8000.0 <= float(d_arr_m) <= 35000.0 and not self._approach_vatsim_checked:
                self._approach_vatsim_checked = True
                self._vatsim_refresh_in_progress = True
                checkpoint_to_run = "Approach"

        if not checkpoint_to_run:
            return

        def _worker():
            try:
                self.backend.refresh_arrival_vatsim_stand_if_occupied(checkpoint_label=checkpoint_to_run)
            except Exception as exc:
                print(f"[InteroperabilityHub] VATSIM/IVAO {checkpoint_to_run} refresh warning: {exc}")
            finally:
                with self.lock:
                    self._vatsim_refresh_in_progress = False

        threading.Thread(target=_worker, daemon=True).start()

    def on_vatsim_arrival_stand_reassigned(
        self,
        icao: str,
        old_gate: str,
        new_gate: str,
        coords: Optional[Tuple[float, float]],
        gate_meta: Optional[Dict[str, Any]] = None,
        occupying_pilot: Optional[Dict[str, Any]] = None,
        checkpoint_label: str = "Pre-TOD"
    ):
        """
        Called when the Pre-TOD or Approach VATSIM/IVAO refresh detects that the predicted
        arrival stand is now occupied by another online pilot and reassigns a conflict-free stand.
        """
        with self.lock:
            net_name = (occupying_pilot or {}).get("network", "VATSIM")
            cs_name = (occupying_pilot or {}).get("callsign", "Online Traffic")
            self.midflight_alert = {
                "timestamp": int(time.time()),
                "icao": icao,
                "old_gate": old_gate,
                "new_gate": new_gate,
                "network": net_name,
                "callsign": cs_name,
                "checkpoint": checkpoint_label,
                "message": f"{checkpoint_label} {net_name} Check: Stand {old_gate} occupied by {cs_name} -> Reassigned to Stand {new_gate}"
            }
            self._apply_gate_decision(
                phase="arrival",
                icao=icao,
                gate_id=new_gate,
                source=GateSource.VATSIM_REASSIGNED,
                coords=coords,
                gate_meta=gate_meta,
                batc_handles_gsx=False
            )

    # ------------------------------------------------------------------
    # MANUAL GATE OVERRIDE & GSX REPOSITION AIRCRAFT
    # ------------------------------------------------------------------
    def set_manual_gate(self, phase: str, raw_gate: str) -> Optional[GateDecision]:
        with self.lock:
            self._last_user_manual_gate_ts = time.time()
            icao = self.get_phase_icao(phase)
            if not icao or not raw_gate:
                return None
            resolved_gate, resolved_coords, gate_meta = self.backend.resolve_stand_in_airport_db(
                icao, raw_gate
            )
            return self._apply_gate_decision(
                phase=phase,
                icao=icao,
                gate_id=resolved_gate,
                source=GateSource.USER_MANUAL,
                coords=resolved_coords,
                gate_meta=gate_meta,
                batc_handles_gsx=False
            )

    def reposition_aircraft_to_gate(self, phase: str, raw_gate: str) -> Optional[GateDecision]:
        """
        Selects `raw_gate` in GateFinder AND executes GSX Pro's 'Reposition Aircraft' ->
        'Just warp me there' flow to physically teleport/reposition the aircraft onto that stand.
        """
        with self.lock:
            self._last_user_manual_gate_ts = time.time()
            self._was_airborne_for_arrival = False
            if phase not in ("departure", "arrival"):
                phase = self._get_current_ground_phase() or "departure"
            icao = self.get_phase_icao(phase)
            if not icao or not raw_gate:
                return None
            resolved_gate, resolved_coords, gate_meta = self.backend.resolve_stand_in_airport_db(
                icao, raw_gate
            )
            prev_gate = self.active_decision[phase].gate_id if self.active_decision.get(phase) else None
            lat = resolved_coords[0] if resolved_coords else None
            lon = resolved_coords[1] if resolved_coords else None
            dec = GateDecision(
                phase=phase,
                icao=icao,
                gate_id=resolved_gate,
                source=GateSource.USER_MANUAL,
                lat=lat,
                lon=lon,
                gsx_synced=False,
                batc_handles_gsx=False
            )
            self.active_decision[phase] = dec
            self.state[phase] = HubState.GSX_INJECTING
            self.backend.apply_hub_gate_override(phase, resolved_gate, resolved_coords, gate_meta, GateSource.USER_MANUAL)
            self._sync_gate_to_sayintentions_on_change(dec, previous_gate=prev_gate)

            fd = self.backend.current_flight_data or {}
            apt = fd.get(phase) or {}
            term_hint = str(apt.get("terminal") or "")
            tokens = parse_gsx_gate_tokens(resolved_gate)
            if phase == "arrival" or (self.gsx_injection_task and self.gsx_injection_task.get("phase") == phase):
                self.gsx_injection_task = {
                    "task_id": int(time.time() * 1000),
                    "phase": phase,
                    "icao": icao,
                    "target_gate": resolved_gate,
                    "terminal_hint": term_hint,
                    "prefix": tokens["prefix"],
                    "number": tokens["number"],
                    "suffix": tokens["suffix"],
                    "search_query": tokens["search_query"],
                    "request_follow_me": False,
                    "status": "INJECTING"
                }

        self.gsx_automator.start_arrival_sync(
            icao=icao,
            target_gate=resolved_gate,
            terminal_hint=term_hint,
            manual=True,
            initial_delay_sec=0.0,
            wait_for_batc_gsx=False,
            warp=True
        )
        return dec

    def _apply_gate_decision(self, phase: str, icao: str, gate_id: str,
                             source: GateSource,
                             coords: Optional[Tuple[float, float]],
                             gate_meta: Optional[Dict[str, Any]] = None,
                             batc_handles_gsx: bool = False) -> GateDecision:
        prev_gate = self.active_decision[phase].gate_id if self.active_decision.get(phase) else None
        lat = coords[0] if coords else None
        lon = coords[1] if coords else None

        dec = GateDecision(
            phase=phase,
            icao=icao,
            gate_id=gate_id,
            source=source,
            lat=lat,
            lon=lon,
            gsx_synced=False,
            batc_handles_gsx=batc_handles_gsx
        )
        self.active_decision[phase] = dec
        self.state[phase] = HubState.GATE_LOCKED

        # Update backend flight data & recompute A* ground taxi routing
        self.backend.apply_hub_gate_override(phase, gate_id, coords, gate_meta, source)

        # Fire global ON_GATE_CHANGED event (updates SayIntentions SAPI & queues GSX injection)
        self._emit_on_gate_changed(dec, previous_gate=prev_gate)
        return dec

    # ------------------------------------------------------------------
    # SNAPSHOT FOR FRONTEND (GUI + MSFS IN-GAME PANEL)
    # ------------------------------------------------------------------
    def get_hub_status_payload(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "states": {k: v.value for k, v in self.state.items()},
                "decisions": {
                    k: (v.to_dict() if v else None)
                    for k, v in self.active_decision.items()
                },
                "addons_detected": {
                    "beyond_atc": self.batc_watcher.is_active,
                    "say_intentions": self.si_watcher.is_active,
                    "say_intentions_sapi_ready": bool(self.si_watcher.api_key),
                },
                "pending_conflict": self.pending_conflict,
                "midflight_alert": self.midflight_alert,
                "gsx_injection_task": self.gsx_injection_task,
                "last_sapi_sync": self.last_sapi_sync_status,
            }
