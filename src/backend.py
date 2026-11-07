import os
import sys
import json
import re
import unicodedata
import urllib.request
from urllib.parse import urlparse, parse_qs
import http.server
import socketserver
import threading
import random
import configparser
import time
from network import OnlineNetworkChecker, haversine
from taxi_router import TaxiRouter
from interoperability_hub import (
    InteroperabilityHub,
    GateSource,
    clean_gate_token,
    strip_redundant_gate_suffix,
    gate_tokens_match,
)
from SimConnect import SimConnect as SC, RECV_SIMOBJECT_DATA_BYTYPE, OBJECT_ID_USER
from SimConnect.datadef import DataDefinition
from SimConnect.scdefs import (
    RECV_SIMOBJECT_DATA,
    SIMOBJECT_TYPE_AIRCRAFT,
    PERIOD_SIM_FRAME,
    DATATYPE_FLOAT64,
    DATATYPE_INT32,
    DATA_REQUEST_FLAG_CHANGED,
    DATA_REQUEST_FLAG_TAGGED,
)

AIRCRAFT_WINGSPANS = {
    'A318': 34.1, 'A319': 34.1, 'A320': 35.8, 'A321': 35.8,
    'A19N': 34.1, 'A20N': 35.8, 'A21N': 35.8,
    'A221': 35.1, 'A223': 35.1, 'BCS1': 35.1, 'BCS3': 35.1,
    'A332': 60.3, 'A333': 60.3, 'A338': 64.0, 'A339': 64.0, 'A343': 60.3, 'A346': 63.4,
    'A359': 64.75, 'A35K': 64.75, 'A388': 79.75,
    'B712': 28.4, 'B733': 28.9, 'B734': 28.9, 'B735': 28.9,
    'B736': 34.3, 'B737': 34.3, 'B738': 34.3, 'B739': 34.3,
    'B37M': 35.9, 'B38M': 35.9, 'B39M': 35.9, 'B3XM': 35.9,
    'B744': 64.4, 'B748': 68.4,
    'B752': 38.0, 'B753': 38.0,
    'B762': 47.6, 'B763': 47.6, 'B764': 51.9,
    'B772': 60.9, 'B773': 60.9, 'B77W': 64.8, 'B77L': 64.8,
    'B788': 60.1, 'B789': 60.1, 'B78X': 60.1,
    'E135': 20.0, 'E145': 20.0,
    'E170': 26.0, 'E175': 28.6, 'E190': 28.7, 'E195': 28.7,
    'E290': 33.7, 'E295': 35.1,
    'CRJ2': 21.2, 'CRJ7': 23.2, 'CRJ9': 24.8, 'CRJX': 26.2,
    'AT45': 24.6, 'AT46': 24.6, 'AT72': 27.0, 'AT75': 27.0, 'AT76': 27.0,
    'DH8A': 25.9, 'DH8B': 25.9, 'DH8C': 27.4, 'DH8D': 28.4,
    'SF34': 21.4, 'SB20': 24.7, 'F70': 28.1, 'F100': 28.1, 'BA46': 26.3, 'RJ85': 26.3, 'RJ1H': 26.3,
    # Freighters & Heavy Cargo
    'B77F': 64.8, 'A332F': 60.3, 'B748F': 68.4, 'B744F': 64.4, 'B742F': 64.4,
    'B738F': 34.3, 'B738BCF': 34.3, 'B733F': 34.3, 'B734F': 34.3,
    'B752F': 38.0, 'B763F': 47.6, 'B762F': 47.6, 'B76F': 47.6, 'MD11': 51.7, 'MD11F': 51.7,
    'A306': 44.8, 'A306F': 44.8, 'A310': 43.9, 'A310F': 43.9, 'A321F': 35.8, 'A320F': 35.8, 'A330F': 60.3,
    'AN124': 73.3, 'AN225': 88.4, 'AN12': 38.0, 'AN26': 29.2, 'C17': 51.7, 'C130': 40.4
}

VIRTUAL_TO_REAL_AIRLINE_MAP = {
    "AFV": "AFR", "VAF": "AFR",
    "DLHV": "DLH", "BAWV": "BAW",
    "EZYV": "EZY", "EZV": "EZY",
    "RYRV": "RYR", "VSAS": "SAS",
    "EDWV": "EDW", "BELV": "BEL",
    "VOEV": "VOE", "TAPV": "TAP",
    "ITAV": "ITY", "AZA": "ITY", "ITA": "ITY",
    "UNER": "UAE", "VAAL": "AAL",
    "DALV": "DAL", "UALV": "UAL",
    "SWV": "SWA", "NKSV": "NKS",
    "CPAV": "CPA", "EXSV": "EXS",
    "FDXV": "FDX", "UPSV": "UPS",
    "DHLV": "DHL", "BOXV": "BOX",
}

AIRLINE_SISTER_GROUPS = [
    {"SWR", "OAW", "EDW"},
    {"DLH", "CLH", "LHX", "OCN", "DLA"},
    {"EWG", "EWL"},
    {"AFR", "HOP"},
    {"KLM", "KLC"},
    {"TRA", "TVF"},
    {"FWI", "CAJ", "FBU"},
    {"RZO", "SAT"},
    {"BAW", "SHT", "CFE"},
    {"IBE", "IBS", "ANE"},
    {"EZY", "EJU", "EZS"},
    {"RYR", "RUK", "MAY", "RYS"},
    {"WZZ", "WMT", "WUK", "WAZ"},
    {"SAS", "SZS", "SVS"},
    {"NAX", "NSZ", "NOZ", "IBK"},
    {"FIN", "FCM"},
    {"TAP", "PGA"},
    {"AEE", "OAL"},
    {"THY", "TKJ"},
    {"TOM", "TUI", "TFL", "JAF", "BLX"},
    {"CND", "CAI", "CXI"},
    {"TVS", "CSA", "TVP", "TVQ"},
    {"AAL", "ENY", "JIA", "PDT"},
    {"DAL", "EDV"},
    {"UAL", "SKW", "RPA", "GJS", "ASH"},
    {"ACA", "JZA", "ROU"},
    {"QFA", "QLK", "JST"},
    {"DHL", "BCS", "DHK"},
    {"CLX", "ICV"},
    {"LAN", "TAM", "LPE"},
    {"SIA", "TGW"},
    {"CPA", "HKE"},
    {"ANA", "APJ"},
    {"KAL", "JNA", "AAR"},
]

AIRLINE_ALLIANCES = {
    "STAR_ALLIANCE": {
        "DLH", "SWR", "AUA", "BEL", "LOT", "TAP", "AEE", "CTN", "THY",
        "UAL", "ACA", "CMP", "AVA", "SIA", "ANA", "EVA", "CCA", "AIC",
        "THA", "ANZ", "MSR", "ETH", "SAA"
    },
    "SKYTEAM": {
        "AFR", "KLM", "SAS", "AEA", "ROT", "SVA", "MEA", "TAR", "KQA",
        "DAL", "AMX", "ARG", "KAL", "CAL", "CES", "CXA", "GIA", "HVN", "VIR"
    },
    "ONEWORLD": {
        "BAW", "IBE", "FIN", "RAM", "QTR", "RJA", "AAL", "ASA", "CPA",
        "JAL", "MAS", "QFA", "FJI", "OMA"
    }
}

ULTRA_LOW_COST_CARRIERS = {
    "RYR", "RUK", "MAY", "RYS", "WZZ", "WMT", "WUK", "WAZ",
    "NKS", "FFT", "AAY", "FXX"
}

LOW_COST_CARRIERS = ULTRA_LOW_COST_CARRIERS | {
    "EZY", "EJU", "EZS", "TRA", "TVF", "VLG", "VOE", "FPY", "PGT",
    "EXS", "NAX", "NSZ", "NOZ", "IBK", "TOM", "TUI", "TFL", "JAF",
    "BLX", "CND", "CAI", "CXI", "TVS", "SXS", "FDB", "ABY", "FAD",
    "KNE", "SWA", "JBU", "SCX", "MXY", "VXP", "VOI", "VIV", "TGW",
    "HKE", "APJ", "JNA", "TWB", "IGO", "AXM", "CEB", "VJC", "JST"
}

TURBOPROP_TYPES = {
    "AT43", "AT45", "AT46", "AT72", "AT75", "AT76",
    "DH8A", "DH8B", "DH8C", "DH8D", "SF34", "SB20", "D328", "JS41", "B190"
}

REGIONAL_JET_TYPES = {
    "CRJ2", "CRJ7", "CRJ9", "CRJX", "E135", "E145", "E170", "E175", "E190", "E195",
    "E290", "E295", "BCS1", "BCS3", "A221", "A223", "F70", "F100", "BA46", "RJ85", "RJ1H"
}

STRETCHED_NARROWBODY_TYPES = {
    "A321", "A21N", "B739", "B39M", "B3XM", "B752", "B753"
}

AIRCRAFT_EQUIVALENT_FAMILIES = {
    "BCS1": {"BCS1", "A221"}, "A221": {"BCS1", "A221"},
    "BCS3": {"BCS3", "A223"}, "A223": {"BCS3", "A223"},
    "A19N": {"A19N", "A319"}, "A20N": {"A20N", "A320"},
    "A21N": {"A21N", "A321"}, "A321": {"A321", "A21N"},
    "B38M": {"B38M", "B738"}, "B738": {"B738", "B38M"},
    "B39M": {"B39M", "B739"}, "B739": {"B739", "B39M"},
}

def normalize_airline_icao(code):
    if not code:
        return ""
    c = str(code).strip().upper()
    if c in VIRTUAL_TO_REAL_AIRLINE_MAP:
        return VIRTUAL_TO_REAL_AIRLINE_MAP[c]
    if len(c) == 4:
        if c.endswith("V"):
            return c[:3]
        if c.startswith("V"):
            return c[1:]
    return c

def get_sister_airlines(code):
    norm = normalize_airline_icao(code)
    if not norm:
        return set()
    res = {norm, str(code).strip().upper()}
    for grp in AIRLINE_SISTER_GROUPS:
        if norm in grp:
            res.update(grp)
    return res

def get_alliance_airlines(code):
    norm = normalize_airline_icao(code)
    if not norm:
        return set()
    res = set()
    for members in AIRLINE_ALLIANCES.values():
        if norm in members:
            res.update(members)
    return res

def is_schengen_airport(icao):
    ic = str(icao or "").strip().upper()
    if len(ic) != 4:
        return False
    # Exclude Faroe Islands (EKVG), Gibraltar (LXGB), Svalbard (ENSB), French Overseas (TF/SO/FM/NW/NT)
    if ic in {"EKVG", "LXGB", "ENSB"}:
        return False
    p2 = ic[:2]
    # Air Schengen member states (including Romania LR & Bulgaria LB since March 2024, Croatia LD, Switzerland LS, Norway EN, Iceland BI)
    schengen_p2 = {
        "LF", "LS", "ED", "ET", "LO", "EB", "EH", "EL", "LE", "GC",
        "LP", "LI", "LG", "LM", "EK", "EN", "ES", "EF", "EE", "EV",
        "EY", "EP", "LK", "LZ", "LH", "LJ", "LD", "BI", "LR", "LB"
    }
    return p2 in schengen_p2

def classify_flight_customs_profile(origin_icao, dest_icao):
    o = str(origin_icao or "").strip().upper()
    d = str(dest_icao or "").strip().upper()
    o_sch = is_schengen_airport(o)
    d_sch = is_schengen_airport(d)
    is_schengen = bool(o and d and o_sch and d_sch)
    is_non_schengen = bool(o and d and (not o_sch or not d_sch))

    def _country_key(ic):
        if len(ic) != 4:
            return ""
        if ic.startswith(("K", "C", "Y", "Z")):
            return ic[0]
        if ic[:2] in {"LE", "GC"}:
            return "ES"
        if ic[:2] in {"ED", "ET"}:
            return "DE"
        return ic[:2]

    c_o = _country_key(o)
    c_d = _country_key(d)
    is_domestic = bool(c_o and c_d and c_o == c_d)
    is_french_endpoint = bool(o.startswith("LF") or d.startswith("LF"))
    return {
        "is_schengen": is_schengen,
        "is_non_schengen": is_non_schengen,
        "is_domestic": is_domestic,
        "is_french_endpoint": is_french_endpoint,
        "origin_schengen": o_sch,
        "dest_schengen": d_sch,
    }

def infer_airport_stand_terminal(icao, gate_name, current_term=""):
    """
    Enriches or corrects terminal/pier names and Schengen/Non-Schengen zones
    based on official airport stand numbering where OSM or BGL data is incomplete.
    """
    icao_u = str(icao or "").strip().upper()
    g_clean = re.sub(r'^(?:GATE|STAND|PARKING|RAMP|DOCK|APRON)\s*', '', str(gate_name or "").strip().upper()).strip()
    cur = str(current_term or "").strip()
    cur_l = cur.lower()

    m_num = re.search(r'(\d+)', g_clean)
    num_val = int(m_num.group(1)) if m_num else None
    m_let = re.match(r'^([A-Z]+)', g_clean.replace(" ", ""))
    let_val = m_let.group(1) if m_let and m_let.group(1) not in ("L", "R", "C", "M") else ""

    if icao_u == "EGKK" and num_val is not None:
        # London Gatwick official stand numbering
        if 1 <= num_val <= 38:
            return "South Terminal"
        if (45 <= num_val <= 59) or (101 <= num_val <= 113) or (551 <= num_val <= 574):
            return "North Terminal"
        if 680 <= num_val <= 699:
            return "North Terminal (Pier 6)"
        if (40 <= num_val <= 44) or (60 <= num_val <= 99) or (130 <= num_val <= 399):
            return "Remote Stands"

    if icao_u == "LSGG" and num_val is not None:
        if not any(k in cur_l for k in ("schengen", "main terminal", "satellite", "east wing", "remote", "cargo", "business", "general")):
            if 1 <= num_val <= 11:
                return "Main Terminal (Schengen)"
            if (14 <= num_val <= 20) or (190 <= num_val <= 199):
                return "East Wing (Non-Schengen)"
            if (31 <= num_val <= 34) or (42 <= num_val <= 44):
                return "Satellite (Non-Schengen)"
            if (83 <= num_val <= 84) or (121 <= num_val <= 127):
                return "Satellite (Schengen)"
            if (61 <= num_val <= 68) or (85 <= num_val <= 89):
                return "Remote Stands"

    if icao_u == "LSZH":
        if let_val in ("A", "B") or "terminal a" in cur_l or "terminal b" in cur_l:
            base_t = f"Terminal {let_val}" if let_val in ("A", "B") else cur
            return f"{base_t} (Schengen)" if "schengen" not in cur_l else cur
        if let_val in ("D", "E") or "terminal d" in cur_l or "terminal e" in cur_l:
            base_t = f"Terminal {let_val}" if let_val in ("D", "E") else cur
            return f"{base_t} (Non-Schengen)" if "schengen" not in cur_l else cur

    if icao_u == "EBBR":
        if let_val == "A" or (num_val is not None and 100 <= num_val <= 199 and "pier b" not in cur_l):
            return "Pier A (Schengen)" if "schengen" not in cur_l else cur
        if let_val == "B" or (num_val is not None and 200 <= num_val <= 399 and "pier a" not in cur_l):
            return "Pier B (Non-Schengen)" if "schengen" not in cur_l else cur

    if icao_u == "OMDB":
        if not let_val and m_let and m_let.group(1) == "C" and re.match(r'^C\s*\d+', g_clean):
            let_val = "C"
        if let_val in ("A", "D") or cur_l in ("apron a", "apron d"):
            return "Terminal 3 (Concourse A)"
        if let_val == "B" or cur_l == "apron b":
            return "Terminal 3 (Concourse B)"
        if let_val == "F" or cur_l == "apron f":
            return "Terminal 3 (Concourse C)"
        if let_val == "C" or cur_l == "apron c":
            return "Terminal 1 (Concourse D)"
        if let_val in ("E", "G") or cur_l in ("apron e", "apron g"):
            return "Terminal 2"
        if let_val in ("S", "Q", "H") or cur_l in ("apron s", "apron q", "apron h"):
            return "Cargo / Remote Apron"

    if icao_u == "LHBP" and num_val is not None:
        if g_clean.startswith("R") or (200 <= num_val <= 299):
            return "Pier 1 (Low-Cost Stands)"
        if 40 <= num_val <= 49:
            return "Terminal 2A (Schengen)"
        if 30 <= num_val <= 39:
            return "Terminal 2B (Non-Schengen)"

    if icao_u == "LFPO":
        if not let_val and m_let and m_let.group(1) in ("C", "M") and re.match(r'^[CM]\s*\d+', g_clean):
            let_val = m_let.group(1)
        if let_val in ("P", "N") or cur_l in ("gate p", "gate n", "terminal p", "terminal n"):
            return "Orly 1 (Schengen)"
        if let_val == "A" or cur_l in ("gate a", "terminal a"):
            return "Orly 2 / 3 (Schengen)"
        if let_val in ("D", "E", "G", "M", "T", "U", "V") or cur_l in ("gate d", "gate e", "gate g", "gate m", "gate t", "gate u", "gate v"):
            return "Orly 3 (Schengen)"
        if let_val in ("B", "C", "F", "Q", "R", "S") or cur_l in ("gate b", "gate c", "gate f", "gate q", "gate r", "gate s", "terminal b", "terminal c", "terminal f", "terminal r"):
            return "Orly 4 (International & Outre-Mer)"

    return cur


# Official Airline Brand Styles: ICAO -> (bg_hex, fg_hex, border_hex, iata_code)
AIRLINE_BRAND_STYLES = {
    "SWR": ("#DC2626", "#FFFFFF", "#DC2626", "LX"),
    "EDW": ("#DC2626", "#FFFFFF", "#FACC15", "WK"),
    "OAW": ("#DC2626", "#FFFFFF", "#DC2626", "2L"),
    "AFR": ("#002157", "#FFFFFF", "#EF4444", "AF"),
    "HOP": ("#002157", "#FFFFFF", "#EF4444", "A5"),
    "EZY": ("#FF6600", "#FFFFFF", "#FF6600", "U2"),
    "EJU": ("#FF6600", "#FFFFFF", "#FF6600", "EC"),
    "EZS": ("#FF6600", "#FFFFFF", "#FF6600", "DS"),
    "BAW": ("#075AAA", "#FFFFFF", "#EB2226", "BA"),
    "SHT": ("#075AAA", "#FFFFFF", "#EB2226", "BA"),
    "CFE": ("#075AAA", "#FFFFFF", "#EB2226", "CJ"),
    "DLH": ("#05164D", "#FFAD00", "#05164D", "LH"),
    "CLH": ("#05164D", "#FFAD00", "#05164D", "CL"),
    "OCN": ("#05164D", "#38BDF8", "#05164D", "4Y"),
    "DLA": ("#00665E", "#FFFFFF", "#00665E", "EN"),
    "RYR": ("#073590", "#F1C933", "#073590", "FR"),
    "RUK": ("#073590", "#F1C933", "#073590", "RK"),
    "KLM": ("#00A1DE", "#FFFFFF", "#00A1DE", "KL"),
    "KLC": ("#00A1DE", "#FFFFFF", "#00A1DE", "WA"),
    "UAE": ("#D71921", "#FFFFFF", "#D71921", "EK"),
    "FDB": ("#0066B3", "#F59E0B", "#0066B3", "FZ"),
    "ABY": ("#E30613", "#FFFFFF", "#E30613", "G9"),
    "QTR": ("#5C0632", "#FFFFFF", "#5C0632", "QR"),
    "ETD": ("#BD8B13", "#FFFFFF", "#BD8B13", "EY"),
    "IBE": ("#D7192D", "#FACC15", "#D7192D", "IB"),
    "IBS": ("#D7192D", "#FACC15", "#D7192D", "I2"),
    "ANE": ("#D7192D", "#FACC15", "#D7192D", "YW"),
    "VLG": ("#FFCC00", "#1E293B", "#D97706", "VY"),
    "AEA": ("#0066CC", "#FFFFFF", "#0066CC", "UX"),
    "VOE": ("#E11D48", "#FFFFFF", "#E11D48", "V7"),
    "CRL": ("#0072CE", "#FFFFFF", "#00A3E0", "SS"),
    "FBU": ("#009FE3", "#FFFFFF", "#0369A1", "BF"),
    "FWI": ("#00A8B5", "#FFFFFF", "#F59E0B", "TX"),
    "CAJ": ("#00A8B5", "#FFFFFF", "#F59E0B", "TX"),
    "DJT": ("#1E3A8A", "#38BDF8", "#38BDF8", "B0"),
    "CCM": ("#0079B4", "#FFFFFF", "#0284C7", "XK"),
    "FPO": ("#003399", "#FACC15", "#003399", "5O"),
    "TJT": ("#003366", "#FFFFFF", "#E30613", "T7"),
    "CLG": ("#1E3A8A", "#FFFFFF", "#DC2626", "CE"),
    "AEH": ("#0F172A", "#FFFFFF", "#E11D48", "8R"),
    "TAP": ("#009B3A", "#FFFFFF", "#DC2626", "TP"),
    "RZO": ("#003366", "#FFFFFF", "#00A3E0", "S4"),
    "SAT": ("#003366", "#FFFFFF", "#00A3E0", "SP"),
    "SAS": ("#000099", "#FFFFFF", "#000099", "SK"),
    "FIN": ("#0B1560", "#FFFFFF", "#0B1560", "AY"),
    "EIN": ("#006272", "#FFFFFF", "#006272", "EI"),
    "THY": ("#C8102E", "#FFFFFF", "#C8102E", "TK"),
    "TKJ": ("#C8102E", "#FFFFFF", "#005596", "VF"),
    "SXS": ("#F59E0B", "#003366", "#003366", "XQ"),
    "FHY": ("#D71920", "#FFFFFF", "#F59E0B", "FH"),
    "VIR": ("#E10A0A", "#FFFFFF", "#6B21A8", "VS"),
    "TOM": ("#00A0DF", "#FFFFFF", "#DC2626", "BY"),
    "TUI": ("#00A0DF", "#FFFFFF", "#DC2626", "X3"),
    "JAF": ("#00A0DF", "#FFFFFF", "#DC2626", "TB"),
    "TFL": ("#00A0DF", "#FFFFFF", "#DC2626", "OR"),
    "BLX": ("#00A0DF", "#FFFFFF", "#DC2626", "6B"),
    "CND": ("#D71920", "#FFFFFF", "#D71920", "CD"),
    "CAI": ("#D71920", "#FFFFFF", "#D71920", "XC"),
    "WZZ": ("#C6007E", "#FFFFFF", "#2563EB", "W6"),
    "NAX": ("#D81939", "#FFFFFF", "#003057", "DY"),
    "NSZ": ("#D81939", "#FFFFFF", "#003057", "D8"),
    "WIF": ("#007A3D", "#FFFFFF", "#007A3D", "WF"),
    "FPY": ("#E11D48", "#FFFFFF", "#E11D48", "OG"),
    "TVF": ("#00D66C", "#FFFFFF", "#00D66C", "TO"),
    "TRA": ("#00D66C", "#FFFFFF", "#00D66C", "HV"),
    "AUA": ("#D71920", "#FFFFFF", "#D71920", "OS"),
    "BEL": ("#00205B", "#FFFFFF", "#E4002B", "SN"),
    "EWG": ("#830051", "#FFFFFF", "#00A1DE", "EW"),
    "CFG": ("#F59E0B", "#111827", "#F59E0B", "DE"),
    "ITY": ("#003399", "#FFFFFF", "#009933", "AZ"),
    "NOS": ("#009FE3", "#FFFFFF", "#009FE3", "NO"),
    "AEE": ("#002B7F", "#FFFFFF", "#002B7F", "A3"),
    "SEH": ("#0F172A", "#EC4899", "#EC4899", "GQ"),
    "PGT": ("#FBBF24", "#111827", "#D97706", "PC"),
    "EXS": ("#DC2626", "#FFFFFF", "#DC2626", "LS"),
    "LOT": ("#002664", "#FFFFFF", "#002664", "LO"),
    "ENT": ("#003399", "#FFFFFF", "#FACC15", "E4"),
    "TVS": ("#1D4ED8", "#F97316", "#1D4ED8", "QS"),
    "CSA": ("#003366", "#FFFFFF", "#D71920", "OK"),
    "BTI": ("#97D700", "#0F172A", "#65A30D", "BT"),
    "ROT": ("#003399", "#FFFFFF", "#FACC15", "RO"),
    "LZB": ("#00843D", "#FFFFFF", "#DA291C", "FB"),
    "ASL": ("#00205B", "#FFFFFF", "#C8102E", "JU"),
    "CTN": ("#003399", "#FFFFFF", "#DC2626", "OU"),
    "ICE": ("#00205B", "#FACC15", "#00205B", "FI"),
    "LGL": ("#00A3E0", "#FFFFFF", "#003366", "LG"),
    "AMC": ("#D71920", "#FFFFFF", "#D71920", "KM"),
    "CYP": ("#005A9C", "#FFFFFF", "#005A9C", "CY"),
    "IBB": ("#00843D", "#FFFFFF", "#00843D", "NT"),
    "ELY": ("#0038B8", "#FFFFFF", "#0038B8", "LY"),
    "AIZ": ("#00529B", "#FFFFFF", "#F59E0B", "IZ"),
    "ISR": ("#0038B8", "#FFFFFF", "#0038B8", "6H"),
    "RJA": ("#1E293B", "#FACC15", "#DC2626", "RJ"),
    "MEA": ("#00843D", "#FFFFFF", "#DC2626", "ME"),
    "SVA": ("#006C35", "#FFFFFF", "#B45309", "SV"),
    "FAD": ("#581C87", "#D9F99D", "#581C87", "F3"),
    "KNE": ("#0D9488", "#FFFFFF", "#0D9488", "XY"),
    "OMA": ("#B45309", "#FFFFFF", "#DC2626", "WY"),
    "KAC": ("#00205B", "#FFFFFF", "#00A3E0", "KU"),
    "JZR": ("#005596", "#FACC15", "#005596", "J9"),
    "GFA": ("#85714D", "#FFFFFF", "#85714D", "GF"),
    "MSR": ("#00205B", "#FFFFFF", "#B45309", "MS"),
    "RAM": ("#C1272D", "#FFFFFF", "#006233", "AT"),
    "DAH": ("#DA291C", "#FFFFFF", "#006233", "AH"),
    "TAR": ("#E70013", "#FFFFFF", "#E70013", "TU"),
    "LBT": ("#005596", "#FACC15", "#005596", "BJ"),
    "ETH": ("#00843D", "#FACC15", "#DA291C", "ET"),
    "KQA": ("#DA291C", "#FFFFFF", "#006633", "KQ"),
    "RWD": ("#005596", "#FACC15", "#10B981", "WB"),
    "DTA": ("#D71920", "#FACC15", "#111827", "DT"),
    "SAA": ("#007749", "#FFFFFF", "#FFB81C", "SA"),
    "MAU": ("#D71920", "#FFFFFF", "#D71920", "MK"),
    "AAL": ("#0078D2", "#FFFFFF", "#C8102E", "AA"),
    "DAL": ("#003366", "#FFFFFF", "#E3132C", "DL"),
    "UAL": ("#002244", "#FFFFFF", "#005DAA", "UA"),
    "SWA": ("#304CB2", "#FFBF27", "#D5152E", "WN"),
    "JBU": ("#003876", "#FFFFFF", "#00A1DE", "B6"),
    "ASA": ("#01426A", "#FFFFFF", "#66C5CC", "AS"),
    "HAL": ("#4C1D95", "#F43F5E", "#4C1D95", "HA"),
    "NKS": ("#FFEC00", "#111827", "#111827", "NK"),
    "FFT": ("#006747", "#FFFFFF", "#006747", "F9"),
    "ACA": ("#D8262E", "#FFFFFF", "#111827", "AC"),
    "WJA": ("#00857D", "#FFFFFF", "#003B5C", "WS"),
    "TSC": ("#005596", "#FFFFFF", "#00A3E0", "TS"),
    "POE": ("#0F172A", "#FFFFFF", "#38BDF8", "PD"),
    "AMX": ("#0B2343", "#FFFFFF", "#E31B23", "AM"),
    "VOI": ("#111827", "#A855F7", "#A855F7", "Y4"),
    "VIV": ("#15803D", "#FFFFFF", "#15803D", "VB"),
    "AVA": ("#DA291C", "#FFFFFF", "#DA291C", "AV"),
    "CMP": ("#00529B", "#FFFFFF", "#B45309", "CM"),
    "LAN": ("#1B0088", "#FFFFFF", "#E8114B", "LA"),
    "TAM": ("#1B0088", "#FFFFFF", "#E8114B", "JJ"),
    "GLO": ("#FF6600", "#FFFFFF", "#FF6600", "G3"),
    "AZU": ("#0038A8", "#FFFFFF", "#00A3E0", "AD"),
    "ARG": ("#0080C6", "#FFFFFF", "#0080C6", "AR"),
    "SIA": ("#00266B", "#F59E0B", "#F59E0B", "SQ"),
    "TGW": ("#FACC15", "#111827", "#111827", "TR"),
    "CPA": ("#006564", "#FFFFFF", "#006564", "CX"),
    "HKE": ("#6D28D9", "#FFFFFF", "#EC4899", "UO"),
    "ANA": ("#00467F", "#FFFFFF", "#00A0E9", "NH"),
    "APJ": ("#DB2777", "#FFFFFF", "#DB2777", "MM"),
    "JAL": ("#CC0000", "#FFFFFF", "#CC0000", "JL"),
    "KAL": ("#0064DE", "#FFFFFF", "#C8102E", "KE"),
    "AAR": ("#C8102E", "#FFFFFF", "#4B5563", "OZ"),
    "CCA": ("#D71920", "#FFFFFF", "#D71920", "CA"),
    "CES": ("#002C5F", "#FFFFFF", "#DA291C", "MU"),
    "CSN": ("#0066B3", "#FFFFFF", "#DA291C", "CZ"),
    "CHH": ("#D71920", "#FACC15", "#D71920", "HU"),
    "CAL": ("#0033A0", "#FFFFFF", "#E4007F", "CI"),
    "EVA": ("#00693E", "#FFFFFF", "#F37021", "BR"),
    "SJX": ("#1E293B", "#D97706", "#D97706", "JX"),
    "THA": ("#4B0082", "#FACC15", "#EC4899", "TG"),
    "MAS": ("#00205B", "#FFFFFF", "#DA291C", "MH"),
    "AXM": ("#DC2626", "#FFFFFF", "#DC2626", "AK"),
    "GIA": ("#0065B3", "#FFFFFF", "#00A3E0", "GA"),
    "PAL": ("#00205B", "#FFFFFF", "#DC2626", "PR"),
    "CEB": ("#FACC15", "#005596", "#005596", "5J"),
    "HVN": ("#005596", "#FACC15", "#005596", "VN"),
    "VJC": ("#DC2626", "#FACC15", "#DC2626", "VJ"),
    "AIC": ("#C8102E", "#FACC15", "#C8102E", "AI"),
    "IGO": ("#001B94", "#FFFFFF", "#001B94", "6E"),
    "QFA": ("#E40000", "#FFFFFF", "#E40000", "QF"),
    "JST": ("#FF6600", "#111827", "#FF6600", "JQ"),
    "VOZ": ("#DA291C", "#FFFFFF", "#581C87", "VA"),
    "ANZ": ("#111827", "#FFFFFF", "#00A3E0", "NZ"),
    "FDX": ("#4D148C", "#FFFFFF", "#FF6600", "FX"),
    "UPS": ("#351C15", "#FFB500", "#FFB500", "5X"),
    "DHK": ("#FFCC00", "#D40511", "#D40511", "D0"),
    "BCS": ("#FFCC00", "#D40511", "#D40511", "QY"),
    "CLX": ("#D71920", "#FFFFFF", "#003399", "CV"),
    "GEC": ("#05164D", "#FFAD00", "#05164D", "LH"),
    "BOX": ("#05164D", "#FFCC00", "#FFCC00", "3S"),
    "NJE": ("#0F172A", "#38BDF8", "#38BDF8", "1I"),
}


def get_airline_brand_style(code):
    """Returns (bg_hex, fg_hex, border_hex, iata_code) for a given airline ICAO code."""
    c = normalize_airline_icao(code)
    if c in AIRLINE_BRAND_STYLES:
        return AIRLINE_BRAND_STYLES[c]
    # Deterministic vibrant palette for any other airline
    palettes = [
        ("#1D4ED8", "#FFFFFF", "#3B82F6"),
        ("#B91C1C", "#FFFFFF", "#EF4444"),
        ("#047857", "#FFFFFF", "#10B981"),
        ("#6D28D9", "#FFFFFF", "#8B5CF6"),
        ("#B45309", "#FFFFFF", "#F59E0B"),
        ("#0E7490", "#FFFFFF", "#06B6D4"),
        ("#9D174D", "#FFFFFF", "#EC4899"),
    ]
    h = sum(ord(ch) * (i + 1) for i, ch in enumerate(c or "AIR"))
    bg, fg, bd = palettes[h % len(palettes)]
    return (bg, fg, bd, "")


AIRLINE_FULL_NAMES = {
    "SWR": "SWISS International Air Lines",
    "EDW": "Edelweiss Air",
    "OAW": "Helvetic Airways",
    "AFR": "Air France",
    "HOP": "Air France HOP",
    "EZY": "easyJet",
    "EJU": "easyJet Europe",
    "EZS": "easyJet Switzerland",
    "BAW": "British Airways",
    "SHT": "British Airways Shuttle",
    "CFE": "BA CityFlyer",
    "DLH": "Lufthansa",
    "CLH": "Lufthansa CityLine",
    "OCN": "Discover Airlines",
    "DLA": "Air Dolomiti",
    "RYR": "Ryanair",
    "RUK": "Ryanair UK",
    "KLM": "KLM Royal Dutch Airlines",
    "KLC": "KLM Cityhopper",
    "UAE": "Emirates",
    "FDB": "flydubai",
    "ABY": "Air Arabia",
    "QTR": "Qatar Airways",
    "ETD": "Etihad Airways",
    "IBE": "Iberia",
    "IBS": "Iberia Express",
    "ANE": "Air Nostrum",
    "VLG": "Vueling",
    "AEA": "Air Europa",
    "VOE": "Volotea",
    "CRL": "Corsair International",
    "FBU": "French bee",
    "FWI": "Air Caraïbes",
    "CAJ": "Air Caraïbes Atlantique",
    "DJT": "La Compagnie",
    "CCM": "Air Corsica",
    "TJT": "Twin Jet",
    "CLG": "Chalair Aviation",
    "AEH": "Amelia International",
    "TAP": "TAP Air Portugal",
    "RZO": "Azores Airlines",
    "SAT": "SATA Air Açores",
    "SAS": "SAS Scandinavian Airlines",
    "FIN": "Finnair",
    "EIN": "Aer Lingus",
    "THY": "Turkish Airlines",
    "TKJ": "AJet",
    "SXS": "SunExpress",
    "FHY": "Freebird Airlines",
    "VIR": "Virgin Atlantic",
    "TOM": "TUI Airways",
    "TUI": "TUIfly",
    "JAF": "TUI fly Belgium",
    "TFL": "TUI fly Netherlands",
    "BLX": "TUIfly Nordic",
    "CND": "Corendon Dutch Airlines",
    "CAI": "Corendon Airlines",
    "WZZ": "Wizz Air",
    "NAX": "Norwegian Air Shuttle",
    "NSZ": "Norwegian Air Sweden",
    "FPY": "PLAY Airlines",
    "TVF": "Transavia France",
    "TRA": "Transavia",
    "AUA": "Austrian Airlines",
    "BEL": "Brussels Airlines",
    "EWG": "Eurowings",
    "CFG": "Condor",
    "ITY": "ITA Airways",
    "NOS": "Neos",
    "AEE": "Aegean Airlines",
    "SEH": "Sky Express",
    "PGT": "Pegasus Airlines",
    "EXS": "Jet2.com",
    "LOT": "LOT Polish Airlines",
    "ENT": "Enter Air",
    "CSA": "Czech Airlines",
    "BTI": "airBaltic",
    "ROT": "TAROM",
    "LZB": "Bulgaria Air",
    "ASL": "Air Serbia",
    "CTN": "Croatia Airlines",
    "ICE": "Icelandair",
    "LGL": "Luxair",
    "AMC": "KM Malta Airlines",
    "CYP": "Cyprus Airways",
    "IBB": "Binter Canarias",
    "ELY": "El Al Israel Airlines",
    "AIZ": "Arkia Israeli Airlines",
    "ISR": "Israir Airlines",
    "RJA": "Royal Jordanian",
    "MEA": "Middle East Airlines",
    "SVA": "Saudia",
    "FAD": "flyadeal",
    "KNE": "flynas",
    "OMA": "Oman Air",
    "KAC": "Kuwait Airways",
    "JZR": "Jazeera Airways",
    "GFA": "Gulf Air",
    "MSR": "EgyptAir",
    "RAM": "Royal Air Maroc",
    "DAH": "Air Algérie",
    "TAR": "Tunisair",
    "LBT": "Nouvelair",
    "ETH": "Ethiopian Airlines",
    "KQA": "Kenya Airways",
    "RWD": "RwandAir",
    "DTA": "TAAG Angola Airlines",
    "SAA": "South African Airways",
    "MAU": "Air Mauritius",
    "AAL": "American Airlines",
    "DAL": "Delta Air Lines",
    "UAL": "United Airlines",
    "SWA": "Southwest Airlines",
    "JBU": "JetBlue Airways",
    "ASA": "Alaska Airlines",
    "HAL": "Hawaiian Airlines",
    "NKS": "Spirit Airlines",
    "FFT": "Frontier Airlines",
    "ACA": "Air Canada",
    "WJA": "WestJet",
    "TSC": "Air Transat",
    "POE": "Porter Airlines",
    "AMX": "Aeroméxico",
    "VOI": "Volaris",
    "VIV": "Viva Aerobus",
    "AVA": "Avianca",
    "CMP": "Copa Airlines",
    "LAN": "LATAM Airlines",
    "TAM": "LATAM Brasil",
    "GLO": "GOL Linhas Aéreas",
    "AZU": "Azul Brazilian Airlines",
    "ARG": "Aerolíneas Argentinas",
    "SIA": "Singapore Airlines",
    "TGW": "Scoot",
    "CPA": "Cathay Pacific",
    "HKE": "HK Express",
    "ANA": "All Nippon Airways (ANA)",
    "APJ": "Peach Aviation",
    "JAL": "Japan Airlines (JAL)",
    "KAL": "Korean Air",
    "AAR": "Asiana Airlines",
    "CCA": "Air China",
    "CES": "China Eastern Airlines",
    "CSN": "China Southern Airlines",
    "CHH": "Hainan Airlines",
    "CAL": "China Airlines",
    "EVA": "EVA Air",
    "SJX": "Starlux Airlines",
    "THA": "Thai Airways",
    "MAS": "Malaysia Airlines",
    "AXM": "AirAsia",
    "GIA": "Garuda Indonesia",
    "PAL": "Philippine Airlines",
    "CEB": "Cebu Pacific",
    "HVN": "Vietnam Airlines",
    "VJC": "VietJet Air",
    "AIC": "Air India",
    "IGO": "IndiGo",
    "QFA": "Qantas",
    "JST": "Jetstar Airways",
    "VOZ": "Virgin Australia",
    "ANZ": "Air New Zealand",
    "FDX": "FedEx Express",
    "UPS": "UPS Airlines",
    "DHK": "DHL Air UK",
    "BCS": "European Air Transport (DHL)",
    "CLX": "Cargolux",
    "GEC": "Lufthansa Cargo",
    "BOX": "AeroLogic",
    "NJE": "NetJets Aviation",
    "LOG": "Loganair",
    "AUR": "Aurigny Air Services",
    "FPO": "ASL Airlines France",
    "TVS": "Smartwings",
    "WIF": "Widerøe",
}


def get_airline_display_name(code, extra_map=None):
    c = normalize_airline_icao(code)
    if not c:
        return ""
    if c in AIRLINE_FULL_NAMES:
        return AIRLINE_FULL_NAMES[c]
    if extra_map and c in extra_map and extra_map[c]:
        return str(extra_map[c])
    raw = str(code or "").strip().upper()
    if raw in AIRLINE_FULL_NAMES:
        return AIRLINE_FULL_NAMES[raw]
    if extra_map and raw in extra_map and extra_map[raw]:
        return str(extra_map[raw])
    return c


COUNTRY_AIRLINE_POOLS = {
    "LF": [["AFR"], ["EZY"], ["AFR", "HOP"], ["TVF"], ["AFR", "KLM"], ["RYR"], ["BAW"], ["VLG"]],
    "LS": [["SWR"], ["EZY"], ["SWR", "EDW"], ["SWR", "DLH"], ["AFR"], ["BAW"], ["KLM"]],
    "ED": [["DLH"], ["DLH", "EWG"], ["EWG"], ["CFG"], ["DLH", "SWR"], ["RYR"], ["BAW"], ["THY"]],
    "ET": [["DLH"], ["EWG"], ["RYR"]],
    "EG": [["BAW"], ["EZY"], ["RYR"], ["TOM"], ["EXS"], ["VIR"], ["KLM", "AFR"], ["DLH", "SWR"], ["EIN"]],
    "EI": [["EIN"], ["RYR"], ["EIN", "BAW"], ["DLH"], ["AFR", "KLM"]],
    "LE": [["IBE"], ["VLG"], ["RYR"], ["IBE", "BAW"], ["EZY"], ["AFR", "KLM"], ["DLH", "SWR"]],
    "GC": [["IBE"], ["VLG"], ["RYR"], ["EZY"], ["TOM"], ["CFG"], ["EWG"]],
    "LP": [["TAP"], ["RYR"], ["EZY"], ["TAP", "IBE"], ["AFR", "KLM"], ["BAW"], ["DLH"]],
    "LI": [["ITY"], ["RYR"], ["EZY"], ["WZZ"], ["DLH", "SWR"], ["AFR", "KLM"], ["BAW"], ["VLG"]],
    "EH": [["KLM"], ["KLM", "TRA"], ["EZY"], ["KLM", "AFR"], ["KLM", "DAL"], ["BAW"], ["DLH", "SWR"]],
    "EB": [["BEL"], ["RYR"], ["TUI"], ["BEL", "DLH"], ["AFR", "KLM"], ["VLG"], ["BAW"]],
    "EL": [["LGL"], ["DLH"], ["BAW"], ["EZY"], ["RYR"]],
    "LO": [["AUA"], ["RYR"], ["WZZ"], ["AUA", "DLH"], ["AUA", "SWR"], ["EWG"]],
    "EK": [["SAS"], ["NAX"], ["RYR"], ["EZY"], ["KLM"], ["DLH"], ["BAW"]],
    "ES": [["SAS"], ["NAX"], ["RYR"], ["FIN"], ["DLH"], ["KLM"]],
    "EN": [["SAS"], ["NAX"], ["WIF"], ["KLM"], ["DLH"], ["BAW"]],
    "EF": [["FIN"], ["NAX"], ["SAS"], ["RYR"], ["DLH"]],
    "BI": [["ICE"], ["EZY"], ["SAS"], ["DLH"], ["BAW"]],
    "LG": [["AEE"], ["RYR"], ["EZY"], ["WZZ"], ["TOM"], ["DLH"], ["BAW"], ["AFR"]],
    "LT": [["THY"], ["PGT"], ["THY", "DLH"], ["BAW"]],
    "LK": [["TVS"], ["RYR"], ["EZY"], ["DLH"], ["AFR", "KLM"], ["BAW"]],
    "EP": [["LOT"], ["RYR"], ["WZZ"], ["DLH"], ["KLM"]],
    "LH": [["WZZ"], ["RYR"], ["DLH"], ["AUA"], ["KLM"], ["BAW"]],
    "LR": [["ROT"], ["WZZ"], ["RYR"], ["DLH"], ["AFR", "KLM"]],
    "LZ": [["RYR"], ["WZZ"]],
    "LB": [["LZB"], ["WZZ"], ["RYR"], ["DLH", "AUA"]],
    "LY": [["ASL"], ["WZZ"], ["DLH", "AUA"], ["THY"]],
    "LD": [["CTN"], ["RYR"], ["EZY"], ["DLH", "EWG"]],
    "LJ": [["DLH"], ["SWR"], ["EZY"], ["AFR"], ["THY"]],
    "EV": [["BTI"], ["RYR"], ["WZZ"], ["FIN"], ["DLH"]],
    "EY": [["BTI"], ["RYR"], ["WZZ"], ["LOT"], ["SAS"]],
    "EE": [["BTI"], ["RYR"], ["FIN"], ["SAS"], ["DLH"]],
    "LM": [["AMC"], ["RYR"], ["EZY"], ["DLH"], ["BAW"]],
    "LC": [["CYP"], ["WZZ"], ["RYR"], ["EZY"], ["BAW"], ["AEE"]],
    "LL": [["ELY"], ["WZZ"], ["RYR"], ["EZY"], ["DLH"], ["AFR"], ["BAW"]],
    "OM": [["UAE"], ["ETD"], ["FDB"], ["ABY"], ["BAW"], ["QTR"], ["SIA"]],
    "OT": [["QTR"], ["BAW"], ["UAE"]],
    "OE": [["SVA"], ["FAD"], ["UAE"], ["QTR"], ["MSR"]],
    "OJ": [["RJA"], ["UAE"], ["QTR"], ["MSR"], ["THY"]],
    "OL": [["MEA"], ["AFR"], ["UAE"], ["QTR"], ["THY"]],
    "OK": [["KAC"], ["JZR"], ["UAE"], ["QTR"], ["SVA"]],
    "OB": [["GFA"], ["UAE"], ["QTR"], ["SVA"], ["BAW"]],
    "OO": [["OMA"], ["UAE"], ["QTR"], ["SAL"]],
    "HE": [["MSR"], ["UAE"], ["SVA"], ["QTR"], ["THY"], ["DLH"]],
    "GM": [["RAM"], ["RYR"], ["EZY"], ["TVF"], ["AFR"], ["IBE"]],
    "DA": [["DAH"], ["AFR"], ["TVF"], ["THY"]],
    "DT": [["TAR"], ["AFR"], ["TVF"], ["DLH"]],
    "HA": [["ETH"], ["UAE"], ["QTR"], ["DLH"]],
    "HK": [["KQA"], ["ETH"], ["UAE"], ["QTR"], ["BAW"], ["KLM"]],
    "FA": [["SAA"], ["BAW"], ["UAE"], ["QTR"], ["KLM", "AFR"], ["DLH"]],
    "RJ": [["ANA"], ["JAL"], ["SIA"], ["UAL"], ["DAL"]],
    "RK": [["KAL"], ["AAR"], ["DLH"], ["UAL"], ["DAL"]],
    "RC": [["CAL"], ["EVA"], ["CPA"], ["ANA"], ["JAL"]],
    "VH": [["CPA"], ["HKE"], ["SIA"], ["BAW"], ["UAE"]],
    "WS": [["SIA"], ["TRG"], ["QFA"], ["BAW"], ["UAE"]],
    "WM": [["MAS"], ["AXM"], ["SIA"], ["UAE"], ["QTR"]],
    "VT": [["THA"], ["AIQ"], ["UAE"], ["QTR"], ["SIA"], ["EVA"]],
    "WI": [["GIA"], ["LNI"], ["SIA"], ["MAS"], ["QTR"]],
    "VA": [["AIC"], ["IGO"], ["UAE"], ["QTR"], ["BAW"]],
    "VI": [["AIC"], ["IGO"], ["UAE"], ["QTR"], ["BAW"], ["DLH"]],
    "VO": [["AIC"], ["IGO"], ["UAE"], ["QTR"], ["SIA"]],
    "VE": [["AIC"], ["IGO"]],
    "YB": [["QFA"], ["VOZ"], ["JST"], ["SIA"], ["UAE"], ["ANZ"]],
    "YM": [["QFA"], ["VOZ"], ["JST"], ["SIA"], ["UAE"], ["QTR"]],
    "YP": [["QFA"], ["VOZ"], ["JST"], ["SIA"], ["UAE"]],
    "YS": [["QFA"], ["VOZ"], ["JST"], ["SIA"], ["UAE"], ["UAL"], ["ANZ"]],
    "NZ": [["ANZ"], ["JST"], ["QFA"], ["UAE"]],
    "SB": [["TAM"], ["GLO"], ["AZU"], ["TAP"], ["AFR"], ["AAL"]],
    "SA": [["ARG"], ["TAM"], ["IBE"], ["AAL"], ["AFR"]],
    "SC": [["LAN"], ["SKY"], ["IBE"], ["AAL"], ["DAL"]],
    "SK": [["AVA"], ["LAN"], ["AAL"], ["IBE"]],
    "SP": [["LAN"], ["SKY"], ["AAL"], ["IBE"], ["KLM"]],
    "MP": [["CMP"], ["AVA"], ["AAL"], ["IBE"], ["KLM"]],
    "MM": [["AMX"], ["VOI"], ["VIV"], ["AAL"], ["UAL"], ["DAL"]],
}


# Ground handling, catering, and ramp agent tokens sometimes placed inside GSX `airlinecodes`
GSX_NON_AIRLINE_TOKENS = {
    "ANY", "NONE", "ALL", "GEN", "GA", "VIP", "MIL", "CARGO",
    "MENZIES", "SWISSPORT", "SWP", "_SWP", "DNATA", "SERVAIR",
    "SAMSIC", "SVS", "_SVS", "GATE", "GOURMET", "GATEGOURMET",
    "RED", "HANDLING", "HANDLIN", "WHITE", "DHL_WHITE", "AVIA",
    "PARTNER", "AVIAPARTNER", "CELEBI", "WFS", "FRAPORT", "ASG",
}

# Common 2-letter IATA codes or full names sometimes written by GSX profile authors in `airlinecodes`
GSX_TOKEN_TO_ICAO_MAP = {
    "LA": "TAM", "LATAM": "TAM", "JJ": "TAM",
    "G3": "GLO", "GOL": "GLO", "AD": "AZU", "AZUL": "AZU",
    "AR": "ARG", "AM": "AMX", "AV": "AVA", "CM": "CMP",
    "LH": "DLH", "LX": "SWR", "OS": "AUA", "SN": "BEL", "EW": "EWG",
    "AF": "AFR", "KL": "KLM", "HV": "TRA", "TO": "TVF",
    "BA": "BAW", "IB": "IBE", "VY": "VLG", "EI": "EIN", "AY": "FIN",
    "U2": "EZY", "FR": "RYR", "W6": "WZZ", "DY": "NAX", "LS": "EXS", "BY": "TOM",
    "SK": "SAS", "TP": "TAP", "AZ": "ITY", "ITA": "ITY", "TK": "THY", "PC": "PGT",
    "A3": "AEE", "LO": "LOT", "RO": "ROT", "BT": "BTI", "JU": "ASL", "OU": "CTN",
    "EK": "UAE", "FZ": "FDB", "EY": "ETD", "QR": "QTR", "SV": "SVA",
    "GF": "GFA", "WY": "OMA", "KU": "KAC", "RJ": "RJA", "ME": "MEA",
    "MS": "MSR", "ET": "ETH", "AT": "RAM", "AH": "DAH", "TU": "TAR",
    "AA": "AAL", "DL": "DAL", "UA": "UAL", "WN": "SWA", "B6": "JBU", "AS": "ASA",
    "AC": "ACA", "WS": "WJA", "TS": "TSC",
    "SQ": "SIA", "CX": "CPA", "QF": "QFA", "NZ": "ANZ", "NH": "ANA", "JL": "JAL",
    "KE": "KAL", "OZ": "AAR", "CI": "CAL", "BR": "EVA", "TG": "THA", "MH": "MAS",
    "GA": "GIA", "AI": "AIC", "6E": "IGO", "CA": "CCA", "MU": "CES", "CZ": "CSN",
    "V7": "VOE", "SS": "CRL", "BF": "FBU", "TX": "FWI", "B0": "DJT", "XK": "CCM",
    "UX": "AEA", "XQ": "SXS", "EN": "DLA", "4Y": "OCN", "2L": "OAW", "S4": "RZO", "SP": "SAT",
}

# Subsidiary ICAO codes that share the exact same parent visual logo on stand badges
LOGO_TWIN_CANONICAL_MAP = {
    "EJU": "EZY", "EZS": "EZY",
    "WUK": "WZZ", "WMT": "WZZ", "WAZ": "WZZ",
    "RYS": "RYR", "RUK": "RYR", "MAY": "RYR",
    "SHT": "BAW", "CFE": "BAW", "EFW": "BAW",
    "KLC": "KLM", "KLMX": "KLM",
    "HOP": "AFR", "AFRX": "AFR",
    "CLH": "DLH", "LHX": "DLH",
    "EAI": "EIN", "EAG": "EIN",
    "IBS": "IBE", "ANE": "IBE",
    "NSZ": "NAX", "NOZ": "NAX", "IBK": "NAX",
    "TUI": "TOM", "TFL": "TOM", "BLX": "TOM",
    "ENY": "AAL", "JIA": "AAL", "PDT": "AAL",
    "EDV": "DAL",
    "SKW": "UAL", "RPA": "UAL", "GJS": "UAL", "ASH": "UAL",
    "JZA": "ACA", "ROU": "ACA",
    "QLK": "QFA",
    "CAJ": "FWI",
    "SAT": "RZO",
}

# Known defunct / ceased / sanctioned airline codes frequently leftover in older GSX .ini profiles
DEFUNCT_GSX_AIRLINES = {
    "ADR", "AFL", "ABB", "ABW", "BER", "MON", "TCX", "WOW", "BEE",
    "AWE", "COA", "NWA", "TWA", "SAB", "CSA", "AUI", "IGD", "SDM",
}


def _interleave_weighted_slots(items_with_counts):
    """
    Given a list of `(airline_code, slot_count)` pairs, returns a round-robin interleaved list
    so that every airline appears in the first N positions before any high-frequency airline repeats.
    This prevents narrow stand-number ranges (e.g. Gate C 1..C 8) from starving airlines later in the list.
    """
    if not items_with_counts:
        return []
    max_c = max((cnt for _, cnt in items_with_counts), default=1)
    interleaved = []
    for r in range(max_c):
        for code, cnt in items_with_counts:
            if r < cnt:
                interleaved.append(code)
    return interleaved


def clean_and_normalize_gsx_airline_codes(raw_input, collapse_logo_twins=False):
    """
    Cleans and normalizes raw `airlinecodes` from a GSX .ini section (or list):
      - Supports both comma-separated and space/semicolon-separated strings (e.g. 'IBE ANE').
      - Removes ground handling / catering names (Menzies, Swissport, _SWP, dnata, Servair, Gate Gourmet, etc.).
      - Converts 2-letter IATA codes or full names (LA, LATAM, G3, AR) to 3-letter ICAO codes.
      - Optionally collapses subsidiary codes that share the exact same visual logo (EJU->EZY, WMT->WZZ, etc.).
    """
    if not raw_input:
        return []
    if isinstance(raw_input, str):
        s_clean = re.sub(
            r'\b(?:gate\s+gourmet|red\s+handlin\w*|avia\s*partner|dhl_white|swissport|menzies|servair|samsic|dnata|celebi|fraport)\b',
            ' ',
            raw_input,
            flags=re.IGNORECASE,
        )
        tokens = [t.strip() for t in re.split(r'[,;\s]+', s_clean) if t.strip()]
    elif isinstance(raw_input, (list, tuple, set)):
        tokens = []
        for item in raw_input:
            if isinstance(item, str):
                for sub in re.split(r'[,;\s]+', item.strip()):
                    if sub.strip():
                        tokens.append(sub.strip())
    else:
        return []

    result = []
    for tok in tokens:
        t_up = tok.strip().upper().strip("_")
        if not t_up or t_up in GSX_NON_AIRLINE_TOKENS or tok.strip().upper() in GSX_NON_AIRLINE_TOKENS:
            continue
        if t_up in GSX_TOKEN_TO_ICAO_MAP:
            c = GSX_TOKEN_TO_ICAO_MAP[t_up]
        else:
            c = normalize_airline_icao(t_up)
        if not c or c in GSX_NON_AIRLINE_TOKENS or len(c) != 3 or not c.isalpha():
            continue
        if collapse_logo_twins:
            c = LOGO_TWIN_CANONICAL_MAP.get(c, c)
        if c not in result:
            result.append(c)
    return result


def infer_stand_airlines(
    icao,
    stand_ref,
    terminal_name="",
    explicit_airlines=None,
    is_cargo=False,
    is_ga=False,
    is_military=False,
    has_jetway=True,
    wingspan=36.0,
    airport_rules=None,
    real_world_airlines=None,
    stand_seq_override=None,
):
    """
    Determines the realistic 1-2 airline ICAO codes operating at a specific gate/stand
    by tempering GSX .ini `explicit_airlines` with real-world airport destination data
    (`real_world_airlines` from Wikipedia + VATSIM/IVAO) and `airlines_terminals.json`.
    """
    icao_u = str(icao or "").strip().upper()
    s_clean = re.sub(r'^(?:GATE|STAND|PARKING|RAMP|DOCK|APRON)\s*', '', str(stand_ref or "").strip().upper()).strip()
    m_num = re.search(r'(\d+)', s_clean)
    num_val = int(m_num.group(1)) if m_num else 0
    m_let = re.match(r'^([A-Z]+)', s_clean.replace(" ", ""))
    let_val = m_let.group(1) if m_let and m_let.group(1) not in ("L", "R", "C", "M") else ""
    if not let_val and m_let and m_let.group(1) in ("C", "M") and re.match(r'^[CM]\s*\d+', s_clean):
        let_val = m_let.group(1)
    term_l = str(terminal_name or "").lower()
    ws = float(wingspan or 36.0)

    # Deterministic block index & sequential stand index (incorporating pier letter so small stand numbers cycle across piers)
    pier_salt = sum(ord(ch) * 5 for ch in let_val) if let_val else 0
    digit_mix = (num_val // 100) * 7 + ((num_val // 10) % 10) * 3 + (num_val % 10)
    if stand_seq_override is not None:
        stand_seq = int(stand_seq_override)
        blk = int(stand_seq_override)
    else:
        blk = (digit_mix + pier_salt) if num_val > 0 else sum(ord(ch) for ch in s_clean)
        stand_seq = (digit_mix + pier_salt) if num_val > 0 else sum(ord(ch) for ch in s_clean)

    rw_map = real_world_airlines if isinstance(real_world_airlines, dict) else {}
    has_rw = len(rw_map) >= 4

    def _rw_score(code):
        if not rw_map:
            return 0
        c_canon = LOGO_TWIN_CANONICAL_MAP.get(code, code)
        sc = int(rw_map.get(code, 0) or 0)
        if c_canon != code:
            sc = max(sc, int(rw_map.get(c_canon, 0) or 0))
        if sc == 0:
            # Check sister airlines (e.g. KLC->KLM, CLH->DLH, EDW->SWR, JAF->TOM, CAJ->FWI)
            for sis in get_sister_airlines(code):
                if sis in rw_map:
                    sc = max(sc, max(1, int(rw_map[sis]) // 2))
        return sc

    def _expand_term_aliases(raw_term_str):
        tl = str(raw_term_str or "").strip().lower()
        if not tl:
            return []
        out = [tl]
        m_t = re.match(r'^(?:terminal|gate|pier|concourse|hall|apron)\s+([a-z0-9]{1,2})$', tl)
        if m_t:
            let_t = m_t.group(1)
            for pfx in ("terminal", "gate", "pier", "concourse", "hall"):
                cand = f"{pfx} {let_t}"
                if cand not in out:
                    out.append(cand)
        return out

    def _term_known_in_rules():
        if not term_l or not airport_rules or not isinstance(airport_rules, dict):
            return False
        rules = airport_rules.get("rules") or {}
        mapping = airport_rules.get("mapping") or {}
        known_terms = set()
        for k, vals in mapping.items():
            for a_k in _expand_term_aliases(k):
                known_terms.add(a_k)
            if isinstance(vals, list):
                for v in vals:
                    for a_v in _expand_term_aliases(v):
                        known_terms.add(a_v)
        if isinstance(rules, dict):
            for r_list in rules.values():
                if isinstance(r_list, list):
                    for rt in r_list:
                        for a_r in _expand_term_aliases(rt):
                            known_terms.add(a_r)
        return any(kt and (kt in term_l or term_l in kt) for kt in known_terms)

    term_is_mapped = _term_known_in_rules()

    def _is_allowed_in_terminal(code):
        """Checks if `airport_rules` explicitly restricts `code` to a OTHER terminal than `term_l`."""
        if not term_is_mapped or not term_l or not airport_rules or not isinstance(airport_rules, dict):
            return True
        rules = airport_rules.get("rules") or {}
        mapping = airport_rules.get("mapping") or {}
        req_terms = rules.get(code)
        if not req_terms or not isinstance(req_terms, list):
            return True
        expanded = []
        for rt in req_terms:
            expanded.extend(_expand_term_aliases(rt))
            for sub_t in mapping.get(rt, []):
                expanded.extend(_expand_term_aliases(sub_t))
        return any(et in term_l or term_l in et for et in expanded if et)

    # Clean explicit GSX / BGL airline codes (filtering out handlers, IATA codes, and twin subsidiary logos)
    cleaned = clean_and_normalize_gsx_airline_codes(explicit_airlines, collapse_logo_twins=True)

    # At French airports (LF*), if both TVF (Transavia France) and TRA (Transavia NL) are listed, collapse TRA into TVF
    if icao_u.startswith("LF") and "TVF" in cleaned and "TRA" in cleaned:
        cleaned = [c for c in cleaned if c != "TRA"]

    # Special handling for Dubai International (OMDB) where GSX profiles copy-paste
    # 'UAE,ACA,UAL,QFA' on all 57 Terminal 3 gates and 118 airlines on all Concourse D gates
    if icao_u == "OMDB":
        if let_val in ("A", "D") or "concourse a" in term_l or "apron a" in term_l or "apron d" in term_l:
            if num_val == 4 and let_val == "A":
                return ["UAE", "QFA"]
            if num_val == 8 and let_val == "D":
                return ["UAE", "ACA"]
            return ["UAE"]
        if let_val in ("B", "F") or "concourse b" in term_l or "concourse c" in term_l or "apron b" in term_l or "apron f" in term_l:
            if num_val in (10, 11) and let_val == "B":
                return ["UAE", "UAL"]
            if num_val == 18 and let_val == "B":
                return ["UAE", "ACA"]
            if num_val == 24 and let_val == "B":
                return ["UAE", "QFA"]
            if num_val in (4, 12) and let_val == "F":
                return ["UAE", "FDB"]
            return ["UAE"]
        if let_val == "C" or "concourse d" in term_l or "apron c" in term_l:
            cd_pool = [
                ["BAW"], ["DLH", "SWR"], ["AFR", "KLM"], ["SIA"], ["CPA"], ["THY"],
                ["SVA"], ["QTR"], ["VIR"], ["AIC", "IGO"], ["FIN", "LOT"], ["MAS"],
                ["ETH"], ["MSR"], ["GFA", "OMA"], ["KAC", "RJA"]
            ]
            return cd_pool[blk % len(cd_pool)]
        if let_val in ("E", "G") or "terminal 2" in term_l or "apron e" in term_l or "apron g" in term_l:
            t2_pool = [["FDB"], ["FDB"], ["FDB"], ["FDB", "PGT"], ["FDB"], ["FDB", "SVA"]]
            return t2_pool[blk % len(t2_pool)]
        if let_val in ("S", "Q", "H") or any(x in term_l for x in ("apron s", "apron q", "apron h", "cargo")):
            cg_pool = [["UAE"], ["FDX"], ["UPS"], ["CLX"], ["DHK"], ["GEC"]]
            return cg_pool[blk % len(cg_pool)]

    if icao_u == "LHBP":
        # Budapest Liszt Ferenc Intl:
        # - Gates 40..49: Terminal 2A (Schengen Jetway Gates: Lufthansa Group, Air France-KLM, LOT, Finnair, SAS)
        # - Gates 30..39: Terminal 2B (Non-Schengen Jetway Gates: British Airways, Turkish, Emirates, Qatar, Air China, Korean Air, El Al, Wizz Air)
        # - Stands R210..R279: Walk-in / Pier 1 Low-Cost Stands (Wizz Air, Ryanair, easyJet, Eurowings, Smartwings, Jet2, Norwegian)
        if s_clean.startswith("R") or not has_jetway or (200 <= num_val <= 299):
            lcc_bud = [["WZZ"], ["RYR"], ["WZZ"], ["RYR"], ["EZY"], ["EWG"], ["TVS"], ["WZZ", "RYR"], ["EXS"], ["NAX"]]
            return lcc_bud[blk % len(lcc_bud)]
        if 40 <= num_val <= 49 or "2a" in term_l:
            t2a_bud = [["DLH", "SWR"], ["AFR", "KLM"], ["DLH", "AUA"], ["LOT"], ["SWR", "BEL"], ["FIN", "SAS"], ["EWG"]]
            return t2a_bud[blk % len(t2a_bud)]
        if 30 <= num_val <= 39 or "2b" in term_l:
            t2b_bud = [["BAW"], ["THY"], ["UAE"], ["QTR"], ["WZZ"], ["CCA"], ["EIN"], ["BAW", "FIN"]]
            return t2b_bud[blk % len(t2b_bud)]

    # 1. Explicit GSX .ini stand airline codes — Tempered by Real-World Verification
    if cleaned:
        # Step 1a: Always strip known defunct/ceased airlines (ADR, AFL, ABB, BER, etc.) from multi-airline lists.
        # Only prune by `_rw_score(c) > 0` on large catch-all lists (> 12 airlines, e.g. 45-airline alphabetical dumps),
        # so curated pier lists (<= 12 airlines, like LFPO Orly 4 / Pier P) never lose legitimate specialized carriers!
        if len(cleaned) >= 2:
            non_defunct = [c for c in cleaned if c not in DEFUNCT_GSX_AIRLINES or _rw_score(c) > 0]
            if non_defunct:
                cleaned = non_defunct
        if has_rw and len(cleaned) > 12:
            active_in_rw = [c for c in cleaned if _rw_score(c) > 0]
            if len(active_in_rw) >= 3:
                cleaned = active_in_rw

        # Step 1b: On large catch-all lists (> 10 airlines), filter out airlines that `airlines_terminals.json`
        # explicitly assigns exclusively to a different terminal at this airport
        if len(cleaned) > 10 and term_is_mapped:
            term_compatible = [c for c in cleaned if _is_allowed_in_terminal(c)]
            if len(term_compatible) >= 2:
                cleaned = term_compatible

        # Step 1c: Re-rank GSX list by real-world flight/destination volume at `icao`
        # (fixes alphabetical GSX lists like EDDM 'ACA,ADR,AEA...DLH', EBBR 'AFL,DAH...BEL', LPPT 'AEE,EIN...TAP')
        if has_rw and len(cleaned) >= 2:
            orig_order = {c: idx for idx, c in enumerate(cleaned)}
            cleaned = sorted(cleaned, key=lambda c: (-_rw_score(c), orig_order[c]))

        if len(cleaned) == 1:
            return cleaned

        if len(cleaned) == 2:
            c1, c2 = cleaned[0], cleaned[1]
            w1, w2 = max(1, _rw_score(c1)), max(1, _rw_score(c2))
            # If c1 dominates c2 by >= 6:1 in real life at this airport, show c1 alone on most stands
            if has_rw and w1 >= 6 * w2:
                return [c1, c2] if (stand_seq % 5 == 0) else [c1]
            return [c1, c2]

        # Step 1d: 3+ airlines in GSX list — check if this is a large catch-all hub dump (>= 12 airlines)
        # vs. a curated shared multi-airline pier (3..11 airlines explicitly chosen for that pier by the GSX author).
        c_top = cleaned[0]
        partners = cleaned[1:]
        if has_rw and len(cleaned) >= 12:
            weights = [max(1, _rw_score(c)) for c in cleaned]
            total_w = sum(weights)
            top_share = weights[0] / max(1, total_w)
            is_dedicated_hub = top_share >= 0.65 and weights[0] >= 35
            is_primary_hub = (top_share >= 0.50 and weights[0] >= 28) or (weights[0] >= 45 and weights[0] >= 3.0 * weights[1])
        else:
            is_dedicated_hub = False
            is_primary_hub = False

        if is_dedicated_hub:
            # Dedicated Hub Terminal (e.g. DLH at EDDM T2, UAE at OMDB T3, FIN at EFHK):
            # Show the hub carrier alone on ~75-85% of gates, and pair with a rotating partner on ~15-25%
            solo_mod = 5 if top_share >= 0.75 else 3
            if (stand_seq % solo_mod) == 0 and partners:
                top_partners = partners[:min(10, len(partners))]
                partner = top_partners[(stand_seq // solo_mod) % len(top_partners)]
                return [c_top, partner]
            return [c_top]

        if is_primary_hub and partners:
            # Primary Hub Carrier sharing a pier with visiting airlines (e.g. BEL at EBBR Pier A, TAP at LPPT T1, SAS at EKCH):
            top_partners = partners[:min(12, len(partners))]
            p1 = top_partners[stand_seq % len(top_partners)]
            if (stand_seq % 3) == 0:
                return [c_top]
            if (stand_seq % 3) == 1:
                return [c_top, p1]
            if len(top_partners) >= 2 and (stand_seq % 6) == 2:
                p2 = top_partners[(stand_seq + 1) % len(top_partners)]
                if p2 != p1:
                    return [p1, p2]
            return [p1]

        # Shared Multi-Airline Pier (e.g. LFPO Gates A/B/C/P/R/S/T/U/V, EBBR Pier B, EHAM Pier D, LSGG, EGKK):
        # Preserve ALL airlines in `cleaned` (never drop unbranded regional/leisure carriers) and interleave
        # slots round-robin so every airline on the pier is guaranteed to appear across consecutive stands!
        pool_src = cleaned[:18]
        is_curated_pier = len(pool_src) <= 12
        items_with_counts = []
        for idx_c, c in enumerate(pool_src):
            w_c = _rw_score(c)
            if is_curated_pier:
                # On curated pier lists (<= 12 airlines), keep slot weights balanced (1..2) so all carriers appear
                n_slots = 2 if (w_c >= 15 or idx_c < 2) else 1
            elif has_rw:
                n_slots = 4 if w_c >= 50 else (3 if w_c >= 25 else (2 if w_c >= 8 else 1))
            else:
                n_slots = 2 if idx_c < 3 else 1
            items_with_counts.append((c, n_slots))

        interleaved_slots = _interleave_weighted_slots(items_with_counts) or pool_src
        c1 = interleaved_slots[stand_seq % len(interleaved_slots)]
        if (stand_seq % 2 == 0) and len(pool_src) >= 3:
            c2 = pool_src[(stand_seq + 1) % len(pool_src)]
            if c2 == c1:
                c2 = pool_src[(stand_seq + 2) % len(pool_src)]
            if c2 != c1:
                return [c1, c2]
        return [c1]

    cargo_only_set = {
        "FDX", "UPS", "DHL", "BCS", "DHK", "CLX", "ICV", "BOX", "GTI",
        "CKS", "PAC", "ABX", "GEC", "MPH", "NCA", "SQC", "CKK"
    }

    # 2. Cargo / GA / Military
    if is_cargo or "cargo" in term_l or "fret" in term_l:
        rw_cargo = [[c] for c, cnt in sorted(rw_map.items(), key=lambda x: -x[1]) if c in cargo_only_set and cnt > 0]
        cargo_pool = rw_cargo if len(rw_cargo) >= 2 else [["FDX"], ["DHK"], ["UPS"], ["CLX"], ["GEC"], ["BOX"]]
        return cargo_pool[blk % len(cargo_pool)]
    if is_ga or "general aviation" in term_l or "business" in term_l or "affaires" in term_l:
        return ["NJE"]
    if is_military:
        return []

    # 3. Airport-Specific Real-World Pier & Stand-Sector Allocations (for stands without explicit GSX airlinecodes)
    if icao_u == "LFPO":
        # Paris-Orly (for stands where GSX .ini left airlinecodes empty: Gates E, F, G, M, N, Q)
        if let_val in ("F", "Q", "R", "S") or "orly 4" in term_l:
            orly4_pool = [
                ["FWI"], ["CRL"], ["FBU"], ["FWI", "CRL"], ["FBU", "FWI"],
                ["DJT"], ["DAH"], ["RAM"], ["TAR"], ["CRL", "FBU"],
            ]
            return orly4_pool[stand_seq % len(orly4_pool)]
        if let_val in ("B", "C") or "orly 2" in term_l or "orly 1b" in term_l:
            orly2_pool = [
                ["FWI"], ["CRL"], ["FBU"], ["DJT"], ["AFR"],
                ["DAH"], ["RAM"], ["TAR"], ["TVF"],
            ]
            return orly2_pool[stand_seq % len(orly2_pool)]
        if let_val in ("A", "P", "N") or "orly 1" in term_l:
            orly1_pool = [
                ["EZY"], ["VLG"], ["VOE"], ["EZY", "VOE"], ["VLG", "VOE"],
                ["IBE"], ["TAP"], ["AEA"], ["CLG"], ["TJT"], ["AEH"],
            ]
            return orly1_pool[stand_seq % len(orly1_pool)]
        # Orly 3 (Gates D, E, G, M, T, U, V): Transavia France main hub + Air France & Air Corsica
        orly3_pool = [
            ["TVF"], ["TVF"], ["AFR"], ["TVF", "AFR"], ["CCM"],
            ["TVF"], ["AFR", "CCM"], ["TVF", "EZY"],
        ]
        return orly3_pool[stand_seq % len(orly3_pool)]

    if icao_u == "EGKK":
        # London Gatwick
        if 551 <= num_val <= 574:
            return ["EZY"]  # North Terminal Pier 5 (100% easyJet)
        if (45 <= num_val <= 59) or (101 <= num_val <= 113) or (680 <= num_val <= 699) or "north" in term_l:
            if num_val in (52, 53, 54, 55, 56, 57, 58, 102, 104, 107, 686, 688) or ws >= 52.0:
                wb_pool = [["UAE"], ["QTR"], ["VIR"], ["TOM"]]
                return wb_pool[blk % len(wb_pool)]
            nt_pool = [["EZY"], ["SWR", "DLH"], ["EZY"], ["AFR"], ["TOM"], ["EZY"], ["KLM"]]
            return nt_pool[blk % len(nt_pool)]
        if 1 <= num_val <= 10:
            p1_pool = [["BAW"], ["EIN"], ["TAP"], ["BAW"]]
            return p1_pool[blk % len(p1_pool)]
        if (11 <= num_val <= 28) or (111 <= num_val <= 128):
            p2_pool = [["BAW"], ["BAW", "VLG"], ["BAW", "IBE"], ["BAW"], ["THY"], ["BAW"]]
            return p2_pool[blk % len(p2_pool)]
        if (31 <= num_val <= 38) or (331 <= num_val <= 338):
            p3_pool = [["RYR"], ["WZZ"], ["NAX"], ["RYR"], ["EZY"]]
            return p3_pool[blk % len(p3_pool)]
        rem_pool = [["EZY"], ["BAW"], ["TOM"], ["RYR"]]
        return rem_pool[blk % len(rem_pool)]

    if icao_u == "LSGG":
        # Geneva Cointrin
        if (31 <= num_val <= 36 and let_val == "B") or (not has_jetway and 31 <= num_val <= 36):
            return ["EZY"]
        if let_val == "F" or (61 <= num_val <= 68):
            fr_pool = [["AFR"], ["AFR", "EZY"], ["AFR"]]
            return fr_pool[blk % len(fr_pool)]
        if "non-schengen" in term_l or "non schengen" in term_l or "east wing" in term_l or let_val == "C" or (14 <= num_val <= 20) or (160 <= num_val <= 199):
            if num_val in (17, 18, 30, 190, 191, 192, 193, 194, 195) or ws >= 52.0:
                wb_pool = [["SWR"], ["UAE"], ["QTR"], ["BAW"], ["ETH"], ["UAL"]]
                return wb_pool[blk % len(wb_pool)]
            ns_pool = [["SWR"], ["BAW"], ["EZY"], ["SWR", "THY"], ["BAW", "EIN"], ["SWR"]]
            return ns_pool[blk % len(ns_pool)]
        if "satellite" in term_l or let_val == "B" or (21 <= num_val <= 36) or (83 <= num_val <= 84) or (121 <= num_val <= 127):
            sat_pool = [["EZY"], ["SWR"], ["EZY", "SWR"], ["EZY"]]
            return sat_pool[blk % len(sat_pool)]
        main_pool = [["SWR"], ["SWR", "DLH"], ["EZY"], ["SWR"], ["KLM", "AFR"], ["IBE", "TAP"], ["SWR", "AUA"]]
        return main_pool[blk % len(main_pool)]

    if icao_u == "LSZH":
        # Zurich Kloten
        if let_val == "A" or "terminal a" in term_l:
            ta_pool = [["SWR"], ["SWR", "DLH"], ["SWR", "AUA"], ["SWR"], ["EWG"], ["TAP"]]
            return ta_pool[blk % len(ta_pool)]
        if let_val == "B" or "terminal b" in term_l:
            tb_pool = [["SWR"], ["SWR", "EDW"], ["AFR", "KLM"], ["IBE", "VLG"], ["SWR"], ["SAS"]]
            return tb_pool[blk % len(tb_pool)]
        if let_val == "D" or "terminal d" in term_l:
            td_pool = [["SWR"], ["BAW"], ["EZY"], ["THY"], ["EIN"], ["SWR", "EDW"]]
            return td_pool[blk % len(td_pool)]
        if let_val == "E" or "terminal e" in term_l:
            te_pool = [["SWR"], ["SWR", "EDW"], ["UAE"], ["QTR"], ["UAL", "DAL"], ["SIA"], ["SWR"]]
            return te_pool[blk % len(te_pool)]
        rem_pool = [["SWR"], ["EDW"], ["SWR", "DLH"], ["EZY"]]
        return rem_pool[blk % len(rem_pool)]

    if icao_u == "LFPG":
        # Paris CDG
        if let_val in ("E", "F", "G", "K", "L", "M") or any(x in term_l for x in ("2e", "2f", "2g", "terminal e", "terminal f", "terminal g", "terminal k", "terminal l", "terminal m")):
            af_pool = [["AFR"], ["AFR", "KLM"], ["AFR", "DAL"], ["AFR"], ["AFR", "HOP"]]
            return af_pool[blk % len(af_pool)]
        if let_val in ("A", "B", "C", "D") or any(x in term_l for x in ("2a", "2b", "2c", "2d", "terminal a", "terminal b", "terminal c", "terminal d")):
            t2_pool = [["EZY"], ["BAW"], ["AAL"], ["EIN", "FIN"], ["EZY"]]
            return t2_pool[blk % len(t2_pool)]
        if let_val in ("H", "I", "J") or "terminal 3" in term_l:
            t3_pool = [["TVF"], ["VLG"], ["TRA"], ["EZY"]]
            return t3_pool[blk % len(t3_pool)]
        t1_pool = [["DLH", "SWR"], ["UAE"], ["QTR"], ["UAL", "ACA"], ["THY"], ["SIA"], ["AUA", "SAS"]]
        return t1_pool[blk % len(t1_pool)]

    if icao_u == "EDDF":
        if let_val in ("A", "B", "C", "Z", "F") or "terminal 1" in term_l:
            lh_pool = [["DLH"], ["DLH", "SWR"], ["DLH", "AUA"], ["UAL", "ACA"], ["DLH"], ["SIA", "ANA"], ["THY"]]
            return lh_pool[blk % len(lh_pool)]
        t2_pool = [["BAW", "IBE"], ["AFR", "KLM"], ["UAE"], ["QTR"], ["AAL", "DAL"], ["CFG", "TUI"], ["EZY"]]
        return t2_pool[blk % len(t2_pool)]

    if icao_u == "EHAM":
        if let_val in ("H", "M"):
            lcc_pool = [["EZY"], ["RYR"], ["TRA"]]
            return lcc_pool[blk % len(lcc_pool)]
        if let_val in ("E", "F", "G") or ws >= 52.0:
            wb_pool = [["KLM"], ["KLM", "DAL"], ["UAE"], ["QTR"], ["SIA"], ["KLM"]]
            return wb_pool[blk % len(wb_pool)]
        if let_val == "D":
            d_pool = [["KLM"], ["BAW"], ["EZY"], ["DLH", "SWR"], ["KLM"], ["EIN"]]
            return d_pool[blk % len(d_pool)]
        bc_pool = [["KLM"], ["KLM", "AFR"], ["KLM", "SAS"], ["IBE", "VLG"], ["KLM"], ["TAP"]]
        return bc_pool[blk % len(bc_pool)]

    if icao_u == "EGLL":
        if 500 <= num_val <= 599 or "terminal 5" in term_l:
            t5_pool = [["BAW"], ["BAW"], ["BAW", "IBE"], ["BAW"]]
            return t5_pool[blk % len(t5_pool)]
        if 400 <= num_val <= 499 or "terminal 4" in term_l:
            t4_pool = [["AFR", "KLM"], ["QTR"], ["ETD"], ["SVA", "RAM"]]
            return t4_pool[blk % len(t4_pool)]
        if 300 <= num_val <= 399 or "terminal 3" in term_l:
            t3_pool = [["VIR", "DAL"], ["AAL"], ["UAE"], ["QFA", "CPA"], ["FIN", "JAL"]]
            return t3_pool[blk % len(t3_pool)]
        t2_pool = [["DLH", "SWR"], ["UAL", "ACA"], ["SAS", "EIN"], ["SIA", "THY"], ["TAP", "AUA"]]
        return t2_pool[blk % len(t2_pool)]

    # 4. Use airlines_terminals.json rules + Real-World Airport Airlines (Wikipedia / VATSIM)
    matched_als = []
    if airport_rules and isinstance(airport_rules, dict):
        mapping = airport_rules.get("mapping") or {}
        rules = airport_rules.get("rules") or {}
        if rules:
            for al_code, req_terms in rules.items():
                if not isinstance(req_terms, list):
                    continue
                expanded = []
                for rt in req_terms:
                    expanded.extend(_expand_term_aliases(rt))
                    for sub_t in mapping.get(rt, []):
                        expanded.extend(_expand_term_aliases(sub_t))
                if term_l and any(et in term_l or term_l in et for et in expanded if et):
                    c_norm = LOGO_TWIN_CANONICAL_MAP.get(normalize_airline_icao(al_code), normalize_airline_icao(al_code))
                    if c_norm and len(c_norm) == 3 and c_norm not in cargo_only_set and c_norm not in matched_als:
                        matched_als.append(c_norm)
            if not matched_als:
                for al_code in rules.keys():
                    c_norm = LOGO_TWIN_CANONICAL_MAP.get(normalize_airline_icao(al_code), normalize_airline_icao(al_code))
                    if c_norm and len(c_norm) == 3 and c_norm not in cargo_only_set and c_norm not in matched_als:
                        matched_als.append(c_norm)

    is_walkin_remote = (not has_jetway) or ("remote" in term_l) or s_clean.startswith("R")
    lcc_leisure_set = ULTRA_LOW_COST_CARRIERS | LOW_COST_CARRIERS | {"TVS", "TOM", "EXS", "CFG"}

    # Also merge real-world passenger airlines operating at `icao` (filtering out 1-route outliers when main operators exist)
    if has_rw:
        multi_route_cnt = sum(1 for c, cnt in rw_map.items() if cnt >= 2 and c not in cargo_only_set)
        min_rw_cnt = 2 if multi_route_cnt >= 5 else 1
        for rw_c, cnt in sorted(rw_map.items(), key=lambda x: -x[1]):
            if cnt < min_rw_cnt:
                continue
            c_norm = LOGO_TWIN_CANONICAL_MAP.get(normalize_airline_icao(rw_c), normalize_airline_icao(rw_c))
            if not (c_norm and len(c_norm) == 3 and c_norm not in cargo_only_set and c_norm not in matched_als):
                continue
            if _is_allowed_in_terminal(c_norm) or (is_walkin_remote and c_norm in lcc_leisure_set):
                matched_als.append(c_norm)

    if matched_als:
        if has_rw:
            orig_ord = {c: idx for idx, c in enumerate(matched_als)}
            matched_als = sorted(matched_als, key=lambda c: (-_rw_score(c), orig_ord[c]))
        # On walk-in / remote passenger stands without jetways (e.g. R210-R279), prioritize Low-Cost / Leisure operators
        if is_walkin_remote:
            lcc_als = [c for c in matched_als if c in lcc_leisure_set]
            if len(lcc_als) >= 2:
                matched_als = lcc_als
        items_m = []
        for idx_m, mc in enumerate(matched_als[:12]):
            w_m = _rw_score(mc)
            slots = 3 if w_m >= 40 else (2 if (w_m >= 12 or idx_m < 2) else 1)
            items_m.append((mc, slots))
        weighted_pool = _interleave_weighted_slots(items_m) or matched_als
        primary = weighted_pool[stand_seq % len(weighted_pool)]
        if (stand_seq % 3 == 1) and len(matched_als) >= 3:
            sec = matched_als[(stand_seq + 1) % min(8, len(matched_als))]
            if sec != primary:
                return [primary, sec]
        return [primary]

    # 5. Country / Regional ICAO Prefix Pool
    p2 = icao_u[:2]
    if p2 in COUNTRY_AIRLINE_POOLS:
        pool = COUNTRY_AIRLINE_POOLS[p2]
        return pool[blk % len(pool)]
    p1 = icao_u[:1]
    if p1 == "K":
        us_pool = [["AAL"], ["DAL"], ["UAL"], ["SWA"], ["JBU"], ["ASA"]]
        return us_pool[blk % len(us_pool)]
    if p1 == "C":
        ca_pool = [["ACA"], ["WJA"], ["TSC"]]
        return ca_pool[blk % len(ca_pool)]

    default_pool = [["DLH"], ["AFR"], ["BAW"], ["SWR"], ["EZY"], ["KLM"]]
    return default_pool[blk % len(default_pool)]


def is_freighter_aircraft(ac_icao, ac_name=""):
    if not ac_icao: ac_icao = ""
    if not ac_name: ac_name = ""
    ac_icao_u = str(ac_icao).upper().strip()
    ac_name_u = str(ac_name).upper().strip()

    cargo_icaos = {
        "B77F", "A332F", "B748F", "B744F", "B742F", "B738F", "B738BCF", "B733F", "B734F",
        "B752F", "B763F", "B762F", "MD11F", "A306F", "A310F", "A321F", "A320F", "A330F",
        "AN124", "AN225", "AN12", "AN26", "AN72", "C17", "C130", "IL76", "AT7F", "AT4F",
        "DC10F", "L1011F", "B707F", "DC8F"
    }
    if ac_icao_u in cargo_icaos:
        return True

    if (ac_icao_u.endswith("F") and len(ac_icao_u) >= 4) or any(k in ac_icao_u for k in ("BCF", "P2F", "BDSF")):
        return True

    cargo_keywords = ("BCF", "P2F", "BDSF", "FREIGHTER", "CARGO", "ALL-CARGO", "PACK", "FEDEX", "UPS", "DHL", "CARGO-F", "FREIGHT")
    if (ac_name_u.endswith("F") and len(ac_name_u) >= 4) or any(k in ac_name_u for k in cargo_keywords):
        return True

    return False

def is_a380_aircraft(ac_icao, ac_name="", base_type=""):
    if not ac_icao: ac_icao = ""
    if not ac_name: ac_name = ""
    if not base_type: base_type = ""
    
    icao_u = str(ac_icao).upper().strip()
    name_u = str(ac_name).upper().strip()
    base_u = str(base_type).upper().strip()
    
    if icao_u in {"A388", "A380", "A388F", "A389"}:
        return True
    if base_u in {"A388", "A380", "A388F", "A389"}:
        return True
    if "A380" in icao_u or "A380" in name_u or "A380" in base_u or "A388" in name_u:
        return True
    return False

KNOWN_A380_AIRPORTS = {
    # Europe
    "LFPG", "EGLL", "EDDF", "EDDM", "EHAM", "LEMD", "LEBL", "LIRF", "LIMC", "LOWW",
    "LSZH", "EBBR", "EGCC", "EKCH", "ENGM", "ESSA", "UUEE", "UUDD", "LFSB", "LFLL", "LFBO",
    # Middle East & Africa
    "OMDB", "OTHH", "OMAA", "OEDF", "OEJN", "OEMA", "ORER", "HECA", "HAAB", "HKJK",
    "FAOR", "OBBI", "OKBK", "DGAA", "OIFM", "OIII",
    # Americas
    "KJFK", "KLAX", "KSFO", "KORD", "KMIA", "KBOS", "KIAD", "KATL", "KDFW", "KHOU",
    "CYYZ", "CYVR", "SBGR", "SBGL", "SKBO", "SPJC", "SEQM", "MPTO",
    # Asia & Oceania
    "WSSS", "RJTT", "RJAA", "RJBB", "RKSI", "YSSY", "YMML", "YBBN", "YPAD", "NZAA",
    "VHHH", "VTBS", "WMKK", "VIDP", "VABB", "VOBL", "VOMM", "VCCC", "WIII", "RPLL",
    "RCSS", "RCTP", "ZBAA", "ZGSZ", "ZSPD", "ZGHA", "ZPPP", "ZUCK", "NFFN"
}

def is_ga_ramp_gate(name, terminal="", g_type="", is_cargo=False):
    if is_cargo:
        return False
    name_lower = name.lower()
    term_lower = (terminal or '').lower()
    g_type_lower = (g_type or '').lower()
    
    if "cargo" in name_lower or "cargo" in term_lower or "cargo" in g_type_lower:
        return False

    for text in (name_lower, term_lower):
        if "general aviation" in text or "private" in text or "small" in text or "prop" in text:
            return True
        words = re.split(r'[\s\-_]', text)
        if "ga" in words or "mil" in words:
            return True
        for w in words:
            if (w.startswith("ga") or w.startswith("mil")) and len(w) > 2 and w[2].isdigit():
                return True

    if g_type_lower in ("ga_ramp", "ramp_ga", "small_ramp"):
        return True
        
    return False


def are_mars_related_stands(name_a, name_b, dist_m, user_wingspan=36.0):
    """
    Determines whether stand `name_b` at distance `dist_m` (meters) from `name_a`
    is an overlapping / MARS (Multiple Aircraft Ramp System) twin or triple stand
    whose occupancy physically conflicts with an aircraft of `user_wingspan` on `name_a`.
    Examples:
      - LFPO Orly: A4 <-> A41, A3 <-> A31
      - Letter-suffixed split stands: 10 <-> 10L / 10R, E14 <-> E14A / E14B
      - Geometric wingtip collision overlap (< max(36.5m, user_wingspan/2 + 18.5m))
    """
    if dist_m is None or dist_m <= 0.2:
        return False
    tok_a = clean_gate_token(name_a)
    tok_b = clean_gate_token(name_b)
    if not tok_a or not tok_b or tok_a == tok_b:
        return False

    try:
        ws = float(user_wingspan or 36.0)
    except (ValueError, TypeError):
        ws = 36.0
    half_u = max(17.5, ws * 0.5)
    geom_overlap_m = max(36.5, half_u + 18.5)
    if dist_m <= geom_overlap_m:
        return True

    m_a = re.match(r'^([A-Z]*)(\d+)([A-Z]*)$', tok_a)
    m_b = re.match(r'^([A-Z]*)(\d+)([A-Z]*)$', tok_b)
    if m_a and m_b:
        pa, da, sa = m_a.groups()
        pb, db, sb = m_b.groups()
        if pa == pb:
            # 1. Same base number with L/R/A/B/C suffix (e.g. 12 vs 12L/12R, A4 vs A4A)
            if da == db and dist_m <= 65.0:
                return True
            # 2. Parent number vs sub-digit stand (e.g. A4 vs A41/A42, A3 vs A31/A32)
            if ((len(db) == len(da) + 1 and db.startswith(da)) or (len(da) == len(db) + 1 and da.startswith(db))) and dist_m <= 55.0:
                return True
            # 3. Sub-stands sharing the same parent prefix digit on the same bay (e.g. A41 vs A42)
            if len(da) >= 2 and len(db) == len(da) and da[:-1] == db[:-1]:
                try:
                    if abs(int(da) - int(db)) == 1 and dist_m <= 42.0:
                        return True
                except ValueError:
                    pass
    return False


class SimConnectManager:
    def __init__(self, backend):
        self.backend = backend
        self.connected = False
        self.sm = None
        self.user_lat = None
        self.user_lon = None
        self.user_hdg = None
        self.user_gs = None
        self.user_on_ground = None
        self.user_engines_running = None
        self.in_menu = False
        self.dep_gate_name = None
        self.dep_coords = None
        self.dep_mars_stands = []
        self.dep_user_was_parked = False
        self.arr_gate_name = None
        self.arr_coords = None
        self.arr_mars_stands = []
        self.arr_icao = None
        self.arr_protected_history = []
        self.user_wingspan = 36.0
        self.dep_loop_active = False
        self.arr_loop_active = False
        self.dep_cleared = False
        self.arr_cleared = False
        self.ai_def_id = None
        self.ai_evict_def_id = None
        self.user_object_id = None
        self.req_id_counter = 1000
        self.lock = threading.Lock()
        self._last_check_time = 0
        self._active_query_req_id = None
        self._active_query_target_coords = None
        self._active_query_mars_stands = []
        self._lvar_write_queue = []
        self._event_write_queue = []
        self._lvar_def_ids = {}
        self._lvar_next_def_id = 900
        self.gsx_lvars = {
            "couatl_started": 0.0,
            "couatl_alive": 0.0,
            "menu_open": 0.0,
            "menu_choice": -2.0,
            "search_gen": 0.0,
        }
        self.gsx_dd = None
        self._msfs_was_running = False

        self._log("SimConnectManager initialized.")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _is_msfs_process_running(self) -> bool:
        try:
            import ctypes
            from ctypes import wintypes
            TH32CS_SNAPPROCESS = 0x00000002

            class PROCESSENTRY32W(ctypes.Structure):
                _fields_ = [
                    ("dwSize", wintypes.DWORD),
                    ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260),
                ]

            k32 = ctypes.windll.kernel32
            h_snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if h_snap == -1 or h_snap is None:
                return False
            try:
                pe = PROCESSENTRY32W()
                pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
                if k32.Process32FirstW(h_snap, ctypes.byref(pe)):
                    while True:
                        exe_name = (pe.szExeFile or "").lower()
                        if exe_name in ("flightsimulator2024.exe", "flightsimulator.exe"):
                            return True
                        if not k32.Process32NextW(h_snap, ctypes.byref(pe)):
                            break
            finally:
                k32.CloseHandle(h_snap)
            return False
        except Exception:
            return False

    def _check_auto_quit_if_msfs_closed(self):
        try:
            if not self.backend.config.settings.get("auto_quit_with_msfs", False):
                return
            if self._is_msfs_process_running():
                self._msfs_was_running = True
                return
            if self._msfs_was_running:
                time.sleep(2.0)
                if not self._is_msfs_process_running() and self.backend.config.settings.get("auto_quit_with_msfs", False):
                    self._log("MSFS process closed and auto_quit_with_msfs is enabled. Exiting GateFinder...")
                    os._exit(0)
        except Exception:
            pass

    def set_lvar(self, lvar_name: str, value: float):
        if not lvar_name:
            return
        with self.lock:
            self._lvar_write_queue.append((str(lvar_name), float(value)))

    def set_lvars_batch(self, pairs):
        if not pairs:
            return
        with self.lock:
            for name, val in pairs:
                if name:
                    self._lvar_write_queue.append((str(name), float(val)))

    def send_sim_event(self, event_name: str, data: int = 0):
        if not event_name:
            return
        with self.lock:
            self._event_write_queue.append((str(event_name), int(data)))

    def close_gsx_panel(self, cancel_choice: bool = False):
        """
        Hides the in-sim GSX Pro panel window (`FSDT_GSX_Panel.js`) by firing
        `EXTERNAL_SYSTEM_TOGGLE = 2` (`EXTERNAL_SYSTEM_TOGGLE_HIDE_MENU`), which
        directly invokes `this.hideMenu()` (`this.ingameUi.style.display = "none"`),
        and resets `L:FSDT_GSX_MENU_OPEN = 0`.
        """
        if cancel_choice:
            self.set_lvar("L:FSDT_GSX_MENU_CHOICE", -1.0)
        self.set_lvar("L:FSDT_GSX_MENU_OPEN", 0.0)
        self.send_sim_event("EXTERNAL_SYSTEM_TOGGLE", 2)

    def write_gsx_string_slot(self, slot_name: str, text: str, max_chunks: int = 22):
        """
        Encodes `text` using GSX Pro v3's Base64 StringSlot protocol (`FSDT_GSX_Panel.js`)
        into `L:FSDT_GSX_<slot_name>_B0..B{max_chunks-1}` and `L:FSDT_GSX_<slot_name>_LEN`.
        If `slot_name == 'SEARCH'`, also increments `L:FSDT_GSX_SEARCH_GEN`.
        """
        import base64
        b64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        raw_bytes = (text or "").encode("utf-8")
        b64_str = base64.b64encode(raw_bytes).decode("ascii").rstrip("=")
        str_len = len(b64_str)
        needed_chunks = min(max_chunks, (str_len + 3) // 4)
        prefix = f"L:FSDT_GSX_{slot_name.upper()}"
        batch = []
        for i in range(max_chunks):
            val = 0.0
            if i < needed_chunks:
                base_idx = i * 4
                for j in range(4):
                    if base_idx + j < str_len:
                        ch = b64_str[base_idx + j]
                        c_idx = b64_chars.find(ch)
                        if c_idx > 0:
                            val += float(c_idx) * (64.0 ** j)
            batch.append((f"{prefix}_B{i}", val))
        batch.append((f"{prefix}_LEN", float(str_len)))
        if slot_name.upper() == "SEARCH":
            next_gen = float(int(self.gsx_lvars.get("search_gen", 0.0)) + 1)
            self.gsx_lvars["search_gen"] = next_gen
            batch.append(("L:FSDT_GSX_SEARCH_GEN", next_gen))
        self.set_lvars_batch(batch)

    def _flush_lvar_writes(self):
        if not self.connected or not self.sm:
            return
        with self.lock:
            if not self._lvar_write_queue and not self._event_write_queue:
                return
            pending = list(self._lvar_write_queue)
            self._lvar_write_queue.clear()
            pending_events = list(self._event_write_queue)
            self._event_write_queue.clear()

        import ctypes
        for lvar_name, val in pending:
            try:
                def_id = self._lvar_def_ids.get(lvar_name)
                if def_id is None:
                    def_id = self._lvar_next_def_id
                    self._lvar_next_def_id += 1
                    self.sm.AddToDataDefinition(def_id, lvar_name, "number", DATATYPE_FLOAT64, 0, 0)
                    self._lvar_def_ids[lvar_name] = def_id
                c_val = ctypes.c_double(float(val))
                self.sm.SetDataOnSimObject(
                    def_id,
                    OBJECT_ID_USER,
                    0,
                    0,
                    ctypes.sizeof(ctypes.c_double),
                    ctypes.cast(ctypes.byref(c_val), ctypes.c_void_p)
                )
            except Exception as e:
                self._log(f"LVar write failed for {lvar_name}={val}: {e}")

        for ev_name, ev_data in pending_events:
            try:
                self.sm.send_event(ev_name, int(ev_data))
            except Exception as e:
                self._log(f"SimEvent send failed for {ev_name}={ev_data}: {e}")

    def _log(self, msg):
        import datetime
        try:
            log_file = os.path.join(os.path.dirname(self.backend.config.settings_file), "simconnect_debug.log")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {msg}\n")
        except Exception:
            pass

    def _next_req_id(self):
        self.req_id_counter += 1
        if self.req_id_counter > 999999:
            self.req_id_counter = 1000
        return self.req_id_counter

    def _find_overlapping_mars_stands(self, apt_dict, user_wingspan=36.0):
        if not apt_dict or not isinstance(apt_dict, dict):
            return []
        g_name = str(apt_dict.get("gate") or "").strip()
        g_lat = apt_dict.get("lat")
        g_lon = apt_dict.get("lon")
        icao = str(apt_dict.get("icao") or "").strip().upper()
        if not g_name or g_lat is None or g_lon is None:
            return []
        try:
            g_lat_f = float(g_lat)
            g_lon_f = float(g_lon)
        except (ValueError, TypeError):
            return []

        candidates = {}
        chart_stands = (apt_dict.get("chart_data") or {}).get("stands") or []
        for st in chart_stands:
            s_ref = str(st.get("ref") or st.get("name") or "").strip()
            slat, slon = st.get("lat"), st.get("lon")
            if s_ref and slat is not None and slon is not None:
                tok = clean_gate_token(s_ref)
                if tok and tok not in candidates:
                    candidates[tok] = (s_ref, float(slat), float(slon))

        if icao and hasattr(self, "backend") and self.backend:
            coherent_map = getattr(self.backend, "coherent_airports", {}) or {}
            for db in (coherent_map.get(icao), self.backend.data.get(icao), self.backend.builtin_data.get(icao)):
                if not db or not isinstance(db, dict):
                    continue
                for _, al_list in db.items():
                    if not isinstance(al_list, list):
                        continue
                    for g in al_list:
                        s_ref = str(g.get("name") or "").strip()
                        slat, slon = g.get("lat"), g.get("lon")
                        if s_ref and slat is not None and slon is not None:
                            tok = clean_gate_token(s_ref)
                            if tok and tok not in candidates:
                                candidates[tok] = (s_ref, float(slat), float(slon))

        mars_list = []
        for tok, (s_ref, slat, slon) in candidates.items():
            d_m = self._haversine(g_lat_f, g_lon_f, slat, slon)
            if are_mars_related_stands(g_name, s_ref, d_m, user_wingspan=user_wingspan):
                mars_list.append({
                    "name": s_ref,
                    "lat": slat,
                    "lon": slon,
                    "dist_m": round(d_m, 1)
                })
        mars_list.sort(key=lambda x: x["dist_m"])
        return mars_list

    def register_flight(self, flight_data):
        if not flight_data:
            self._log("register_flight called with no flight data.")
            return
        dep = flight_data.get("departure")
        arr = flight_data.get("arrival")
        try:
            ws = float(flight_data.get("aircraft_wingspan") or 36.0)
        except (ValueError, TypeError):
            ws = 36.0
        with self.lock:
            self.user_wingspan = ws
            self.dep_cleared = False
            self.arr_cleared = False
            self.dep_user_was_parked = False
            if dep and dep.get("gate_coords_found") and dep.get("lat") is not None:
                self.dep_gate_name = dep.get("gate")
                self.dep_coords = (dep.get("lat"), dep.get("lon"))
                self.dep_mars_stands = self._find_overlapping_mars_stands(dep, user_wingspan=ws)
                dep["mars_protected_stands"] = [m["name"] for m in self.dep_mars_stands]
                self.dep_loop_active = True
                mars_names = ", ".join(f"{m['name']} ({m['dist_m']}m)" for m in self.dep_mars_stands) or "none"
                self._log(f"Departure gate registered: {self.dep_gate_name} @ {self.dep_coords} | MARS overlapping stands: {mars_names}")
            else:
                self.dep_coords = None
                self.dep_mars_stands = []
                self.dep_loop_active = False
                self._log("Departure gate not registered (no coordinates).")

            if arr and arr.get("gate_coords_found") and arr.get("lat") is not None:
                arr_icao_cur = str(arr.get("icao") or "").strip().upper()
                if arr_icao_cur != self.arr_icao:
                    self.arr_icao = arr_icao_cur
                    self.arr_protected_history = []
                self.arr_gate_name = arr.get("gate")
                self.arr_coords = (float(arr.get("lat")), float(arr.get("lon")))
                cur_tok = clean_gate_token(self.arr_gate_name or "")
                if cur_tok and not any(clean_gate_token(h.get("name", "")) == cur_tok for h in self.arr_protected_history):
                    self.arr_protected_history.append({
                        "name": self.arr_gate_name,
                        "lat": self.arr_coords[0],
                        "lon": self.arr_coords[1],
                    })
                mars_base = self._find_overlapping_mars_stands(arr, user_wingspan=ws)
                seen_mars_toks = {clean_gate_token(m["name"]) for m in mars_base}
                for h_st in self.arr_protected_history:
                    h_tok = clean_gate_token(h_st["name"])
                    if h_tok and h_tok != cur_tok and h_tok not in seen_mars_toks:
                        seen_mars_toks.add(h_tok)
                        d_hist = self._haversine(self.arr_coords[0], self.arr_coords[1], h_st["lat"], h_st["lon"])
                        mars_base.append({
                            "name": h_st["name"],
                            "lat": h_st["lat"],
                            "lon": h_st["lon"],
                            "dist_m": round(d_hist, 1),
                        })
                self.arr_mars_stands = mars_base
                arr["mars_protected_stands"] = [m["name"] for m in self.arr_mars_stands]
                self.arr_loop_active = True
                self._last_check_time = 0
                mars_names = ", ".join(f"{m['name']} ({m['dist_m']}m)" for m in self.arr_mars_stands) or "none"
                self._log(f"Arrival gate registered: {self.arr_gate_name} @ {self.arr_coords} | Protected/MARS stands: {mars_names}")
            else:
                self.arr_coords = None
                self.arr_mars_stands = []
                self.arr_loop_active = False
                self._log("Arrival gate not registered (no coordinates).")

    def _haversine(self, lat1, lon1, lat2, lon2):
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return float('inf')
        import math
        R = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    def _evict_ai_simobject(self, ai_id: int):
        """
        Removes or teleports an AI aircraft off a protected stand.
        1. Calls `AIRemoveObject` (works for native MSFS traffic).
        2. Calls `SetDataOnSimObject` on `self.ai_evict_def_id` to teleport the aircraft to
           (0.0, 0.0, -20000.0 ft), which bypasses SimConnect's creator-handle restriction
           when the AI aircraft was spawned by an external injector (BeyondATC, FSLTL, AIG).
        """
        import ctypes
        delete_req_id = self._next_req_id()
        try:
            self.sm.AIRemoveObject(ai_id, delete_req_id)
        except Exception:
            pass
        if self.ai_evict_def_id is not None:
            try:
                evict_vec = (ctypes.c_double * 3)(0.0, 0.0, -20000.0)
                self.sm.SetDataOnSimObject(
                    self.ai_evict_def_id,
                    ai_id,
                    0,
                    0,
                    ctypes.sizeof(evict_vec),
                    ctypes.cast(ctypes.byref(evict_vec), ctypes.c_void_p)
                )
            except Exception as ev_err:
                self._log(f"SetDataOnSimObject eviction fallback warning for {ai_id}: {ev_err}")

    def _on_bytype_recv(self, recv) -> bool:
        import ctypes

        with self.lock:
            active_req_id = self._active_query_req_id
            target_coords = self._active_query_target_coords
            target_mars = list(self._active_query_mars_stands or [])
            user_ws = float(self.user_wingspan or 36.0)
            known_user_id = self.user_object_id

        if active_req_id is None or recv.dwRequestID != active_req_id:
            return False

        ai_id = recv.dwObjectID
        if ai_id == 0 or ai_id == OBJECT_ID_USER or (known_user_id is not None and ai_id == known_user_id):
            return True

        offset = RECV_SIMOBJECT_DATA.dwData.offset
        gs_val = 0.0
        is_user_sim = 0
        try:
            ptr_lat = ctypes.cast(ctypes.byref(recv, offset), ctypes.POINTER(ctypes.c_double))
            lat_val = ptr_lat[0]
            offset += ctypes.sizeof(ctypes.c_double)

            ptr_lon = ctypes.cast(ctypes.byref(recv, offset), ctypes.POINTER(ctypes.c_double))
            lon_val = ptr_lon[0]
            offset += ctypes.sizeof(ctypes.c_double)

            try:
                ptr_gs = ctypes.cast(ctypes.byref(recv, offset), ctypes.POINTER(ctypes.c_double))
                gs_val = float(ptr_gs[0])
                offset += ctypes.sizeof(ctypes.c_double)
            except Exception:
                gs_val = 0.0

            try:
                ptr_usr = ctypes.cast(ctypes.byref(recv, offset), ctypes.POINTER(ctypes.c_int32))
                is_user_sim = int(ptr_usr[0])
            except Exception:
                is_user_sim = 0
        except Exception as err:
            self._log(f"Error unpacking AI position: {err}")
            return True

        # Layer 1 self-protection: SimConnect 'IS USER SIM' flag
        if is_user_sim != 0:
            self.user_object_id = ai_id
            return True

        # Layer 2 self-protection: 18.0m radius around the user's live GPS coordinates
        if self.user_lat is not None and self.user_lon is not None:
            u_dist = self._haversine(lat_val, lon_val, self.user_lat, self.user_lon)
            if u_dist < 18.0:
                return True

        if target_coords:
            dist = self._haversine(lat_val, lon_val, target_coords[0], target_coords[1])
            mars_enabled = bool(self.backend.config.settings.get("mars_overlap_protection", True))
            should_delete = False
            delete_reason = ""

            if dist < 25.0:
                should_delete = True
                delete_reason = f"occupying primary gate ({dist:.1f}m away)"
            elif mars_enabled:
                # 1. Check MARS / overlapping twin or triple stands (and previously assigned arrival stands)
                for m_st in target_mars:
                    m_dist = self._haversine(lat_val, lon_val, m_st["lat"], m_st["lon"])
                    if m_dist < 25.0 and gs_val <= 6.0:
                        should_delete = True
                        delete_reason = f"occupying protected/MARS stand {m_st['name']} ({m_dist:.1f}m from {m_st['name']}, {dist:.1f}m from primary)"
                        break
                # 2. Geometric wingtip collision envelope for stationary/parked AI aircraft
                if not should_delete and gs_val <= 2.5:
                    wingtip_envelope_m = max(36.5, (user_ws * 0.5) + 18.5)
                    if dist < wingtip_envelope_m:
                        should_delete = True
                        delete_reason = f"parked inside wingtip overlap zone ({dist:.1f}m < {wingtip_envelope_m:.1f}m, gs={gs_val:.1f}kt)"

            if should_delete:
                self._log(f"Deleting AI aircraft {ai_id} {delete_reason}")
                try:
                    self._evict_ai_simobject(ai_id)
                    if self.dep_loop_active and target_coords == self.dep_coords:
                        self.dep_cleared = True
                        self._log("Cleared departure gate / MARS zone.")
                    elif self.arr_loop_active and target_coords == self.arr_coords:
                        self.arr_cleared = True
                        self._log("Cleared arrival gate / MARS zone.")
                except Exception as ex:
                    self._log(f"Failed to delete AI aircraft {ai_id}: {ex}")
        return True

    def _query_and_clear_gate(self, gate_coords, radius, mars_stands=None):
        if not self.connected or not self.sm or self.ai_def_id is None:
            return
        req_id = self._next_req_id()
        with self.lock:
            self._active_query_req_id = req_id
            self._active_query_target_coords = gate_coords
            self._active_query_mars_stands = list(mars_stands or [])
        try:
            self.sm.RequestDataOnSimObjectType(
                req_id,
                self.ai_def_id,
                int(radius),
                SIMOBJECT_TYPE_AIRCRAFT
            )
        except Exception as e:
            self._log(f"RequestDataOnSimObjectType failed: {e}")

    def _tick(self):
        if not self.dep_coords and not self.arr_coords:
            return
        if not self.backend.config.settings.get("auto_clear_ai", True):
            return

        if self.user_lat is None or self.user_lon is None or self.in_menu:
            return

        now = time.time()
        if now - self._last_check_time < 5.0:
            return
        self._last_check_time = now

        if self.dep_coords and self.dep_loop_active:
            user_dist = self._haversine(self.user_lat, self.user_lon, self.dep_coords[0], self.dep_coords[1])
            if user_dist <= 90.0:
                self.dep_user_was_parked = True
                self._query_and_clear_gate(self.dep_coords, radius=200, mars_stands=self.dep_mars_stands)
            elif self.dep_user_was_parked and user_dist > 150.0:
                self._log(f"User taxied away ({user_dist:.1f}m from departure stand). Deactivating departure loop.")
                self.dep_loop_active = False
            elif not self.dep_user_was_parked and user_dist < 4000.0:
                # Pre-clear departure gate & MARS stands while at the departure airport before/during spawn
                self._query_and_clear_gate(self.dep_coords, radius=4500, mars_stands=self.dep_mars_stands)

        if self.arr_coords and self.arr_loop_active:
            user_dist = self._haversine(self.user_lat, self.user_lon, self.arr_coords[0], self.arr_coords[1])
            if user_dist < 27780.0: # 15 NM
                query_radius = 30000 if user_dist > 500.0 else 500
                self._query_and_clear_gate(self.arr_coords, radius=query_radius, mars_stands=self.arr_mars_stands)

    def _run(self):
        self.user_dd = None
        while True:
            if not self.connected:
                try:
                    self._log("Attempting to connect to MSFS...")
                    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                        try:
                            import shutil
                            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                            for cand_cfg in (
                                os.path.join(exe_dir, "SimConnect.cfg"),
                                os.path.join(os.getcwd(), "SimConnect.cfg"),
                            ):
                                if os.path.isfile(cand_cfg):
                                    for dst_cfg in (
                                        os.path.join(sys._MEIPASS, "SimConnect", "SimConnect.cfg"),
                                        os.path.join(sys._MEIPASS, "SimConnect.cfg"),
                                    ):
                                        shutil.copy2(cand_cfg, dst_cfg)
                                    self._log(f"Loaded custom SimConnect.cfg from {cand_cfg}")
                                    break
                        except Exception:
                            pass
                    DataDefinition._instances.clear()
                    self.sm = SC(name="GateFinder V2.0")
                    self.connected = True
                    self._msfs_was_running = True
                    self._log("Connected to MSFS successfully!")
                    self.sm.add_receiver(RECV_SIMOBJECT_DATA_BYTYPE, self._on_bytype_recv)
                    
                    # Setup AI query definitions (Lat, Lon, Groundspeed, IsUserSim for MARS stationary check)
                    ai_simvars = [
                        {"name": "PLANE LATITUDE", "units": "degrees"},
                        {"name": "PLANE LONGITUDE", "units": "degrees"},
                        {"name": "GROUND VELOCITY", "units": "knots"},
                        {"name": "IS USER SIM", "units": "bool", "dtyp": DATATYPE_INT32}
                    ]
                    ai_dd = DataDefinition.create(self.sm, ai_simvars)
                    self.ai_def_id = ai_dd.id

                    ai_evict_dd = DataDefinition.create(self.sm, [
                        {"name": "PLANE LATITUDE", "units": "degrees"},
                        {"name": "PLANE LONGITUDE", "units": "degrees"},
                        {"name": "PLANE ALTITUDE", "units": "feet"}
                    ])
                    self.ai_evict_def_id = ai_evict_dd.id
                    
                    # Setup User Position & Telemetry subscription (PERIOD_SIM_FRAME w/ interval=4 -> ~15 Hz continuous updates)
                    user_simvars = [
                        {"name": "PLANE LATITUDE", "units": "degrees"},
                        {"name": "PLANE LONGITUDE", "units": "degrees"},
                        {"name": "PLANE HEADING DEGREES TRUE", "units": "degrees"},
                        {"name": "GROUND VELOCITY", "units": "knots"},
                        {"name": "SIM ON GROUND", "units": "bool"},
                        {"name": "GENERAL ENG COMBUSTION:1", "units": "bool"},
                        {"name": "GENERAL ENG COMBUSTION:2", "units": "bool"}
                    ]
                    self.user_dd = self.sm.subscribe_simdata(user_simvars, period=PERIOD_SIM_FRAME, interval=4)
                    self._lvar_def_ids = {}
                    self._lvar_next_def_id = 900
                    try:
                        gsx_defs = [
                            {"name": "L:FSDT_GSX_COUATL_STARTED", "units": "number", "dtyp": DATATYPE_FLOAT64, "epsilon": 0},
                            {"name": "L:FSDT_GSX_COUATL_ALIVE", "units": "number", "dtyp": DATATYPE_FLOAT64, "epsilon": 0},
                            {"name": "L:FSDT_GSX_MENU_OPEN", "units": "number", "dtyp": DATATYPE_FLOAT64, "epsilon": 0},
                            {"name": "L:FSDT_GSX_MENU_CHOICE", "units": "number", "dtyp": DATATYPE_FLOAT64, "epsilon": 0},
                            {"name": "L:FSDT_GSX_SEARCH_GEN", "units": "number", "dtyp": DATATYPE_FLOAT64, "epsilon": 0},
                        ]
                        self.gsx_dd = DataDefinition(self.sm, 850, gsx_defs)
                        self.gsx_dd.add_receiver(self.sm, 850)
                        self.sm.RequestDataOnSimObject(
                            850, 850, OBJECT_ID_USER, PERIOD_SIM_FRAME,
                            DATA_REQUEST_FLAG_CHANGED | DATA_REQUEST_FLAG_TAGGED, 0, 4, 0
                        )
                    except Exception as gsx_err:
                        self.gsx_dd = None
                        self._log(f"GSX LVar subscription warning: {gsx_err}")
                except Exception as e:
                    self.connected = False
                    self.user_dd = None
                    self.gsx_dd = None
                    self.sm = None
                    self._log(f"Connection failed: {e}")
                    self._check_auto_quit_if_msfs_closed()
                    time.sleep(10)
                    continue

            try:
                self._flush_lvar_writes()
                while self.sm.receive(0.01):
                    pass

                if self.gsx_dd and self.gsx_dd.simdata:
                    sd = self.gsx_dd.simdata
                    if "L:FSDT_GSX_COUATL_STARTED" in sd:
                        self.gsx_lvars["couatl_started"] = float(sd.get("L:FSDT_GSX_COUATL_STARTED") or 0.0)
                    if "L:FSDT_GSX_COUATL_ALIVE" in sd:
                        self.gsx_lvars["couatl_alive"] = float(sd.get("L:FSDT_GSX_COUATL_ALIVE") or 0.0)
                    if "L:FSDT_GSX_MENU_OPEN" in sd:
                        self.gsx_lvars["menu_open"] = float(sd.get("L:FSDT_GSX_MENU_OPEN") or 0.0)
                    if "L:FSDT_GSX_MENU_CHOICE" in sd:
                        self.gsx_lvars["menu_choice"] = float(sd.get("L:FSDT_GSX_MENU_CHOICE") if sd.get("L:FSDT_GSX_MENU_CHOICE") is not None else -2.0)
                    if "L:FSDT_GSX_SEARCH_GEN" in sd:
                        self.gsx_lvars["search_gen"] = float(sd.get("L:FSDT_GSX_SEARCH_GEN") or 0.0)
                
                if self.user_dd and self.user_dd.simdata:
                    raw_lat = self.user_dd.simdata.get("PLANE LATITUDE")
                    raw_lon = self.user_dd.simdata.get("PLANE LONGITUDE")
                    raw_hdg = self.user_dd.simdata.get("PLANE HEADING DEGREES TRUE")
                    raw_gs = self.user_dd.simdata.get("GROUND VELOCITY")
                    og = self.user_dd.simdata.get("SIM ON GROUND")
                    og_bool = bool(og) if og is not None else None
                    eng1 = self.user_dd.simdata.get("GENERAL ENG COMBUSTION:1")
                    eng2 = self.user_dd.simdata.get("GENERAL ENG COMBUSTION:2")
                    if eng1 is not None or eng2 is not None:
                        eng_running = bool(eng1) or bool(eng2)
                    else:
                        eng_running = None

                    gs_val = float(raw_gs or 0.0)
                    # Detect MSFS 2020/2024 Main Menu / World Map / Pre-Flight state:
                    # - MSFS 2024 World Map reports dummy coords near (0.0, 90.0) or (0.0, 0.0) with SIM ON GROUND=False, GS=0 kt
                    # - Or SIM ON GROUND is False while stationary/slow (< 35 kt) with engines off
                    is_dummy_coords = (
                        raw_lat is None
                        or raw_lon is None
                        or (abs(float(raw_lat)) < 0.05 and (abs(float(raw_lon)) < 0.05 or abs(abs(float(raw_lon)) - 90.0) < 0.05))
                    )
                    is_menu_state = bool(is_dummy_coords or (og_bool is False and gs_val < 35.0 and not eng_running))
                    self.in_menu = is_menu_state
                    if is_menu_state:
                        self.user_lat = None
                        self.user_lon = None
                        self.user_hdg = raw_hdg
                        self.user_gs = 0.0
                        self.user_on_ground = None
                        self.user_engines_running = False
                    else:
                        self.user_lat = raw_lat
                        self.user_lon = raw_lon
                        self.user_hdg = raw_hdg
                        self.user_gs = gs_val
                        self.user_on_ground = og_bool
                        self.user_engines_running = eng_running
                else:
                    self.in_menu = False
                    self.user_lat = None
                    self.user_lon = None
                    self.user_hdg = None
                    self.user_gs = None
                    self.user_on_ground = None
                    self.user_engines_running = None

                self._tick()
                time.sleep(0.08)
            except Exception as e:
                self._log(f"Exception in run loop: {e}")
                self.connected = False
                self.user_dd = None
                if self.sm:
                    try: self.sm.Close()
                    except Exception: pass
                    self.sm = None
                self._check_auto_quit_if_msfs_closed()
                time.sleep(5)

BGL_PARKING_NAMES = {
    0: "", 1: "PARKING", 2: "N", 3: "NE", 4: "E",
    5: "SE", 6: "S", 7: "SW", 8: "W",
    9: "NW", 10: "", 11: "DOCK",
    12: "A", 13: "B", 14: "C", 15: "D", 16: "E",
    17: "F", 18: "G", 19: "H", 20: "I", 21: "J",
    22: "K", 23: "L", 24: "M", 25: "N", 26: "O",
    27: "P", 28: "Q", 29: "R", 30: "S", 31: "T",
    32: "U", 33: "V", 34: "W", 35: "X", 36: "Y",
    37: "Z"
}

NON_AIRPORT_INI_PREFIXES = (
    "configuration.ini", "flywithlua.ini", "saveinitialassignments.ini",
    "fwl_prefs.ini", "en-us.ini", "fi-fi.ini", "swannsim"
)

def extract_icao_from_filename(filename):
    fn_lower = filename.lower()
    if any(fn_lower.startswith(p) for p in NON_AIRPORT_INI_PREFIXES):
        return None
    base = filename[:-4] if fn_lower.endswith('.ini') else filename
    first4 = base[:4].upper()
    if len(first4) == 4 and first4.isalnum() and first4 != "SCOT":
        return first4
    # Try finding a 4-letter ICAO token separated by _ or -
    for token in re.split(r'[_\-\s]+', base.upper()):
        if len(token) == 4 and token.isalnum() and token not in ("SCOT", "VBLE", "PROF", "TEST", "2020", "2024", "ASVD"):
            return token
    return None

def convert_bgl_entry_to_gate_info(name_idx, number, ptype, radius, lat, lon, has_jw, airlines):
    if ptype in (12, 13): # FUEL, VEHICLES
        return None, []
    prefix_letter = BGL_PARKING_NAMES.get(name_idx, "")
    if prefix_letter in ("PARKING", "DOCK", ""):
        name = f"{number}"
    else:
        name = f"{prefix_letter} {number}"

    g_type = "GATE"
    is_cargo = False
    is_ga = False
    is_military = False

    if ptype in (1, 2, 3, 4, 14):
        g_type = "STAND"
        if ptype in (1, 2, 3):
            is_ga = True
    elif ptype == 5:
        g_type = "RAMP"
        is_cargo = True
    elif ptype in (6, 7):
        g_type = "RAMP"
        is_military = True
    elif ptype in (8, 9, 10, 15):
        g_type = "GATE"
    elif ptype == 11:
        g_type = "DOCK"
        is_ga = True

    if ptype in (14, 15) or radius >= 35.0:
        wingspan = max(round(radius * 2.0, 2), 80.0)
    elif ptype == 10 or radius >= 27.0 or (ptype == 5 and radius >= 25.0):
        wingspan = max(round(radius * 2.0, 2), 68.5)
    elif ptype == 9:
        wingspan = max(round(radius * 2.0, 2), 46.0)
    elif ptype == 8:
        wingspan = max(round(radius * 2.0, 2), 36.0)
    else:
        wingspan = max(round(radius * 2.0, 2), 20.0)

    al_clean = [a.strip().upper() for a in (airlines or []) if a and str(a).strip()]
    gate_info = {
        'name': name,
        'wingspan': wingspan,
        'terminal': '',
        'type': g_type,
        'lat': lat,
        'lon': lon,
        'has_jetway': bool(has_jw),
        'is_cargo': is_cargo,
        'is_ga': is_ga,
        'is_military': is_military,
        'airlines': al_clean
    }
    return gate_info, al_clean

class _LazyGSXDataDict(dict):
    """
    Fast on-demand GSX profile dictionary: indexes `.ini` filenames in `gsx_profile_path`
    in < 1ms on startup and lazily parses individual airport `.ini` + companion `.py`
    files the first time `data.get(icao)`, `icao in data`, or `data[icao]` is accessed.
    """
    def __init__(self, backend):
        super().__init__()
        self._backend = backend
        self._ini_index = {}
        self._loaded_icaos = set()
        self._lock = threading.RLock()

    def reset_index(self, ini_index):
        with self._lock:
            super().clear()
            self._ini_index = dict(ini_index or {})
            self._loaded_icaos.clear()

    def _ensure_icao(self, key):
        if not isinstance(key, str):
            return
        icao = key.strip().upper()
        if not icao or icao in self._loaded_icaos:
            return
        with self._lock:
            if icao in self._loaded_icaos:
                return
            self._loaded_icaos.add(icao)
            paths = self._ini_index.get(icao)
            if not paths:
                return
            merged = {}
            for fp in paths:
                try:
                    icao_gates = self._backend._parse_gsx_ini_file(icao, fp)
                    if icao_gates:
                        for al_k, g_list in icao_gates.items():
                            if al_k not in merged:
                                merged[al_k] = []
                            merged[al_k].extend(g_list)
                except Exception:
                    pass
            if merged:
                super().__setitem__(icao, merged)

    def __contains__(self, key):
        if super().__contains__(key):
            return True
        if isinstance(key, str) and key.strip().upper() in self._ini_index:
            self._ensure_icao(key)
            return super().__contains__(key.strip().upper())
        return False

    def __getitem__(self, key):
        if not super().__contains__(key):
            self._ensure_icao(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        if not super().__contains__(key):
            self._ensure_icao(key)
        return super().get(key, default)

    def __len__(self):
        return max(super().__len__(), len(self._ini_index))


class GateFinderBackend:
    def __init__(self, config, defer_heavy_init=False):
        self.config = config
        self._init_lock = threading.RLock()
        self._init_done = False
        self.network_checker = OnlineNetworkChecker()
        self.data = _LazyGSXDataDict(self)
        self.builtin_data = {}
        self.coherent_airports = {}
        self.airport_names = {}
        self.current_flight_data = None
        self.airline_names = self._load_airlines()
        self.cloud_ruleset = {}
        self.server_thread = None
        self.osm_cache = {}
        self.city_cache = {}
        self._logo_pil_cache = {}
        self._logo_png_cache = {}
        self._logo_fetch_inflight = set()
        self._logo_fetch_failed = set()
        self.logo_generation = 0
        self.taxi_router = TaxiRouter(defer_load=defer_heavy_init)
        self.simconnect_manager = SimConnectManager(self)
        self.interop_hub = InteroperabilityHub(self, self.config)
        if not defer_heavy_init:
            self.ensure_initialized()

    def ensure_initialized(self, progress_callback=None):
        if self._init_done:
            return
        with self._init_lock:
            if self._init_done:
                return
            if progress_callback:
                try:
                    progress_callback(0.05, "Loading airport & GSX stand databases...")
                except Exception:
                    pass
            if not self.cloud_ruleset:
                self.cloud_ruleset = self._fetch_cloud_ruleset()
            if not self.builtin_data:
                self._load_builtin_db()
            self.load_data()
            if hasattr(self, "taxi_router") and self.taxi_router:
                self.taxi_router.ensure_disk_cache_loaded()
            threading.Thread(target=self._sync_msfs_community_packages, daemon=True).start()
            self._init_done = True

    OFFICIAL_AIRPORT_NAMES = {
        "EBBR": "Brussels National",
        "EBCI": "Brussels South Charleroi",
        "EBLG": "Liège",
        "EBAW": "Antwerp International",
        "EBOS": "Ostend-Bruges International",
        "ELLX": "Luxembourg Findel",
        "LFPG": "Paris Charles de Gaulle",
        "LFPO": "Paris Orly",
        "LFPB": "Paris Le Bourget",
        "LFOB": "Paris Beauvais",
        "LFMN": "Nice Côte d'Azur",
        "LFML": "Marseille Provence",
        "LFLL": "Lyon Saint-Exupéry",
        "LFBO": "Toulouse Blagnac",
        "LFBD": "Bordeaux Mérignac",
        "LFRS": "Nantes Atlantique",
        "LFSB": "EuroAirport Basel-Mulhouse",
        "LFST": "Strasbourg Entzheim",
        "LFQQ": "Lille Lesquin",
        "LFMT": "Montpellier Méditerranée",
        "LFBZ": "Biarritz Pays Basque",
        "LFKJ": "Ajaccio Napoléon Bonaparte",
        "LFKB": "Bastia Poretta",
        "LFKC": "Calvi Sainte-Catherine",
        "LFKF": "Figari Sud-Corse",
        "TFFR": "Pointe-à-Pitre Le Raizet",
        "TFFF": "Fort-de-France Aimé Césaire",
        "FMEE": "Roland Garros",
        "EGLL": "London Heathrow",
        "EGKK": "London Gatwick",
        "EGSS": "London Stansted",
        "EGGW": "London Luton",
        "EGLC": "London City",
        "EGCC": "Manchester",
        "EGBB": "Birmingham",
        "EGPH": "Edinburgh",
        "EGPF": "Glasgow International",
        "EGGD": "Bristol",
        "EIDW": "Dublin",
        "LSGG": "Geneva Cointrin",
        "LSZH": "Zurich Kloten",
        "EDDF": "Frankfurt Main",
        "EDDM": "Munich",
        "EDDB": "Berlin Brandenburg",
        "EDDL": "Düsseldorf",
        "EDDH": "Hamburg",
        "EDDK": "Cologne Bonn",
        "EDDS": "Stuttgart",
        "EDDV": "Hannover",
        "LOWW": "Vienna Schwechat",
        "LOWI": "Innsbruck Kranebitten",
        "LOWS": "Salzburg",
        "EHAM": "Amsterdam Schiphol",
        "EHRD": "Rotterdam The Hague",
        "EHEH": "Eindhoven",
        "LIRF": "Rome Fiumicino",
        "LIRA": "Rome Ciampino",
        "LIMC": "Milan Malpensa",
        "LIML": "Milan Linate",
        "LIME": "Milan Bergamo",
        "LIPZ": "Venice Marco Polo",
        "LIPE": "Bologna Guglielmo Marconi",
        "LIRQ": "Florence Peretola",
        "LIRP": "Pisa International",
        "LIRN": "Naples Capodichino",
        "LICC": "Catania Fontanarossa",
        "LICJ": "Palermo Falcone-Borsellino",
        "LEMD": "Madrid Barajas",
        "LEBL": "Barcelona El Prat",
        "LEPA": "Palma de Mallorca",
        "LEMG": "Málaga Costa del Sol",
        "LEAL": "Alicante-Elche",
        "LEVC": "Valencia",
        "LEZL": "Seville",
        "GCLP": "Gran Canaria",
        "GCTS": "Tenerife South",
        "GCXO": "Tenerife North",
        "LPPT": "Lisbon Humberto Delgado",
        "LPPR": "Porto Francisco Sá Carneiro",
        "LPFR": "Faro",
        "LPMA": "Madeira Cristiano Ronaldo",
        "LGAV": "Athens Eleftherios Venizelos",
        "EKCH": "Copenhagen Kastrup",
        "ENGM": "Oslo Gardermoen",
        "ESSA": "Stockholm Arlanda",
        "EFHK": "Helsinki Vantaa",
        "BIKF": "Keflavík International",
        "EPWA": "Warsaw Chopin",
        "LKPR": "Prague Václav Havel",
        "LHBP": "Budapest Ferenc Liszt",
        "LROP": "Bucharest Henri Coandă",
        "LTFM": "Istanbul",
        "LTAI": "Antalya",
        "OMDB": "Dubai International",
        "OMAA": "Abu Dhabi International",
        "OTHH": "Doha Hamad International",
        "KJFK": "New York John F. Kennedy",
        "KEWR": "Newark Liberty International",
        "KLGA": "New York LaGuardia",
        "KBOS": "Boston Logan International",
        "KIAD": "Washington Dulles International",
        "KATL": "Atlanta Hartsfield-Jackson",
        "KMIA": "Miami International",
        "KMCO": "Orlando International",
        "KORD": "Chicago O'Hare International",
        "KDFW": "Dallas/Fort Worth International",
        "KDEN": "Denver International",
        "KLAX": "Los Angeles International",
        "KSFO": "San Francisco International",
        "KLAS": "Las Vegas Harry Reid",
        "KSEA": "Seattle-Tacoma International",
        "CYYZ": "Toronto Pearson International",
        "CYUL": "Montréal-Trudeau International",
        "CYVR": "Vancouver International",
    }

    def get_airport_display_name(self, icao, raw_name=""):
        icao_u = str(icao or "").strip().upper()
        if icao_u in self.OFFICIAL_AIRPORT_NAMES:
            return self.OFFICIAL_AIRPORT_NAMES[icao_u]
        s = str(raw_name or "").strip()
        if not s:
            return ""
        s_title = s.title()
        # Expand SimBrief ARINC 424 13-character abbreviations
        abbrev_map = [
            (r"\bNatl\.?\b", "National"),
            (r"\bNat\.?\b", "National"),
            (r"\bInt'L\.?\b", "International"),
            (r"\bIntl\.?\b", "International"),
            (r"\bInt\.?\b", "International"),
            (r"\bIntercont\.?\b", "Intercontinental"),
            (r"\bMuni\.?\b", "Municipal"),
            (r"\bRegl\.?\b", "Regional"),
            (r"\bMetro\.?\b", "Metropolitan"),
            (r"\bArpt\.?\b", "Airport"),
            (r"\bApt\.?\b", "Airport"),
            (r"\bMem\.?\b", "Memorial"),
            (r"\bFld\.?\b", "Field"),
        ]
        for pat, repl in abbrev_map:
            s_title = re.sub(pat, repl, s_title, flags=re.IGNORECASE)
        return s_title

    def get_airport_city(self, icao, lat=None, lon=None, ofp_apt_block=None):
        if not icao:
            return ""
        icao_u = str(icao).strip().upper()
        if icao_u in self.city_cache:
            return self.city_cache[icao_u]

        builtin_cities = {
            # France & Corsica & Outre-Mer
            "LFKJ": "Ajaccio", "LFKB": "Bastia", "LFKC": "Calvi", "LFKF": "Figari",
            "LFPO": "Paris", "LFPG": "Paris", "LFPB": "Paris", "LFOB": "Beauvais",
            "LFMN": "Nice", "LFML": "Marseille", "LFLL": "Lyon", "LFLY": "Lyon",
            "LFBO": "Toulouse", "LFBD": "Bordeaux", "LFRS": "Nantes", "LFSB": "Bâle / Mulhouse",
            "LFST": "Strasbourg", "LFQQ": "Lille", "LFMT": "Montpellier", "LFBZ": "Biarritz",
            "LFBP": "Pau", "LFBT": "Tarbes / Lourdes", "LFTH": "Toulon / Hyères", "LFMP": "Perpignan",
            "LFTW": "Nîmes", "LFMU": "Béziers", "LFLC": "Clermont-Ferrand", "LFLB": "Chambéry",
            "LFLP": "Annecy", "LFLS": "Grenoble", "LFRB": "Brest", "LFRN": "Rennes",
            "LFRD": "Dinard", "LFRK": "Caen", "LFRG": "Deauville", "LFRQ": "Quimper",
            "LFRH": "Lorient", "LFBI": "Poitiers", "LFBL": "Limoges", "LFBH": "La Rochelle",
            "LFOT": "Tours", "LFOK": "Châlons / Vatry", "LFJL": "Metz / Nancy", "LFGJ": "Dole",
            "LFMD": "Cannes", "LFTZ": "La Môle / Saint-Tropez", "LFCR": "Rodez", "LFCK": "Castres",
            "LFBA": "Agen", "LFSL": "Brive", "LFLX": "Châteauroux", "LFMK": "Carcassonne",
            "TFFR": "Pointe-à-Pitre", "TFFF": "Fort-de-France", "FMEE": "Saint-Denis (La Réunion)",
            "SOCA": "Cayenne", "NTAA": "Papeete", "NWWW": "Nouméa", "TFFJ": "Saint-Barthélemy",
            "TNCM": "Sint Maarten", "TFFG": "Saint-Martin",
            # UK & Ireland
            "EGLL": "London", "EGKK": "London", "EGSS": "London", "EGGW": "London",
            "EGLC": "London", "EGKB": "London", "EGMC": "Southend", "EGCC": "Manchester",
            "EGBB": "Birmingham", "EGPH": "Edinburgh", "EGPF": "Glasgow", "EGGD": "Bristol",
            "EGGP": "Liverpool", "EGNX": "East Midlands", "EGNM": "Leeds / Bradford",
            "EGNT": "Newcastle", "EGAA": "Belfast", "EGAC": "Belfast", "EGPD": "Aberdeen",
            "EGPE": "Inverness", "EGFF": "Cardiff", "EGHI": "Southampton", "EGHH": "Bournemouth",
            "EGJJ": "Jersey", "EGJB": "Guernsey", "EIDW": "Dublin", "EICK": "Cork", "EINN": "Shannon",
            # Switzerland, Germany, Austria, Benelux
            "LSGG": "Geneva", "LSZH": "Zurich", "LSZB": "Bern", "LSZA": "Lugano", "LSZR": "St. Gallen",
            "EDDF": "Frankfurt", "EDDM": "Munich", "EDDB": "Berlin", "EDDL": "Düsseldorf",
            "EDDH": "Hamburg", "EDDK": "Cologne / Bonn", "EDDS": "Stuttgart", "EDDV": "Hannover",
            "EDDP": "Leipzig", "EDDN": "Nuremberg", "EDDW": "Bremen", "EDDC": "Dresden",
            "EDFH": "Hahn", "EDJA": "Memmingen", "EDSB": "Karlsruhe / Baden-Baden",
            "EDLV": "Weeze", "EDLW": "Dortmund", "EDDG": "Münster / Osnabrück",
            "LOWW": "Vienna", "LOWI": "Innsbruck", "LOWS": "Salzburg", "LOWG": "Graz", "LOWL": "Linz", "LOWK": "Klagenfurt",
            "EHAM": "Amsterdam", "EHRD": "Rotterdam", "EHEH": "Eindhoven", "EHBK": "Maastricht",
            "EBBR": "Brussels", "EBCI": "Charleroi", "EBLG": "Liège", "EBAW": "Antwerp", "EBOS": "Ostend",
            "ELLX": "Luxembourg",
            # Italy, Spain, Portugal, Greece, Malta
            "LIRF": "Rome", "LIRA": "Rome", "LIMC": "Milan", "LIML": "Milan", "LIME": "Bergamo",
            "LIPZ": "Venice", "LIPH": "Treviso", "LIPE": "Bologna", "LIRQ": "Florence", "LIRP": "Pisa",
            "LIRN": "Naples", "LICC": "Catania", "LICJ": "Palermo", "LIEE": "Cagliari", "LIEO": "Olbia",
            "LIEA": "Alghero", "LIMF": "Turin", "LIMJ": "Genoa", "LIPX": "Verona", "LIBD": "Bari",
            "LIBR": "Brindisi", "LICA": "Lamezia Terme", "LIPY": "Ancona", "LIPQ": "Trieste",
            "LEMD": "Madrid", "LEBL": "Barcelona", "LEPA": "Palma de Mallorca", "LEMG": "Málaga",
            "LEAL": "Alicante", "LEVC": "Valencia", "LEZL": "Seville", "LEBB": "Bilbao",
            "LEIB": "Ibiza", "LEMH": "Menorca", "LEST": "Santiago de Compostela", "LEVX": "Vigo",
            "LEAS": "Asturias", "LEXJ": "Santander", "LEJR": "Jerez", "LEGR": "Granada",
            "GCLP": "Gran Canaria", "GCTS": "Tenerife", "GCXO": "Tenerife", "GCRR": "Lanzarote",
            "GCFV": "Fuerteventura", "GCLA": "La Palma", "LXGB": "Gibraltar",
            "LPPT": "Lisbon", "LPPR": "Porto", "LPFR": "Faro", "LPMA": "Funchal (Madeira)", "LPPD": "Ponta Delgada",
            "LGAV": "Athens", "LGTS": "Thessaloniki", "LGIR": "Heraklion", "LGSR": "Santorini",
            "LGMK": "Mykonos", "LGRP": "Rhodes", "LGKR": "Corfu", "LGKO": "Kos", "LGZA": "Zakynthos",
            "LMML": "Luqa (Malta)", "LCLK": "Larnaca", "LCPH": "Paphos",
            # Nordics, Eastern Europe & Turkey
            "EKCH": "Copenhagen", "EKBI": "Billund", "EKYT": "Aalborg",
            "ENGM": "Oslo", "ENBR": "Bergen", "ENZV": "Stavanger", "ENVA": "Trondheim", "ENTC": "Tromsø",
            "ESSA": "Stockholm", "ESSB": "Stockholm", "ESGG": "Gothenburg", "ESMS": "Malmö",
            "EFHK": "Helsinki", "EFOU": "Oulu", "EFRO": "Rovaniemi", "BIKF": "Reykjavik",
            "EPWA": "Warsaw", "EPKK": "Kraków", "EPGD": "Gdańsk", "EPKT": "Katowice", "EPWR": "Wrocław", "EPPO": "Poznań",
            "LKPR": "Prague", "LHBP": "Budapest", "LROP": "Bucharest", "LZIB": "Bratislava",
            "LJLJ": "Ljubljana", "LDZA": "Zagreb", "LDSP": "Split", "LDDU": "Dubrovnik",
            "LYBE": "Belgrade", "LBSF": "Sofia", "EVRA": "Riga", "EYVI": "Vilnius", "EETN": "Tallinn",
            "LTFM": "Istanbul", "LTFJ": "Istanbul", "LTAI": "Antalya", "LTAC": "Ankara", "LTBJ": "Izmir", "LTBS": "Dalaman", "LTFE": "Bodrum",
            # Middle East, Africa, Americas, Asia-Pacific
            "OMDB": "Dubai", "OMDW": "Dubai", "OMAA": "Abu Dhabi", "OMSJ": "Sharjah",
            "OTHH": "Doha", "OERK": "Riyadh", "OEJN": "Jeddah", "OEDF": "Dammam",
            "OKBK": "Kuwait City", "OBBI": "Manama (Bahrain)", "OOMS": "Muscat", "OJAI": "Amman",
            "OLBA": "Beirut", "LLBG": "Tel Aviv", "HECA": "Cairo", "HEGN": "Hurghada", "HESH": "Sharm El Sheikh",
            "GMMN": "Casablanca", "GMMX": "Marrakech", "GMAD": "Agadir", "GMTT": "Tangier", "GMFF": "Fès", "GMME": "Rabat",
            "DAAG": "Algiers", "DAOO": "Oran", "DTTA": "Tunis", "DTMB": "Monastir", "DTTJ": "Djerba",
            "KJFK": "New York", "KEWR": "Newark", "KLGA": "New York", "KBOS": "Boston", "KIAD": "Washington",
            "KDCA": "Washington", "KATL": "Atlanta", "KMIA": "Miami", "KMCO": "Orlando", "KORD": "Chicago",
            "KDFW": "Dallas", "KIAH": "Houston", "KDEN": "Denver", "KLAX": "Los Angeles", "KSFO": "San Francisco",
            "KLAS": "Las Vegas", "KSEA": "Seattle", "KPHX": "Phoenix", "CYYZ": "Toronto", "CYUL": "Montreal", "CYVR": "Vancouver",
            "RJTT": "Tokyo", "RJAA": "Tokyo", "RJBB": "Osaka", "RKSI": "Seoul", "VHHH": "Hong Kong",
            "WSSS": "Singapore", "VTBS": "Bangkok", "WMKK": "Kuala Lumpur", "YSSY": "Sydney", "YMML": "Melbourne"
        }
        if icao_u in builtin_cities:
            self.city_cache[icao_u] = builtin_cities[icao_u]
            return builtin_cities[icao_u]

        # Try extracting city from SimBrief ATIS block if present (e.g. "AJACCIO-NAPOLEON BONAPARTE")
        if isinstance(ofp_apt_block, dict):
            atis_raw = ofp_apt_block.get("atis")
            atis_list = atis_raw if isinstance(atis_raw, list) else ([atis_raw] if isinstance(atis_raw, dict) else [])
            for atis_item in atis_list:
                if isinstance(atis_item, dict):
                    msg = str(atis_item.get("message") or "").strip()
                    m_atis = re.match(r'^([A-Z\s]+?)\s*-\s*[A-Z]', msg)
                    if m_atis:
                        cand = m_atis.group(1).strip().title()
                        if 2 < len(cand) < 28 and cand.upper() != self.airport_names.get(icao_u, "").upper():
                            self.city_cache[icao_u] = cand
                            return cand

        # Fast reverse-geocoding via Nominatim if coordinates are known
        if lat is not None and lon is not None:
            try:
                url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={float(lat):.4f}&lon={float(lon):.4f}&zoom=10&accept-language=fr,en"
                req = urllib.request.Request(url, headers={"User-Agent": "GateFinder-EFB/2.0"})
                with urllib.request.urlopen(req, timeout=1.8) as resp:
                    rdata = json.loads(resp.read().decode("utf-8"))
                    addr = rdata.get("address") or {}
                    city_val = (
                        addr.get("city")
                        or addr.get("town")
                        or addr.get("municipality")
                        or addr.get("village")
                        or addr.get("county")
                        or ""
                    ).strip()
                    if city_val:
                        self.city_cache[icao_u] = city_val
                        return city_val
            except Exception:
                pass

        return ""

    def _get_logo_cache_dir(self):
        cfg_file = getattr(self.config, "settings_file", None) or getattr(self.config, "config_file", None)
        base_dir = os.path.dirname(os.path.abspath(cfg_file)) if cfg_file else os.path.abspath(".")
        cdir = os.path.join(base_dir, "cache", "airline_logos")
        try:
            os.makedirs(cdir, exist_ok=True)
        except Exception:
            pass
        return cdir

    def get_airline_camaieu_palette(self, code):
        """
        Extracts ALL distinct brand colors of the airline (combining official brand styles
        and multi-cluster logo color analysis) and mixes their pastel camaïeux into a soft,
        muted 6-shade palette ('s1'..'s6' + 'accent') calibrated for crisp #FFFFFF white text.
        """
        import colorsys
        c = normalize_airline_icao(code) if code else "AIR"
        if not hasattr(self, "_camaieu_cache"):
            self._camaieu_cache = {}
        cache_key = ("pastel_mix_v2", c, getattr(self, "logo_generation", 0))
        if cache_key in self._camaieu_cache:
            return self._camaieu_cache[cache_key]

        def _hue_dist_deg(h1, h2):
            d = abs(h1 - h2) % 360.0
            return d if d <= 180.0 else 360.0 - d

        hues = []
        def _add_hue(h_deg, min_sep=28.0):
            hd = h_deg % 360.0
            for eh in hues:
                if _hue_dist_deg(hd, eh) < min_sep:
                    return
            hues.append(hd)

        # 1. Collect all chromatic brand colors from AIRLINE_BRAND_STYLES (bg, border/secondary, fg)
        if c and c in AIRLINE_BRAND_STYLES:
            bg_hex, fg_hex, bd_hex, _ = AIRLINE_BRAND_STYLES[c]
            for hx_raw in (bg_hex, bd_hex, fg_hex):
                hx = str(hx_raw or "").lstrip("#")
                if len(hx) == 6:
                    r_b, g_b, b_b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
                    h_b, l_b, s_b = colorsys.rgb_to_hls(r_b / 255.0, g_b / 255.0, b_b / 255.0)
                    if s_b >= 0.20 and 0.06 <= l_b <= 0.88:
                        _add_hue(h_b * 360.0, min_sep=28.0)

        # 2. Collect all significant chromatic color clusters from the raw airline logo image
        if c and c not in ("ANY", "NONE", "AIR"):
            try:
                cdir = self._get_logo_cache_dir()
                raw_path = os.path.join(cdir, f"{c}_raw.png")
                if os.path.exists(raw_path) and os.path.getsize(raw_path) > 100:
                    from PIL import Image
                    im = Image.open(raw_path).convert("RGBA").resize((56, 56))
                    pixels = list(im.get_flattened_data()) if hasattr(im, "get_flattened_data") else list(im.getdata())
                    bins = [0.0] * 36
                    bin_h_sum = [0.0] * 36
                    for r_p, g_p, b_p, a_p in pixels:
                        if a_p < 105:
                            continue
                        if r_p > 234 and g_p > 234 and b_p > 234:
                            continue
                        if max(r_p, g_p, b_p) < 25:
                            continue
                        h_p, l_p, s_p = colorsys.rgb_to_hls(r_p / 255.0, g_p / 255.0, b_p / 255.0)
                        if s_p < 0.16:
                            continue
                        b_idx = int(round(h_p * 36)) % 36
                        w = (s_p ** 1.05)
                        bins[b_idx] += w
                        bin_h_sum[b_idx] += (h_p * 360.0) * w
                    tot_w = sum(bins)
                    if tot_w > 0:
                        scored = []
                        for i in range(36):
                            win_w = bins[(i - 1) % 36] + bins[i] + bins[(i + 1) % 36]
                            avg_h = (bin_h_sum[i] / bins[i]) if bins[i] > 0 else ((i * 10.0) % 360.0)
                            scored.append((win_w, avg_h))
                        scored.sort(reverse=True)
                        for win_w, avg_h in scored:
                            if win_w >= tot_w * 0.065:
                                _add_hue(avg_h, min_sep=30.0)
            except Exception:
                pass

        # 3. Fallback if airline is unknown and has no cached logo
        if not hues:
            bg_hex, fg_hex, bd_hex, _ = get_airline_brand_style(c)
            for hx_raw in (bg_hex, bd_hex, fg_hex):
                hx = str(hx_raw or "").lstrip("#")
                if len(hx) == 6:
                    r_b, g_b, b_b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
                    h_b, l_b, s_b = colorsys.rgb_to_hls(r_b / 255.0, g_b / 255.0, b_b / 255.0)
                    if s_b >= 0.18:
                        _add_hue(h_b * 360.0, min_sep=28.0)
            if not hues:
                hues = [202.0]

        def _pastel_hex(h_deg, l_val, s_val):
            hd = h_deg % 360.0
            # Soften saturation on reds/crimsons/corals so they render as warm pastel terracotta/rose
            if hd >= 330.0 or hd <= 24.0:
                s_adj = s_val * 0.78
                l_adj = l_val + 0.015
            # Slightly temper lightness on yellows/limes so #FFFFFF text remains ultra-crisp
            elif 35.0 <= hd <= 105.0:
                s_adj = s_val * 0.86
                l_adj = l_val - 0.038
            # Slightly lift deep blues/indigos so they feel airy and pastel on dark EFB cards
            elif 210.0 <= hd <= 265.0:
                s_adj = s_val * 0.90
                l_adj = l_val + 0.025
            else:
                s_adj = s_val * 0.86
                l_adj = l_val
            l_adj = max(0.37, min(0.54, l_adj))
            s_adj = max(0.21, min(0.35, s_adj))
            rr, gg, bb = colorsys.hls_to_rgb(hd / 360.0, l_adj, s_adj)
            return "#%02X%02X%02X" % (
                max(0, min(255, int(round(rr * 255)))),
                max(0, min(255, int(round(gg * 255)))),
                max(0, min(255, int(round(bb * 255))))
            )

        def _dark_tint_hex(h_deg, l_val, s_val):
            hd = h_deg % 360.0
            rr, gg, bb = colorsys.hls_to_rgb(hd / 360.0, l_val, s_val)
            return "#%02X%02X%02X" % (
                max(0, min(255, int(round(rr * 255)))),
                max(0, min(255, int(round(gg * 255)))),
                max(0, min(255, int(round(bb * 255))))
            )

        h_card_1 = hues[0]
        h_card_2 = hues[1] if len(hues) >= 2 else hues[0]

        # 4. Build and interleave the pastel camaïeux of all extracted brand colors
        if len(hues) == 1:
            h0 = hues[0]
            pal = {
                "s1": _pastel_hex(h0, 0.51, 0.36),
                "s2": _pastel_hex(h0 + 7.0, 0.47, 0.34),
                "s3": _pastel_hex(h0 - 6.0, 0.43, 0.32),
                "s4": _pastel_hex(h0 + 3.0, 0.39, 0.29),
                "s5": _pastel_hex(h0 - 9.0, 0.49, 0.33),
                "s6": _pastel_hex(h0 + 9.0, 0.41, 0.30),
                "accent": _pastel_hex(h0, 0.56, 0.40),
            }
        elif len(hues) == 2:
            h0, h1 = hues[0], hues[1]
            pal = {
                "s1": _pastel_hex(h0, 0.50, 0.36),
                "s2": _pastel_hex(h1, 0.49, 0.36),
                "s3": _pastel_hex(h0 + 5.0, 0.43, 0.32),
                "s4": _pastel_hex(h1 - 5.0, 0.42, 0.31),
                "s5": _pastel_hex(h0 - 5.0, 0.39, 0.29),
                "s6": _pastel_hex(h1 + 5.0, 0.38, 0.29),
                "accent": _pastel_hex(h0, 0.56, 0.40),
            }
        else:
            h0, h1, h2 = hues[0], hues[1], hues[2]
            h3 = hues[3] if len(hues) >= 4 else (h0 + 5.0)
            pal = {
                "s1": _pastel_hex(h0, 0.50, 0.36),
                "s2": _pastel_hex(h1, 0.49, 0.36),
                "s3": _pastel_hex(h2, 0.47, 0.34),
                "s4": _pastel_hex(h1 - 4.0, 0.42, 0.31),
                "s5": _pastel_hex(h0 + 5.0, 0.41, 0.31),
                "s6": _pastel_hex(h3, 0.39, 0.29),
                "accent": _pastel_hex(h0, 0.56, 0.40),
            }

        # Uniform neutral dark grey for all base cards; airline-tinted nuance exclusively for active DEPARTURE / ARRIVAL selection
        pal["card_bg"] = "#1B1E24"
        pal["card_sel_bg"] = _dark_tint_hex(h_card_2, 0.22, 0.28)
        pal["card_hover_bg"] = _dark_tint_hex(h_card_2, 0.17, 0.24)
        pal["subcard_bg"] = "#1B1E24"

        self._camaieu_cache[cache_key] = pal
        return pal

    def _fetch_and_cache_raw_logo(self, code):
        import ssl
        import urllib.request
        c = normalize_airline_icao(code)
        if not c or c in ("ANY", "NONE"):
            return None
        cdir = self._get_logo_cache_dir()
        raw_path = os.path.join(cdir, f"{c}_raw.png")
        if os.path.exists(raw_path) and os.path.getsize(raw_path) > 100:
            return raw_path
        if c in self._logo_fetch_failed:
            return None

        _, _, _, iata = get_airline_brand_style(c)
        urls = [f"https://www.flightaware.com/images/airline_logos/90p/{c}.png"]
        if iata:
            urls.append(f"https://images.kiwi.com/airlines/64/{iata}.png")
            urls.append(f"https://pics.avs.io/64/64/{iata}.png")

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for u in urls:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 GateFinder/2.0"})
                with urllib.request.urlopen(req, timeout=3.5, context=ctx) as resp:
                    data = resp.read()
                    if data and len(data) > 120:
                        with open(raw_path, "wb") as wf:
                            wf.write(data)
                        self.logo_generation += 1
                        return raw_path
            except Exception:
                continue

        self._logo_fetch_failed.add(c)
        return None

    def prefetch_airline_logos(self, codes):
        if not codes:
            return
        to_fetch = []
        cdir = self._get_logo_cache_dir()
        for raw_c in codes:
            c = normalize_airline_icao(raw_c)
            if not c or c in ("ANY", "NONE") or c in self._logo_fetch_failed or c in self._logo_fetch_inflight:
                continue
            raw_path = os.path.join(cdir, f"{c}_raw.png")
            if not (os.path.exists(raw_path) and os.path.getsize(raw_path) > 100):
                self._logo_fetch_inflight.add(c)
                to_fetch.append(c)
        if not to_fetch:
            return

        def _bg():
            for c in to_fetch:
                try:
                    self._fetch_and_cache_raw_logo(c)
                finally:
                    self._logo_fetch_inflight.discard(c)

        threading.Thread(target=_bg, daemon=True).start()

    @staticmethod
    def _hex_to_rgba(hex_str, alpha=255):
        h = str(hex_str or "#1E293B").lstrip("#")
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)
        return (30, 41, 59, alpha)

    def get_airline_pill_pil_image(self, code, size=18, allow_network=False, width=None, corner_radius=0):
        import io
        from PIL import Image, ImageDraw, ImageFont

        c = normalize_airline_icao(code) or "AIR"
        h_sz = max(14, min(96, int(size)))
        w_sz = max(16, int(width)) if width is not None else max(16, int(round(h_sz * 1.18)))
        cr = max(0, int(corner_radius))
        cdir = self._get_logo_cache_dir()
        raw_path = os.path.join(cdir, f"{c}_raw.png")
        has_raw = os.path.exists(raw_path) and os.path.getsize(raw_path) > 100

        if not has_raw:
            if allow_network:
                self._fetch_and_cache_raw_logo(c)
                has_raw = os.path.exists(raw_path) and os.path.getsize(raw_path) > 100
            else:
                self.prefetch_airline_logos([c])

        cache_key = ("rect_v3", c, w_sz, h_sz, cr, has_raw)
        if cache_key in self._logo_pil_cache:
            return self._logo_pil_cache[cache_key]

        bg_hex, fg_hex, bd_hex, iata = get_airline_brand_style(c)
        ss_w = w_sz * 2
        ss_h = h_sz * 2
        canvas = Image.new("RGBA", (ss_w, ss_h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        rendered_logo = False
        if has_raw:
            try:
                im = Image.open(raw_path).convert("RGBA")
                # Strip near-white opaque background so the bbox crops tightly to the actual airline emblem
                datas = list(im.get_flattened_data()) if hasattr(im, "get_flattened_data") else list(im.getdata())
                new_data = []
                for item in datas:
                    if item[3] < 18 or (item[0] > 242 and item[1] > 242 and item[2] > 242):
                        new_data.append((255, 255, 255, 0))
                    else:
                        new_data.append(item)
                im.putdata(new_data)
                bbox = im.getbbox()
                if bbox:
                    im = im.crop(bbox)
                # Full-bleed rectangular tile (minimal margin so wide logos fill the badge generously)
                pad_x = max(2, int(round(ss_w * 0.045)))
                pad_y = max(2, int(round(ss_h * 0.05)))
                max_w = max(4, ss_w - pad_x * 2)
                max_h = max(4, ss_h - pad_y * 2)
                lw, lh = im.size
                scale = min(max_w / max(1, lw), max_h / max(1, lh))
                nw = max(1, int(round(lw * scale)))
                nh = max(1, int(round(lh * scale)))
                im_r = im.resize((nw, nh), Image.Resampling.LANCZOS)
                ox = (ss_w - nw) // 2
                oy = (ss_h - nh) // 2
                canvas.alpha_composite(im_r, (ox, oy))
                rendered_logo = True
            except Exception:
                rendered_logo = False

        if not rendered_logo:
            draw.rectangle([0, 0, ss_w, ss_h], fill=self._hex_to_rgba(bg_hex, 255))
            lbl = (iata if (iata and h_sz <= 18) else c[:3]).upper()
            f_sz = max(10, int(round(ss_h * (0.48 if len(lbl) <= 2 else 0.36))))
            try:
                font = ImageFont.truetype("arialbd.ttf", f_sz)
            except Exception:
                font = ImageFont.load_default()
            tb = draw.textbbox((0, 0), lbl, font=font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            tx = (ss_w - tw) / 2.0 - tb[0]
            ty = (ss_h - th) / 2.0 - tb[1]
            draw.text((tx, ty), lbl, fill=self._hex_to_rgba(fg_hex, 255), font=font)

        if cr > 0:
            mask = Image.new("L", (ss_w, ss_h), 0)
            mdraw = ImageDraw.Draw(mask)
            mdraw.rounded_rectangle([0, 0, ss_w - 1, ss_h - 1], radius=cr * 2, fill=255)
            out_canvas = Image.new("RGBA", (ss_w, ss_h), (0, 0, 0, 0))
            out_canvas.paste(canvas, (0, 0), mask)
            canvas = out_canvas

        final_im = canvas.resize((w_sz, h_sz), Image.Resampling.LANCZOS)
        self._logo_pil_cache[cache_key] = final_im
        return final_im

    def get_airline_pill_png_bytes(self, code, size=22, allow_network=True, width=None, corner_radius=0):
        import io
        c = normalize_airline_icao(code) or "AIR"
        h_sz = max(14, min(64, int(size)))
        w_sz = max(16, int(width)) if width else max(16, int(round(h_sz * 1.18)))
        r_sz = max(0, int(corner_radius or 0))
        cdir = self._get_logo_cache_dir()
        raw_path = os.path.join(cdir, f"{c}_raw.png")
        has_raw = os.path.exists(raw_path) and os.path.getsize(raw_path) > 100
        if not has_raw and allow_network:
            self._fetch_and_cache_raw_logo(c)
            has_raw = os.path.exists(raw_path) and os.path.getsize(raw_path) > 100
        cache_key = ("rect_v3", c, w_sz, h_sz, r_sz, has_raw)
        if cache_key in self._logo_png_cache:
            return self._logo_png_cache[cache_key]
        pil_im = self.get_airline_pill_pil_image(c, size=h_sz, allow_network=allow_network, width=width, corner_radius=r_sz)
        buf = io.BytesIO()
        pil_im.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        self._logo_png_cache[cache_key] = png_bytes
        return png_bytes

    def fetch_real_world_airport_airlines(self, icao, chart_data=None):
        """
        On-the-fly Real-World Verification Phase:
        Queries Wikipedia's 'Airlines and destinations' table for `icao` (cached in memory
        and inside `chart_data['real_world_airlines']` in taxi_charts_cache.json), and merges
        live VATSIM/IVAO flights at `icao` to determine the true real-world airline destination
        counts `{airline_icao: count}` operating at `icao`.
        """
        icao_u = str(icao or "").strip().upper()
        if not icao_u or len(icao_u) != 4:
            return {}

        if not hasattr(self, "_real_world_airlines_cache"):
            self._real_world_airlines_cache = {}
        if not hasattr(self, "_rw_fetch_failed_ts"):
            self._rw_fetch_failed_ts = {}

        if icao_u in self._real_world_airlines_cache and self._real_world_airlines_cache[icao_u]:
            res_cached = dict(self._real_world_airlines_cache[icao_u])
            if isinstance(chart_data, dict):
                chart_data["real_world_airlines"] = res_cached
                chart_data["real_world_airlines_v"] = 3
            return res_cached

        if (
            isinstance(chart_data, dict)
            and chart_data.get("real_world_airlines_v") == 3
            and isinstance(chart_data.get("real_world_airlines"), dict)
            and len(chart_data["real_world_airlines"]) >= 3
        ):
            res_cached = dict(chart_data["real_world_airlines"])
            self._real_world_airlines_cache[icao_u] = res_cached
            return res_cached

        def _norm_al_key(txt):
            if not txt:
                return ""
            s = unicodedata.normalize("NFKD", str(txt))
            s = "".join(ch for ch in s if not unicodedata.combining(ch))
            s = re.sub(r"\s*\(.*?\)", "", s)
            s = re.sub(r"[^a-zA-Z0-9\s.&'-]", " ", s)
            return re.sub(r"\s+", " ", s).strip().lower()

        counts = {}
        if time.time() - self._rw_fetch_failed_ts.get(icao_u, 0.0) >= 60.0:
            try:
                import requests
                name_to_icao = {}
                for k, v in (getattr(self, "airline_names", None) or {}).items():
                    if isinstance(k, str) and len(k) == 3 and k.isalpha() and v:
                        nk = _norm_al_key(v)
                        if nk and len(nk) >= 3:
                            name_to_icao[nk] = k.upper()
                for k, v in AIRLINE_FULL_NAMES.items():
                    if len(k) == 3 and v:
                        nk = _norm_al_key(v)
                        if nk:
                            name_to_icao[nk] = k.upper()
                name_to_icao.update({
                    "tui fly belgium": "JAF", "eurowings discover": "OCN", "discover airlines": "OCN",
                    "lufthansa cityline": "CLH", "lufthansa city airlines": "LHX", "air dolomiti": "DLA",
                    "ba euroflyer": "BAW", "ba cityflyer": "BAW", "tui airways": "TOM", "tui fly": "TUI",
                    "tui fly netherlands": "TFL", "tui fly nordic": "BLX", "wizz air malta": "WZZ",
                    "wizz air uk": "WZZ", "klm cityhopper": "KLM", "hop": "AFR", "air france hop": "AFR",
                    "iberia express": "IBE", "air nostrum": "IBE", "aer lingus regional": "EIN",
                    "swiss international air lines": "SWR", "swiss": "SWR", "ita airways": "ITY",
                    "brussels airlines": "BEL", "tap air portugal": "TAP", "edelweiss air": "EDW",
                    "helvetic airways": "OAW", "easyjet switzerland": "EZY", "easyjet europe": "EZY",
                    "easyjet uk": "EZY", "flydubai": "FDB", "virgin atlantic": "VIR",
                    "jet2.com": "EXS", "jet2": "EXS", "norwegian air shuttle": "NAX",
                    "norwegian air sweden": "NAX", "sas": "SAS", "scandinavian airlines": "SAS",
                    "corsair": "CRL", "corsair international": "CRL", "french bee": "FBU",
                    "french blue": "FBU", "air caraibes": "FWI", "air caraibes atlantique": "FWI",
                    "la compagnie": "DJT", "volotea": "VOE", "air corsica": "CCM",
                    "chalair": "CLG", "chalair aviation": "CLG", "twin jet": "TJT",
                    "amelia": "AEH", "amelia international": "AEH", "transavia france": "TVF",
                    "transavia": "TRA", "sunexpress": "SXS", "air europa": "AEA",
                    "air europa express": "AEA", "binter canarias": "IBB", "binter": "IBB",
                    "wideroe": "WIF", "sky express": "SEH", "nouvelair": "LBT",
                    "tunisair express": "TAR", "royal air maroc express": "RAM",
                    "corendon airlines": "CAI", "corendon airlines europe": "CAI",
                    "corendon dutch airlines": "CND", "smartwings": "TVS", "play": "FPY",
                    "fly play": "FPY", "neos": "NOS", "arkia": "AIZ", "israir": "ISR",
                    "pegasus": "PGT", "pegasus airlines": "PGT", "ajet": "TKJ", "anadolujet": "TKJ",
                    "sata air acores": "SAT", "azores airlines": "RZO", "air arabia maroc": "MAC",
                    "air arabia": "ABY", "eastern airways": "EZE", "loganair": "LOG",
                })
                apt_name = (getattr(self, "airport_names", {}) or {}).get(icao_u, "")
                q_str = f"{icao_u} {apt_name} airport".strip() if apt_name else f"{icao_u} airport"
                r = requests.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "generator": "search",
                        "gsrsearch": f"{icao_u} airport",
                        "gsrlimit": 1,
                        "prop": "revisions",
                        "rvprop": "content",
                        "rvslots": "main",
                        "format": "json",
                    },
                    headers={"User-Agent": "GateFinder/2.0 (https://github.com/wildbill75/gsx-gatefinder)"},
                    timeout=3.5,
                )
                if r.status_code == 200:
                    data_j = r.json()
                    pages = (data_j.get("query") or {}).get("pages") or {}
                    if pages:
                        page = list(pages.values())[0]
                        revs = page.get("revisions") or []
                        wt = (((revs[0].get("slots") or {}).get("main") or {}).get("*")) if revs else ""
                        m = re.search(r'==\s*Airlines and destinations\s*==(.*?)(?:\n==[^=]|$)', wt, re.S | re.I)
                        sec = m.group(1) if m else ""
                        if sec:
                            sec = re.sub(r'<!--.*?-->', '', sec, flags=re.S)
                            sec = re.sub(r'<ref[^/>]*/\s*>', '', sec, flags=re.I)
                            sec = re.sub(r'<ref[^>]*>.*?</ref>', '', sec, flags=re.S | re.I)
                            sec = re.sub(r'\{\{\s*nowrap\s*\|([^{}]*)\}\}', r'\1', sec, flags=re.I)
                            sec_p = re.sub(
                                r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]',
                                lambda m_lk: f"@@{m_lk.group(1)}@@{m_lk.group(2)}@@" if m_lk.group(2) else f"@@{m_lk.group(1)}@@",
                                sec,
                            )
                            sec_p = re.sub(r'\{\{\s*Airport[ _-]dest(?:ination)?[ _-]list', '[[ADL_START]]', sec_p, flags=re.I)
                            while re.search(r'\{\{[^{}]*\}\}', sec_p):
                                sec_p = re.sub(r'\{\{[^{}]*\}\}', '', sec_p)
                            tokens = [t.strip() for t in sec_p.split('|')]
                            i = 0
                            while i < len(tokens) - 1:
                                raw_tok = tokens[i]
                                cand_names = []
                                for m_lk in re.finditer(r'@@([^@]+)@@(?:([^@]+)@@)?', raw_tok):
                                    if m_lk.group(1):
                                        cand_names.append(_norm_al_key(m_lk.group(1)))
                                    if m_lk.group(2):
                                        cand_names.append(_norm_al_key(m_lk.group(2)))
                                plain_tok = _norm_al_key(raw_tok.replace('@@', ' '))
                                if plain_tok and plain_tok not in cand_names:
                                    cand_names.append(plain_tok)

                                code = None
                                for t_clean in cand_names:
                                    if not t_clean:
                                        continue
                                    code = name_to_icao.get(t_clean)
                                    if not code and 2 <= len(t_clean) <= 32 and ',' not in t_clean:
                                        for nm, cd in name_to_icao.items():
                                            if t_clean == nm or t_clean == nm + ' airlines' or t_clean == nm + ' airways':
                                                code = cd
                                                break
                                    if code:
                                        break
                                if code:
                                    n_dest = len(re.findall(r'@@[^@]+@@', tokens[i + 1]))
                                    if n_dest > 0:
                                        counts[code] = counts.get(code, 0) + n_dest
                                        i += 2
                                        continue
                                i += 1
            except Exception:
                self._rw_fetch_failed_ts[icao_u] = time.time()

        wiki_ok = len(counts) >= 3

        # Merge known terminal rules from `airlines_terminals.json` as baseline verified operators
        apt_rules = ((getattr(self, "cloud_ruleset", None) or {}).get(icao_u) or {}).get("rules") or {}
        if isinstance(apt_rules, dict):
            for r_al in apt_rules.keys():
                c_norm = LOGO_TWIN_CANONICAL_MAP.get(normalize_airline_icao(r_al), normalize_airline_icao(r_al))
                if c_norm and len(c_norm) == 3 and c_norm.isalpha():
                    counts[c_norm] = max(counts.get(c_norm, 0), 2)

        # Boost with any live VATSIM/IVAO aircraft currently parked at or flying to/from `icao_u`
        try:
            nc = getattr(self, "network_checker", None)
            pilots = getattr(nc, "cached_data", None) or []
            c_lat = (chart_data or {}).get("center_lat")
            c_lon = (chart_data or {}).get("center_lon")
            if pilots and c_lat is not None and c_lon is not None:
                for p in pilots:
                    p_lat, p_lon = p.get("lat"), p.get("lon")
                    if p_lat is not None and p_lon is not None and abs(p_lat - c_lat) < 0.08 and abs(p_lon - c_lon) < 0.10:
                        cs = str(p.get("callsign") or "").strip().upper()
                        if len(cs) >= 4 and cs[:3].isalpha() and cs[3].isdigit():
                            c_live = LOGO_TWIN_CANONICAL_MAP.get(normalize_airline_icao(cs[:3]), normalize_airline_icao(cs[:3]))
                            if c_live in AIRLINE_FULL_NAMES or c_live in AIRLINE_BRAND_STYLES:
                                counts[c_live] = counts.get(c_live, 0) + 3
        except Exception:
            pass

        if wiki_ok:
            self._real_world_airlines_cache[icao_u] = counts
            if isinstance(chart_data, dict):
                chart_data["real_world_airlines"] = counts
                chart_data["real_world_airlines_v"] = 3
                try:
                    if hasattr(self, "taxi_router") and self.taxi_router:
                        self.taxi_router._save_disk_cache()
                except Exception:
                    pass
        elif counts:
            if isinstance(chart_data, dict):
                chart_data["real_world_airlines"] = counts
            self._rw_fetch_failed_ts[icao_u] = time.time()
        else:
            self._rw_fetch_failed_ts[icao_u] = time.time()

        return counts

    def enrich_chart_stands_with_airlines(self, icao, chart_data, assigned_gate=None, assigned_airline=None):
        """
        Ensures every stand in `chart_data['stands']` has its realistic `airlines` list
        (tempered by real-world Wikipedia/VATSIM verification) and brand colors metadata populated,
        and prefetches all airline logos in the background.
        """
        if not chart_data or not isinstance(chart_data, dict):
            return
        icao_u = str(icao or "").strip().upper()
        apt_rules = (self.cloud_ruleset or {}).get(icao_u) or {}
        rw_airlines = self.fetch_real_world_airport_airlines(icao_u, chart_data=chart_data)
        norm_assigned_al = normalize_airline_icao(assigned_airline)
        if norm_assigned_al in ("", "ANY", "NONE"):
            norm_assigned_al = ""

        assigned_clean = re.sub(r'^(?:GATE|STAND|PARKING|RAMP|DOCK|APRON)\s*', '', str(assigned_gate or "").strip().upper()).replace(" ", "")
        assigned_norm = re.sub(r'^([A-Z]*)0+(\d+)', r'\1\2', assigned_clean)

        unique_codes = set()
        if norm_assigned_al:
            unique_codes.add(norm_assigned_al)

        raw_stands = chart_data.get("stands") or []
        for st in raw_stands:
            s_ref = str(st.get("ref") or "")
            term = infer_airport_stand_terminal(icao_u, s_ref, st.get("terminal", ""))
            st["terminal"] = term
            if "gsx_airlines" not in st:
                raw_existing = st.get("airlines") or []
                st["gsx_airlines"] = list(raw_existing)

        def _stand_sort_key(st_item):
            sr = str(st_item.get("ref") or "").strip().upper()
            sc = re.sub(r'^(?:GATE|STAND|PARKING|RAMP|DOCK|APRON)\s*', '', sr).replace(" ", "")
            ml = re.match(r'^([A-Z]+)', sc)
            mn = re.search(r'(\d+)', sc)
            return (
                str(st_item.get("terminal") or ""),
                ml.group(1) if ml else "",
                int(mn.group(1)) if mn else 0,
                sc,
            )

        group_seq_counters = {}
        for st in sorted(raw_stands, key=_stand_sort_key):
            s_ref = str(st.get("ref") or "")
            s_clean = re.sub(r'^(?:GATE|STAND|PARKING|RAMP|DOCK|APRON)\s*', '', s_ref.strip().upper()).replace(" ", "")
            s_norm = re.sub(r'^([A-Z]*)0+(\d+)', r'\1\2', s_clean)
            term = st.get("terminal", "")
            norm_gsx_tuple = tuple(clean_and_normalize_gsx_airline_codes(st.get("gsx_airlines"), collapse_logo_twins=True))
            grp_key = ("GSX", norm_gsx_tuple) if norm_gsx_tuple else ("TERM", str(term).lower(), bool(st.get("is_cargo", False)))
            seq_idx = group_seq_counters.get(grp_key, 0)
            group_seq_counters[grp_key] = seq_idx + 1
            als = infer_stand_airlines(
                icao_u,
                s_ref,
                terminal_name=term,
                explicit_airlines=st.get("gsx_airlines"),
                is_cargo=bool(st.get("is_cargo", False)),
                is_ga=bool(st.get("is_ga", False)),
                is_military=bool(st.get("is_military", False)),
                has_jetway=bool(st.get("has_jetway", True)),
                wingspan=float(st.get("wingspan", 36.0) or 36.0),
                airport_rules=apt_rules,
                real_world_airlines=rw_airlines,
                stand_seq_override=seq_idx,
            )
            if norm_assigned_al and assigned_clean and (s_clean == assigned_clean or s_norm == assigned_norm):
                als = [norm_assigned_al] + [a for a in als if a != norm_assigned_al]
            st["airlines"] = als[:2]
            for a_c in st["airlines"]:
                unique_codes.add(a_c)

        # Attach brand styles dictionary onto chart_data so In-Game Panel VR can draw instant vector pills while PNGs load
        brand_map = {}
        for c in unique_codes:
            bg, fg, bd, iata = get_airline_brand_style(c)
            brand_map[c] = {
                "bg": bg,
                "fg": fg,
                "bd": bd,
                "iata": iata,
                "name": self.get_airline_full_name(c),
            }
        chart_data["airline_styles"] = brand_map

        if unique_codes:
            self.prefetch_airline_logos(unique_codes)

    def get_airline_full_name(self, code):
        """Returns the full human-readable airline name for a given ICAO/IATA code."""
        return get_airline_display_name(code, getattr(self, "airline_names", None))

    def _sync_msfs_community_packages(self):
        """
        Automatically keeps any installed `gatefinder-ingame-panel` folder in MSFS Community / Community2024
        synchronized with the latest local MSFS_Package files (and automatically migrates/removes any legacy
        `wildbill75-gatefinder` folder).
        """
        import shutil
        from config import find_all_possible_community_folders
        src_pkg = self._get_resource_file(os.path.join("MSFS_Package", "gatefinder-ingame-panel"))
        if not src_pkg or not os.path.isdir(src_pkg):
            src_pkg = self._get_resource_file("gatefinder-ingame-panel")
        if not src_pkg or not os.path.isdir(src_pkg):
            return

        # 1. Refresh layout.json sizes in src_pkg if writable
        try:
            layout_path = os.path.join(src_pkg, "layout.json")
            if os.path.exists(layout_path):
                with open(layout_path, "r", encoding="utf-8") as f:
                    layout_data = json.load(f)
                changed = False
                for entry in layout_data.get("content", []):
                    rel_p = entry.get("path", "").replace("/", os.sep)
                    full_p = os.path.join(src_pkg, rel_p)
                    if os.path.exists(full_p):
                        sz = os.path.getsize(full_p)
                        if entry.get("size") != sz:
                            entry["size"] = sz
                            changed = True
                if changed:
                    with open(layout_path, "w", encoding="utf-8") as f:
                        json.dump(layout_data, f, indent=2)
        except Exception:
            pass

        # 2. Sync to any existing Community / Community2024 folders where gatefinder-ingame-panel (or legacy wildbill75-gatefinder) is installed
        comm_dirs = set()
        for k in ("msfs_community_path", "msfs_community2024_path"):
            val = self.config.settings.get(k, "")
            for p in str(val).split(";"):
                if p.strip() and os.path.isdir(p.strip()):
                    comm_dirs.add(os.path.normpath(p.strip()))
        for p in find_all_possible_community_folders():
            if p and os.path.isdir(p):
                comm_dirs.add(os.path.normpath(p))

        for cdir in list(comm_dirs):
            parent = os.path.dirname(cdir)
            if parent and os.path.isdir(parent):
                for sib in ("Community", "Community2024"):
                    sp = os.path.join(parent, sib)
                    if os.path.isdir(sp):
                        comm_dirs.add(os.path.normpath(sp))

        src_real = os.path.realpath(src_pkg)
        exe_dir_norm = ""
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            if os.path.isdir(exe_dir):
                exe_dir_norm = os.path.normpath(exe_dir)
                comm_dirs.add(exe_dir_norm)
        for cdir in comm_dirs:
            legacy_pkg = os.path.join(cdir, "wildbill75-gatefinder")
            had_legacy = False
            if os.path.exists(legacy_pkg) or os.path.islink(legacy_pkg):
                try:
                    if os.path.islink(legacy_pkg):
                        os.unlink(legacy_pkg)
                    elif os.path.isdir(legacy_pkg):
                        shutil.rmtree(legacy_pkg)
                    else:
                        os.remove(legacy_pkg)
                    had_legacy = True
                except Exception:
                    pass
            dst_pkg = os.path.join(cdir, "gatefinder-ingame-panel")
            if os.path.exists(dst_pkg) or had_legacy:
                try:
                    if os.path.exists(dst_pkg) and os.path.realpath(dst_pkg) == src_real:
                        continue  # Already a symlink/junction to src_pkg
                    shutil.copytree(src_pkg, dst_pkg, dirs_exist_ok=True)
                    if not exe_dir_norm or os.path.normpath(cdir) != exe_dir_norm:
                        self._apply_fenix_efb_state_to_pkg(dst_pkg, src_pkg=src_pkg)
                except Exception:
                    pass

    def _apply_fenix_efb_state_to_pkg(self, dst_pkg: str, src_pkg: str = None):
        """
        Ensures `dst_pkg` (inside an MSFS Community folder) either includes or excludes
        the Fenix A320 EFB VFS override files (`html_ui/Pages/VCockpit/Instruments/FNX32X/...`)
        and updates `dst_pkg/layout.json` accordingly, based on `fenix_efb_enabled`.
        """
        import shutil
        if not dst_pkg or not os.path.isdir(dst_pkg):
            return
        fenix_enabled = bool(self.config.settings.get("fenix_efb_enabled", True))
        fnx_rel_dir = os.path.join("html_ui", "Pages", "VCockpit", "Instruments", "FNX32X")
        dst_fnx_dir = os.path.join(dst_pkg, fnx_rel_dir)

        if not src_pkg or not os.path.isdir(src_pkg):
            src_pkg = self._get_resource_file(os.path.join("MSFS_Package", "gatefinder-ingame-panel"))
            if not src_pkg or not os.path.isdir(src_pkg):
                src_pkg = self._get_resource_file("gatefinder-ingame-panel")

        fnx_rel_files = [
            "html_ui/Pages/VCockpit/Instruments/FNX32X/EFB/EfbHost_Captain.html",
            "html_ui/Pages/VCockpit/Instruments/FNX32X/EFB/EfbHost_FO.html",
        ]

        if fenix_enabled:
            if src_pkg and os.path.isdir(src_pkg):
                src_fnx_dir = os.path.join(src_pkg, fnx_rel_dir)
                if os.path.isdir(src_fnx_dir) and os.path.realpath(src_pkg) != os.path.realpath(dst_pkg):
                    os.makedirs(os.path.dirname(dst_fnx_dir), exist_ok=True)
                    shutil.copytree(src_fnx_dir, dst_fnx_dir, dirs_exist_ok=True)
        else:
            if os.path.exists(dst_fnx_dir):
                try:
                    shutil.rmtree(dst_fnx_dir)
                except Exception:
                    pass

        layout_path = os.path.join(dst_pkg, "layout.json")
        if os.path.exists(layout_path):
            try:
                with open(layout_path, "r", encoding="utf-8") as f:
                    layout_data = json.load(f)
                content = [
                    e for e in layout_data.get("content", [])
                    if "FNX32X/" not in str(e.get("path", "")).replace("\\", "/")
                ]
                if fenix_enabled:
                    for rel_f in fnx_rel_files:
                        full_f = os.path.join(dst_pkg, rel_f.replace("/", os.sep))
                        if os.path.isfile(full_f):
                            content.append({
                                "path": rel_f,
                                "size": os.path.getsize(full_f),
                                "date": 133760000000000000,
                            })
                for e in content:
                    full_p = os.path.join(dst_pkg, str(e.get("path", "")).replace("/", os.sep))
                    if os.path.isfile(full_p):
                        e["size"] = os.path.getsize(full_p)
                layout_data["content"] = content
                with open(layout_path, "w", encoding="utf-8") as f:
                    json.dump(layout_data, f, indent=2)
            except Exception:
                pass

    def is_fenix_efb_installed(self, extra_community_paths=None) -> bool:
        """Returns True if the Fenix A320 EFB integration files are present in any configured MSFS Community folder."""
        paths = []
        for k in ("msfs_community_path", "msfs_community2024_path"):
            v = str(self.config.settings.get(k, "")).strip()
            if v:
                paths.append(v)
        for p in (extra_community_paths or []):
            if p and str(p).strip():
                paths.append(str(p).strip())
        for cdir in paths:
            cap_html = os.path.join(
                cdir, "gatefinder-ingame-panel",
                "html_ui", "Pages", "VCockpit", "Instruments", "FNX32X", "EFB", "EfbHost_Captain.html"
            )
            if os.path.isfile(cap_html):
                return True
        return False

    def install_fenix_efb(self, extra_community_paths=None) -> dict:
        """Installs/enables the Fenix A320 EFB integration inside the user's MSFS Community folder(s)."""
        import shutil
        self.config.settings["fenix_efb_enabled"] = True
        self.config.save()

        src_pkg = self._get_resource_file(os.path.join("MSFS_Package", "gatefinder-ingame-panel"))
        if not src_pkg or not os.path.isdir(src_pkg):
            src_pkg = self._get_resource_file("gatefinder-ingame-panel")
        if not src_pkg or not os.path.isdir(src_pkg):
            return {"success": False, "error": "Could not locate source 'gatefinder-ingame-panel' package."}

        comm_dirs = []
        for p in (extra_community_paths or []):
            if p and os.path.isdir(p) and p not in comm_dirs:
                comm_dirs.append(p)
        for k in ("msfs_community_path", "msfs_community2024_path"):
            v = str(self.config.settings.get(k, "")).strip()
            if v and os.path.isdir(v) and v not in comm_dirs:
                comm_dirs.append(v)
        if not comm_dirs:
            return {"success": False, "error": "Please select a valid MSFS Community folder path first."}

        installed_in = []
        errors = []
        for cdir in comm_dirs:
            dst_pkg = os.path.join(cdir, "gatefinder-ingame-panel")
            try:
                if not os.path.exists(dst_pkg):
                    shutil.copytree(src_pkg, dst_pkg, dirs_exist_ok=True)
                self._apply_fenix_efb_state_to_pkg(dst_pkg, src_pkg=src_pkg)
                installed_in.append(cdir)
            except Exception as e:
                errors.append(f"{cdir}: {e}")
        return {"success": bool(installed_in), "installed_in": installed_in, "errors": errors}

    def uninstall_fenix_efb(self, extra_community_paths=None) -> dict:
        """Uninstalls/disables the Fenix A320 EFB integration from all MSFS Community folders."""
        from config import find_all_possible_community_folders
        self.config.settings["fenix_efb_enabled"] = False
        self.config.save()

        comm_dirs = []
        for p in (extra_community_paths or []):
            if p and os.path.isdir(p) and p not in comm_dirs:
                comm_dirs.append(p)
        for k in ("msfs_community_path", "msfs_community2024_path"):
            v = str(self.config.settings.get(k, "")).strip()
            if v and os.path.isdir(v) and v not in comm_dirs:
                comm_dirs.append(v)
        for p in find_all_possible_community_folders():
            if p and os.path.isdir(p) and p not in comm_dirs:
                comm_dirs.append(p)

        removed_from = []
        errors = []
        for cdir in comm_dirs:
            dst_pkg = os.path.join(cdir, "gatefinder-ingame-panel")
            if os.path.isdir(dst_pkg):
                try:
                    self._apply_fenix_efb_state_to_pkg(dst_pkg)
                    removed_from.append(cdir)
                except Exception as e:
                    errors.append(f"{cdir}: {e}")
        return {"success": len(errors) == 0, "removed_from": removed_from, "errors": errors}

    def _get_resource_file(self, filename):
        import sys
        candidates = []
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            candidates.append(os.path.join(exe_dir, "..", filename))
            candidates.append(os.path.join(exe_dir, filename))
        if hasattr(sys, '_MEIPASS'):
            candidates.append(os.path.join(sys._MEIPASS, filename))
        base_src = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(base_src, "..", filename))
        candidates.append(os.path.join(base_src, filename))
        candidates.append(os.path.abspath(filename))
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def _load_builtin_db(self):
        import zlib
        self.builtin_data = {}
        db_path = self._get_resource_file("default_airports_db.bin")
        if not db_path:
            return
        try:
            with open(db_path, "rb") as f:
                raw_json = zlib.decompress(f.read()).decode("utf-8")
                raw_db = json.loads(raw_json)
            for icao, compact_list in raw_db.items():
                icao_dict = {}
                for entry in compact_list:
                    name_idx, number, ptype, radius, lat, lon, has_jw, airlines = entry
                    gate_info, al_list = convert_bgl_entry_to_gate_info(
                        name_idx, number, ptype, radius, lat, lon, has_jw, airlines
                    )
                    if not gate_info:
                        continue
                    if al_list:
                        for a in al_list:
                            if a not in icao_dict:
                                icao_dict[a] = []
                            icao_dict[a].append(gate_info)
                    else:
                        if 'ANY' not in icao_dict:
                            icao_dict['ANY'] = []
                        icao_dict['ANY'].append(gate_info)
                if icao_dict:
                    self.builtin_data[icao] = icao_dict
        except Exception as e:
            print(f"Error loading default_airports_db.bin: {e}")

    # Known multi-airport bundles & city-named 3rd-party packages
    SCENERY_BUNDLE_ICAOS = {
        "apt1": {"LFBD", "LFMT", "LFRB", "LFRN", "LFSB"},
        "pack1": {"LFBD", "LFMT", "LFRB", "LFRN", "LFSB"},
        "apt2": {"LFBO", "LFKF", "LFML", "LFMN", "LFST", "LFTH"},
        "pack2": {"LFBO", "LFKF", "LFML", "LFMN", "LFST", "LFTH"},
        "apt3": {"LFLC", "LFLL", "LFOB", "LFOT", "LFQQ", "LFRS"},
        "pack3": {"LFLC", "LFLL", "LFOB", "LFOT", "LFQQ", "LFRS"},
        "apt4": {"LFBH", "LFBI", "LFBZ", "LFKB", "LFKJ", "LFMP", "LFRD", "LFRG", "LFRK", "LFRO", "LFRZ"},
        "pack4": {"LFBH", "LFBI", "LFBZ", "LFKB", "LFKJ", "LFMP", "LFRD", "LFRG", "LFRK", "LFRO", "LFRZ"},
        "marseille": {"LFML"},
        "copenhagen": {"EKCH"},
        "amsterdam": {"EHAM"},
        "schiphol": {"EHAM"},
        "athens": {"LGAV"},
        "boston": {"KBOS"},
        "barcelona": {"LEBL"},
        "miami": {"KMIA"},
        "kuwait": {"OKKK", "OKBK"},
        "paderborn": {"EDLP"},
        "sevilla": {"LEZL"},
        "gatwick": {"EGKK"},
        "heathrow": {"EGLL"},
        "stansted": {"EGSS"},
        "luton": {"EGGW"},
        "bristol": {"EGGD"},
        "fiumicino": {"LIRF"},
        "malpensa": {"LIMC"},
        "geneva": {"LSGG"},
        "zurich": {"LSZH"},
        "zuerich": {"LSZH"},
        "frankfurt": {"EDDF"},
        "munich": {"EDDM"},
        "muenchen": {"EDDM"},
        "duesseldorf": {"EDDL"},
        "dusseldorf": {"EDDL"},
        "hamburg": {"EDDH"},
        "stuttgart": {"EDDS"},
        "nuernberg": {"EDDN"},
        "nuremberg": {"EDDN"},
        "brussels": {"EBBR"},
        "charleroi": {"EBCI"},
        "gardermoen": {"ENGM"},
        "bergen": {"ENBR"},
        "tromso": {"ENTC"},
        "dubrovnik": {"LDDU"},
        "pula": {"LDPL"},
        "alicante": {"LEAL"},
        "menorca": {"LEMH"},
        "corfu": {"LGKR"},
        "kefalonia": {"LGKF"},
        "rhodes": {"LGRP"},
        "skiathos": {"LGSK"},
        "heraklion": {"LGIR"},
        "napoli": {"LIRN"},
        "firenze": {"LIRQ"},
        "prague": {"LKPR"},
        "budapest": {"LHBP"},
        "porto": {"LPPR"},
        "lisbon": {"LPPT"},
        "otopeni": {"LROP"},
        "tahiti": {"NTAA"},
        "fukuoka": {"RJFF"},
        "soekarno": {"WIII"},
    }

    def _scan_installed_msfs_packages(self):
        """
        Fast indexer for installed 3rd-party MSFS 2020 / 2024 packages across
        Community, Community2024, Official2020, Official2024, and StreamedPackages.
        Stores `self.installed_packages` and `self.installed_bgls`.
        """
        installed_bgls = set()
        installed_packages = set()
        comm_2020_set = self.config.settings.get("msfs_community_path", "")
        comm_2024_set = self.config.settings.get("msfs_community2024_path", "")

        raw_paths = []
        if comm_2020_set:
            raw_paths.extend([p.strip() for p in comm_2020_set.split(";") if p.strip()])
        if comm_2024_set:
            raw_paths.extend([p.strip() for p in comm_2024_set.split(";") if p.strip()])

        target_dirs = set()
        for raw in raw_paths:
            if os.path.exists(raw):
                target_dirs.add(raw)
            parent = os.path.dirname(raw)
            if parent and os.path.exists(parent):
                for sub in ["Community", "Community2024", "Official2020", "Official2024", "StreamedPackages"]:
                    sp = os.path.join(parent, sub)
                    if os.path.exists(sp):
                        target_dirs.add(sp)

        for ucfg in (
            os.path.expandvars(r"%LOCALAPPDATA%\Packages\Microsoft.Limitless_8wekyb3d8bbwe\LocalCache\UserCfg.opt"),
            os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator 2024\UserCfg.opt"),
            os.path.expandvars(r"%LOCALAPPDATA%\Packages\Microsoft.FlightSimulator_8wekyb3d8bbwe\LocalCache\UserCfg.opt"),
            os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator\UserCfg.opt"),
        ):
            if os.path.exists(ucfg):
                try:
                    with open(ucfg, "r", encoding="utf-8", errors="ignore") as uf:
                        for line in uf:
                            if "InstalledPackagesPath" in line:
                                m_p = re.search(r'"([^"]+)"', line)
                                if m_p and os.path.exists(m_p.group(1)):
                                    pkg_root = m_p.group(1)
                                    for sub in ["Community", "Community2024", "Official2020", "Official2024", "StreamedPackages"]:
                                        sp = os.path.join(pkg_root, sub)
                                        if os.path.exists(sp):
                                            target_dirs.add(sp)
                except Exception:
                    pass

        asobo_prefixes = (
            "asobo-", "microsoft-", "fs24-asobo-", "fs24-microsoft-",
            "fs20-asobo-", "fs20-microsoft-", "fs-base", "workingtitle-"
        )

        def _scan_pkg_dir(pkg_path, pkg_name, is_official_dir=False):
            nl = pkg_name.lower()
            if nl.endswith(".disabled") or nl in ("gatefinder-ingame-panel", "wildbill75-gatefinder"):
                return
            if is_official_dir and nl.startswith(asobo_prefixes):
                return
            installed_packages.add(nl)
            layout_path = os.path.join(pkg_path, "layout.json")
            if os.path.exists(layout_path):
                try:
                    with open(layout_path, "r", encoding="utf-8", errors="ignore") as lf:
                        layout_data = json.load(lf)
                        for entry in layout_data.get("content", []):
                            path = entry.get("path", "")
                            if path.lower().endswith(".bgl"):
                                installed_bgls.add(os.path.basename(path).lower())
                except Exception:
                    pass

        for subpath in target_dirs:
            try:
                if os.path.exists(subpath):
                    sub_base = os.path.basename(subpath).lower()
                    is_official = sub_base.startswith("official") or sub_base == "streamedpackages"
                    for item in os.listdir(subpath):
                        fullpath = os.path.join(subpath, item)
                        if os.path.isdir(fullpath):
                            if item.lower() in ["onestore", "steam"]:
                                for subitem in os.listdir(fullpath):
                                    subfullpath = os.path.join(fullpath, subitem)
                                    if os.path.isdir(subfullpath):
                                        _scan_pkg_dir(subfullpath, subitem, is_official_dir=True)
                            else:
                                _scan_pkg_dir(fullpath, item, is_official_dir=is_official)
            except Exception as e:
                print(f"Error scanning MSFS folder {subpath}: {e}")

        self.installed_packages = installed_packages
        self.installed_bgls = installed_bgls
        return installed_packages, installed_bgls

    def _has_third_party_scenery_for_airport(self, icao, afcad_path="", airport_name="", filename=""):
        installed_packages = getattr(self, "installed_packages", None)
        installed_bgls = getattr(self, "installed_bgls", None)
        if installed_packages is None or installed_bgls is None:
            installed_packages, installed_bgls = self._scan_installed_msfs_packages()

        if not installed_packages and not installed_bgls:
            return True

        icao_u = (icao or "").strip().upper()
        icao_l = icao_u.lower()
        if not icao_l:
            return False

        # 1. Check direct ICAO token or substring match in non-Asobo packages / BGLs
        has_addon = any(icao_l in pkg for pkg in installed_packages) or any(icao_l in bgl for bgl in installed_bgls)

        # 2. Check multi-airport bundles & city-named package mappings (e.g., flytampa-amsterdam, francevfr-apt1, fs20-flytampa-copenhagen)
        if not has_addon:
            for bundle_kw, icao_set in self.SCENERY_BUNDLE_ICAOS.items():
                if icao_u in icao_set:
                    if any(bundle_kw in pkg for pkg in installed_packages):
                        has_addon = True
                        break

        # 3. Check airport city/name tokens from SimBrief (if available)
        if not has_addon and airport_name:
            generic_words = {
                "airport", "international", "aeroport", "airfield", "municipal",
                "regional", "intercontinental", "metropolitan", "island", "national",
                "base", "air", "field", "saint", "santa", "north", "south", "east", "west"
            }
            for tok in re.split(r'[^a-zA-Z0-9]+', airport_name.lower()):
                if len(tok) >= 5 and tok not in generic_words:
                    if any(tok in pkg for pkg in installed_packages):
                        has_addon = True
                        break

        # 4. Check afcad_path package folder name against installed packages
        if afcad_path:
            path_lower = afcad_path.lower().replace("/", "\\")
            # Reject if afcad_path explicitly points to a default Asobo/Microsoft BGL and no addon is installed
            if any(x in path_lower for x in ("\\asobo-", "\\microsoft-", "\\fs-base", "\\apx")):
                if not has_addon:
                    return False
            bgl_filename = os.path.basename(path_lower)
            if bgl_filename in installed_bgls:
                return True
            parts = [p for p in path_lower.split("\\") if p]
            for idx, part in enumerate(parts):
                if part in ("community", "community2024", "onestore", "steam", "streamedpackages") and idx + 1 < len(parts):
                    afcad_pkg = parts[idx + 1]
                    # Strip fs20- / fs24- prefixes when comparing package names across MSFS 2020 & 2024
                    afcad_pkg_core = re.sub(r'^fs2[04]-', '', afcad_pkg)
                    for pkg in installed_packages:
                        pkg_core = re.sub(r'^fs2[04]-', '', pkg)
                        if pkg == afcad_pkg or pkg_core == afcad_pkg_core or (len(afcad_pkg_core) >= 6 and (afcad_pkg_core in pkg_core or pkg_core in afcad_pkg_core)):
                            return True

        return has_addon

    @staticmethod
    def _eval_gsx_companion_py(py_path):
        """
        Executes a companion GSX Python script (e.g. LFMN-5k9kmcwx.py, eham-flytampa.py) in a
        restricted sandbox to evaluate all CustomizedName templates, custom helper functions
        (TerminalName, MyTerminalNames, AutoGateNames, etc.), integer group keys (0..37),
        and group-level None default rules.
        Returns (exact_map, group_default_map) where:
          - exact_map: dict[sec_norm_key] -> (stand_name, terminal_name, is_disabled)
          - group_default_map: dict[group_key] -> (s_template, t_clean, current_letter, is_disabled)
        """
        exact_map = {}
        group_default_map = {}
        if not py_path or not os.path.exists(py_path):
            return exact_map, group_default_map

        try:
            try:
                with open(py_path, "r", encoding="utf-8") as pf:
                    py_text = pf.read()
            except UnicodeDecodeError:
                with open(py_path, "r", encoding="cp1252", errors="ignore") as pf:
                    py_text = pf.read()

            # Sanitize unquoted alphanumeric dict keys (e.g. `1L : (General, ),` in LSGG)
            py_clean = re.sub(r'^(\s*)(\d+[A-Za-z]+)(\s*:)', r'\1"\2"\3', py_text, flags=re.MULTILINE)

            class _CN:
                def __init__(self, name="", *args, **kwargs):
                    self.name = str(name)

            class _AltStop:
                def __init__(self, fn=None, *args, **kwargs):
                    self.fn = fn
                    self.aircraft_types = []
                    if callable(fn) and hasattr(fn, "__code__"):
                        found = set()
                        for c in getattr(fn.__code__, "co_consts", ()):
                            items = c if isinstance(c, tuple) else (c,)
                            for sub in items:
                                if isinstance(sub, str):
                                    cu = sub.strip().upper()
                                    if 3 <= len(cu) <= 6 and cu.isalnum() and cu != "UNKNOWN" and any(ch.isdigit() for ch in cu):
                                        found.add(cu)
                        self.aircraft_types = sorted(found)

            class _Dummy:
                def __init__(self, *args, **kwargs):
                    pass
                def __add__(self, other): return self
                def __radd__(self, other): return self
                def __sub__(self, other): return self
                def __mul__(self, other): return self
                def __rmul__(self, other): return self

            class _Dist(float):
                @classmethod
                def fromMeters(cls, v=0.0): return cls(v)
                @classmethod
                def fromFeet(cls, v=0.0): return cls(v * 0.3048)

            env = {
                "CustomizedName": _CN,
                "AlternativeStopPositions": _AltStop,
                "WingSpan": _Dummy,
                "AircraftRecord": _Dummy,
                "Distance": _Dist,
                "Vector3": _Dummy,
                "GATE": "gate",
                "PARKING": "parking",
                "DOCK": "dock",
                "RAMP": "ramp",
                "STAND": "stand",
                "NONE": "none",
            }
            for d_p in ("N", "NE", "E", "SE", "S", "SW", "W", "NW"):
                env[f"{d_p}_PARKING"] = f"{d_p.lower()} parking"
            for ch_code in range(ord('A'), ord('Z') + 1):
                ch = chr(ch_code)
                env[f"GATE_{ch}"] = f"gate {ch.lower()}"
                env[f"PARKING_{ch}"] = f"parking {ch.lower()}"

            exec(py_clean, env)
            parkings = env.get("parkings")
            if not isinstance(parkings, dict):
                return exact_map, group_default_map

            int_group_map = {
                0: ("none", ""),
                1: ("parking", ""),
                2: ("n parking", ""),
                3: ("ne parking", ""),
                4: ("e parking", ""),
                5: ("se parking", ""),
                6: ("s parking", ""),
                7: ("sw parking", ""),
                8: ("w parking", ""),
                9: ("nw parking", ""),
                10: ("gate", ""),
                11: ("dock", ""),
            }
            for idx_c in range(12, 38):
                let = chr(ord('A') + (idx_c - 12))
                int_group_map[idx_c] = (f"gate {let.lower()}", let)

            def _extract_tpl_from_val(val):
                items = val if isinstance(val, (tuple, list)) else (val,)
                for it in items:
                    if isinstance(it, _CN):
                        return it.name
                    if isinstance(it, (tuple, list)):
                        for sub in it:
                            if isinstance(sub, _CN):
                                return sub.name
                return None

            def _extract_ac_types_from_val(val):
                items = val if isinstance(val, (tuple, list)) else (val,)
                for it in items:
                    if isinstance(it, _AltStop) and it.aircraft_types:
                        return it.aircraft_types
                    if isinstance(it, (tuple, list)):
                        for sub in it:
                            if isinstance(sub, _AltStop) and sub.aircraft_types:
                                return sub.aircraft_types
                return []

            def _is_disabled_template(tpl_str):
                tl = tpl_str.lower()
                return any(kw in tl for kw in (
                    "do not use", "donotuse", "disabled", "deicing only",
                    "de-icing only", "deice only", "de-ice pad", "dummy"
                ))

            for grp_raw, entries in parkings.items():
                if not isinstance(entries, dict):
                    continue
                if isinstance(grp_raw, int):
                    current_group, current_letter = int_group_map.get(grp_raw, (f"none", ""))
                else:
                    current_group = str(grp_raw).lower().replace("_", " ").strip()
                    parts_g = current_group.split()
                    current_letter = parts_g[1].upper() if (len(parts_g) == 2 and len(parts_g[1]) == 1) else ""

                for k_raw, val in entries.items():
                    tpl = _extract_tpl_from_val(val)
                    if not tpl:
                        continue
                    ac_types = _extract_ac_types_from_val(val)
                    is_dis = _is_disabled_template(tpl)
                    if "|" in tpl:
                        t_part, s_part = tpl.split("|", 1)
                    else:
                        t_part, s_part = "", tpl

                    t_clean = re.sub(r'\[.*?\]', '', t_part)
                    t_clean = re.sub(r'^[>\-\s]+', '', t_clean)
                    t_clean = re.sub(r'-{2,}', ' ', t_clean).strip()

                    if k_raw is None or str(k_raw).strip() == "None":
                        group_default_map[current_group] = (s_part, t_clean, current_letter, is_dis)
                        continue

                    key_tok = str(k_raw).strip().strip('"\'')
                    t_exp = t_clean.replace("#§", "#").replace("#\ufffd", "#").replace("#", key_tok).replace("§", current_letter).replace("\ufffd", current_letter).strip()
                    s_exp = s_part.replace("#§", "#").replace("#\ufffd", "#").replace("#", key_tok).replace("§", current_letter).replace("\ufffd", current_letter).strip()
                    s_exp = re.sub(r'^(?:Gate|Stand|Stands|Parking|Dock|Ramp|VIP\s+Gate)\s+', '', s_exp, flags=re.IGNORECASE).strip()
                    # Extract aircraft type hints from parenthetical or hyphenated annotations (e.g. "A7 (A320/B738))", "33 - B748 SUITABLE")
                    for m_ac in re.findall(r'\b([AB]\d{3}[A-Z]?|ATR\d*|E\d{3}|CRJ\d*|MD\d{2}|DH8[A-D]?)\b', s_exp.upper()):
                        if m_ac not in ac_types:
                            ac_types.append(m_ac)
                    s_exp = re.sub(r'\s*[\(\[].*$', '', s_exp)
                    s_exp = re.sub(r'\)+$', '', s_exp)
                    s_exp = re.sub(r'\s+-\s+.*$', '', s_exp)
                    s_exp = re.sub(r'\s+MARS\s+.*$', '', s_exp, flags=re.IGNORECASE).strip()
                    sec_key = f"{current_group} {key_tok.lower()}".strip()
                    exact_map[sec_key] = (s_exp.upper() if s_exp else key_tok.upper(), t_exp, is_dis, ac_types)

        except Exception as e:
            print(f"[GSX Py Sandbox] Warning parsing {os.path.basename(py_path)}: {e}")

        return exact_map, group_default_map

    def _find_companion_py_for_icao(self, icao, ini_filepath=""):
        if ini_filepath and os.path.exists(ini_filepath[:-4] + ".py"):
            return ini_filepath[:-4] + ".py"
        gsx_path = self.config.settings.get("gsx_profile_path", "")
        icao_u = (icao or "").strip().upper()
        if gsx_path and os.path.exists(gsx_path) and icao_u:
            try:
                for fn in os.listdir(gsx_path):
                    fn_l = fn.lower()
                    if fn_l.endswith(".py") and not fn_l.endswith("_handler.py") and fn_l != "sendtraffic.py":
                        if extract_icao_from_filename(fn[:-3] + ".ini") == icao_u:
                            return os.path.join(gsx_path, fn)
            except Exception:
                pass
        return ""

    def _parse_gsx_ini_file(self, icao, filepath):
        """
        Parses a single GSX .ini file + its companion .py script (if present) into a dict
        mapping airline -> list[gate_info].
        Supports all BGL parking section prefixes (parking, gate, stand, ramp, dock, none, n..nw parking).
        """
        parser = configparser.ConfigParser(interpolation=None)
        try:
            try:
                parser.read(filepath, encoding='utf-8')
            except UnicodeDecodeError:
                parser.read(filepath, encoding='cp1252')
        except Exception:
            return None

        py_path = self._find_companion_py_for_icao(icao, filepath)
        exact_py_map, group_py_defaults = self._eval_gsx_companion_py(py_path)

        valid_prefixes = (
            'n parking_', 'n parking ', 'ne parking_', 'ne parking ',
            'e parking_', 'e parking ', 'se parking_', 'se parking ',
            's parking_', 's parking ', 'sw parking_', 'sw parking ',
            'w parking_', 'w parking ', 'nw parking_', 'nw parking ',
            'parking_', 'parking ', 'gate_', 'gate ', 'stand_', 'stand ',
            'ramp_', 'ramp ', 'dock_', 'dock ', 'none_', 'none '
        )

        def _is_parking_section(sec_l):
            if sec_l in ('general', 'jetway_rootfloor_heights', 'parkpos'):
                return False
            if sec_l.startswith(('rwy', 'runway', 'taxiway', 'twy', 'deice', 'deicing', 'da-')):
                return False
            return sec_l.startswith(valid_prefixes)

        has_any_coords_in_profile = any(
            any(k in parser[sec] for k in ('this_parking_pos', 'parkingsystem_stopposition', 'parkingsystem_objectposition', 'pushback_pos', 'pushbackleftpos'))
            for sec in parser.sections()
            if _is_parking_section(sec.lower().strip())
        )

        icao_gates = {}
        for section in parser.sections():
            sec_lower = section.lower().strip()
            if not _is_parking_section(sec_lower):
                continue
            if parser[section].get('is_deicearea', '').strip() == '1':
                continue

            prefix = ""
            for p in valid_prefixes:
                if sec_lower.startswith(p):
                    prefix = p
                    break

            if prefix:
                raw_name = section[len(prefix):].replace('_', ' ').strip().upper()
            else:
                raw_name = section.replace('_', ' ').strip().upper()

            name = raw_name
            py_term = ""
            is_disabled_stand = False
            has_py_custom = False
            py_ac_types = []
            sec_norm_key = re.sub(r'[\s_]+', ' ', sec_lower)

            if sec_norm_key in exact_py_map:
                py_entry = exact_py_map[sec_norm_key]
                name, py_term, is_disabled_stand = py_entry[:3]
                py_ac_types = py_entry[3] if len(py_entry) > 3 else []
                has_py_custom = True
            else:
                # Check group-level None default template in .py companion
                for grp_k, (s_tpl, t_tpl, grp_let, grp_dis) in group_py_defaults.items():
                    if sec_norm_key.startswith(grp_k + " "):
                        key_tok = sec_norm_key[len(grp_k) + 1:].strip().upper()
                        is_disabled_stand = grp_dis
                        py_term = t_tpl.replace("#§", "#").replace("#\ufffd", "#").replace("#", key_tok).replace("§", grp_let).replace("\ufffd", grp_let).strip()
                        s_exp = s_tpl.replace("#§", "#").replace("#\ufffd", "#").replace("#", key_tok).replace("§", grp_let).replace("\ufffd", grp_let).strip()
                        s_exp = re.sub(r'^(?:Gate|Stand|Stands|Parking|Dock|Ramp|VIP\s+Gate)\s+', '', s_exp, flags=re.IGNORECASE).strip()
                        s_exp = re.sub(r'\s*\(.*$', '', s_exp).strip()
                        s_exp = re.sub(r'\s+-\s+.*$', '', s_exp).strip()
                        s_exp = re.sub(r'\s+MARS\b.*$', '', s_exp, flags=re.IGNORECASE).strip()
                        if s_exp:
                            name = s_exp.upper()
                            has_py_custom = True
                        break

            if is_disabled_stand:
                continue

            airlines = []
            if 'airlinecodes' in parser[section]:
                airlines = clean_and_normalize_gsx_airline_codes(parser[section]['airlinecodes'])
            elif 'airline_codes' in parser[section]:
                airlines = clean_and_normalize_gsx_airline_codes(parser[section]['airline_codes'])

            wingspan = 999.0
            if 'maxwingspan' in parser[section]:
                try:
                    wingspan = float(parser[section]['maxwingspan'])
                except ValueError:
                    pass
            elif 'max_wingspan' in parser[section]:
                try:
                    wingspan = float(parser[section]['max_wingspan'])
                except ValueError:
                    pass

            if wingspan <= 5.0:
                continue

            term_explicit = parser[section].get('name', '').strip() or py_term

            g_type = "GATE"
            is_cargo = False
            is_ga = False
            is_military = False

            type_val = parser[section].get('type')
            if type_val is not None:
                type_val_str = type_val.strip()
                if type_val_str in ('12', '13'):
                    continue
                if type_val_str in ('0', '1', '2', '3'):
                    g_type = "STAND"
                    if type_val_str in ('1', '2', '3') and (wingspan < 31.0 or ("ga" in sec_lower and "gate" not in sec_lower) or name.endswith("G")):
                        is_ga = True
                elif type_val_str in ('4', '14'):
                    g_type = "STAND"
                elif type_val_str == '5':
                    g_type = "RAMP"
                    is_cargo = True
                elif type_val_str in ('6', '7'):
                    g_type = "RAMP"
                    is_military = True
                elif type_val_str in ('8', '9', '10', '15'):
                    g_type = "GATE"
                elif type_val_str == '11':
                    g_type = "DOCK"
                    if wingspan < 31.0:
                        is_ga = True
            else:
                if "ramp" in sec_lower:
                    g_type = "RAMP"
                elif "dock" in sec_lower:
                    g_type = "DOCK"
                elif "stand" in sec_lower:
                    g_type = "STAND"
                elif "gate" in sec_lower:
                    g_type = "GATE"
                else:
                    g_type = "STAND"

            term_l = term_explicit.lower()
            if "cargo" in sec_lower or ("cargo" in term_l and "pax" not in term_l and "passenger" not in term_l and "remote" not in term_l):
                is_cargo = True
            elif is_cargo and term_l and any(k in term_l for k in ("terminal", "pier", "concourse", "satellite")) and "cargo" not in term_l and "fret" not in term_l:
                is_cargo = False
            if "mil" in sec_lower or "military" in sec_lower or "military" in term_l:
                is_military = True
            if ("ga" in sec_lower and "gate" not in sec_lower) or "general aviation" in term_l or term_l.startswith("ga "):
                is_ga = True

            has_jetway = None
            if 'hasjetway' in parser[section]:
                try:
                    has_jetway = int(parser[section]['hasjetway']) == 1
                except ValueError:
                    pass

            if has_jetway is None:
                has_jetway = (g_type == "GATE")

            lat, lon = None, None
            heading = None
            for pos_key in ('this_parking_pos', 'parkingsystem_stopposition', 'parkingsystem_objectposition', 'pushback_pos', 'pushbackleftpos'):
                if pos_key in parser[section]:
                    parts = parser[section][pos_key].split()
                    if len(parts) >= 2:
                        try:
                            lat, lon = float(parts[0]), float(parts[1])
                            if len(parts) >= 3 and pos_key in ('this_parking_pos', 'parkingsystem_stopposition', 'parkingsystem_objectposition'):
                                heading = float(parts[2]) % 360.0
                            break
                        except ValueError:
                            pass
            if heading is None:
                for h_key in ('this_parking_pos', 'parkingsystem_stopposition', 'parkingsystem_objectposition'):
                    if h_key in parser[section]:
                        parts = parser[section][h_key].split()
                        if len(parts) >= 3:
                            try:
                                heading = float(parts[2]) % 360.0
                                break
                            except ValueError:
                                pass

            if has_any_coords_in_profile and (lat is None or lon is None):
                continue

            no_pushback = (parser[section].get('pushback', '').strip() == '0')

            gate_info = {
                'name': name,
                'raw_name': raw_name,
                'has_py_custom': has_py_custom,
                'py_aircraft_types': py_ac_types,
                'wingspan': wingspan,
                'terminal': term_explicit,
                'type': g_type,
                'lat': lat,
                'lon': lon,
                'heading': heading,
                'no_pushback': no_pushback,
                'has_jetway': has_jetway,
                'is_cargo': is_cargo,
                'is_ga': is_ga,
                'is_military': is_military,
                'airlines': airlines
            }

            if airlines:
                for a in airlines:
                    if a not in icao_gates:
                        icao_gates[a] = []
                    icao_gates[a].append(gate_info)
            else:
                if 'ANY' not in icao_gates:
                    icao_gates['ANY'] = []
                icao_gates['ANY'].append(gate_info)

        return icao_gates

    def load_data(self):
        gsx_path = self.config.settings.get("gsx_profile_path", "")
        if not isinstance(getattr(self, "data", None), _LazyGSXDataDict):
            self.data = _LazyGSXDataDict(self)
        self.coherent_airports = {}
        self.airport_names = {}
        self._scan_installed_msfs_packages()
        ini_index = {}
        if gsx_path and os.path.exists(gsx_path):
            try:
                for filename in os.listdir(gsx_path):
                    if filename.lower().endswith('.ini'):
                        icao = extract_icao_from_filename(filename)
                        if not icao:
                            continue
                        icao_u = icao.strip().upper()
                        filepath = os.path.join(gsx_path, filename)
                        if icao_u not in ini_index:
                            ini_index[icao_u] = []
                        ini_index[icao_u].append(filepath)
            except Exception:
                pass
        self.data.reset_index(ini_index)

    def _load_airlines(self):
        return {
            "AFR": "Air France",
            "AFV": "Air France Virtuelle",
            "VAF": "Virtual Air France",
            "HOP": "Air France Hop",
            "DLH": "Lufthansa",
            "DLHV": "LH Virtual (Lufthansa)",
            "CLH": "Lufthansa CityLine",
            "LHX": "Lufthansa City Airlines",
            "OCN": "Discover Airlines",
            "EWG": "Eurowings",
            "EWL": "Eurowings Europe",
            "CFG": "Condor",
            "BAW": "British Airways",
            "BAWV": "British Airways Virtual",
            "CFE": "BA CityFlyer",
            "SHT": "British Airways Shuttle",
            "VIR": "Virgin Atlantic",
            "LOG": "Loganair",
            "AUR": "Aurigny Air Services",
            "EAI": "Emerald Airlines",
            "EIN": "Aer Lingus",
            "RYR": "Ryanair",
            "RYRV": "vRYR (Ryanair Virtual)",
            "RUK": "Ryanair UK",
            "MAY": "Malta Air",
            "RYS": "Buzz (Ryanair Sun)",
            "EZY": "easyJet",
            "EZYV": "vEZY (easyJet Virtual)",
            "EZV": "vEZY (easyJet Virtual)",
            "EJU": "easyJet Europe",
            "EZS": "easyJet Switzerland",
            "WZZ": "Wizz Air",
            "WMT": "Wizz Air Malta",
            "WUK": "Wizz Air UK",
            "WAZ": "Wizz Air Abu Dhabi",
            "BLX": "TUIfly Nordic",
            "TOM": "TUI Airways",
            "TUI": "TUI fly",
            "TFL": "TUI fly Netherlands",
            "JAF": "TUI fly Belgium",
            "VKG": "Sunclass Airlines",
            "NVR": "Novair",
            "SAS": "Scandinavian Airlines",
            "SZS": "SAS Connect",
            "SVS": "SAS Link",
            "VSAS": "Virtual Scandinavian Airlines",
            "NAX": "Norwegian Air Shuttle",
            "NSZ": "Norwegian Air Sweden",
            "NOZ": "Norwegian Air Norway",
            "IBK": "Norwegian Air International",
            "BRA": "BRA Braathens Regional",
            "FIN": "Finnair",
            "FCM": "Nordic Regional Airlines",
            "ICE": "Icelandair",
            "FPY": "PLAY Airlines",
            "BTI": "airBaltic",
            "EST": "Nordica",
            "LOT": "LOT Polish Airlines",
            "ENT": "Enter Air",
            "TVS": "Smartwings",
            "CSA": "Czech Airlines",
            "TVP": "Smartwings Poland",
            "TVQ": "Smartwings Slovakia",
            "AUA": "Austrian Airlines",
            "SWR": "SWISS",
            "OAW": "Helvetic Airways",
            "EDW": "Edelweiss Air",
            "EDWV": "Edelweiss Virtual",
            "BEL": "Brussels Airlines",
            "BELV": "vbrussels (Brussels Virtual)",
            "KLM": "KLM Royal Dutch Airlines",
            "KLC": "KLM Cityhopper",
            "TRA": "Transavia",
            "TVF": "Transavia France",
            "CND": "Corendon Dutch Airlines",
            "CAI": "Corendon Airlines",
            "CXI": "Corendon Airlines Europe",
            "LGL": "Luxair",
            "CCM": "Air Corsica",
            "CRL": "Corsair International",
            "FPO": "ASL Airlines France",
            "FBU": "French bee",
            "IBE": "Iberia",
            "IBS": "Iberia Express",
            "ANE": "Air Nostrum",
            "VLG": "Vueling",
            "AEA": "Air Europa",
            "VOE": "Volotea",
            "VOEV": "vVOE (Volotea Virtual)",
            "IBB": "Binter Canarias",
            "PLM": "Wamos Air",
            "EVE": "Iberojet",
            "TAP": "TAP Air Portugal",
            "TAPV": "vTP (TAP Virtual)",
            "PGA": "Portugalia Airlines",
            "RZO": "SATA Internacional (Azores Airlines)",
            "SAT": "SATA Air Acores",
            "ITY": "ITA Airways",
            "AZA": "ITA Airways",
            "ITAV": "VITA Virtual (ITA Airways)",
            "NOS": "Neos",
            "DLA": "Air Dolomiti",
            "AEE": "Aegean Airlines",
            "OAL": "Olympic Air",
            "SEH": "Sky Express",
            "CYP": "Cyprus Airways",
            "AMC": "KM Malta Airlines",
            "CTN": "Croatia Airlines",
            "ASL": "Air Serbia",
            "ROU": "Air Canada Rouge",
            "ROT": "TAROM",
            "LZB": "Bulgaria Air",
            "THY": "Turkish Airlines",
            "TKJ": "AJet (AnadoluJet)",
            "PGT": "Pegasus Airlines",
            "SXS": "SunExpress",
            "FHY": "Freebird Airlines",
            "UAE": "Emirates",
            "UNER": "Emirates Virtual Airline",
            "FDB": "flydubai",
            "ETD": "Etihad Airways",
            "ABY": "Air Arabia",
            "QTR": "Qatar Airways",
            "SVA": "Saudia",
            "FAD": "flyadeal",
            "KNE": "flynas",
            "GFA": "Gulf Air",
            "OMA": "Oman Air",
            "KAC": "Kuwait Airways",
            "RJA": "Royal Jordanian",
            "MEA": "Middle East Airlines",
            "ELY": "El Al Israel Airlines",
            "ISR": "Israir Airlines",
            "AIZ": "Arkia Israeli Airlines",
            "MSR": "EgyptAir",
            "RAM": "Royal Air Maroc",
            "DAH": "Air Algerie",
            "TAR": "Tunisair",
            "ETH": "Ethiopian Airlines",
            "KQA": "Kenya Airways",
            "SAA": "South African Airways",
            "LNK": "Airlink",
            "MAU": "Air Mauritius",
            "AAL": "American Airlines",
            "VAAL": "vAAL (American Airlines Virtual)",
            "ENY": "Envoy Air",
            "JIA": "PSA Airlines",
            "PDT": "Piedmont Airlines",
            "DAL": "Delta Air Lines",
            "DALV": "Delta Virtual Air Lines",
            "EDV": "Endeavor Air",
            "UAL": "United Airlines",
            "UALV": "United Virtual Airlines",
            "SKW": "SkyWest Airlines",
            "RPA": "Republic Airways",
            "GJS": "GoJet Airlines",
            "ASH": "Mesa Airlines",
            "SWA": "Southwest Airlines",
            "SWV": "SW Virtual (Southwest)",
            "JBU": "JetBlue Airways",
            "ASA": "Alaska Airlines",
            "QXE": "Horizon Air",
            "HAL": "Hawaiian Airlines",
            "NKS": "Spirit Airlines",
            "NKSV": "vSpirit (Spirit Virtual)",
            "FFT": "Frontier Airlines",
            "AAY": "Allegiant Air",
            "SCX": "Sun Country Airlines",
            "MXY": "Breeze Airways",
            "VXP": "Avelo Airlines",
            "ACA": "Air Canada",
            "JZA": "Air Canada Express (Jazz)",
            "WJA": "WestJet",
            "TSC": "Air Transat",
            "POE": "Porter Airlines",
            "SWG": "Sunwing Airlines",
            "FXX": "Flair Airlines",
            "AMX": "Aeromexico",
            "VOI": "Volaris",
            "VIV": "Viva Aerobus",
            "CMP": "Copa Airlines",
            "AVA": "Avianca",
            "LAN": "LATAM Airlines",
            "TAM": "LATAM Brasil",
            "LPE": "LATAM Peru",
            "AZU": "Azul Brazilian Airlines",
            "GLO": "GOL Linhas Aereas",
            "ARG": "Aerolineas Argentinas",
            "SIA": "Singapore Airlines",
            "TGW": "Scoot",
            "CPA": "Cathay Pacific",
            "CPAV": "Cathay Pacific Virtual",
            "HKE": "HK Express",
            "ANA": "All Nippon Airways",
            "JAL": "Japan Airlines",
            "APJ": "Peach Aviation",
            "KAL": "Korean Air",
            "AAR": "Asiana Airlines",
            "JNA": "Jin Air",
            "TWB": "T'way Air",
            "EVA": "EVA Air",
            "CAL": "China Airlines",
            "SJX": "Starlux Airlines",
            "CCA": "Air China",
            "CSN": "China Southern Airlines",
            "CES": "China Eastern Airlines",
            "CHH": "Hainan Airlines",
            "CXA": "XiamenAir",
            "AIC": "Air India",
            "IGO": "IndiGo",
            "THA": "Thai Airways",
            "MAS": "Malaysia Airlines",
            "AXM": "AirAsia",
            "GIA": "Garuda Indonesia",
            "PAL": "Philippine Airlines",
            "CEB": "Cebu Pacific",
            "HVN": "Vietnam Airlines",
            "VJC": "VietJet Air",
            "QFA": "Qantas",
            "QLK": "QantasLink",
            "JST": "Jetstar Airways",
            "VOZ": "Virgin Australia",
            "ANZ": "Air New Zealand",
            "EXS": "Jet2.com",
            "EXSV": "Jet2 Virtual",
            "PVA": "PVA Historical Group",
            "WAT": "Walker Air Transport",
            "FLUK": "FlyUK Virtual Airways",
            "FLY": "FlyUK Virtual Airways",
            "FDX": "FedEx Express",
            "FDXV": "vDHL / FedEx Cargo Virtual",
            "UPS": "UPS Airlines",
            "UPSV": "UPS Virtual Cargo",
            "DHL": "DHL Aviation",
            "DHLV": "vDHL Group",
            "BCS": "European Air Transport (DHL)",
            "DHK": "DHL Air UK",
            "CLX": "Cargolux",
            "ICV": "Cargolux Italia",
            "BOX": "AeroLogic",
            "BOXV": "BoxVirtual (Freighter Fleet)",
            "GTI": "Atlas Air",
            "CKS": "Kalitta Air",
            "PAC": "Polar Air Cargo",
            "ABX": "ABX Air",
            "GEC": "Lufthansa Cargo",
            "MPH": "Martinair Cargo",
            "NCA": "Nippon Cargo Airlines",
            "SQC": "Singapore Airlines Cargo",
            "CKK": "China Cargo Airlines",
            **{k: v for k, v in AIRLINE_FULL_NAMES.items() if k not in ("ANY", "NONE")},
        }

    def _fetch_cloud_ruleset(self):
        merged = {}
        local_file = self._get_resource_file("airlines_terminals.json")
        if local_file and os.path.exists(local_file):
            try:
                with open(local_file, 'r', encoding='utf-8') as f:
                    merged.update(json.load(f))
            except Exception:
                pass

        cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cloud_rules_cache.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    for k, v in cached.items():
                        if k not in merged:
                            merged[k] = v
            except Exception:
                pass

        def _refresh_remote():
            url = "https://raw.githubusercontent.com/wildbill75/gsx-gatefinder/main/airlines_terminals.json"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'GateFinder-Client'})
                with urllib.request.urlopen(req, timeout=2.5) as response:
                    remote_data = json.loads(response.read().decode('utf-8'))
                    if isinstance(remote_data, dict):
                        for k, v in remote_data.items():
                            if k not in self.cloud_ruleset:
                                self.cloud_ruleset[k] = v
                        try:
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                json.dump(self.cloud_ruleset, f)
                        except Exception:
                            pass
            except Exception:
                pass

        threading.Thread(target=_refresh_remote, daemon=True).start()
        return merged

    def fetch_osm_gates(self, icao, lat=None, lon=None):
        cache_key = f"{icao}_{lat}_{lon}" if (lat and lon) else icao
        if cache_key in self.osm_cache:
            return self.osm_cache[cache_key], None

        chart = self.taxi_router.fetch_airport_vector_data(icao, center_lat=lat, center_lon=lon)
        osm_stands = (chart or {}).get("osm_stands") or (chart or {}).get("stands") or []
        if not osm_stands:
            return {}, "Failed to fetch OSM data"

        bgl_stands = []
        if icao in self.builtin_data:
            for al_list in self.builtin_data[icao].values():
                for bg in al_list:
                    if bg.get("lat") is not None and bg.get("lon") is not None:
                        bgl_stands.append(bg)

        gates = {}
        for p in osm_stands:
            ref = p.get("ref")
            p_lat = p.get("lat")
            p_lon = p.get("lon")
            if not ref or p_lat is None or p_lon is None:
                continue
            len_m = float(p.get("length_m") or 0.0)
            has_jetway = bool(p.get("has_jetway", False))

            nearest_bgl = None
            best_d = 9999.0
            for bg in bgl_stands:
                dm = haversine(p_lat, p_lon, bg["lat"], bg["lon"])
                if dm < best_d:
                    best_d = dm
                    nearest_bgl = bg

            if nearest_bgl and best_d <= 45.0 and nearest_bgl.get("has_jetway"):
                has_jetway = True

            min_neighbor_d = 9999.0
            for other in osm_stands:
                if other is not p and other.get("lat") is not None and other.get("lon") is not None:
                    nd = haversine(p_lat, p_lon, other["lat"], other["lon"])
                    if nd < min_neighbor_d:
                        min_neighbor_d = nd

            is_ga = False
            max_ws = 36.0
            if len_m >= 68.0:
                max_ws = 65.0
            elif 0.0 < len_m < 14.0 and not has_jetway:
                is_ga = True
                max_ws = 24.0
            elif min_neighbor_d < 18.0 and not has_jetway and len_m < 20.0:
                is_ga = True
                max_ws = 24.0
            elif nearest_bgl and best_d <= 40.0 and nearest_bgl.get("is_ga") and nearest_bgl.get("wingspan", 36.0) < 28.0 and not has_jetway:
                is_ga = True
                max_ws = float(nearest_bgl.get("wingspan", 24.0))

            if nearest_bgl and best_d <= 40.0 and not is_ga:
                max_ws = max(max_ws, float(nearest_bgl.get("wingspan", 36.0)))

            gates[ref] = {
                "lat": p_lat,
                "lon": p_lon,
                "heading": p.get("heading"),
                "has_jetway": has_jetway,
                "is_ga": is_ga,
                "wingspan": max_ws
            }

        self.osm_cache[cache_key] = gates
        return gates, None

    def build_coherent_airport_data(self, icao, airport_name="", default_lat=None, default_lon=None):
        """
        On-the-fly 2-Airport Coherent Builder:
        Constructs a unified, 100% consistent stand/terminal/coordinate dictionary for `icao`
        by fusing:
          1. Installed 3rd-party Scenery + GSX (.ini + sandboxed .py companion script) if present,
          2. OpenStreetMap vector geometry (parking_position nodes/ways + terminal building polygons),
          3. Built-in MSFS BGL database (airline codes, jetway flags, wingspan radii).
        Caches the result in `self.coherent_airports[icao]`.
        """
        icao_u = (icao or "").strip().upper()
        if not icao_u:
            return None
        self.ensure_initialized()
        if not hasattr(self, "coherent_airports"):
            self.coherent_airports = {}
        if icao_u in self.coherent_airports and self.coherent_airports[icao_u]:
            return self.coherent_airports[icao_u]

        # 1. Re-check GSX folder specifically for `icao_u` using `airport_name` from SimBrief
        # (catches city-named addons whose name is only known after SimBrief OFP is fetched)
        gsx_path = self.config.settings.get("gsx_profile_path", "")
        if icao_u not in self.data and gsx_path and os.path.exists(gsx_path):
            try:
                for filename in os.listdir(gsx_path):
                    if filename.lower().endswith(".ini") and extract_icao_from_filename(filename) == icao_u:
                        filepath = os.path.join(gsx_path, filename)
                        parsed_gates = self._parse_gsx_ini_file(icao_u, filepath)
                        if parsed_gates:
                            self.data[icao_u] = parsed_gates
                            break
            except Exception:
                pass

        # 2. Fetch OpenStreetMap vector geometry & stands (cached in TaxiRouter & osm_cache)
        if default_lat is None or default_lon is None:
            for src_map in (self.data.get(icao_u), self.builtin_data.get(icao_u)):
                if not src_map:
                    continue
                pts_ll = [
                    (float(g["lat"]), float(g["lon"]))
                    for gl in src_map.values()
                    for g in gl
                    if g.get("lat") is not None and g.get("lon") is not None
                ]
                if pts_ll:
                    default_lat = sum(p[0] for p in pts_ll) / len(pts_ll)
                    default_lon = sum(p[1] for p in pts_ll) / len(pts_ll)
                    break

        osm_dict, _ = self.fetch_osm_gates(icao_u, lat=default_lat, lon=default_lon)
        chart = self.taxi_router.fetch_airport_vector_data(icao_u, center_lat=default_lat, center_lon=default_lon)

        # Extract named & unnamed OSM terminal polygons (excluding fire stations / ATC towers) for spatial terminal assignment
        named_terminals = []
        unnamed_terminals = []
        for t_poly in (chart or {}).get("terminals", []):
            t_name = (t_poly.get("name") or "").strip()
            t_pts = t_poly.get("points") or []
            if not t_pts:
                continue
            if t_name and re.search(r'terminal|term|hall|concourse|pier|sat|dock|jet[eé]e|orly\s*\d|fret|cargo|affaires|general\s+aviation|vip', t_name, re.I):
                if not re.search(r'sslia|pompier|fire|tower|tour\s+de', t_name, re.I):
                    named_terminals.append((t_name, t_pts))
            elif not t_name:
                unnamed_terminals.append(t_pts)

        def _infer_spatial_terminal(lat_v, lon_v):
            if lat_v is None or lon_v is None or not named_terminals:
                return ""
            best_t = ""
            best_d = 9999.0
            for t_name, t_pts in named_terminals:
                for pt in t_pts:
                    d = haversine(lat_v, lon_v, pt[0], pt[1])
                    if d < best_d:
                        best_d = d
                        best_t = t_name
            if best_d > 145.0:
                return ""
            # If stand is > 85m from the nearest named terminal, but sits right next (<= 55m) to an unnamed terminal building,
            # do not falsely assign the distant named terminal (e.g. EGKK South Terminal vs North Terminal).
            if best_d > 85.0 and unnamed_terminals:
                for u_pts in unnamed_terminals:
                    for pt in u_pts:
                        if haversine(lat_v, lon_v, pt[0], pt[1]) <= 55.0:
                            return ""
            return best_t

        # CASE A: 3rd-Party Addon with GSX Profile Installed -> Fuse GSX stands with OSM (< 18m)
        if icao_u in self.data and self.data[icao_u]:
            coherent_db = {}
            enriched_cache = {}
            for al_k, g_list in self.data[icao_u].items():
                coherent_db[al_k] = []
                for g_orig in g_list:
                    cache_key = (
                        g_orig.get("name", ""),
                        g_orig.get("raw_name", ""),
                        g_orig.get("lat"),
                        g_orig.get("lon"),
                        g_orig.get("terminal", ""),
                    )
                    if cache_key in enriched_cache:
                        coherent_db[al_k].append(dict(enriched_cache[cache_key]))
                        continue
                    g = dict(g_orig)
                    g_lat, g_lon = g.get("lat"), g.get("lon")
                    # Spatial GPS fusion with OSM stands (< 18m)
                    if g_lat is not None and g_lon is not None and osm_dict:
                        best_ref = None
                        best_d = 9999.0
                        for o_ref, o_info in osm_dict.items():
                            d = haversine(g_lat, g_lon, o_info["lat"], o_info["lon"])
                            if d < best_d:
                                best_d = d
                                best_ref = o_ref
                        if best_ref and best_d <= 18.0:
                            g["osm_ref"] = best_ref
                            if g.get("heading") is None and osm_dict[best_ref].get("heading") is not None:
                                g["heading"] = osm_dict[best_ref]["heading"]
                    elif (g_lat is None or g_lon is None) and osm_dict:
                        # Fill missing coordinates from OSM if stand name matches
                        g_tok = clean_gate_token(g.get("name", ""))
                        r_tok = clean_gate_token(g.get("raw_name", ""))
                        for o_ref, o_info in osm_dict.items():
                            o_tok = clean_gate_token(o_ref)
                            if o_tok and (o_tok == g_tok or o_tok == r_tok):
                                g["lat"] = o_info["lat"]
                                g["lon"] = o_info["lon"]
                                g["osm_ref"] = o_ref
                                if g.get("heading") is None:
                                    g["heading"] = o_info.get("heading")
                                break
                    raw_g_term = (g.get("terminal") or "").strip()
                    is_generic_gate_group = bool(
                        re.match(r"^(?:gate|stand|parking|ramp|apron|dock)\s+[a-z0-9]{1,3}$", raw_g_term, re.I)
                    )
                    if (not raw_g_term or is_generic_gate_group) and g.get("lat") is not None:
                        sp_term = _infer_spatial_terminal(g["lat"], g["lon"])
                        if sp_term:
                            g["terminal"] = sp_term
                    g["terminal"] = infer_airport_stand_terminal(icao_u, g.get("name", ""), g.get("terminal", ""))
                    enriched_cache[cache_key] = g
                    coherent_db[al_k].append(g)
            self.coherent_airports[icao_u] = coherent_db
            return coherent_db

        # CASE B: Pure Asobo / Default Airport (or standalone .py only) -> Fuse OpenStreetMap stands with Built-in BGL DB
        if osm_dict:
            standalone_py_exact = {}
            py_only_path = self._find_companion_py_for_icao(icao_u)
            if py_only_path:
                ex_m, _ = self._eval_gsx_companion_py(py_only_path)
                for sec_k, py_val in ex_m.items():
                    s_n, t_n, is_dis = py_val[:3]
                    py_ac = py_val[3] if len(py_val) > 3 else []
                    tok_s = clean_gate_token(s_n)
                    if tok_s:
                        standalone_py_exact[tok_s] = (s_n, t_n, is_dis, py_ac)
                    parts_sk = sec_k.split()
                    if parts_sk:
                        tok_raw = clean_gate_token(parts_sk[-1])
                        if tok_raw and tok_raw not in standalone_py_exact:
                            standalone_py_exact[tok_raw] = (s_n, t_n, is_dis, py_ac)

            coherent_db = {"ANY": []}
            bgl_db = self.builtin_data.get(icao_u) or {}
            # Build flat list of unique BGL stands with their airlines list
            bgl_map = {}
            for al_code, al_list in bgl_db.items():
                for bg in al_list:
                    b_key = (bg.get("name"), bg.get("lat"), bg.get("lon"))
                    if b_key not in bgl_map:
                        b_copy = dict(bg)
                        b_copy["airlines"] = set()
                        bgl_map[b_key] = b_copy
                    if al_code != "ANY":
                        bgl_map[b_key]["airlines"].add(al_code)
            bgl_unique = list(bgl_map.values())

            for o_ref, o_info in osm_dict.items():
                o_tok = clean_gate_token(o_ref)
                py_s_name, py_t_name, py_dis, py_ac_list = standalone_py_exact.get(o_tok, (None, None, False, []))
                if py_dis:
                    continue
                o_lat = o_info["lat"]
                o_lon = o_info["lon"]
                nearest_bgl = None
                best_d = 9999.0
                for bg in bgl_unique:
                    if bg.get("lat") is not None and bg.get("lon") is not None:
                        d = haversine(o_lat, o_lon, bg["lat"], bg["lon"])
                        if d < best_d:
                            best_d = d
                            nearest_bgl = bg

                matched_bgl = nearest_bgl if (nearest_bgl and best_d <= 38.0) else None
                has_jw = bool(o_info.get("has_jetway") or (matched_bgl and matched_bgl.get("has_jetway")))
                max_ws = float(o_info.get("wingspan", 36.0))
                if matched_bgl and not o_info.get("is_ga"):
                    max_ws = max(max_ws, float(matched_bgl.get("wingspan", 36.0)))

                is_generic_py_t = bool(
                    py_t_name and re.match(r"^(?:gate|stand|parking|ramp|apron|dock)\s+[a-z0-9]{1,3}$", str(py_t_name).strip(), re.I)
                )
                sp_term = (_infer_spatial_terminal(o_lat, o_lon) or py_t_name or "") if is_generic_py_t else (py_t_name or _infer_spatial_terminal(o_lat, o_lon))
                sp_term = infer_airport_stand_terminal(icao_u, py_s_name or o_ref, sp_term)
                sp_term_l = sp_term.lower()
                is_ga = bool(
                    o_info.get("is_ga", False)
                    or (matched_bgl and matched_bgl.get("is_ga", False) and not has_jw)
                    or "affaires" in sp_term_l
                    or "general aviation" in sp_term_l
                )
                is_cargo = bool(
                    (matched_bgl and matched_bgl.get("is_cargo", False))
                    or "cargo" in o_ref.lower()
                    or (("fret" in sp_term_l or "cargo" in sp_term_l) and "pax" not in sp_term_l)
                )
                is_mil = bool(matched_bgl and matched_bgl.get("is_military", False))
                g_type = "RAMP" if is_cargo else ("GATE" if has_jw else "STAND")
                al_set = sorted(list(matched_bgl["airlines"])) if matched_bgl else []

                gate_info = {
                    "name": py_s_name or o_ref,
                    "raw_name": matched_bgl["name"] if matched_bgl else o_ref,
                    "osm_ref": o_ref,
                    "py_aircraft_types": py_ac_list,
                    "wingspan": max_ws,
                    "terminal": sp_term,
                    "type": g_type,
                    "lat": o_lat,
                    "lon": o_lon,
                    "heading": o_info.get("heading") if o_info.get("heading") is not None else (matched_bgl.get("heading") if matched_bgl else None),
                    "no_pushback": False,
                    "has_jetway": has_jw,
                    "is_cargo": is_cargo,
                    "is_ga": is_ga,
                    "is_military": is_mil,
                    "airlines": al_set
                }
                coherent_db["ANY"].append(gate_info)
                for a_c in al_set:
                    if a_c not in coherent_db:
                        coherent_db[a_c] = []
                    coherent_db[a_c].append(gate_info)

            self.coherent_airports[icao_u] = coherent_db
            return coherent_db

        # CASE C: Fallback to Built-in BGL DB if OSM has no stands for this airport
        if icao_u in self.builtin_data:
            self.coherent_airports[icao_u] = self.builtin_data[icao_u]
            return self.builtin_data[icao_u]

        return None

    def peek_latest_simbrief_ofp(self, username):
        """
        Lightweight non-intrusive check of the user's latest SimBrief OFP metadata
        (ofp_id, origin, destination, planned runways, airline, aircraft) to detect
        when a new OFP or turnaround flight plan has been generated.
        """
        if not username or not str(username).strip():
            return None
        try:
            from urllib.parse import quote
            username_clean = str(username).strip()
            cb = int(time.time() * 1000)
            if username_clean.isdigit():
                url = f"https://www.simbrief.com/api/xml.fetcher.php?userid={username_clean}&json=1&_={cb}"
            else:
                url = f"https://www.simbrief.com/api/xml.fetcher.php?username={quote(username_clean)}&json=1&_={cb}"
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'GateFinder-Client',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache'
                }
            )
            with urllib.request.urlopen(req, timeout=5.0) as response:
                data = json.loads(response.read().decode('utf-8'))
            origin = data.get('origin', {}).get('icao_code', '')
            origin_name = self.get_airport_display_name(origin, data.get('origin', {}).get('name', ''))
            origin_rwy = data.get('origin', {}).get('plan_rwy', '')
            destination = data.get('destination', {}).get('icao_code', '')
            dest_name = self.get_airport_display_name(destination, data.get('destination', {}).get('name', ''))
            dest_rwy = data.get('destination', {}).get('plan_rwy', '')
            params_block = data.get('params', {}) if isinstance(data.get('params'), dict) else {}
            req_id = str(params_block.get('request_id') or '')
            t_gen = str(params_block.get('time_generated') or '')
            ofp_id = f"{req_id}_{t_gen}_{origin}_{destination}" if (req_id or t_gen) else f"{origin}_{destination}"
            general = data.get('general', {}) if isinstance(data.get('general'), dict) else {}
            airline = general.get('icao_airline', '') or general.get('airline', '')
            flight_num = general.get('flight_number', '')
            ac_block = data.get('aircraft', {}) if isinstance(data.get('aircraft'), dict) else {}
            aircraft = ac_block.get('name') or ac_block.get('icaocode', '')
            if not origin or not destination:
                return None
            return {
                "ofp_id": ofp_id,
                "origin": origin,
                "origin_name": origin_name,
                "origin_rwy": origin_rwy,
                "destination": destination,
                "dest_name": dest_name,
                "dest_rwy": dest_rwy,
                "airline": airline,
                "flight_number": flight_num,
                "aircraft": aircraft
            }
        except Exception:
            return None

    def get_flight_data(self, username, on_turnaround_check=None, progress_callback=None, _mock_data=None, turnaround_keep_gate=None):
        def _report_progress(pct, msg):
            if progress_callback:
                try:
                    progress_callback(pct, msg)
                except Exception:
                    pass

        self.ensure_initialized(progress_callback=_report_progress)
        _report_progress(0.10, "Fetching SimBrief OFP...")
        from concurrent.futures import ThreadPoolExecutor
        check_traffic = self.config.settings.get("check_online_traffic", True)
        traffic_executor = None
        traffic_future = None
        if check_traffic and not _mock_data:
            traffic_executor = ThreadPoolExecutor(max_workers=1)
            traffic_future = traffic_executor.submit(self.network_checker.fetch_data)

        try:
            if _mock_data:
                data = _mock_data
            else:
                from urllib.parse import quote
                username_clean = username.strip()
                cb = int(time.time() * 1000)
                if username_clean.isdigit():
                    url = f"https://www.simbrief.com/api/xml.fetcher.php?userid={username_clean}&json=1&_={cb}"
                else:
                    url = f"https://www.simbrief.com/api/xml.fetcher.php?username={quote(username_clean)}&json=1&_={cb}"
                    
                req = urllib.request.Request(
                    url,
                    headers={
                        'User-Agent': 'GateFinder-Client',
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache'
                    }
                )
                try:
                    with urllib.request.urlopen(req, timeout=8) as response:
                        data = json.loads(response.read().decode('utf-8'))
                except urllib.error.HTTPError as http_err:
                    try:
                        err_body = http_err.read().decode('utf-8')
                        err_json = json.loads(err_body)
                        st = err_json.get("fetch", {}).get("status", "")
                        if st:
                            raise Exception(st)
                    except urllib.error.HTTPError:
                        pass
                    except Exception as parsed_ex:
                        if str(parsed_ex) != str(http_err):
                            raise parsed_ex
                    raise Exception("Unknown SimBrief ID or no active OFP found.")
        finally:
            if traffic_executor:
                traffic_executor.shutdown(wait=False)
            
        origin = data.get('origin', {}).get('icao_code', '')
        origin_rwy = data.get('origin', {}).get('plan_rwy', '')
        if origin:
            self.airport_names[origin] = self.get_airport_display_name(origin, data.get('origin', {}).get('name', ''))
        
        destination = data.get('destination', {}).get('icao_code', '')
        dest_rwy = data.get('destination', {}).get('plan_rwy', '')
        if destination:
            self.airport_names[destination] = self.get_airport_display_name(destination, data.get('destination', {}).get('name', ''))
        
        params_block = data.get('params', {}) if isinstance(data.get('params'), dict) else {}
        req_id = str(params_block.get('request_id') or '')
        t_gen = str(params_block.get('time_generated') or '')
        ofp_id = f"{req_id}_{t_gen}_{origin}_{destination}" if (req_id or t_gen) else f"{origin}_{destination}"
        
        general = data.get('general', {})
        airline = general.get('icao_airline', '')
        if not airline:
            airline = general.get('airline', '')

        atc_block = data.get('atc', {}) if isinstance(data.get('atc'), dict) else {}
        ofp_callsign = str(atc_block.get('callsign') or '').strip().upper()
        if not ofp_callsign:
            fl_num = str(general.get('flight_number') or '').strip().upper()
            if airline and fl_num:
                ofp_callsign = f"{airline.strip().upper()}{fl_num}"
            elif general.get('callsign'):
                ofp_callsign = str(general.get('callsign')).strip().upper()

        sc_self = getattr(self, "simconnect_manager", None)
        u_lat_self = None
        u_lon_self = None
        if sc_self and sc_self.connected and not getattr(sc_self, "in_menu", False):
            u_lat_self = sc_self.user_lat
            u_lon_self = sc_self.user_lon
            
        ac_block = data.get('aircraft', {}) if isinstance(data.get('aircraft'), dict) else {}
        aircraft_icao = str(ac_block.get('icaocode') or '').strip()
        aircraft_name = str(ac_block.get('name') or '').strip()
        aircraft_engines = str(ac_block.get('engines') or '').strip()
        aircraft_reg = str(ac_block.get('reg') or '').strip().upper()
        if not aircraft_reg:
            m_reg = re.search(r'\bREG/([A-Z0-9-]+)', str(atc_block.get('flightplan_text') or '').upper())
            if m_reg:
                aircraft_reg = m_reg.group(1)
        aircraft = aircraft_name if aircraft_name and aircraft_name != aircraft_icao else f"{aircraft_icao}"
        if aircraft_engines and aircraft_engines.upper() not in aircraft.upper():
            aircraft_version = f"{aircraft} - {aircraft_engines}"
        else:
            aircraft_version = aircraft
        
        base_type = str(ac_block.get('base_type') or '').strip()
        wingspan = AIRCRAFT_WINGSPANS.get(aircraft_icao, AIRCRAFT_WINGSPANS.get(base_type, 36.0))

        weights_block = data.get('weights', {}) if isinstance(data.get('weights'), dict) else {}
        ofp_is_all_cargo = False
        try:
            pax_cnt_raw = weights_block.get("pax_count")
            cargo_raw = weights_block.get("cargo")
            if pax_cnt_raw is not None and str(pax_cnt_raw).strip() != "":
                if int(float(pax_cnt_raw)) == 0 and float(cargo_raw or 0) >= 2000.0:
                    ofp_is_all_cargo = True
        except Exception:
            pass

        airline_norm = normalize_airline_icao(airline)
        sister_airlines = get_sister_airlines(airline_norm)
        alliance_airlines = get_alliance_airlines(airline_norm)
        customs_profile = classify_flight_customs_profile(origin, destination)

        def get_terminal(g, icao_code=""):
            if not g:
                return "Main Apron"
            inferred = infer_airport_stand_terminal(icao_code, g, "")
            if inferred:
                return inferred
            g_clean = g.strip().upper()
            
            t_match = re.search(r'\b(?:TERMINAL|TERM|T)\b\s*([0-9A-Z]+)', g_clean)
            if t_match:
                t_val = t_match.group(1)
                if t_val.isdigit():
                    return f"Terminal {t_val}"
                elif len(t_val) <= 2 and t_val not in ("L", "R", "C"):
                    return f"Terminal {t_val}"

            clean_prefix = re.sub(r'^(?:GATE|STAND|PARKING|RAMP|APRON)\s*', '', g_clean)
            clean_prefix_no_space = clean_prefix.replace(' ', '')
            
            lr_match = re.match(r'^[LRC]\s*\d+', clean_prefix)
            if lr_match:
                num_match = re.search(r'\d+', clean_prefix)
                if num_match:
                    num = int(num_match.group())
                    hundreds = (num // 100) * 100
                    return f"Zone {hundreds}s" if hundreds > 0 else "Main Apron"
                return "Main Apron"

            m = re.match(r'^([A-Z]+)', clean_prefix_no_space)
            if m:
                term = m.group(1)
                if term.startswith('T') and len(term) > 1 and term[1:].isdigit():
                    return f"Terminal {term[1:]}"
                if term in ("L", "R", "C"):
                    num_match = re.search(r'\d+', clean_prefix_no_space)
                    if num_match:
                        num = int(num_match.group())
                        hundreds = (num // 100) * 100
                        return f"Zone {hundreds}s" if hundreds > 0 else "Main Apron"
                    return "Main Apron"
                return f"Terminal {term}"
                
            m_num = re.match(r'^(\d+)', clean_prefix_no_space)
            if m_num:
                num = int(m_num.group(1))
                hundreds = (num // 100) * 100
                return f"Zone {hundreds}s" if hundreds > 0 else "Main Apron"
            return "Other"

        def process_airport(icao, phase_mode="departure", plan_rwy="", excluded_gate=""):
            if not icao: return None
            
            is_cargo_aircraft = is_freighter_aircraft(aircraft_icao, aircraft_name)
            builtin_cargo_code = airline_norm in {"FDX", "UPS", "DHL", "BOX", "GTI", "PAC", "CKS", "CLX", "ICV", "NCA", "ABX", "AJK", "SQC", "BCS", "DHK", "CCG", "CKK", "GEC", "MPH"}
            force_cargo = self.config.settings.get("force_cargo_mode", False)
            is_cargo_carrier = is_cargo_aircraft or builtin_cargo_code or ofp_is_all_cargo or force_cargo
            is_a380 = is_a380_aircraft(aircraft_icao, aircraft_name, base_type)
            
            # Find default airport coordinates from SimBrief response
            default_lat = None
            default_lon = None
            apt_block = None
            if 'origin' in data and data['origin'].get('icao_code') == icao:
                apt_block = data['origin']
                default_lat = apt_block.get('pos_lat')
                default_lon = apt_block.get('pos_long')
            elif 'destination' in data and data['destination'].get('icao_code') == icao:
                apt_block = data['destination']
                default_lat = apt_block.get('pos_lat')
                default_lon = apt_block.get('pos_long')
                
            if default_lat:
                try: default_lat = float(default_lat)
                except ValueError: default_lat = None
            if default_lon:
                try: default_lon = float(default_lon)
                except ValueError: default_lon = None
                
            res = {
                "icao": icao,
                "name": self.airport_names.get(icao, ''),
                "city": self.get_airport_city(icao, lat=default_lat, lon=default_lon, ofp_apt_block=apt_block),
                "osm": False,
                "gates": {},
                "gate": "",
                "error": None,
                "lat": None,
                "lon": None,
                "gate_coords_found": False,
                "bypassed_summary": ""
            }
            
            _osm_gates_dict_cached = None
            def get_osm_gates_dict():
                nonlocal _osm_gates_dict_cached
                if _osm_gates_dict_cached is None:
                    _osm_gates_dict_cached, _ = self.fetch_osm_gates(icao, lat=default_lat, lon=default_lon)
                return _osm_gates_dict_cached
            
            def find_osm_coords(gate_name):
                clean_name = gate_name.replace(" ", "").upper()
                for p in ("GATE", "STAND", "PARKING", "RAMP", "DOCK"):
                    if clean_name.startswith(p):
                        clean_name = clean_name[len(p):]
                num_only = re.sub(r'^[A-Z]+', '', clean_name) if re.match(r'^[A-Z]+\d+$', clean_name) else None
                # Check built-in BGL DB first (0.0001s, no network needed!)
                if icao in self.builtin_data:
                    for al_list in self.builtin_data[icao].values():
                        for bg in al_list:
                            if bg.get('lat') is not None and bg.get('lon') is not None:
                                b_clean = bg['name'].replace(" ", "").upper()
                                if b_clean == clean_name:
                                    return bg['lat'], bg['lon']
                    if num_only:
                        for al_list in self.builtin_data[icao].values():
                            for bg in al_list:
                                if bg.get('lat') is not None and bg.get('lon') is not None:
                                    b_clean = bg['name'].replace(" ", "").upper()
                                    if b_clean == num_only:
                                        return bg['lat'], bg['lon']
                osm_dict = get_osm_gates_dict()
                if not osm_dict: return None, None
                for ref, coords in osm_dict.items():
                    if clean_name == ref.replace(" ", "").upper():
                        return coords["lat"], coords["lon"]
                if num_only:
                    for ref, coords in osm_dict.items():
                        if num_only == ref.replace(" ", "").upper():
                            return coords["lat"], coords["lon"]
                return None, None
            
            # Build coherent, unified stand/terminal/vector data on the fly for this airport
            airport_source = self.build_coherent_airport_data(
                icao, airport_name=self.airport_names.get(icao, ''),
                default_lat=default_lat, default_lon=default_lon
            )

            def attach_chart_and_route(r_dict):
                try:
                    extra_stands = []
                    seen_extra = set()
                    src_for_stands = airport_source or {}
                    for g_list in src_for_stands.values():
                        for g_item in g_list:
                            if g_item.get("lat") is not None and g_item.get("lon") is not None:
                                s_key = (g_item.get("name", ""), round(g_item["lat"], 6), round(g_item["lon"], 6))
                                if s_key not in seen_extra:
                                    seen_extra.add(s_key)
                                    extra_stands.append(g_item)
                    c_lat = r_dict.get("lat") or default_lat
                    c_lon = r_dict.get("lon") or default_lon
                    chart_d = self.taxi_router.fetch_airport_vector_data(icao, c_lat, c_lon, extra_stands=extra_stands)
                    r_dict["airline_code"] = normalize_airline_icao(airline)
                    if chart_d:
                        self.enrich_chart_stands_with_airlines(
                            icao,
                            chart_d,
                            assigned_gate=r_dict.get("gate"),
                            assigned_airline=airline,
                        )
                    r_dict["chart_data"] = chart_d
                    if chart_d and r_dict.get("gate") and r_dict.get("lat") is not None and r_dict.get("lon") is not None:
                        u_lat = self.simconnect_manager.user_lat if hasattr(self, "simconnect_manager") else None
                        u_lon = self.simconnect_manager.user_lon if hasattr(self, "simconnect_manager") else None
                        u_hdg = self.simconnect_manager.user_hdg if hasattr(self, "simconnect_manager") else None
                        u_gs = self.simconnect_manager.user_gs if hasattr(self, "simconnect_manager") else None
                        u_og = self.simconnect_manager.user_on_ground if hasattr(self, "simconnect_manager") else None
                        t_route = self.taxi_router.compute_taxi_route(
                            chart_d, phase_mode, r_dict["lat"], r_dict["lon"], r_dict["gate"],
                            runway_id=plan_rwy, user_lat=u_lat, user_lon=u_lon,
                            user_hdg=u_hdg, user_gs=u_gs, user_on_ground=u_og,
                            gate_hdg=r_dict.get("heading"), no_pushback=r_dict.get("no_pushback", False)
                        )
                        r_dict["taxi_route"] = t_route
                        r_dict["selected_runway"] = t_route.get("runway_id", plan_rwy) if t_route else plan_rwy
                        r_dict["available_runways"] = t_route.get("available_runways", []) if t_route else chart_d.get("available_runways", [])
                    else:
                        r_dict["taxi_route"] = None
                        r_dict["selected_runway"] = plan_rwy
                        r_dict["available_runways"] = chart_d.get("available_runways", []) if chart_d else []
                except Exception as ex_tr:
                    print(f"[TaxiRouter] Warning attaching chart for {icao}: {ex_tr}")
                    r_dict["chart_data"] = None
                    r_dict["taxi_route"] = None
                    r_dict["selected_runway"] = plan_rwy
                    r_dict["available_runways"] = []
                return r_dict

            if not airport_source:
                osm_dict = get_osm_gates_dict()
                if osm_dict:
                    import random
                    bypassed = []
                    available_refs = list(osm_dict.keys())
                    
                    # Filter by aircraft wingspan & exclude small GA stands for airliners
                    ws_filtered = [
                        r for r in available_refs
                        if osm_dict[r].get("wingspan", 36.0) >= wingspan
                        and not (osm_dict[r].get("is_ga", False) and wingspan >= 28.0)
                    ]
                    if ws_filtered:
                        available_refs = ws_filtered

                    if is_a380 and icao not in KNOWN_A380_AIRPORTS:
                        a380_osm_refs = [r for r in available_refs if "a380" in r.lower() or "code f" in r.lower() or "code-f" in r.lower()]
                        if not a380_osm_refs:
                            res["error"] = "No A380 gate for this airport"
                            res["lat"] = default_lat
                            res["lon"] = default_lon
                            res["gate_coords_found"] = False
                            res["max_wingspan"] = 79.75
                            res["type"] = "GATE"
                            return attach_chart_and_route(res)
                        available_refs = a380_osm_refs
                    
                    exclude_cargo = self.config.settings.get("exclude_cargo", False)
                    exclude_ga_ramp = self.config.settings.get("exclude_ga_ramp", False)
                    
                    if exclude_cargo or exclude_ga_ramp:
                        filtered_refs = []
                        for ref in available_refs:
                            ref_lower = ref.lower()
                            if exclude_cargo and "cargo" in ref_lower and not is_cargo_carrier:
                                continue
                            if exclude_ga_ramp and (osm_dict[ref].get("is_ga") or is_ga_ramp_gate(ref)) and not is_cargo_carrier:
                                continue
                            filtered_refs.append(ref)
                        if filtered_refs:
                            available_refs = filtered_refs
                            
                    # Universal Cargo Rule for OSM Airports:
                    if is_cargo_carrier:
                        cargo_osm_refs = []
                        # Priority 1: Refs explicitly containing "cargo", "freight", "ramp", or starting with "R" / "C"
                        for ref in available_refs:
                            ref_l = ref.lower()
                            if "cargo" in ref_l or "freight" in ref_l or "ramp" in ref_l or ref_l.startswith("r") or ref_l.startswith("c"):
                                cargo_osm_refs.append(ref)
                        
                        # Priority 2: Any stand/gate that does NOT have a jetway
                        if not cargo_osm_refs:
                            for ref in available_refs:
                                if not osm_dict[ref].get("has_jetway", False):
                                    cargo_osm_refs.append(ref)
                                    
                        if cargo_osm_refs:
                            available_refs = cargo_osm_refs

                    if self.config.settings.get("check_online_traffic", True):
                        try:
                            pilots = self.network_checker.fetch_data()
                        except Exception as e:
                            print(f"Error fetching traffic data: {e}")
                            pilots = []
                        if pilots:
                            clean_refs = []
                            for ref in available_refs:
                                coords = osm_dict[ref]
                                occupied = False
                                occupying_pilot = None
                                for pilot in pilots:
                                    if self.network_checker.is_pilot_self(pilot, user_lat=u_lat_self, user_lon=u_lon_self, user_callsign=ofp_callsign):
                                        continue
                                    if haversine(coords["lat"], coords["lon"], pilot["lat"], pilot["lon"]) < 50:
                                        occupied = True
                                        occupying_pilot = pilot
                                        break
                                if occupied:
                                    bypassed.append({
                                        "name": ref,
                                        "network": occupying_pilot["network"],
                                        "callsign": occupying_pilot["callsign"]
                                    })
                                else:
                                    clean_refs.append(ref)
                            if clean_refs:
                                available_refs = clean_refs

                    if excluded_gate and len(available_refs) > 1:
                        ex_tok = clean_gate_token(excluded_gate)
                        non_ex = [r for r in available_refs if clean_gate_token(r) != ex_tok]
                        if non_ex:
                            available_refs = non_ex
                                
                    selected_gate_ref = random.choice(available_refs)
                    res["osm"] = True
                    res["gate"] = selected_gate_ref
                    
                    raw_t = get_terminal(selected_gate_ref, icao)
                    if is_cargo_carrier:
                        res["terminal"] = f"CARGO APRON ({raw_t})" if raw_t and raw_t not in ("Main Apron", "Other") else "CARGO APRON"
                    else:
                        res["terminal"] = raw_t

                    res["lat"] = osm_dict[selected_gate_ref]["lat"]
                    res["lon"] = osm_dict[selected_gate_ref]["lon"]
                    res["heading"] = osm_dict[selected_gate_ref].get("heading")
                    res["gate_coords_found"] = True
                    res["max_wingspan"] = osm_dict[selected_gate_ref].get("wingspan", 36.0)
                    res["has_jetway"] = osm_dict[selected_gate_ref].get("has_jetway", False)
                    
                    if bypassed:
                        items = [f"{item['name']} ({item['network']})" for item in bypassed]
                        res["bypassed_summary"] = "Occupied: " + ", ".join(items)
                            
                    ref_lower = selected_gate_ref.lower()
                    if "ramp" in ref_lower:
                        res["type"] = "RAMP"
                    elif "dock" in ref_lower:
                        res["type"] = "DOCK"
                    elif "stand" in ref_lower:
                        res["type"] = "STAND"
                    else:
                        res["type"] = "RAMP" if is_cargo_carrier else "GATE"
                else:
                    res["error"] = "No A380 gate for this airport" if is_a380 else "No compatible stands found for this airport."
                    res["lat"] = default_lat
                    res["lon"] = default_lon
                    res["gate_coords_found"] = False
                    res["max_wingspan"] = 79.75 if is_a380 else 999.0
                    res["type"] = "GATE"
                return attach_chart_and_route(res)

            # Build deduplicated master list of all stands at `icao`, preserving complete airline code sets
            gates_by_name = {}
            for a_code, g_list in airport_source.items():
                a_clean = str(a_code or "").strip().upper()
                for g in g_list:
                    g_name = g.get("name")
                    if not g_name:
                        continue
                    if g_name not in gates_by_name:
                        g_copy = dict(g)
                        als = set()
                        for raw_a in (g.get("airlines") or []):
                            if raw_a and str(raw_a).strip().upper() != "ANY":
                                als.add(str(raw_a).strip().upper())
                                als.add(normalize_airline_icao(raw_a))
                        if a_clean and a_clean != "ANY":
                            als.add(a_clean)
                            als.add(normalize_airline_icao(a_clean))
                        als.discard("")
                        g_copy["_norm_airlines"] = als
                        gates_by_name[g_name] = g_copy
                    else:
                        als = gates_by_name[g_name]["_norm_airlines"]
                        if a_clean and a_clean != "ANY":
                            als.add(a_clean)
                            als.add(normalize_airline_icao(a_clean))
                        for raw_a in (g.get("airlines") or []):
                            if raw_a and str(raw_a).strip().upper() != "ANY":
                                als.add(str(raw_a).strip().upper())
                                als.add(normalize_airline_icao(raw_a))
                        als.discard("")

            all_gates = list(gates_by_name.values())

            if is_a380:
                a380_capable = [g for g in all_gates if g['wingspan'] >= 65.0 or "a380" in g['name'].lower() or "code f" in g['name'].lower() or "code-f" in g['name'].lower()]
                if not a380_capable:
                    res["error"] = "No A380 gate for this airport"
                    res["lat"] = default_lat
                    res["lon"] = default_lon
                    res["gate_coords_found"] = False
                    res["max_wingspan"] = 79.75
                    res["type"] = "GATE"
                    return attach_chart_and_route(res)

            airport_cloud_data = self.cloud_ruleset.get(icao, {})
            cloud_rules = []
            alliance_cloud_rules = []
            mapping = {}
            rules_dict = airport_cloud_data.get("rules", {}) if "rules" in airport_cloud_data else airport_cloud_data
            if "rules" in airport_cloud_data:
                mapping = airport_cloud_data.get("mapping", {})

            if isinstance(rules_dict, dict):
                for cand_al in [airline, airline_norm] + sorted(list(sister_airlines)):
                    if cand_al and cand_al in rules_dict and rules_dict[cand_al]:
                        cloud_rules = list(rules_dict[cand_al])
                        break
                if not cloud_rules and alliance_airlines:
                    seen_acr = []
                    for al_part in sorted(list(alliance_airlines)):
                        for r_item in rules_dict.get(al_part, []):
                            if r_item not in seen_acr:
                                seen_acr.append(r_item)
                    alliance_cloud_rules = seen_acr

            def _match_terminal_against_rules(g_obj, target_rules):
                if not target_rules:
                    return None
                g_term = (g_obj.get('terminal') or '').strip()
                t = get_terminal(g_obj['name'], icao)
                t_raw = get_terminal(g_obj.get('raw_name', ''), icao) if g_obj.get('raw_name') else t
                g_term_alt = ""
                if g_term:
                    m_gt = re.match(r"^(?:gate|stand|parking|ramp|apron|dock)\s+([a-z0-9]{1,3})$", g_term, re.I)
                    if m_gt:
                        g_term_alt = f"Terminal {m_gt.group(1).upper()}"
                    g_term_l = g_term.lower()
                    g_term_alt_l = g_term_alt.lower()
                    for idx_r, cr in enumerate(target_rules):
                        cr_l = cr.lower()
                        if g_term_l == cr_l or cr_l in g_term_l or g_term_l in cr_l:
                            return idx_r
                        if g_term_alt_l and (g_term_alt_l == cr_l or cr_l in g_term_alt_l or g_term_alt_l in cr_l):
                            return idx_r
                if mapping:
                    matched_real_terminals = []
                    for real_term, aliases in mapping.items():
                        if (
                            t in aliases
                            or t_raw in aliases
                            or (g_term and g_term in aliases)
                            or (g_term_alt and g_term_alt in aliases)
                        ):
                            matched_real_terminals.append(real_term)
                    for idx_r, cr in enumerate(target_rules):
                        if cr in matched_real_terminals:
                            return idx_r
                else:
                    for idx_r, cr in enumerate(target_rules):
                        if t == cr or t_raw == cr or (g_term_alt and g_term_alt == cr):
                            return idx_r
                return None

            compatible_gates = [g for g in all_gates if g['wingspan'] >= wingspan]

            if is_a380:
                a380_compatible = [g for g in compatible_gates if g['wingspan'] >= 65.0 or "a380" in g['name'].lower() or "code f" in g['name'].lower() or "code-f" in g['name'].lower()]
                if a380_compatible:
                    compatible_gates = a380_compatible
                
                a380_named = [g for g in compatible_gates if "a380" in g['name'].lower()]
                if a380_named:
                    compatible_gates = a380_named

            if not compatible_gates and not is_a380 and all_gates:
                max_avail_ws = max((float(g.get('wingspan') or 0.0) for g in all_gates), default=0.0)
                compatible_gates = [g for g in all_gates if float(g.get('wingspan') or 0.0) >= max_avail_ws - 4.0] or list(all_gates)

            if not compatible_gates:
                res["error"] = "No A380 gate for this airport" if is_a380 else "No gates found compatible with aircraft size."
                res["lat"] = default_lat
                res["lon"] = default_lon
                res["gate_coords_found"] = False
                res["max_wingspan"] = 79.75 if is_a380 else 999.0
                res["type"] = "GATE"
                return attach_chart_and_route(res)
                        
            def is_passenger_gate(g):
                if g.get('is_cargo') or g.get('is_ga') or g.get('is_military'):
                    return False
                    
                name_lower = g['name'].lower()
                term_lower = (g.get('terminal') or '').lower()
                g_type_lower = g.get('type', '').lower()
                
                exclude_keywords = ("cargo", "military", " general aviation", "private", "prop", "business aviation")
                for kw in exclude_keywords:
                    if kw in name_lower or kw in term_lower or kw in g_type_lower:
                        return False
                        
                for text in (name_lower, term_lower):
                    if text.startswith("ga ") or text.startswith("ga-") or text == "ga":
                        return False
                    if text.startswith("mil ") or text.startswith("mil-") or text == "mil":
                        return False
                        
                return True
                
            def is_cargo_gate(g):
                if g.get('is_cargo'):
                    return True
                name_lower = g['name'].lower()
                term_lower = (g.get('terminal') or '').lower()
                g_type_lower = g.get('type', '').lower()
                if "cargo" in name_lower or "cargo" in term_lower or "cargo" in g_type_lower:
                    return True
                return False

            preferred_gates = []
            if is_cargo_carrier:
                # Priority 1: Explicit cargo gates
                for g in compatible_gates:
                    if is_cargo_gate(g):
                        preferred_gates.append(g)
                # Priority 2: Ramps / Stands without jetways that are NOT passenger, NOT military, NOT GA
                if not preferred_gates:
                    for g in compatible_gates:
                        if not is_passenger_gate(g) and not g.get('is_military') and not g.get('is_ga') and not g.get('has_jetway'):
                            preferred_gates.append(g)
                # Priority 3: Any stand/ramp without jetway
                if not preferred_gates:
                    for g in compatible_gates:
                        if not g.get('has_jetway'):
                            preferred_gates.append(g)
            else:
                for g in compatible_gates:
                    if is_passenger_gate(g):
                        preferred_gates.append(g)
                    
            if preferred_gates:
                compatible_gates = preferred_gates

            # Apply user exclusions
            exclude_cargo = self.config.settings.get("exclude_cargo", False)
            exclude_ga_ramp = self.config.settings.get("exclude_ga_ramp", False)
            
            filtered_compatible = []
            for g in compatible_gates:
                name_lower = g['name'].lower()
                term_lower = (g.get('terminal') or '').lower()
                g_type_lower = g.get('type', '').lower()
                
                # Check Cargo: exclude cargo gates ONLY if user requested exclude_cargo AND this is NOT a cargo flight
                is_cargo = g.get('is_cargo') or "cargo" in name_lower or "cargo" in term_lower or "cargo" in g_type_lower
                if exclude_cargo and is_cargo and not is_cargo_carrier:
                    continue
                    
                # Check GA/Ramp/Military: exclude GA ramps ONLY if user requested exclude_ga_ramp AND this is NOT a cargo flight
                is_ga_ramp = g.get('is_ga') or g.get('is_military') or is_ga_ramp_gate(g['name'], g.get('terminal'), g.get('type'), is_cargo=is_cargo)
                if exclude_ga_ramp and is_ga_ramp and not is_cargo_carrier:
                    continue
                    
                filtered_compatible.append(g)
            if filtered_compatible:
                compatible_gates = filtered_compatible
                    
            if not compatible_gates:
                res["error"] = "No gates found compatible with aircraft size."
                res["lat"] = default_lat
                res["lon"] = default_lon
                res["gate_coords_found"] = False
                res["max_wingspan"] = 999.0
                res["type"] = "GATE"
                return attach_chart_and_route(res)
                
            # Parse ignored gates list
            ignored = self.config.settings.get("ignored_gates", "")
            ignored_set = set()
            if ignored:
                for item in ignored.split(","):
                    item_clean = item.strip().upper().replace(" ", "")
                    if ":" in item_clean:
                        ignored_set.add(item_clean)

            seen = set()
            unique_gates = []
            for g in compatible_gates:
                if g['name'] not in seen:
                    gate_id_normalized = f"{icao}:{g['name'].upper().replace(' ', '')}"
                    if gate_id_normalized in ignored_set:
                        print(f"Filtering out blacklisted gate: {gate_id_normalized}")
                        continue
                    seen.add(g['name'])
                    unique_gates.append(g)
            
            bypassed = []
            available_gates = unique_gates
            if self.config.settings.get("check_online_traffic", True):
                try:
                    pilots = self.network_checker.fetch_data()
                except Exception as e:
                    print(f"Error fetching traffic data: {e}")
                    pilots = []
                if pilots:
                    mars_prot = bool(self.config.settings.get("mars_overlap_protection", True))
                    occ_rad = max(46.0, (float(wingspan or 36.0) * 0.5) + 19.0) if mars_prot else 32.0
                    direct_occ_stands = []
                    for g in unique_gates:
                        glat, glon = g.get('lat'), g.get('lon')
                        if glat is None or glon is None:
                            continue
                        for pilot in pilots:
                            if self.network_checker.is_pilot_self(pilot, user_lat=u_lat_self, user_lon=u_lon_self, user_callsign=ofp_callsign):
                                continue
                            if haversine(glat, glon, pilot["lat"], pilot["lon"]) < 28.0:
                                direct_occ_stands.append((g['name'], glat, glon, pilot))
                                break

                    clean_gates = []
                    for g in unique_gates:
                        lat, lon = g.get('lat'), g.get('lon')
                        occupied = False
                        occupying_pilot = None
                        if lat is not None and lon is not None:
                            for pilot in pilots:
                                if self.network_checker.is_pilot_self(pilot, user_lat=u_lat_self, user_lon=u_lon_self, user_callsign=ofp_callsign):
                                    continue
                                if haversine(lat, lon, pilot["lat"], pilot["lon"]) < occ_rad:
                                    occupied = True
                                    occupying_pilot = pilot
                                    break
                            if not occupied and mars_prot and direct_occ_stands:
                                for occ_name, olat, olon, opilot in direct_occ_stands:
                                    d_mars = haversine(lat, lon, olat, olon)
                                    if are_mars_related_stands(g['name'], occ_name, d_mars, user_wingspan=wingspan):
                                        occupied = True
                                        occupying_pilot = opilot
                                        break
                        if occupied:
                            bypassed.append({
                                "name": g['name'],
                                "network": occupying_pilot["network"],
                                "callsign": occupying_pilot["callsign"]
                            })
                        else:
                            clean_gates.append(g)
                    if clean_gates:
                        available_gates = clean_gates
                        
            if bypassed:
                items = [f"{item['name']} ({item['network']})" for item in bypassed]
                res["bypassed_summary"] = "Occupied: " + ", ".join(items)
            
            import random
            if excluded_gate and len(available_gates) > 1:
                ex_tok = clean_gate_token(excluded_gate)
                non_ex = [g for g in available_gates if clean_gate_token(g['name']) != ex_tok]
                if non_ex:
                    available_gates = non_ex

            ac_icao_u = str(aircraft_icao or "").strip().upper()
            base_u = str(base_type or "").strip().upper()
            airline_u = str(airline or "").strip().upper()
            ac_equiv_set = set(AIRCRAFT_EQUIVALENT_FAMILIES.get(ac_icao_u, {ac_icao_u}))
            if base_u:
                ac_equiv_set.add(base_u)
                ac_equiv_set.update(AIRCRAFT_EQUIVALENT_FAMILIES.get(base_u, {base_u}))

            # Precompute inferred airlines & terminal Schengen/Non-Schengen profile across all candidate stands
            all_lcc_set = LOW_COST_CARRIERS | ULTRA_LOW_COST_CARRIERS
            is_user_lcc = bool(airline_norm in all_lcc_set or airline_u in all_lcc_set)
            schengen_airline_set = {
                "DLH", "SWR", "AUA", "BEL", "EWG", "AFR", "KLM", "TRA", "TVF", "IBE", "IBS",
                "VLG", "AEA", "ITY", "TAP", "SAS", "FIN", "LOT", "CSA", "TVS", "BTI", "ELL",
                "AEE", "AMC", "ICE", "NAX", "LGL", "ROT", "EDW", "OAW", "CFG", "TUI", "VOE"
            }
            non_schengen_airline_set = {
                "BAW", "VIR", "EIN", "EXS", "TOM", "AAL", "DAL", "UAL", "ACA", "UAE", "QTR",
                "ETD", "THY", "PGT", "SVA", "ELY", "MSR", "RAM", "DAH", "TAR", "SIA", "CPA",
                "QFA", "ANA", "JAL", "KAL", "AAR", "CCA", "CES", "CSN", "ETH", "AIC", "FDB"
            }
            term_schengen_votes = {}  # term_l -> [schengen_count, non_schengen_count]
            airport_has_direct_airline = False
            rw_map_for_apt = self.fetch_real_world_airport_airlines(icao)

            for g_cand in available_gates:
                g_c_term = (g_cand.get("terminal") or get_terminal(g_cand["name"], icao) or "").strip()
                g_c_term_l = g_c_term.lower()
                raw_als_list = list(g_cand.get("_norm_airlines") or [])
                inf_list = infer_stand_airlines(
                    icao,
                    g_cand["name"],
                    terminal_name=g_c_term,
                    explicit_airlines=raw_als_list,
                    is_cargo=bool(g_cand.get("is_cargo")),
                    is_ga=bool(g_cand.get("is_ga")),
                    is_military=bool(g_cand.get("is_military")),
                    has_jetway=bool(g_cand.get("has_jetway")),
                    wingspan=float(g_cand.get("wingspan") or 36.0),
                    airport_rules=airport_cloud_data,
                    real_world_airlines=rw_map_for_apt,
                )
                inf_set = {normalize_airline_icao(c) for c in inf_list if c}
                inf_set.discard("")
                g_cand["_inferred_airlines"] = inf_set
                g_c_als = g_cand.get("_norm_airlines") or set()
                if airline_norm and (airline_norm in g_c_als or airline_u in g_c_als or airline_norm in inf_set):
                    airport_has_direct_airline = True

                if g_c_term_l:
                    votes = term_schengen_votes.setdefault(g_c_term_l, [0, 0])
                    for al_c in (g_c_als or inf_set):
                        if al_c in schengen_airline_set:
                            votes[0] += 1
                        elif al_c in non_schengen_airline_set:
                            votes[1] += 1

            def score_candidate_gate(g):
                score = 0.0
                g_als = g.get("_norm_airlines") or set()
                g_inf_als = g.get("_inferred_airlines") or set()
                g_all_als = g_als | g_inf_als
                g_term = (g.get("terminal") or get_terminal(g["name"], icao) or "").strip()
                g_term_l = g_term.lower()
                has_jw = bool(g.get("has_jetway"))
                g_ws = float(g.get("wingspan") or 36.0)
                fallback_tier = None

                # 1. Tiered Airline Affinity + Multi-Tier Visiting / Unserved Airline Fallback Hierarchy
                n_gsx_als = len(g_als)
                if airline_norm and (airline_norm in g_als or airline_u in g_als):
                    if n_gsx_als <= 2:
                        score += 1060.0
                    elif n_gsx_als <= 8:
                        score += 1025.0
                    elif n_gsx_als <= 25:
                        score += 985.0
                    else:
                        score += 915.0
                elif airline_norm and (airline_norm in g_inf_als or airline_u in g_inf_als):
                    score += 890.0
                elif sister_airlines and (g_als & sister_airlines):
                    score += 865.0 if n_gsx_als <= 8 else (830.0 if n_gsx_als <= 25 else 780.0)
                    if not airport_has_direct_airline:
                        fallback_tier = "Sister Group Fallback"
                elif sister_airlines and (g_inf_als & sister_airlines):
                    score += 580.0
                    if not airport_has_direct_airline:
                        fallback_tier = "Sister Group Fallback"
                elif alliance_airlines and (g_als & alliance_airlines):
                    score += 420.0
                    if not airport_has_direct_airline:
                        fallback_tier = "Alliance Partner Fallback"
                elif alliance_airlines and (g_inf_als & alliance_airlines):
                    score += 320.0
                    if not airport_has_direct_airline:
                        fallback_tier = "Alliance Partner Fallback"
                else:
                    # Tier 3 Fallback: Unserved / Visiting Airline without Sister or Alliance presence on this stand
                    if is_user_lcc:
                        if g_all_als & all_lcc_set:
                            score += 240.0
                            fallback_tier = "Visiting LCC Fallback"
                        elif not g_als:
                            score += 180.0
                            fallback_tier = "Visiting LCC Fallback"
                        elif n_gsx_als == 1:
                            score -= 85.0
                    else:
                        # Visiting Full-Service / Legacy Carrier: prefer common-use / multi-airline legacy stands with jetways
                        legacy_als_on_stand = g_all_als - all_lcc_set
                        if len(g_als) >= 2 and legacy_als_on_stand:
                            score += 235.0
                            fallback_tier = "Visiting Carrier Fallback"
                        elif not g_als and legacy_als_on_stand:
                            score += 210.0
                            fallback_tier = "Visiting Carrier Fallback"
                        elif not g_als:
                            score += 165.0
                            fallback_tier = "Visiting Carrier Fallback"
                        elif g_all_als and g_all_als.issubset(all_lcc_set):
                            score -= 95.0
                        elif n_gsx_als == 1:
                            score -= 75.0

                g["_fallback_tier"] = fallback_tier

                # 2. Terminal Rules & Remote Stand Filtering
                rule_idx = _match_terminal_against_rules(g, cloud_rules)
                if cloud_rules:
                    if rule_idx is not None:
                        # Primary terminal gets a +30 priority boost over secondary terminals
                        term_bonus = 170.0 if rule_idx == 0 else max(115.0, 150.0 - 15.0 * rule_idx)
                        if "pier 6" in g_term_l:
                            term_bonus -= 35.0
                        score += term_bonus
                    else:
                        score -= 130.0
                elif alliance_cloud_rules:
                    if _match_terminal_against_rules(g, alliance_cloud_rules) is not None:
                        score += 75.0

                if not is_cargo_carrier and ("remote" in g_term_l or g_term_l.startswith("parking")):
                    if not (is_user_lcc and not has_jw):
                        score -= 95.0

                # 3. Geopolitical & Customs / Schengen Zone Intelligence (Origin <-> Destination)
                if not is_cargo_carrier:
                    is_term_non_sch = any(k in g_term_l for k in ("non-schengen", "non schengen", "extra-schengen", "hors schengen"))
                    is_term_sch = ("schengen" in g_term_l) and not is_term_non_sch
                    if not is_term_non_sch and not is_term_sch and g_term_l in term_schengen_votes:
                        sch_v, non_sch_v = term_schengen_votes[g_term_l]
                        if sch_v >= 2 and sch_v >= non_sch_v * 2:
                            is_term_sch = True
                        elif non_sch_v >= 2 and non_sch_v >= sch_v * 2:
                            is_term_non_sch = True

                    if is_term_non_sch:
                        score += 165.0 if customs_profile["is_non_schengen"] else -220.0
                    elif is_term_sch:
                        score += 165.0 if customs_profile["is_schengen"] else -220.0

                    if "domestic" in g_term_l:
                        score += 65.0 if customs_profile["is_domestic"] else -75.0
                    elif "international" in g_term_l and not (is_term_sch or is_term_non_sch):
                        score += 45.0 if not customs_profile["is_domestic"] else -45.0

                # 4. GSX .py @AlternativeStopPositions Aircraft-Type Fit
                py_ac = set(g.get("py_aircraft_types") or [])
                if py_ac:
                    if py_ac & ac_equiv_set:
                        score += 40.0
                    else:
                        max_py_ws = max((AIRCRAFT_WINGSPANS.get(c, 34.0) for c in py_ac), default=36.0)
                        if max_py_ws < wingspan - 0.3:
                            score -= 95.0
                        elif (ac_icao_u in STRETCHED_NARROWBODY_TYPES or base_u in STRETCHED_NARROWBODY_TYPES) and not (py_ac & STRETCHED_NARROWBODY_TYPES):
                            score -= 65.0

                # 5. Carrier & Aircraft Boarding Profile (Jetway vs Walk-in)
                if is_cargo_carrier:
                    if is_cargo_gate(g):
                        score += 500.0
                    score += 120.0 if not has_jw else -250.0
                elif ac_icao_u in TURBOPROP_TYPES or base_u in TURBOPROP_TYPES:
                    score += 55.0 if not has_jw else -20.0
                elif airline_norm in ULTRA_LOW_COST_CARRIERS:
                    score += 25.0 if not has_jw else 15.0
                elif airline_norm in LOW_COST_CARRIERS:
                    score += 50.0 if has_jw else 20.0
                else:
                    # Full-Service / Legacy Carrier
                    if (ac_icao_u in REGIONAL_JET_TYPES or base_u in REGIONAL_JET_TYPES) and wingspan < 30.0:
                        score += 45.0 if has_jw else 15.0
                    else:
                        score += 95.0 if has_jw else -40.0

                # 6. ICAO Aircraft Size Class Plateau & MARS Bay Variant Matching
                if wingspan < 30.0:
                    if g_ws <= 36.5:
                        score += 75.0
                    elif g_ws <= 45.0:
                        score += 35.0
                    elif g_ws <= 53.0:
                        score -= 90.0
                    else:
                        score -= 180.0
                elif wingspan <= 36.2:
                    if g_ws <= 39.5:
                        score += 78.0
                    elif g_ws <= 45.5:
                        score += 55.0
                    elif g_ws <= 53.0:
                        score -= 85.0
                    elif g_ws <= 66.0:
                        score -= 165.0
                    else:
                        score -= 220.0
                elif wingspan <= 42.5:
                    if g_ws <= 45.5:
                        score += 75.0
                    elif g_ws <= 53.0:
                        score -= 45.0
                    else:
                        score -= 140.0
                elif wingspan <= 52.0:
                    if g_ws <= 55.0:
                        score += 72.0
                    elif g_ws <= 68.5:
                        score += 45.0
                    else:
                        score += 15.0
                elif wingspan <= 65.5:
                    if g_ws <= 68.5:
                        score += 72.0
                    else:
                        score += 40.0
                else:
                    score += 70.0
                    if "a380" in g["name"].lower():
                        score += 40.0

                # 7. MARS Double/Triple Bay Variant Discrimination (e.g. A4 Heavy 65m vs A41 Narrowbody 36m)
                if g.get("_mars_has_better_size_sibling"):
                    score -= 380.0
                elif g.get("_mars_is_optimal_size_sibling"):
                    score += 42.0

                return score

            # Precompute MARS sibling size relationships so narrowbodies never pick the widebody parent of a MARS bay
            for idx_a, g_a in enumerate(available_gates):
                lat_a, lon_a = g_a.get("lat"), g_a.get("lon")
                if lat_a is None or lon_a is None:
                    continue
                ws_a = float(g_a.get("wingspan") or 36.0)
                mars_siblings = []
                for idx_b, g_b in enumerate(available_gates):
                    if idx_a == idx_b:
                        continue
                    lat_b, lon_b = g_b.get("lat"), g_b.get("lon")
                    if lat_b is None or lon_b is None:
                        continue
                    d_ab = haversine(float(lat_a), float(lon_a), float(lat_b), float(lon_b))
                    if d_ab <= 60.0 and are_mars_related_stands(g_a["name"], g_b["name"], d_ab, user_wingspan=65.0):
                        mars_siblings.append(g_b)
                if mars_siblings:
                    # Check if a sibling on the same MARS bay has a much closer wingspan match for this aircraft
                    my_excess = max(0.0, ws_a - wingspan)
                    better_sib = False
                    for sib in mars_siblings:
                        ws_b = float(sib.get("wingspan") or 36.0)
                        if ws_b >= wingspan - 0.3:
                            sib_excess = max(0.0, ws_b - wingspan)
                            if sib_excess + 6.0 < my_excess:
                                better_sib = True
                                sib["_mars_is_optimal_size_sibling"] = True
                    if better_sib:
                        g_a["_mars_has_better_size_sibling"] = True

            for g in available_gates:
                g["_match_score"] = score_candidate_gate(g)

            available_gates.sort(key=lambda x: x.get("_match_score", 0.0), reverse=True)
            best_score = available_gates[0].get("_match_score", 0.0) if available_gates else 0.0
            top_gates = [g for g in available_gates if (best_score - g.get("_match_score", 0.0)) <= 22.0][:5]
            if not top_gates:
                top_gates = available_gates[:5]
            selected_gate = random.choice(top_gates)
            res["gate"] = selected_gate['name']
            if selected_gate.get("_fallback_tier"):
                res["fallback_tier"] = selected_gate["_fallback_tier"]
                res["gate_source"] = f"GateFinder ({selected_gate['_fallback_tier']})"
            
            raw_term = selected_gate.get('terminal') or get_terminal(selected_gate['name'], icao)
            # Only map generic Zone/Letter aliases to cloud terminal names if `raw_term` is not already descriptive
            is_descriptive_term = bool(
                raw_term and any(kw in raw_term.lower() for kw in (
                    "schengen", "satellite", "wing", "north terminal", "south terminal",
                    "pier", "hall", "concourse", "orly", "domestic", "international", "module"
                ))
            )
            if mapping and raw_term and not is_descriptive_term:
                matched_rts = [rt for rt, aliases in mapping.items() if raw_term in aliases]
                if len(matched_rts) == 1:
                    raw_term = matched_rts[0]
                elif len(matched_rts) > 1 and cloud_rules:
                    for rt in matched_rts:
                        if rt in cloud_rules:
                            raw_term = rt
                            break

            is_cargo_gate = selected_gate.get('is_cargo') or "cargo" in selected_gate['name'].lower() or selected_gate.get('type') == 'RAMP'
            if is_cargo_carrier or is_cargo_gate:
                if not raw_term or raw_term in ("Main Apron", "Other"):
                    res["terminal"] = "CARGO APRON"
                elif raw_term.startswith("Zone"):
                    res["terminal"] = f"CARGO APRON ({raw_term})"
                else:
                    res["terminal"] = f"CARGO APRON - {raw_term}"
            else:
                res["terminal"] = raw_term
                
            res["max_wingspan"] = selected_gate.get('wingspan', 999.0)
            res["type"] = selected_gate.get('type', 'GATE')
            res["has_jetway"] = selected_gate.get('has_jetway', False)
            res["heading"] = selected_gate.get('heading')
            res["no_pushback"] = selected_gate.get('no_pushback', False)
            
            lat, lon = selected_gate.get('lat'), selected_gate.get('lon')
            if lat is not None and lon is not None:
                res["lat"] = lat
                res["lon"] = lon
                res["gate_coords_found"] = True
            else:
                lat, lon = find_osm_coords(res["gate"])
                if lat is not None and lon is not None:
                    res["lat"] = lat
                    res["lon"] = lon
                    res["gate_coords_found"] = True
                else:
                    res["lat"] = default_lat
                    res["lon"] = default_lon
                    res["gate_coords_found"] = False
            
            return attach_chart_and_route(res)

        al_name = self.airline_names.get(airline, '')
        if not al_name:
            code_u = airline.upper().strip()
            if code_u.startswith("AF") or code_u.startswith("VAF"):
                al_name = "Air France Virtuelle"
            elif code_u.startswith("DLH") or code_u.startswith("LH"):
                al_name = "Lufthansa Virtuelle"
            elif code_u.startswith("BA") or code_u.startswith("BAW"):
                al_name = "British Airways Virtuelle"
            elif code_u.startswith("EZY") or code_u.startswith("EZ"):
                al_name = "easyJet Virtual"
            elif code_u.startswith("RYR") or code_u.startswith("RY"):
                al_name = "Ryanair Virtual"
            elif code_u.startswith("KLM") or code_u.startswith("KL"):
                al_name = "KLM Virtuelle"
            elif code_u.startswith("DAL"):
                al_name = "Delta Virtual Airlines"
            elif code_u.startswith("UAL"):
                al_name = "United Virtual Airlines"
            elif code_u.startswith("SWA"):
                al_name = "Southwest Virtual"
            elif code_u.startswith("QFA"):
                al_name = "Qantas Virtual Airways"
            elif code_u.endswith("V") or code_u.startswith("V"):
                al_name = f"{code_u} (Virtual Airline)"

        al_display = f"{airline} - {al_name}" if al_name else airline

        prev_flight_snapshot = dict(self.current_flight_data) if self.current_flight_data else None

        # Always reset all router latches, telemetry route caches, and coherent airport caches
        # so every new OFP / turnaround performs a complete, fresh scan and A* calculation for both airports
        self.taxi_router.dep_runway_entered.clear()
        self.taxi_router.arr_vacated_runway.clear()
        self.taxi_router.locked_arrival_exit.clear()
        self._last_dep_route_pos = None
        self._last_dep_route_key = None
        self._last_arr_route_pos = None
        self._last_arr_route_key = None
        if hasattr(self, "coherent_airports") and isinstance(self.coherent_airports, dict):
            if origin:
                self.coherent_airports.pop(origin.upper(), None)
            if destination:
                self.coherent_airports.pop(destination.upper(), None)

        _report_progress(0.35, f"Loading airport data ({origin} & {destination})...")
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_dep = pool.submit(process_airport, origin, "departure", origin_rwy)
            f_arr = pool.submit(process_airport, destination, "arrival", dest_rwy)
            dep_data = f_dep.result()
            _report_progress(0.75, f"Computing gate assignment & taxi routes ({origin} -> {destination})...")
            arr_data = f_arr.result()

        # Check if MSFS is live with aircraft parked at a stand at `origin`, OR if the previous flight
        # (in-memory or persisted in last_flight_session.json) arrived at or departed from `origin` at a specific stand.
        # However, if this is a cold restart of the exact same SimBrief OFP (`ofp_id`) or while airborne,
        # let `_restore_session_state_if_matching()` silently restore the flight in progress without asking a modal question.
        locked_turnaround_stand = None
        stand_decision_made = False
        is_same_ofp_cold_resume = False
        saved_dep_gate_for_ofp = None
        if prev_flight_snapshot is None and ofp_id:
            try:
                p_sess = self._get_session_state_path()
                if os.path.exists(p_sess):
                    with open(p_sess, "r", encoding="utf-8") as rf_s:
                        s_dict = json.load(rf_s)
                    if (
                        isinstance(s_dict, dict)
                        and (time.time() - float(s_dict.get("timestamp") or 0) <= 14 * 3600)
                        and str(s_dict.get("ofp_id") or "") == str(ofp_id)
                        and str(s_dict.get("origin") or "").upper() == str(origin or "").upper()
                        and str(s_dict.get("destination") or "").upper() == str(destination or "").upper()
                    ):
                        is_same_ofp_cold_resume = True
                        saved_dep_gate_for_ofp = s_dict.get("dep_gate")
            except Exception:
                pass

        sc_live = getattr(self, "simconnect_manager", None)
        is_airborne_now = bool(
            sc_live
            and sc_live.connected
            and not getattr(sc_live, "in_menu", False)
            and sc_live.user_on_ground is False
            and float(sc_live.user_gs or 0.0) >= 35.0
        )

        candidate_stand = self.get_candidate_departure_stand(
            origin,
            default_lat=dep_data.get("lat") if dep_data else None,
            default_lon=dep_data.get("lon") if dep_data else None,
            prev_flight_snapshot=prev_flight_snapshot,
            fresh_dep_chart=(dep_data or {}).get("chart_data"),
            aircraft_wingspan=wingspan
        )
        if candidate_stand and candidate_stand.get("gate"):
            cand_gate = candidate_stand["gate"]
            cand_reason = candidate_stand.get("reason", "turnaround_arrival")
            # If relaunching GateFinder during the exact same OFP (e.g. after auto-quit on takeoff),
            # skip the turnaround modal unless the user is on the ground parked at a different live MSFS stand.
            if is_same_ofp_cold_resume and (
                is_airborne_now
                or cand_reason != "msfs_live"
                or (saved_dep_gate_for_ofp and clean_gate_token(cand_gate) == clean_gate_token(saved_dep_gate_for_ofp))
            ):
                use_previous = False
                stand_decision_made = False
            elif turnaround_keep_gate is not None:
                use_previous = bool(turnaround_keep_gate)
                stand_decision_made = True
            elif self.config.settings.get("auto_lock_turnaround", True) or cand_reason == "msfs_live":
                use_previous = True
                if on_turnaround_check:
                    try:
                        use_previous = on_turnaround_check(cand_gate, origin, destination, origin_rwy, dest_rwy, cand_reason)
                    except TypeError:
                        try:
                            use_previous = on_turnaround_check(cand_gate, origin, destination, origin_rwy, dest_rwy)
                        except TypeError:
                            use_previous = on_turnaround_check(cand_gate)
                stand_decision_made = True
            else:
                use_previous = False

            if use_previous:
                locked_turnaround_stand = candidate_stand
            elif stand_decision_made:
                # User explicitly requested a new stand different from `cand_gate`
                if dep_data and clean_gate_token(dep_data.get("gate", "")) == clean_gate_token(cand_gate):
                    dep_data = process_airport(origin, "departure", origin_rwy, excluded_gate=cand_gate)
                if dep_data:
                    dep_data["user_requested_new_stand"] = True

        # If Turnaround / MSFS Live stand lock was confirmed, apply the locked stand onto the freshly scanned departure airport
        if locked_turnaround_stand and dep_data:
            t_gate = locked_turnaround_stand["gate"]
            mars_best_lock = self.resolve_mars_stand_variant_for_aircraft(
                origin, t_gate,
                gate_lat=locked_turnaround_stand.get("lat"),
                gate_lon=locked_turnaround_stand.get("lon"),
                aircraft_wingspan=wingspan
            )
            if mars_best_lock:
                t_gate = mars_best_lock["name"]
            canon_gate, coords, g_meta = self.resolve_stand_in_airport_db(
                origin, t_gate,
                fallback_lat=(mars_best_lock or locked_turnaround_stand).get("lat"),
                fallback_lon=(mars_best_lock or locked_turnaround_stand).get("lon")
            )
            dep_data["gate"] = canon_gate or t_gate
            dep_data["error"] = None
            dep_data["turnaround_locked"] = True
            dep_data["turnaround_reason"] = locked_turnaround_stand.get("reason", "turnaround_arrival")
            if coords and coords[0] is not None and coords[1] is not None:
                dep_data["lat"] = float(coords[0])
                dep_data["lon"] = float(coords[1])
                dep_data["gate_coords_found"] = True
            if g_meta:
                if g_meta.get("terminal"):
                    dep_data["terminal"] = g_meta["terminal"]
                elif locked_turnaround_stand.get("terminal"):
                    dep_data["terminal"] = locked_turnaround_stand["terminal"]
                if "has_jetway" in g_meta:
                    dep_data["has_jetway"] = bool(g_meta["has_jetway"])
                elif locked_turnaround_stand.get("has_jetway") is not None:
                    dep_data["has_jetway"] = bool(locked_turnaround_stand["has_jetway"])
                if g_meta.get("wingspan"):
                    dep_data["max_wingspan"] = float(g_meta["wingspan"])
                elif locked_turnaround_stand.get("max_wingspan"):
                    dep_data["max_wingspan"] = float(locked_turnaround_stand["max_wingspan"])
                if g_meta.get("heading") is not None:
                    dep_data["heading"] = g_meta["heading"]
                elif locked_turnaround_stand.get("heading") is not None:
                    dep_data["heading"] = locked_turnaround_stand["heading"]
                if "no_pushback" in g_meta:
                    dep_data["no_pushback"] = bool(g_meta["no_pushback"])
                else:
                    dep_data["no_pushback"] = bool(locked_turnaround_stand.get("no_pushback", False))
            if dep_data.get("chart_data") and dep_data.get("lat") is not None and dep_data.get("lon") is not None:
                sc = getattr(self, "simconnect_manager", None)
                u_lat = sc.user_lat if sc else None
                u_lon = sc.user_lon if sc else None
                u_hdg = sc.user_hdg if sc else None
                u_gs = sc.user_gs if sc else None
                u_og = sc.user_on_ground if sc else None
                dep_data["taxi_route"] = self.taxi_router.compute_taxi_route(
                    dep_data["chart_data"], "departure", dep_data["lat"], dep_data["lon"], dep_data["gate"],
                    runway_id=origin_rwy,
                    user_lat=u_lat, user_lon=u_lon, user_hdg=u_hdg, user_gs=u_gs, user_on_ground=u_og,
                    gate_hdg=dep_data.get("heading"), no_pushback=dep_data.get("no_pushback", False)
                )
                if dep_data["taxi_route"]:
                    dep_data["selected_runway"] = dep_data["taxi_route"].get("runway_id", origin_rwy)

        _report_progress(0.95, "Synchronizing EFB & ATC...")
        # Restore persisted session gates/runways/latches ONLY if restarting GateFinder cold on the exact same OFP
        if prev_flight_snapshot is None:
            self._restore_session_state_if_matching(
                origin, destination, dep_data, arr_data,
                ofp_id=ofp_id,
                skip_dep_gate=stand_decision_made
            )
            for ph_d, ph_icao, ph_rwy in ((dep_data, origin, origin_rwy), (arr_data, destination, dest_rwy)):
                if ph_d and ph_d.get("gate") and ph_icao:
                    m_var = self.resolve_mars_stand_variant_for_aircraft(
                        ph_icao, ph_d["gate"],
                        gate_lat=ph_d.get("lat"), gate_lon=ph_d.get("lon"),
                        aircraft_wingspan=wingspan
                    )
                    if m_var and clean_gate_token(m_var["name"]) != clean_gate_token(ph_d["gate"]):
                        ph_d["gate"] = m_var["name"]
                        ph_d["lat"] = m_var["lat"]
                        ph_d["lon"] = m_var["lon"]
                        ph_d["max_wingspan"] = m_var["wingspan"]

        style_key = self.config.settings.get("map_style", "Satellite Imagery")
        style_mapping = {
            "Sleek Dark Mode": "dark",
            "Minimalist Light": "light",
            "Satellite Imagery": "satellite",
            "Standard Map": "osm"
        }
        map_style_short = style_key if style_key in ("dark", "light", "satellite", "osm") else style_mapping.get(style_key, "dark")

        self.current_flight_data = {
            "ofp_id": ofp_id,
            "callsign": ofp_callsign,
            "registration": aircraft_reg,
            "aircraft": aircraft,
            "aircraft_engines": aircraft_engines,
            "aircraft_version": aircraft_version,
            "aircraft_wingspan": wingspan,
            "airline": al_display,
            "departure": dep_data,
            "arrival": arr_data,
            "map_style": map_style_short,
            "show_maps": self.config.settings.get("show_maps", True),
            "hibernate_map_in_flight": self.config.settings.get("hibernate_map_in_flight", False),
            "show_wingspan": self.config.settings.get("show_wingspan", True),
            "check_online_traffic": self.config.settings.get("check_online_traffic", True),
            "auto_clear_ai": self.config.settings.get("auto_clear_ai", True)
        }
        if hasattr(self, "simconnect_manager") and self.simconnect_manager:
            self.simconnect_manager.register_flight(self.current_flight_data)
        if hasattr(self, "interop_hub") and self.interop_hub:
            self.interop_hub.on_flight_loaded(self.current_flight_data)
            if self.current_flight_data.get("arrival"):
                self.current_flight_data["arrival"]["gsx_status"] = self.interop_hub.get_arrival_gsx_status()
        self._save_session_state()

        return self.current_flight_data

    def resolve_mars_stand_variant_for_aircraft(self, icao, gate_name, gate_lat=None, gate_lon=None, aircraft_wingspan=None):
        """
        If `gate_name` belongs to a multi-stand MARS bay (e.g. A 4 [65m Widebody] & A 41 [36m Narrowbody] at LFPO),
        automatically selects the stand variant on that same bay whose max wingspan best matches `aircraft_wingspan`.
        """
        icao_u = str(icao or "").strip().upper()
        g_clean = str(gate_name or "").strip()
        if not icao_u or not g_clean or aircraft_wingspan is None:
            return None
        try:
            ac_ws = float(aircraft_wingspan)
        except (ValueError, TypeError):
            return None

        canon_g, coords, g_meta = self.resolve_stand_in_airport_db(
            icao_u, g_clean, fallback_lat=gate_lat, fallback_lon=gate_lon
        )
        base_name = canon_g or g_clean
        base_lat = coords[0] if (coords and coords[0] is not None) else gate_lat
        base_lon = coords[1] if (coords and coords[1] is not None) else gate_lon
        if base_lat is None or base_lon is None:
            return None
        base_ws = float((g_meta or {}).get("wingspan") or 36.0)

        bay_variants = [{
            "name": base_name,
            "lat": float(base_lat),
            "lon": float(base_lon),
            "wingspan": base_ws,
            "meta": g_meta or {}
        }]
        seen_toks = {clean_gate_token(base_name)}

        coherent_map = getattr(self, "coherent_airports", {}) or {}
        for db in (coherent_map.get(icao_u), self.data.get(icao_u), self.builtin_data.get(icao_u)):
            if not db or not isinstance(db, dict):
                continue
            for al_list in db.values():
                if not isinstance(al_list, list):
                    continue
                for g in al_list:
                    sname = str(g.get("name") or "").strip()
                    slat, slon = g.get("lat"), g.get("lon")
                    if not sname or slat is None or slon is None:
                        continue
                    stok = clean_gate_token(sname)
                    if not stok or stok in seen_toks:
                        continue
                    d_m = haversine(float(base_lat), float(base_lon), float(slat), float(slon))
                    if d_m <= 55.0 and are_mars_related_stands(base_name, sname, d_m, user_wingspan=65.0):
                        seen_toks.add(stok)
                        bay_variants.append({
                            "name": sname,
                            "lat": float(slat),
                            "lon": float(slon),
                            "wingspan": float(g.get("wingspan") or 36.0),
                            "meta": g
                        })

        if len(bay_variants) < 2:
            return None

        compatible = [v for v in bay_variants if v["wingspan"] >= ac_ws - 0.3]
        if not compatible:
            return None
        compatible.sort(key=lambda v: (abs(v["wingspan"] - ac_ws), v["wingspan"]))
        best_v = compatible[0]
        if clean_gate_token(best_v["name"]) != clean_gate_token(base_name):
            print(f"[MARS Variant Match] Remapped {icao_u} '{base_name}' ({base_ws:.1f}m) -> '{best_v['name']}' ({best_v['wingspan']:.1f}m) for aircraft wingspan {ac_ws:.1f}m")
        return best_v

    def detect_live_msfs_parked_stand(self, icao, default_lat=None, default_lon=None, extra_chart_data=None, aircraft_wingspan=None, resolve_mars_variant=False):
        """
        If MSFS is open (SimConnect connected) and the user aircraft is on the ground
        and stationary/slow (<= 8 kt) at `icao`, returns the stand at `icao` closest
        to the aircraft's live GPS coordinates (within 45m), or None.
        """
        icao_u = str(icao or "").strip().upper()
        if not icao_u:
            return None
        sc = getattr(self, "simconnect_manager", None)
        if not sc or not sc.connected or sc.user_lat is None or sc.user_lon is None:
            return None
        if sc.user_on_ground is False or float(sc.user_gs or 0.0) > 8.0:
            return None

        u_lat = float(sc.user_lat)
        u_lon = float(sc.user_lon)
        ac_ws = aircraft_wingspan
        if ac_ws is None and self.current_flight_data:
            ac_ws = self.current_flight_data.get("aircraft_wingspan")

        best_stand = None
        best_dist = 9999.0

        coherent_map = getattr(self, "coherent_airports", {}) or {}
        for db in (coherent_map.get(icao_u), self.data.get(icao_u), self.builtin_data.get(icao_u)):
            if not db:
                continue
            for al_list in db.values():
                for g in al_list:
                    glat, glon = g.get("lat"), g.get("lon")
                    gname = str(g.get("name") or "").strip()
                    if gname and glat is not None and glon is not None:
                        d = haversine(u_lat, u_lon, float(glat), float(glon))
                        if d < best_dist:
                            best_dist = d
                            best_stand = g

        charts_to_check = []
        if extra_chart_data and isinstance(extra_chart_data, dict):
            charts_to_check.append(extra_chart_data)
        if self.current_flight_data:
            for ph in ("departure", "arrival"):
                apt = self.current_flight_data.get(ph) or {}
                if str(apt.get("icao") or "").upper() == icao_u and apt.get("chart_data"):
                    charts_to_check.append(apt["chart_data"])

        for ch in charts_to_check:
            for st in (ch.get("stands") or []):
                s_ref = str(st.get("ref") or "").strip()
                slat, slon = st.get("lat"), st.get("lon")
                if s_ref and slat is not None and slon is not None:
                    d = haversine(u_lat, u_lon, float(slat), float(slon))
                    if d < best_dist:
                        best_dist = d
                        best_stand = {
                            "name": s_ref,
                            "lat": float(slat),
                            "lon": float(slon),
                            "heading": st.get("heading"),
                            "has_jetway": st.get("has_jetway", True),
                            "wingspan": 999.0
                        }

        if best_stand and best_dist <= 45.0:
            mars_best = None
            if resolve_mars_variant:
                mars_best = self.resolve_mars_stand_variant_for_aircraft(
                    icao_u, best_stand["name"],
                    gate_lat=best_stand.get("lat"),
                    gate_lon=best_stand.get("lon"),
                    aircraft_wingspan=ac_ws
                )
            target_name = mars_best["name"] if mars_best else best_stand["name"]
            canon_gate, coords, g_meta = self.resolve_stand_in_airport_db(
                icao_u, target_name,
                fallback_lat=(mars_best or best_stand).get("lat"),
                fallback_lon=(mars_best or best_stand).get("lon")
            )
            return {
                "gate": canon_gate or target_name,
                "lat": coords[0] if coords else (mars_best or best_stand).get("lat"),
                "lon": coords[1] if coords else (mars_best or best_stand).get("lon"),
                "heading": (g_meta or {}).get("heading", best_stand.get("heading")),
                "no_pushback": (g_meta or {}).get("no_pushback", best_stand.get("no_pushback", False)),
                "terminal": (g_meta or {}).get("terminal", best_stand.get("terminal")),
                "has_jetway": (g_meta or {}).get("has_jetway", best_stand.get("has_jetway")),
                "max_wingspan": (g_meta or {}).get("wingspan", (mars_best or best_stand).get("wingspan")),
                "reason": "msfs_live",
                "distance_m": round(best_dist, 1)
            }
        return None

    def get_candidate_departure_stand(self, origin_icao, default_lat=None, default_lon=None, prev_flight_snapshot=None, fresh_dep_chart=None, aircraft_wingspan=None):
        """
        Returns the candidate stand to propose keeping at `origin_icao` when importing a flight plan:
          1. Live MSFS aircraft parked at a stand at `origin_icao` (SimConnect GPS match <= 45m).
          2. Previous in-memory flight's arrival stand if `prev_arrival.icao == origin_icao`.
          3. Previous in-memory flight's departure stand if `prev_departure.icao == origin_icao`.
          4. Persisted session (`last_flight_session.json`) arrival or departure stand at `origin_icao`.
        """
        icao_u = str(origin_icao or "").strip().upper()
        if not icao_u:
            return None

        # 1. Live MSFS parked stand at `origin_icao`
        live_st = self.detect_live_msfs_parked_stand(
            icao_u, default_lat=default_lat, default_lon=default_lon,
            extra_chart_data=fresh_dep_chart, aircraft_wingspan=aircraft_wingspan,
            resolve_mars_variant=True
        )
        if live_st and live_st.get("gate") and live_st.get("gate") != "N/A":
            return live_st

        # 2 & 3. Previous in-memory flight data (arrival at `origin_icao` OR same departure `origin_icao`)
        fd_prev = prev_flight_snapshot if prev_flight_snapshot is not None else self.current_flight_data
        if fd_prev:
            for ph, r_tag in (("arrival", "turnaround_arrival"), ("departure", "same_departure")):
                apt = fd_prev.get(ph) or {}
                if str(apt.get("icao") or "").strip().upper() == icao_u:
                    g_val = str(apt.get("gate") or "").strip()
                    if g_val and g_val != "N/A":
                        return {
                            "gate": g_val,
                            "lat": apt.get("lat"),
                            "lon": apt.get("lon"),
                            "heading": apt.get("heading"),
                            "no_pushback": apt.get("no_pushback", False),
                            "terminal": apt.get("terminal"),
                            "has_jetway": apt.get("has_jetway"),
                            "max_wingspan": apt.get("max_wingspan"),
                            "reason": r_tag
                        }

        # 4. Persisted session (`last_flight_session.json` + `last_stands_by_icao`)
        try:
            p = self._get_session_state_path()
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict) and (time.time() - float(saved.get("timestamp") or 0) <= 24 * 3600):
                    if str(saved.get("destination") or "").strip().upper() == icao_u:
                        s_arr_g = str(saved.get("arr_gate") or "").strip()
                        if s_arr_g and s_arr_g != "N/A":
                            return {"gate": s_arr_g, "reason": "turnaround_arrival"}
                    if str(saved.get("origin") or "").strip().upper() == icao_u:
                        s_dep_g = str(saved.get("dep_gate") or "").strip()
                        if s_dep_g and s_dep_g != "N/A":
                            return {"gate": s_dep_g, "reason": "same_departure"}
                    by_icao = saved.get("last_stands_by_icao")
                    if isinstance(by_icao, dict) and icao_u in by_icao:
                        entry = by_icao[icao_u]
                        if isinstance(entry, dict) and (time.time() - float(entry.get("timestamp") or 0) <= 24 * 3600):
                            eg = str(entry.get("gate") or "").strip()
                            if eg and eg != "N/A":
                                return {
                                    "gate": eg,
                                    "lat": entry.get("lat"),
                                    "lon": entry.get("lon"),
                                    "reason": entry.get("reason", "turnaround_arrival")
                                }
        except Exception:
            pass

        return None

    def _get_session_state_path(self):
        cfg_file = getattr(self.config, "settings_file", None) or getattr(self.config, "config_file", None)
        base_dir = os.path.dirname(os.path.abspath(cfg_file)) if cfg_file else os.path.abspath(".")
        return os.path.join(base_dir, "last_flight_session.json")

    def _save_session_state(self):
        if not self.current_flight_data:
            return
        try:
            p_path = self._get_session_state_path()
            last_stands_by_icao = {}
            if os.path.exists(p_path):
                try:
                    with open(p_path, "r", encoding="utf-8") as rf:
                        prev_saved = json.load(rf)
                    if isinstance(prev_saved, dict) and isinstance(prev_saved.get("last_stands_by_icao"), dict):
                        now_t = time.time()
                        for k_icao, v_st in prev_saved["last_stands_by_icao"].items():
                            if isinstance(v_st, dict) and (now_t - float(v_st.get("timestamp") or 0) <= 24 * 3600):
                                last_stands_by_icao[k_icao] = v_st
                except Exception:
                    pass

            dep = self.current_flight_data.get("departure") or {}
            arr = self.current_flight_data.get("arrival") or {}
            now_ts = time.time()
            if dep.get("icao") and dep.get("gate") and dep.get("gate") != "N/A":
                last_stands_by_icao[str(dep["icao"]).upper()] = {
                    "gate": dep.get("gate"),
                    "lat": dep.get("lat"),
                    "lon": dep.get("lon"),
                    "reason": "same_departure",
                    "timestamp": now_ts
                }
            if arr.get("icao") and arr.get("gate") and arr.get("gate") != "N/A":
                last_stands_by_icao[str(arr["icao"]).upper()] = {
                    "gate": arr.get("gate"),
                    "lat": arr.get("lat"),
                    "lon": arr.get("lon"),
                    "reason": "turnaround_arrival",
                    "timestamp": now_ts
                }

            payload = {
                "timestamp": now_ts,
                "ofp_id": self.current_flight_data.get("ofp_id"),
                "origin": dep.get("icao"),
                "destination": arr.get("icao"),
                "aircraft": self.current_flight_data.get("aircraft"),
                "airline": self.current_flight_data.get("airline"),
                "dep_gate": dep.get("gate"),
                "dep_gate_source": dep.get("gate_source"),
                "dep_selected_runway": dep.get("selected_runway"),
                "dep_atc_runway": dep.get("atc_runway"),
                "dep_atc_runway_source": dep.get("atc_runway_source"),
                "arr_gate": arr.get("gate"),
                "arr_gate_source": arr.get("gate_source"),
                "arr_selected_runway": arr.get("selected_runway"),
                "arr_atc_runway": arr.get("atc_runway"),
                "arr_atc_runway_source": arr.get("atc_runway_source"),
                "dep_runway_entered": dict(self.taxi_router.dep_runway_entered),
                "arr_vacated_runway": dict(self.taxi_router.arr_vacated_runway),
                "locked_arrival_exit": dict(self.taxi_router.locked_arrival_exit),
                "last_stands_by_icao": last_stands_by_icao
            }
            with open(p_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    def _restore_session_state_if_matching(self, origin, destination, dep_data, arr_data, ofp_id=None, skip_dep_gate=False):
        try:
            p = self._get_session_state_path()
            if not os.path.exists(p):
                return
            with open(p, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if not isinstance(saved, dict):
                return
            # Valid for 14 hours on the same origin -> destination pair and same SimBrief OFP ID
            if time.time() - float(saved.get("timestamp") or 0) > 14 * 3600:
                return
            if saved.get("origin") != origin or saved.get("destination") != destination:
                return
            if ofp_id and saved.get("ofp_id") and str(saved.get("ofp_id")) != str(ofp_id):
                return

            sc = getattr(self, "simconnect_manager", None)
            u_lat = sc.user_lat if sc else None
            u_lon = sc.user_lon if sc else None
            u_hdg = sc.user_hdg if sc else None
            u_gs = sc.user_gs if sc else None
            u_og = sc.user_on_ground if sc else None

            if isinstance(saved.get("dep_runway_entered"), dict):
                self.taxi_router.dep_runway_entered.update(saved["dep_runway_entered"])
            if isinstance(saved.get("arr_vacated_runway"), dict):
                self.taxi_router.arr_vacated_runway.update(saved["arr_vacated_runway"])
            if isinstance(saved.get("locked_arrival_exit"), dict):
                self.taxi_router.locked_arrival_exit.update(saved["locked_arrival_exit"])

            for phase, apt, prefix in (("departure", dep_data, "dep"), ("arrival", arr_data, "arr")):
                if not apt:
                    continue
                chart = apt.get("chart_data") or {}
                c_lat = chart.get("center_lat")
                c_lon = chart.get("center_lon")
                s_gate = None if (phase == "departure" and skip_dep_gate) else saved.get(f"{prefix}_gate")
                if isinstance(s_gate, str):
                    s_gate = re.sub(r'\s*\(.*$', '', s_gate).strip()
                    s_gate = re.sub(r'\s+-\s+.*$', '', s_gate).strip()
                    s_gate = re.sub(r'\s+MARS\b.*$', '', s_gate, flags=re.IGNORECASE).strip()
                s_rwy = saved.get(f"{prefix}_selected_runway")
                if isinstance(s_rwy, str) and s_rwy.strip().upper() in ("RWY", "N/A", "NONE"):
                    s_rwy = None
                if s_gate and s_gate != "N/A" and s_gate != apt.get("gate"):
                    canon_gate, coords, g_meta = self.resolve_stand_in_airport_db(apt.get("icao"), s_gate)
                    if coords and coords[0] is not None and coords[1] is not None:
                        if c_lat is None or c_lon is None or (abs(float(coords[0]) - float(c_lat)) < 0.25 and abs(float(coords[1]) - float(c_lon)) < 0.35):
                            apt["gate"] = canon_gate
                            apt["error"] = None
                            apt["lat"] = float(coords[0])
                            apt["lon"] = float(coords[1])
                            apt["gate_coords_found"] = True
                            if saved.get(f"{prefix}_gate_source"):
                                s_src = str(saved[f"{prefix}_gate_source"])
                                if "LIVE" in s_src.upper() or "PARKED" in s_src.upper():
                                    s_src = "GateFinder"
                                apt["gate_source"] = s_src
                            if g_meta:
                                if g_meta.get("terminal"):
                                    apt["terminal"] = g_meta["terminal"]
                                if "has_jetway" in g_meta:
                                    apt["has_jetway"] = bool(g_meta["has_jetway"])
                                if g_meta.get("wingspan"):
                                    apt["max_wingspan"] = float(g_meta["wingspan"])
                                if "heading" in g_meta:
                                    apt["heading"] = g_meta["heading"]
                                if "no_pushback" in g_meta:
                                    apt["no_pushback"] = bool(g_meta["no_pushback"])
                if s_rwy:
                    apt["selected_runway"] = s_rwy
                if saved.get(f"{prefix}_atc_runway"):
                    apt["atc_runway"] = saved[f"{prefix}_atc_runway"]
                if saved.get(f"{prefix}_atc_runway_source"):
                    apt["atc_runway_source"] = saved[f"{prefix}_atc_runway_source"]
                if apt.get("chart_data") and apt.get("lat") is not None and apt.get("lon") is not None:
                    apt["taxi_route"] = self.taxi_router.compute_taxi_route(
                        apt["chart_data"], phase, apt["lat"], apt["lon"], apt["gate"],
                        runway_id=apt.get("selected_runway"),
                        user_lat=u_lat, user_lon=u_lon, user_hdg=u_hdg, user_gs=u_gs, user_on_ground=u_og,
                        gate_hdg=apt.get("heading"), no_pushback=apt.get("no_pushback", False)
                    )
        except Exception:
            pass

    def resolve_stand_in_airport_db(self, icao, raw_gate, fallback_lat=None, fallback_lon=None):
        """
        Matches a raw gate string from BeyondATC, SayIntentions, or manual input
        against the loaded GSX INI database, built-in BGL DB, or OSM stands for `icao`.
        Returns (canonical_gate_name, (lat, lon) or None, metadata_dict).
        """
        icao_u = str(icao or "").strip().upper()
        target_tok = clean_gate_token(raw_gate)
        base_tok = strip_redundant_gate_suffix(target_tok)
        bgl_type_stripped_tok = None
        m_bgl_suf = re.match(r'^([A-Z]+\d+)[GPMSLH]$', target_tok)
        if m_bgl_suf:
            bgl_type_stripped_tok = m_bgl_suf.group(1)

        num_only = re.sub(r'^[A-Z]+', '', base_tok) if re.match(r'^[A-Z]+\d+$', base_tok) else None
        # Also support prefix<->suffix swap (e.g. BATC says "A 65" while GSX/MSFS calls it "65A")
        swapped_tok = None
        m_pre = re.match(r'^([A-Z]+)(\d+)$', base_tok)
        m_suf = re.match(r'^(\d+)([A-Z]+)$', base_tok)
        if m_pre:
            swapped_tok = f"{m_pre.group(2)}{m_pre.group(1)}"
        elif m_suf:
            swapped_tok = f"{m_suf.group(2)}{m_suf.group(1)}"

        # 1. Search Coherent On-the-Fly DB, GSX INI DB, and Built-in BGL DB
        coherent_map = getattr(self, "coherent_airports", {}) or {}
        for db in (coherent_map.get(icao_u), self.data.get(icao_u), self.builtin_data.get(icao_u)):
            if not db:
                continue
            # First pass: exact token or redundant-suffix-stripped match (e.g. "Ramp P8P" <-> "P8")
            for al_list in db.values():
                for g in al_list:
                    g_tok = clean_gate_token(g.get("name", ""))
                    r_tok = clean_gate_token(g.get("raw_name", ""))
                    o_tok = clean_gate_token(g.get("osm_ref", ""))
                    if g_tok and (
                        gate_tokens_match(g_tok, target_tok)
                        or (r_tok and gate_tokens_match(r_tok, target_tok))
                        or (o_tok and gate_tokens_match(o_tok, target_tok))
                        or (swapped_tok and (g_tok == swapped_tok or r_tok == swapped_tok or o_tok == swapped_tok))
                    ):
                        coords = (g["lat"], g["lon"]) if (g.get("lat") is not None and g.get("lon") is not None) else None
                        return g["name"], coords, g
            # Second pass: BGL parking-type trailing letter strip (e.g. "P8G" -> "P8") or numeric match
            is_pure_num_target = bool(re.match(r'^\d+[A-Z]?$', target_tok))
            if bgl_type_stripped_tok or num_only or is_pure_num_target:
                for al_list in db.values():
                    for g in al_list:
                        g_tok = clean_gate_token(g.get("name", ""))
                        r_tok = clean_gate_token(g.get("raw_name", ""))
                        o_tok = clean_gate_token(g.get("osm_ref", ""))
                        if bgl_type_stripped_tok and (
                            g_tok == bgl_type_stripped_tok or r_tok == bgl_type_stripped_tok or o_tok == bgl_type_stripped_tok
                        ):
                            coords = (g["lat"], g["lon"]) if (g.get("lat") is not None and g.get("lon") is not None) else None
                            return g["name"], coords, g
                        if num_only and (g_tok == num_only or r_tok == num_only or o_tok == num_only):
                            coords = (g["lat"], g["lon"]) if (g.get("lat") is not None and g.get("lon") is not None) else None
                            return g["name"], coords, g
                        if is_pure_num_target:
                            g_num = re.sub(r'^[A-Z]+', '', g_tok) if g_tok else ""
                            r_num = re.sub(r'^[A-Z]+', '', r_tok) if r_tok else ""
                            if g_num == target_tok or r_num == target_tok:
                                coords = (g["lat"], g["lon"]) if (g.get("lat") is not None and g.get("lon") is not None) else None
                                return g["name"], coords, g

        # 2. Search cached chart_data stands (OSM + BGL merged stands)
        if self.current_flight_data:
            for ph in ("departure", "arrival"):
                apt = self.current_flight_data.get(ph) or {}
                if apt.get("icao") == icao_u and apt.get("chart_data"):
                    for st in (apt["chart_data"].get("stands") or []):
                        s_ref = str(st.get("ref") or "").strip()
                        s_tok = clean_gate_token(s_ref)
                        s_num = re.sub(r'^[A-Z]+', '', s_tok) if s_tok else ""
                        if (
                            gate_tokens_match(s_tok, target_tok)
                            or (bgl_type_stripped_tok and s_tok == bgl_type_stripped_tok)
                            or (num_only and s_tok == num_only)
                            or (re.match(r'^\d+[A-Z]?$', target_tok) and s_num == target_tok)
                        ):
                            return s_ref, (st.get("lat"), st.get("lon")), {
                                "name": s_ref,
                                "lat": st.get("lat"),
                                "lon": st.get("lon"),
                                "has_jetway": st.get("has_jetway", True),
                                "wingspan": 999.0
                            }

        # 3. Fallback to cleaned label and provided coordinates
        pretty_label = re.sub(r'^(GATE|STAND|PARKING|RAMP)[\s_\-]*', '', str(raw_gate).strip(), flags=re.IGNORECASE)
        pretty_label = re.sub(r'[\s_\-]+NONE$', '', pretty_label, flags=re.IGNORECASE).strip() or str(raw_gate).strip()
        fb_coords = (fallback_lat, fallback_lon) if (fallback_lat is not None and fallback_lon is not None) else None
        return pretty_label, fb_coords, {"name": pretty_label, "lat": fallback_lat, "lon": fallback_lon}

    def apply_hub_gate_override(self, phase, gate_id, coords, gate_meta=None, source=None):
        """
        Updates the active gate for `phase` ('departure' or 'arrival'), updates SimConnect
        AI clearing target coordinates, and recalculates the Lido A* ground taxi route.
        """
        if not self.current_flight_data or phase not in ("departure", "arrival"):
            return
        apt = self.current_flight_data.get(phase)
        if not apt:
            return

        apt["gate"] = gate_id
        if source is not None:
            apt["gate_source"] = source.value if hasattr(source, "value") else str(source)
            apt["gate_source_key"] = source.name if hasattr(source, "name") else str(source)
        apt["gsx_synced"] = False

        if coords and coords[0] is not None and coords[1] is not None:
            apt["lat"] = float(coords[0])
            apt["lon"] = float(coords[1])
            apt["gate_coords_found"] = True

        if gate_meta:
            if gate_meta.get("terminal"):
                apt["terminal"] = gate_meta["terminal"]
            if "has_jetway" in gate_meta:
                apt["has_jetway"] = bool(gate_meta["has_jetway"])
            if gate_meta.get("wingspan"):
                apt["max_wingspan"] = float(gate_meta["wingspan"])
            if "heading" in gate_meta:
                apt["heading"] = gate_meta["heading"]
            if "no_pushback" in gate_meta:
                apt["no_pushback"] = bool(gate_meta["no_pushback"])

        # Recompute A* Ground Taxi Route immediately to the new stand
        if apt.get("chart_data") and apt.get("lat") is not None and apt.get("lon") is not None:
            sc = getattr(self, "simconnect_manager", None)
            u_lat = sc.user_lat if sc else None
            u_lon = sc.user_lon if sc else None
            u_hdg = sc.user_hdg if sc else None
            u_gs = sc.user_gs if sc else None
            u_og = sc.user_on_ground if sc else None
            t_route = self.taxi_router.compute_taxi_route(
                apt["chart_data"], phase, apt["lat"], apt["lon"], apt["gate"],
                runway_id=apt.get("selected_runway"),
                user_lat=u_lat, user_lon=u_lon, user_hdg=u_hdg, user_gs=u_gs, user_on_ground=u_og,
                gate_hdg=apt.get("heading"), no_pushback=apt.get("no_pushback", False),
                atc_taxi_via=apt.get("atc_taxi_via")
            )
            apt["taxi_route"] = t_route
            if t_route and t_route.get("runway_id"):
                apt["selected_runway"] = t_route["runway_id"]

        # Update SimConnect AI gate guardian with the new stand coordinates
        if hasattr(self, "simconnect_manager") and self.simconnect_manager:
            self.simconnect_manager.register_flight(self.current_flight_data)
        self._save_session_state()

    def set_active_runway(self, phase, rwy_id, manual=True):
        if not self.current_flight_data or phase not in ("departure", "arrival"):
            return None
        apt = self.current_flight_data.get(phase)
        if not apt:
            return None
        if manual:
            apt["atc_taxi_via"] = None
            if phase == "departure":
                self.taxi_router.dep_runway_entered.pop(apt.get("icao", ""), None)
        if manual and hasattr(self, "interop_hub") and self.interop_hub:
            self.interop_hub.on_user_runway_selected(phase, rwy_id)
        apt["selected_runway"] = rwy_id
        if apt.get("chart_data") and apt.get("gate") and apt.get("lat") is not None:
            u_lat = self.simconnect_manager.user_lat if hasattr(self, "simconnect_manager") else None
            u_lon = self.simconnect_manager.user_lon if hasattr(self, "simconnect_manager") else None
            u_hdg = self.simconnect_manager.user_hdg if hasattr(self, "simconnect_manager") else None
            u_gs = self.simconnect_manager.user_gs if hasattr(self, "simconnect_manager") else None
            u_og = self.simconnect_manager.user_on_ground if hasattr(self, "simconnect_manager") else None
            t_route = self.taxi_router.compute_taxi_route(
                apt["chart_data"], phase, apt["lat"], apt["lon"], apt["gate"],
                runway_id=rwy_id, user_lat=u_lat, user_lon=u_lon,
                user_hdg=u_hdg, user_gs=u_gs, user_on_ground=u_og,
                gate_hdg=apt.get("heading"), no_pushback=apt.get("no_pushback", False),
                atc_taxi_via=apt.get("atc_taxi_via")
            )
            apt["taxi_route"] = t_route
            if t_route:
                apt["selected_runway"] = t_route.get("runway_id", rwy_id)
        self._save_session_state()
        return apt.get("taxi_route")

    def reposition_aircraft(self, phase, gate_id):
        """
        Selects `gate_id` in GateFinder and triggers GSX Pro 'Reposition Aircraft' -> 'Just warp me there'.
        """
        if hasattr(self, "interop_hub") and self.interop_hub:
            return self.interop_hub.reposition_aircraft_to_gate(phase, gate_id)
        return None

    def resolve_live_stand_prompt(self, keep_live=True):
        prompt = getattr(self, "pending_live_stand_prompt", None)
        self.pending_live_stand_prompt = None
        if not prompt or not self.current_flight_data:
            return
        if keep_live:
            dep_icao = prompt.get("icao")
            live_stand = prompt.get("live_stand")
            if dep_icao and live_stand:
                try:
                    canon_g, coords, meta = self.resolve_stand_in_airport_db(dep_icao, live_stand)
                    self.apply_hub_gate_override(
                        "departure",
                        canon_g or live_stand,
                        coords,
                        gate_meta=meta,
                        source="GateFinder"
                    )
                except Exception as e:
                    print(f"[Backend] Error applying live MSFS stand {live_stand}: {e}")

    def refresh_arrival_vatsim_stand_if_occupied(self, checkpoint_label="Pre-TOD"):
        """
        Re-fetches live VATSIM & IVAO traffic at the arrival airport (e.g. at Pre-TOD ~180 NM
        and on Approach ~18 NM). Updates `bypassed_summary` and, if the currently predicted
        arrival stand is now occupied by another online pilot, automatically reassigns a
        conflict-free stand in the same terminal/airline group.
        """
        if not self.config.settings.get("check_online_traffic", True):
            return None
        if not self.current_flight_data:
            return None
        arr = self.current_flight_data.get("arrival")
        if not arr or not isinstance(arr, dict):
            return None
        arr_icao = str(arr.get("icao") or "").strip().upper()
        cur_gate = str(arr.get("gate") or "").strip()
        if not arr_icao or not cur_gate or cur_gate in ("N/A", "No Gate Found", "No Suitable Stand"):
            return None

        try:
            pilots = self.network_checker.fetch_data(force=True)
        except Exception as exc:
            print(f"[VATSIM Refresh] Error fetching live traffic: {exc}")
            return None
        if not pilots:
            return None

        sc = getattr(self, "simconnect_manager", None)
        u_lat_self = sc.user_lat if (sc and sc.connected and not getattr(sc, "in_menu", False)) else None
        u_lon_self = sc.user_lon if (sc and sc.connected and not getattr(sc, "in_menu", False)) else None
        ofp_callsign = str(self.current_flight_data.get("callsign") or "").strip().upper()

        # Gather all stands at arrival airport to compute updated bypassed_summary & candidate pool
        candidate_stands = []
        seen_names = set()
        coherent_map = getattr(self, "coherent_airports", {}) or {}
        for db in (coherent_map.get(arr_icao), self.data.get(arr_icao), self.builtin_data.get(arr_icao)):
            if not db:
                continue
            for al_code, al_list in db.items():
                for g in al_list:
                    gname = str(g.get("name") or "").strip()
                    glat, glon = g.get("lat"), g.get("lon")
                    if not gname or glat is None or glon is None:
                        continue
                    norm_n = clean_gate_token(gname)
                    if norm_n not in seen_names:
                        seen_names.add(norm_n)
                        g_copy = dict(g)
                        als = set(g.get("airlines") or [])
                        if al_code and str(al_code).upper() != "ANY":
                            als.add(str(al_code).upper())
                        g_copy["_als"] = {str(a).strip().upper() for a in als if a}
                        candidate_stands.append(g_copy)

        chart = arr.get("chart_data") or {}
        for st in (chart.get("stands") or []):
            s_ref = str(st.get("ref") or "").strip()
            slat, slon = st.get("lat"), st.get("lon")
            if not s_ref or slat is None or slon is None:
                continue
            norm_s = clean_gate_token(s_ref)
            if norm_s not in seen_names:
                seen_names.add(norm_s)
                candidate_stands.append({
                    "name": s_ref,
                    "lat": float(slat),
                    "lon": float(slon),
                    "terminal": st.get("terminal") or "",
                    "wingspan": float(st.get("wingspan") or 36.0),
                    "has_jetway": bool(st.get("has_jetway", True)),
                    "_als": {str(a).strip().upper() for a in (st.get("airlines") or []) if a}
                })

        bypassed = []
        free_stands = []
        for g in candidate_stands:
            glat, glon = float(g["lat"]), float(g["lon"])
            occ_pilot = None
            for p in pilots:
                if self.network_checker.is_pilot_self(p, user_lat=u_lat_self, user_lon=u_lon_self, user_callsign=ofp_callsign):
                    continue
                if haversine(glat, glon, p["lat"], p["lon"]) < 50.0:
                    occ_pilot = p
                    break
            if occ_pilot:
                bypassed.append({
                    "name": g["name"],
                    "network": occ_pilot["network"],
                    "callsign": occ_pilot["callsign"]
                })
            else:
                free_stands.append(g)

        if bypassed:
            items = [f"{item['name']} ({item['network']})" for item in bypassed]
            arr["bypassed_summary"] = "Occupied: " + ", ".join(items)
        else:
            arr["bypassed_summary"] = ""

        # Check if currently assigned arrival stand is occupied
        arr_lat, arr_lon = arr.get("lat"), arr.get("lon")
        if arr_lat is None or arr_lon is None:
            return None

        occupying_current = None
        for p in pilots:
            if self.network_checker.is_pilot_self(p, user_lat=u_lat_self, user_lon=u_lon_self, user_callsign=ofp_callsign):
                continue
            if haversine(float(arr_lat), float(arr_lon), p["lat"], p["lon"]) < 48.0:
                occupying_current = p
                break

        if not occupying_current:
            return None

        # Do not override a stand explicitly assigned by AI ATC or manually chosen by the pilot
        src_key = str(arr.get("gate_source_key") or "").upper()
        if src_key in ("BEYOND_ATC", "SAY_INTENTIONS", "USER_MANUAL"):
            return None

        ac_ws = float(self.current_flight_data.get("aircraft_wingspan") or 36.0)
        cur_term = str(arr.get("terminal") or "").strip().lower()
        cur_al = str(arr.get("airline_code") or "").strip().upper()
        cur_jw = bool(arr.get("has_jetway", True))
        cur_tok = clean_gate_token(cur_gate)

        viable = [
            g for g in free_stands
            if clean_gate_token(g["name"]) != cur_tok
            and float(g.get("wingspan") or 36.0) >= ac_ws
            and not g.get("is_ga")
            and not g.get("is_military")
        ]
        if not viable:
            return None

        def _score_alt(g):
            sc_val = 0.0
            als = g.get("_als") or set()
            if cur_al and cur_al in als:
                sc_val += 500.0
            g_term = str(g.get("terminal") or "").strip().lower()
            if cur_term and g_term and cur_term == g_term:
                sc_val += 250.0
            if bool(g.get("has_jetway", True)) == cur_jw:
                sc_val += 80.0
            # Prefer a stand geographically close to the original terminal/apron
            try:
                d_orig = haversine(float(arr_lat), float(arr_lon), float(g["lat"]), float(g["lon"]))
                sc_val += max(0.0, 120.0 - (d_orig / 15.0))
            except Exception:
                pass
            return sc_val

        viable.sort(key=_score_alt, reverse=True)
        chosen = viable[0]
        canon_g, coords, meta = self.resolve_stand_in_airport_db(
            arr_icao, chosen["name"], fallback_lat=chosen["lat"], fallback_lon=chosen["lon"]
        )
        new_gate = canon_g or chosen["name"]
        if hasattr(self, "interop_hub") and self.interop_hub:
            self.interop_hub.on_vatsim_arrival_stand_reassigned(
                icao=arr_icao,
                old_gate=cur_gate,
                new_gate=new_gate,
                coords=coords,
                gate_meta=meta,
                occupying_pilot=occupying_current,
                checkpoint_label=checkpoint_label
            )
        return {
            "icao": arr_icao,
            "old_gate": cur_gate,
            "new_gate": new_gate,
            "occupying_pilot": occupying_current,
            "checkpoint": checkpoint_label
        }

    def get_dynamic_flight_data(self):
        if not self.current_flight_data:
            return {}
        fd = dict(self.current_flight_data)
        hib_opt = bool(self.config.settings.get("hibernate_map_in_flight", True))
        fd["hibernate_map_in_flight"] = hib_opt
        fd["map_hibernated"] = False
        fd["is_airborne"] = False
        if hasattr(self, "simconnect_manager") and self.simconnect_manager:
            sc = self.simconnect_manager
            sc_conn = sc.connected
            in_menu = bool(getattr(sc, "in_menu", False))
            u_lat, u_lon, u_hdg, u_gs, u_og = sc.user_lat, sc.user_lon, sc.user_hdg, sc.user_gs, sc.user_on_ground
            is_airborne = bool(sc_conn and not in_menu and u_og is False and float(u_gs or 0.0) >= 35.0)
            fd["is_airborne"] = is_airborne
            fd["map_hibernated"] = bool(hib_opt and is_airborne)
            if is_airborne or (u_gs or 0.0) >= 4.0:
                self.pending_live_stand_prompt = None
            if is_airborne:
                fd["recommended_phase"] = "arrival"
            elif in_menu:
                fd["recommended_phase"] = "departure"
            fd["user_aircraft"] = {
                "connected": sc_conn,
                "in_menu": in_menu,
                "lat": round(u_lat, 6) if u_lat is not None else None,
                "lon": round(u_lon, 6) if u_lon is not None else None,
                "heading": round(u_hdg, 1) if u_hdg is not None else 0.0,
                "gs": round(u_gs, 1) if u_gs is not None else 0.0,
                "on_ground": u_og,
                "engines_running": getattr(sc, "user_engines_running", None)
            }
            d_dep = float('inf')
            d_arr = float('inf')
            if sc_conn and u_lat is not None:
                if "departure" in fd and fd["departure"] and fd["departure"].get("lat") is not None:
                    d_dep = haversine(u_lat, u_lon, fd["departure"]["lat"], fd["departure"]["lon"])
                if "arrival" in fd and fd["arrival"] and fd["arrival"].get("lat") is not None:
                    d_arr = haversine(u_lat, u_lon, fd["arrival"]["lat"], fd["arrival"]["lon"])
            fd["d_dep_m"] = d_dep if d_dep != float('inf') else None
            fd["d_arr_m"] = d_arr if d_arr != float('inf') else None
            if "departure" in fd and fd["departure"]:
                dep = dict(fd["departure"])
                dep["ai_cleared"] = sc.dep_cleared
                dep["ai_active"] = sc.dep_loop_active and sc_conn
                dep["simconnect_connected"] = sc_conn
                if sc_conn and u_lat is not None and dep.get("chart_data") and dep.get("lat") is not None:
                    if d_dep < 6500.0:
                        prev_pos = getattr(self, "_last_dep_route_pos", None)
                        prev_key = getattr(self, "_last_dep_route_key", None)
                        cur_key = (dep.get("icao"), dep.get("gate"), dep.get("selected_runway"), tuple(dep.get("atc_taxi_via") or ()), bool(u_og))
                        cur_dep_status = (dep.get("taxi_route") or {}).get("live_status")
                        back_at_gate = (d_dep < 55.0 and (u_gs or 0.0) < 3.0 and u_og is not False)
                        if cur_dep_status == "ON_RUNWAY" and not back_at_gate and prev_key == cur_key:
                            need_recalc = False
                        else:
                            need_recalc = (
                                not dep.get("taxi_route")
                                or prev_pos is None
                                or prev_key != cur_key
                                or haversine(u_lat, u_lon, prev_pos[0], prev_pos[1]) > 4.0
                            )
                        if need_recalc:
                            dep["taxi_route"] = self.taxi_router.compute_taxi_route(
                                dep["chart_data"], "departure", dep["lat"], dep["lon"], dep["gate"],
                                runway_id=dep.get("selected_runway"),
                                user_lat=u_lat, user_lon=u_lon, user_hdg=u_hdg, user_gs=u_gs, user_on_ground=u_og,
                                gate_hdg=dep.get("heading"), no_pushback=dep.get("no_pushback", False),
                                atc_taxi_via=dep.get("atc_taxi_via")
                            )
                            self.current_flight_data["departure"]["taxi_route"] = dep["taxi_route"]
                            self._last_dep_route_pos = (u_lat, u_lon)
                            self._last_dep_route_key = cur_key
                            self._save_session_state()
                        if u_og is not False:
                            fd["recommended_phase"] = "departure"
                    elif is_airborne or (d_dep >= 6500.0 and d_arr < 15000.0):
                        # Aircraft has already departed (in flight or on ground at arrival airport)
                        dep_icao = dep.get("icao", "")
                        if dep_icao and not self.taxi_router.dep_runway_entered.get(dep_icao):
                            self.taxi_router.dep_runway_entered[dep_icao] = dep.get("selected_runway") or "RWY"
                            dep["taxi_route"] = self.taxi_router.compute_taxi_route(
                                dep["chart_data"], "departure", dep["lat"], dep["lon"], dep["gate"],
                                runway_id=dep.get("selected_runway"),
                                user_lat=u_lat, user_lon=u_lon, user_hdg=u_hdg, user_gs=u_gs, user_on_ground=u_og,
                                gate_hdg=dep.get("heading"), no_pushback=dep.get("no_pushback", False)
                            )
                            self.current_flight_data["departure"]["taxi_route"] = dep["taxi_route"]
                fd["departure"] = dep

            if "arrival" in fd and fd["arrival"]:
                arr = dict(fd["arrival"])
                arr["ai_cleared"] = sc.arr_cleared
                arr["ai_active"] = sc.arr_loop_active and sc_conn
                arr["simconnect_connected"] = sc_conn
                if sc_conn and u_lat is not None and arr.get("chart_data") and arr.get("lat") is not None:
                    if d_arr < 8500.0:
                        prev_pos = getattr(self, "_last_arr_route_pos", None)
                        prev_key = getattr(self, "_last_arr_route_key", None)
                        cur_key = (arr.get("icao"), arr.get("gate"), arr.get("selected_runway"), tuple(arr.get("atc_taxi_via") or ()), bool(u_og))
                        need_recalc = (
                            not arr.get("taxi_route")
                            or prev_pos is None
                            or prev_key != cur_key
                            or haversine(u_lat, u_lon, prev_pos[0], prev_pos[1]) > 4.0
                        )
                        if need_recalc:
                            arr["taxi_route"] = self.taxi_router.compute_taxi_route(
                                arr["chart_data"], "arrival", arr["lat"], arr["lon"], arr["gate"],
                                runway_id=arr.get("selected_runway"),
                                user_lat=u_lat, user_lon=u_lon, user_hdg=u_hdg, user_gs=u_gs, user_on_ground=u_og,
                                gate_hdg=arr.get("heading"), no_pushback=arr.get("no_pushback", False),
                                atc_taxi_via=arr.get("atc_taxi_via")
                            )
                            if arr["taxi_route"] and arr["taxi_route"].get("runway_id"):
                                arr["selected_runway"] = arr["taxi_route"]["runway_id"]
                            self.current_flight_data["arrival"]["taxi_route"] = arr["taxi_route"]
                            self.current_flight_data["arrival"]["selected_runway"] = arr.get("selected_runway")
                            self._last_arr_route_pos = (u_lat, u_lon)
                            self._last_arr_route_key = cur_key
                            self._save_session_state()
                        fd["recommended_phase"] = "arrival"
                    elif u_og is False and (d_dep > 1800.0 or (u_gs or 0.0) > 65.0):
                        # In-flight / Enroute / Approach -> automatically recommend Arrival phase
                        fd["recommended_phase"] = "arrival"
                if hasattr(self, "interop_hub") and self.interop_hub:
                    self.interop_hub.check_vatsim_arrival_refresh(
                        d_arr_m=d_arr if d_arr != float('inf') else None,
                        is_airborne=is_airborne
                    )
                    self.interop_hub.check_arrival_gsx_auto_trigger(
                        d_arr_m=d_arr if d_arr != float('inf') else None,
                        on_ground=u_og,
                        gs_kt=u_gs,
                        in_menu=in_menu,
                        sc_connected=sc_conn
                    )
                    arr["gsx_status"] = self.interop_hub.get_arrival_gsx_status()
                fd["arrival"] = arr
        if hasattr(self, "interop_hub") and self.interop_hub:
            if "arrival" in fd and fd["arrival"] and "gsx_status" not in fd["arrival"]:
                arr_copy = dict(fd["arrival"])
                arr_copy["gsx_status"] = self.interop_hub.get_arrival_gsx_status()
                fd["arrival"] = arr_copy
            fd["interop_hub"] = self.interop_hub.get_hub_status_payload()
        for _ph_k in ("departure", "arrival"):
            _apt_d = fd.get(_ph_k)
            if isinstance(_apt_d, dict) and not _apt_d.get("city") and _apt_d.get("icao"):
                _apt_d["city"] = self.get_airport_city(_apt_d["icao"], lat=_apt_d.get("lat"), lon=_apt_d.get("lon"))
        fd["pending_live_stand_prompt"] = getattr(self, "pending_live_stand_prompt", None)
        al_code_cam = fd.get("airline_code") or (fd.get("departure") or {}).get("airline_code") or ""
        if not al_code_cam and fd.get("airline"):
            raw_al_s = str(fd["airline"])
            al_code_cam = raw_al_s.split("-")[0].strip().upper() if "-" in raw_al_s else raw_al_s.strip().upper()[:3]
        if fd.get("aircraft_version") and "•" in str(fd["aircraft_version"]):
            fd["aircraft_version"] = re.sub(r"\s*•\s*", " - ", str(fd["aircraft_version"]))
        fd["camaieu_palette"] = self.get_airline_camaieu_palette(al_code_cam)
        fd["app_version"] = "2.0.4"
        return fd

    def scan_gsx_profiles(self):
        gsx_path = self.config.settings.get("gsx_profile_path", "")
        if not gsx_path or not os.path.exists(gsx_path):
            return {"supported": [], "unknown": []}
            
        shared_contributions = set(self.config.settings.get("shared_contributions", []))
        supported = set()
        unknown = set()
        for filename in os.listdir(gsx_path):
            if filename.lower().endswith('.ini'):
                if filename in shared_contributions:
                    continue
                icao = extract_icao_from_filename(filename)
                if not icao:
                    continue
                if icao in self.cloud_ruleset:
                    supported.add(icao)
                else:
                    # Quick check if it's a valid GSX profile with airlines
                    filepath = os.path.join(gsx_path, filename)
                    has_airlines = False
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            if re.search(r'airline_?codes[ \t]*=[ \t]*[a-z0-9]', content):
                                has_airlines = True
                    except Exception:
                        pass
                        
                    if has_airlines:
                        unknown.add(filename)
                    
        return {"supported": sorted(list(supported)), "unknown": sorted(list(unknown))}

    def generate_contribution_file(self, unknown_filenames):
        """Generates a JSON file containing the extracted data from unknown airports to contribute"""
        data_to_contribute = {}
        gsx_path = self.config.settings.get("gsx_profile_path", "")
        
        for filename in unknown_filenames:
            # Use the filename (without .ini) to avoid collisions like GSX-EHAM.ini and GSX-LFPG.ini
            file_key = filename[:-4] if filename.lower().endswith('.ini') else filename
            filepath = os.path.join(gsx_path, filename)
            
            try:
                parser = configparser.ConfigParser(interpolation=None)
                try:
                    parser.read(filepath, encoding='utf-8')
                except UnicodeDecodeError:
                    parser.read(filepath, encoding='cp1252')
            except Exception:
                continue
                
            airport_data = {}
            for section in parser.sections():
                sec_lower = section.lower()
                if sec_lower.startswith(('parking', 'gate', 'stand', 'ramp', 'dock')):
                    prefix = ""
                    for p in ('parking_', 'parking ', 'gate_', 'gate ', 'stand_', 'stand ', 'ramp_', 'ramp ', 'dock_', 'dock '):
                        if sec_lower.startswith(p):
                            prefix = p
                            break
                    
                    if prefix:
                        name = section[len(prefix):].replace('_', ' ').upper()
                    else:
                        name = section.replace('_', ' ').upper()
                        
                    airlines = []
                    if 'airlinecodes' in parser[section]:
                        airlines = [a.strip().upper() for a in parser[section]['airlinecodes'].split(',') if a.strip()]
                    elif 'airline_codes' in parser[section]:
                        airlines = [a.strip().upper() for a in parser[section]['airline_codes'].split(',') if a.strip()]
                        
                    if airlines:
                        airport_data[name] = airlines
            
            if airport_data:
                data_to_contribute[file_key] = airport_data
                
        if not data_to_contribute:
            return None
            
        import sys
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.abspath(".")
            
        out_path = os.path.join(app_dir, "GateFinder_Contribution.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data_to_contribute, f, indent=2)
            
        return out_path

    def uninstall_app(self, extra_community_paths=None):
        """Thoroughly uninstalls the GateFinder Community package across all MSFS installations and cleans up autostart."""
        import shutil
        from autostart import AutoStartManager
        from config import find_all_possible_community_folders
        
        # 1. Disable autostart across all exe.xml files
        autostart_ok = False
        try:
            asm = AutoStartManager()
            autostart_ok = asm.disable()
            print("[Uninstall] Auto-start entry disabled/removed successfully.")
        except Exception as e:
            print(f"[Uninstall] Error disabling autostart: {e}")
            
        # 2. Gather all community folders to scan and clean
        searched_folders = set()

        def add_candidate(folder):
            if folder and isinstance(folder, str):
                norm = os.path.normpath(folder.strip())
                if os.path.exists(norm) and os.path.isdir(norm):
                    searched_folders.add(norm)

        # Configured paths
        add_candidate(self.config.settings.get("msfs_community_path", ""))
        add_candidate(self.config.settings.get("msfs_community2024_path", ""))

        # Extra paths passed in from GUI input fields
        if extra_community_paths:
            for p in extra_community_paths:
                add_candidate(p)

        # Auto-detected paths from UserCfg.opt and fallback locations
        for p in find_all_possible_community_folders():
            add_candidate(p)

        # Also inspect parent folder of any Community directory for sibling Community folders (e.g. Community2024)
        for cf in list(searched_folders):
            parent = os.path.dirname(cf)
            if parent and os.path.exists(parent):
                for sibling in ["Community", "Community2024", "Community2020"]:
                    sib_p = os.path.join(parent, sibling)
                    add_candidate(sib_p)

        removed_paths = []
        failed_paths = []

        # 3. Check and remove package (both V2.0 'gatefinder-ingame-panel' and legacy 'wildbill75-gatefinder') in every candidate Community folder
        for comm_dir in searched_folders:
            for pkg_folder_name in ("gatefinder-ingame-panel", "wildbill75-gatefinder", "gsx-gatefinder"):
                package_path = os.path.join(comm_dir, pkg_folder_name)
                if os.path.exists(package_path) or os.path.islink(package_path):
                    try:
                        if os.path.islink(package_path):
                            os.unlink(package_path)
                        elif os.path.isdir(package_path):
                            try:
                                os.rmdir(package_path)
                            except OSError:
                                shutil.rmtree(package_path)
                        else:
                            os.remove(package_path)

                        removed_paths.append(package_path)
                        print(f"[Uninstall] Successfully removed package: {package_path}")
                    except Exception as e:
                        failed_paths.append((package_path, str(e)))
                        print(f"[Uninstall] Error removing {package_path}: {e}")

        success = (len(failed_paths) == 0)
        return {
            "success": success,
            "removed_paths": removed_paths,
            "failed_paths": failed_paths,
            "autostart_disabled": autostart_ok,
            "searched_folders": sorted(list(searched_folders))
        }

    def get_local_lan_ip(self) -> str:
        import socket
        candidate_ips = []
        try:
            _, _, host_ips = socket.gethostbyname_ex(socket.gethostname())
            for hip in (host_ips or []):
                if hip and not hip.startswith("127.") and not hip.startswith("169.254."):
                    candidate_ips.append(hip)
        except Exception:
            pass
        routed_ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                    routed_ip = ip
            finally:
                s.close()
        except Exception:
            pass
        # If the default internet route goes through a VPN tunnel (e.g. ProtonVPN 10.2.x.x or Tailscale 100.x.x.x),
        # prefer the PC's physical 192.168.x.x Wi-Fi / Ethernet LAN address so tablets/phones on home Wi-Fi can connect!
        if routed_ip and routed_ip.startswith("192.168."):
            return routed_ip
        for cip in candidate_ips:
            if cip.startswith("192.168."):
                return cip
        if routed_ip:
            return routed_ip
        if candidate_ips:
            return candidate_ips[0]
        return "127.0.0.1"

    def get_web_efb_url(self) -> str:
        return f"http://{self.get_local_lan_ip()}:8420/"

    def _get_panel_asset_dir(self) -> str:
        rel_p = os.path.join("MSFS_Package", "gatefinder-ingame-panel", "html_ui", "ingamePanels", "GateFinderPanel")
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            cand_ext = os.path.join(exe_dir, rel_p)
            if os.path.isdir(cand_ext):
                return cand_ext
            if hasattr(sys, "_MEIPASS"):
                cand_mei = os.path.join(sys._MEIPASS, rel_p)
                if os.path.isdir(cand_mei):
                    return cand_mei
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", rel_p))

    def start_server(self):
        class APIHandler(http.server.SimpleHTTPRequestHandler):
            backend_instance = self
            
            def log_message(self, format, *args):
                pass
                
            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', '*')
                if not getattr(self, '_custom_cache_control', False):
                    self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Expires', '0')
                ctype = getattr(self, '_custom_content_type', 'application/json')
                self.send_header('Content-type', ctype)
                super().end_headers()

            def do_OPTIONS(self):
                self.send_response(200)
                self.end_headers()

            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path in ('/', '/index.html', '/efb', '/phone', '/tablet'):
                    web_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="mobile-web-app-capable" content="yes" />
    <title>GateFinder V2.0.4 - Live Web EFB</title>
    <link rel="stylesheet" href="/GateFinderPanel.css?v=44" />
    <style>
        html, body {
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
            height: 100dvh;
            background-color: #121418;
            color: #ffffff;
            font-family: 'Segoe UI', 'Open Sans', sans-serif;
            overflow: hidden;
            -webkit-tap-highlight-color: transparent;
        }
        gsx-gatefinder-panel {
            border-radius: 0 !important;
            padding: 10px 14px !important;
            width: 100vw !important;
            height: 100vh !important;
            height: 100dvh !important;
            background-color: #121418 !important;
            box-sizing: border-box !important;
        }
        ingame-ui, #MainDisplay, #EFBContainer {
            display: flex !important;
            flex-direction: column !important;
            width: 100% !important;
            height: 100% !important;
            min-height: 0 !important;
            flex: 1 1 auto !important;
        }
        #EFBContainer.hidden, #StatusMessage.hidden, .hidden {
            display: none !important;
        }
        .header-right-actions {
            display: flex;
            align-items: center;
            gap: 6px;
            flex-shrink: 0;
        }
        .env-switcher {
            display: inline-flex;
            align-items: center;
            background-color: #12151B;
            border: 1px solid #2B303B;
            border-radius: 7px;
            padding: 2px;
            flex-shrink: 0;
        }
        .env-btn {
            padding: 5px 10px;
            font-size: 11.5px;
            font-weight: 700;
            color: #94A3B8;
            border-radius: 5px;
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }
        .env-btn.active {
            background-color: #2B303B;
            color: #FFFFFF;
        }
        #WebImportBtn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            height: 38px;
            padding: 0 16px;
            background-color: #0A86C2;
            color: #ffffff;
            font-weight: 700;
            font-size: 13px;
            border-radius: 8px;
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
            flex-shrink: 0;
        }
        #WebImportBtn:hover {
            background-color: #0284C7;
        }
        #MobileHudBar {
            display: none;
        }
        #MobileDrawerCloseBar {
            display: none;
        }

        /* =========================================================
           ENVIRONMENT 1: TABLET EFB MODE (iPad / Android Tablet)
           ========================================================= */
        body.env-tablet gsx-gatefinder-panel {
            padding: 6px 8px !important;
        }
        body.env-tablet .top-bar {
            margin-bottom: 6px !important;
        }
        body.env-tablet .header-row {
            min-height: 46px !important;
            padding: 6px 10px !important;
            margin-bottom: 6px !important;
        }
        body.env-tablet #al_logo_wide {
            width: 68px !important;
            height: 30px !important;
            margin-right: 6px !important;
        }
        body.env-tablet .pill-badge {
            min-height: 30px !important;
            height: 30px !important;
            padding: 0 11px !important;
            font-size: 12px !important;
            margin-right: 6px !important;
        }
        body.env-tablet #WebImportBtn {
            height: 30px !important;
            padding: 0 12px !important;
            font-size: 12px !important;
        }
        body.env-tablet .phase-card {
            min-height: 42px !important;
            padding: 6px 10px !important;
        }
        body.env-tablet .phase-card span {
            min-height: 26px !important;
            height: 26px !important;
            min-width: 44px !important;
            padding: 0 10px !important;
            font-size: 12px !important;
            margin-right: 5px !important;
        }
        body.env-tablet .phase-card span:first-child {
            background: transparent !important;
            padding: 0 !important;
            min-width: 0 !important;
            font-size: 12.5px !important;
            margin-right: 8px !important;
        }
        body.env-tablet .left-sidebar {
            width: 268px;
            min-width: 222px;
            max-width: 65%;
            margin-right: 0 !important;
            -webkit-overflow-scrolling: touch;
        }
        body.env-phone .sidebar-splitter {
            display: none !important;
        }
        body.env-tablet .chart-top-bar {
            min-height: 40px !important;
            padding: 4px 8px !important;
        }
        body.env-tablet #sc_val {
            height: 28px !important;
            padding: 0 10px !important;
            font-size: 11px !important;
        }
        body.env-tablet .chart-btn {
            height: 30px !important;
            padding: 0 10px !important;
            font-size: 11.5px !important;
        }

        /* =========================================================
           ENVIRONMENT 2: SMARTPHONE EFB MODE (iPhone / Android Phone)
           ========================================================= */
        body.env-phone gsx-gatefinder-panel {
            padding: 4px 5px !important;
        }
        body.env-phone .top-bar {
            margin-bottom: 4px !important;
        }
        body.env-phone .header-row {
            min-height: 36px !important;
            padding: 4px 7px !important;
            margin-bottom: 4px !important;
            border-radius: 8px !important;
            flex-wrap: nowrap !important;
        }
        body.env-phone .flight-pills {
            flex-wrap: nowrap !important;
            overflow: hidden !important;
            min-width: 0 !important;
        }
        body.env-phone #al_logo_wide {
            width: 48px !important;
            height: 22px !important;
            margin-right: 5px !important;
            border-radius: 4px !important;
        }
        body.env-phone #reg_val,
        body.env-phone #ac_val {
            display: none !important;
        }
        body.env-phone .pill-badge {
            min-height: 24px !important;
            height: 24px !important;
            padding: 0 8px !important;
            font-size: 11px !important;
            margin-right: 4px !important;
            border-radius: 5px !important;
        }
        body.env-phone .env-btn {
            padding: 3px 7px !important;
            font-size: 10.5px !important;
        }
        body.env-phone #WebImportBtn {
            height: 24px !important;
            padding: 0 8px !important;
            font-size: 10.5px !important;
            border-radius: 5px !important;
        }
        body.env-phone .phase-tabs-row {
            gap: 4px !important;
        }
        body.env-phone #TabDep {
            margin-right: 0 !important;
        }
        body.env-phone .phase-card {
            min-height: 32px !important;
            padding: 4px 6px !important;
            border-radius: 8px !important;
        }
        body.env-phone .phase-card span {
            min-height: 21px !important;
            height: 21px !important;
            min-width: 0 !important;
            padding: 0 6px !important;
            font-size: 10.5px !important;
            margin-right: 3px !important;
            border-radius: 5px !important;
        }
        body.env-phone .phase-card span:first-child {
            display: none !important;
        }
        body.env-phone #MobileHudBar {
            display: flex !important;
            align-items: center;
            justify-content: space-between;
            background-color: #1B1E24;
            border-radius: 8px;
            padding: 5px 8px;
            margin-bottom: 4px;
            gap: 6px;
            flex-shrink: 0;
        }
        .mob-hud-route {
            display: flex;
            align-items: center;
            gap: 4px;
            overflow-x: auto;
            white-space: nowrap;
            flex: 1 1 auto;
            min-width: 0;
            scrollbar-width: none;
        }
        .mob-hud-route::-webkit-scrollbar {
            display: none;
        }
        .mob-hud-pill {
            display: inline-flex;
            align-items: center;
            height: 24px;
            padding: 0 8px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 700;
            color: #ffffff;
            background-color: #2B303B;
            flex-shrink: 0;
        }
        #BtnMobileDrawerToggle {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            height: 26px;
            padding: 0 10px;
            border-radius: 6px;
            background-color: #25343D;
            border: 1px solid #38BDF8;
            color: #38BDF8;
            font-size: 11px;
            font-weight: 700;
            cursor: pointer;
            user-select: none;
            flex-shrink: 0;
        }
        body.env-phone .workspace-area {
            position: relative !important;
            flex-direction: column !important;
        }
        body.env-phone:not(.phone-drawer-open) .left-sidebar {
            display: none !important;
        }
        body.env-phone.phone-drawer-open .left-sidebar {
            display: flex !important;
            width: 100% !important;
            min-width: 100% !important;
            max-width: 100% !important;
            height: 100% !important;
            margin-right: 0 !important;
            z-index: 60 !important;
            -webkit-overflow-scrolling: touch;
        }
        body.env-phone.phone-drawer-open .right-chart-pane {
            display: none !important;
        }
        body.env-phone.phone-drawer-open #MobileDrawerCloseBar {
            display: flex !important;
            align-items: center;
            justify-content: space-between;
            background-color: #132235;
            border: 1px solid #0284C7;
            border-radius: 8px;
            padding: 8px 12px;
            margin-bottom: 6px;
            cursor: pointer;
            flex-shrink: 0;
        }
        body.env-phone .chart-top-bar {
            min-height: 34px !important;
            padding: 3px 6px !important;
            justify-content: center !important;
        }
        body.env-phone .chart-top-left,
        body.env-phone #sc_val {
            display: none !important;
        }
        body.env-phone .chart-toolbar {
            width: 100% !important;
            justify-content: space-between !important;
        }
        body.env-phone .chart-btn {
            height: 26px !important;
            padding: 0 7px !important;
            font-size: 11px !important;
            margin-left: 3px !important;
            flex: 1 1 auto !important;
            text-align: center !important;
        }
        body.env-phone .chart-footer-hint {
            display: none !important;
        }
    </style>
    <script type="text/javascript" src="/GateFinderPanel.js?v=44"></script>
</head>
<body class="border-box color-white">
    <gsx-gatefinder-panel>
        <ingame-ui id="GSX_GateFinder" panel-id="PANEL_GATEFINDER" title="GATEFINDER V2.0.4">
            <div id="MainDisplay">
                <div id="StatusMessage" class="status-message-box">
                    <h2 id="StatusTitle" class="status-title">Awaiting Flight Data</h2>
                    <p id="StatusText" class="status-text">Click <strong>Import SimBrief</strong> or load a flight in the <strong>GateFinder</strong> desktop application on your MSFS PC.</p>
                    <div style="margin-top:14px;">
                        <span id="BtnStatusImport" style="display:inline-block;background:#0A86C2;color:#ffffff;font-weight:700;font-size:14px;padding:10px 24px;border-radius:8px;cursor:pointer;">Import SimBrief</span>
                    </div>
                </div>

                <div id="EFBContainer" class="efb-container hidden">
                    <div class="top-bar">
                        <div id="HeaderCard" class="header-row">
                            <div class="flight-pills">
                                <img id="al_logo_wide" class="airline-wide-logo hidden" alt="" />
                                <span id="al_val" class="pill-badge"></span>
                                <span id="cs_val" class="pill-badge hidden"></span>
                                <span id="reg_val" class="pill-badge hidden"></span>
                                <span id="ac_val" class="pill-badge"></span>
                            </div>
                            <div class="header-right-actions">
                                <div id="EnvSwitcher" class="env-switcher" title="Switch display environment (Phone / Tablet / PC)">
                                    <span class="env-btn" data-env="phone">Phone</span>
                                    <span class="env-btn" data-env="tablet">Tablet</span>
                                    <span class="env-btn" data-env="pc">PC</span>
                                </div>
                                <div id="WebImportBtn" title="Import latest SimBrief OFP">SimBrief</div>
                            </div>
                        </div>
                        <div class="phase-tabs-row">
                            <div id="TabDep" class="phase-card active"></div>
                            <div id="TabArr" class="phase-card"></div>
                        </div>
                    </div>

                    <div id="MobileHudBar">
                        <div id="MobileHudRoute" class="mob-hud-route"></div>
                        <div id="BtnMobileDrawerToggle">Gates &amp; ATC</div>
                    </div>

                    <div id="MobileDrawerCloseBar">
                        <span style="font-size:12px;font-weight:700;color:#38BDF8;">STAND, RUNWAY &amp; ATC SELECTION</span>
                        <span style="font-size:12px;font-weight:700;color:#FFFFFF;background:#0284C7;padding:3px 10px;border-radius:5px;">Back to Map &#10005;</span>
                    </div>

                    <div id="WorkspaceArea" class="workspace-area">
                        <div id="LeftSidebar" class="left-sidebar"></div>
                        <div id="RightChartPane" class="right-chart-pane">
                            <div id="MapTopBar" class="chart-top-bar">
                                <div class="chart-top-left">
                                    <span id="sc_val" class="sc-status-pill">SimConnect Standby</span>
                                </div>
                                <div class="chart-toolbar">
                                    <div id="BtnZoomIn" class="chart-btn" title="Zoom In">+</div>
                                    <div id="BtnZoomOut" class="chart-btn" title="Zoom Out">-</div>
                                    <div id="BtnAPC" class="chart-btn" title="Zooms in on the assigned stand and terminal apron">Gate</div>
                                    <div id="BtnAGC" class="chart-btn active" title="Zooms to fit the entire taxi route between stand and runway">Route</div>
                                    <div id="BtnFollow" class="chart-btn" title="Follow live aircraft position with Heading-Up orientation">Follow + Hdg Up</div>
                                    <div id="BtnTheme" class="chart-btn" title="Toggle Map Day / Map Night theme">Map Day</div>
                                </div>
                            </div>
                            <div id="ChartWrapper" class="chart-wrapper">
                                <canvas id="LidoCanvas"></canvas>
                                <div id="DragHandBadge" class="drag-hand-badge hidden">
                                    <svg width="24" height="24" viewBox="-12 -12 24 24">
                                        <path d="M-6,2 L-8,-2 Q-8,-5 -5.5,-4 L-5,-1 L-5,-7 Q-5,-9.5 -2.5,-9.5 Q-1,-9.5 -1,-7 L-1,-1 L-1,-8 Q-1,-10.5 1.2,-10.5 Q3,-10.5 3,-8 L3,-1 L3,-7 Q3,-9.2 5,-9.2 Q6.8,-9.2 6.8,-7 L6.8,-1 L6.8,-5 Q6.8,-7 8.5,-7 Q10,-7 10,-4.5 L10,3 Q10,9 3,9 L-2,9 Q-6,9 -6,2 Z" fill="#f8fafc" stroke="#0f172a" stroke-width="1.2" stroke-linejoin="round" stroke-linecap="round"/>
                                    </svg>
                                </div>
                                <div class="chart-footer-hint">Scroll/Pinch: Zoom  |  Drag: Pan  |  Lido Vector</div>
                            </div>
                        </div>
                    </div>

                    <div id="AtcRunwayModal" class="atc-modal-overlay hidden">
                        <div class="atc-modal-card">
                            <div id="AtcModalHeader" class="atc-modal-header">ATC CLEARANCE ACTIVE</div>
                            <div id="AtcModalText" class="atc-modal-text"></div>
                            <div class="atc-modal-actions">
                                <div id="BtnAtcModalKeep" class="atc-modal-btn keep">Keep ATC Runway</div>
                                <div id="BtnAtcModalOverride" class="atc-modal-btn override">Override Runway</div>
                            </div>
                        </div>
                    </div>

                    <div id="LiveStandModal" class="atc-modal-overlay hidden">
                        <div class="atc-modal-card" style="border-color: #10b981;">
                            <div id="LiveStandModalHeader" class="atc-modal-header" style="color: #10b981;">MSFS LIVE STAND DETECTED</div>
                            <div id="LiveStandModalText" class="atc-modal-text"></div>
                            <div class="atc-modal-actions">
                                <div id="BtnLiveStandKeep" class="atc-modal-btn keep" style="background-color: #10b981;">Keep MSFS Stand</div>
                                <div id="BtnLiveStandStay" class="atc-modal-btn override" style="background-color: #374151;">Stay on Stand</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </ingame-ui>
    </gsx-gatefinder-panel>
    <script>
        (function() {
            let manualEnv = null;
            function detectBestEnv() {
                if (window.location.pathname === "/phone") return "phone";
                if (window.location.pathname === "/tablet") return "tablet";
                let params = new URLSearchParams(window.location.search);
                if (params.get("env")) return params.get("env").toLowerCase();
                if (manualEnv) return manualEnv;
                let w = window.innerWidth || document.documentElement.clientWidth || 1024;
                let h = window.innerHeight || document.documentElement.clientHeight || 768;
                let minDim = Math.min(w, h);
                let maxDim = Math.max(w, h);
                if (minDim < 540 || w < 660) return "phone";
                if (maxDim <= 1366 && w <= 1220) return "tablet";
                return "pc";
            }

            function applyEnvMode(mode) {
                document.body.classList.remove("env-phone", "env-tablet", "env-pc");
                if (mode !== "phone") {
                    document.body.classList.remove("phone-drawer-open");
                }
                document.body.classList.add("env-" + mode);
                let btns = document.querySelectorAll("#EnvSwitcher .env-btn");
                btns.forEach(function(b) {
                    if (b.getAttribute("data-env") === mode) b.classList.add("active");
                    else b.classList.remove("active");
                });
                let btnFollow = document.getElementById("BtnFollow");
                if (btnFollow) {
                    btnFollow.innerText = (mode === "phone") ? "Follow" : "Follow + Hdg Up";
                }
                let btnTheme = document.getElementById("BtnTheme");
                if (btnTheme && mode === "phone") {
                    let p = document.querySelector("gsx-gatefinder-panel");
                    btnTheme.innerText = (p && p.themeMode === "day") ? "Night" : "Day";
                }
                setTimeout(function() {
                    let panel = document.querySelector("gsx-gatefinder-panel");
                    if (panel && panel.updateCanvasMetrics) {
                        panel.updateCanvasMetrics();
                        panel.lastBaseKey = "";
                        panel.drawChart();
                    }
                }, 60);
            }

            function syncMobileHud() {
                let panel = document.querySelector("gsx-gatefinder-panel");
                let hudRoute = document.getElementById("MobileHudRoute");
                if (!panel || !panel.currentData || !hudRoute) return;
                let d = panel.currentData;
                let cam = panel.getCamaieu ? panel.getCamaieu(d) : { s1: "#578DA8", s2: "#517B90", s3: "#4A6C7D" };
                let apt = d[panel.activePhase || "departure"] || {};
                let tr = apt.taxi_route || {};
                let standTxt = apt.gate ? ("STAND " + apt.gate) : "NO STAND";
                let rwyTxt = apt.selected_runway ? ("RWY " + apt.selected_runway) : "RWY --";
                let html = '<span class="mob-hud-pill" style="background:' + cam.s1 + ';">' + standTxt + '</span>';
                html += '<span class="mob-hud-pill" style="background:' + cam.s2 + ';">' + rwyTxt + '</span>';
                let twys = tr.taxiways || [];
                if (twys.length > 0) {
                    for (let i = 0; i < twys.length; i++) {
                        html += '<span class="mob-hud-pill" style="background:#2B303B;">' + twys[i] + '</span>';
                    }
                } else if (apt.gate_source) {
                    html += '<span class="mob-hud-pill" style="background:#2B303B;">' + apt.gate_source + '</span>';
                }
                if (hudRoute.getAttribute("data-last") !== html) {
                    hudRoute.setAttribute("data-last", html);
                    hudRoute.innerHTML = html;
                }
            }

            function triggerImport(btn) {
                if (!btn || btn.getAttribute("data-busy") === "1") return;
                let orig = btn.innerText;
                btn.setAttribute("data-busy", "1");
                btn.innerText = "...";
                fetch("/api/simbrief")
                    .then(r => r.json())
                    .then(() => {
                        btn.removeAttribute("data-busy");
                        btn.innerText = orig;
                        let panel = document.querySelector("gsx-gatefinder-panel");
                        if (panel && panel.fetchCurrentData) panel.fetchCurrentData();
                    })
                    .catch(() => {
                        btn.removeAttribute("data-busy");
                        btn.innerText = orig;
                    });
            }

            window.addEventListener("DOMContentLoaded", function() {
                applyEnvMode(detectBestEnv());
                window.addEventListener("resize", function() {
                    if (!manualEnv) applyEnvMode(detectBestEnv());
                });
                let btns = document.querySelectorAll("#EnvSwitcher .env-btn");
                btns.forEach(function(b) {
                    b.addEventListener("click", function() {
                        manualEnv = b.getAttribute("data-env");
                        applyEnvMode(manualEnv);
                    });
                });
                let drawerBtn = document.getElementById("BtnMobileDrawerToggle");
                let closeBar = document.getElementById("MobileDrawerCloseBar");
                let hudRoute = document.getElementById("MobileHudRoute");
                function toggleDrawer(forceState) {
                    let isOpen = document.body.classList.contains("phone-drawer-open");
                    let next = (forceState !== undefined) ? forceState : !isOpen;
                    if (next) document.body.classList.add("phone-drawer-open");
                    else document.body.classList.remove("phone-drawer-open");
                    if (drawerBtn) drawerBtn.innerText = next ? "Show Map" : "Gates & ATC";
                    if (!next) {
                        setTimeout(function() {
                            let panel = document.querySelector("gsx-gatefinder-panel");
                            if (panel && panel.updateCanvasMetrics) {
                                panel.updateCanvasMetrics();
                                panel.lastBaseKey = "";
                                panel.drawChart();
                            }
                        }, 50);
                    }
                }
                if (drawerBtn) drawerBtn.addEventListener("click", function() { toggleDrawer(); });
                if (closeBar) closeBar.addEventListener("click", function() { toggleDrawer(false); });
                if (hudRoute) hudRoute.addEventListener("click", function() { toggleDrawer(true); });

                let b1 = document.getElementById("WebImportBtn");
                let b2 = document.getElementById("BtnStatusImport");
                if (b1) b1.addEventListener("click", function() { triggerImport(b1); });
                if (b2) b2.addEventListener("click", function() { triggerImport(b2); });

                setInterval(syncMobileHud, 600);
            });
        })();
    </script>
</body>
</html>"""
                    self._custom_content_type = 'text/html; charset=utf-8'
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(web_html.encode('utf-8'))
                    return

                if parsed.path in ('/GateFinderPanel.js', '/GateFinderPanel.css', '/GateFinderEfbFrame.html', '/GateFinderFenixFrame.html', '/fenix_efb'):
                    asset_dir = APIHandler.backend_instance._get_panel_asset_dir()
                    fname = 'GateFinderEfbFrame.html' if parsed.path == '/fenix_efb' else parsed.path.lstrip('/')
                    fpath = os.path.join(asset_dir, fname)
                    if os.path.isfile(fpath):
                        self._custom_content_type = (
                            'application/javascript; charset=utf-8'
                            if fname.endswith('.js')
                            else ('text/html; charset=utf-8' if fname.endswith('.html') else 'text/css; charset=utf-8')
                        )
                        self.send_response(200)
                        self.end_headers()
                        with open(fpath, 'rb') as f:
                            raw_bytes = f.read()
                        if fname.endswith('.html'):
                            ts_b = str(int(time.time())).encode('ascii')
                            raw_bytes = raw_bytes.replace(b'?v=204', b'?v=' + ts_b).replace(b'?v=203', b'?v=' + ts_b)
                        self.wfile.write(raw_bytes)
                        return

                if parsed.path == '/api/airline_logo':
                    query = parse_qs(parsed.query)
                    code = query.get('code', [''])[0].strip().upper()
                    try:
                        sz = int(query.get('size', ['24'])[0])
                    except Exception:
                        sz = 24
                    try:
                        w_arg = int(query.get('width', ['0'])[0]) or None
                    except Exception:
                        w_arg = None
                    try:
                        rad_arg = int(query.get('radius', ['0'])[0])
                    except Exception:
                        rad_arg = 0
                    png_bytes = APIHandler.backend_instance.get_airline_pill_png_bytes(
                        code, size=sz, allow_network=True, width=w_arg, corner_radius=rad_arg
                    )
                    self._custom_content_type = 'image/png'
                    self._custom_cache_control = True
                    self.send_response(200)
                    self.send_header('Cache-Control', 'public, max-age=86400')
                    self.end_headers()
                    self.wfile.write(png_bytes)
                    return

                if parsed.path == '/api/current':
                    query = parse_qs(parsed.query)
                    have_dep = query.get('have_dep', [''])[0].strip().upper()
                    have_arr = query.get('have_arr', [''])[0].strip().upper()
                    self.send_response(200)
                    self.end_headers()
                    fd = APIHandler.backend_instance.get_dynamic_flight_data()
                    if fd:
                        if have_dep and fd.get("departure") and fd["departure"].get("icao") == have_dep:
                            dep_copy = dict(fd["departure"])
                            dep_copy.pop("chart_data", None)
                            fd["departure"] = dep_copy
                        if have_arr and fd.get("arrival") and fd["arrival"].get("icao") == have_arr:
                            arr_copy = dict(fd["arrival"])
                            arr_copy.pop("chart_data", None)
                            fd["arrival"] = arr_copy
                    self.wfile.write(json.dumps(fd).encode())
                    return

                if parsed.path == '/api/show_window':
                    APIHandler.backend_instance.show_window_requested = True
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True}).encode())
                    return

                if parsed.path == '/api/set_runway':
                    query = parse_qs(parsed.query)
                    phase = query.get('phase', [''])[0].strip().lower()
                    rwy = query.get('rwy', [''])[0].strip().upper()
                    APIHandler.backend_instance.set_active_runway(phase, rwy)
                    self.send_response(200)
                    self.end_headers()
                    fd = APIHandler.backend_instance.get_dynamic_flight_data()
                    self.wfile.write(json.dumps(fd).encode())
                    return

                if parsed.path == '/api/set_gate':
                    query = parse_qs(parsed.query)
                    phase = query.get('phase', ['arrival'])[0].strip().lower()
                    gate = query.get('gate', [''])[0].strip().upper()
                    if gate and hasattr(APIHandler.backend_instance, "interop_hub") and APIHandler.backend_instance.interop_hub:
                        APIHandler.backend_instance.interop_hub.set_manual_gate(phase, gate)
                    self.send_response(200)
                    self.end_headers()
                    fd = APIHandler.backend_instance.get_dynamic_flight_data()
                    self.wfile.write(json.dumps(fd).encode())
                    return

                if parsed.path == '/api/reposition_aircraft':
                    query = parse_qs(parsed.query)
                    phase = query.get('phase', ['departure'])[0].strip().lower()
                    gate = query.get('gate', [''])[0].strip().upper()
                    if gate and hasattr(APIHandler.backend_instance, "interop_hub") and APIHandler.backend_instance.interop_hub:
                        APIHandler.backend_instance.interop_hub.reposition_aircraft_to_gate(phase, gate)
                    self.send_response(200)
                    self.end_headers()
                    fd = APIHandler.backend_instance.get_dynamic_flight_data()
                    self.wfile.write(json.dumps(fd).encode())
                    return

                if parsed.path == '/api/trigger_gsx':
                    query = parse_qs(parsed.query)
                    phase = query.get('phase', ['arrival'])[0].strip().lower()
                    if hasattr(APIHandler.backend_instance, "interop_hub") and APIHandler.backend_instance.interop_hub:
                        APIHandler.backend_instance.interop_hub.trigger_manual_gsx_sync(phase)
                    self.send_response(200)
                    self.end_headers()
                    fd = APIHandler.backend_instance.get_dynamic_flight_data()
                    self.wfile.write(json.dumps(fd).encode())
                    return

                if parsed.path == '/api/resolve_live_stand':
                    query = parse_qs(parsed.query)
                    action = query.get('action', ['keep_assigned'])[0].strip().lower()
                    APIHandler.backend_instance.resolve_live_stand_prompt(keep_live=(action == 'keep_live'))
                    self.send_response(200)
                    self.end_headers()
                    fd = APIHandler.backend_instance.get_dynamic_flight_data()
                    self.wfile.write(json.dumps(fd).encode())
                    return
                    
                if parsed.path == '/api/simbrief':
                    query = parse_qs(parsed.query)
                    username = query.get('username', [''])[0]
                    if not username:
                        username = APIHandler.backend_instance.config.settings.get("simbrief_username", "").strip()
                        
                    if not username:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": "No username provided"}).encode('utf-8'))
                        return
                        
                    try:
                        data = APIHandler.backend_instance.get_flight_data(username)
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(json.dumps(data).encode('utf-8'))
                    except Exception as e:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                    return

                if parsed.path == '/api/test_simbrief':
                    query = parse_qs(parsed.query)
                    username = query.get('username', [''])[0].strip()
                    if not username:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": "No username provided"}).encode('utf-8'))
                        return
                    
                    try:
                        import urllib.request
                        if username.isdigit():
                            url = f"https://www.simbrief.com/api/xml.fetcher.php?userid={username}&json=1"
                        else:
                            url = f"https://www.simbrief.com/api/xml.fetcher.php?username={username}&json=1"
                        
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
                        
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "status": "success",
                            "callsign": callsign,
                            "origin": origin,
                            "destination": destination
                        }).encode('utf-8'))
                    except Exception as e:
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            "status": "error",
                            "error": str(e)
                        }).encode('utf-8'))
                    return
                    
                self.send_response(404)
                self.end_headers()

        def run_server():
            class ThreadingSimpleServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
                allow_reuse_address = True
            try:
                with ThreadingSimpleServer(("0.0.0.0", 8420), APIHandler) as httpd:
                    httpd.serve_forever()
            except Exception:
                with ThreadingSimpleServer(("127.0.0.1", 8420), APIHandler) as httpd:
                    httpd.serve_forever()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
