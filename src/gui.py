import customtkinter as ctk
from tkinter import messagebox
from config import Config
from autostart import AutoStartManager
import os
import re
import sys
import time
import tkinter
import tkinter as tk
import math

# Configuration du thème moderne et chic
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def _clean_terminal_label(raw_term):
    """Strips parenthetical zone descriptions (e.g. '(Schengen)', '(International & Outre-Mer)') and tightens slashes."""
    s = re.sub(r'\s*\([^)]*\)', '', str(raw_term or ""))
    s = re.sub(r'\s*/\s*', '/', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _compact_gate_label(raw_gate):
    """Compacts gate designators like 'A 11' -> 'A11' or 'C 1' -> 'C1' for clean display."""
    s = str(raw_gate or "").strip()
    s = re.sub(r'^([A-Za-z]+)\s+(\d+[A-Za-z]*)$', r'\1\2', s)
    return s

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        try:
            self.widget.bind("<Enter>", self.show_tip, add="+")
            self.widget.bind("<Leave>", self.hide_tip, add="+")
        except Exception:
            self.widget.bind("<Enter>", self.show_tip)
            self.widget.bind("<Leave>", self.hide_tip)
        for sub_attr in ("_text_label", "_canvas", "_entry"):
            sub_w = getattr(self.widget, sub_attr, None)
            if sub_w is not None:
                try:
                    sub_w.bind("<Enter>", self.show_tip, add="+")
                    sub_w.bind("<Leave>", self.hide_tip, add="+")
                except Exception:
                    pass

    def bind_child(self, child_widget):
        try:
            child_widget.bind("<Enter>", self.show_tip, add="+")
            child_widget.bind("<Leave>", self.hide_tip, add="+")
        except Exception:
            pass
        for sub_attr in ("_text_label", "_canvas", "_entry"):
            sub_w = getattr(child_widget, sub_attr, None)
            if sub_w is not None:
                try:
                    sub_w.bind("<Enter>", self.show_tip, add="+")
                    sub_w.bind("<Leave>", self.hide_tip, add="+")
                except Exception:
                    pass

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        if event:
            x = event.x_root + 15
            y = event.y_root + 15
        else:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + 25

        self.tip_window = tw = tkinter.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tkinter.Label(
            tw, text=self.text, justify="left", wraplength=440,
            background="#1E293B", foreground="#F8FAFC", relief="flat", borderwidth=0,
            font=("Segoe UI", 10), padx=12, pady=8
        )
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()


class EFBOptionMenu(ctk.CTkFrame):
    """
    Flicker-free CustomTkinter dropdown menu that replaces native Win32 tk_popup
    used by CTkOptionMenu (which flickers during periodic background UI sync loops).
    """
    def __init__(self, parent, values=None, width=105, height=28, fg_color="#0284C7", button_color="#0369A1", font=None, command=None, **kwargs):
        super().__init__(parent, width=width, height=height, corner_radius=6, fg_color=fg_color, **kwargs)
        self.pack_propagate(False)
        self._values = list(values) if values else ["RWY"]
        self._current_val = self._values[0] if self._values else ""
        self._fg_color = fg_color
        self._btn_color = button_color
        self._font = font or ctk.CTkFont(family="Consolas", size=13, weight="bold")
        self._command = command
        self._dropdown_frame = None
        self._outside_bind_id = None

        self._val_lbl = ctk.CTkLabel(
            self, text=self._current_val, font=self._font,
            text_color="#FFFFFF", fg_color="transparent", anchor="w", cursor="hand2"
        )
        self._val_lbl.pack(side="left", fill="both", expand=True, padx=(10, 2))

        self._arrow_box = ctk.CTkFrame(
            self, width=26, height=height, corner_radius=6,
            fg_color=button_color, cursor="hand2"
        )
        self._arrow_box.pack(side="right", fill="y")
        self._arrow_box.pack_propagate(False)

        self._arrow_lbl = ctk.CTkLabel(
            self._arrow_box, text="▾", font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#FFFFFF", fg_color="transparent", cursor="hand2"
        )
        self._arrow_lbl.place(relx=0.5, rely=0.5, anchor="center")

        for w in (self, self._val_lbl, self._arrow_box, self._arrow_lbl):
            w.bind("<Button-1>", self._toggle_dropdown)

    def get(self):
        return self._current_val

    def set(self, value):
        val_str = str(value)
        if val_str != self._current_val:
            self._current_val = val_str
            self._val_lbl.configure(text=val_str)

    def configure(self, **kwargs):
        vals = kwargs.pop("values", None)
        fg_c = kwargs.pop("fg_color", None)
        btn_c = kwargs.pop("button_color", None)
        cmd = kwargs.pop("command", None)
        if vals is not None:
            new_vals = [str(v) for v in vals]
            if new_vals != self._values:
                self._values = new_vals
        if fg_c is not None and fg_c != self._fg_color:
            self._fg_color = fg_c
            super().configure(fg_color=fg_c)
        if btn_c is not None and btn_c != self._btn_color:
            self._btn_color = btn_c
            self._arrow_box.configure(fg_color=btn_c)
        if cmd is not None:
            self._command = cmd
        if kwargs:
            super().configure(**kwargs)

    def _close_dropdown(self, event=None):
        if self._dropdown_frame is not None:
            try:
                top = self.winfo_toplevel()
                if self._outside_bind_id is not None:
                    top.unbind("<Button-1>", self._outside_bind_id)
            except Exception:
                pass
            self._outside_bind_id = None
            try:
                if self._dropdown_frame.winfo_exists():
                    self._dropdown_frame.destroy()
            except Exception:
                pass
            self._dropdown_frame = None

    def _on_global_click(self, event):
        if self._dropdown_frame is None or not self._dropdown_frame.winfo_exists():
            self._close_dropdown()
            return
        try:
            mx, my = event.x_root, event.y_root
            # Check if click is inside dropdown or inside button itself
            dx0, dy0 = self._dropdown_frame.winfo_rootx(), self._dropdown_frame.winfo_rooty()
            dx1, dy1 = dx0 + self._dropdown_frame.winfo_width(), dy0 + self._dropdown_frame.winfo_height()
            bx0, by0 = self.winfo_rootx(), self.winfo_rooty()
            bx1, by1 = bx0 + self.winfo_width(), by0 + self.winfo_height()
            if (dx0 <= mx <= dx1 and dy0 <= my <= dy1) or (bx0 <= mx <= bx1 and by0 <= my <= by1):
                return
        except Exception:
            pass
        self._close_dropdown()

    def _select_value(self, val):
        self._close_dropdown()
        self.set(val)
        if self._command:
            self._command(val)

    def _toggle_dropdown(self, event=None):
        now = time.monotonic()
        if now - getattr(self, "_last_toggle_ts", 0.0) < 0.22:
            return "break"
        self._last_toggle_ts = now
        if self._dropdown_frame is not None and self._dropdown_frame.winfo_exists():
            self._close_dropdown()
            return "break"
        if not self._values:
            return "break"

        top = self.winfo_toplevel()
        x = self.winfo_rootx() - top.winfo_rootx()
        y = self.winfo_rooty() - top.winfo_rooty() + self.winfo_height() + 3
        w = max(self.winfo_width(), 105)

        dd = ctk.CTkFrame(
            top, width=w, fg_color="#1E293B", corner_radius=8,
            border_width=0
        )
        for v in self._values:
            is_sel = (str(v) == str(self._current_val))
            btn = ctk.CTkButton(
                dd, text=str(v), width=w - 8, height=28, corner_radius=6,
                fg_color=self._fg_color if is_sel else "transparent",
                hover_color=self._btn_color,
                text_color="#FFFFFF",
                font=self._font,
                anchor="w",
                command=lambda val=v: self._select_value(val)
            )
            btn.pack(fill="x", padx=4, pady=2)

        dd.place(x=x, y=y)
        dd.lift()
        self._dropdown_frame = dd
        def _bind_later():
            if self._dropdown_frame is dd and dd.winfo_exists():
                try:
                    self._outside_bind_id = top.bind("<Button-1>", self._on_global_click, add="+")
                except Exception:
                    pass
        self.after(80, _bind_later)
        return "break"

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, config: Config, autostart: AutoStartManager, backend, on_save_callback, on_close_callback):
        super().__init__(parent, fg_color="transparent")
        self.config = config
        self.autostart = autostart
        self.backend = backend
        self.on_save_callback = on_save_callback
        self.on_close_callback = on_close_callback
        self._chk_widgets = []
        self._primary_btns = []

        from tkinter import filedialog

        # Single non-scrolling EFB container using the main window's #121418 background
        main_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0, border_width=0)
        main_container.pack(fill="both", expand=True, padx=16, pady=(8, 10))

        def _make_section_card(title_text, is_first=False, is_last=False, subtitle_text="", right_widget_builder=None):
            card = ctk.CTkFrame(main_container, fg_color="#1B1E24", corner_radius=10, border_width=0)
            card.pack(fill="both", expand=True, padx=0, pady=(0 if is_first else 3, 0 if is_last else 3))

            hdr_row = ctk.CTkFrame(card, fg_color="transparent")
            hdr_row.pack(fill="x", padx=14, pady=(8, 4))

            title_bar = ctk.CTkFrame(hdr_row, fg_color="#252932", corner_radius=7, border_width=0)
            title_bar.pack(side="left", fill="x", expand=True, padx=(0, 8 if (is_first or right_widget_builder) else 0))
            ctk.CTkLabel(
                title_bar, text=title_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#FFFFFF"
            ).pack(side="left", padx=(12, 8), pady=3)
            if subtitle_text:
                ctk.CTkLabel(
                    title_bar, text=subtitle_text,
                    font=ctk.CTkFont(size=11),
                    text_color="#94A3B8"
                ).pack(side="left", padx=(4, 10), pady=3)

            if is_first:
                self.btn_back = ctk.CTkButton(
                    hdr_row, text="Back", command=self.on_close_callback,
                    width=84, height=26, corner_radius=7,
                    fg_color="#578DA8", hover_color="#4A6C7D", border_width=0,
                    text_color="#FFFFFF",
                    font=ctk.CTkFont(size=12, weight="bold")
                )
                self.btn_back.pack(side="right")
                self._primary_btns.append(self.btn_back)
                Tooltip(self.btn_back, "Return to the Lido Ground Chart view.")
            elif right_widget_builder:
                right_widget_builder(hdr_row)

            body = ctk.CTkFrame(card, fg_color="transparent")
            body.pack(fill="both", expand=True, padx=16, pady=(1, 8))
            body.grid_columnconfigure(0, minsize=230)
            body.grid_columnconfigure(1, weight=1)
            return body

        chk_style = {
            "font": ctk.CTkFont(size=13),
            "text_color": "#E2E8F0",
            "fg_color": "#578DA8",
            "hover_color": "#4A6C7D",
            "border_color": "#383E4C",
            "checkmark_color": "#FFFFFF",
            "checkbox_width": 19,
            "checkbox_height": 19,
            "corner_radius": 5,
        }

        # ==================================================================
        # CARD 1: DISPATCH & STAND SELECTION
        # ==================================================================
        c1 = _make_section_card("DISPATCH & STAND SELECTION", is_first=True)

        lbl_sb = ctk.CTkLabel(c1, text="SimBrief Username or Pilot ID:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#E2E8F0")
        lbl_sb.grid(row=0, column=0, sticky="w", pady=3)
        Tooltip(lbl_sb, "Enter your SimBrief username or 6-digit Pilot ID to import your Operational Flight Plans.")

        sb_entry_frame = ctk.CTkFrame(c1, fg_color="transparent")
        sb_entry_frame.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=3)

        self.simbrief_entry = ctk.CTkEntry(
            sb_entry_frame, width=160, height=28, corner_radius=6,
            border_width=0, fg_color="#2B303B", text_color="#FFFFFF",
            placeholder_text="Username or ID"
        )
        self.simbrief_entry.pack(side="left")
        self.simbrief_entry.insert(0, self.config.settings.get("simbrief_username", ""))
        Tooltip(self.simbrief_entry, "Enter your SimBrief username or 6-digit Pilot ID to import your Operational Flight Plans.")

        self.btn_test_connection = ctk.CTkButton(
            sb_entry_frame,
            text="Test Connection",
            width=120,
            height=28,
            corner_radius=6,
            fg_color="#578DA8",
            hover_color="#4A6C7D",
            border_width=0,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.test_simbrief_connection
        )
        self.btn_test_connection.pack(side="left", padx=8)
        self._primary_btns.append(self.btn_test_connection)
        Tooltip(self.btn_test_connection, "Verify your SimBrief account and preview your active flight plan.")

        self.lbl_connection_status = ctk.CTkLabel(sb_entry_frame, text="", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_connection_status.pack(side="left", padx=4)

        c1_checks = ctk.CTkFrame(c1, fg_color="transparent")
        c1_checks.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.autofetch_var = ctk.BooleanVar(value=self.config.settings.get("auto_fetch", False))
        chk_autofetch = ctk.CTkCheckBox(
            c1_checks,
            text="Auto-fetch latest SimBrief OFP on startup",
            variable=self.autofetch_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_autofetch.pack(anchor="w", pady=3)
        self._chk_widgets.append(chk_autofetch)
        Tooltip(chk_autofetch, "Automatically download and load your active SimBrief flight plan when GateFinder starts.")

        self.auto_lock_turnaround_var = ctk.BooleanVar(value=self.config.settings.get("auto_lock_turnaround", True))
        chk_turnaround = ctk.CTkCheckBox(
            c1_checks,
            text="Prompt to keep arrival or live MSFS parked stand on Turnaround",
            variable=self.auto_lock_turnaround_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_turnaround.pack(anchor="w", pady=3)
        self._chk_widgets.append(chk_turnaround)
        Tooltip(chk_turnaround, "When importing a new flight departing from your previous arrival airport or current MSFS position, offer to keep the same gate.")

        self.force_cargo_var = ctk.BooleanVar(value=self.config.settings.get("force_cargo_mode", False))
        chk_cargo = ctk.CTkCheckBox(
            c1_checks,
            text="Force Cargo Mode",
            variable=self.force_cargo_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_cargo.pack(anchor="w", pady=3)
        self._chk_widgets.append(chk_cargo)
        Tooltip(chk_cargo, "Always assign a Cargo / Freighter ramp even when flying a passenger aircraft.")

        # ==================================================================
        # CARD 2: ATC, GSX PRO & ONLINE TRAFFIC
        # ==================================================================
        c2 = _make_section_card("ATC, GSX PRO & ONLINE TRAFFIC")

        c2_checks = ctk.CTkFrame(c2, fg_color="transparent")
        c2_checks.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        self.prioritize_ai_atc_var = ctk.BooleanVar(value=self.config.settings.get("prioritize_ai_atc", True))
        chk_ai_atc = ctk.CTkCheckBox(
            c2_checks,
            text="Auto-sync gate & active runway assigned by AI ATC",
            variable=self.prioritize_ai_atc_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_ai_atc.pack(anchor="w", pady=3)
        self._chk_widgets.append(chk_ai_atc)
        Tooltip(chk_ai_atc, "Automatically adopt active runway and arrival stand assignments received from BeyondATC or SayIntentions.AI.")

        self.auto_inject_gsx_var = ctk.BooleanVar(value=self.config.settings.get("auto_inject_gsx", True))
        chk_gsx = ctk.CTkCheckBox(
            c2_checks,
            text="Enable GSX Pro Arrival Auto-Sync",
            variable=self.auto_inject_gsx_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_gsx.pack(anchor="w", pady=3)
        self._chk_widgets.append(chk_gsx)
        Tooltip(chk_gsx, "Automatically selects your arrival gate and default handling operator in GSX Pro on landing. Uncheck to hide GSX UI controls.")

        self.check_online_traffic_var = ctk.BooleanVar(value=self.config.settings.get("check_online_traffic", True))
        chk_online = ctk.CTkCheckBox(
            c2_checks,
            text="Filter occupied stands on VATSIM & IVAO",
            variable=self.check_online_traffic_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_online.pack(anchor="w", pady=3)
        self._chk_widgets.append(chk_online)
        Tooltip(chk_online, "Excludes stands occupied by other online pilots on VATSIM and IVAO at Dispatch, Pre-TOD (~180 NM) and Approach (~19 NM).")

        self.auto_clear_ai_var = ctk.BooleanVar(value=self.config.settings.get("auto_clear_ai", True))
        chk_clear_ai = ctk.CTkCheckBox(
            c2_checks,
            text="Auto-clear MSFS AI traffic at assigned stands",
            variable=self.auto_clear_ai_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_clear_ai.pack(anchor="w", pady=3)
        self._chk_widgets.append(chk_clear_ai)
        Tooltip(chk_clear_ai, "Automatically removes SimConnect AI aircraft parked at your assigned Departure and Arrival stands.")

        self.mars_overlap_protection_var = ctk.BooleanVar(value=self.config.settings.get("mars_overlap_protection", True))
        chk_mars_overlap = ctk.CTkCheckBox(
            c2_checks,
            text="Protect overlapping / double stands (MARS) from AI & traffic collisions",
            variable=self.mars_overlap_protection_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_mars_overlap.pack(anchor="w", pady=3)
        self._chk_widgets.append(chk_mars_overlap)
        Tooltip(chk_mars_overlap, "Prevents wingtip collisions on double/triple MARS stands (e.g. A4 & A41) by automatically clearing AI traffic (BeyondATC / MSFS) spawned on overlapping neighbor sub-stands and filtering overlapping occupied stands.")

        lbl_si_key = ctk.CTkLabel(c2, text="SayIntentions.AI SAPI Key:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#E2E8F0")
        lbl_si_key.grid(row=1, column=0, sticky="w", pady=3)
        Tooltip(lbl_si_key, "Optional. Leave blank to auto-detect your API key directly from your local SayIntentions.AI installation.")

        si_frame = ctk.CTkFrame(c2, fg_color="transparent")
        si_frame.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=3)

        self.si_api_key_entry = ctk.CTkEntry(
            si_frame, width=220, height=28, corner_radius=6,
            border_width=0, fg_color="#2B303B", text_color="#FFFFFF",
            placeholder_text="Auto-detected if left blank"
        )
        self.si_api_key_entry.pack(side="left")
        saved_si_key = self.config.settings.get("sayintentions_api_key", "")
        if saved_si_key:
            self.si_api_key_entry.insert(0, saved_si_key)
        Tooltip(self.si_api_key_entry, "Optional. Leave blank to auto-detect your API key directly from your local SayIntentions.AI installation.")

        # ==================================================================
        # CARD 3: PERFORMANCE & SYSTEM
        # ==================================================================
        web_efb_url = (
            self.backend.get_web_efb_url()
            if (self.backend and hasattr(self.backend, "get_web_efb_url"))
            else "http://127.0.0.1:8420/"
        )

        def _build_web_efb_hdr_btns(hdr_parent):
            def _open_web_efb():
                import webbrowser
                webbrowser.open(web_efb_url)

            btn_open_web = ctk.CTkButton(
                hdr_parent, text="Open Web EFB", width=112, height=26, corner_radius=6,
                fg_color="#578DA8", hover_color="#4A6C7D",
                border_width=0,
                text_color="#FFFFFF", font=ctk.CTkFont(size=12, weight="bold"),
                command=_open_web_efb
            )
            btn_open_web.pack(side="right", padx=(6, 0))
            self._primary_btns.append(btn_open_web)
            Tooltip(btn_open_web, f"Open the Live Web EFB ({web_efb_url}) in your browser. Open this exact URL on any 2nd PC, iPad, or tablet on your local network.")

            btn_copy_web = ctk.CTkButton(
                hdr_parent, text="Copy URL", width=84, height=26, corner_radius=6,
                fg_color="#252932", hover_color="#323846",
                border_width=1, border_color="#334155",
                text_color="#E2E8F0", font=ctk.CTkFont(size=12, weight="bold")
            )

            def _copy_web_efb():
                try:
                    self.clipboard_clear()
                    self.clipboard_append(web_efb_url)
                    btn_copy_web.configure(text="Copied!")
                    self.after(1600, lambda: btn_copy_web.configure(text="Copy URL") if btn_copy_web.winfo_exists() else None)
                except Exception:
                    pass

            btn_copy_web.configure(command=_copy_web_efb)
            btn_copy_web.pack(side="right", padx=(6, 0))
            Tooltip(btn_copy_web, f"Copy {web_efb_url} to clipboard to open on a 2nd PC, Mac, iPad, or Android tablet.")

            btn_qr_web = ctk.CTkButton(
                hdr_parent, text="QR Code", width=78, height=26, corner_radius=6,
                fg_color="#252932", hover_color="#323846",
                border_width=1, border_color="#334155",
                text_color="#38BDF8", font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda: self.open_web_efb_qr_modal(web_efb_url)
            )
            btn_qr_web.pack(side="right")
            Tooltip(btn_qr_web, "Display a scannable QR Code to open the Live Web EFB directly on your iPhone, iPad, or Android phone/tablet.")

        c3 = _make_section_card(
            "PERFORMANCE & SYSTEM",
            subtitle_text=f"Web EFB (Phone / Tablet / 2nd PC): {web_efb_url}",
            right_widget_builder=_build_web_efb_hdr_btns
        )

        c3_checks = ctk.CTkFrame(c3, fg_color="transparent")
        c3_checks.grid(row=0, column=0, columnspan=2, sticky="w")

        self.autostart_var = ctk.BooleanVar(value=self.config.settings.get("auto_start", False))
        chk_autostart = ctk.CTkCheckBox(
            c3_checks,
            text="Auto-Start GateFinder silently when MSFS launches",
            variable=self.autostart_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_autostart.pack(anchor="w", pady=2)
        self._chk_widgets.append(chk_autostart)
        Tooltip(chk_autostart, "Registers GateFinder in your MSFS exe.xml file so it starts automatically in the background when the simulator launches.")

        self.auto_quit_msfs_var = ctk.BooleanVar(value=self.config.settings.get("auto_quit_with_msfs", False))
        chk_autoquit = ctk.CTkCheckBox(
            c3_checks,
            text="Auto-Quit GateFinder when MSFS closes",
            variable=self.auto_quit_msfs_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_autoquit.pack(anchor="w", pady=2)
        self._chk_widgets.append(chk_autoquit)
        Tooltip(chk_autoquit, "Automatically closes GateFinder in the background when Microsoft Flight Simulator exits.")

        self.hibernate_map_in_flight_var = ctk.BooleanVar(value=self.config.settings.get("hibernate_map_in_flight", True))
        chk_hibernate = ctk.CTkCheckBox(
            c3_checks,
            text="Auto-suspend Lido chart rendering while airborne",
            variable=self.hibernate_map_in_flight_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_hibernate.pack(anchor="w", pady=2)
        self._chk_widgets.append(chk_hibernate)
        Tooltip(chk_hibernate, "Pauses map canvas redraws between Wheels-Off and Touchdown to save GPU and CPU resources during flight.")

        # ==================================================================
        # CARD 4: CRASH REPORTING & DIAGNOSTIC PRIVACY (SceneryX Style)
        # ==================================================================
        def _build_crash_hdr_btns(hdr_parent):
            btn_hist = ctk.CTkButton(
                hdr_parent, text="History", width=76, height=26, corner_radius=6,
                fg_color="#161920", hover_color="#2B303B",
                border_width=1, border_color="#2B303B",
                text_color="#E2E8F0", font=ctk.CTkFont(size=12, weight="bold"),
                command=self.open_crash_history_modal
            )
            btn_hist.pack(side="right", padx=(6, 0))
            Tooltip(btn_hist, "View locally recorded crash logs in %APPDATA%\\GateFinder\\crashes\\.")

            btn_issue = ctk.CTkButton(
                hdr_parent, text="Report an Issue...", width=136, height=26, corner_radius=6,
                fg_color="#252932", hover_color="#323846",
                border_width=1, border_color="#334155",
                text_color="#FFFFFF", font=ctk.CTkFont(size=12, weight="bold"),
                command=self.report_an_issue
            )
            btn_issue.pack(side="right")
            Tooltip(btn_issue, "Send an anonymized diagnostic or issue report to contact@sidestickpriority.com.")

        c_crash = _make_section_card(
            "CRASH REPORTING & DIAGNOSTIC PRIVACY",
            subtitle_text="Help improve GateFinder reliability with zero personal data collection",
            right_widget_builder=_build_crash_hdr_btns
        )

        crash_box = ctk.CTkFrame(
            c_crash, fg_color="#15181E", corner_radius=8,
            border_width=1, border_color="#252932"
        )
        crash_box.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(1, 2))
        crash_box.grid_columnconfigure(0, weight=1)

        # Row 1: Send Crash Reports Automatically
        row_cr1 = ctk.CTkFrame(crash_box, fg_color="transparent")
        row_cr1.pack(fill="x", padx=14, pady=(7, 5))
        cr1_left = ctk.CTkFrame(row_cr1, fg_color="transparent")
        cr1_left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            cr1_left, text="Send Crash Reports Automatically",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#F8FAFC", anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            cr1_left,
            text="Captures unhandled exceptions, call stacks, and anonymized hardware/simulator specs upon fatal errors. No usernames, personal file paths, or credentials are ever collected.",
            font=ctk.CTkFont(size=11), text_color="#64748B", anchor="w", justify="left"
        ).pack(anchor="w")

        self.send_crash_reports_var = ctk.BooleanVar(value=self.config.settings.get("send_crash_reports", True))
        chk_crash_auto = ctk.CTkCheckBox(
            row_cr1, text="", width=22,
            variable=self.send_crash_reports_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_crash_auto.pack(side="right", padx=(12, 0))
        self._chk_widgets.append(chk_crash_auto)

        # Thin separator line
        ctk.CTkFrame(crash_box, height=1, fg_color="#222630").pack(fill="x", padx=14, pady=1)

        # Row 2: Share Anonymized Flight Statistics
        row_cr2 = ctk.CTkFrame(crash_box, fg_color="transparent")
        row_cr2.pack(fill="x", padx=14, pady=(5, 7))
        cr2_left = ctk.CTkFrame(row_cr2, fg_color="transparent")
        cr2_left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            cr2_left, text="Share Anonymized Flight Statistics",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#F8FAFC", anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            cr2_left,
            text="Submits high-level flight dispatch aggregates (aircraft type, airport ICAO, ATC source) to help optimize default stand presets and Lido LOD tuning.",
            font=ctk.CTkFont(size=11), text_color="#64748B", anchor="w", justify="left"
        ).pack(anchor="w")

        self.share_flight_stats_var = ctk.BooleanVar(value=self.config.settings.get("share_flight_stats", True))
        chk_flight_stats = ctk.CTkCheckBox(
            row_cr2, text="", width=22,
            variable=self.share_flight_stats_var,
            command=self.save_settings_silent,
            **chk_style
        )
        chk_flight_stats.pack(side="right", padx=(12, 0))
        self._chk_widgets.append(chk_flight_stats)

        # ==================================================================
        # CARD 5: MSFS PATHS & IN-GAME TOOLBAR PANEL
        # ==================================================================
        c4 = _make_section_card("MSFS PATHS & IN-GAME TOOLBAR PANEL")

        path_entry_width = 370

        # Row 0: GSX Profile Path
        lbl_gsx = ctk.CTkLabel(c4, text="GSX Profile Path:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#E2E8F0")
        lbl_gsx.grid(row=0, column=0, sticky="w", pady=2)
        Tooltip(lbl_gsx, "Path to your Virtuali GSX MSFS profiles folder (%APPDATA%\\Virtuali\\GSX\\MSFS) containing custom airport .ini and .py files.")

        gsx_frame = ctk.CTkFrame(c4, fg_color="transparent")
        gsx_frame.grid(row=0, column=1, padx=(10, 0), pady=2, sticky="w")

        self.gsx_entry = ctk.CTkEntry(
            gsx_frame, width=path_entry_width, height=26, corner_radius=6,
            border_width=0, fg_color="#2B303B", text_color="#FFFFFF",
            placeholder_text="Leave empty if GSX Pro is not installed"
        )
        self.gsx_entry.pack(side="left")
        self.gsx_entry.insert(0, self.config.settings.get("gsx_profile_path", ""))
        Tooltip(self.gsx_entry, "Path to your Virtuali GSX MSFS profiles folder (%APPDATA%\\Virtuali\\GSX\\MSFS) containing custom airport .ini and .py files.")

        def browse_gsx():
            d = filedialog.askdirectory(title="Select GSX Profile Folder")
            if d:
                self.gsx_entry.delete(0, 'end')
                self.gsx_entry.insert(0, d)
                self.save_settings_silent()

        def auto_scan_gsx():
            appdata = os.environ.get("APPDATA", "")
            d = os.path.join(appdata, "Virtuali", "GSX", "MSFS")
            self.gsx_entry.delete(0, 'end')
            if os.path.exists(d):
                self.gsx_entry.insert(0, d)
            self.save_settings_silent()

        btn_browse_gsx = ctk.CTkButton(
            gsx_frame, text="...", width=34, height=26, corner_radius=6,
            fg_color="#2B303B", hover_color="#383E4C", border_width=0, command=browse_gsx
        )
        btn_browse_gsx.pack(side="left", padx=6)
        Tooltip(btn_browse_gsx, "Browse for your GSX MSFS profiles folder.")

        btn_autodetect_gsx = ctk.CTkButton(
            gsx_frame, text="Auto-Detect", width=95, height=26, corner_radius=6,
            fg_color="#578DA8", hover_color="#4A6C7D", border_width=0,
            text_color="#FFFFFF", font=ctk.CTkFont(size=12, weight="bold"), command=auto_scan_gsx
        )
        btn_autodetect_gsx.pack(side="left")
        self._primary_btns.append(btn_autodetect_gsx)
        Tooltip(btn_autodetect_gsx, "Automatically locate the default %APPDATA%\\Virtuali\\GSX\\MSFS directory.")

        # Row 1: Primary MSFS Community Folder
        lbl_comm20 = ctk.CTkLabel(c4, text="Primary Community Folder:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#E2E8F0")
        lbl_comm20.grid(row=1, column=0, sticky="w", pady=2)
        Tooltip(lbl_comm20, "Path to your primary MSFS Community folder used to scan third-party sceneries and install the In-Game Panel.")

        comm2020_frame = ctk.CTkFrame(c4, fg_color="transparent")
        comm2020_frame.grid(row=1, column=1, padx=(10, 0), pady=2, sticky="w")

        self.community2020_entry = ctk.CTkEntry(
            comm2020_frame, width=path_entry_width, height=26, corner_radius=6,
            border_width=0, fg_color="#2B303B", text_color="#FFFFFF",
            placeholder_text="Path to primary MSFS Community folder"
        )
        self.community2020_entry.pack(side="left")
        self.community2020_entry.insert(0, self.config.settings.get("msfs_community_path", ""))
        Tooltip(self.community2020_entry, "Path to your primary MSFS Community folder used to scan third-party sceneries and install the In-Game Panel.")

        def browse_comm2020():
            d = filedialog.askdirectory(title="Select Primary MSFS Community Folder")
            if d:
                self.community2020_entry.delete(0, 'end')
                self.community2020_entry.insert(0, d)
                self.save_settings_silent()
                self.refresh_dynamic_statuses()

        btn_browse_c20 = ctk.CTkButton(
            comm2020_frame, text="...", width=34, height=26, corner_radius=6,
            fg_color="#2B303B", hover_color="#383E4C", border_width=0, command=browse_comm2020
        )
        btn_browse_c20.pack(side="left", padx=(6, 0))
        Tooltip(btn_browse_c20, "Browse for your primary MSFS Community folder.")

        # Row 2: Custom / Secondary Community Folder
        lbl_comm24 = ctk.CTkLabel(c4, text="Secondary / MSFS 2024 Folder:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#E2E8F0")
        lbl_comm24.grid(row=2, column=0, sticky="w", pady=2)
        Tooltip(lbl_comm24, "Optional path to a secondary MSFS 2024 Community folder or custom Addon Linker scenery directory.")

        comm2024_frame = ctk.CTkFrame(c4, fg_color="transparent")
        comm2024_frame.grid(row=2, column=1, padx=(10, 0), pady=2, sticky="w")

        self.community2024_entry = ctk.CTkEntry(
            comm2024_frame, width=path_entry_width, height=26, corner_radius=6,
            border_width=0, fg_color="#2B303B", text_color="#FFFFFF",
            placeholder_text="Optional path to Community2024 or Addon Linker"
        )
        self.community2024_entry.pack(side="left")
        self.community2024_entry.insert(0, self.config.settings.get("msfs_community2024_path", ""))
        Tooltip(self.community2024_entry, "Optional path to a secondary MSFS 2024 Community folder or custom Addon Linker scenery directory.")

        def browse_comm2024():
            d = filedialog.askdirectory(title="Select Custom / Secondary Community Folder")
            if d:
                self.community2024_entry.delete(0, 'end')
                self.community2024_entry.insert(0, d)
                self.save_settings_silent()
                self.refresh_dynamic_statuses()

        btn_browse_c24 = ctk.CTkButton(
            comm2024_frame, text="...", width=34, height=26, corner_radius=6,
            fg_color="#2B303B", hover_color="#383E4C", border_width=0, command=browse_comm2024
        )
        btn_browse_c24.pack(side="left", padx=(6, 0))
        Tooltip(btn_browse_c24, "Browse for a secondary MSFS 2024 Community or Addon Linker folder.")

        # Row 3: MSFS EFB & In-Game Toolbar Panel + Migrate / Clean V1.x
        lbl_panel = ctk.CTkLabel(c4, text="MSFS EFB & In-Game Panel:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#E2E8F0")
        lbl_panel.grid(row=3, column=0, sticky="w", pady=(4, 1))
        Tooltip(lbl_panel, "Install or uninstall the GateFinder MSFS EFB App & VR/Toolbar In-Game Panel ('gatefinder-ingame-panel') in your MSFS Community folder(s).")

        panel_frame = ctk.CTkFrame(c4, fg_color="transparent")
        panel_frame.grid(row=3, column=1, padx=(10, 0), pady=(4, 1), sticky="ew")

        self.btn_install_panel = ctk.CTkButton(
            panel_frame, text="Install MSFS EFB", width=148, height=26, corner_radius=6,
            fg_color="#578DA8", hover_color="#4A6C7D", border_width=0,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.install_ingame_panel
        )
        self.btn_install_panel.pack(side="left")
        Tooltip(self.btn_install_panel, "Click to install or uninstall the GateFinder MSFS EFB & In-Game Panel ('gatefinder-ingame-panel') in your configured MSFS Community folder(s).")

        self.lbl_msfs_efb_status = ctk.CTkLabel(
            panel_frame, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color="#10B981"
        )
        self.lbl_msfs_efb_status.pack(side="left", padx=(10, 0))

        self.btn_migrate_v1 = ctk.CTkButton(
            panel_frame, text="Migrate / Clean V1.x...", width=155, height=26, corner_radius=6,
            fg_color="#252932", hover_color="#323846",
            border_width=1, border_color="#334155",
            text_color="#E2E8F0",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.open_v1_migration_modal
        )
        self.btn_migrate_v1.pack(side="right")
        Tooltip(self.btn_migrate_v1, "Find and cleanly remove any previous GateFinder V1.x installation ('wildbill75-gatefinder'), import its settings, and install V2.0.")

        # Row 4: Fenix A320 EFB Integration + Uninstall GateFinder right-justified in red
        lbl_fenix_efb = ctk.CTkLabel(c4, text="Fenix A320 EFB Integration:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#E2E8F0")
        lbl_fenix_efb.grid(row=4, column=0, sticky="w", pady=(3, 1))
        Tooltip(lbl_fenix_efb, "Install or uninstall the GateFinder app directly inside the Fenix A319/A320/A321 cockpit EFB tablet (Captain & First Officer).")

        fenix_frame = ctk.CTkFrame(c4, fg_color="transparent")
        fenix_frame.grid(row=4, column=1, padx=(10, 0), pady=(3, 1), sticky="ew")

        self.btn_install_fenix_efb = ctk.CTkButton(
            fenix_frame, text="Install Fenix EFB", width=148, height=26, corner_radius=6,
            fg_color="#578DA8", hover_color="#4A6C7D", border_width=0,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.install_fenix_efb_ui
        )
        self.btn_install_fenix_efb.pack(side="left")
        Tooltip(self.btn_install_fenix_efb, "Click to install/enable or uninstall/disable GateFinder inside the Fenix A320 3D cockpit tablet EFB.")

        self.lbl_fenix_efb_status = ctk.CTkLabel(
            fenix_frame, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color="#10B981"
        )
        self.lbl_fenix_efb_status.pack(side="left", padx=(10, 0))

        self.btn_uninstall_app = ctk.CTkButton(
            fenix_frame, text="Uninstall GateFinder", command=self.run_uninstall,
            width=155, height=26, corner_radius=6,
            fg_color="#B91C1C", hover_color="#991B1B",
            border_width=0, text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_uninstall_app.pack(side="right")
        Tooltip(self.btn_uninstall_app, "Removes the GateFinder In-Game Panel & EFB integrations from all MSFS Community folders and cleans MSFS exe.xml auto-start entries.")

        # ==================================================================
        # CARD 6: LEGAL & COMPLIANCE (SceneryX Style)
        # ==================================================================
        def _build_legal_hdr_btns(hdr_parent):
            for tab_id, tab_lbl, w_px in [
                ("Third-Party Licenses", "Third-Party Licenses", 142),
                ("Privacy Policy", "Privacy Policy", 104),
                ("EULA", "EULA", 68),
            ]:
                btn_l = ctk.CTkButton(
                    hdr_parent, text=tab_lbl, width=w_px, height=26, corner_radius=6,
                    fg_color="#252932", hover_color="#323846",
                    border_width=1, border_color="#334155",
                    text_color="#F8FAFC", font=ctk.CTkFont(size=12, weight="bold"),
                    command=lambda t=tab_id: self.open_legal_modal(initial_tab=t)
                )
                btn_l.pack(side="right", padx=(6, 0))

        c_legal = _make_section_card(
            "LEGAL & COMPLIANCE",
            is_last=True,
            subtitle_text="End User License Agreement (EULA), Privacy Policy & Third-Party Open-Source Licenses  •  © 2026 Sidestick Priority",
            right_widget_builder=_build_legal_hdr_btns
        )
        c_legal.pack_forget()

        # Bind live auto-save on text entries
        for entry_w in (self.simbrief_entry, self.si_api_key_entry, self.gsx_entry, self.community2020_entry, self.community2024_entry):
            entry_w.bind("<FocusOut>", lambda e: self.save_settings_silent(), add="+")
            entry_w.bind("<Return>", lambda e: self.save_settings_silent(), add="+")
            entry_w.bind("<KeyRelease>", lambda e: self.save_settings_silent(), add="+")

        self.refresh_dynamic_statuses()

    def refresh_dynamic_statuses(self):
        """Updates the In-Game Panel button ('Install Panel' vs 'Uninstall Panel') and syncs active camaïeu colors."""
        c_primary = "#578DA8"
        c_hover = "#4A6C7D"
        try:
            top = self.winfo_toplevel()
            if hasattr(top, "_get_active_camaieu"):
                cam = top._get_active_camaieu()
                c_primary = cam.get("s1", "#578DA8")
                c_hover = cam.get("s3", "#4A6C7D")
        except Exception:
            pass

        for chk in getattr(self, "_chk_widgets", ()):
            try:
                chk.configure(fg_color=c_primary, hover_color=c_hover)
            except Exception:
                pass
        for pb in getattr(self, "_primary_btns", ()):
            try:
                pb.configure(fg_color=c_primary, hover_color=c_hover)
            except Exception:
                pass

        try:
            comm20 = self.community2020_entry.get().strip() if hasattr(self, "community2020_entry") else ""
            comm24 = self.community2024_entry.get().strip() if hasattr(self, "community2024_entry") else ""
            is_installed = False
            if comm20 and os.path.exists(os.path.join(comm20, "gatefinder-ingame-panel", "InGamePanels")):
                is_installed = True
            if comm24 and os.path.exists(os.path.join(comm24, "gatefinder-ingame-panel", "InGamePanels")):
                is_installed = True
            if hasattr(self, "btn_install_panel"):
                if is_installed:
                    self.btn_install_panel.configure(
                        text="Uninstall MSFS EFB",
                        fg_color="#2B303B",
                        hover_color="#383E4C",
                        border_width=0,
                        command=self.uninstall_ingame_panel
                    )
                    if hasattr(self, "lbl_msfs_efb_status"):
                        self.lbl_msfs_efb_status.configure(text="● Installed", text_color="#10B981")
                else:
                    self.btn_install_panel.configure(
                        text="Install MSFS EFB",
                        fg_color=c_primary,
                        hover_color=c_hover,
                        border_width=0,
                        command=self.install_ingame_panel
                    )
                    if hasattr(self, "lbl_msfs_efb_status"):
                        self.lbl_msfs_efb_status.configure(text="○ Not Installed", text_color="#94A3B8")

            is_fenix_installed = False
            if self.backend and hasattr(self.backend, "is_fenix_efb_installed"):
                is_fenix_installed = self.backend.is_fenix_efb_installed(extra_community_paths=[comm20, comm24])
            if hasattr(self, "btn_install_fenix_efb"):
                if is_fenix_installed:
                    self.btn_install_fenix_efb.configure(
                        text="Uninstall Fenix EFB",
                        fg_color="#2B303B",
                        hover_color="#383E4C",
                        border_width=0,
                        command=self.uninstall_fenix_efb_ui
                    )
                    if hasattr(self, "lbl_fenix_efb_status"):
                        self.lbl_fenix_efb_status.configure(text="● Installed (Captain & FO)", text_color="#10B981")
                else:
                    self.btn_install_fenix_efb.configure(
                        text="Install Fenix EFB",
                        fg_color=c_primary,
                        hover_color=c_hover,
                        border_width=0,
                        command=self.install_fenix_efb_ui
                    )
                    if hasattr(self, "lbl_fenix_efb_status"):
                        self.lbl_fenix_efb_status.configure(text="○ Not Installed", text_color="#94A3B8")
        except Exception:
            pass

    def run_uninstall(self):
        ans = messagebox.askyesno(
            "Uninstall GateFinder?",
            "This will completely remove the GateFinder In-Game Panel from all detected MSFS Community folders and clean auto-start entries.\n\n"
            "Make sure Microsoft Flight Simulator is closed before continuing.\n\n"
            "Are you sure you want to proceed?"
        )
        if not ans:
            return

        extra_paths = []
        if hasattr(self, 'community2020_entry'):
            p20 = self.community2020_entry.get().strip()
            if p20:
                extra_paths.append(p20)
        if hasattr(self, 'community2024_entry'):
            p24 = self.community2024_entry.get().strip()
            if p24:
                extra_paths.append(p24)

        result = self.backend.uninstall_app(extra_community_paths=extra_paths)

        if not result.get("success"):
            failed_str = "\n".join([f"- {path}: {err}" for path, err in result.get("failed_paths", [])])
            messagebox.showerror(
                "Uninstall Error",
                f"Failed to delete the package from some folder(s):\n{failed_str}\n\n"
                "Please ensure MSFS is completely closed, verify file permissions, and try again."
            )
            return

        removed = result.get("removed_paths", [])
        if removed:
            removed_str = "\n".join([f"• {p}" for p in removed])
            msg = (
                "GateFinder has been successfully uninstalled!\n\n"
                f"Removed In-Game Panel from:\n{removed_str}\n\n"
                "• MSFS Auto-start (exe.xml) entries cleaned.\n\n"
                "You can now close this window and delete the folder containing GateFinder.exe."
            )
        else:
            msg = (
                "GateFinder uninstall complete.\n\n"
                "• Checked all standard MSFS Community folders (no existing 'gatefinder-ingame-panel' or 'wildbill75-gatefinder' package was found).\n"
                "• MSFS Auto-start (exe.xml) entries have been cleaned.\n\n"
                "Note: If you use MSFS Addon Linker, make sure GateFinder is unlinked from within Addon Linker.\n\n"
                "You can now close this window and delete the folder containing GateFinder.exe."
            )

        messagebox.showinfo("Uninstall Complete", msg)
        self.winfo_toplevel().destroy()
        sys.exit(0)

    def test_simbrief_connection(self):
        username = self.simbrief_entry.get().strip()
        if not username:
            self.lbl_connection_status.configure(text="Please enter a username", text_color="#EF4444")
            return
            
        self.btn_test_connection.configure(state="disabled", text="Testing...")
        self.lbl_connection_status.configure(text="")
        
        import threading
        def check():
            try:
                import urllib.request
                import json
                from urllib.parse import quote
                
                if username.isdigit():
                    url = f"https://www.simbrief.com/api/xml.fetcher.php?userid={username}&json=1"
                else:
                    url = f"https://www.simbrief.com/api/xml.fetcher.php?username={quote(username)}&json=1"
                    
                req = urllib.request.Request(url, headers={'User-Agent': 'GateFinder-Client'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    raw_data = response.read()
                    data = json.loads(raw_data.decode('utf-8'))
                    
                if "fetch" in data and "status" in data["fetch"] and "error" in data["fetch"]:
                    raise Exception(data["fetch"]["error"])
                    
                callsign = data.get("general", {}).get("icao_airline", "") + data.get("general", {}).get("flight_number", "")
                if not callsign:
                    callsign = data.get("general", {}).get("callsign", "Unknown")
                origin = data.get("origin", {}).get("icao_code", "")
                destination = data.get("destination", {}).get("icao_code", "")
                
                # Auto-save valid SimBrief ID immediately so Import OFP works right away
                self.config.settings["simbrief_username"] = username
                self.config.save()
                
                status_text = f"Connected: {callsign} ({origin} -> {destination})"
                self.after(0, lambda: self.update_connection_status(True, status_text))
            except urllib.error.HTTPError as e:
                status_text = "Unknown SimBrief ID"
                try:
                    err_body = e.read().decode('utf-8')
                    err_data = json.loads(err_body)
                    fetch_status = err_data.get("fetch", {}).get("status", "")
                    if "No flight plan on file" in fetch_status:
                        self.config.settings["simbrief_username"] = username
                        self.config.save()
                        status_text = f"Connected: {username} (No active OFP)"
                        self.after(0, lambda: self.update_connection_status(True, status_text))
                        return
                    elif "Unknown UserID" in fetch_status or "Error" in fetch_status:
                        status_text = "Unknown SimBrief ID"
                except Exception:
                    pass
                self.after(0, lambda: self.update_connection_status(False, status_text))
            except Exception as e:
                status_text = "Unknown SimBrief ID"
                self.after(0, lambda: self.update_connection_status(False, status_text))
                
        threading.Thread(target=check, daemon=True).start()

    def update_connection_status(self, success, text):
        self.btn_test_connection.configure(state="normal", text="Test Connection")
        if success:
            self.lbl_connection_status.configure(text=text, text_color="#10B981")
        else:
            self.lbl_connection_status.configure(text=text, text_color="#EF4444")

    def install_ingame_panel(self):
        comm2020 = self.community2020_entry.get().strip()
        comm2024 = self.community2024_entry.get().strip()
        
        destinations = {}
        if comm2020 and os.path.exists(comm2020):
            destinations[comm2020] = "MSFS 2020 Community"
        if comm2024 and os.path.exists(comm2024):
            destinations[comm2024] = "MSFS 2024 Community"
            
        if not destinations:
            messagebox.showerror("Error", "Please select a valid MSFS 2020 or 2024 Community folder path first.")
            return
        
        # Locate package folder
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            
        src_panel = None
        for cand in [
            os.path.join(base_dir, "MSFS_Package", "gatefinder-ingame-panel"),
            os.path.join(base_dir, "gatefinder-ingame-panel"),
            os.path.join(base_dir, "..", "MSFS_Package", "gatefinder-ingame-panel"),
            os.path.join(getattr(sys, "_MEIPASS", ""), "MSFS_Package", "gatefinder-ingame-panel") if hasattr(sys, "_MEIPASS") else "",
        ]:
            if cand and os.path.exists(cand):
                src_panel = cand
                break

        if not src_panel:
            messagebox.showerror("Error", "Could not locate 'gatefinder-ingame-panel' package folder. Please make sure the zip archive contents are fully extracted.")
            return

        # Check if already installed in any of the destinations
        already_installed = False
        for dest_path in destinations.keys():
            package_path = os.path.join(dest_path, "gatefinder-ingame-panel")
            if os.path.exists(package_path):
                already_installed = True
                break
                
        if already_installed:
            ans = messagebox.askyesno("Overwrite?", "The GateFinder In-Game Panel ('gatefinder-ingame-panel') is already installed. Do you want to overwrite it with the latest version?")
            if not ans:
                return
                
        try:
            import shutil
            copied_folders = []
            copy_errors = []
            for dest_path, folder_name in destinations.items():
                # Clean any legacy V1.x 'wildbill75-gatefinder' folder in the same Community directory
                legacy_path = os.path.join(dest_path, "wildbill75-gatefinder")
                if os.path.exists(legacy_path):
                    try:
                        shutil.rmtree(legacy_path)
                    except Exception:
                        pass
                package_path = os.path.join(dest_path, "gatefinder-ingame-panel")
                try:
                    shutil.copytree(src_panel, package_path, dirs_exist_ok=True)
                    if self.backend and hasattr(self.backend, "_apply_fenix_efb_state_to_pkg"):
                        self.backend._apply_fenix_efb_state_to_pkg(package_path, src_pkg=src_panel)
                    copied_folders.append(folder_name)
                except Exception as copy_err:
                    print(f"Warning: Failed to copy to {folder_name}: {copy_err}")
                    copy_errors.append(f"{folder_name}: {copy_err}")
            
            self.refresh_dynamic_statuses()
            if not copied_folders:
                messagebox.showerror("Error", "Failed to install In-Game Panel:\n" + "\n".join(copy_errors))
                return
            elif len(copied_folders) > 1:
                success_msg = f"GateFinder MSFS EFB & In-Game Panel ('gatefinder-ingame-panel') installed successfully in folders: {', '.join(copied_folders)}!"
            else:
                success_msg = "GateFinder MSFS EFB & In-Game Panel ('gatefinder-ingame-panel') installed successfully in your Community folder!"
            messagebox.showinfo("Success", success_msg)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy package: {e}")

    def uninstall_ingame_panel(self):
        comm2020 = self.community2020_entry.get().strip() if hasattr(self, "community2020_entry") else ""
        comm2024 = self.community2024_entry.get().strip() if hasattr(self, "community2024_entry") else ""
        targets = []
        for p in (comm2020, comm2024):
            if p:
                for pkg_name in ("gatefinder-ingame-panel", "wildbill75-gatefinder"):
                    pkg = os.path.join(p, pkg_name)
                    if os.path.exists(pkg) and pkg not in targets:
                        targets.append(pkg)
        if not targets:
            self.refresh_dynamic_statuses()
            return
        import shutil
        errors = []
        for pkg in targets:
            try:
                shutil.rmtree(pkg)
            except Exception as e:
                errors.append(f"{pkg}: {e}")
        self.refresh_dynamic_statuses()
        if errors:
            messagebox.showerror(
                "Error",
                "Failed to uninstall MSFS EFB & In-Game Panel (please ensure MSFS is closed):\n" + "\n".join(errors)
            )
        else:
            messagebox.showinfo("Success", "GateFinder MSFS EFB & In-Game Panel has been uninstalled from your Community folder(s).")

    def install_fenix_efb_ui(self):
        comm20 = self.community2020_entry.get().strip() if hasattr(self, "community2020_entry") else ""
        comm24 = self.community2024_entry.get().strip() if hasattr(self, "community2024_entry") else ""
        res = self.backend.install_fenix_efb(extra_community_paths=[comm20, comm24])
        self.refresh_dynamic_statuses()
        if res.get("success"):
            messagebox.showinfo(
                "Success",
                "GateFinder Fenix A320 EFB Integration has been installed!\n\n"
                "You will now see the GateFinder app icon on the Captain & First Officer Fenix EFB Home screen."
            )
        else:
            err_msg = res.get("error") or "\n".join(res.get("errors", []))
            messagebox.showerror("Error", f"Failed to install Fenix A320 EFB integration:\n{err_msg}")

    def uninstall_fenix_efb_ui(self):
        comm20 = self.community2020_entry.get().strip() if hasattr(self, "community2020_entry") else ""
        comm24 = self.community2024_entry.get().strip() if hasattr(self, "community2024_entry") else ""
        res = self.backend.uninstall_fenix_efb(extra_community_paths=[comm20, comm24])
        self.refresh_dynamic_statuses()
        if res.get("success"):
            messagebox.showinfo(
                "Success",
                "GateFinder Fenix A320 EFB Integration has been uninstalled and disabled.\n\n"
                "Restart your flight (or MSFS) for the Fenix EFB to return to its default state."
            )
        else:
            err_msg = "\n".join(res.get("errors", []))
            messagebox.showerror("Error", f"Failed to uninstall Fenix A320 EFB integration:\n{err_msg}")

    def open_web_efb_qr_modal(self, url: str):
        top_win = self.winfo_toplevel()
        modal = ctk.CTkToplevel(top_win)
        modal.title("GateFinder - Mobile & Tablet Web EFB")
        modal.geometry("440x535")
        modal.configure(fg_color="#0D1017")
        modal.transient(top_win)
        modal.grab_set()
        if hasattr(top_win, "_apply_window_icon"):
            top_win._apply_window_icon(modal)

        outer = ctk.CTkFrame(modal, fg_color="#0D1017", corner_radius=10, border_width=1, border_color="#1E2532")
        outer.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            outer, text="SCAN TO OPEN LIVE WEB EFB",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC"
        ).pack(pady=(14, 4))

        ctk.CTkLabel(
            outer,
            text="Scan with your iPhone, iPad, or Android camera (on your local Wi-Fi).\nAuto-detects Smartphone vs Tablet EFB layout.",
            font=ctk.CTkFont(size=12), text_color="#94A3B8", justify="center"
        ).pack(padx=18, pady=(0, 10))

        try:
            import qrcode
            from PIL import Image
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=3,
            )
            qr.add_data(url)
            qr.make(fit=True)
            matrix = qr.get_matrix()
            rows = len(matrix)
            scale = 8
            img_sz = rows * scale
            pil_img = Image.new("RGB", (img_sz, img_sz), (255, 255, 255))
            pix = pil_img.load()
            for r in range(rows):
                for c in range(rows):
                    if matrix[r][c]:
                        for dy in range(scale):
                            for dx in range(scale):
                                pix[c * scale + dx, r * scale + dy] = (13, 16, 23)
            ctk_qr = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(230, 230))
            qr_frame = ctk.CTkFrame(outer, fg_color="#FFFFFF", corner_radius=12)
            qr_frame.pack(pady=(2, 10))
            lbl_qr = ctk.CTkLabel(qr_frame, text="", image=ctk_qr)
            lbl_qr.pack(padx=10, pady=10)
        except Exception as e:
            ctk.CTkLabel(
                outer, text=f"QR generation error: {e}",
                font=ctk.CTkFont(size=12), text_color="#EF4444"
            ).pack(pady=20)

        url_pill = ctk.CTkFrame(outer, fg_color="#161E2E", corner_radius=8, border_width=1, border_color="#25343D")
        url_pill.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkLabel(
            url_pill, text=url,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"), text_color="#38BDF8"
        ).pack(pady=7)

        ctk.CTkLabel(
            outer,
            text="⚠️ Using a VPN (ProtonVPN, NordVPN…)? Disable VPN on your phone/tablet\nor enable \"Allow LAN connections\" in your VPN settings.",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#FBBF24", justify="center"
        ).pack(padx=16, pady=(0, 10))

        ctk.CTkButton(
            outer, text="Close", width=110, height=32, corner_radius=6,
            fg_color="#578DA8", hover_color="#4A6C7D", text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"), command=modal.destroy
        ).pack(pady=(0, 10))

    def report_an_issue(self):
        from legal_and_diagnostics import CrashReporter
        cr = getattr(self.backend, "crash_reporter", None) or CrashReporter(config=self.config, backend=self.backend)
        cr.open_mailto_issue()

    def open_crash_history_modal(self):
        from legal_and_diagnostics import CrashReporter, get_crashes_dir
        cr = getattr(self.backend, "crash_reporter", None) or CrashReporter(config=self.config, backend=self.backend)
        top_win = self.winfo_toplevel()

        modal = ctk.CTkToplevel(top_win)
        modal.title("GateFinder - Crash & Diagnostic History")
        modal.geometry("700x460")
        modal.configure(fg_color="#0D1017")
        modal.transient(top_win)
        modal.grab_set()
        if hasattr(top_win, "_apply_window_icon"):
            top_win._apply_window_icon(modal)

        outer = ctk.CTkFrame(modal, fg_color="#0D1017", corner_radius=10, border_width=1, border_color="#1E2532")
        outer.pack(fill="both", expand=True, padx=10, pady=10)

        hdr = ctk.CTkFrame(outer, fg_color="transparent")
        hdr.pack(fill="x", padx=18, pady=(14, 10))
        ctk.CTkLabel(
            hdr, text="CRASH & DIAGNOSTIC HISTORY",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC"
        ).pack(side="left")

        def _open_folder():
            try:
                os.startfile(get_crashes_dir())
            except Exception:
                pass

        ctk.CTkButton(
            hdr, text="Open Crashes Folder", width=148, height=28, corner_radius=6,
            fg_color="#1E2532", hover_color="#2B3446", text_color="#E2E8F0",
            font=ctk.CTkFont(size=12, weight="bold"), command=_open_folder
        ).pack(side="right")

        ctk.CTkFrame(outer, height=1, fg_color="#1E2532").pack(fill="x")

        scroll = ctk.CTkScrollableFrame(outer, fg_color="#0D1017", corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=14, pady=10)

        def _populate():
            for w in scroll.winfo_children():
                w.destroy()
            reports = cr.get_crash_history()
            if not reports:
                empty_box = ctk.CTkFrame(scroll, fg_color="#131822", corner_radius=8, border_width=1, border_color="#1E293B")
                empty_box.pack(fill="x", padx=6, pady=18)
                ctk.CTkLabel(
                    empty_box,
                    text="No crash reports recorded.\nGateFinder V2.0 has been running cleanly with zero unhandled exceptions.",
                    font=ctk.CTkFont(size=13), text_color="#94A3B8", justify="center"
                ).pack(padx=20, pady=24)
                return

            for rep in reports:
                item = ctk.CTkFrame(scroll, fg_color="#131822", corner_radius=8, border_width=1, border_color="#1E293B")
                item.pack(fill="x", padx=4, pady=5)
                top_r = ctk.CTkFrame(item, fg_color="transparent")
                top_r.pack(fill="x", padx=12, pady=(8, 4))
                ctk.CTkLabel(
                    top_r,
                    text=f"{rep.get('id', 'CRASH')}  •  {rep.get('timestamp', '')}",
                    font=ctk.CTkFont(size=12, weight="bold"), text_color="#F8FAFC"
                ).pack(side="left")
                ctk.CTkButton(
                    top_r, text="Send Report via Email", width=145, height=24, corner_radius=6,
                    fg_color="#252932", hover_color="#334155", text_color="#38BDF8",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=lambda r=rep: cr.open_mailto_for_report(r)
                ).pack(side="right")
                ctk.CTkLabel(
                    item,
                    text=f"{rep.get('exception_type', 'Exception')}: {rep.get('exception_message', '')}",
                    font=ctk.CTkFont(size=11), text_color="#CBD5E1", anchor="w", justify="left"
                ).pack(fill="x", padx=12, pady=(0, 8))

        _populate()

        ctk.CTkFrame(outer, height=1, fg_color="#1E2532").pack(fill="x")
        ftr = ctk.CTkFrame(outer, fg_color="transparent")
        ftr.pack(fill="x", padx=18, pady=(10, 12))

        def _clear():
            cr.clear_crash_history()
            _populate()

        ctk.CTkButton(
            ftr, text="Clear History", width=110, height=30, corner_radius=6,
            fg_color="#1E2532", hover_color="#2B3446", text_color="#94A3B8",
            font=ctk.CTkFont(size=12, weight="bold"), command=_clear
        ).pack(side="left")

        ctk.CTkButton(
            ftr, text="Close", width=90, height=30, corner_radius=6,
            fg_color="#00B4D8", hover_color="#0284C7", text_color="#081018",
            font=ctk.CTkFont(size=12, weight="bold"), command=modal.destroy
        ).pack(side="right")

    def open_legal_modal(self, initial_tab="EULA"):
        """Opens the SceneryX-style LEGAL & COMPLIANCE modal window (EULA / Privacy Policy / Third-Party Licenses)."""
        from legal_and_diagnostics import (
            ensure_local_legal_files, get_legal_dir,
            EULA_SECTIONS, PRIVACY_SECTIONS, THIRD_PARTY_SECTIONS
        )
        ensure_local_legal_files()
        top_win = self.winfo_toplevel()

        modal = ctk.CTkToplevel(top_win)
        modal.title("GateFinder - Legal & Compliance")
        modal.geometry("780x570")
        modal.configure(fg_color="#0B0E14")
        modal.transient(top_win)
        modal.grab_set()
        if hasattr(top_win, "_apply_window_icon"):
            top_win._apply_window_icon(modal)

        outer = ctk.CTkFrame(modal, fg_color="#0B0E14", corner_radius=10, border_width=1, border_color="#1E2532")
        outer.pack(fill="both", expand=True, padx=8, pady=8)

        # Header
        hdr = ctk.CTkFrame(outer, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(14, 10))
        ctk.CTkLabel(
            hdr, text="LEGAL & COMPLIANCE",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC"
        ).pack(side="left")

        ctk.CTkFrame(outer, height=1, fg_color="#1E2532").pack(fill="x")

        # Segmented Tab Bar Row
        tab_row = ctk.CTkFrame(outer, fg_color="transparent")
        tab_row.pack(fill="x", padx=20, pady=(10, 8))

        seg_pill = ctk.CTkFrame(tab_row, fg_color="#0F131C", corner_radius=8, border_width=1, border_color="#1E293B")
        seg_pill.pack(side="left")

        # Bottom Footer Bar (packed with side="bottom" first so it is always visible)
        ftr = ctk.CTkFrame(outer, fg_color="transparent")
        ftr.pack(side="bottom", fill="x", padx=20, pady=(10, 12))
        ctk.CTkFrame(outer, height=1, fg_color="#1E2532").pack(side="bottom", fill="x")

        ftr_left = ctk.CTkFrame(ftr, fg_color="transparent")
        ftr_left.pack(side="left")
        ctk.CTkLabel(
            ftr_left, text="© 2026 Sidestick Priority   •   ",
            font=ctk.CTkFont(size=12), text_color="#94A3B8"
        ).pack(side="left")

        lbl_link = ctk.CTkLabel(
            ftr_left, text="Local files available in %APPDATA%\\GateFinder\\legal\\",
            font=ctk.CTkFont(size=12, underline=True), text_color="#38BDF8", cursor="hand2"
        )
        lbl_link.pack(side="left")
        lbl_link.bind("<Button-1>", lambda e: os.startfile(get_legal_dir()) if os.path.isdir(get_legal_dir()) else None)

        ctk.CTkButton(
            ftr, text="Close", width=90, height=30, corner_radius=6,
            fg_color="#00B4D8", hover_color="#0284C7", text_color="#081018",
            font=ctk.CTkFont(size=12, weight="bold"), command=modal.destroy
        ).pack(side="right")

        tab_btns = {}
        scroll_body = ctk.CTkScrollableFrame(outer, fg_color="#0B0E14", corner_radius=0)
        scroll_body.pack(fill="both", expand=True, padx=16, pady=(2, 8))

        def _forward_wheel(event):
            try:
                scroll_body._parent_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass
            return "break"

        tab_configs = {
            "EULA": {
                "title": "End User License Agreement (EULA)",
                "sub": "Author & Licensor: Sidestick Priority • Software: GateFinder (Desktop Application for Microsoft Windows)",
                "intro": "Please review the terms of this license carefully. By downloading, installing, copying, or using GateFinder, you agree to be bound by the terms below.",
                "sections": EULA_SECTIONS,
            },
            "Privacy Policy": {
                "title": "Privacy Policy & Diagnostic Data Protection",
                "sub": "Author & Data Controller: Sidestick Priority (contact@sidestickpriority.com) • Software: GateFinder V2.0",
                "intro": "GateFinder is engineered on a strict privacy-by-design principle. Your personal data, SimBrief credentials, and local file paths remain strictly on your device.",
                "sections": PRIVACY_SECTIONS,
            },
            "Third-Party Licenses": {
                "title": "Third-Party Open Source & Data Licenses",
                "sub": "Software: GateFinder V2.0 • Open-Source Software & Cartographic Attributions",
                "intro": "GateFinder incorporates and interacts with the following third-party open-source libraries, APIs, and cartographic data providers.",
                "sections": THIRD_PARTY_SECTIONS,
            },
        }

        def _select_tab(tab_name):
            for t_key, b_widget in tab_btns.items():
                if t_key == tab_name:
                    b_widget.configure(fg_color="#232B3A", text_color="#F8FAFC")
                else:
                    b_widget.configure(fg_color="transparent", text_color="#94A3B8")

            for w in scroll_body.winfo_children():
                w.destroy()

            try:
                scroll_body._parent_canvas.yview_moveto(0.0)
            except Exception:
                pass

            cfg = tab_configs.get(tab_name, tab_configs["EULA"])

            # Top Highlighted Callout Box (SceneryX Style)
            banner = ctk.CTkFrame(
                scroll_body, fg_color="#101520", corner_radius=8,
                border_width=1, border_color="#1E293B"
            )
            banner.pack(fill="x", padx=6, pady=(4, 14))
            l_t = ctk.CTkLabel(
                banner, text=cfg["title"],
                font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC", anchor="w"
            )
            l_t.pack(fill="x", padx=16, pady=(12, 2))
            l_s = ctk.CTkLabel(
                banner, text=cfg["sub"],
                font=ctk.CTkFont(size=12), text_color="#94A3B8", anchor="w"
            )
            l_s.pack(fill="x", padx=16, pady=(0, 8))
            l_i = ctk.CTkLabel(
                banner, text=cfg["intro"],
                font=ctk.CTkFont(size=12), text_color="#CBD5E1", anchor="w", justify="left", wraplength=680
            )
            l_i.pack(fill="x", padx=16, pady=(0, 12))
            for bw in (banner, l_t, l_s, l_i):
                bw.bind("<MouseWheel>", _forward_wheel)

            for sec_title, items in cfg["sections"]:
                sec_lbl = ctk.CTkLabel(
                    scroll_body, text=sec_title,
                    font=ctk.CTkFont(size=12, weight="bold"), text_color="#F8FAFC", anchor="w"
                )
                sec_lbl.pack(fill="x", padx=8, pady=(10, 4))
                sec_lbl.bind("<MouseWheel>", _forward_wheel)
                for label_bold, body_txt in items:
                    full_len = len(label_bold or "") + len(body_txt or "")
                    est_lines = max(1, int((full_len + 86) // 82))
                    rt = tk.Text(
                        scroll_body,
                        height=est_lines,
                        bg="#0B0E14",
                        fg="#94A3B8",
                        bd=0,
                        highlightthickness=0,
                        wrap="word",
                        font=("Segoe UI", 10),
                        padx=8,
                        pady=2,
                        cursor="arrow",
                        spacing1=2,
                        spacing2=3,
                        spacing3=2,
                    )
                    rt.tag_configure("bold_hdr", font=("Segoe UI", 10, "bold"), foreground="#F8FAFC")
                    rt.tag_configure("body_txt", font=("Segoe UI", 10), foreground="#94A3B8")
                    rt.tag_configure("code_pill", font=("Consolas", 9, "bold"), background="#161E2E", foreground="#E2E8F0")
                    if label_bold:
                        rt.insert("end", label_bold + " ", "bold_hdr")
                    if "GateFinder.exe" in body_txt:
                        parts = body_txt.split("GateFinder.exe")
                        for idx_p, part_str in enumerate(parts):
                            if part_str:
                                rt.insert("end", part_str, "body_txt")
                            if idx_p < len(parts) - 1:
                                rt.insert("end", " GateFinder.exe ", "code_pill")
                    else:
                        rt.insert("end", body_txt, "body_txt")
                    rt.configure(state="disabled")
                    rt.bind("<MouseWheel>", _forward_wheel)
                    rt.pack(fill="x", padx=6, pady=(1, 3))

        for t_name in ("EULA", "Privacy Policy", "Third-Party Licenses"):
            btn = ctk.CTkButton(
                seg_pill, text=t_name, height=28,
                width=68 if t_name == "EULA" else (112 if t_name == "Privacy Policy" else 148),
                corner_radius=6, border_width=0,
                fg_color="transparent", hover_color="#1E2532",
                text_color="#94A3B8", font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda tn=t_name: _select_tab(tn)
            )
            btn.pack(side="left", padx=3, pady=3)
            tab_btns[t_name] = btn

        _select_tab(initial_tab if initial_tab in tab_configs else "EULA")

    def open_v1_migration_modal(self):
        """
        Provides a guided one-click upgrade & cleanup wizard for users upgrading from GateFinder V1.x:
        - Automatically detects legacy 'wildbill75-gatefinder' packages in Community and old V1.x folders from exe.xml / disk.
        - Allows browsing for an old GateFinder V1.x folder if stored elsewhere.
        - Imports SimBrief/GSX/Community settings, removes 'wildbill75-gatefinder', installs 'gatefinder-ingame-panel' V2.0,
          updates exe.xml, and optionally removes the old V1.x directory.
        """
        from legal_and_diagnostics import LegacyMigrationManager
        top_win = self.winfo_toplevel()

        modal = ctk.CTkToplevel(top_win)
        modal.title("GateFinder - Upgrade & Clean Legacy V1.x")
        modal.geometry("680x430")
        modal.configure(fg_color="#0D1017")
        modal.transient(top_win)
        modal.grab_set()
        if hasattr(top_win, "_apply_window_icon"):
            top_win._apply_window_icon(modal)

        outer = ctk.CTkFrame(modal, fg_color="#0D1017", corner_radius=10, border_width=1, border_color="#1E2532")
        outer.pack(fill="both", expand=True, padx=10, pady=10)

        hdr = ctk.CTkFrame(outer, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(14, 10))
        ctk.CTkLabel(
            hdr, text="UPGRADE FROM GATEFINDER V1.x TO V2.0",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC"
        ).pack(side="left")

        ctk.CTkFrame(outer, height=1, fg_color="#1E2532").pack(fill="x")

        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=12)

        info_box = ctk.CTkFrame(body, fg_color="#131822", corner_radius=8, border_width=1, border_color="#1E293B")
        info_box.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            info_box,
            text=(
                "This tool ensures a clean transition from any previous GateFinder V1.x installation:\n"
                "  1. Imports your SimBrief ID and MSFS/GSX paths from your old V1.x settings.json\n"
                "  2. Uninstalls the legacy 'wildbill75-gatefinder' package from all MSFS Community folders\n"
                "  3. Installs the new 'gatefinder-ingame-panel' V2.0 package with the updated GF toolbar icon\n"
                "  4. Updates MSFS exe.xml auto-start entries and optionally deletes the old V1.x folder"
            ),
            font=ctk.CTkFont(size=12), text_color="#CBD5E1", justify="left", anchor="w"
        ).pack(fill="x", padx=14, pady=12)

        # Detect any legacy folder found on startup
        mig_summary = getattr(self.backend, "migration_summary", None) or {}
        found_dirs = mig_summary.get("legacy_app_folders_found") or []
        initial_v1_dir = found_dirs[0] if found_dirs else ""

        lbl_dir = ctk.CTkLabel(
            body, text="Old GateFinder V1.x Folder (optional — select to import settings & remove old folder):",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#E2E8F0", anchor="w"
        )
        lbl_dir.pack(fill="x", pady=(4, 4))

        dir_row = ctk.CTkFrame(body, fg_color="transparent")
        dir_row.pack(fill="x", pady=(0, 10))

        v1_entry = ctk.CTkEntry(
            dir_row, height=28, corner_radius=6, border_width=0,
            fg_color="#252932", text_color="#FFFFFF",
            placeholder_text="Leave blank to only clean Community folders & exe.xml, or browse to old V1.x folder"
        )
        v1_entry.pack(side="left", fill="x", expand=True)
        if initial_v1_dir:
            v1_entry.insert(0, initial_v1_dir)

        def _browse_v1():
            from tkinter import filedialog
            d = filedialog.askdirectory(title="Select Old GateFinder V1.x Folder")
            if d:
                v1_entry.delete(0, "end")
                v1_entry.insert(0, d)

        ctk.CTkButton(
            dir_row, text="Browse...", width=90, height=28, corner_radius=6,
            fg_color="#2B303B", hover_color="#383E4C", text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"), command=_browse_v1
        ).pack(side="left", padx=(8, 0))

        del_old_var = ctk.BooleanVar(value=True)
        chk_del_old = ctk.CTkCheckBox(
            body,
            text="Delete the old GateFinder V1.x folder from disk after migrating settings",
            variable=del_old_var,
            font=ctk.CTkFont(size=12), text_color="#E2E8F0",
            fg_color="#578DA8", hover_color="#4A6C7D", border_color="#383E4C",
            checkbox_width=18, checkbox_height=18, corner_radius=5
        )
        chk_del_old.pack(anchor="w", pady=(2, 8))

        lbl_status = ctk.CTkLabel(body, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color="#10B981", anchor="w")
        lbl_status.pack(fill="x", pady=(4, 0))

        def _execute_upgrade():
            import shutil
            selected_old = v1_entry.get().strip()
            current_dir = os.path.normpath(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)))

            # 1. If a valid old V1 folder is specified, import its settings.json
            imported_cfg = False
            if selected_old and os.path.isdir(selected_old):
                old_cfg_file = os.path.join(selected_old, "settings.json")
                if os.path.isfile(old_cfg_file):
                    try:
                        with open(old_cfg_file, "r", encoding="utf-8") as f:
                            old_s = json.load(f)
                        for k in ("simbrief_username", "gsx_profile_path", "msfs_community_path", "msfs_community2024_path", "sayintentions_api_key"):
                            if old_s.get(k) and not self.config.settings.get(k):
                                self.config.settings[k] = old_s[k]
                        self.config.save()
                        # Refresh UI entries
                        if self.config.settings.get("simbrief_username"):
                            self.simbrief_entry.delete(0, "end")
                            self.simbrief_entry.insert(0, self.config.settings["simbrief_username"])
                        imported_cfg = True
                    except Exception:
                        pass

            # 2. Run migration manager (cleans wildbill75-gatefinder, updates exe.xml, installs gatefinder-ingame-panel)
            mgr = LegacyMigrationManager(self.config, self.autostart)
            res = mgr.run_startup_migration()

            # 3. Also ensure gatefinder-ingame-panel is installed in configured Community folders
            self.backend._sync_msfs_community_packages()
            self.refresh_dynamic_statuses()

            # 4. Optionally delete old V1 folder if requested and safe
            deleted_old = False
            if selected_old and os.path.isdir(selected_old) and del_old_var.get():
                norm_old = os.path.normpath(os.path.abspath(selected_old))
                if norm_old.lower() != current_dir.lower() and not current_dir.lower().startswith(norm_old.lower() + os.sep):
                    try:
                        shutil.rmtree(norm_old)
                        deleted_old = True
                    except Exception as e:
                        print(f"[Migration] Could not delete old folder {norm_old}: {e}")

            lines = ["Upgrade & Cleanup completed successfully:"]
            if imported_cfg or res.get("migrated_settings_from"):
                lines.append("• Migrated user settings from GateFinder V1.x")
            lines.append("• Cleaned legacy 'wildbill75-gatefinder' from MSFS Community folders")
            lines.append("• Installed & synced 'gatefinder-ingame-panel' V2.0")
            if deleted_old:
                lines.append(f"• Removed old V1.x folder: {selected_old}")
            messagebox.showinfo("Upgrade Complete", "\n".join(lines))
            modal.destroy()

        ctk.CTkFrame(outer, height=1, fg_color="#1E2532").pack(fill="x")
        ftr = ctk.CTkFrame(outer, fg_color="transparent")
        ftr.pack(fill="x", padx=20, pady=(10, 12))

        ctk.CTkButton(
            ftr, text="Cancel", width=90, height=30, corner_radius=6,
            fg_color="#1E2532", hover_color="#2B3446", text_color="#94A3B8",
            font=ctk.CTkFont(size=12, weight="bold"), command=modal.destroy
        ).pack(side="left")

        ctk.CTkButton(
            ftr, text="Clean Legacy V1.x & Install V2.0", width=230, height=30, corner_radius=6,
            fg_color="#00B4D8", hover_color="#0284C7", text_color="#081018",
            font=ctk.CTkFont(size=12, weight="bold"), command=_execute_upgrade
        ).pack(side="right")

    def save_settings_silent(self):
        new_vals = {
            "simbrief_username": self.simbrief_entry.get().strip(),
            "gsx_profile_path": self.gsx_entry.get().strip(),
            "msfs_community_path": self.community2020_entry.get().strip(),
            "msfs_community2024_path": self.community2024_entry.get().strip(),
            "ignored_gates": "",
            "sayintentions_api_key": self.si_api_key_entry.get().strip(),
            "auto_start": self.autostart_var.get(),
            "auto_quit_with_msfs": self.auto_quit_msfs_var.get() if hasattr(self, "auto_quit_msfs_var") else False,
            "auto_fetch": self.autofetch_var.get(),
            "prioritize_ai_atc": self.prioritize_ai_atc_var.get(),
            "check_online_traffic": self.check_online_traffic_var.get(),
            "auto_lock_turnaround": self.auto_lock_turnaround_var.get(),
            "hibernate_map_in_flight": self.hibernate_map_in_flight_var.get(),
            "auto_clear_ai": self.auto_clear_ai_var.get(),
            "mars_overlap_protection": self.mars_overlap_protection_var.get() if hasattr(self, "mars_overlap_protection_var") else True,
            "auto_inject_gsx": self.auto_inject_gsx_var.get(),
            "force_cargo_mode": self.force_cargo_var.get(),
            "send_crash_reports": self.send_crash_reports_var.get() if hasattr(self, "send_crash_reports_var") else True,
            "share_flight_stats": self.share_flight_stats_var.get() if hasattr(self, "share_flight_stats_var") else True,
            "show_maps": True,
            "show_wingspan": True,
            "exclude_cargo": False,
            "exclude_ga_ramp": False,
        }
        changed_keys = {
            k for k, v in new_vals.items()
            if self.config.settings.get(k) != v
        }
        if not changed_keys:
            return

        prev_auto = self.config.settings.get("auto_start", False)
        self.config.settings.update(new_vals)
        self.config.save()

        auto = new_vals["auto_start"]
        if auto != prev_auto:
            if auto:
                self.autostart.enable()
            else:
                self.autostart.disable()
        elif auto and hasattr(self.autostart, "is_enabled") and not self.autostart.is_enabled():
            self.autostart.enable()

        try:
            self.on_save_callback(changed_keys)
        except TypeError:
            self.on_save_callback()

    def save_settings(self):
        self.save_settings_silent()
        self.on_close_callback()

class LidoVectorChart(ctk.CTkFrame):
    """
    Interactive Geo-Referenced Lido-Styled Vector Ground Chart (APC / AGC).
    Renders airport aprons, terminal buildings, runways with thresholds, taxiways,
    holding points, neighboring Lido-orange stands, the active A* taxi route with
    directional chevrons, and the live SimConnect aircraft icon.
    """
    def __init__(self, parent, initial_theme="night", backend=None, on_stand_click=None, on_runway_click=None, **kwargs):
        super().__init__(parent, fg_color="#1B1E24", corner_radius=12, border_width=0, **kwargs)
        self.theme_mode = initial_theme  # "day" (Lido paper chart) or "night" (Lido EFB dark)
        self.backend = backend
        self.on_stand_click = on_stand_click
        self.on_runway_click = on_runway_click
        self._tk_logo_cache = {}
        self.chart_data = None
        self.airport_data = None
        self.phase_mode = "departure"
        self.user_aircraft = None
        self.follow_aircraft = False
        self.heading_up = False
        self._last_live_status = None
        self._was_airborne = False
        self.view_mode = "route"  # "route" (AGC) or "terminal" (APC)

        # Viewport state: center (lat, lon) and scale (meters per pixel)
        self.center_lat = 0.0
        self.center_lon = 0.0
        self.meters_per_pixel = 4.5
        self._drag_start = None
        self._click_origin = None
        self._did_drag = False
        self._initial_fit_done = False
        self._stand_hitboxes = []
        self._rwy_hitboxes = []
        self._hovered_stand_info = None
        self._stand_ctx_modal = None

        # Top Lido Chart Controls Header Bar (SimConnect pill on left, chart control pills on right)
        self.header_bar = ctk.CTkFrame(self, height=48, corner_radius=0, fg_color="#1B1E24", border_width=0)
        self.header_bar.pack(fill="x", side="top", padx=0, pady=0)
        self.header_bar.pack_propagate(False)

        self.lbl_simconnect_pill = ctk.CTkLabel(
            self.header_bar,
            text="SimConnect Standby",
            height=32,
            corner_radius=8,
            fg_color="#2B303B",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            padx=14
        )
        self.lbl_simconnect_pill.pack(side="left", padx=(12, 5), pady=8)

        btn_cfg = {
            "height": 34,
            "corner_radius": 8,
            "font": ctk.CTkFont(size=12, weight="bold"),
            "fg_color": "#2B303B",
            "hover_color": "#383E4C",
            "border_width": 0,
            "text_color": "#FFFFFF"
        }
        self.btn_theme = ctk.CTkButton(self.header_bar, text="Map Day", width=92, command=self.toggle_theme, **btn_cfg)
        self.btn_theme.pack(side="right", padx=(4, 10), pady=8)
        Tooltip(self.btn_theme, "Switch between Day and Night map themes")

        self.btn_follow = ctk.CTkButton(self.header_bar, text="Follow + Hdg Up", width=130, command=self.toggle_follow, **btn_cfg)
        self.btn_follow.pack(side="right", padx=4, pady=8)
        Tooltip(self.btn_follow, "Follow live aircraft position with Heading-Up rotation")

        self.btn_agc = ctk.CTkButton(self.header_bar, text="Route", width=74, command=self.fit_route_view, **btn_cfg)
        self.btn_agc.pack(side="right", padx=4, pady=8)
        Tooltip(self.btn_agc, "Fit full airport layout & taxi route")

        self.btn_apc = ctk.CTkButton(self.header_bar, text="Gate", width=70, command=self.fit_terminal_view, **btn_cfg)
        self.btn_apc.pack(side="right", padx=4, pady=8)
        Tooltip(self.btn_apc, "Zoom to terminal & assigned stand")

        self.btn_zoom_out = ctk.CTkButton(self.header_bar, text="-", width=36, command=lambda: self.zoom_by(1.33), **btn_cfg)
        self.btn_zoom_out.pack(side="right", padx=4, pady=8)

        self.btn_zoom_in = ctk.CTkButton(self.header_bar, text="+", width=36, command=lambda: self.zoom_by(0.75), **btn_cfg)
        self.btn_zoom_in.pack(side="right", padx=4, pady=8)

        import webbrowser
        self.btn_sceneryx_promo = ctk.CTkButton(
            self.header_bar,
            text="BUY SCENERY X & GET 10% DISCOUNT",
            height=32,
            width=238,
            corner_radius=8,
            fg_color="#132235",
            hover_color="#1B314B",
            border_width=1,
            border_color="#0284C7",
            text_color="#38BDF8",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: webbrowser.open("https://sidestickpriority.gumroad.com/l/zzlsus/SCENERYX-10")
        )
        self.btn_sceneryx_promo.pack(side="left", padx=(4, 6), pady=8)
        Tooltip(self.btn_sceneryx_promo, "Boost your MSFS 2020/2024 FPS & VRAM with SceneryX by Sidestick Priority — Click to claim your 10% discount on Gumroad!")

        # Main Vector Drawing Canvas
        self.canvas = tkinter.Canvas(self, bg="#0B1120", highlightthickness=0, cursor="arrow")
        self.canvas.pack(fill="both", expand=True, padx=2, pady=2)

        # Bind interactive pan, zoom, and resize events
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_click)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Motion>", self._on_mouse_motion)
        self.canvas.bind("<Leave>", self._on_mouse_leave)
        self._update_theme_buttons()

    def _get_palette(self):
        if self.theme_mode == "day":
            # Authentic Lido Paper Chart Palette
            return {
                "bg": "#ECEAE2",
                "apron_fill": "#D5D8DC",
                "apron_outline": "#9CA3AF",
                "term_fill": "#1F2937",
                "term_outline": "#111827",
                "term_text": "#FFFFFF",
                "apron_text": "#334155",
                "twy_border": "#6B7280",
                "twy_fill": "#BFC4CA",
                "twy_center": "#D97706",
                "twy_label_bg": "#FACC15",
                "twy_label_border": "#0F172A",
                "twy_label_fg": "#090D16",
                "rwy_shoulder": "#334155",
                "rwy_fill": "#1E293B",
                "rwy_outline": "#0F172A",
                "rwy_edge": "#E2E8F0",
                "rwy_center": "#FFFFFF",
                "rwy_markings": "#F8FAFC",
                "rwy_circle_fill": "#0F293D",
                "rwy_circle_ring": "#0284C7",
                "stand_bg": "#FFF7ED",
                "stand_border": "#EA580C",
                "stand_fg": "#9A3412",
                "route_glow": "#047857",
                "route_main": "#10B981",
                "route_arrow": "#FFFFFF",
                "rollout": "#0284C7",
                "hold_bar": "#EAB308",
                "hold_bar_border": "#0F172A",
                "grid_line": "#DFDDD4"
            }
        else:
            # Authentic Lido AMM / Navigraph Cockpit EFB Dark Palette
            return {
                "bg": "#2B353E",
                "apron_fill": "#465664",
                "apron_outline": "#526474",
                "term_fill": "#070A0F",
                "term_outline": "#1A242F",
                "term_text": "#FFFFFF",
                "apron_text": "#F1F5F9",
                "twy_border": "#364450",
                "twy_fill": "#4E6070",
                "twy_center": "#EAB308",
                "twy_label_bg": "#E5A91F",
                "twy_label_border": "#0B111A",
                "twy_label_fg": "#090D16",
                "rwy_shoulder": "#24303C",
                "rwy_fill": "#111722",
                "rwy_outline": "#64748B",
                "rwy_edge": "#E2E8F0",
                "rwy_center": "#F8FAFC",
                "rwy_markings": "#F1F5F9",
                "rwy_circle_fill": "#0C2B3D",
                "rwy_circle_ring": "#22D3EE",
                "stand_bg": "#1D2630",
                "stand_border": "#F0743E",
                "stand_fg": "#FFFFFF",
                "route_glow": "#065F46",
                "route_main": "#10B981",
                "route_arrow": "#ECFDF5",
                "rollout": "#38BDF8",
                "hold_bar": "#FACC15",
                "hold_bar_border": "#090D16",
                "grid_line": "#2F3A44"
            }

    def toggle_theme(self):
        self.theme_mode = "day" if self.theme_mode == "night" else "night"
        self._update_theme_buttons()
        self.redraw()

    def _is_airborne(self):
        return bool(
            self.user_aircraft
            and self.user_aircraft.get("connected")
            and not self.user_aircraft.get("in_menu")
            and self.user_aircraft.get("on_ground") is False
            and float(self.user_aircraft.get("gs") or 0.0) >= 35.0
        )

    def _get_airline_camaieu(self):
        al_code = str((self.airport_data or {}).get("airline_code") or "").strip().upper()
        if self.backend and hasattr(self.backend, "get_airline_camaieu_palette"):
            return self.backend.get_airline_camaieu_palette(al_code)
        return {
            "s1": "#578DA8",
            "s2": "#517B90",
            "s3": "#4A6C7D",
            "s4": "#435D6B",
            "s5": "#4E788E",
            "s6": "#3F5663",
            "accent": "#66A1BE",
        }

    def set_simconnect_status(self, text):
        if hasattr(self, "lbl_simconnect_pill") and self.lbl_simconnect_pill and self.lbl_simconnect_pill.winfo_exists():
            if getattr(self, "_last_simconnect_pill_txt", None) != text:
                self._last_simconnect_pill_txt = text
                self.lbl_simconnect_pill.configure(text=text, fg_color="#2B303B", text_color="#FFFFFF")

    def _update_theme_buttons(self):
        airborne = self._is_airborne()
        if airborne:
            self.follow_aircraft = False
            self.heading_up = False
        elif not self.follow_aircraft:
            self.heading_up = False
        else:
            self.heading_up = True

        al_code = str((self.airport_data or {}).get("airline_code") or "").strip().upper()
        cam = self._get_airline_camaieu()
        btn_state_key = (self.theme_mode, airborne, bool(self.follow_aircraft), self.view_mode, al_code, cam["s1"], cam["s2"])
        if getattr(self, "_last_btn_state_key", None) == btn_state_key:
            return
        self._last_btn_state_key = btn_state_key

        if self.theme_mode == "day":
            self.btn_theme.configure(text="Map Night", fg_color=cam["s3"], hover_color=cam["s4"], text_color="#FFFFFF")
        else:
            self.btn_theme.configure(text="Map Day", fg_color="#2B303B", hover_color="#383E4C", text_color="#FFFFFF")

        if airborne:
            self.btn_follow.configure(state="disabled", text="Follow + Hdg Up", fg_color="#2B303B", hover_color="#2B303B", text_color="#64748B")
            if self.view_mode == "terminal":
                self.btn_apc.configure(fg_color=cam["s2"], hover_color=cam["s4"])
                self.btn_agc.configure(fg_color="#2B303B", hover_color="#383E4C")
            else:
                self.btn_agc.configure(fg_color=cam["s2"], hover_color=cam["s4"])
                self.btn_apc.configure(fg_color="#2B303B", hover_color="#383E4C")
        elif self.follow_aircraft:
            self.btn_follow.configure(state="normal", text="Follow + Hdg Up", fg_color=cam["s2"], hover_color=cam["s4"], text_color="#FFFFFF")
            self.btn_apc.configure(fg_color="#2B303B", hover_color="#383E4C")
            self.btn_agc.configure(fg_color="#2B303B", hover_color="#383E4C")
        else:
            self.btn_follow.configure(state="normal", text="Follow + Hdg Up", fg_color="#2B303B", hover_color="#383E4C", text_color="#FFFFFF")
            if self.view_mode == "terminal":
                self.btn_apc.configure(fg_color=cam["s2"], hover_color=cam["s4"])
                self.btn_agc.configure(fg_color="#2B303B", hover_color="#383E4C")
            else:
                self.btn_agc.configure(fg_color=cam["s2"], hover_color=cam["s4"])
                self.btn_apc.configure(fg_color="#2B303B", hover_color="#383E4C")

    def _compute_draw_sig(self):
        ap = self.airport_data or {}
        tr = ap.get("taxi_route") or {}
        r_pts = tr.get("route_points") or []
        u = self.user_aircraft or {}
        u_conn = bool(u.get("connected"))
        u_og = u.get("on_ground")
        u_lat = round(float(u["lat"]), 5) if (u_conn and u.get("lat") is not None) else None
        u_lon = round(float(u["lon"]), 5) if (u_conn and u.get("lon") is not None) else None
        u_hdg = round(float(u["heading"]), 1) if (u_conn and u.get("heading") is not None) else None
        return (
            self.theme_mode,
            self.phase_mode,
            ap.get("icao"),
            ap.get("airline_code"),
            ap.get("gate"),
            ap.get("selected_runway"),
            tr.get("live_status"),
            tr.get("detected_exit"),
            len(r_pts),
            tuple(r_pts[0]) if r_pts else None,
            tuple(r_pts[-1]) if r_pts else None,
            bool(self.follow_aircraft),
            bool(self.heading_up),
            self.view_mode,
            round(float(self.center_lat), 6),
            round(float(self.center_lon), 6),
            round(float(self.meters_per_pixel), 4),
            u_conn,
            u_og,
            u_lat,
            u_lon,
            u_hdg,
            getattr(self.backend, "logo_generation", 0) if self.backend else 0,
            self.canvas.winfo_width(),
            self.canvas.winfo_height()
        )

    def _get_tk_logo(self, code, size=16):
        if not self.backend or not code:
            return None
        try:
            from PIL import ImageTk
            c = str(code).strip().upper()
            gen = getattr(self.backend, "logo_generation", 0)
            key = (c, int(size), gen)
            if key in self._tk_logo_cache:
                return self._tk_logo_cache[key]
            pil_im = self.backend.get_airline_pill_pil_image(c, size=size, allow_network=False)
            if pil_im is None:
                return None
            tk_im = ImageTk.PhotoImage(pil_im)
            self._tk_logo_cache[key] = tk_im
            return tk_im
        except Exception:
            return None

    def toggle_orientation(self):
        self.toggle_follow()

    def _apply_smart_follow_camera(self, snap=False):
        """
        Smart Follow Camera: automatically keeps both the live aircraft and the target Gate
        (or Runway Hold-Short point on departure) framed on screen in Heading-Up orientation,
        dynamically adapting zoom (`meters_per_pixel`) unless the user has manually adjusted
        zoom or pan while Follow + Hdg Up is locked.
        """
        pan_lat = float(getattr(self, "_follow_pan_lat_offset", 0.0) or 0.0)
        pan_lon = float(getattr(self, "_follow_pan_lon_offset", 0.0) or 0.0)
        user_zoom = getattr(self, "_follow_user_zoom_mpp", None)

        if not self.user_aircraft or self.user_aircraft.get("lat") is None or self.user_aircraft.get("lon") is None:
            if self.airport_data and self.airport_data.get("lat") is not None:
                self.center_lat = float(self.airport_data["lat"]) + pan_lat
                self.center_lon = float(self.airport_data["lon"]) + pan_lon
                self.meters_per_pixel = float(user_zoom) if user_zoom is not None else 0.85
            return

        ac_lat = float(self.user_aircraft["lat"])
        ac_lon = float(self.user_aircraft["lon"])
        tgt_lat = self.airport_data.get("lat") if self.airport_data else None
        tgt_lon = self.airport_data.get("lon") if self.airport_data else None

        if self.phase_mode == "departure" and self.airport_data:
            tr = self.airport_data.get("taxi_route") or {}
            r_pts = tr.get("route_points") or []
            if len(r_pts) >= 2:
                tgt_lat = float(r_pts[-1][0])
                tgt_lon = float(r_pts[-1][1])

        if tgt_lat is None or tgt_lon is None:
            self.center_lat = ac_lat + pan_lat
            self.center_lon = ac_lon + pan_lon
            self.meters_per_pixel = float(user_zoom) if user_zoom is not None else 0.85
            return

        tgt_lat = float(tgt_lat)
        tgt_lon = float(tgt_lon)
        cos_lat = max(0.15, math.cos(math.radians(ac_lat)))
        dx_m = (tgt_lon - ac_lon) * 111320.0 * cos_lat
        dy_m = -(tgt_lat - ac_lat) * 111320.0
        dist_m = math.hypot(dx_m, dy_m)

        if dist_m > 12000.0:
            self.center_lat = ac_lat + pan_lat
            self.center_lon = ac_lon + pan_lon
            self.meters_per_pixel = float(user_zoom) if user_zoom is not None else 0.85
            return

        self.center_lat = ((ac_lat + tgt_lat) / 2.0) + pan_lat
        self.center_lon = ((ac_lon + tgt_lon) / 2.0) + pan_lon

        if user_zoom is not None:
            self.meters_per_pixel = float(user_zoom)
            return

        if self.heading_up and self.user_aircraft.get("connected") and self.user_aircraft.get("heading") is not None:
            ang = -math.radians(float(self.user_aircraft["heading"]))
            rx_m = dx_m * math.cos(ang) - dy_m * math.sin(ang)
            ry_m = dx_m * math.sin(ang) + dy_m * math.cos(ang)
        else:
            rx_m, ry_m = dx_m, dy_m

        w = max(self.canvas.winfo_width(), 540)
        h = max(self.canvas.winfo_height(), 420)
        span_x_m = max(95.0, abs(rx_m) * 1.48)
        span_y_m = max(95.0, abs(ry_m) * 1.48)
        target_mpp = max(span_x_m / max(220.0, w - 100.0), span_y_m / max(200.0, h - 100.0), 0.45)
        target_mpp = min(12.0, target_mpp)

        if snap or self.meters_per_pixel <= 0.0:
            self.meters_per_pixel = target_mpp
        else:
            self.meters_per_pixel = (0.68 * self.meters_per_pixel) + (0.32 * target_mpp)

    def toggle_follow(self):
        if self._is_airborne():
            return
        self.follow_aircraft = not self.follow_aircraft
        self.heading_up = bool(self.follow_aircraft)
        self._follow_user_zoom_mpp = None
        self._follow_pan_lat_offset = 0.0
        self._follow_pan_lon_offset = 0.0
        self._initial_fit_done = True
        if self.follow_aircraft:
            self._update_theme_buttons()
            self._apply_smart_follow_camera(snap=True)
            self.redraw()
        else:
            self._update_theme_buttons()
            self.fit_route_view()

    def set_data(self, airport_data, phase_mode="departure", user_aircraft=None, preserve_camera=False):
        self.airport_data = airport_data or {}
        self.chart_data = self.airport_data.get("chart_data")
        self.phase_mode = phase_mode
        self.user_aircraft = user_aircraft

        live_st = (self.airport_data.get("taxi_route") or {}).get("live_status")
        prev_st = self._last_live_status
        self._last_live_status = live_st

        airborne = self._is_airborne()
        just_touched_down = (self._was_airborne and not airborne)
        self._was_airborne = airborne

        if airborne:
            if self.follow_aircraft or self.heading_up:
                self.follow_aircraft = False
                self.heading_up = False
            self._update_theme_buttons()
        else:
            # Auto-engage Smart Follow (Follow + Hdg Up + Dynamic Gate Zoom) at Touchdown / Rollout on Arrival
            if (
                phase_mode == "arrival"
                and (
                    just_touched_down
                    or (live_st in ("LANDING_ROLL", "TAXI_IN") and prev_st not in ("LANDING_ROLL", "TAXI_IN"))
                )
                and user_aircraft
                and user_aircraft.get("lat") is not None
            ):
                self.follow_aircraft = True
                self.heading_up = True
                self._apply_smart_follow_camera(snap=True)
            self._update_theme_buttons()

        if self.follow_aircraft and phase_mode == "departure" and live_st == "ON_RUNWAY":
            self.follow_aircraft = False
            self.heading_up = False
            self._update_theme_buttons()
            self.fit_route_view()
            return

        if self.follow_aircraft:
            self._initial_fit_done = True
            self._apply_smart_follow_camera(snap=not preserve_camera)
            if not preserve_camera or self._compute_draw_sig() != getattr(self, "_last_draw_sig", None):
                self.redraw()
            return

        if not preserve_camera or not self._initial_fit_done:
            self.fit_route_view()
            if self.canvas.winfo_width() >= 200 and self.canvas.winfo_height() >= 200:
                self._initial_fit_done = True
            else:
                self._initial_fit_done = False
        else:
            if self._compute_draw_sig() != getattr(self, "_last_draw_sig", None):
                self.redraw()

    def fit_terminal_view(self):
        self.view_mode = "terminal"
        self.follow_aircraft = False
        self.heading_up = False
        self._follow_user_zoom_mpp = None
        self._follow_pan_lat_offset = 0.0
        self._follow_pan_lon_offset = 0.0
        self._update_theme_buttons()
        glat = self.airport_data.get("lat") if self.airport_data else None
        glon = self.airport_data.get("lon") if self.airport_data else None
        if glat is not None and glon is not None:
            self.center_lat = float(glat)
            self.center_lon = float(glon)
            self.meters_per_pixel = 1.15
        elif self.chart_data:
            self.center_lat = self.chart_data.get("center_lat", 0.0)
            self.center_lon = self.chart_data.get("center_lon", 0.0)
            self.meters_per_pixel = 2.5
        self.redraw()

    def fit_route_view(self):
        self.view_mode = "route"
        self.follow_aircraft = False
        self.heading_up = False
        self._follow_user_zoom_mpp = None
        self._follow_pan_lat_offset = 0.0
        self._follow_pan_lon_offset = 0.0
        self._update_theme_buttons()
        pts = []
        if self.chart_data:
            for rwy in self.chart_data.get("runways", []):
                for p in rwy.get("points", []):
                    pts.append((float(p[0]), float(p[1])))
            for term in self.chart_data.get("terminals", []):
                for p in term.get("points", []):
                    pts.append((float(p[0]), float(p[1])))
        if self.airport_data:
            if self.airport_data.get("lat") is not None and self.airport_data.get("lon") is not None:
                pts.append((float(self.airport_data["lat"]), float(self.airport_data["lon"])))
            tr = self.airport_data.get("taxi_route") or {}
            for p in tr.get("route_points", []):
                pts.append((float(p[0]), float(p[1])))
            for p in tr.get("rollout_points", []):
                pts.append((float(p[0]), float(p[1])))

        if len(pts) >= 2:
            min_lat = min(p[0] for p in pts)
            max_lat = max(p[0] for p in pts)
            min_lon = min(p[1] for p in pts)
            max_lon = max(p[1] for p in pts)
            self.center_lat = (min_lat + max_lat) / 2.0
            self.center_lon = (min_lon + max_lon) / 2.0
            w = max(self.canvas.winfo_width(), 780)
            h = max(self.canvas.winfo_height(), 520)
            span_y_m = max(450.0, (max_lat - min_lat) * 111320.0 * 1.26)
            span_x_m = max(450.0, (max_lon - min_lon) * 111320.0 * max(0.2, math.cos(math.radians(self.center_lat))) * 1.26)
            self.meters_per_pixel = max(span_x_m / max(200, w - 64), span_y_m / max(200, h - 64), 0.9)
        elif len(pts) == 1:
            self.center_lat, self.center_lon = pts[0]
            self.meters_per_pixel = 1.8
        elif self.chart_data:
            self.center_lat = self.chart_data.get("center_lat", 0.0)
            self.center_lon = self.chart_data.get("center_lon", 0.0)
            self.meters_per_pixel = 3.8
        self.redraw()

    def zoom_by(self, factor):
        self._close_stand_context_modal()
        self.meters_per_pixel = max(0.22, min(25.0, self.meters_per_pixel * factor))
        if self.follow_aircraft:
            self._follow_user_zoom_mpp = self.meters_per_pixel
        self._update_theme_buttons()
        self.redraw()

    def _adapt_header_bar_layout(self, width_px):
        if not hasattr(self, "btn_sceneryx_promo") or not self.btn_sceneryx_promo.winfo_exists():
            return
        if width_px >= 1030:
            mode = "full"
        elif width_px >= 900:
            mode = "compact"
        else:
            mode = "hidden"
        if getattr(self, "_promo_btn_mode", None) == mode:
            return
        self._promo_btn_mode = mode
        if mode == "hidden":
            if self.btn_sceneryx_promo.winfo_ismapped():
                self.btn_sceneryx_promo.pack_forget()
        elif mode == "compact":
            self.btn_sceneryx_promo.configure(text="SCENERY X (-10%)", width=130)
            if not self.btn_sceneryx_promo.winfo_ismapped():
                self.btn_sceneryx_promo.pack(side="left", padx=(4, 6), pady=8)
        else:
            self.btn_sceneryx_promo.configure(text="BUY SCENERY X & GET 10% DISCOUNT", width=236)
            if not self.btn_sceneryx_promo.winfo_ismapped():
                self.btn_sceneryx_promo.pack(side="left", padx=(4, 6), pady=8)

    def _deferred_resize_redraw(self):
        self._resize_redraw_after_id = None
        if not self.winfo_exists():
            return
        if self.follow_aircraft:
            self._apply_smart_follow_camera(snap=True)
        self.redraw()

    def _on_resize(self, event):
        if event.width < 100 or event.height < 100:
            return
        cur_sz = (event.width, event.height)
        if getattr(self, "_last_canvas_size", None) == cur_sz:
            return
        self._last_canvas_size = cur_sz
        self._adapt_header_bar_layout(event.width)
        if not self._initial_fit_done and self.airport_data:
            if self.follow_aircraft:
                self._apply_smart_follow_camera(snap=True)
                self.redraw()
            else:
                self.fit_route_view()
            self._initial_fit_done = True
        else:
            is_sash_drag = False
            try:
                is_sash_drag = bool(getattr(self.winfo_toplevel(), "_sash_dragging", False))
            except Exception:
                pass
            if is_sash_drag:
                if getattr(self, "_resize_redraw_after_id", None) is None:
                    self._resize_redraw_after_id = self.after(32, self._deferred_resize_redraw)
            else:
                if getattr(self, "_resize_redraw_after_id", None) is not None:
                    try:
                        self.after_cancel(self._resize_redraw_after_id)
                    except Exception:
                        pass
                    self._resize_redraw_after_id = None
                if self.follow_aircraft:
                    self._apply_smart_follow_camera(snap=True)
                self.redraw()

    def _on_drag_start(self, event):
        self._drag_start = (event.x, event.y)
        self._click_origin = (event.x, event.y)
        self._did_drag = False
        self._hovered_stand_info = None
        self.canvas.delete("stand_hover_tooltip")
        self.canvas.configure(cursor="hand2")
        self._update_theme_buttons()

    def _on_drag_motion(self, event):
        if not self._drag_start:
            return
        if self._click_origin and math.hypot(event.x - self._click_origin[0], event.y - self._click_origin[1]) > 5.0:
            self._did_drag = True
            self._close_stand_context_modal()
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._drag_start = (event.x, event.y)
        cos_lat = max(0.15, math.cos(math.radians(self.center_lat)))
        if (
            self.follow_aircraft
            and self.heading_up
            and not self._is_airborne()
            and self.user_aircraft
            and self.user_aircraft.get("connected")
            and self.user_aircraft.get("heading") is not None
        ):
            ang = -math.radians(float(self.user_aircraft["heading"]))
            ux = dx * math.cos(ang) + dy * math.sin(ang)
            uy = -dx * math.sin(ang) + dy * math.cos(ang)
        else:
            ux, uy = dx, dy
        dlat = (uy * self.meters_per_pixel) / 111320.0
        dlon = -(ux * self.meters_per_pixel) / (111320.0 * cos_lat)
        self.center_lat += dlat
        self.center_lon += dlon
        if self.follow_aircraft:
            self._follow_pan_lat_offset = float(getattr(self, "_follow_pan_lat_offset", 0.0) or 0.0) + dlat
            self._follow_pan_lon_offset = float(getattr(self, "_follow_pan_lon_offset", 0.0) or 0.0) + dlon
        self.redraw()

    def _pick_stand_hitbox_at(self, mx, my, pad=5.0):
        if not self._stand_hitboxes:
            return None
        best_hb = None
        best_d2 = float("inf")
        for hb in reversed(self._stand_hitboxes):
            x0, y0, x1, y1, s_ref, st_als, st_term, is_assigned = hb
            if not s_ref:
                continue
            if (x0 - pad) <= mx <= (x1 + pad) and (y0 - pad) <= my <= (y1 + pad):
                cx = 0.5 * (x0 + x1)
                cy = 0.5 * (y0 + y1)
                d2 = (mx - cx) ** 2 + (my - cy) ** 2
                if d2 < best_d2:
                    best_d2 = d2
                    best_hb = hb
        return best_hb

    def _on_drag_end(self, event):
        was_drag = bool(getattr(self, "_did_drag", False))
        self._drag_start = None
        self._click_origin = None
        self._did_drag = False
        self.canvas.configure(cursor="arrow")
        if not was_drag:
            mx, my = event.x, event.y
            if self.on_runway_click and self._rwy_hitboxes:
                for rhb in reversed(self._rwy_hitboxes):
                    rx0, ry0, rx1, ry1, end_id, is_act = rhb
                    if (rx0 - 4) <= mx <= (rx1 + 4) and (ry0 - 4) <= my <= (ry1 + 4):
                        self._close_stand_context_modal()
                        if not is_act and end_id:
                            self.on_runway_click(end_id)
                            return
                        break
            hb = self._pick_stand_hitbox_at(mx, my, pad=5.0)
            if hb is not None:
                self.canvas.delete("stand_hover_tooltip")
                self._open_stand_context_modal(hb)
                return
            self._close_stand_context_modal()
        self.redraw()

    def _on_right_click(self, event):
        mx, my = event.x, event.y
        hb = self._pick_stand_hitbox_at(mx, my, pad=5.0)
        if hb is not None:
            self.canvas.delete("stand_hover_tooltip")
            self._open_stand_context_modal(hb)
            return
        self._close_stand_context_modal()

    def _close_stand_context_modal(self):
        modal = getattr(self, "_stand_ctx_modal", None)
        self._stand_ctx_modal = None
        if modal is not None:
            try:
                if modal.winfo_exists():
                    modal.destroy()
            except Exception:
                pass

    def _open_stand_context_modal(self, hb):
        self._close_stand_context_modal()
        x0, y0, x1, y1, s_ref, st_als, st_term, is_assigned = hb
        cx = (x0 + x1) / 2.0
        s_disp = _compact_gate_label(s_ref)
        clean_term = _clean_terminal_label(st_term).upper()

        card = ctk.CTkFrame(
            self.canvas,
            fg_color="#111827",
            corner_radius=10,
            border_width=0
        )
        self._stand_ctx_modal = card

        hdr_row = ctk.CTkFrame(card, fg_color="transparent")
        hdr_row.pack(fill="x", padx=12, pady=(10, 6))

        title_txt = f"STAND {s_disp}  {clean_term}" if clean_term else f"STAND {s_disp}"
        lbl_title = ctk.CTkLabel(
            hdr_row,
            text=title_txt,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#F8FAFC"
        )
        lbl_title.pack(side="left")

        btn_x = ctk.CTkButton(
            hdr_row,
            text="X",
            width=22,
            height=22,
            corner_radius=6,
            fg_color="transparent",
            hover_color="#1E293B",
            text_color="#94A3B8",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._close_stand_context_modal
        )
        btn_x.pack(side="right", padx=(8, 0))

        btn_warp = ctk.CTkButton(
            card,
            text=f"Reposition Aircraft to {s_disp}",
            height=32,
            corner_radius=7,
            fg_color="#0284C7",
            hover_color="#0369A1",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda g=s_ref: self._trigger_stand_reposition(g)
        )
        btn_warp.pack(fill="x", padx=12, pady=(0, 6 if not is_assigned else 10))

        if not is_assigned:
            btn_sel = ctk.CTkButton(
                card,
                text=f"Select Stand {s_disp} Only",
                height=28,
                corner_radius=7,
                fg_color="#1E293B",
                hover_color="#334155",
                text_color="#E2E8F0",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda g=s_ref: self._trigger_stand_select_only(g)
            )
            btn_sel.pack(fill="x", padx=12, pady=(0, 10))

        card.update_idletasks()
        cw = max(215, card.winfo_reqwidth())
        ch = max(78, card.winfo_reqheight())
        w_can = max(self.canvas.winfo_width(), 400)
        h_can = max(self.canvas.winfo_height(), 320)

        px = int(cx - (cw / 2.0))
        py = int(y0 - ch - 10)
        if py < 10:
            py = int(y1 + 10)
        px = max(10, min(w_can - cw - 10, px))
        py = max(10, min(h_can - ch - 10, py))
        card.place(x=px, y=py)

    def _hide_gate_toast(self, event=None):
        after_id = getattr(self, "_gate_toast_after_id", None)
        self._gate_toast_after_id = None
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        toast_card = getattr(self, "_gate_toast_card", None)
        if toast_card is not None:
            try:
                if toast_card.winfo_exists():
                    toast_card.place_forget()
            except Exception:
                pass

    def show_gate_toast(self, toast_info):
        if not toast_info or not isinstance(toast_info, dict):
            return
        try:
            if not self.canvas or not self.canvas.winfo_exists():
                return
        except Exception:
            return

        after_id = getattr(self, "_gate_toast_after_id", None)
        self._gate_toast_after_id = None
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass

        txt = str(toast_info.get("text") or toast_info.get("message") or toast_info.get("title") or "GSX Pro Armed").strip()
        pill_txt = f"   {txt}   "
        canvas_bg = self._get_palette().get("bg", "#2B353E")

        toast_card = getattr(self, "_gate_toast_card", None)
        if toast_card is None or not toast_card.winfo_exists():
            toast_card = ctk.CTkLabel(
                self.canvas,
                text=pill_txt,
                fg_color="#1B1E24",
                bg_color=canvas_bg,
                text_color="#FFFFFF",
                corner_radius=8,
                height=34,
                font=ctk.CTkFont(size=13, weight="bold"),
                cursor="hand2"
            )
            toast_card.bind("<Button-1>", self._hide_gate_toast)
            self._gate_toast_card = toast_card
        else:
            toast_card.configure(text=pill_txt, bg_color=canvas_bg)

        toast_card.place(relx=0.5, rely=0.5, anchor="center")
        toast_card.lift()
        self._gate_toast_after_id = self.after(2500, self._hide_gate_toast)

    def _trigger_stand_reposition(self, s_ref):
        self._close_stand_context_modal()
        if not s_ref:
            return
        if self.backend and hasattr(self.backend, "reposition_aircraft"):
            self.backend.reposition_aircraft(self.phase_mode, s_ref)
            root = self.winfo_toplevel()
            if hasattr(root, "last_flight_data") and hasattr(root, "render_results"):
                fd = self.backend.get_dynamic_flight_data() if hasattr(self.backend, "get_dynamic_flight_data") else getattr(self.backend, "last_flight_data", None)
                if fd:
                    root.last_flight_data = fd
                    root.render_results(fd, preserve_camera=True)
            if hasattr(root, "_check_and_show_gate_toast"):
                root._check_and_show_gate_toast()
        elif self.on_stand_click:
            self.on_stand_click(s_ref)

    def _trigger_stand_select_only(self, s_ref):
        self._close_stand_context_modal()
        if s_ref and self.on_stand_click:
            self.on_stand_click(s_ref)

    def _on_mousewheel(self, event):
        factor = 0.80 if event.delta > 0 else 1.25
        self.zoom_by(factor)

    def _on_mouse_leave(self, event):
        if self._hovered_stand_info is not None:
            self._hovered_stand_info = None
            self.canvas.delete("stand_hover_tooltip")
            if not self._drag_start:
                self.canvas.configure(cursor="arrow")

    def _on_mouse_motion(self, event):
        if self._drag_start:
            return
        mx, my = event.x, event.y
        hit = None
        for rhb in reversed(self._rwy_hitboxes):
            rx0, ry0, rx1, ry1, end_id, is_act = rhb
            if (rx0 - 3) <= mx <= (rx1 + 3) and (ry0 - 3) <= my <= (ry1 + 3):
                hit = ("rwy", rx0, ry0, rx1, ry1, end_id, is_act)
                break
        if hit is None:
            hit = self._pick_stand_hitbox_at(mx, my, pad=3.0)
        if hit != self._hovered_stand_info:
            self._hovered_stand_info = hit
            if hit is not None:
                self.canvas.configure(cursor="hand2")
                self._draw_stand_hover_tooltip()
            else:
                self.canvas.delete("stand_hover_tooltip")
                self.canvas.configure(cursor="arrow")

    def _draw_stand_hover_tooltip(self):
        self.canvas.delete("stand_hover_tooltip")
        if not self._hovered_stand_info or self._drag_start:
            return
        if self._hovered_stand_info[0] == "rwy":
            _, x0, y0, x1, y1, end_id, is_assigned = self._hovered_stand_info
            cx = (x0 + x1) / 2.0
            hdr_line = f"RUNWAY {end_id}  {'ACTIVE RUNWAY' if is_assigned else 'SELECT RUNWAY'}"
            phase_lbl = "Departure" if self.phase_mode == "departure" else "Arrival"
            al_line = f"Active {phase_lbl} Runway" if is_assigned else f"Set RWY {end_id} as Active {phase_lbl} Runway"
        else:
            x0, y0, x1, y1, s_ref, st_als, st_term, is_assigned = self._hovered_stand_info
            cx = (x0 + x1) / 2.0
            s_disp = _compact_gate_label(s_ref)
            clean_term = _clean_terminal_label(st_term).upper()
            hdr_parts = [f"STAND {s_disp}"]
            if is_assigned:
                hdr_parts.append("ASSIGNED GATE")
            if clean_term:
                hdr_parts.append(clean_term)
            hdr_line = "  ".join(hdr_parts)

            al_names = []
            for al_c in (st_als or []):
                full_n = self.backend.get_airline_full_name(al_c) if (self.backend and hasattr(self.backend, "get_airline_full_name")) else al_c
                if full_n and full_n.upper() != al_c.upper():
                    al_names.append(f"{full_n} ({al_c})")
                else:
                    al_names.append(str(al_c))
            al_line = "  ".join(al_names) if al_names else "General Commercial Stand"

        w_can = max(self.canvas.winfo_width(), 400)
        h_can = max(self.canvas.winfo_height(), 320)
        box_w = max(190, len(hdr_line) * 6.8 + 28, len(al_line) * 7.6 + 28)
        box_h = 46
        tx0 = cx - (box_w / 2.0)
        tx1 = cx + (box_w / 2.0)
        ty1 = y0 - 9
        ty0 = ty1 - box_h
        if ty0 < 44:
            ty0 = y1 + 9
            ty1 = ty0 + box_h
        if tx0 < 8:
            tx1 += (8 - tx0)
            tx0 = 8
        if tx1 > w_can - 8:
            tx0 -= (tx1 - (w_can - 8))
            tx1 = w_can - 8
        tcx = (tx0 + tx1) / 2.0
        cam = self._get_airline_camaieu()
        hdr_col = cam["accent"] if is_assigned else "#38BDF8"
        self.canvas.create_rectangle(
            tx0 + 2, ty0 + 3, tx1 + 2, ty1 + 3,
            fill="#020617", outline="", tags="stand_hover_tooltip"
        )
        self.canvas.create_rectangle(
            tx0, ty0, tx1, ty1,
            fill="#0F172A", outline="", tags="stand_hover_tooltip"
        )
        self.canvas.create_text(
            tcx, ty0 + 14,
            text=hdr_line, fill=hdr_col, font=("Consolas", 9, "bold"),
            tags="stand_hover_tooltip"
        )
        self.canvas.create_text(
            tcx, ty0 + 32,
            text=al_line, fill="#FFFFFF", font=("Arial", 10, "bold"),
            tags="stand_hover_tooltip"
        )

    def _latlon_to_xy(self, lat, lon, w, h, cos_lat):
        dx = ((lon - self.center_lon) * 111320.0 * cos_lat) / self.meters_per_pixel
        dy = -((lat - self.center_lat) * 111320.0) / self.meters_per_pixel
        if (
            self.follow_aircraft
            and self.heading_up
            and not self._is_airborne()
            and self.user_aircraft
            and self.user_aircraft.get("connected")
            and self.user_aircraft.get("heading") is not None
        ):
            ang = -math.radians(float(self.user_aircraft["heading"]))
            rx = dx * math.cos(ang) - dy * math.sin(ang)
            ry = dx * math.sin(ang) + dy * math.cos(ang)
            return (w / 2.0) + rx, (h / 2.0) + ry
        return (w / 2.0) + dx, (h / 2.0) + dy

    def redraw(self):
        self._last_draw_sig = self._compute_draw_sig()
        self.canvas.delete("all")
        self._stand_hitboxes = []
        self._rwy_hitboxes = []
        pal = self._get_palette()
        cam = self._get_airline_camaieu()
        if getattr(self, "_last_canvas_bg", None) != pal["bg"]:
            self._last_canvas_bg = pal["bg"]
            self.canvas.configure(bg=pal["bg"])

        w = max(self.canvas.winfo_width(), 400)
        h = max(self.canvas.winfo_height(), 320)
        cos_lat = max(0.15, math.cos(math.radians(self.center_lat)))

        # Subtle Lido Coordinate Grid Lines
        grid_step = 90
        for gx in range(0, w, grid_step):
            self.canvas.create_line(gx, 0, gx, h, fill=pal["grid_line"], width=1)
        for gy in range(0, h, grid_step):
            self.canvas.create_line(0, gy, w, gy, fill=pal["grid_line"], width=1)

        if not self.chart_data:
            self.canvas.create_text(
                w / 2, h / 2,
                text="Vector Ground Chart loading or unavailable for this airport",
                fill="#94A3B8", font=("Arial", 14, "bold")
            )
            return

        # 1. Draw Aprons (Polygon layer)
        apron_label_candidates = []
        for apron in self.chart_data.get("aprons", []):
            pts = apron.get("points", [])
            if len(pts) >= 3:
                flat = []
                xs, ys = [], []
                for p in pts:
                    x, y = self._latlon_to_xy(p[0], p[1], w, h, cos_lat)
                    flat.extend((x, y))
                    xs.append(x)
                    ys.append(y)
                self.canvas.create_polygon(flat, fill=pal["apron_fill"], outline="")
                ap_name = str(apron.get("name") or "").strip()
                if ap_name and (max(xs) - min(xs) >= 55 or max(ys) - min(ys) >= 55):
                    ap_u = ap_name.upper()
                    if any(k in ap_u for k in ("APRON", "AIRE", "PARKING", "RAMP", "ZONE")):
                        apron_label_candidates.append((ap_u, sum(xs) / len(xs), sum(ys) / len(ys)))

        # 2. Draw Taxiways & Taxilanes (3-pass seamless pavement: Borders -> Fills -> Centerlines)
        twy_width = max(2.5, min(14.0, 18.0 / self.meters_per_pixel))
        twy_border_w = twy_width + 2.0
        twy_label_positions = []
        twy_labels_by_ref = {}
        twy_draw_items = []
        twy_screen_segs = []

        for twy in self.chart_data.get("taxiways", []):
            pts = twy.get("points", [])
            if len(pts) < 2:
                continue
            flat = []
            scr_pts = []
            for p in pts:
                x, y = self._latlon_to_xy(p[0], p[1], w, h, cos_lat)
                flat.extend((x, y))
                scr_pts.append((x, y))
            is_lane = (twy.get("type") == "taxilane")
            w_line = max(1.8, twy_width * 0.65) if is_lane else twy_width
            twy_draw_items.append((flat, is_lane, w_line))
            if not is_lane:
                for k in range(len(scr_pts) - 1):
                    twy_screen_segs.append((scr_pts[k][0], scr_pts[k][1], scr_pts[k + 1][0], scr_pts[k + 1][1]))

            ref = (twy.get("ref") or "").strip()
            if ref and len(ref) <= 7 and not is_lane:
                n_pts = len(pts)
                if n_pts >= 8:
                    cand_indices = [n_pts // 4, n_pts // 2, (3 * n_pts) // 4]
                else:
                    cand_indices = [n_pts // 2]
                for ci in cand_indices:
                    mx, my = scr_pts[ci]
                    if 30 < mx < w - 30 and 30 < my < h - 30:
                        same_list = twy_labels_by_ref.get(ref, ())
                        if any(math.hypot(mx - px, my - py) < 155.0 for px, py in same_list):
                            continue
                        if any(math.hypot(mx - ox, my - oy) < 32.0 for _, ox, oy in twy_label_positions):
                            continue
                        twy_labels_by_ref.setdefault(ref, []).append((mx, my))
                        twy_label_positions.append((ref, mx, my))

        if self.meters_per_pixel < 5.0:
            for flat, is_lane, _ in twy_draw_items:
                if not is_lane:
                    self.canvas.create_line(flat, fill=pal["twy_border"], width=twy_border_w, capstyle="round", joinstyle="round")
        for flat, _, w_line in twy_draw_items:
            self.canvas.create_line(flat, fill=pal["twy_fill"], width=w_line, capstyle="round", joinstyle="round")
        if self.meters_per_pixel < 3.8:
            center_w = 1.35 if self.meters_per_pixel < 1.8 else 1.15
            for flat, is_lane, _ in twy_draw_items:
                self.canvas.create_line(
                    flat,
                    fill=pal["twy_center"],
                    width=1.0 if is_lane else center_w,
                    capstyle="round",
                    joinstyle="round"
                )

        # 3. Draw Terminal Buildings (Pitch-black Lido AMM silhouettes) & collect Terminal / Pier labels
        term_poly_labels = []
        seen_term_labels = set()
        term_screen_polys = []
        for term in self.chart_data.get("terminals", []):
            pts = term.get("points", [])
            if len(pts) >= 3:
                flat = []
                xs, ys = [], []
                for p in pts:
                    x, y = self._latlon_to_xy(p[0], p[1], w, h, cos_lat)
                    flat.extend((x, y))
                    xs.append(x)
                    ys.append(y)
                self.canvas.create_polygon(flat, fill=pal["term_fill"], outline=pal["term_outline"], width=1)
                term_screen_polys.append((xs, ys))
                raw_tn = str(term.get("name") or "").strip()
                if raw_tn and (max(xs) - min(xs) >= 36 or max(ys) - min(ys) >= 36):
                    if re.search(r'terminal|term|orly\s*\d|hall|concourse|pier|sat|dock|jet[eé]e', raw_tn, re.I) and not re.search(r'sslia|pompier|fire|tower|tour\s+de|hangar|servair|fret|wfs', raw_tn, re.I):
                        clean_tn = re.sub(r'\s*\([^)]*\)', '', raw_tn).strip()
                        clean_tn = re.sub(r'^(?:a[eé]rogare|a[eé]roport|b[aâ]timent)\s+(?:d[\'\u2019]|de\s+|du\s+)?', '', clean_tn, flags=re.I).strip().upper()
                        if clean_tn == "ORLY 1 ET 2":
                            sw_x = min(xs) + 0.34 * (max(xs) - min(xs))
                            sw_y = min(ys) + 0.68 * (max(ys) - min(ys))
                            ne_x = min(xs) + 0.66 * (max(xs) - min(xs))
                            ne_y = min(ys) + 0.32 * (max(ys) - min(ys))
                            if "ORLY 1" not in seen_term_labels:
                                term_poly_labels.append(("ORLY 1", sw_x, sw_y))
                                seen_term_labels.add("ORLY 1")
                            if "ORLY 2" not in seen_term_labels:
                                term_poly_labels.append(("ORLY 2", ne_x, ne_y))
                                seen_term_labels.add("ORLY 2")
                        else:
                            m_short = re.match(r'^((?:TERMINAL|TERM|PIER|CONCOURSE|HALL|SAT(?:ELLITE)?|DOCK|JET[EÉ]E)\s*(?:[0-9]{1,2}[A-Z]?|[A-Z]\b)?)', clean_tn)
                            if m_short and len(clean_tn) > 16:
                                clean_tn = m_short.group(1).strip()
                            elif len(clean_tn) > 22:
                                clean_tn = clean_tn[:22].strip()
                            if clean_tn and clean_tn not in seen_term_labels:
                                term_poly_labels.append((clean_tn, sum(xs) / len(xs), sum(ys) / len(ys)))
                                seen_term_labels.add(clean_tn)

        # 4. Draw Runways (Authentic Lido AMM / Navigraph Runway Surface, Edge Stripes, Piano Keys, Aiming Points & Crisp Vector Centerline)
        rwy_w = max(8.0, min(34.0, 45.0 / self.meters_per_pixel))
        active_rwy = (self.airport_data.get("selected_runway") or "").upper() if self.airport_data else ""
        rwy_threshold_badges = []

        for rwy in self.chart_data.get("runways", []):
            pts = rwy.get("points", [])
            if len(pts) < 2:
                continue
            flat = []
            screen_rwy_pts = []
            for p in pts:
                x, y = self._latlon_to_xy(p[0], p[1], w, h, cos_lat)
                flat.extend((x, y))
                screen_rwy_pts.append((x, y))
            is_selected_rwy = active_rwy in rwy.get("ends", {})
            outline_col = pal["rwy_circle_ring"] if is_selected_rwy else pal["rwy_outline"]
            border_extra = 3.2 if is_selected_rwy else 2.2
            self.canvas.create_line(flat, fill=outline_col, width=rwy_w + border_extra, capstyle="butt", joinstyle="miter")
            self.canvas.create_line(flat, fill=pal["rwy_fill"], width=rwy_w, capstyle="butt", joinstyle="miter")

            p_start = screen_rwy_pts[0]
            p_end = screen_rwy_pts[-1]
            rdx = p_end[0] - p_start[0]
            rdy = p_end[1] - p_start[1]
            rwy_px_len = math.hypot(rdx, rdy)
            if rwy_px_len > 28.0:
                ux = rdx / rwy_px_len
                uy = rdy / rwy_px_len
                nx = -uy
                ny = ux
                mark_col = pal.get("rwy_markings", pal["rwy_center"])

                def _rwy_pt(along_px, across_px):
                    return (
                        p_start[0] + along_px * ux + across_px * nx,
                        p_start[1] + along_px * uy + across_px * ny
                    )

                # 4a. Continuous White Runway Edge Stripes (inset slightly from asphalt edge)
                if rwy_w >= 9.5 and rwy_px_len > 50.0:
                    edge_off = (rwy_w * 0.5) - 1.3
                    e_pad = min(16.0, rwy_px_len * 0.06)
                    for side_sign in (-1.0, 1.0):
                        ep0 = _rwy_pt(e_pad, side_sign * edge_off)
                        ep1 = _rwy_pt(rwy_px_len - e_pad, side_sign * edge_off)
                        self.canvas.create_line(
                            ep0[0], ep0[1], ep1[0], ep1[1],
                            fill=pal.get("rwy_edge", mark_col), width=1.0, capstyle="butt"
                        )

                # 4b. Threshold "Piano Keys" (Peignes de seuil) at both ends
                if rwy_w >= 9.0 and rwy_px_len > 75.0:
                    pk_start = 17.5
                    pk_len = max(5.5, min(13.0, 26.0 / self.meters_per_pixel))
                    n_pairs = 3 if rwy_w < 16.0 else 4
                    max_lat_off = (rwy_w * 0.5) - 2.4
                    min_lat_off = max(1.3, rwy_w * 0.08)
                    stripe_w = max(1.0, min(1.8, (rwy_w / 14.0)))
                    for i_pk in range(n_pairs):
                        t_frac = i_pk / float(max(1, n_pairs - 1)) if n_pairs > 1 else 0.5
                        lat_d = min_lat_off + t_frac * (max_lat_off - min_lat_off)
                        for side_s in (-1.0, 1.0):
                            # Start threshold piano key
                            k0 = _rwy_pt(pk_start, side_s * lat_d)
                            k1 = _rwy_pt(pk_start + pk_len, side_s * lat_d)
                            self.canvas.create_line(k0[0], k0[1], k1[0], k1[1], fill=mark_col, width=stripe_w, capstyle="butt")
                            # End threshold piano key
                            ke0 = _rwy_pt(rwy_px_len - pk_start - pk_len, side_s * lat_d)
                            ke1 = _rwy_pt(rwy_px_len - pk_start, side_s * lat_d)
                            self.canvas.create_line(ke0[0], ke0[1], ke1[0], ke1[1], fill=mark_col, width=stripe_w, capstyle="butt")

                # 4c. Aiming Point Blocks (~300m from threshold) & Touchdown Zone (TDZ) Bars
                if rwy_w >= 10.0 and rwy_px_len > 140.0:
                    aim_d = min(rwy_px_len * 0.22, max(36.0, 290.0 / self.meters_per_pixel))
                    aim_len = max(6.5, min(16.0, 42.0 / self.meters_per_pixel))
                    aim_lat = rwy_w * 0.22
                    aim_w = max(1.8, min(3.6, rwy_w * 0.13))
                    for side_s in (-1.0, 1.0):
                        a0 = _rwy_pt(aim_d, side_s * aim_lat)
                        a1 = _rwy_pt(aim_d + aim_len, side_s * aim_lat)
                        self.canvas.create_line(a0[0], a0[1], a1[0], a1[1], fill=mark_col, width=aim_w, capstyle="butt")
                        ae0 = _rwy_pt(rwy_px_len - aim_d - aim_len, side_s * aim_lat)
                        ae1 = _rwy_pt(rwy_px_len - aim_d, side_s * aim_lat)
                        self.canvas.create_line(ae0[0], ae0[1], ae1[0], ae1[1], fill=mark_col, width=aim_w, capstyle="butt")

                    if self.meters_per_pixel <= 3.2 and rwy_px_len > 220.0:
                        tdz_len = max(4.5, min(10.0, 20.0 / self.meters_per_pixel))
                        tdz_w = max(1.2, min(2.2, rwy_w * 0.08))
                        for tdz_d in (aim_d * 0.58, aim_d * 1.42):
                            if 30.0 < tdz_d < (rwy_px_len * 0.42):
                                for side_s in (-1.0, 1.0):
                                    t0 = _rwy_pt(tdz_d, side_s * aim_lat)
                                    t1 = _rwy_pt(tdz_d + tdz_len, side_s * aim_lat)
                                    self.canvas.create_line(t0[0], t0[1], t1[0], t1[1], fill=mark_col, width=tdz_w, capstyle="butt")
                                    te0 = _rwy_pt(rwy_px_len - tdz_d - tdz_len, side_s * aim_lat)
                                    te1 = _rwy_pt(rwy_px_len - tdz_d, side_s * aim_lat)
                                    self.canvas.create_line(te0[0], te0[1], te1[0], te1[1], fill=mark_col, width=tdz_w, capstyle="butt")

                # 4d. Crisp Vector Long Runway Centerline Dashes (no broken Windows GDI dots)
                cl_margin = min(rwy_px_len * 0.42, 34.0 if rwy_w >= 9.0 else 20.0)
                cl_span = rwy_px_len - (2.0 * cl_margin)
                if cl_span > 12.0:
                    dash_len = max(13.0, min(26.0, 32.0 / self.meters_per_pixel))
                    gap_len = max(8.5, min(17.0, 20.0 / self.meters_per_pixel))
                    step_len = dash_len + gap_len
                    cl_w = 1.6 if rwy_w >= 12.0 else 1.25
                    cur_d = cl_margin
                    while cur_d < (rwy_px_len - cl_margin - 3.0):
                        seg_end = min(rwy_px_len - cl_margin, cur_d + dash_len)
                        if (seg_end - cur_d) >= 4.0:
                            c0 = _rwy_pt(cur_d, 0.0)
                            c1 = _rwy_pt(seg_end, 0.0)
                            self.canvas.create_line(
                                c0[0], c0[1], c1[0], c1[1],
                                fill=pal["rwy_center"], width=cl_w, capstyle="butt"
                            )
                        cur_d += step_len

            for end_id, end_info in rwy.get("ends", {}).items():
                ex, ey = self._latlon_to_xy(end_info["lat"], end_info["lon"], w, h, cos_lat)
                is_act = (end_id == active_rwy)
                rwy_hdg = float(end_info.get("heading") or 0.0)
                rwy_threshold_badges.append((ex, ey, end_id, is_act, rwy_hdg))

        # 4e. Draw Perpendicular ICAO Hold-Short Bars across taxiways at holding points
        if self.meters_per_pixel <= 3.8:
            hb_half = max(3.6, min(8.0, twy_width * 0.52))
            for hp in self.chart_data.get("holding_points", []):
                hlat, hlon = hp.get("lat"), hp.get("lon")
                if hlat is not None and hlon is not None:
                    hx, hy = self._latlon_to_xy(hlat, hlon, w, h, cos_lat)
                    if 10 < hx < w - 10 and 10 < hy < h - 10:
                        best_d2 = 324.0  # 18px radius
                        best_nx, best_ny = 0.98, 0.18
                        best_tx, best_ty = -0.18, 0.98
                        for sx0, sy0, sx1, sy1 in twy_screen_segs:
                            sdx = sx1 - sx0
                            sdy = sy1 - sy0
                            slen2 = sdx * sdx + sdy * sdy
                            if slen2 < 1.0:
                                continue
                            t_p = max(0.0, min(1.0, ((hx - sx0) * sdx + (hy - sy0) * sdy) / slen2))
                            px_s = sx0 + t_p * sdx
                            py_s = sy0 + t_p * sdy
                            d2 = (hx - px_s) ** 2 + (hy - py_s) ** 2
                            if d2 < best_d2:
                                best_d2 = d2
                                slen = math.sqrt(slen2)
                                best_tx = sdx / slen
                                best_ty = sdy / slen
                                best_nx = -best_ty
                                best_ny = best_tx
                        hx0 = hx - best_nx * hb_half
                        hy0 = hy - best_ny * hb_half
                        hx1 = hx + best_nx * hb_half
                        hy1 = hy + best_ny * hb_half
                        self.canvas.create_line(
                            hx0, hy0, hx1, hy1,
                            fill=pal.get("hold_bar_border", "#090D16"), width=3.4, capstyle="butt"
                        )
                        self.canvas.create_line(
                            hx0, hy0, hx1, hy1,
                            fill=pal["hold_bar"], width=1.9, capstyle="butt"
                        )
                        if self.meters_per_pixel <= 1.8:
                            off_t = 2.4
                            self.canvas.create_line(
                                hx0 + best_tx * off_t, hy0 + best_ty * off_t,
                                hx1 + best_tx * off_t, hy1 + best_ty * off_t,
                                fill=pal["hold_bar"], width=1.4, capstyle="butt"
                            )

        # 5. Draw Stands (Authentic Lido AMM Oriented Pentagonal / Triangular-Nose Stand Tags)
        #    and aggregate Terminal / Pier / Apron labels from stand groups
        assigned_gate = str(self.airport_data.get("gate", "")).replace(" ", "").upper() if self.airport_data else ""
        assigned_norm = re.sub(r'([A-Z]*)0+(\d+)', r'\1\2', assigned_gate)
        assigned_digits = "".join(c for c in assigned_gate if c.isdigit())
        gx_pin, gy_pin = None, None
        if self.airport_data and self.airport_data.get("lat") is not None and self.airport_data.get("lon") is not None:
            gx_pin, gy_pin = self._latlon_to_xy(float(self.airport_data["lat"]), float(self.airport_data["lon"]), w, h, cos_lat)

        use_hdg_up = bool(
            self.follow_aircraft
            and self.heading_up
            and not self._is_airborne()
            and self.user_aircraft
            and self.user_aircraft.get("connected")
        )
        ac_hdg_s = float(self.user_aircraft.get("heading") or 0.0) if use_hdg_up else 0.0

        # Gather terminal/pier clusters and lettered Apron clusters from stands
        stand_term_groups = {}   # term_upper -> list of (sx, sy, cos_r, sin_r)
        stand_apron_groups = {}  # letter_prefix -> list of (sx, sy, cos_r, sin_r)
        all_stands_list = self.chart_data.get("stands", [])

        for st in all_stands_list:
            s_ref = str(st.get("ref", "")).strip()
            if not s_ref or st.get("lat") is None or st.get("lon") is None:
                continue
            sx_g, sy_g = self._latlon_to_xy(st["lat"], st["lon"], w, h, cos_lat)
            s_hdg_g = st.get("heading")
            vis_hdg_g = ((float(s_hdg_g) - ac_hdg_s) if use_hdg_up else float(s_hdg_g)) if s_hdg_g is not None else 0.0
            rad_g = math.radians(vis_hdg_g - 90.0)
            cr_g, sr_g = math.cos(rad_g), math.sin(rad_g)

            raw_t = str(st.get("terminal") or "").strip()
            if raw_t:
                t_u = re.sub(r'\s*\([^)]*\)', '', raw_t).strip().upper()
                if t_u and t_u not in ("MAIN APRON", "OTHER", "CARGO APRON", "GENERAL AVIATION", "ORLY 1 ET 2") and not t_u.startswith("ZONE "):
                    stand_term_groups.setdefault(t_u, []).append((sx_g, sy_g, cr_g, sr_g))

            s_clean_g = re.sub(r'^(?:STAND|GATE|PARKING|RAMP|DOCK|APRON)\s*', '', s_ref.upper()).replace(" ", "")
            m_ap = re.match(r'^([A-Z])\d{1,3}[A-Z]?$', s_clean_g)
            if m_ap:
                ap_letter = m_ap.group(1)
                stand_apron_groups.setdefault(ap_letter, []).append((sx_g, sy_g, cr_g, sr_g))

        def _draw_lido_stand_tag(sx, sy, s_disp, vis_hdg, fill_col, border_col, fg_col, sc_mult=1.0, border_w=1.6, logo_codes=None):
            s_rad = math.radians(vis_hdg - 90.0)
            cos_r, sin_r = math.cos(s_rad), math.sin(s_rad)
            perp_x, perp_y = -sin_r, cos_r

            sc = max(0.70, min(1.38, (1.05 / (max(0.24, self.meters_per_pixel) ** 0.28)) * sc_mult))
            font_sz = 9 if sc >= 1.02 else (8 if sc >= 0.82 else 7)
            half_w = max(6.8, min(12.0, 8.4 * sc))
            text_len = max(17.0, len(s_disp) * (font_sz * 0.72) + 7.5)
            body_back = text_len * 0.52
            body_front = text_len * 0.48
            nose_len = max(7.0, min(13.5, 9.2 * sc))
            tail_line = body_back + max(5.0, min(16.0, 8.0 / max(0.35, self.meters_per_pixel)))

            def _pt(along, across):
                return (
                    sx + along * cos_r + across * perp_x,
                    sy + along * sin_r + across * perp_y
                )

            # 1. Yellow/Amber stand lead-in line from taxilane into rear of stand tag
            t0x, t0y = _pt(-tail_line, 0.0)
            t1x, t1y = _pt(-body_back, 0.0)
            self.canvas.create_line(t0x, t0y, t1x, t1y, fill=pal["twy_center"], width=1.4, capstyle="round")

            # 2. Rectangular body of the Lido AMM stand tag
            b_rl = _pt(-body_back, -half_w)
            b_fl = _pt(body_front, -half_w)
            b_fr = _pt(body_front, +half_w)
            b_rr = _pt(-body_back, +half_w)
            self.canvas.create_polygon(
                [b_rl[0], b_rl[1], b_fl[0], b_fl[1], b_fr[0], b_fr[1], b_rr[0], b_rr[1]],
                fill=fill_col, outline=border_col, width=border_w, joinstyle="miter"
            )

            # 3. Triangular directional nose cone sharing the front edge of the tag body
            n_tip = _pt(body_front + nose_len, 0.0)
            self.canvas.create_polygon(
                [b_fl[0], b_fl[1], n_tip[0], n_tip[1], b_fr[0], b_fr[1]],
                fill=fill_col, outline=border_col, width=border_w, joinstyle="miter"
            )

            # 4. Rotated stand designator text (always right-side-up)
            txt_angle = (-math.degrees(math.atan2(sin_r, cos_r))) % 360.0
            if txt_angle > 180.0:
                txt_angle -= 360.0
            if txt_angle > 90.0:
                txt_angle -= 180.0
            elif txt_angle < -90.0:
                txt_angle += 180.0

            self.canvas.create_text(
                sx, sy,
                text=s_disp,
                fill=fg_col,
                font=("Arial", font_sz, "bold"),
                angle=txt_angle
            )

            all_x = [b_rl[0], b_fl[0], b_fr[0], b_rr[0], n_tip[0]]
            all_y = [b_rl[1], b_fl[1], b_fr[1], b_rr[1], n_tip[1]]

            # 5. Airline icon(s) displayed right in front of the triangular tip ("devant la pointe des markers")
            #    Applies a progressive scale multiplier (up to 1.45x) when the user zooms in to maximum zoom
            if logo_codes and self.backend and self.meters_per_pixel <= 2.6:
                logo_zoom_mult = 1.0 + 0.45 * max(0.0, min(1.0, (0.85 - self.meters_per_pixel) / 0.65))
                raw_lh = (18.0 if sc_mult > 1.05 else 13.5) * sc * logo_zoom_mult
                max_lh_cap = 34 if sc_mult > 1.05 else 28
                logo_h = max(12, min(max_lh_cap, int(round(raw_lh / 2.0)) * 2))
                logo_w = int(round(logo_h * 1.16))
                max_logos = 2 if (self.meters_per_pixel <= 0.85 and sc_mult <= 1.05) else 1
                logo_imgs = []
                for al_c in logo_codes:
                    tk_l = self._get_tk_logo(al_c, size=logo_h)
                    if tk_l is not None:
                        logo_imgs.append(tk_l)
                        if len(logo_imgs) >= max_logos:
                            break
                tip_along = body_front + nose_len
                for idx_l, tk_l in enumerate(logo_imgs):
                    l_along = tip_along + 2.8 + (logo_h * 0.56) + idx_l * (logo_h + 2.0)
                    lx, ly = _pt(l_along, 0.0)
                    self.canvas.create_image(lx, ly, image=tk_l)

            return min(all_x), min(all_y), max(all_x), max(all_y)

        # Dynamic LOD: Hide individual neighboring stands when zoomed out in global view (> 1.55 m/px)
        # so only terminal names, main taxiways, runways, and the assigned stand remain visible.
        drawn_stand_boxes = []
        if self.meters_per_pixel <= 1.55:
            for st in all_stands_list:
                s_ref = str(st.get("ref", "")).strip()
                if not s_ref:
                    continue
                s_clean = s_ref.replace(" ", "").upper()
                s_norm = re.sub(r'([A-Z]*)0+(\d+)', r'\1\2', s_clean)
                if s_clean == assigned_gate or s_norm == assigned_norm or (assigned_digits and s_clean == assigned_digits):
                    continue
                sx, sy = self._latlon_to_xy(st["lat"], st["lon"], w, h, cos_lat)
                if not (14 < sx < w - 14 and 14 < sy < h - 14):
                    continue
                if gx_pin is not None and math.hypot(sx - gx_pin, sy - gy_pin) < 16:
                    continue

                s_hdg = st.get("heading")
                vis_s_hdg = ((float(s_hdg) - ac_hdg_s) if use_hdg_up else float(s_hdg)) if s_hdg is not None else 0.0
                s_rad = math.radians(vis_s_hdg - 90.0)
                cos_r, sin_r = math.cos(s_rad), math.sin(s_rad)
                perp_x, perp_y = -sin_r, cos_r

                # Oriented overlap check so side-by-side parallel stands (like C01, C02, C03) never cull each other
                too_close = False
                lat_thr = 11.5 if self.meters_per_pixel < 1.2 else (14.5 if self.meters_per_pixel <= 2.0 else 20.0)
                lon_thr = 22.0 if self.meters_per_pixel < 1.2 else 28.0
                for ox, oy in drawn_stand_boxes:
                    ddx, ddy = sx - ox, sy - oy
                    d_along = abs(ddx * cos_r + ddy * sin_r)
                    d_across = abs(ddx * perp_x + ddy * perp_y)
                    if d_across < lat_thr and d_along < lon_thr:
                        too_close = True
                        break
                if too_close:
                    continue
                drawn_stand_boxes.append((sx, sy))

                s_disp = re.sub(r'^(?:STAND|GATE|PARKING|RAMP|DOCK)\s*', '', s_ref, flags=re.I).replace(" ", "").upper() or s_ref
                st_als = st.get("airlines") or []
                st_term = str(st.get("terminal") or "")
                bx0, by0, bx1, by1 = _draw_lido_stand_tag(
                    sx, sy, s_disp, vis_s_hdg,
                    fill_col=pal["stand_bg"],
                    border_col=pal["stand_border"],
                    fg_col=pal["stand_fg"],
                    logo_codes=st_als
                )
                self._stand_hitboxes.append((bx0, by0, bx1, by1, s_ref, tuple(st_als), st_term, False))

        # 5b. Draw Terminal / Pier Names & Apron Names (ORLY 3, ORLY 4, APRON B, APRON C, etc.)
        drawn_area_labels = []
        if self.meters_per_pixel <= 6.5:
            # Combine OSM terminal polygon names + inferred stand terminal/pier groups
            all_term_labels = list(term_poly_labels)
            for t_name, grp in stand_term_groups.items():
                if len(grp) < 2:
                    continue
                avg_x = sum(item[0] for item in grp) / len(grp)
                avg_y = sum(item[1] for item in grp) / len(grp)
                avg_cr = sum(item[2] for item in grp) / len(grp)
                avg_sr = sum(item[3] for item in grp) / len(grp)
                norm_len = math.hypot(avg_cr, avg_sr) or 1.0
                shift_px = max(24.0, min(52.0, 36.0 / max(0.4, self.meters_per_pixel)))
                tx_lbl = avg_x + (avg_cr / norm_len) * shift_px
                ty_lbl = avg_y + (avg_sr / norm_len) * shift_px
                all_term_labels.append((t_name, tx_lbl, ty_lbl))

            for t_lbl, tx_l, ty_l in all_term_labels:
                if not (35 < tx_l < w - 35 and 25 < ty_l < h - 25):
                    continue
                if any(
                    t_lbl == prev_t or math.hypot(tx_l - px, ty_l - py) < 85.0
                    for prev_t, px, py in drawn_area_labels
                ):
                    continue
                drawn_area_labels.append((t_lbl, tx_l, ty_l))
                self.canvas.create_text(tx_l + 1, ty_l + 1, text=t_lbl, fill="#000000", font=("Arial", 10, "bold"))
                self.canvas.create_text(tx_l, ty_l, text=t_lbl, fill=pal["term_text"], font=("Arial", 10, "bold"))

        if self.meters_per_pixel <= 3.0:
            for ap_letter, grp in sorted(stand_apron_groups.items()):
                if len(grp) < 2:
                    continue
                ap_lbl = f"APRON {ap_letter}"
                avg_x = sum(item[0] for item in grp) / len(grp)
                avg_y = sum(item[1] for item in grp) / len(grp)
                avg_cr = sum(item[2] for item in grp) / len(grp)
                avg_sr = sum(item[3] for item in grp) / len(grp)
                norm_len = math.hypot(avg_cr, avg_sr) or 1.0
                # Offset behind the stands toward the apron taxilane (just like APRON B, C, D, E, F in Lido AMM)
                back_px = max(22.0, min(44.0, 28.0 / max(0.45, self.meters_per_pixel)))
                ax_l = avg_x - (avg_cr / norm_len) * back_px
                ay_l = avg_y - (avg_sr / norm_len) * back_px
                # Nudge if colliding with a drawn stand box
                for ox, oy in drawn_stand_boxes:
                    if math.hypot(ax_l - ox, ay_l - oy) < 20.0:
                        ax_l -= (avg_cr / norm_len) * 16.0
                        ay_l -= (avg_sr / norm_len) * 16.0
                        break
                apron_label_candidates.append((ap_lbl, ax_l, ay_l))

            for ap_lbl, ax_l, ay_l in apron_label_candidates:
                if not (35 < ax_l < w - 35 and 25 < ay_l < h - 25):
                    continue
                if any(
                    ap_lbl == prev_t or math.hypot(ax_l - px, ay_l - py) < 70.0
                    for prev_t, px, py in drawn_area_labels
                ):
                    continue
                drawn_area_labels.append((ap_lbl, ax_l, ay_l))
                self.canvas.create_text(ax_l + 1, ay_l + 1, text=ap_lbl, fill="#090D14", font=("Arial", 8, "bold"))
                self.canvas.create_text(ax_l, ay_l, text=ap_lbl, fill=pal["apron_text"], font=("Arial", 8, "bold"))

        # 6. Draw Active A* Taxi Route & Rollout Line
        tr = (self.airport_data.get("taxi_route") or {}) if self.airport_data else {}
        rollout_pts = tr.get("rollout_points", [])
        if len(rollout_pts) >= 2:
            r_flat = []
            for p in rollout_pts:
                rx, ry = self._latlon_to_xy(p[0], p[1], w, h, cos_lat)
                r_flat.extend((rx, ry))
            self.canvas.create_line(r_flat, fill=pal["rollout"], width=3.5, dash=(10, 6), capstyle="round")

        route_pts = tr.get("route_points", [])
        if len(route_pts) >= 2:
            rt_flat = []
            xy_pts = []
            for p in route_pts:
                rx, ry = self._latlon_to_xy(p[0], p[1], w, h, cos_lat)
                rt_flat.extend((rx, ry))
                xy_pts.append((rx, ry))
            route_w = max(5.0, min(11.0, 14.0 / self.meters_per_pixel))
            self.canvas.create_line(rt_flat, fill=pal["route_glow"], width=route_w + 4.0, capstyle="round", joinstyle="round")
            self.canvas.create_line(rt_flat, fill=pal["route_main"], width=route_w, capstyle="round", joinstyle="round")

            # Draw directional arrows along the taxi route every ~75 pixels
            accum = 0.0
            for i in range(len(xy_pts) - 1):
                x1, y1 = xy_pts[i]
                x2, y2 = xy_pts[i + 1]
                seg = math.hypot(x2 - x1, y2 - y1)
                accum += seg
                if accum >= 70.0 and seg > 4.0:
                    accum = 0.0
                    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                    ang = math.atan2(y2 - y1, x2 - x1)
                    sz = 6.0
                    p_tip = (mx + sz * math.cos(ang), my + sz * math.sin(ang))
                    p_l = (mx + sz * math.cos(ang + 2.4), my + sz * math.sin(ang + 2.4))
                    p_r = (mx + sz * math.cos(ang - 2.4), my + sz * math.sin(ang - 2.4))
                    self.canvas.create_polygon([p_tip[0], p_tip[1], p_l[0], p_l[1], p_r[0], p_r[1]], fill=pal["route_arrow"], outline="")

        # 7. Draw Taxiway Labels (Authentic Aviation Amber-Yellow EFB Sign Badges) on top of the taxiways
        if self.meters_per_pixel < 5.2:
            lbl_border = pal.get("twy_label_border", "#0B111A")
            for ref, mx, my in twy_label_positions:
                if any(math.hypot(mx - rx, my - ry) < 25.0 for rx, ry, _, _, _ in rwy_threshold_badges):
                    continue
                rw = max(8.5, len(ref) * 3.8 + 4.5)
                rh = 6.5
                c_cut = 2.0
                # Beveled capsule polygon for a crisp EFB taxiway sign look
                self.canvas.create_polygon(
                    [
                        mx - rw + c_cut, my - rh,
                        mx + rw - c_cut, my - rh,
                        mx + rw, my - rh + c_cut,
                        mx + rw, my + rh - c_cut,
                        mx + rw - c_cut, my + rh,
                        mx - rw + c_cut, my + rh,
                        mx - rw, my + rh - c_cut,
                        mx - rw, my - rh + c_cut
                    ],
                    fill=pal["twy_label_bg"],
                    outline=lbl_border,
                    width=1.2
                )
                self.canvas.create_text(mx, my, text=ref, fill=pal["twy_label_fg"], font=("Arial", 8, "bold"))

        # 7b. Draw Interactive Circular Runway Badges (Lido AMM Cyan-Ringed Circles) on top of the runway & taxi route
        for ex, ey, end_id, is_act, rwy_hdg in rwy_threshold_badges:
            rad_c = 16 if is_act else 14
            fill_c = cam["s1"] if is_act else pal["rwy_circle_fill"]
            ring_c = pal["rwy_circle_ring"]
            if is_act:
                self.canvas.create_oval(
                    ex - (rad_c + 4), ey - (rad_c + 4), ex + (rad_c + 4), ey + (rad_c + 4),
                    fill="", outline=ring_c, width=1.5
                )
            self.canvas.create_oval(
                ex - rad_c, ey - rad_c, ex + rad_c, ey + rad_c,
                fill=fill_c, outline=ring_c, width=2.5
            )
            vis_r_hdg = (rwy_hdg - ac_hdg_s) if use_hdg_up else rwy_hdg
            r_rad = math.radians(vis_r_hdg - 90.0)
            r_ang = (-math.degrees(math.atan2(math.sin(r_rad), math.cos(r_rad)))) % 360.0
            if r_ang > 180.0:
                r_ang -= 360.0
            if r_ang > 90.0:
                r_ang -= 180.0
            elif r_ang < -90.0:
                r_ang += 180.0
            self.canvas.create_text(
                ex, ey,
                text=str(end_id),
                fill="#FFFFFF",
                font=("Arial", 10, "bold"),
                angle=r_ang
            )
            self._rwy_hitboxes.append((ex - rad_c, ey - rad_c, ex + rad_c, ey + rad_c, end_id, is_act))

        # 8. Draw Assigned Gate Marker (Highlighted Lido AMM Directional Stand Tag + Airline Icon in front of tip)
        if self.airport_data and self.airport_data.get("lat") is not None and self.airport_data.get("lon") is not None:
            gx, gy = self._latlon_to_xy(float(self.airport_data["lat"]), float(self.airport_data["lon"]), w, h, cos_lat)
            gate_lbl = str(self.airport_data.get("gate") or "GATE")
            g_disp = re.sub(r'^(?:STAND|GATE|PARKING|RAMP|DOCK)\s*', '', gate_lbl, flags=re.I).replace(" ", "").upper() or gate_lbl
            g_hdg = self.airport_data.get("heading")
            if g_hdg is None and self.chart_data:
                for st in self.chart_data.get("stands", []):
                    if st.get("heading") is None:
                        continue
                    s_ref = str(st.get("ref", "")).replace(" ", "").upper()
                    s_norm = re.sub(r'([A-Z]*)0+(\d+)', r'\1\2', s_ref)
                    if s_ref == assigned_gate or s_norm == assigned_norm or (assigned_digits and s_ref == assigned_digits):
                        g_hdg = st["heading"]
                        break
            vis_g_hdg = ((float(g_hdg) - ac_hdg_s) if use_hdg_up else float(g_hdg)) if g_hdg is not None else 0.0
            hero_al = str(self.airport_data.get("airline_code") or "").strip().upper()
            hero_als_list = [hero_al] if hero_al else []
            assigned_term = str(self.airport_data.get("terminal") or "")
            if self.chart_data:
                for st in self.chart_data.get("stands", []):
                    s_ref = str(st.get("ref", "")).replace(" ", "").upper()
                    s_norm = re.sub(r'([A-Z]*)0+(\d+)', r'\1\2', s_ref)
                    if s_ref == assigned_gate or s_norm == assigned_norm:
                        als = [str(a).upper() for a in (st.get("airlines") or []) if a]
                        if not hero_al and als:
                            hero_al = als[0]
                        for a_c in als:
                            if a_c not in hero_als_list:
                                hero_als_list.append(a_c)
                        if not assigned_term and st.get("terminal"):
                            assigned_term = str(st.get("terminal"))
                        break

            gx0, gy0, gx1, gy1 = _draw_lido_stand_tag(
                gx, gy, g_disp, vis_g_hdg,
                fill_col=cam["s1"],
                border_col="#FFFFFF",
                fg_col="#FFFFFF",
                sc_mult=1.22,
                border_w=2.4,
                logo_codes=[hero_al] if hero_al else hero_als_list
            )
            self._stand_hitboxes.append((gx0, gy0, gx1, gy1, gate_lbl, tuple(hero_als_list), assigned_term, True))

        # 9. Draw Live SimConnect User Aircraft Icon (only on ground and within airport area)
        if not self._is_airborne() and self.user_aircraft and self.user_aircraft.get("connected") and self.user_aircraft.get("lat") is not None:
            ulat = self.user_aircraft["lat"]
            ulon = self.user_aircraft["lon"]
            uhdg = float(self.user_aircraft.get("heading") or 0.0)
            ax, ay = self._latlon_to_xy(ulat, ulon, w, h, cos_lat)
            if -100 <= ax <= w + 100 and -100 <= ay <= h + 100:
                # GPS pulse ring
                self.canvas.create_oval(ax - 18, ay - 18, ax + 18, ay + 18, outline="#38BDF8", width=2, dash=(4, 3))
                # Swept-wing jet silhouette rotated by true heading (or pointing straight up in Follow + Hdg Up mode)
                vis_hdg = 0.0 if use_hdg_up else uhdg
                rad = math.radians(vis_hdg - 90.0)
                def rot(px, py):
                    rx = px * math.cos(rad) - py * math.sin(rad)
                    ry = px * math.sin(rad) + py * math.cos(rad)
                    return ax + rx, ay + ry
                jet_shape = [
                    rot(14, 0),    # Nose
                    rot(4, -3),
                    rot(-2, -13),  # Left wingtip
                    rot(-5, -13),
                    rot(-3, -3),
                    rot(-11, -2),
                    rot(-13, -6),  # Left tailplane
                    rot(-14, -6),
                    rot(-13, 0),
                    rot(-14, 6),   # Right tailplane
                    rot(-13, 6),
                    rot(-11, 2),
                    rot(-3, 3),
                    rot(-5, 13),   # Right wingtip
                    rot(-2, 13),
                    rot(4, 3)
                ]
                flat_jet = [coord for pt in jet_shape for coord in pt]
                self.canvas.create_polygon(flat_jet, fill="#38BDF8", outline="")

        # 10. Bottom-Right Lido Legend & Status Overlay
        self.canvas.create_rectangle(w - 225, h - 28, w - 8, h - 6, fill="#0F172A", outline="")
        self.canvas.create_text(
            w - 116, h - 17,
            text="Scroll: Zoom  |  Drag: Pan  |  Lido Vector",
            fill="#94A3B8", font=("Arial", 9, "bold")
        )

        # 11. Grabbing Hand Icon at cursor when Left-Click + Hold is active
        if self._drag_start:
            hx, hy = self._drag_start
            self.canvas.create_oval(hx - 15, hy - 15, hx + 15, hy + 15, fill="#0F172A", outline="#38BDF8", width=2)
            hand_pts = [
                hx - 5, hy + 2,
                hx - 7, hy - 2,
                hx - 5, hy - 4,
                hx - 4, hy - 1,
                hx - 4, hy - 8,
                hx - 1, hy - 8,
                hx - 1, hy - 1,
                hx - 1, hy - 9,
                hx + 2, hy - 9,
                hx + 2, hy - 1,
                hx + 2, hy - 8,
                hx + 5, hy - 8,
                hx + 5, hy - 1,
                hx + 5, hy - 6,
                hx + 8, hy - 6,
                hx + 8, hy + 3,
                hx + 5, hy + 8,
                hx - 2, hy + 8
            ]
            self.canvas.create_polygon(hand_pts, fill="#F8FAFC", outline="#0F172A", width=1)
        elif self._hovered_stand_info:
            self._draw_stand_hover_tooltip()


class GUIApp(ctk.CTk):
    def get_resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

    def _apply_window_icon(self, win):
        """Applies the new GateFinder GF icon to the main window or any CTkToplevel modal (overriding CustomTkinter's 200ms delayed default icon)."""
        icon_path = self.get_resource_path("icon.ico")
        png_path = self.get_resource_path("icon.png")
        def _set_ico():
            try:
                if not win.winfo_exists():
                    return
                if os.path.exists(icon_path):
                    win.iconbitmap(icon_path)
                    try:
                        win.wm_iconbitmap(icon_path)
                    except Exception:
                        pass
                if os.path.exists(png_path):
                    from PIL import Image, ImageTk
                    if not hasattr(self, "_gf_win_icon_photo") or self._gf_win_icon_photo is None:
                        im = Image.open(png_path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
                        self._gf_win_icon_photo = ImageTk.PhotoImage(im)
                    win.iconphoto(False, self._gf_win_icon_photo)
            except Exception:
                pass
        _set_ico()
        try:
            win.after(210, _set_ico)
            win.after(360, _set_ico)
        except Exception:
            pass

    def _get_active_camaieu(self, fd=None):
        data = fd or getattr(self, "last_flight_data", None) or {}
        raw_al = str(data.get("airline") or "").strip()
        al_code = raw_al.split("-")[0].strip().upper() if "-" in raw_al else raw_al[:3].strip().upper()
        if hasattr(self, "backend") and self.backend and hasattr(self.backend, "get_airline_camaieu_palette"):
            return self.backend.get_airline_camaieu_palette(al_code)
        return {
            "s1": "#578DA8",
            "s2": "#517B90",
            "s3": "#4A6C7D",
            "s4": "#435D6B",
            "s5": "#4E788E",
            "s6": "#3F5663",
            "accent": "#66A1BE",
            "card_bg": "#1B1E24",
            "card_sel_bg": "#25343D",
            "card_hover_bg": "#1D2930",
            "subcard_bg": "#1B1E24",
        }

    def __init__(self, config, autostart, backend):
        super().__init__()
        self.config = config
        self.autostart = autostart
        self.backend = backend
        self._startup_splash = None
        self._geom_save_after_id = None

        self.configure(fg_color="#121418")
        self.title("MSFS 2024 - GateFinder V2.0.4")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        min_w = min(1180, int(screen_w * 0.80))
        min_h = min(700, int(screen_h * 0.68))
        win_w = min(1600, int(screen_w * 0.84))
        win_h = min(870, int(screen_h * 0.80))
        win_x = max(0, (screen_w - win_w) // 2)
        win_y = max(10, (screen_h - win_h - 40) // 2)

        self._restore_zoomed = False
        saved_geom = self.config.settings.get("window_geometry")
        if isinstance(saved_geom, dict):
            try:
                sw_val = int(saved_geom.get("w", 0))
                sh_val = int(saved_geom.get("h", 0))
                sx_val = saved_geom.get("x")
                sy_val = saved_geom.get("y")
                self._restore_zoomed = bool(saved_geom.get("zoomed", False))
                if sw_val >= min_w and sh_val >= min_h:
                    win_w = min(sw_val, max(min_w, screen_w))
                    win_h = min(sh_val, max(min_h, screen_h - 30))
                if sx_val is not None and sy_val is not None:
                    sx_i = int(sx_val)
                    sy_i = int(sy_val)
                    try:
                        import ctypes
                        u32 = ctypes.windll.user32
                        vx = int(u32.GetSystemMetrics(76))
                        vy = int(u32.GetSystemMetrics(77))
                        vw = int(u32.GetSystemMetrics(78))
                        vh = int(u32.GetSystemMetrics(79))
                        if vw <= 0 or vh <= 0:
                            vx, vy, vw, vh = 0, 0, screen_w, screen_h
                    except Exception:
                        vx, vy, vw, vh = 0, 0, screen_w, screen_h
                    if (vx - 80) <= sx_i <= (vx + vw - 160) and (vy - 20) <= sy_i <= (vy + vh - 120):
                        win_x = sx_i
                        win_y = max(vy, sy_i)
            except Exception:
                pass

        self._last_normal_geom = {"w": int(win_w), "h": int(win_h), "x": int(win_x), "y": int(win_y)}
        self.geometry(f"{win_w}x{win_h}+{win_x}+{win_y}")
        self._apply_window_icon(self)
        self.minsize(min_w, min_h)

        has_recent_session = False
        try:
            p_sess = self.backend._get_session_state_path()
            if os.path.exists(p_sess) and (time.time() - os.path.getmtime(p_sess) < 14 * 3600):
                has_recent_session = True
        except Exception:
            pass
        has_sb_user = bool(self.config.settings.get("simbrief_username", "").strip())
        will_show_startup_splash = bool(
            "--silent" not in sys.argv
            and has_sb_user
            and (self.config.settings.get("auto_fetch", True) or has_recent_session)
        )

        # Only start withdrawn if launched silently or if the startup splash screen will be shown
        if "--silent" in sys.argv or will_show_startup_splash:
            self.withdraw()
        if will_show_startup_splash:
            self._create_startup_splash_window(initial_step="Initializing GateFinder...")
            self.update()
            
        self.active_phase = "departure"  # "departure" or "arrival"
        self.user_manual_phase_override = False
        self.vector_chart = None
        
        # Bind close, minimize, focus, and window move/resize persistence events
        self.protocol("WM_DELETE_WINDOW", self.on_close_request)
        self.bind("<Unmap>", self.on_unmap)
        self.bind("<FocusIn>", self._on_window_focus_in)
        self.bind("<Configure>", self._on_root_configure)
        
        self.create_widgets()
        
        self.last_flight_data = None
        self._last_rendered_signature = None
        self._is_importing_ofp = False
        self._last_prompted_ofp_id = None
        self._ofp_check_in_progress = False
        self._ofp_modal_open = False
        self._last_ofp_poll_time = time.time()
        self._last_live_stand_check_time = 0.0
        self._prompted_live_msfs_stands = set()
        self._was_engines_running_at_arr = False
        self._engine_shutdown_prompted_for_ofp = None
        self._inflight_map_preview_override = False
        self._was_airborne_state = False
        self._just_touched_down_latch = False
        self._airborne_toast_timer = None
        self._live_stand_modal_dlg = None
        self.check_sync_loop()
        
        # Check for updates in background
        import threading
        threading.Thread(target=self.check_for_updates, daemon=True).start()
        
        # Check if setup is needed
        if not has_sb_user:
            self.show_settings()
            if "--silent" not in sys.argv:
                self.deiconify()
                self.after(80, self.show_main_window)
        else:
            self._startup_init_running = True
            self.show_main_view()
            self._startup_init_running = False
            if self.config.settings.get("auto_fetch", True) or has_recent_session:
                self.after(10, lambda keep=has_recent_session: self.fetch_simbrief(turnaround_keep_gate=True if keep else None, startup_splash=True))
                if "--silent" not in sys.argv:
                    self.after(12000, self._ensure_window_visible_after_splash)
            else:
                if "--silent" not in sys.argv:
                    self.deiconify()
                    self.after(80, self.show_main_window)

    def _ensure_window_visible_after_splash(self):
        """Safety watchdog so the main window is guaranteed to open even if startup SimBrief takes too long."""
        if getattr(self, "_is_importing_ofp", False):
            self.after(5000, self._ensure_window_visible_after_splash)
            return
        if "--silent" not in sys.argv and self.state() == "withdrawn":
            self._close_startup_splash()
            self.show_main_window()

    def _on_window_focus_in(self, event=None):
        """Immediately check SimBrief when the user switches focus back to GateFinder (e.g. from their browser)."""
        if event is not None and event.widget != self:
            return
        now_ts = time.time()
        if (now_ts - getattr(self, "_last_ofp_poll_time", 0.0)) >= 2.5:
            self._last_ofp_poll_time = now_ts
            self._poll_simbrief_for_new_ofp(engine_cut_trigger=False)

    def check_sync_loop(self):
        next_delay_ms = 200
        try:
            if getattr(self.backend, "show_window_requested", False):
                self.backend.show_window_requested = False
                self.show_main_window()
            if getattr(self, "_is_importing_ofp", False):
                return
            fd = self.backend.get_dynamic_flight_data()
            if fd:
                u_ac = fd.get("user_aircraft") or {}

                # Auto-switch tab to Arrival immediately when Wheels-Off (is_airborne == True)
                is_airborne = bool(fd.get("is_airborne", False))
                if getattr(self, "_was_airborne_state", False) and not is_airborne and u_ac.get("connected") and u_ac.get("on_ground") is True:
                    self._just_touched_down_latch = True
                self._was_airborne_state = is_airborne

                # Auto-dismiss any open MSFS Live Stand modal if aircraft starts moving, takes off, or was resolved in the In-Game Panel
                live_dlg = getattr(self, "_live_stand_modal_dlg", None)
                if live_dlg is not None:
                    if is_airborne or float(u_ac.get("gs") or 0.0) >= 4.0 or fd.get("pending_live_stand_prompt") is None:
                        try:
                            if live_dlg.winfo_exists():
                                live_dlg.destroy()
                        except Exception:
                            pass
                        self._live_stand_modal_dlg = None
                        self._ofp_modal_open = False
                        self.backend.pending_live_stand_prompt = None

                if is_airborne:
                    self.user_manual_phase_override = False
                    if self.active_phase != "arrival":
                        self.active_phase = "arrival"
                        self._last_rendered_signature = None
                else:
                    rec_phase = fd.get("recommended_phase")
                    if rec_phase in ("departure", "arrival") and not self.user_manual_phase_override:
                        if rec_phase != self.active_phase:
                            self.active_phase = rec_phase
                            self._last_rendered_signature = None

                # Check if core structural data changed (airport, gate, runway, active tab) vs live telemetry/route progress
                dep = fd.get("departure") or {}
                arr = fd.get("arrival") or {}

                # Detect post-arrival engine shutdown at stand OR newly generated SimBrief OFP on the ground
                cur_ofp_id = fd.get("ofp_id")
                arr_tr = arr.get("taxi_route") or {}
                arr_live_status = arr_tr.get("live_status")
                eng_running = u_ac.get("engines_running")
                d_arr_m = fd.get("d_arr_m")
                at_arr_airport_ground = bool(
                    u_ac.get("connected")
                    and u_ac.get("on_ground") is True
                    and d_arr_m is not None
                    and float(d_arr_m) < 6500.0
                )
                if self.active_phase == "arrival" or arr_live_status in ("TAXI_IN", "ARRIVED_AT_GATE") or at_arr_airport_ground:
                    if eng_running is True:
                        self._was_engines_running_at_arr = True
                    elif eng_running is False and self._was_engines_running_at_arr:
                        parked_at_arr = (arr_live_status == "ARRIVED_AT_GATE")
                        if not parked_at_arr and at_arr_airport_ground and float(u_ac.get("gs") or 0.0) < 2.5:
                            arr_ic = str(arr.get("icao") or "").strip().upper()
                            if arr_ic:
                                live_arr_info = self.backend.detect_live_msfs_parked_stand(
                                    arr_ic,
                                    default_lat=arr.get("lat"),
                                    default_lon=arr.get("lon"),
                                    extra_chart_data=arr.get("chart_data")
                                )
                                live_arr_gate = live_arr_info.get("gate") if isinstance(live_arr_info, dict) else live_arr_info
                                if live_arr_gate:
                                    parked_at_arr = True
                                    cur_arr_g = str(arr.get("gate") or "").strip()
                                    if re.sub(r'[^A-Z0-9]', '', str(live_arr_gate).upper()) != re.sub(r'[^A-Z0-9]', '', cur_arr_g.upper()):
                                        try:
                                            canon_g, coords, meta = self.backend.resolve_stand_in_airport_db(arr_ic, live_arr_gate)
                                            final_g = canon_g or live_arr_gate
                                            self.backend.apply_hub_gate_override(
                                                "arrival",
                                                final_g,
                                                coords,
                                                gate_meta=meta,
                                                source=arr.get("atc_runway_source") or "GateFinder"
                                            )
                                            self.config.settings["last_arrival_icao"] = arr_ic
                                            self.config.settings["last_arrival_gate"] = final_g
                                            self.config.save()
                                            fd = self.backend.get_dynamic_flight_data()
                                            arr = fd.get("arrival") or {}
                                        except Exception as err_arr_live:
                                            print(f"[GUI] Error syncing live arrival stand {live_arr_gate}: {err_arr_live}")
                        if parked_at_arr:
                            self._was_engines_running_at_arr = False
                            if self._engine_shutdown_prompted_for_ofp != cur_ofp_id:
                                self._engine_shutdown_prompted_for_ofp = cur_ofp_id
                                self._poll_simbrief_for_new_ofp(engine_cut_trigger=True)

                now_ts = time.time()
                if cur_ofp_id and u_ac.get("on_ground") is not False and (now_ts - self._last_ofp_poll_time >= 6.0):
                    self._last_ofp_poll_time = now_ts
                    self._poll_simbrief_for_new_ofp(engine_cut_trigger=False)

                # Live MSFS Parked Stand Monitor: if aircraft is parked on the ground at a stand different from dep['gate']
                # (and AI ATC has not already overridden the departure stand), auto-sync GateFinder to the live stand!
                dep_gate_src = str(dep.get("gate_source") or "").upper()
                if (
                    u_ac.get("connected")
                    and u_ac.get("on_ground") is True
                    and float(u_ac.get("gs") or 0.0) < 3.0
                    and self.active_phase == "departure"
                    and "BEYOND" not in dep_gate_src
                    and "SAYINTENTIONS" not in dep_gate_src
                    and not getattr(self, "_ofp_modal_open", False)
                    and (now_ts - getattr(self, "_last_live_stand_check_time", 0.0) >= 2.0)
                ):
                    self._last_live_stand_check_time = now_ts
                    dep_icao = str(dep.get("icao") or "").strip().upper()
                    dep_gate = str(dep.get("gate") or "").strip()
                    if dep_icao and dep_gate and dep_gate not in ("N/A", "No Gate Found", "No Suitable Stand"):
                        live_stand_info = self.backend.detect_live_msfs_parked_stand(
                            dep_icao,
                            default_lat=dep.get("lat"),
                            default_lon=dep.get("lon"),
                            extra_chart_data=dep.get("chart_data")
                        )
                        live_stand = live_stand_info.get("gate") if isinstance(live_stand_info, dict) else live_stand_info
                        if live_stand:
                            norm_live = re.sub(r'[^A-Z0-9]', '', str(live_stand).upper())
                            norm_cur = re.sub(r'[^A-Z0-9]', '', str(dep_gate).upper())
                            if norm_live and norm_live != norm_cur:
                                # Do not overwrite if the user manually picked a sub-stand (e.g. P2A vs P2) within the last 25s
                                # or if `dep_gate` and `live_stand` are overlapping MARS stands of the same bay (e.g. A 4 vs A 41)
                                hub_obj = getattr(self.backend, "interop_hub", None)
                                last_manual_ts = max(
                                    float(getattr(hub_obj, "_last_user_manual_gate_ts", 0.0) or 0.0),
                                    float(getattr(hub_obj, "_last_manual_gate_change_ts", 0.0) or 0.0)
                                ) if hub_obj else 0.0
                                skip_substand = False
                                if hasattr(self.backend, "are_mars_related_stands") and self.backend.are_mars_related_stands(dep_gate, live_stand, 25.0):
                                    skip_substand = True
                                elif (now_ts - last_manual_ts) < 25.0:
                                    m_c = re.match(r'^([A-Z]*)(\d+)([A-Z]*)$', norm_cur)
                                    m_l = re.match(r'^([A-Z]*)(\d+)([A-Z]*)$', norm_live)
                                    if m_c and m_l and int(m_c.group(2)) == int(m_l.group(2)):
                                        skip_substand = True
                                if not skip_substand:
                                    prompt_key = (str(cur_ofp_id or ""), dep_icao, norm_live)
                                    if prompt_key not in self._prompted_live_msfs_stands:
                                        self._prompted_live_msfs_stands.add(prompt_key)
                                        self.backend.pending_live_stand_prompt = None
                                        try:
                                            canon_g, coords, meta = self.backend.resolve_stand_in_airport_db(
                                                dep_icao, live_stand, default_lat=dep.get("lat"), default_lon=dep.get("lon")
                                            )
                                            self.backend.apply_hub_gate_override(
                                                "departure",
                                                canon_g or live_stand,
                                                coords,
                                                gate_meta=meta,
                                                source=dep.get("atc_runway_source") or "GateFinder"
                                            )
                                        except Exception as err_auto_dep:
                                            print(f"[GUI] Error auto-syncing live departure stand {live_stand}: {err_auto_dep}")

                raw_map_hib = bool(fd.get("map_hibernated", False))
                if not raw_map_hib:
                    self._inflight_map_preview_override = False
                eff_map_hib = bool(raw_map_hib and not getattr(self, "_inflight_map_preview_override", False))
                show_maps_cfg = bool(self.config.settings.get("show_maps", True))

                sig = (
                    fd.get("aircraft"), fd.get("airline"),
                    dep.get("icao"), dep.get("gate"), dep.get("gate_source"), dep.get("atc_runway_source"), dep.get("selected_runway"), dep.get("atc_runway"), tuple(dep.get("atc_taxi_via") or ()), dep.get("bypassed_summary"),
                    arr.get("icao"), arr.get("gate"), arr.get("gate_source"), arr.get("atc_runway_source"), arr.get("selected_runway"), arr.get("atc_runway"), tuple(arr.get("atc_taxi_via") or ()), arr.get("bypassed_summary"),
                    self.active_phase, eff_map_hib, show_maps_cfg, is_airborne
                )
                self.last_flight_data = fd
                if sig != self._last_rendered_signature:
                    active_apt = dep if self.active_phase == "departure" else arr
                    cur_route_key = (self.active_phase, active_apt.get("icao"), active_apt.get("gate"), active_apt.get("selected_runway"), tuple(active_apt.get("atc_taxi_via") or ()))
                    preserve_cam = (getattr(self, "_last_route_cam_key", None) == cur_route_key)
                    self._last_route_cam_key = cur_route_key
                    self._last_rendered_signature = sig
                    self.render_results(fd, preserve_camera=preserve_cam)
                else:
                    apt_active = fd.get(self.active_phase) or {}
                    self._update_live_sidebar_labels(apt_active)
                    if not eff_map_hib and self.vector_chart and self.vector_chart.winfo_exists():
                        # Fast canvas refresh for live aircraft movement without rebuilding sidebar widgets
                        self.vector_chart.set_data(apt_active, phase_mode=self.active_phase, user_aircraft=u_ac, preserve_camera=True)

                self._check_and_show_gate_toast()

                next_delay_ms = 800 if eff_map_hib else 200
        except Exception as e:
            print(f"[GUI] check_sync_loop recovered from error: {e}")
        finally:
            self.after(next_delay_ms, self.check_sync_loop)

    def _check_and_show_gate_toast(self):
        try:
            if not hasattr(self, "backend") or not self.backend:
                return
            hub = getattr(self.backend, "interop_hub", None)
            if not hub:
                return
            toast = getattr(hub, "last_gate_toast", None)
            if not toast or not isinstance(toast, dict):
                return
            tid = toast.get("id")
            if not tid or tid == getattr(self, "_last_shown_gate_toast_id", None):
                return
            # Wait until main window is visible and vector_chart exists before consuming the toast
            if self.state() == "withdrawn":
                return
            if not hasattr(self, "vector_chart") or not self.vector_chart or not self.vector_chart.winfo_exists():
                return
            self._last_shown_gate_toast_id = tid
            if (time.time() - float(toast.get("timestamp") or 0.0)) <= 12.0:
                self.vector_chart.show_gate_toast(toast)
        except Exception:
            pass

    def _format_gsx_pill_info(self, gsx_st, gate_name=""):
        raw_lbl = str((gsx_st or {}).get("label") or "").strip()
        u = raw_lbl.upper()
        if "INJECTED" in u or "SYNCED" in u or "ACTIVE" in u:
            short_txt = "GSX Pro: Synced"
        elif "ARMED" in u:
            short_txt = "GSX Pro: Armed"
        else:
            short_txt = "GSX Pro: Sync"
        tip_txt = f"{raw_lbl or 'GSX Pro Arrival Auto-Sync'} — Click to manually sync GSX Pro with Stand {gate_name or ''}".strip()
        return short_txt, tip_txt

    def _update_live_sidebar_labels(self, airport_data):
        if not airport_data:
            return
        tr = airport_data.get("taxi_route") or {}
        live_status = tr.get("live_status", "PLANNED")
        det_exit = tr.get("detected_exit")

        # Update EXIT pill in the active phase header card if detected_exit changed
        if hasattr(self, "_phase_tab_widgets"):
            w_map = self._phase_tab_widgets.get(self.active_phase)
            if w_map and "pill_exit" in w_map:
                exit_str = f"EXIT : {det_exit}" if det_exit else ""
                if exit_str:
                    w_map["lbl_exit"].configure(text=exit_str, text_color="#FFFFFF")
                    if not w_map["pill_exit"].winfo_ismapped():
                        w_map["pill_exit"].pack(side="left", padx=(8, 0))
                else:
                    if w_map["pill_exit"].winfo_ismapped():
                        w_map["pill_exit"].pack_forget()

        status_map = {
            "PARKED": ("PARKED AT GATE  -  READY FOR TAXI", "#FFFFFF"),
            "TAXI_OUT": ("LIVE TAXIING TO RUNWAY", "#FFFFFF"),
            "ON_RUNWAY": ("ON RUNWAY  -  MONITORING STOPPED", "#FFFFFF"),
            "LANDING_ROLL": (f"LANDING ROLL  -  EXIT: {det_exit or 'AUTO'}", "#FFFFFF"),
            "TAXI_IN": (f"VACATED VIA {det_exit or 'TWY'}  -  TAXI TO STAND", "#FFFFFF"),
            "ARRIVED_AT_GATE": ("ARRIVED AT STAND  -  BLOCKS ON", "#FFFFFF"),
            "PLANNED": ("" if self.active_phase == "arrival" else "OPTIMAL TAXI ROUTE READY", "#FFFFFF")
        }
        st_text, st_col = status_map.get(live_status, ("", "#FFFFFF"))
        if hasattr(self, "lbl_live_status_pill") and self.lbl_live_status_pill and self.lbl_live_status_pill.winfo_exists():
            if st_text:
                if not self.lbl_live_status_pill.winfo_ismapped():
                    self.lbl_live_status_pill.pack(fill="x", padx=14, pady=(12, 6), before=self._sb_clearance_hdr_lbl)
                if getattr(self, "_last_st_pill_val", None) != (st_text, st_col):
                    self._last_st_pill_val = (st_text, st_col)
                    self.lbl_live_status_pill.configure(text=st_text, text_color="#FFFFFF")
            else:
                if self.lbl_live_status_pill.winfo_ismapped():
                    self.lbl_live_status_pill.pack_forget()

        gate_val = airport_data.get("gate") or "N/A"
        if airport_data.get("osm") and gate_val != "N/A":
            gate_val = f"Stand {gate_val}"
        sel_rwy = airport_data.get("selected_runway") or "RWY"
        clearance_str = (tr.get("clearance_text") or f"Stand {gate_val} -> RWY {sel_rwy}").replace("➔", "->")
        self._render_clearance_pills(clearance_str, sel_rwy=sel_rwy, det_exit=det_exit)

        if airport_data.get("ai_cleared"):
            ai_txt = "AI Aircraft Cleared from Stand"
        elif airport_data.get("ai_active"):
            ai_txt = "Gate Secured (Auto-Clear Active)"
        elif airport_data.get("simconnect_connected"):
            ai_txt = "SimConnect Connected (Stand Monitored)"
        else:
            ai_txt = "SimConnect Standby"
        if hasattr(self, "vector_chart") and self.vector_chart and self.vector_chart.winfo_exists():
            self.vector_chart.set_simconnect_status(ai_txt)

        if self.active_phase == "arrival" and hasattr(self, "_sb_gsx_pill") and self._sb_gsx_pill and self._sb_gsx_pill.winfo_exists():
            gsx_st = airport_data.get("gsx_status") or {}
            if not gsx_st.get("visible", True):
                self._sb_gsx_pill.grid_remove()
            else:
                short_gsx, tip_gsx = self._format_gsx_pill_info(gsx_st, airport_data.get("gate", ""))
                self._sb_gsx_lbl.configure(text=short_gsx, text_color="#FFFFFF")
                self._sb_gsx_tip.text = tip_gsx
                self._sb_gsx_pill.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(0, 0))

    def _on_root_configure(self, event=None):
        if event is not None and event.widget != self:
            return
        try:
            st = self.state()
            if st not in ("normal", "zoomed"):
                return
            if st == "normal":
                w, h, x, y = self._parse_geometry_string(self.geometry())
                if w is not None and h is not None and w >= 900 and h >= 550:
                    self._last_normal_geom = {
                        "w": int(w),
                        "h": int(h),
                        "x": int(x if x is not None else self.winfo_x()),
                        "y": int(y if y is not None else self.winfo_y()),
                    }
            if getattr(self, "_geom_save_after_id", None) is not None:
                try:
                    self.after_cancel(self._geom_save_after_id)
                except Exception:
                    pass
            self._geom_save_after_id = self.after(450, self._save_window_geometry)
        except Exception:
            pass

    def _save_window_geometry(self):
        self._geom_save_after_id = None
        try:
            if not self.winfo_exists():
                return
            st = self.state()
            if st == "normal":
                w, h, x, y = self._parse_geometry_string(self.geometry())
                if w is not None and h is not None and w >= 900 and h >= 550:
                    self._last_normal_geom = {
                        "w": int(w),
                        "h": int(h),
                        "x": int(x if x is not None else self.winfo_x()),
                        "y": int(y if y is not None else self.winfo_y()),
                    }
            base = dict(getattr(self, "_last_normal_geom", None) or {})
            if not base:
                return
            base["zoomed"] = bool(st == "zoomed")
            if self.config.settings.get("window_geometry") != base:
                self.config.settings["window_geometry"] = base
                self.config.save()
        except Exception:
            pass

    def on_close_request(self):
        from tkinter import messagebox
        self._save_window_geometry()
        ans = messagebox.askyesno("Quit GateFinder", "Are you sure you want to quit GateFinder?")
        if ans:
            self._save_window_geometry()
            self.destroy()
            sys.exit(0)

    def on_unmap(self, event):
        if event.widget == self:
            if self.state() == "iconic":
                self.hide_to_tray()

    def hide_to_tray(self):
        self._save_window_geometry()
        self.withdraw()

    def show_main_window(self):
        try:
            self.deiconify()
            if getattr(self, "_restore_zoomed", False):
                self._restore_zoomed = False
                self.state("zoomed")
            else:
                self.state("normal")
            self.lift()
            self.focus_force()
            if hasattr(self, "vector_chart") and self.vector_chart and self.vector_chart.winfo_exists():
                if not getattr(self.vector_chart, "_initial_fit_done", False) and not getattr(self.vector_chart, "follow_aircraft", False):
                    self.after(40, self.vector_chart.fit_route_view)
        except Exception:
            pass

    def check_for_updates(self):
        import urllib.request
        import json
        current_ver = "v2.0.4"
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/wildbill75/gsx-gatefinder/releases/latest",
                headers={'User-Agent': 'GateFinder-Updater'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name", "").strip()
                html_url = data.get("html_url", "https://github.com/wildbill75/gsx-gatefinder/releases")
                
                def parse_version(v_str):
                    cleaned = "".join(c for c in v_str if c.isdigit() or c == '.')
                    try:
                        return tuple(map(int, cleaned.split('.')))
                    except Exception:
                        return (0,)
                
                if parse_version(latest_tag) > parse_version(current_ver):
                    self.after(0, lambda url=html_url, tag=latest_tag: self.show_update_banner(url, tag))
        except Exception as e:
            print("Update check failed:", e)

    def show_update_banner(self, url, tag):
        self.update_banner_container.pack(fill="x", padx=20, pady=(0, 8), after=self.header_frame)
        banner_frame = ctk.CTkFrame(self.update_banner_container, fg_color="#10B981", corner_radius=8)
        banner_frame.pack(fill="x")
        
        lbl = ctk.CTkLabel(
            banner_frame, 
            text=f"Update Available: Click here to download {tag}", 
            text_color="white",
            font=ctk.CTkFont(size=13, weight="bold"),
            cursor="hand2"
        )
        lbl.pack(expand=True, fill="both", pady=6)
        
        def open_link(event):
            import webbrowser
            webbrowser.open(url)
            
        lbl.bind("<Button-1>", open_link)

    def create_widgets(self):
        # Sleek EFB Top Navigation & SimBrief Dispatch Header Bar (Zero borders)
        self.header_frame = ctk.CTkFrame(self, fg_color="#1B1E24", corner_radius=12, border_width=0)
        self.header_frame.pack(fill="x", padx=16, pady=(12, 8))

        # Right side controls in Top Bar: Settings & Import SimBrief (Solid filled action buttons)
        self.btn_settings = ctk.CTkButton(
            self.header_frame, text="Settings", width=116, height=46,
            fg_color="#2B303B", hover_color="#383E4C", border_width=0,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.show_settings
        )
        self.btn_settings.pack(side="right", padx=(8, 16), pady=12)

        self.btn_import = ctk.CTkButton(
            self.header_frame, text="Import SimBrief", width=182, height=46,
            fg_color="#0A86C2", hover_color="#0A6E9E", border_width=0,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.fetch_simbrief
        )
        self.btn_import.pack(side="right", padx=6, pady=12)

        # Left/Center SimBrief OFP Summary Pill Container (fixed 46px height when empty so header never stretches vertically)
        self.flight_strip_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent", height=46, width=1)
        self.flight_strip_frame.pack(side="left", padx=(16, 8), pady=12)
        ctk.CTkLabel(
            self.flight_strip_frame,
            text="GATEFINDER V2.0.4  •  SIMBRIEF EFB DISPATCH",
            height=46,
            fg_color="#2B303B",
            text_color="#94A3B8",
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            padx=18,
            pady=6,
        ).pack(side="left")

        # Dedicated container for update banner
        self.update_banner_container = ctk.CTkFrame(self, fg_color="transparent")
        
        # Container for main content
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True)

        # 1. Main View Frame (Full-window EFB workspace)
        self.main_view_frame = ctk.CTkFrame(self.content_container, fg_color="transparent")

        # BeyondATC-style Two Separate Phase Cards (DEPARTURE vs ARRIVAL)
        self.tabs_bar = ctk.CTkFrame(self.main_view_frame, fg_color="transparent")
        self.tabs_bar.pack(fill="x", padx=16, pady=(0, 8))
        self.tabs_bar.grid_columnconfigure(0, weight=1, uniform="phase_col")
        self.tabs_bar.grid_columnconfigure(1, weight=1, uniform="phase_col")

        self._hovered_phase_tab = None
        self._phase_tab_widgets = {}

        def _build_phase_zone(col_idx, phase_key, title_txt):
            card = ctk.CTkFrame(
                self.tabs_bar, fg_color="#1B1E24", corner_radius=12,
                border_width=0, cursor="hand2"
            )
            card.grid(row=0, column=col_idx, sticky="ew", padx=(0, 6) if col_idx == 0 else (6, 0), pady=0)

            inner = ctk.CTkFrame(card, fg_color="#1B1E24", corner_radius=0, border_width=0, cursor="hand2")
            inner.pack(anchor="center", pady=11)

            lbl_title = ctk.CTkLabel(
                inner, text=title_txt, fg_color="transparent",
                font=ctk.CTkFont(size=15, weight="bold"), text_color="#FFFFFF", cursor="hand2"
            )
            lbl_title.pack(side="left", padx=(6, 16))

            pill_icao = ctk.CTkFrame(inner, fg_color="#0A6E9E", corner_radius=8, border_width=0, cursor="hand2")
            pill_icao.pack(side="left", padx=(0, 8))
            lbl_icao = ctk.CTkLabel(
                pill_icao, text="----", fg_color="transparent",
                font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFFFFF", cursor="hand2"
            )
            lbl_icao.pack(padx=18, pady=7)

            pill_stand = ctk.CTkFrame(inner, fg_color="#0D587D", corner_radius=8, border_width=0, cursor="hand2")
            pill_stand.pack(side="left", padx=(0, 8))
            lbl_stand = ctk.CTkLabel(
                pill_stand, text="STAND --", fg_color="transparent",
                font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFFFFF", cursor="hand2"
            )
            lbl_stand.pack(padx=18, pady=7)

            pill_rwy = ctk.CTkFrame(inner, fg_color="#0D435E", corner_radius=8, border_width=0, cursor="hand2")
            pill_rwy.pack(side="left")
            lbl_rwy = ctk.CTkLabel(
                pill_rwy, text="RWY --", fg_color="transparent",
                font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFFFFF", cursor="hand2"
            )
            lbl_rwy.pack(padx=18, pady=7)

            def _on_stand_pill_click(event, p=phase_key):
                self.switch_phase(p, manual=True)
                self.after(40, lambda: self._open_manual_stand_picker_modal(phase=p))
                return "break"

            all_w = (card, inner, lbl_title, pill_icao, lbl_icao, pill_stand, lbl_stand, pill_rwy, lbl_rwy)
            for w in all_w:
                if w in (pill_stand, lbl_stand):
                    w.bind("<Button-1>", _on_stand_pill_click)
                else:
                    w.bind("<Button-1>", lambda e, p=phase_key: self.switch_phase(p, manual=True))
                w.bind("<Enter>", lambda e, p=phase_key: self._on_phase_zone_enter(p), add="+")
                w.bind("<Leave>", lambda e, p=phase_key: self._on_phase_zone_leave(p), add="+")

            self._phase_tab_widgets[phase_key] = {
                "card": card,
                "inner": inner,
                "lbl_title": lbl_title,
                "pill_icao": pill_icao,
                "lbl_icao": lbl_icao,
                "pill_stand": pill_stand,
                "lbl_stand": lbl_stand,
                "pill_rwy": pill_rwy,
                "lbl_rwy": lbl_rwy,
                "all": set(all_w),
            }

        _build_phase_zone(0, "departure", "DEPARTURE")
        _build_phase_zone(1, "arrival", "ARRIVAL")
        self._apply_phase_tabs_visual_state()

        # Main Full-Screen Workspace Frame
        self.results_frame = ctk.CTkFrame(self.main_view_frame, corner_radius=0, fg_color="transparent", border_width=0)
        self.results_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        
        self.placeholder_lbl = ctk.CTkLabel(
            self.results_frame,
            text="Click 'Import SimBrief' to load your Departure & Arrival Lido Ground Charts and Live Taxi Routes.",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#94A3B8"
        )
        self.placeholder_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # 2. Settings View Frame
        self.settings_view = SettingsView(self.content_container, self.config, self.autostart, self.backend, self.on_settings_saved, self.show_main_view)

    def _show_airborne_departure_locked_toast(self):
        try:
            if hasattr(self, "_airborne_toast_frame") and self._airborne_toast_frame and self._airborne_toast_frame.winfo_exists():
                self._airborne_toast_frame.destroy()
            toast = ctk.CTkFrame(
                self.main_view_frame,
                fg_color="#2B303B",
                corner_radius=8,
                border_width=0
            )
            toast.place(relx=0.5, rely=0.075, anchor="n")
            toast.lift()
            ctk.CTkLabel(
                toast,
                text="  IN FLIGHT  Departure chart locked while airborne (Arrival diagram active)  ",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#FBBF24",
                padx=14,
                pady=6
            ).pack()
            self._airborne_toast_frame = toast
            if getattr(self, "_airborne_toast_timer", None):
                try:
                    self.after_cancel(self._airborne_toast_timer)
                except Exception:
                    pass
            self._airborne_toast_timer = self.after(
                3500,
                lambda: toast.destroy() if toast.winfo_exists() else None
            )
        except Exception:
            pass

    def _on_phase_zone_enter(self, phase):
        if getattr(self, "_hovered_phase_tab", None) != phase:
            self._hovered_phase_tab = phase
            self._apply_phase_tabs_visual_state()

    def _on_phase_zone_leave(self, phase):
        def _check_pointer():
            try:
                px, py = self.winfo_pointerx(), self.winfo_pointery()
                w_under = self.winfo_containing(px, py)
                w_set = (self._phase_tab_widgets.get(phase) or {}).get("all", set())
                curr = w_under
                inside = False
                while curr is not None:
                    if curr in w_set:
                        inside = True
                        break
                    curr = getattr(curr, "master", None)
                if not inside and getattr(self, "_hovered_phase_tab", None) == phase:
                    self._hovered_phase_tab = None
                    self._apply_phase_tabs_visual_state()
            except Exception:
                self._hovered_phase_tab = None
                self._apply_phase_tabs_visual_state()
        self.after(20, _check_pointer)

    def _apply_phase_tabs_visual_state(self):
        if not hasattr(self, "_phase_tab_widgets"):
            return
        cam = self._get_active_camaieu()
        c_base = "#1B1E24"
        c_sel = cam.get("card_sel_bg", "#25343D")
        c_hov = cam.get("card_hover_bg", "#1D2930")
        for p_key in ("departure", "arrival"):
            w_map = self._phase_tab_widgets.get(p_key)
            if not w_map:
                continue
            is_active = (self.active_phase == p_key)
            is_hovered = (getattr(self, "_hovered_phase_tab", None) == p_key)
            if is_active:
                card_bg = c_sel
            elif is_hovered:
                card_bg = c_hov
            else:
                card_bg = c_base

            w_map["card"].configure(fg_color=card_bg, border_width=0)
            w_map["inner"].configure(fg_color=card_bg)

    def switch_phase(self, phase, manual=False):
        if phase not in ("departure", "arrival"):
            return
        if phase == "departure" and self.last_flight_data:
            is_airborne = bool(self.last_flight_data.get("is_airborne", False))
            if is_airborne:
                self._show_airborne_departure_locked_toast()
                return
        if manual:
            self.user_manual_phase_override = True
            if phase == self.active_phase and getattr(self, "_last_rendered_signature", None) is not None:
                return
        self.active_phase = phase
        self._apply_phase_tabs_visual_state()
        self._last_rendered_signature = None
        if self.last_flight_data:
            self.render_results(self.last_flight_data, preserve_camera=False)

    def _close_clearance_rwy_dropdown(self, event=None):
        bind_id = getattr(self, "_clearance_outside_bind_id", None)
        self._clearance_outside_bind_id = None
        if bind_id is not None:
            try:
                self.unbind("<Button-1>", bind_id)
            except Exception:
                pass
        pop = getattr(self, "_clearance_rwy_popup", None)
        self._clearance_rwy_popup = None
        if pop is not None:
            try:
                if pop.winfo_exists():
                    pop.destroy()
            except Exception:
                pass

    def _on_clearance_rwy_global_click(self, event):
        pop = getattr(self, "_clearance_rwy_popup", None)
        if pop is None or not pop.winfo_exists():
            self._close_clearance_rwy_dropdown()
            return
        try:
            mx, my = event.x_root, event.y_root
            px0, py0 = pop.winfo_rootx(), pop.winfo_rooty()
            px1, py1 = px0 + pop.winfo_width(), py0 + pop.winfo_height()
            if px0 <= mx <= px1 and py0 <= my <= py1:
                return
            pill_rwy = getattr(self, "_clearance_rwy_pill_widget", None)
            if pill_rwy is not None and pill_rwy.winfo_exists():
                bx0, by0 = pill_rwy.winfo_rootx(), pill_rwy.winfo_rooty()
                bx1, by1 = bx0 + pill_rwy.winfo_width(), by0 + pill_rwy.winfo_height()
                if bx0 <= mx <= bx1 and by0 <= my <= by1:
                    return
        except Exception:
            pass
        self._clearance_rwy_last_toggle_ts = time.monotonic()
        self._close_clearance_rwy_dropdown()

    def _open_clearance_rwy_dropdown(self, event=None):
        now = time.monotonic()
        if now - getattr(self, "_clearance_rwy_last_toggle_ts", 0.0) < 0.25:
            return "break"
        self._clearance_rwy_last_toggle_ts = now

        t_obj = getattr(self, "_clearance_rwy_tooltip", None)
        if t_obj is not None:
            try:
                t_obj.hide_tip()
            except Exception:
                pass

        if getattr(self, "_clearance_rwy_popup", None) is not None and self._clearance_rwy_popup.winfo_exists():
            self._close_clearance_rwy_dropdown()
            return "break"
        self._close_clearance_rwy_dropdown()

        phase_key = self.active_phase
        if not self.last_flight_data:
            return "break"
        apt = (self.last_flight_data.get(phase_key) or {})
        avail_rwys = list(
            apt.get("available_runways")
            or (apt.get("chart_data") or {}).get("available_runways")
            or (apt.get("taxi_route") or {}).get("available_runways")
            or []
        )
        sel_rwy = str(apt.get("selected_runway") or (avail_rwys[0] if avail_rwys else "")).strip()
        sel_rwy_clean = re.sub(r'^RWY\s*', '', sel_rwy, flags=re.IGNORECASE).upper()
        if sel_rwy_clean and sel_rwy_clean not in [re.sub(r'^RWY\s*', '', str(x).strip(), flags=re.IGNORECASE).upper() for x in avail_rwys]:
            avail_rwys = [sel_rwy_clean] + avail_rwys
        if not avail_rwys:
            return "break"

        pill_rwy = getattr(self, "_clearance_rwy_pill_widget", None)
        if not pill_rwy or not pill_rwy.winfo_exists():
            return "break"
        cam = self._get_active_camaieu()

        try:
            self.update_idletasks()
            x = pill_rwy.winfo_rootx() - self.winfo_rootx()
            y = pill_rwy.winfo_rooty() - self.winfo_rooty() + pill_rwy.winfo_height() + 4
            w = max(pill_rwy.winfo_width(), 124)
        except Exception:
            x, y, w = 24, 320, 124

        pop = ctk.CTkFrame(
            self,
            width=w,
            fg_color="#1B1E24",
            corner_radius=8,
            border_width=0
        )
        self._clearance_rwy_popup = pop

        def _pick(rwy_val):
            self._clearance_rwy_last_toggle_ts = time.monotonic()
            self._close_clearance_rwy_dropdown()
            self._on_runway_selected(rwy_val, phase=phase_key)

        for r in avail_rwys:
            r_clean = re.sub(r'^RWY\s*', '', str(r).strip(), flags=re.IGNORECASE).upper()
            is_cur = (r_clean == sel_rwy_clean)
            btn = ctk.CTkButton(
                pop,
                text=f"RWY {r_clean}",
                anchor="center",
                width=w - 8,
                height=32,
                corner_radius=6,
                fg_color=cam["s1"] if is_cur else "#2B303B",
                hover_color=cam["s2"],
                border_width=0,
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda rv=r_clean: _pick(rv)
            )
            btn.pack(fill="x", padx=4, pady=2)

        pop.place(x=x, y=y)
        pop.lift()

        def _register_outside():
            if getattr(self, "_clearance_rwy_popup", None) is pop and pop.winfo_exists():
                try:
                    self._clearance_outside_bind_id = self.bind("<Button-1>", self._on_clearance_rwy_global_click, add="+")
                except Exception:
                    pass
        self.after(90, _register_outside)
        return "break"

    def show_settings(self):
        self.main_view_frame.pack_forget()
        self.header_frame.pack_forget()
        if hasattr(self, "settings_view") and hasattr(self.settings_view, "refresh_dynamic_statuses"):
            self.settings_view.refresh_dynamic_statuses()
        self.settings_view.pack(fill="both", expand=True, padx=0, pady=0)

    def show_main_view(self):
        self.settings_view.pack_forget()
        if not self.header_frame.winfo_ismapped():
            self.header_frame.pack(fill="x", padx=16, pady=(12, 8), before=self.content_container)
        self.btn_settings.configure(
            text="Settings",
            width=105,
            height=44,
            fg_color="#374151",
            hover_color="#4B5563",
            state="normal",
            command=self.show_settings
        )
        self.main_view_frame.pack(fill="both", expand=True)
        if hasattr(self, "settings_view") and hasattr(self.settings_view, "save_settings_silent"):
            try:
                self.settings_view.save_settings_silent()
            except Exception:
                pass
        if (
            not getattr(self, "_startup_init_running", False)
            and getattr(self, "last_flight_data", None) is None
            and not getattr(self, "_is_importing_ofp", False)
            and self.config.settings.get("simbrief_username", "").strip()
        ):
            self.after(80, lambda: self.fetch_simbrief(startup_splash=True))

    def on_settings_saved(self, changed_keys=None):
        if changed_keys is not None and not changed_keys:
            return
        if changed_keys is None or ("gsx_profile_path" in changed_keys or "msfs_community_path" in changed_keys or "msfs_community2024_path" in changed_keys):
            self.backend.load_data()
        if hasattr(self.backend, "interop_hub") and self.backend.interop_hub:
            if changed_keys is None or "auto_inject_gsx" in changed_keys:
                self.backend.interop_hub.on_gsx_setting_changed()
        if self.backend.current_flight_data:
            self.backend.current_flight_data["show_maps"] = True
            self.backend.current_flight_data["hibernate_map_in_flight"] = self.config.settings.get("hibernate_map_in_flight", True)
            self.last_flight_data = self.backend.get_dynamic_flight_data()
            
        if self.last_flight_data and (changed_keys is None or "auto_inject_gsx" in changed_keys or "hibernate_map_in_flight" in changed_keys):
            self._last_rendered_signature = None
            self.render_results(self.last_flight_data)

    def _close_startup_splash(self):
        sp = getattr(self, "_startup_splash", None)
        self._startup_splash = None
        self._splash_prog_card = None
        if sp:
            try:
                if sp.winfo_exists():
                    sp.destroy()
            except Exception:
                pass

    def _populate_progress_card(self, prog_card, initial_step="Fetching SimBrief flight plan..."):
        try:
            from PIL import Image, ImageDraw
            gf_png = self.get_resource_path("icon.png")
            if os.path.exists(gf_png):
                logo_sz = 88
                pil_gf = Image.open(gf_png).convert("RGBA").resize((logo_sz, logo_sz), Image.Resampling.LANCZOS)
                mask = Image.new("L", (logo_sz, logo_sz), 0)
                draw_m = ImageDraw.Draw(mask)
                draw_m.rounded_rectangle((0, 0, logo_sz - 1, logo_sz - 1), radius=16, fill=255)
                rounded_gf = Image.new("RGBA", (logo_sz, logo_sz), (0, 0, 0, 0))
                rounded_gf.paste(pil_gf, (0, 0), mask)
                self._splash_gf_ctk = ctk.CTkImage(light_image=rounded_gf, dark_image=rounded_gf, size=(logo_sz, logo_sz))
                ctk.CTkLabel(prog_card, text="", image=self._splash_gf_ctk).pack(pady=(34, 8))
        except Exception:
            pass

        ctk.CTkLabel(
            prog_card, text="GATEFINDER",
            font=ctk.CTkFont(size=18, weight="bold"), text_color="#F8FAFC"
        ).pack(pady=(0, 20))

        self.lbl_import_step = ctk.CTkLabel(
            prog_card, text=initial_step,
            font=ctk.CTkFont(size=13), text_color="#CBD5E1"
        )
        self.lbl_import_step.pack(pady=(0, 14))

        bar_w, bar_h = 350, 8
        prog_canvas = tk.Canvas(
            prog_card, width=bar_w, height=bar_h,
            bg="#0B0E14", bd=0, highlightthickness=0
        )
        prog_canvas.pack(pady=(0, 12))
        self.import_progress_bar = prog_canvas

        def _render_blue_gradient_bar(pct_val):
            try:
                if not prog_canvas.winfo_exists():
                    return
                from PIL import Image, ImageDraw, ImageTk
                scale = 2
                sw_b, sh_b = bar_w * scale, bar_h * scale
                img = Image.new("RGBA", (sw_b, sh_b), (11, 14, 20, 255))
                draw = ImageDraw.Draw(img)
                draw.rounded_rectangle((0, 0, sw_b - 1, sh_b - 1), radius=sh_b // 2, fill=(24, 30, 44, 255))

                clamped = max(0.06, min(1.0, float(pct_val)))
                fill_w = max(sh_b, int(sw_b * clamped))

                grad = Image.new("RGBA", (fill_w, sh_b))
                g_px = grad.load()
                stops = [
                    (0.0, (224, 242, 254)),
                    (0.30, (125, 211, 252)),
                    (0.65, (56, 189, 248)),
                    (1.0, (2, 132, 199)),
                ]
                for x in range(fill_w):
                    t = x / max(1, fill_w - 1)
                    r, g, b = stops[-1][1]
                    for idx_s in range(len(stops) - 1):
                        t0, c0 = stops[idx_s]
                        t1, c1 = stops[idx_s + 1]
                        if t0 <= t <= t1:
                            f = (t - t0) / max(1e-6, t1 - t0)
                            r = int(c0[0] + (c1[0] - c0[0]) * f)
                            g = int(c0[1] + (c1[1] - c0[1]) * f)
                            b = int(c0[2] + (c1[2] - c0[2]) * f)
                            break
                    for y in range(sh_b):
                        g_px[x, y] = (r, g, b, 255)

                p_mask = Image.new("L", (fill_w, sh_b), 0)
                ImageDraw.Draw(p_mask).rounded_rectangle((0, 0, fill_w - 1, sh_b - 1), radius=sh_b // 2, fill=255)
                img.paste(grad, (0, 0), p_mask)

                final_bar = img.resize((bar_w, bar_h), Image.Resampling.LANCZOS)
                self._splash_bar_photo = ImageTk.PhotoImage(final_bar)
                prog_canvas.delete("all")
                prog_canvas.create_image(0, 0, anchor="nw", image=self._splash_bar_photo)
            except Exception:
                pass

        self._render_blue_gradient_bar = _render_blue_gradient_bar
        _render_blue_gradient_bar(0.06)

        lbl_ver_ftr = ctk.CTkLabel(
            prog_card, text="V2.0.4 • © 2026 Sidestick Priority",
            font=ctk.CTkFont(size=11), text_color="#475569"
        )
        lbl_ver_ftr.place(relx=1.0, rely=1.0, x=-20, y=-12, anchor="se")

    def _create_startup_splash_window(self, initial_step="Initializing GateFinder..."):
        sp = getattr(self, "_startup_splash", None)
        if sp and sp.winfo_exists():
            if hasattr(self, "lbl_import_step") and self.lbl_import_step.winfo_exists():
                self.lbl_import_step.configure(text=initial_step)
            return sp
        sp_w, sp_h = 520, 330
        splash = ctk.CTkToplevel(self)
        splash.title("GateFinder V2.0.4")
        splash.overrideredirect(True)
        splash.configure(fg_color="#0B0E14")
        self._apply_window_icon(splash)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        splash.geometry(f"{sp_w}x{sp_h}+{max(0, (sw - sp_w) // 2)}+{max(0, (sh - sp_h) // 2)}")
        try:
            splash.attributes("-topmost", True)
        except Exception:
            pass
        self._startup_splash = splash
        prog_card = ctk.CTkFrame(
            splash, fg_color="#0B0E14", corner_radius=12,
            border_width=1, border_color="#1E2532"
        )
        prog_card.pack(fill="both", expand=True, padx=0, pady=0)
        self._splash_prog_card = prog_card
        self._populate_progress_card(prog_card, initial_step=initial_step)
        return splash

    def fetch_simbrief(self, turnaround_keep_gate=None, startup_splash=False):
        if getattr(self, "_is_importing_ofp", False):
            return
        # Always sync the live SimBrief entry from Settings if the user typed it there without clicking Save yet
        if hasattr(self, "settings_view") and hasattr(self.settings_view, "simbrief_entry"):
            typed_user = self.settings_view.simbrief_entry.get().strip()
            if typed_user:
                self.config.settings["simbrief_username"] = typed_user
                self.config.save()

        username = self.config.settings.get("simbrief_username", "").strip()
        if not username:
            self._close_startup_splash()
            if "--silent" not in sys.argv:
                self.deiconify()
            messagebox.showerror("Error", "Please configure your Simbrief Username or Pilot ID in Settings.")
            self.show_settings()
            return
            
        self._is_importing_ofp = True
        # Ensure we are on the Main View when importing
        self.show_main_view()
        self.btn_import.configure(text="Importing OFP...", state="disabled")

        # Build Sleek EFB On-the-Fly Airport Construction Progress Card
        self._last_clearance_val = None
        self._last_traffic_pills_val = None
        self._last_rendered_signature = None
        for w in self.results_frame.winfo_children():
            w.destroy()

        use_splash = bool((startup_splash or getattr(self, "last_flight_data", None) is None) and "--silent" not in sys.argv)
        sp_w, sp_h = 520, 330
        if use_splash:
            if self.state() != "withdrawn":
                self.withdraw()
            self._create_startup_splash_window(initial_step="Fetching SimBrief flight plan...")
        else:
            prog_card = ctk.CTkFrame(
                self.results_frame, fg_color="#0B0E14", corner_radius=12,
                border_width=1, border_color="#1E2532", width=sp_w, height=sp_h
            )
            prog_card.place(relx=0.5, rely=0.5, anchor="center")
            prog_card.pack_propagate(False)
            self._populate_progress_card(prog_card, initial_step="Fetching SimBrief flight plan...")

        _render_blue_gradient_bar = getattr(self, "_render_blue_gradient_bar", lambda v: None)
        _render_blue_gradient_bar(0.08)

        self.update()

        import threading
        def _on_progress(pct, step_msg):
            def _upd():
                _render_blue_gradient_bar(pct)
                if hasattr(self, "lbl_import_step") and self.lbl_import_step.winfo_exists():
                    self.lbl_import_step.configure(text=step_msg)
            self.after(0, _upd)

        prompted_stand_holder = [None]
        chose_new_stand_holder = [bool(turnaround_keep_gate is False)]
        def thread_safe_turnaround_check(prev_gate, origin="", destination="", origin_rwy="", dest_rwy="", reason="turnaround_arrival"):
            evt = threading.Event()
            ans_holder = [True]
            prompted_stand_holder[0] = (str(origin or "").strip().upper(), str(prev_gate or "").strip())
            def ask_on_main():
                try:
                    ans_holder[0] = self.on_turnaround_check(prev_gate, origin, destination, origin_rwy, dest_rwy, reason=reason)
                    if ans_holder[0] is False:
                        chose_new_stand_holder[0] = True
                finally:
                    evt.set()
            self.after(0, ask_on_main)
            evt.wait(timeout=60)
            return ans_holder[0]

        def _worker():
            try:
                self.backend.get_flight_data(
                    username,
                    on_turnaround_check=thread_safe_turnaround_check,
                    progress_callback=_on_progress,
                    turnaround_keep_gate=turnaround_keep_gate
                )
                dyn_result = self.backend.get_dynamic_flight_data()
                def _on_ok():
                    self._is_importing_ofp = False
                    self.user_manual_phase_override = False
                    ofp_id_val = str(dyn_result.get("ofp_id") or "")
                    self._last_prompted_ofp_id = ofp_id_val
                    if prompted_stand_holder[0]:
                        p_icao, p_gate = prompted_stand_holder[0]
                        norm_p = re.sub(r'[^A-Z0-9]', '', p_gate.upper())
                        if p_icao and norm_p:
                            self._prompted_live_msfs_stands.add((ofp_id_val, p_icao, norm_p))
                    if turnaround_keep_gate is False or chose_new_stand_holder[0]:
                        dep_d = dyn_result.get("departure") or {}
                        dep_ic = str(dep_d.get("icao") or "").strip().upper()
                        live_st_info = self.backend.detect_live_msfs_parked_stand(
                            dep_ic,
                            default_lat=dep_d.get("lat"),
                            default_lon=dep_d.get("lon"),
                            extra_chart_data=dep_d.get("chart_data")
                        )
                        live_st = live_st_info.get("gate") if isinstance(live_st_info, dict) else live_st_info
                        if dep_ic and live_st:
                            norm_ls = re.sub(r'[^A-Z0-9]', '', str(live_st).upper())
                            if norm_ls:
                                self._prompted_live_msfs_stands.add((ofp_id_val, dep_ic, norm_ls))
                    self._was_engines_running_at_arr = False
                    u_ac_now = dyn_result.get("user_aircraft") or {}
                    if turnaround_keep_gate is not None or chose_new_stand_holder[0] or u_ac_now.get("on_ground") is not False:
                        self.active_phase = "departure"
                    else:
                        self.active_phase = dyn_result.get("recommended_phase", "departure")
                    self.last_flight_data = dyn_result
                    self._last_clearance_val = None
                    self._last_traffic_pills_val = None
                    self._last_rendered_signature = None
                    self.render_results(dyn_result, preserve_camera=False)
                    self.btn_import.configure(text="Import SimBrief", state="normal")
                    self._close_startup_splash()
                    if "--silent" not in sys.argv and self.state() == "withdrawn":
                        self.show_main_window()
                    if chose_new_stand_holder[0]:
                        self.after(120, lambda: self._open_manual_stand_picker_modal(phase="departure"))
                self.after(0, _on_ok)
            except Exception as e:
                err_str = str(e)
                def _on_err():
                    self._is_importing_ofp = False
                    self._close_startup_splash()
                    if "--silent" not in sys.argv and self.state() == "withdrawn":
                        self.show_main_window()
                    if self.last_flight_data:
                        self._last_rendered_signature = None
                        self.render_results(self.last_flight_data, preserve_camera=True)
                    messagebox.showerror("Simbrief Error", f"Unable to fetch flight plan.\nCheck your ID.\n{err_str}")
                    self.btn_import.configure(text="Import SimBrief", state="normal")
                self.after(0, _on_err)

        threading.Thread(target=_worker, daemon=True).start()

    def on_turnaround_check(self, prev_gate, origin="", destination="", origin_rwy="", dest_rwy="", reason="turnaround_arrival"):
        """Displays a concise borderless EFB Confirmation Modal with detailed tooltips."""
        result_holder = [True]
        cam = self._get_active_camaieu()
        dlg = ctk.CTkToplevel(self)
        self._apply_window_icon(dlg)
        if reason == "msfs_live":
            win_title = "MSFS Live Stand"
            hdr_prefix = "MSFS LIVE STAND"
            keep_btn_txt = f"Keep Stand {prev_gate}"
            msg = f"Parked at {origin or 'Departure'} Stand {prev_gate}. Keep this stand?"
            tip_txt = f"Your aircraft is currently parked in MSFS at {origin} Stand {prev_gate}. Keep it as your departure stand or let GateFinder assign a new stand."
        elif reason == "same_departure":
            win_title = "Previous Stand"
            hdr_prefix = "PREVIOUS STAND"
            keep_btn_txt = f"Keep Stand {prev_gate}"
            msg = f"Keep previous Stand {prev_gate} at {origin or 'Departure'}?"
            tip_txt = f"Keep your previous departure stand ({prev_gate}) at {origin} or let GateFinder assign a new stand."
        else:
            win_title = "Turnaround Stand"
            hdr_prefix = "TURNAROUND STAND"
            keep_btn_txt = f"Keep Stand {prev_gate}"
            msg = f"Turnaround at {origin or 'Departure'}: keep arrival Stand {prev_gate}?"
            tip_txt = f"You arrived at {origin} Stand {prev_gate} on your previous leg. Keep it for departure or assign a new stand."

        dlg.title(win_title)
        dlg_w, dlg_h = 430, 175
        dlg.geometry(f"{dlg_w}x{dlg_h}")
        dlg.resizable(False, False)
        dlg.configure(fg_color="#0F172A")
        is_root_hidden = bool(self.state() == "withdrawn" or getattr(self, "_startup_splash", None) is not None)
        if not is_root_hidden:
            dlg.transient(self)
        else:
            try:
                if getattr(self, "_startup_splash", None) and self._startup_splash.winfo_exists():
                    self._startup_splash.attributes("-topmost", False)
                dlg.attributes("-topmost", True)
            except Exception:
                pass
        dlg.grab_set()

        try:
            self.update_idletasks()
            if is_root_hidden:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                x = (sw - dlg_w) // 2
                y = (sh - dlg_h) // 2
            else:
                x = self.winfo_rootx() + (self.winfo_width() - dlg_w) // 2
                y = self.winfo_rooty() + (self.winfo_height() - dlg_h) // 2
            dlg.geometry(f"{dlg_w}x{dlg_h}+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(dlg, fg_color="#111827", corner_radius=10, border_width=0)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        route_hdr = f"  {origin} -> {destination}" if origin and destination else ""
        lbl_hdr = ctk.CTkLabel(
            card,
            text=f"{hdr_prefix}{route_hdr}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=cam["accent"]
        )
        lbl_hdr.pack(anchor="w", padx=16, pady=(14, 6))
        Tooltip(lbl_hdr, tip_txt)

        lbl_msg = ctk.CTkLabel(
            card,
            text=msg,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#FFFFFF",
            wraplength=390,
            justify="left"
        )
        lbl_msg.pack(anchor="w", padx=16, pady=(0, 16))
        Tooltip(lbl_msg, tip_txt)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 12))

        def _choose_keep():
            result_holder[0] = True
            dlg.destroy()

        def _choose_new():
            result_holder[0] = False
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", _choose_keep)

        btn_keep = ctk.CTkButton(
            btn_row,
            text=keep_btn_txt,
            fg_color=cam["s1"],
            hover_color=cam["s2"],
            border_width=0,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            command=_choose_keep
        )
        btn_keep.pack(side="left", expand=True, fill="x", padx=(0, 6))
        Tooltip(btn_keep, f"Keep Stand {prev_gate} at {origin} and calculate taxi routing from this stand.")

        btn_new = ctk.CTkButton(
            btn_row,
            text="New Stand",
            fg_color=cam["s3"],
            hover_color=cam["s4"],
            border_width=0,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            command=_choose_new
        )
        btn_new.pack(side="right", expand=True, fill="x", padx=(6, 0))
        Tooltip(btn_new, f"Automatically assign a new stand at {origin} based on your airline and aircraft.")

        self.wait_window(dlg)
        return result_holder[0]

    def _show_live_msfs_stand_mismatch_modal(self, dep_icao, live_stand, cur_gate):
        """Concise borderless modal when SimConnect detects the aircraft parked at a different stand."""
        if getattr(self, "_ofp_modal_open", False) or getattr(self, "_is_importing_ofp", False):
            return
        self._ofp_modal_open = True
        self.show_main_window()

        cam = self._get_active_camaieu()
        dlg = ctk.CTkToplevel(self)
        self._live_stand_modal_dlg = dlg
        self._apply_window_icon(dlg)
        dlg.title("MSFS Live Stand")
        dlg_w, dlg_h = 430, 175
        dlg.geometry(f"{dlg_w}x{dlg_h}")
        dlg.resizable(False, False)
        dlg.configure(fg_color="#0F172A")
        dlg.transient(self)
        dlg.grab_set()

        try:
            self.update_idletasks()
            x = self.winfo_rootx() + (self.winfo_width() - dlg_w) // 2
            y = self.winfo_rooty() + (self.winfo_height() - dlg_h) // 2
            dlg.geometry(f"{dlg_w}x{dlg_h}+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(dlg, fg_color="#111827", corner_radius=10, border_width=0)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        tip_txt = f"SimConnect detected your aircraft parked at {dep_icao} Stand {live_stand}, while GateFinder is set to Stand {cur_gate}."
        lbl_hdr = ctk.CTkLabel(
            card,
            text=f"MSFS LIVE STAND  {dep_icao}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=cam["accent"]
        )
        lbl_hdr.pack(anchor="w", padx=16, pady=(14, 6))
        Tooltip(lbl_hdr, tip_txt)

        lbl_msg = ctk.CTkLabel(
            card,
            text=f"Parked at Stand {live_stand} (Assigned: {cur_gate}) - Switch to {live_stand}?",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#FFFFFF",
            wraplength=390,
            justify="left"
        )
        lbl_msg.pack(anchor="w", padx=16, pady=(0, 16))
        Tooltip(lbl_msg, tip_txt)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 12))

        def _keep_msfs_stand():
            self._ofp_modal_open = False
            self._live_stand_modal_dlg = None
            dlg.destroy()
            try:
                self.backend.resolve_live_stand_prompt(keep_live=True, icao=dep_icao, live_stand=live_stand)
                self.last_flight_data = self.backend.get_dynamic_flight_data()
                self._last_rendered_signature = None
                self.render_results(self.last_flight_data, preserve_camera=False)
            except Exception as e:
                print(f"[GUI] Error applying live MSFS stand {live_stand}: {e}")

        def _keep_assigned():
            self._ofp_modal_open = False
            self._live_stand_modal_dlg = None
            self.backend.resolve_live_stand_prompt(keep_live=False)
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", _keep_assigned)

        btn_live = ctk.CTkButton(
            btn_row,
            text=f"Use Stand {live_stand} (MSFS)",
            fg_color=cam["s1"],
            hover_color=cam["s2"],
            border_width=0,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            command=_keep_msfs_stand
        )
        btn_live.pack(side="left", expand=True, fill="x", padx=(0, 6))
        Tooltip(btn_live, f"Switch departure stand to your live MSFS position (Stand {live_stand}) and recalculate taxi route.")

        btn_stay = ctk.CTkButton(
            btn_row,
            text=f"Keep Stand {cur_gate}",
            fg_color="#374151",
            hover_color="#4B5563",
            border_width=0,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            command=_keep_assigned
        )
        btn_stay.pack(side="right", expand=True, fill="x", padx=(6, 0))
        Tooltip(btn_stay, f"Keep GateFinder's assigned Stand {cur_gate}.")

    def _poll_simbrief_for_new_ofp(self, engine_cut_trigger=False):
        if getattr(self, "_is_importing_ofp", False) or getattr(self, "_ofp_modal_open", False) or getattr(self, "_ofp_check_in_progress", False):
            return
        username = self.config.settings.get("simbrief_username", "").strip()
        if not username or not self.last_flight_data:
            return
        cur_ofp_id = str(self.last_flight_data.get("ofp_id") or "")
        self._ofp_check_in_progress = True

        import threading
        def _bg_peek():
            try:
                peek = self.backend.peek_latest_simbrief_ofp(username)
                def _on_main():
                    self._ofp_check_in_progress = False
                    if getattr(self, "_is_importing_ofp", False) or getattr(self, "_ofp_modal_open", False):
                        return
                    if peek and peek.get("ofp_id") and str(peek["ofp_id"]) != cur_ofp_id:
                        new_id = str(peek["ofp_id"])
                        if new_id != str(getattr(self, "_last_prompted_ofp_id", "") or ""):
                            self._last_prompted_ofp_id = new_id
                            self._show_new_ofp_turnaround_modal(peek)
                            return
                    if engine_cut_trigger:
                        arr = (self.last_flight_data or {}).get("arrival") or {}
                        if arr.get("icao") and arr.get("gate"):
                            self._show_engine_shutdown_turnaround_modal(arr.get("icao"), arr.get("gate"))
                self.after(0, _on_main)
            except Exception:
                self._ofp_check_in_progress = False

        threading.Thread(target=_bg_peek, daemon=True).start()

    def _show_new_ofp_turnaround_modal(self, peek):
        if getattr(self, "_ofp_modal_open", False):
            return
        self._ofp_modal_open = True
        self.show_main_window()

        cam = self._get_active_camaieu()
        new_orig = str(peek.get("origin") or "").strip().upper()
        new_dest = str(peek.get("destination") or "").strip().upper()
        orig_rwy = peek.get("origin_rwy") or "AUTO"
        dest_rwy = peek.get("dest_rwy") or "AUTO"

        cand = self.backend.get_candidate_departure_stand(new_orig)
        prev_gate = (cand.get("gate") or "") if cand else ""
        cand_reason = (cand.get("reason") or "turnaround_arrival") if cand else ""
        has_candidate = bool(prev_gate)

        dlg = ctk.CTkToplevel(self)
        self._apply_window_icon(dlg)
        dlg_title = f"New SimBrief OFP ({new_orig} -> {new_dest})"
        hdr_txt = f"NEW SIMBRIEF OFP  {new_orig} -> {new_dest}"
        keep_lbl = f"Keep Stand {prev_gate}" if has_candidate else ""

        dlg.title(dlg_title)
        dlg_w, dlg_h = 460, 175
        dlg.geometry(f"{dlg_w}x{dlg_h}")
        dlg.resizable(False, False)
        dlg.configure(fg_color="#0F172A")
        dlg.transient(self)
        dlg.grab_set()

        try:
            self.update_idletasks()
            x = self.winfo_rootx() + (self.winfo_width() - dlg_w) // 2
            y = self.winfo_rooty() + (self.winfo_height() - dlg_h) // 2
            dlg.geometry(f"{dlg_w}x{dlg_h}+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(dlg, fg_color="#111827", corner_radius=10, border_width=0)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        tip_txt = f"New SimBrief OFP detected: {new_orig} (RWY {orig_rwy}) -> {new_dest} (RWY {dest_rwy})."
        lbl_hdr = ctk.CTkLabel(
            card,
            text=hdr_txt,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=cam["accent"]
        )
        lbl_hdr.pack(anchor="w", padx=16, pady=(14, 6))
        Tooltip(lbl_hdr, tip_txt)

        if has_candidate:
            msg = f"Load new OFP and keep Stand {prev_gate} at {new_orig}?"
        else:
            msg = f"Load new flight plan {new_orig} -> {new_dest} now?"

        lbl_msg = ctk.CTkLabel(
            card,
            text=msg,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#FFFFFF",
            wraplength=420,
            justify="left"
        )
        lbl_msg.pack(anchor="w", padx=16, pady=(0, 16))
        Tooltip(lbl_msg, tip_txt)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 12))

        def _close_later():
            self._ofp_modal_open = False
            dlg.destroy()

        def _load_keep():
            self._ofp_modal_open = False
            dlg.destroy()
            self.fetch_simbrief(turnaround_keep_gate=True)

        def _load_new_stand():
            self._ofp_modal_open = False
            dlg.destroy()
            self.fetch_simbrief(turnaround_keep_gate=False)

        def _load_auto():
            self._ofp_modal_open = False
            dlg.destroy()
            self.fetch_simbrief(turnaround_keep_gate=None)

        dlg.protocol("WM_DELETE_WINDOW", _close_later)

        if has_candidate:
            b1 = ctk.CTkButton(
                btn_row,
                text=keep_lbl,
                fg_color=cam["s1"],
                hover_color=cam["s2"],
                border_width=0,
                font=ctk.CTkFont(size=12, weight="bold"),
                height=34,
                command=_load_keep
            )
            b1.pack(side="left", expand=True, fill="x", padx=(0, 5))
            Tooltip(b1, f"Import new OFP ({new_orig} -> {new_dest}) and keep Stand {prev_gate} at {new_orig}.")

            b2 = ctk.CTkButton(
                btn_row,
                text="New Stand",
                fg_color=cam["s3"],
                hover_color=cam["s4"],
                border_width=0,
                font=ctk.CTkFont(size=12, weight="bold"),
                height=34,
                command=_load_new_stand
            )
            b2.pack(side="left", expand=True, fill="x", padx=5)
            Tooltip(b2, f"Import new OFP ({new_orig} -> {new_dest}) and assign a new departure stand at {new_orig}.")

            b3 = ctk.CTkButton(
                btn_row,
                text="Later",
                fg_color="#374151",
                hover_color="#4B5563",
                border_width=0,
                width=76,
                font=ctk.CTkFont(size=12, weight="bold"),
                height=34,
                command=_close_later
            )
            b3.pack(side="right", padx=(5, 0))
        else:
            b1 = ctk.CTkButton(
                btn_row,
                text=f"Load {new_orig} -> {new_dest}",
                fg_color=cam["s1"],
                hover_color=cam["s2"],
                border_width=0,
                font=ctk.CTkFont(size=12, weight="bold"),
                height=34,
                command=_load_auto
            )
            b1.pack(side="left", expand=True, fill="x", padx=(0, 6))
            Tooltip(b1, f"Import new OFP ({new_orig} RWY {orig_rwy} -> {new_dest} RWY {dest_rwy}).")

            b2 = ctk.CTkButton(
                btn_row,
                text="Later",
                fg_color="#374151",
                hover_color="#4B5563",
                border_width=0,
                width=95,
                font=ctk.CTkFont(size=12, weight="bold"),
                height=34,
                command=_close_later
            )
            b2.pack(side="right", padx=(6, 0))

    def _show_engine_shutdown_turnaround_modal(self, arr_icao, arr_gate):
        if getattr(self, "_ofp_modal_open", False):
            return
        self._ofp_modal_open = True
        self.show_main_window()

        cam = self._get_active_camaieu()
        dlg = ctk.CTkToplevel(self)
        self._apply_window_icon(dlg)
        dlg.title("Turnaround Ready")
        dlg_w, dlg_h = 460, 175
        dlg.geometry(f"{dlg_w}x{dlg_h}")
        dlg.resizable(False, False)
        dlg.configure(fg_color="#0F172A")
        dlg.transient(self)
        dlg.grab_set()

        try:
            self.update_idletasks()
            x = self.winfo_rootx() + (self.winfo_width() - dlg_w) // 2
            y = self.winfo_rooty() + (self.winfo_height() - dlg_h) // 2
            dlg.geometry(f"{dlg_w}x{dlg_h}+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(dlg, fg_color="#111827", corner_radius=10, border_width=0)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        tip_txt = f"Engines shut down at {arr_icao} Stand {arr_gate}. Load your next SimBrief OFP now or let GateFinder auto-detect it when generated."
        lbl_hdr = ctk.CTkLabel(
            card,
            text=f"TURNAROUND READY  {arr_icao} STAND {arr_gate}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=cam["accent"]
        )
        lbl_hdr.pack(anchor="w", padx=16, pady=(14, 6))
        Tooltip(lbl_hdr, tip_txt)

        lbl_msg = ctk.CTkLabel(
            card,
            text=f"Blocks on at Stand {arr_gate} - Load next SimBrief OFP?",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#FFFFFF",
            wraplength=420,
            justify="left"
        )
        lbl_msg.pack(anchor="w", padx=16, pady=(0, 16))
        Tooltip(lbl_msg, tip_txt)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 12))

        def _auto_wait():
            self._ofp_modal_open = False
            dlg.destroy()

        def _turnaround_keep():
            self._ofp_modal_open = False
            dlg.destroy()
            self.fetch_simbrief(turnaround_keep_gate=True)

        def _turnaround_new():
            self._ofp_modal_open = False
            dlg.destroy()
            self.fetch_simbrief(turnaround_keep_gate=False)

        dlg.protocol("WM_DELETE_WINDOW", _auto_wait)

        b1 = ctk.CTkButton(
            btn_row,
            text=f"Keep Stand {arr_gate}",
            fg_color=cam["s1"],
            hover_color=cam["s2"],
            border_width=0,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            command=_turnaround_keep
        )
        b1.pack(side="left", expand=True, fill="x", padx=(0, 5))
        Tooltip(b1, f"Load next SimBrief OFP and keep Stand {arr_gate} for departure.")

        b2 = ctk.CTkButton(
            btn_row,
            text="New Stand",
            fg_color=cam["s3"],
            hover_color=cam["s4"],
            border_width=0,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            command=_turnaround_new
        )
        b2.pack(side="left", expand=True, fill="x", padx=5)
        Tooltip(b2, "Load next SimBrief OFP and assign a new departure stand.")

        b3 = ctk.CTkButton(
            btn_row,
            text="Auto-Detect",
            fg_color="#374151",
            hover_color="#4B5563",
            border_width=0,
            width=95,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            command=_auto_wait
        )
        b3.pack(side="right", padx=(5, 0))
        Tooltip(b3, "Wait and automatically prompt as soon as you generate a new SimBrief OFP.")

    def _on_runway_selected(self, new_rwy, phase=None):
        if not self.last_flight_data:
            return
        target_phase = phase or self.active_phase
        apt = (self.last_flight_data.get(target_phase) or {})
        cur_rwy = str(apt.get("selected_runway") or "").strip().upper()
        atc_rwy = str(apt.get("atc_runway") or "").strip().upper()
        atc_src = str(apt.get("atc_runway_source") or apt.get("runway_source") or "AI ATC").strip()
        icao = str(apt.get("icao") or "").strip().upper()
        chosen = re.sub(r'^RWY\s*', '', str(new_rwy or "").strip(), flags=re.IGNORECASE).upper()

        if chosen == cur_rwy:
            return

        def _apply_change():
            self.backend.set_active_runway(target_phase, chosen, manual=True)
            self.last_flight_data = self.backend.get_dynamic_flight_data()
            self._last_rendered_signature = None
            self.render_results(self.last_flight_data, preserve_camera=False)

        if atc_rwy and chosen != atc_rwy:
            self._show_atc_runway_override_modal(
                atc_src=atc_src,
                icao=icao,
                atc_rwy=atc_rwy,
                new_rwy=chosen,
                on_confirm=_apply_change,
                on_cancel=lambda: None
            )
        else:
            _apply_change()

    def _show_atc_runway_override_modal(self, atc_src, icao, atc_rwy, new_rwy, on_confirm, on_cancel):
        cam = self._get_active_camaieu()
        dlg = ctk.CTkToplevel(self)
        self._apply_window_icon(dlg)
        dlg.title("ATC Runway Override")
        dlg_w, dlg_h = 410, 170
        dlg.geometry(f"{dlg_w}x{dlg_h}")
        dlg.resizable(False, False)
        dlg.configure(fg_color="#0F172A")
        dlg.transient(self)
        dlg.grab_set()

        try:
            self.update_idletasks()
            x = self.winfo_rootx() + (self.winfo_width() - dlg_w) // 2
            y = self.winfo_rooty() + (self.winfo_height() - dlg_h) // 2
            dlg.geometry(f"{dlg_w}x{dlg_h}+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(dlg, fg_color="#111827", corner_radius=10, border_width=0)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        tip_txt = f"{atc_src} assigned Runway {atc_rwy} at {icao}. Overriding switches GateFinder's ground taxi routing to Runway {new_rwy}."
        lbl_hdr = ctk.CTkLabel(
            card,
            text=f"{atc_src.upper()}  {icao}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=cam["accent"]
        )
        lbl_hdr.pack(anchor="w", padx=16, pady=(14, 6))
        Tooltip(lbl_hdr, tip_txt)

        lbl_msg = ctk.CTkLabel(
            card,
            text=f"ATC active runway is RWY {atc_rwy} - Switch to RWY {new_rwy}?",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#FFFFFF",
            wraplength=375,
            justify="left"
        )
        lbl_msg.pack(anchor="w", padx=16, pady=(0, 16))
        Tooltip(lbl_msg, tip_txt)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 12))

        def _cancel():
            dlg.destroy()
            if on_cancel:
                on_cancel()

        def _confirm():
            dlg.destroy()
            if on_confirm:
                on_confirm()

        dlg.protocol("WM_DELETE_WINDOW", _cancel)

        b_keep = ctk.CTkButton(
            btn_row,
            text=f"Keep RWY {atc_rwy}",
            fg_color=cam["s1"],
            hover_color=cam["s2"],
            border_width=0,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            command=_cancel
        )
        b_keep.pack(side="left", expand=True, fill="x", padx=(0, 6))
        Tooltip(b_keep, f"Stay synchronized with {atc_src} on Runway {atc_rwy}.")

        b_ovr = ctk.CTkButton(
            btn_row,
            text=f"Use RWY {new_rwy}",
            fg_color=cam["s3"],
            hover_color=cam["s4"],
            border_width=0,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            command=_confirm
        )
        b_ovr.pack(side="right", expand=True, fill="x", padx=(6, 0))
        Tooltip(b_ovr, f"Override {atc_src} and compute ground taxi routing for Runway {new_rwy}.")

    def _on_manual_stand_selected(self, new_gate, phase=None, reposition=False):
        if not new_gate or not self.last_flight_data:
            return
        gate_str = str(new_gate).strip()
        if not gate_str or gate_str in ("N/A", "No Gate Found", "No Suitable Stand"):
            return
        target_phase = phase if phase in ("departure", "arrival") else self.active_phase
        apt = (self.last_flight_data.get(target_phase) or {})
        cur_gate = str(apt.get("gate") or "").strip()
        if hasattr(self, "backend") and self.backend and hasattr(self.backend, "interop_hub") and self.backend.interop_hub:
            if reposition and hasattr(self.backend, "reposition_aircraft"):
                self.backend.reposition_aircraft(target_phase, gate_str)
            else:
                self.backend.interop_hub.set_manual_gate(target_phase, gate_str)
            self.last_flight_data = self.backend.get_dynamic_flight_data()
            self._last_rendered_signature = None
            self.render_results(self.last_flight_data, preserve_camera=True)
            self._check_and_show_gate_toast()

    def _open_manual_stand_picker_modal(self, phase=None):
        if not self.last_flight_data:
            return
        target_phase = phase if phase in ("departure", "arrival") else self.active_phase
        if target_phase != self.active_phase:
            self._switch_phase(target_phase)
        apt = (self.last_flight_data.get(target_phase) or {})
        icao = str(apt.get("icao") or "").strip().upper()
        apt_name = str(apt.get("name") or "")
        cur_gate = str(apt.get("gate") or "N/A").strip()
        cur_disp = _compact_gate_label(cur_gate)
        chart = apt.get("chart_data") or {}
        stands_raw = chart.get("stands") or []
        if not icao:
            return

        active_airline = str((self.last_flight_data.get("flight") or {}).get("airline_icao") or "").strip().upper()

        cam = self._get_active_camaieu()
        dlg = ctk.CTkToplevel(self)
        self._apply_window_icon(dlg)
        phase_lbl = "DEPARTURE" if target_phase == "departure" else "ARRIVAL"
        dlg.title(f"GSX/GateFinder Position Selector - {icao}")
        dlg_w, dlg_h = 540, 470
        dlg.geometry(f"{dlg_w}x{dlg_h}")
        dlg.resizable(False, False)
        dlg.configure(fg_color="#0F172A")
        dlg.transient(self)
        dlg.grab_set()

        try:
            self.update_idletasks()
            x = self.winfo_rootx() + (self.winfo_width() - dlg_w) // 2
            y = self.winfo_rooty() + (self.winfo_height() - dlg_h) // 2
            dlg.geometry(f"{dlg_w}x{dlg_h}+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(dlg, fg_color="#111827", corner_radius=12, border_width=0)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        hdr_row = ctk.CTkFrame(card, fg_color="transparent")
        hdr_row.pack(fill="x", padx=16, pady=(12, 8))

        lbl_hdr = ctk.CTkLabel(
            hdr_row,
            text=f"SELECT {phase_lbl} POSITION AT {icao}  CURRENT: {cur_disp}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#FFFFFF"
        )
        lbl_hdr.pack(side="left", anchor="w")
        Tooltip(lbl_hdr, f"{icao} - {apt_name}: Browse Terminal/Gate folders or search by gate number.")

        search_row = ctk.CTkFrame(card, fg_color="transparent")
        search_row.pack(fill="x", padx=16, pady=(0, 8))

        search_entry = ctk.CTkEntry(
            search_row,
            placeholder_text="Search by gate number",
            height=34,
            border_width=0,
            fg_color="#1E293B",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold")
        )
        search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        def _apply_choice(gate_val=None, reposition=False):
            target = (gate_val if gate_val is not None else search_entry.get()).strip()
            if not target:
                return
            dlg.destroy()
            self._on_manual_stand_selected(target, phase=target_phase, reposition=reposition)

        ctk.CTkButton(
            search_row,
            text="Select",
            width=74,
            height=34,
            fg_color="#1E293B",
            hover_color="#334155",
            border_width=0,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: _apply_choice(reposition=False)
        ).pack(side="right", padx=(4, 0))

        ctk.CTkButton(
            search_row,
            text="Warp",
            width=74,
            height=34,
            fg_color=cam["s1"],
            hover_color=cam["s2"],
            border_width=0,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: _apply_choice(reposition=True)
        ).pack(side="right")

        nav_bar = ctk.CTkFrame(card, fg_color="transparent", height=28)
        nav_bar.pack(fill="x", padx=16, pady=(0, 4))

        list_frame = ctk.CTkScrollableFrame(card, fg_color="#0B1120", corner_radius=8, border_width=0)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # Collect stands from both backend airport database (includes all MSFS/GSX gates) and chart_data
        stand_dict = {}
        try:
            if hasattr(self, "backend") and self.backend:
                apt_db = (
                    (getattr(self.backend, "coherent_airports", None) or {}).get(icao)
                    or (getattr(self.backend, "data", None) or {}).get(icao)
                    or (getattr(self.backend, "builtin_data", None) or {}).get(icao)
                    or {}
                )
                db_terms = apt_db.get("terminals") or {}
                for g_ref, als in (apt_db.get("gates") or {}).items():
                    g_clean = str(g_ref or "").strip()
                    if not g_clean:
                        continue
                    key_u = g_clean.replace(" ", "").upper()
                    t_name = _clean_terminal_label(db_terms.get(g_clean) or "")
                    stand_dict[key_u] = [g_clean, t_name, list(als) if isinstance(als, (list, tuple)) else []]
        except Exception:
            pass

        for st in stands_raw:
            s_ref = str(st.get("ref") or "").strip()
            if not s_ref:
                continue
            key_u = s_ref.replace(" ", "").upper()
            st_term = _clean_terminal_label(st.get("terminal") or "")
            st_als = st.get("airlines") or []
            if key_u in stand_dict:
                if st_term and not stand_dict[key_u][1]:
                    stand_dict[key_u][1] = st_term
                if st_als and not stand_dict[key_u][2]:
                    stand_dict[key_u][2] = list(st_als)
            else:
                stand_dict[key_u] = [s_ref, st_term, list(st_als)]

        stand_items = [(v[0], v[1], v[2]) for v in stand_dict.values()]

        def _sort_key(item):
            s_clean = item[0].strip().upper()
            m = re.match(r'^([A-Z]*)\s*(\d+)\s*([A-Z]*)$', s_clean)
            if m:
                return (m.group(1), int(m.group(2)), m.group(3))
            return (s_clean, 0, "")

        stand_items.sort(key=_sort_key)

        # Build GSX-style folder groups (by Gate Letter Prefix + Terminal description)
        groups_map = {}
        group_order = []
        airline_stands = []

        for s_ref, st_term, st_als in stand_items:
            if active_airline and any(str(a).upper() == active_airline for a in st_als):
                airline_stands.append((s_ref, st_term, st_als))
            m_pfx = re.match(r'^([A-Z]+)\s*\d+', s_ref.strip().upper())
            if m_pfx:
                pfx = m_pfx.group(1)
                g_key = f"GATE_{pfx}"
                g_title = f"Gate {pfx}"
            elif st_term:
                g_key = f"TERM_{st_term.upper()}"
                g_title = st_term
            else:
                g_key = "STANDS_NUM"
                g_title = "Numeric/Apron Stands"

            if g_key not in groups_map:
                groups_map[g_key] = {"title": g_title, "terms": [], "items": []}
                group_order.append(g_key)
            groups_map[g_key]["items"].append((s_ref, st_term, st_als))
            if st_term and st_term not in groups_map[g_key]["terms"]:
                groups_map[g_key]["terms"].append(st_term)

        active_group_holder = [None]  # None = Folder Root view, str = group key

        def _render_stand_row(parent, s_ref, st_term, st_als):
            is_cur = (s_ref.replace(" ", "").upper() == cur_gate.replace(" ", "").upper())
            is_al_match = bool(active_airline and any(str(a).upper() == active_airline for a in st_als))
            row = ctk.CTkFrame(
                parent,
                fg_color="#1E293B" if not is_cur else "#172554",
                corner_radius=8,
                border_width=0
            )
            row.pack(fill="x", padx=4, pady=3)

            # Pack right-side buttons FIRST so they are guaranteed full width and never squished
            ctk.CTkButton(
                row,
                text="Select Only",
                width=86,
                height=26,
                fg_color="#334155",
                hover_color="#475569",
                border_width=0,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda r=s_ref: _apply_choice(r, reposition=False)
            ).pack(side="right", padx=(4, 8), pady=5)

            ctk.CTkButton(
                row,
                text="Reposition",
                width=88,
                height=26,
                fg_color=cam["s1"],
                hover_color=cam["s2"],
                border_width=0,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda r=s_ref: _apply_choice(r, reposition=True)
            ).pack(side="right", padx=(0, 4), pady=5)

            s_disp = _compact_gate_label(s_ref)
            parts = [f"Gate {s_disp}"]
            if st_term:
                parts.append(st_term)
            if st_als:
                parts.append(", ".join(st_als[:3]))
            lbl_txt = "  ".join(parts)

            lbl = ctk.CTkLabel(
                row,
                text=lbl_txt,
                anchor="w",
                font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                text_color="#FFFFFF" if not is_al_match else "#38BDF8"
            )
            lbl.pack(side="left", fill="x", expand=True, padx=(10, 6), pady=6)

        def _clear_search():
            search_entry.delete(0, "end")
            try:
                card.focus_set()
            except Exception:
                pass
            _render_view()

        def _render_view(*_):
            for w in nav_bar.winfo_children():
                w.destroy()
            for w in list_frame.winfo_children():
                w.destroy()

            q = search_entry.get().strip().upper()
            q_compact = q.replace(" ", "")

            # Direct search mode across all stands
            if q_compact:
                ctk.CTkButton(
                    nav_bar,
                    text="Back to All Terminals/Gate Groups",
                    height=26,
                    fg_color="#1E293B",
                    hover_color="#334155",
                    border_width=0,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=_clear_search
                ).pack(side="left")

                shown = 0
                for s_ref, st_term, st_als in stand_items:
                    s_comp = s_ref.replace(" ", "").upper()
                    t_comp = st_term.replace(" ", "").upper()
                    al_comp = ",".join(st_als).upper()
                    if q_compact not in s_comp and q_compact not in t_comp and q_compact not in al_comp and q not in f"GATE {s_ref.upper()}":
                        continue
                    _render_stand_row(list_frame, s_ref, st_term, st_als)
                    shown += 1
                    if shown >= 80:
                        break
                return

            # Level 2: Inside a selected Terminal/Gate folder
            cur_grp = active_group_holder[0]
            if cur_grp is not None:
                def _go_root():
                    active_group_holder[0] = None
                    _render_view()

                ctk.CTkButton(
                    nav_bar,
                    text="Back to All Terminals/Gate Groups",
                    height=26,
                    fg_color="#1E293B",
                    hover_color="#334155",
                    border_width=0,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=_go_root
                ).pack(side="left")

                if cur_grp == "__AIRLINE__":
                    grp_items = airline_stands
                    grp_hdr = f"{active_airline} Airline Stands"
                else:
                    grp_info = groups_map.get(cur_grp) or {"title": cur_grp, "items": []}
                    grp_items = grp_info["items"]
                    grp_hdr = grp_info["title"]

                ctk.CTkLabel(
                    nav_bar,
                    text=grp_hdr,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=cam["accent"]
                ).pack(side="right")

                for s_ref, st_term, st_als in grp_items:
                    _render_stand_row(list_frame, s_ref, st_term, st_als)
                return

            # Level 1: GSX-style Root Folder View
            ctk.CTkLabel(
                nav_bar,
                text=f"Select Terminal/Gate Group at {icao}",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#94A3B8"
            ).pack(side="left")

            if airline_stands:
                def _open_al():
                    active_group_holder[0] = "__AIRLINE__"
                    _render_view()

                ctk.CTkButton(
                    list_frame,
                    text=f"📁  Positions for Your Airline ({active_airline})",
                    anchor="w",
                    height=36,
                    fg_color=cam["s1"],
                    hover_color=cam["s2"],
                    border_width=0,
                    text_color="#FFFFFF",
                    font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                    command=_open_al
                ).pack(fill="x", padx=4, pady=(3, 6))

            for g_key in group_order:
                g_info = groups_map[g_key]
                t0 = g_info["terms"][0] if g_info["terms"] else ""
                term_hint = f"  {t0}" if (t0 and t0.upper() != g_info["title"].upper()) else ""
                has_cur = any(it[0].replace(" ", "").upper() == cur_gate.replace(" ", "").upper() for it in g_info["items"])
                cur_tag = f"  [Current: {cur_disp}]" if has_cur else ""
                folder_txt = f"📁  {g_info['title']}{term_hint}{cur_tag}"

                def _open_grp(k=g_key):
                    active_group_holder[0] = k
                    _render_view()

                ctk.CTkButton(
                    list_frame,
                    text=folder_txt,
                    anchor="w",
                    height=34,
                    fg_color="#172554" if has_cur else "#1E293B",
                    hover_color="#1E3A8A" if has_cur else "#334155",
                    border_width=0,
                    text_color="#FFFFFF",
                    font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                    command=_open_grp
                ).pack(fill="x", padx=4, pady=2)

        _render_view()
        search_entry.bind("<KeyRelease>", _render_view)
        search_entry.bind("<Return>", lambda e: _apply_choice(reposition=False))

    def _ensure_sidebar_built(self):
        if hasattr(self, "sidebar_frame") and self.sidebar_frame and self.sidebar_frame.winfo_exists():
            return
        if hasattr(self, "placeholder_lbl") and self.placeholder_lbl and self.placeholder_lbl.winfo_exists():
            self.placeholder_lbl.destroy()
        self._last_clearance_val = None
        self._last_traffic_pills_val = None

        saved_sb_w = int(self.config.settings.get("sidebar_width", 356) or 356)
        self._sidebar_width = max(340, min(780, saved_sb_w))

        self.results_frame.grid_rowconfigure(0, weight=1)
        self.results_frame.grid_columnconfigure(0, weight=0, minsize=self._sidebar_width + 10)
        self.results_frame.grid_columnconfigure(1, weight=1)

        sidebar_outer = ctk.CTkFrame(self.results_frame, width=self._sidebar_width + 10, fg_color="transparent", border_width=0)
        sidebar_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 2), pady=0)
        sidebar_outer.grid_propagate(False)
        sidebar_outer.pack_propagate(False)
        self._sidebar_outer = sidebar_outer

        sidebar = ctk.CTkFrame(sidebar_outer, width=self._sidebar_width, fg_color="transparent", border_width=0)
        sidebar.pack(side="left", fill="both", expand=True, padx=0, pady=0)
        sidebar.pack_propagate(False)
        self.sidebar_frame = sidebar

        # Vertical Draggable Splitter Handle between Left Sidebar and Map
        sash = ctk.CTkFrame(sidebar_outer, width=10, fg_color="transparent", corner_radius=4, cursor="sb_h_double_arrow")
        sash.pack(side="right", fill="y", padx=(2, 0), pady=0)
        sash.pack_propagate(False)
        sash_grip = ctk.CTkFrame(sash, width=4, height=64, fg_color="#2B303B", corner_radius=2, cursor="sb_h_double_arrow")
        sash_grip.place(relx=0.5, rely=0.5, anchor="center")
        Tooltip(sash, "Drag left or right to resize the left panel — cards & pills reflow automatically")

        def _on_sash_enter(e):
            sash_grip.configure(fg_color="#38BDF8")

        def _on_sash_leave(e):
            if not getattr(self, "_sash_dragging", False):
                sash_grip.configure(fg_color="#2B303B")

        def _on_sash_press(e):
            self._sash_dragging = True
            self._sash_start_x = e.x_root
            self._sash_start_w = getattr(self, "_sidebar_width", 356)
            self._last_sash_ts = 0.0
            sash_grip.configure(fg_color="#38BDF8")

        def _on_sash_motion(e):
            if not getattr(self, "_sash_dragging", False):
                return
            now_t = time.perf_counter()
            if (now_t - getattr(self, "_last_sash_ts", 0.0)) < 0.015:
                return
            dx = e.x_root - getattr(self, "_sash_start_x", e.x_root)
            tot_w = max(800, self.results_frame.winfo_width())
            max_allowed = max(420, int(tot_w * 0.65))
            new_w = max(340, min(max_allowed, self._sash_start_w + dx))
            if abs(new_w - getattr(self, "_sidebar_width", 356)) >= 3:
                self._last_sash_ts = now_t
                self._apply_sidebar_width(new_w, is_dragging=True)

        def _on_sash_release(e):
            if getattr(self, "_sash_dragging", False):
                self._sash_dragging = False
                sash_grip.configure(fg_color="#2B303B")
                dx = e.x_root - getattr(self, "_sash_start_x", e.x_root)
                tot_w = max(800, self.results_frame.winfo_width())
                max_allowed = max(420, int(tot_w * 0.65))
                new_w = max(340, min(max_allowed, self._sash_start_w + dx))
                self._apply_sidebar_width(new_w, is_dragging=False)
                if hasattr(self, "vector_chart") and self.vector_chart and self.vector_chart.winfo_exists():
                    if getattr(self.vector_chart, "_resize_redraw_after_id", None) is not None:
                        try:
                            self.vector_chart.after_cancel(self.vector_chart._resize_redraw_after_id)
                        except Exception:
                            pass
                        self.vector_chart._resize_redraw_after_id = None
                    self.vector_chart.redraw()
                try:
                    self.config.settings["sidebar_width"] = int(self._sidebar_width)
                    self.config.save()
                except Exception:
                    pass

        for sw in (sash, sash_grip):
            sw.bind("<Enter>", _on_sash_enter)
            sw.bind("<Leave>", _on_sash_leave)
            sw.bind("<ButtonPress-1>", _on_sash_press)
            sw.bind("<B1-Motion>", _on_sash_motion)
            sw.bind("<ButtonRelease-1>", _on_sash_release)

        # Card 1: Airport & Assigned Stand Hero Card (Borderless)
        gate_card = ctk.CTkFrame(sidebar, fg_color="#1B1E24", corner_radius=12, border_width=0)
        gate_card.pack(fill="x", pady=(0, 10))
        self._sb_gate_card = gate_card

        lbl_wrap = max(320, self._sidebar_width - 20)
        self._sb_icao_title_lbl = ctk.CTkLabel(
            gate_card, text="---", font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#FFFFFF", wraplength=lbl_wrap, justify="center"
        )
        self._sb_icao_title_lbl.pack(fill="x", padx=10, pady=(16, 4))

        self._sb_city_lbl = ctk.CTkLabel(
            gate_card, text="", font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#CBD5E1", wraplength=lbl_wrap, justify="center"
        )
        self._sb_city_lbl.pack(fill="x", padx=10, pady=(0, 14))

        self._sb_err_container = ctk.CTkFrame(gate_card, fg_color="transparent", height=0, border_width=0)
        self._sb_err_lbl = ctk.CTkLabel(
            self._sb_err_container, text="", text_color="#EF4444",
            font=ctk.CTkFont(size=11, weight="bold"), wraplength=lbl_wrap, justify="center"
        )
        self._sb_err_lbl.pack(anchor="center", padx=14, pady=(0, 8))

        # Airline Camaïeu Hero Pill: Stand Number (s1)
        self._sb_gate_pill_lbl = ctk.CTkLabel(
            gate_card, text="   N/A   ",
            fg_color="#0A86C2", text_color="#FFFFFF", corner_radius=8,
            padx=26, pady=10, font=ctk.CTkFont(size=36, weight="bold"),
            cursor="hand2"
        )
        self._sb_gate_pill_lbl.pack(anchor="center", pady=(4, 18))
        self._sb_gate_pill_lbl.bind("<Button-1>", lambda e: self._open_manual_stand_picker_modal())
        Tooltip(self._sb_gate_pill_lbl, "Click to manually select another stand (or click any stand directly on the chart)")

        # 2x2 Grid under the Gate Pill for the sub-pills
        self._sb_pills_grid = ctk.CTkFrame(gate_card, fg_color="transparent", border_width=0)
        self._sb_pills_grid.pack(fill="x", padx=12, pady=(0, 14))
        self._sb_pills_grid.grid_columnconfigure(0, weight=1, uniform="c1_pills")
        self._sb_pills_grid.grid_columnconfigure(1, weight=1, uniform="c1_pills")

        # Grid Cell (0, 0): Boarding Type Pill (s2)
        self._sb_boarding_pill = ctk.CTkFrame(
            self._sb_pills_grid, fg_color="#0A6E9E", corner_radius=8,
            border_width=0, height=30
        )
        self._sb_boarding_pill.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 6))
        self._sb_boarding_pill.pack_propagate(False)
        self._sb_boarding_lbl = ctk.CTkLabel(
            self._sb_boarding_pill, text="Jetway boarding",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#FFFFFF"
        )
        self._sb_boarding_lbl.pack(expand=True, fill="both", padx=6)
        self._sb_boarding_tip = Tooltip(self._sb_boarding_pill, "")
        self._sb_boarding_tip.bind_child(self._sb_boarding_lbl)

        # Grid Cell (0, 1): Max Wingspan Pill (s3) + Tooltip for clearance/tight-fit details
        self._sb_wingspan_pill = ctk.CTkFrame(
            self._sb_pills_grid, fg_color="#0D587D", corner_radius=8,
            border_width=0, height=30
        )
        self._sb_wingspan_pill.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6))
        self._sb_wingspan_pill.pack_propagate(False)
        self._sb_wingspan_lbl = ctk.CTkLabel(
            self._sb_wingspan_pill, text="Max Wingspan: 36.0m",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#FFFFFF"
        )
        self._sb_wingspan_lbl.pack(expand=True, fill="both", padx=6)
        self._sb_wingspan_tip = Tooltip(self._sb_wingspan_pill, "")
        self._sb_wingspan_tip.bind_child(self._sb_wingspan_lbl)

        # Grid Cell (1, 0): Source Pill (s4) + Tooltip explaining source
        self._sb_source_pill = ctk.CTkFrame(
            self._sb_pills_grid, fg_color="#0D435E", corner_radius=8,
            border_width=0, height=30
        )
        self._sb_source_pill.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(0, 0))
        self._sb_source_pill.pack_propagate(False)
        self._sb_source_lbl = ctk.CTkLabel(
            self._sb_source_pill, text="GateFinder",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#FFFFFF"
        )
        self._sb_source_lbl.pack(expand=True, fill="both", padx=6)
        self._sb_source_tip = Tooltip(self._sb_source_pill, "")
        self._sb_source_tip.bind_child(self._sb_source_lbl)

        # Grid Cell (1, 1): 4th slot of the 2x2 grid -> GSX Pro Pill on Arrival (or empty spacer on Departure)
        self._sb_empty_pill_slot = ctk.CTkFrame(
            self._sb_pills_grid, fg_color="transparent", corner_radius=8,
            border_width=0, height=30
        )
        self._sb_empty_pill_slot.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(0, 0))

        def _on_manual_gsx_sync(event=None):
            if hasattr(self, "backend") and self.backend and hasattr(self.backend, "interop_hub") and self.backend.interop_hub:
                self.backend.interop_hub.trigger_manual_gsx_sync("arrival")
                self._check_and_show_gate_toast()

        self._sb_gsx_pill = ctk.CTkFrame(
            self._sb_pills_grid, fg_color="#0D435E", corner_radius=8,
            border_width=0, height=30, cursor="hand2"
        )
        self._sb_gsx_pill.pack_propagate(False)
        self._sb_gsx_lbl = ctk.CTkLabel(
            self._sb_gsx_pill, text="GSX Pro: Armed",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#FFFFFF", cursor="hand2"
        )
        self._sb_gsx_lbl.pack(expand=True, fill="both", padx=6)
        self._sb_gsx_pill.bind("<Button-1>", _on_manual_gsx_sync)
        self._sb_gsx_lbl.bind("<Button-1>", _on_manual_gsx_sync)
        self._sb_gsx_tip = Tooltip(self._sb_gsx_pill, "Click to manually sync GSX Pro with the arrival stand")
        self._sb_gsx_tip.bind_child(self._sb_gsx_lbl)

        # Card 2: ATC Taxi Clearance & Flight Status Card (Borderless, hugs content height)
        route_card = ctk.CTkFrame(sidebar, fg_color="#1B1E24", corner_radius=12, border_width=0)
        route_card.pack(fill="x", expand=False, pady=(0, 10))
        self._sb_route_card = route_card

        self.lbl_live_status_pill = ctk.CTkLabel(
            route_card, text="OPTIMAL TAXI ROUTE READY",
            fg_color="#2B303B", text_color="#FFFFFF", corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"), pady=6
        )
        self.lbl_live_status_pill.pack(fill="x", padx=14, pady=(12, 6))

        self._sb_clearance_hdr_lbl = ctk.CTkLabel(
            route_card, text="ATC TAXI CLEARANCE",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#FFFFFF"
        )
        self._sb_clearance_hdr_lbl.pack(anchor="w", padx=14, pady=(12, 8))

        self.clearance_pills_frame = ctk.CTkFrame(route_card, fg_color="transparent", border_width=0)
        self.clearance_pills_frame.pack(fill="x", expand=False, padx=14, pady=(0, 12))

        # Card 3: Network Traffic & Stand Status Card (Expands to fill remaining sidebar height + internal vertical scrollbar)
        status_card = ctk.CTkFrame(sidebar, fg_color="#1B1E24", corner_radius=12, border_width=0)
        status_card.pack(fill="both", expand=True, pady=(0, 0))
        self._sb_status_card = status_card

        self._sb_traffic_hdr_lbl = ctk.CTkLabel(
            status_card, text="TRAFFIC & STAND STATUS",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#FFFFFF"
        )
        self._sb_traffic_hdr_lbl.pack(anchor="w", padx=14, pady=(12, 6))

        self.traffic_pills_frame = ctk.CTkScrollableFrame(
            status_card,
            fg_color="transparent",
            border_width=0,
            corner_radius=0,
            scrollbar_button_color="#2B303B",
            scrollbar_button_hover_color="#578DA8"
        )
        self.traffic_pills_frame.pack(fill="both", expand=True, padx=(10, 4), pady=(0, 10))

    def _apply_sidebar_width(self, new_w: int, is_dragging: bool = False):
        self._sidebar_width = int(new_w)
        if hasattr(self, "results_frame") and self.results_frame and self.results_frame.winfo_exists():
            self.results_frame.grid_columnconfigure(0, weight=0, minsize=self._sidebar_width + 10)
        if hasattr(self, "_sidebar_outer") and self._sidebar_outer and self._sidebar_outer.winfo_exists():
            self._sidebar_outer.configure(width=self._sidebar_width + 10)
        if hasattr(self, "sidebar_frame") and self.sidebar_frame and self.sidebar_frame.winfo_exists():
            self.sidebar_frame.configure(width=self._sidebar_width)
        lbl_wrap = max(320, self._sidebar_width - 20)
        if not is_dragging or abs(lbl_wrap - getattr(self, "_last_lbl_wrap", 0)) >= 24:
            self._last_lbl_wrap = lbl_wrap
            for lbl_attr in ("_sb_icao_title_lbl", "_sb_city_lbl", "_sb_err_lbl"):
                w_lbl = getattr(self, lbl_attr, None)
                if w_lbl and w_lbl.winfo_exists():
                    w_lbl.configure(wraplength=lbl_wrap)
        if hasattr(self, "_last_clearance_args") and self._last_clearance_args:
            c_str, c_cam, c_rwy, c_exit = self._last_clearance_args
            self._render_clearance_pills(c_str, cam=c_cam, sel_rwy=c_rwy, det_exit=c_exit)
        if hasattr(self, "_last_traffic_args") and self._last_traffic_args:
            t_str, t_cam = self._last_traffic_args
            self._render_traffic_pills(t_str, cam=t_cam)

    def _render_clearance_pills(self, clearance_str, cam=None, sel_rwy="", det_exit=""):
        if not hasattr(self, "clearance_pills_frame") or not self.clearance_pills_frame or not self.clearance_pills_frame.winfo_exists():
            return
        if cam is None:
            cam = self._get_active_camaieu()
        raw_parts = [p.strip() for p in re.split(r'\s*(?:->|➔)\s*', str(clearance_str or "")) if p.strip()]
        tokens = []
        for p in raw_parts:
            p_norm = re.sub(r'^(?:STAND|GATE|PARKING|RAMP|DOCK)\s*', '', p.upper()).replace(" ", "")
            if tokens:
                prev_norm = re.sub(r'^(?:STAND|GATE|PARKING|RAMP|DOCK)\s*', '', tokens[-1].upper()).replace(" ", "")
                if p_norm and p_norm == prev_norm:
                    if len(p) > len(tokens[-1]):
                        tokens[-1] = p
                    continue
            tokens.append(p)
        if not tokens:
            tokens = [str(clearance_str or "ROUTE READY").strip()]

        sel_rwy_clean = re.sub(r'^RWY\s*', '', str(sel_rwy or "").strip(), flags=re.IGNORECASE).upper()
        det_exit_clean = str(det_exit or "").strip()

        # Transform tokens into structured items: (kind, label_text, tooltip_text)
        # where kind is "RWY_DROPDOWN", "EXIT_PILL", or "NORMAL"
        pill_items = []
        has_rwy_dropdown = False
        has_exit_pill = False

        for idx_t, tok in enumerate(tokens):
            # 1. Arrival combined "RWY 02 (Exit W5)" -> split into ("RWY 02  ▾") + ("EXIT : W5")
            m_rwy_exit = re.match(r'^RWY\s+([0-9]{1,2}[LRC]?)\s*\(\s*Exit\s+([^)]+)\s*\)$', tok, flags=re.IGNORECASE)
            if m_rwy_exit:
                r_id = m_rwy_exit.group(1).upper()
                ex_id = m_rwy_exit.group(2).strip()
                pill_items.append((
                    "RWY_DROPDOWN",
                    f"RWY {r_id}  ▾",
                    f"Landing Runway RWY {r_id} - Click to select another runway"
                ))
                has_rwy_dropdown = True
                if ex_id:
                    pill_items.append((
                        "EXIT_PILL",
                        f"EXIT : {ex_id}",
                        f"Planned/detected runway turnoff exit: {ex_id}"
                    ))
                    has_exit_pill = True
                continue

            # 2. Arrival live states: "Next Exit W5", "Exit W5", "Vacated RWY 02"
            m_live_exit = re.match(r'^(?:Next\s+)?Exit\s+(.+)$', tok, flags=re.IGNORECASE)
            if m_live_exit and self.active_phase == "arrival":
                ex_id = m_live_exit.group(1).strip()
                r_id = sel_rwy_clean or "--"
                if not has_rwy_dropdown:
                    pill_items.append((
                        "RWY_DROPDOWN",
                        f"RWY {r_id}  ▾",
                        f"Landing Runway RWY {r_id} - Click to select another runway"
                    ))
                    has_rwy_dropdown = True
                if ex_id and not has_exit_pill:
                    pill_items.append((
                        "EXIT_PILL",
                        f"EXIT : {ex_id}",
                        f"Runway turnoff exit: {ex_id}"
                    ))
                    has_exit_pill = True
                continue

            m_vac_rwy = re.match(r'^Vacated\s+RWY\s+([0-9]{1,2}[LRC]?)$', tok, flags=re.IGNORECASE)
            if m_vac_rwy:
                r_id = m_vac_rwy.group(1).upper()
                pill_items.append((
                    "RWY_DROPDOWN",
                    f"RWY {r_id}  ▾",
                    f"Vacated Runway RWY {r_id} - Click to select another runway"
                ))
                has_rwy_dropdown = True
                if det_exit_clean and not has_exit_pill and self.active_phase == "arrival":
                    pill_items.append((
                        "EXIT_PILL",
                        f"EXIT : {det_exit_clean}",
                        f"Runway turnoff exit: {det_exit_clean}"
                    ))
                    has_exit_pill = True
                continue

            # 3. Departure "Hold D (RWY 20)" or "Hold Short RWY 20"
            m_hold_named = re.match(r'^Hold\s+(.+?)\s*\(\s*RWY\s+([0-9]{1,2}[LRC]?)\s*\)$', tok, flags=re.IGNORECASE)
            if m_hold_named:
                h_name = m_hold_named.group(1).strip()
                r_id = m_hold_named.group(2).upper()
                if h_name and h_name.upper() != "SHORT":
                    if not pill_items or pill_items[-1][1].upper() != h_name.upper():
                        pill_items.append(("NORMAL", h_name, f"Holding point {h_name}"))
                pill_items.append((
                    "RWY_DROPDOWN",
                    f"RWY {r_id}  ▾",
                    f"Hold Short {h_name} (RWY {r_id}) - Click to select another runway"
                ))
                has_rwy_dropdown = True
                continue

            m_hold_short = re.match(r'^Hold\s+Short\s+RWY\s+([0-9]{1,2}[LRC]?)$', tok, flags=re.IGNORECASE)
            if m_hold_short:
                r_id = m_hold_short.group(1).upper()
                pill_items.append((
                    "RWY_DROPDOWN",
                    f"RWY {r_id}  ▾",
                    f"Hold Short RWY {r_id} - Click to select another runway"
                ))
                has_rwy_dropdown = True
                continue

            # 4. Departure "RWY 20 Entered"
            m_rwy_entered = re.match(r'^RWY\s+([0-9]{1,2}[LRC]?)\s+Entered$', tok, flags=re.IGNORECASE)
            if m_rwy_entered:
                r_id = m_rwy_entered.group(1).upper()
                pill_items.append((
                    "RWY_DROPDOWN",
                    f"RWY {r_id}  ▾",
                    f"Active Runway RWY {r_id} - Click to select another runway"
                ))
                has_rwy_dropdown = True
                pill_items.append(("NORMAL", "Entered", None))
                continue

            # 5. Plain "RWY 20" / "RWY 02"
            m_plain_rwy = re.match(r'^RWY\s+([0-9]{1,2}[LRC]?|--)$', tok, flags=re.IGNORECASE)
            if m_plain_rwy:
                r_id = m_plain_rwy.group(1).upper()
                if r_id == "--" and sel_rwy_clean:
                    r_id = sel_rwy_clean
                pill_items.append((
                    "RWY_DROPDOWN",
                    f"RWY {r_id}  ▾",
                    f"Runway RWY {r_id} - Click to select another runway"
                ))
                has_rwy_dropdown = True
                if self.active_phase == "arrival" and det_exit_clean and not has_exit_pill:
                    pill_items.append((
                        "EXIT_PILL",
                        f"EXIT : {det_exit_clean}",
                        f"Planned/detected runway turnoff exit: {det_exit_clean}"
                    ))
                    has_exit_pill = True
                continue

            pill_items.append(("NORMAL", tok, None))

        if not has_rwy_dropdown and sel_rwy_clean:
            rwy_item = (
                "RWY_DROPDOWN",
                f"RWY {sel_rwy_clean}  ▾",
                f"Runway RWY {sel_rwy_clean} - Click to select another runway"
            )
            if self.active_phase == "arrival":
                ins = [rwy_item]
                if det_exit_clean and not has_exit_pill:
                    ins.append((
                        "EXIT_PILL",
                        f"EXIT : {det_exit_clean}",
                        f"Planned/detected runway turnoff exit: {det_exit_clean}"
                    ))
                pill_items = ins + pill_items
            else:
                pill_items.append(rwy_item)

        self._last_clearance_args = (clearance_str, cam, sel_rwy, det_exit)
        sb_w = int(getattr(self, "_sidebar_width", 356) or 356)
        max_row_w = max(295, sb_w - 34)

        pool = (
            cam["s1"],
            cam["s2"],
            cam["s3"],
            cam["s4"],
            cam.get("s5", cam["s2"]),
            cam.get("s6", cam["s3"]),
        )
        # Pre-calculate how pills wrap into rows so dragging the splitter only rebuilds
        # when a pill actually crosses a row boundary (zero widget churn during smooth drag!)
        rows_plan = []
        cur_plan_row = []
        cur_w = 0
        for idx, (kind, tok, tip_txt) in enumerate(pill_items):
            est_w = max(56, len(tok) * 9.5 + 34)
            if cur_plan_row and (cur_w + est_w > max_row_w):
                rows_plan.append(cur_plan_row)
                cur_plan_row = []
                cur_w = 0
            cur_plan_row.append((idx, kind, tok, tip_txt))
            cur_w += est_w + 7
        if cur_plan_row:
            rows_plan.append(cur_plan_row)

        plan_sig = tuple(tuple((kind, tok) for _, kind, tok, _ in r) for r in rows_plan)
        sig = (plan_sig, pool, self.active_phase)
        if getattr(self, "_last_clearance_val", None) == sig and len(self.clearance_pills_frame.winfo_children()) > 0:
            return
        self._last_clearance_val = sig

        self._close_clearance_rwy_dropdown()
        for w in self.clearance_pills_frame.winfo_children():
            w.destroy()

        for plan_row in rows_plan:
            cur_row = ctk.CTkFrame(self.clearance_pills_frame, fg_color="transparent", border_width=0)
            cur_row.pack(anchor="w", pady=(0, 8))
            for idx, kind, tok, tip_txt in plan_row:
                pill_bg = pool[idx % len(pool)]
                if kind == "RWY_DROPDOWN":
                    p_frame = ctk.CTkFrame(cur_row, fg_color=pill_bg, corner_radius=8, border_width=0, cursor="hand2")
                    p_frame.pack(side="left", padx=(0, 7))
                    lbl_p = ctk.CTkLabel(
                        p_frame,
                        text=tok,
                        width=54,
                        height=38,
                        fg_color="transparent",
                        text_color="#FFFFFF",
                        font=ctk.CTkFont(size=14, weight="bold"),
                        padx=16,
                        pady=8,
                        cursor="hand2"
                    )
                    lbl_p.pack()
                    self._clearance_rwy_pill_widget = p_frame
                    for cw in (p_frame, lbl_p):
                        cw.bind("<Button-1>", self._open_clearance_rwy_dropdown)
                    if tip_txt:
                        t_obj = Tooltip(p_frame, tip_txt)
                        t_obj.bind_child(lbl_p)
                        self._clearance_rwy_tooltip = t_obj
                else:
                    is_stand_pill = bool(re.match(r'^(?:STAND|GATE|PARKING|RAMP|DOCK)\b', str(tok or ""), flags=re.IGNORECASE))
                    lbl_p = ctk.CTkLabel(
                        cur_row,
                        text=tok,
                        width=52,
                        height=38,
                        fg_color=pill_bg,
                        text_color="#FFFFFF",
                        corner_radius=8,
                        font=ctk.CTkFont(size=14, weight="bold"),
                        padx=16,
                        pady=8,
                        cursor="hand2" if is_stand_pill else ""
                    )
                    lbl_p.pack(side="left", padx=(0, 7))
                    if is_stand_pill:
                        lbl_p.bind("<Button-1>", lambda e: self._open_manual_stand_picker_modal())
                        Tooltip(lbl_p, f"{tok} - Click to open Terminal/Gate Selector")
                    elif tip_txt:
                        Tooltip(lbl_p, tip_txt)

    def _render_traffic_pills(self, traffic_str, cam=None):
        if not hasattr(self, "traffic_pills_frame") or not self.traffic_pills_frame or not self.traffic_pills_frame.winfo_exists():
            return
        if cam is None:
            cam = self._get_active_camaieu()

        self._last_traffic_args = (traffic_str, cam)

        s = str(traffic_str or "VATSIM / IVAO: Stand clear of online traffic").strip()
        tokens = []
        is_occupied_list = False
        if s.upper().startswith("OCCUPIED") and ":" in s:
            is_occupied_list = True
            _, tail = s.split(":", 1)
            for part in tail.split(","):
                p_clean = part.strip()
                if p_clean:
                    tokens.append(p_clean)
            if not tokens:
                tokens = [s]
                is_occupied_list = False
        else:
            # Single pill when no stands are occupied
            tokens = [s]

        sb_w = int(getattr(self, "_sidebar_width", 356) or 356)
        avail_w = max(300, sb_w - 44)
        num_cols = max(3, avail_w // 100)

        pool = (
            cam["s1"],
            cam["s2"],
            cam["s3"],
            cam["s4"],
            cam.get("s5", cam["s2"]),
            cam.get("s6", cam["s3"]),
        )
        sig = (tuple(tokens), pool, num_cols, is_occupied_list)
        if getattr(self, "_last_traffic_pills_val", None) == sig and len(self.traffic_pills_frame.winfo_children()) > 0:
            return
        self._last_traffic_pills_val = sig

        content_sig = (tuple(tokens), pool, is_occupied_list)
        existing_widgets = getattr(self, "_traffic_pill_widgets", None) or []
        if (
            is_occupied_list
            and getattr(self, "_last_traffic_content_sig", None) == content_sig
            and len(existing_widgets) == len(tokens)
            and all(w.winfo_exists() for w in existing_widgets)
        ):
            # Fast in-place re-gridding during splitter drag: zero widget destruction/recreation!
            for c_idx in range(8):
                if c_idx < num_cols:
                    self.traffic_pills_frame.grid_columnconfigure(c_idx, weight=1, uniform="traf_col")
                else:
                    self.traffic_pills_frame.grid_columnconfigure(c_idx, weight=0, uniform="")
            for idx, lbl_p in enumerate(existing_widgets):
                lbl_p.grid(row=idx // num_cols, column=idx % num_cols, sticky="ew", padx=3, pady=3)
            return

        self._last_traffic_content_sig = content_sig
        self._traffic_pill_widgets = []
        for w in self.traffic_pills_frame.winfo_children():
            w.destroy()

        def _scroll_traffic_wheel(event):
            try:
                if hasattr(self.traffic_pills_frame, "_parent_canvas"):
                    self.traffic_pills_frame._parent_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass
            return "break"

        if not is_occupied_list and len(tokens) == 1:
            for c_idx in range(max(3, num_cols)):
                self.traffic_pills_frame.grid_columnconfigure(c_idx, weight=0, uniform="")
            self.traffic_pills_frame.grid_columnconfigure(0, weight=1)
            lbl_p = ctk.CTkLabel(
                self.traffic_pills_frame,
                text=tokens[0],
                fg_color=pool[0],
                text_color="#FFFFFF",
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
                padx=12,
                pady=6
            )
            lbl_p.grid(row=0, column=0, sticky="w", padx=2, pady=2)
            lbl_p.bind("<MouseWheel>", _scroll_traffic_wheel)
            self._traffic_pill_widgets.append(lbl_p)
            return

        # Equal-width multi-column grid (at least 3 columns wide, expanding to 4, 5, 6+ as sidebar widens)
        for c_idx in range(8):
            if c_idx < num_cols:
                self.traffic_pills_frame.grid_columnconfigure(c_idx, weight=1, uniform="traf_col")
            else:
                self.traffic_pills_frame.grid_columnconfigure(c_idx, weight=0, uniform="")

        for idx, tok in enumerate(tokens):
            r_idx = idx // num_cols
            c_idx = idx % num_cols
            pill_bg = pool[idx % len(pool)]
            lbl_p = ctk.CTkLabel(
                self.traffic_pills_frame,
                text=tok,
                height=28,
                fg_color=pill_bg,
                text_color="#FFFFFF",
                corner_radius=7,
                font=ctk.CTkFont(size=11, weight="bold"),
                padx=4,
                pady=2
            )
            lbl_p.grid(row=r_idx, column=c_idx, sticky="ew", padx=3, pady=3)
            lbl_p.bind("<MouseWheel>", _scroll_traffic_wheel)
            self._traffic_pill_widgets.append(lbl_p)

    def _update_sidebar_in_place(self, airport_data, result):
        self._ensure_sidebar_built()
        cam = self._get_active_camaieu(result)

        card_bg = "#1B1E24"
        if hasattr(self, "_sb_gate_card") and self._sb_gate_card:
            self._sb_gate_card.configure(fg_color=card_bg)
        if hasattr(self, "_sb_route_card") and self._sb_route_card:
            self._sb_route_card.configure(fg_color=card_bg)
        if hasattr(self, "_sb_status_card") and self._sb_status_card:
            self._sb_status_card.configure(fg_color=card_bg)

        term_str = _clean_terminal_label(airport_data.get("terminal") or "MAIN APRON").upper()

        icao_code = str(airport_data.get('icao') or '').strip()
        raw_apt_name = str(airport_data.get('name') or '').strip()
        if hasattr(self, "backend") and self.backend and hasattr(self.backend, "get_airport_display_name"):
            apt_name = self.backend.get_airport_display_name(icao_code, raw_apt_name)
        else:
            apt_name = raw_apt_name
        icao_title = f"{icao_code} - {apt_name}" if apt_name else icao_code
        self._sb_icao_title_lbl.configure(text=icao_title)

        city_str = str(airport_data.get("city") or "").strip()
        if not city_str and hasattr(self, "backend") and self.backend and icao_code:
            city_str = self.backend.get_airport_city(icao_code, lat=airport_data.get("lat"), lon=airport_data.get("lon"))
        if city_str:
            self._sb_city_lbl.configure(text=city_str)
            self._sb_city_lbl.pack(fill="x", padx=10, pady=(0, 14), after=self._sb_icao_title_lbl)
        else:
            self._sb_city_lbl.pack_forget()

        if airport_data.get("error") and not airport_data.get("osm"):
            self._sb_err_lbl.configure(text=airport_data["error"], text_color="#EF4444")
            self._sb_err_container.pack(fill="x", before=self._sb_gate_pill_lbl)
        else:
            self._sb_err_container.pack_forget()

        gate_val = airport_data.get("gate") or "N/A"
        if airport_data.get("osm") and gate_val != "N/A":
            gate_val = f"Stand {gate_val}"
        self._sb_gate_pill_lbl.configure(text=f"   {gate_val}   ", fg_color=cam["s1"], text_color="#FFFFFF")

        has_jetway = airport_data.get("has_jetway")
        if has_jetway is None:
            has_jetway = (airport_data.get("type", "GATE") in ("GATE", "DOCK"))
        is_cargo_disp = "CARGO" in term_str or airport_data.get("is_cargo")
        boarding_text = "Cargo Jetway/Ramp" if (is_cargo_disp and has_jetway) else (
            "Cargo Ramp" if is_cargo_disp else ("Jetway boarding" if has_jetway else "Walk/Bus boarding")
        )
        self._sb_boarding_pill.configure(fg_color=cam["s2"])
        self._sb_boarding_lbl.configure(text=boarding_text, text_color="#FFFFFF")
        self._sb_boarding_tip.text = f"{boarding_text}  {term_str}"

        if self.config.settings.get("show_wingspan", True):
            gate_ws = airport_data.get("max_wingspan", 999.0)
            ac_ws = result.get("aircraft_wingspan", 36.0)
            if gate_ws < 900.0:
                margin = gate_ws - ac_ws
                fit_txt = f"Max Wingspan: {gate_ws:.1f}m"
                fit_tip = f"{'Tight fit' if margin < 3.0 else 'Clearance'}: +{margin:.1f}m margin (Stand max wingspan: {gate_ws:.1f}m vs Aircraft wingspan: {ac_ws:.1f}m)"
            else:
                fit_txt = "Wingspan: Unlimited"
                fit_tip = f"No wingspan restriction on this stand (Aircraft wingspan: {ac_ws:.1f}m)"
            self._sb_wingspan_pill.configure(fg_color=cam["s3"])
            self._sb_wingspan_lbl.configure(text=fit_txt, text_color="#FFFFFF")
            self._sb_wingspan_tip.text = fit_tip
            self._sb_wingspan_pill.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6))
        else:
            self._sb_wingspan_pill.grid_remove()

        raw_gate_src = str(airport_data.get("gate_source") or "GateFinder").strip()
        raw_rwy_src = str(airport_data.get("atc_runway_source") or airport_data.get("runway_source") or "").strip()
        src_u = raw_gate_src.upper()
        rwy_src_u = raw_rwy_src.upper()
        if "MANUAL" in src_u:
            clean_src = "Manual Selection"
            src_tip = "Manual Selection: Stand manually chosen by you on the ground chart or stand list."
        elif "BEYOND" in src_u or "BEYOND" in rwy_src_u:
            clean_src = "BeyondATC"
            src_tip = "BeyondATC: Active clearance / stand synchronized with BeyondATC."
        elif "SAYINTENTIONS" in src_u or "SAYINTENTIONS" in rwy_src_u:
            clean_src = "SayIntentions.AI"
            src_tip = "SayIntentions.AI: Active clearance / stand synchronized with SayIntentions.AI."
        elif "REASSIGNED" in src_u:
            clean_src = "VATSIM / IVAO"
            src_tip = "VATSIM / IVAO: Stand dynamically reassigned to avoid online traffic conflict."
        else:
            clean_src = "GateFinder"
            if "TURNAROUND" in src_u:
                src_tip = "GateFinder (Turnaround Stand): Stand automatically kept from your previous arrival or parked position for a seamless turnaround."
            else:
                src_tip = "GateFinder: Stand and routing managed by GateFinder's smart dispatch engine."
        self._sb_source_pill.configure(fg_color=cam["s4"])
        self._sb_source_lbl.configure(text=clean_src, text_color="#FFFFFF")
        self._sb_source_tip.text = src_tip

        gsx_st = airport_data.get("gsx_status") or {}
        if self.active_phase == "arrival" and gsx_st.get("visible", True):
            short_gsx, tip_gsx = self._format_gsx_pill_info(gsx_st, airport_data.get("gate", ""))
            self._sb_gsx_pill.configure(fg_color=cam.get("s5", cam["s2"]))
            self._sb_gsx_lbl.configure(text=short_gsx, text_color="#FFFFFF")
            self._sb_gsx_tip.text = tip_gsx
            self._sb_gsx_pill.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(0, 0))
        else:
            self._sb_gsx_pill.grid_remove()

        sel_rwy = airport_data.get("selected_runway") or "RWY"
        tr = airport_data.get("taxi_route") or {}
        live_status = tr.get("live_status", "PLANNED")
        det_exit = tr.get("detected_exit")
        status_map = {
            "PARKED": ("PARKED AT GATE  -  READY FOR TAXI", "#FFFFFF"),
            "TAXI_OUT": ("LIVE TAXIING TO RUNWAY", "#FFFFFF"),
            "ON_RUNWAY": ("ON RUNWAY  -  MONITORING STOPPED", "#FFFFFF"),
            "LANDING_ROLL": (f"LANDING ROLL  -  EXIT: {det_exit or 'AUTO'}", "#FFFFFF"),
            "TAXI_IN": (f"VACATED VIA {det_exit or 'TWY'}  -  TAXI TO STAND", "#FFFFFF"),
            "ARRIVED_AT_GATE": ("ARRIVED AT STAND  -  BLOCKS ON", "#FFFFFF"),
            "PLANNED": ("" if self.active_phase == "arrival" else "OPTIMAL TAXI ROUTE READY", "#FFFFFF")
        }
        st_text, st_col = status_map.get(live_status, ("", "#FFFFFF"))
        self._last_st_pill_val = (st_text, "#FFFFFF")
        if st_text:
            self.lbl_live_status_pill.configure(text=st_text, text_color="#FFFFFF", fg_color="#2B303B")
            if not self.lbl_live_status_pill.winfo_ismapped():
                self.lbl_live_status_pill.pack(fill="x", padx=14, pady=(12, 6), before=self._sb_clearance_hdr_lbl)
        else:
            if self.lbl_live_status_pill.winfo_ismapped():
                self.lbl_live_status_pill.pack_forget()

        clearance_str = (tr.get("clearance_text") or f"Stand {gate_val} -> RWY {sel_rwy}").replace("➔", "->")
        self._render_clearance_pills(clearance_str, cam=cam, sel_rwy=sel_rwy, det_exit=det_exit)

        if self.config.settings.get("check_online_traffic", True) and airport_data.get("bypassed_summary"):
            traffic_str = airport_data["bypassed_summary"]
        else:
            traffic_str = "VATSIM / IVAO: Stand clear of online traffic"
        self._render_traffic_pills(traffic_str, cam=cam)

        if airport_data.get("ai_cleared"):
            ai_txt = "AI Aircraft Cleared from Stand"
        elif airport_data.get("ai_active"):
            ai_txt = "Gate Secured (Auto-Clear Active)"
        elif airport_data.get("simconnect_connected"):
            ai_txt = "SimConnect Connected (Stand Monitored)"
        else:
            ai_txt = "SimConnect Standby"
        self._current_simconnect_status_txt = ai_txt
        if hasattr(self, "vector_chart") and self.vector_chart and self.vector_chart.winfo_exists():
            self.vector_chart.set_simconnect_status(ai_txt)

    def render_results(self, result, preserve_camera=False):
        # 1. Update Top Header SimBrief OFP Strip in-place with active Airline Camaïeu
        cam = self._get_active_camaieu(result)
        self.header_frame.configure(fg_color="#1B1E24")
        self.btn_import.configure(fg_color=cam.get("s5", cam["s2"]), hover_color=cam.get("s6", cam["s4"]), text_color="#FFFFFF")

        raw_al_str = str(result.get("airline") or "AIRLINE").strip()
        al_code_hdr = raw_al_str.split("-")[0].strip().upper() if "-" in raw_al_str else raw_al_str.strip().upper()[:3]
        al_str = f"   {raw_al_str}   "

        callsign_raw = str(result.get("callsign") or "").strip()
        cs_str = f"  {callsign_raw}  " if callsign_raw else ""

        reg_raw = str(result.get("registration") or "").strip()
        reg_str = f"  {reg_raw}  " if reg_raw else ""

        ac_ver_raw = str(result.get("aircraft_version") or result.get("aircraft") or "AIRCRAFT").strip()
        ac_str = f"  {ac_ver_raw}  "

        logo_gen = getattr(self.backend, "logo_generation", 0) if hasattr(self, "backend") else 0
        ctk_al_logo = None
        if hasattr(self, "backend") and self.backend and al_code_hdr and al_code_hdr != "AIR":
            try:
                pil_al = self.backend.get_airline_pill_pil_image(al_code_hdr, size=46, allow_network=False, width=106, corner_radius=8)
                if pil_al is not None:
                    ctk_al_logo = ctk.CTkImage(light_image=pil_al, dark_image=pil_al, size=(106, 46))
            except Exception:
                ctk_al_logo = None

        strip_sig = (al_str, cs_str, reg_str, ac_str, logo_gen, cam["s1"], cam["s2"], cam["s3"], cam["s4"])
        if not hasattr(self, "_lbl_strip_al") or not self._lbl_strip_al or not self._lbl_strip_al.winfo_exists():
            for w in self.flight_strip_frame.winfo_children():
                w.destroy()
            self._lbl_strip_logo = ctk.CTkLabel(
                self.flight_strip_frame, text="",
                image=ctk_al_logo, fg_color="transparent", height=46
            )
            if ctk_al_logo is not None:
                self._lbl_strip_logo.pack(side="left", padx=(0, 8))

            self._lbl_strip_al = ctk.CTkLabel(
                self.flight_strip_frame, text=al_str,
                height=46, fg_color=cam["s1"], text_color="#FFFFFF", corner_radius=8,
                font=ctk.CTkFont(size=15, weight="bold"), padx=18, pady=6
            )
            self._lbl_strip_al.pack(side="left", padx=(0, 8))

            self._lbl_strip_cs = ctk.CTkLabel(
                self.flight_strip_frame, text=cs_str, height=46,
                fg_color=cam["s2"], text_color="#FFFFFF", corner_radius=8,
                font=ctk.CTkFont(size=14, weight="bold"), padx=14, pady=6
            )
            if cs_str:
                self._lbl_strip_cs.pack(side="left", padx=(0, 8))

            self._lbl_strip_reg = ctk.CTkLabel(
                self.flight_strip_frame, text=reg_str, height=46,
                fg_color=cam["s3"], text_color="#FFFFFF", corner_radius=8,
                font=ctk.CTkFont(size=14, weight="bold"), padx=14, pady=6
            )
            if reg_str:
                self._lbl_strip_reg.pack(side="left", padx=(0, 8))

            self._lbl_strip_ac = ctk.CTkLabel(
                self.flight_strip_frame, text=ac_str, height=46,
                fg_color=cam["s4"], text_color="#FFFFFF", corner_radius=8,
                font=ctk.CTkFont(size=14, weight="bold"), padx=14, pady=6
            )
            self._lbl_strip_ac.pack(side="left")
            self._last_strip_vals = strip_sig
        elif getattr(self, "_last_strip_vals", None) != strip_sig:
            self._last_strip_vals = strip_sig
            if hasattr(self, "_lbl_strip_logo") and self._lbl_strip_logo and self._lbl_strip_logo.winfo_exists():
                self._lbl_strip_logo.configure(image=ctk_al_logo)
                if ctk_al_logo is not None:
                    self._lbl_strip_logo.pack(side="left", padx=(0, 8), before=self._lbl_strip_al)
                else:
                    self._lbl_strip_logo.pack_forget()
            self._lbl_strip_al.configure(text=al_str, fg_color=cam["s1"], text_color="#FFFFFF")
            self._lbl_strip_cs.configure(text=cs_str, fg_color=cam["s2"], text_color="#FFFFFF")
            if cs_str:
                self._lbl_strip_cs.pack(side="left", padx=(0, 8), before=self._lbl_strip_reg if reg_str else self._lbl_strip_ac)
            else:
                self._lbl_strip_cs.pack_forget()
            self._lbl_strip_reg.configure(text=reg_str, fg_color=cam["s3"], text_color="#FFFFFF")
            if reg_str:
                self._lbl_strip_reg.pack(side="left", padx=(0, 8), before=self._lbl_strip_ac)
            else:
                self._lbl_strip_reg.pack_forget()
            self._lbl_strip_ac.configure(text=ac_str, fg_color=cam["s4"], text_color="#FFFFFF")

        # 2. Update BeyondATC-style Phase Switcher Cards (DEPARTURE vs ARRIVAL) with Airline Camaïeu
        dep = result.get("departure") or {}
        arr = result.get("arrival") or {}

        dep_icao_txt = str(dep.get("icao") or "----").strip().upper()
        dep_gate_txt = f"STAND {dep.get('gate')}" if dep.get("gate") else "NO STAND"
        dep_rwy_txt = f"RWY {dep.get('selected_runway')}" if dep.get("selected_runway") else "RWY --"

        arr_icao_txt = str(arr.get("icao") or "----").strip().upper()
        arr_gate_txt = f"STAND {arr.get('gate')}" if arr.get("gate") else "NO STAND"
        arr_rwy_txt = f"RWY {arr.get('selected_runway')}" if arr.get("selected_runway") else "RWY --"

        u_ac = result.get("user_aircraft")
        is_airborne = bool(result.get("is_airborne", False))
        if is_airborne and self.active_phase == "departure":
            self.active_phase = "arrival"

        tabs_state = (
            self.active_phase, is_airborne,
            dep_icao_txt, dep_gate_txt, dep_rwy_txt,
            arr_icao_txt, arr_gate_txt, arr_rwy_txt,
            cam["s1"], cam["s2"], cam["s3"], cam["s4"], cam.get("s5"), cam.get("s6"),
            cam.get("card_bg"), cam.get("card_sel_bg")
        )
        if getattr(self, "_last_tabs_state", None) != tabs_state:
            self._last_tabs_state = tabs_state
            if hasattr(self, "_phase_tab_widgets"):
                dw = self._phase_tab_widgets.get("departure")
                if dw:
                    dw["lbl_icao"].configure(text=dep_icao_txt, text_color="#FFFFFF")
                    dw["lbl_stand"].configure(text=dep_gate_txt, text_color="#FFFFFF")
                    dw["lbl_rwy"].configure(text=dep_rwy_txt, text_color="#FFFFFF")
                    dw["pill_icao"].configure(fg_color=cam["s1"])
                    dw["pill_stand"].configure(fg_color=cam["s2"])
                    dw["pill_rwy"].configure(fg_color=cam["s3"])
                aw = self._phase_tab_widgets.get("arrival")
                if aw:
                    aw["lbl_icao"].configure(text=arr_icao_txt, text_color="#FFFFFF")
                    aw["lbl_stand"].configure(text=arr_gate_txt, text_color="#FFFFFF")
                    aw["lbl_rwy"].configure(text=arr_rwy_txt, text_color="#FFFFFF")
                    aw["pill_icao"].configure(fg_color=cam["s4"])
                    aw["pill_stand"].configure(fg_color=cam.get("s5", cam["s2"]))
                    aw["pill_rwy"].configure(fg_color=cam.get("s6", cam["s3"]))
            self._apply_phase_tabs_visual_state()

        airport_data = dep if self.active_phase == "departure" else arr

        raw_map_hib = bool(result.get("map_hibernated", False))
        eff_map_hib = bool(raw_map_hib and not getattr(self, "_inflight_map_preview_override", False))
        show_maps_cfg = bool(self.config.settings.get("show_maps", True))

        # Keep sync loop signature up-to-date so check_sync_loop never double-renders 200ms after a click
        self._last_rendered_signature = (
            result.get("aircraft"), result.get("airline"),
            dep.get("icao"), dep.get("gate"), dep.get("gate_source"), dep.get("atc_runway_source"), dep.get("selected_runway"), dep.get("atc_runway"), tuple(dep.get("atc_taxi_via") or ()), dep.get("bypassed_summary"),
            arr.get("icao"), arr.get("gate"), arr.get("gate_source"), arr.get("atc_runway_source"), arr.get("selected_runway"), arr.get("atc_runway"), tuple(arr.get("atc_taxi_via") or ()), arr.get("bypassed_summary"),
            self.active_phase, eff_map_hib, show_maps_cfg, is_airborne
        )
        self._last_route_cam_key = (
            self.active_phase,
            airport_data.get("icao"),
            airport_data.get("gate"),
            airport_data.get("selected_runway"),
            tuple(airport_data.get("atc_taxi_via") or ())
        )

        if not airport_data:
            for widget in self.results_frame.winfo_children():
                widget.destroy()
            self.sidebar_frame = None
            self.vector_chart = None
            ctk.CTkLabel(self.results_frame, text="No airport data available.", font=ctk.CTkFont(size=16)).pack(expand=True)
            return

        # 3. Update Left EFB Dispatch Column in-place (zero flicker)
        self._update_sidebar_in_place(airport_data, result)

        # 4. Update Right Full-Window Lido Vector Chart or Standby Pane in-place
        if eff_map_hib or not show_maps_cfg:
            if self.vector_chart and self.vector_chart.winfo_exists():
                self.vector_chart.destroy()
            self.vector_chart = None

            if hasattr(self, "_standby_pane") and self._standby_pane and self._standby_pane.winfo_exists():
                self._standby_pane.destroy()

            standby_pane = ctk.CTkFrame(self.results_frame, fg_color="#1B1E24", corner_radius=12, border_width=0)
            standby_pane.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=0)
            self._standby_pane = standby_pane

            standby_card = ctk.CTkFrame(standby_pane, fg_color="#2B303B", corner_radius=12, border_width=0, width=520, height=235)
            standby_card.place(relx=0.5, rely=0.5, anchor="center")
            standby_card.pack_propagate(False)

            if eff_map_hib:
                arr_icao_lbl = arr.get("icao") or "DESTINATION"
                arr_gate_lbl = arr.get("gate") or "N/A"
                arr_rwy_lbl = arr.get("selected_runway") or "AUTO"

                ctk.CTkLabel(
                    standby_card,
                    text="IN-FLIGHT LOW-POWER STANDBY  WHEELS OFF",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=cam["accent"]
                ).pack(pady=(24, 8))

                ctk.CTkLabel(
                    standby_card,
                    text="Lido Ground Chart Paused During Flight",
                    font=ctk.CTkFont(size=17, weight="bold"),
                    text_color="#F8FAFC"
                ).pack(pady=(0, 10))

                ctk.CTkLabel(
                    standby_card,
                    text=(
                        f"Map rendering is automatically suspended while airborne\n"
                        f"It will automatically re-activate at Touchdown (Wheels-On) at {arr_icao_lbl}\n"
                        f"(Assigned Stand: {arr_gate_lbl}  RWY {arr_rwy_lbl})"
                    ),
                    font=ctk.CTkFont(size=12),
                    text_color="#94A3B8",
                    justify="center"
                ).pack(pady=(0, 18))

                def _preview_now():
                    self._inflight_map_preview_override = True
                    self._last_rendered_signature = None
                    if self.last_flight_data:
                        self.render_results(self.last_flight_data, preserve_camera=False)

                ctk.CTkButton(
                    standby_card,
                    text="Preview Chart Now",
                    width=190,
                    height=34,
                    fg_color=cam["s1"],
                    hover_color=cam["s2"],
                    border_width=0,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    command=_preview_now
                ).pack()
            else:
                ctk.CTkLabel(
                    standby_card,
                    text="AIRPORT MAPS DISABLED IN SETTINGS",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color="#94A3B8"
                ).pack(expand=True)
            return

        if hasattr(self, "_standby_pane") and self._standby_pane and self._standby_pane.winfo_exists():
            self._standby_pane.destroy()
            self._standby_pane = None

        has_existing_chart = bool(self.vector_chart and self.vector_chart.winfo_exists())
        if not has_existing_chart:
            initial_theme = "day" if self.config.settings.get("map_style") == "Minimalist Light" else "night"
            self.vector_chart = LidoVectorChart(
                self.results_frame,
                initial_theme=initial_theme,
                backend=self.backend,
                on_stand_click=self._on_manual_stand_selected,
                on_runway_click=self._on_runway_selected
            )
            self.vector_chart.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=0)
        else:
            if not preserve_camera:
                self.vector_chart.follow_aircraft = False
                self.vector_chart.heading_up = False
                self.vector_chart.view_mode = "route"
                self.vector_chart._update_theme_buttons()

        self.vector_chart.set_simconnect_status(getattr(self, "_current_simconnect_status_txt", "SimConnect Standby"))

        # Manage "Resume In-Flight Standby" button in header_bar without recreating chart
        show_resume_btn = bool(raw_map_hib and getattr(self, "_inflight_map_preview_override", False))
        if show_resume_btn:
            if not hasattr(self, "_btn_resume_standby") or not self._btn_resume_standby or not self._btn_resume_standby.winfo_exists():
                def _resume_standby():
                    self._inflight_map_preview_override = False
                    self._last_rendered_signature = None
                    if self.last_flight_data:
                        self.render_results(self.last_flight_data, preserve_camera=False)

                self._btn_resume_standby = ctk.CTkButton(
                    self.vector_chart.header_bar,
                    text="Resume In-Flight Standby",
                    width=165,
                    height=24,
                    fg_color=cam["s1"],
                    hover_color=cam["s2"],
                    border_width=0,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=_resume_standby
                )
            self._btn_resume_standby.pack(side="right", padx=10, pady=4)
        else:
            if hasattr(self, "_btn_resume_standby") and self._btn_resume_standby and self._btn_resume_standby.winfo_exists():
                self._btn_resume_standby.pack_forget()

        if getattr(self, "_just_touched_down_latch", False):
            self._just_touched_down_latch = False
            self.vector_chart._was_airborne = True
            preserve_camera = False

        self.vector_chart.set_data(airport_data, phase_mode=self.active_phase, user_aircraft=u_ac, preserve_camera=preserve_camera)


