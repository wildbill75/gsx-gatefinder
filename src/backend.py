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
import ctypes
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
    RECV_QUIT,
    SIMOBJECT_TYPE_AIRCRAFT,
    PERIOD_SIM_FRAME,
    PERIOD_SECOND,
    DATATYPE_FLOAT64,
    DATATYPE_INT32,
    DATATYPE_STRING256,
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
    'B77F': 64.8, 'A332F': 60.3, 'A333F': 60.3, 'B748F': 68.4, 'B744F': 64.4, 'B742F': 64.4, 'B74F': 64.4,
    'B738F': 34.3, 'B738BCF': 34.3, 'B737F': 34.3, 'B733F': 34.3, 'B734F': 34.3, 'B722F': 32.9, 'B722': 32.9,
    'B752F': 38.0, 'B763F': 47.6, 'B762F': 47.6, 'B76F': 47.6, 'MD11': 51.7, 'MD11F': 51.7,
    'A306': 44.8, 'A306F': 44.8, 'A310': 43.9, 'A310F': 43.9, 'A321F': 35.8, 'A320F': 35.8, 'A330F': 60.3,
    'AN124': 73.3, 'AN225': 88.4, 'AN22': 64.4, 'AN12': 38.0, 'AN26': 29.2, 'IL76': 50.5,
    'AT7F': 27.0, 'AT4F': 24.6, 'C208F': 15.9,
    # Military Transports, Tankers, AWACS & Maritime Patrol
    'A400': 42.4, 'A40M': 42.4, 'C17': 51.7, 'C130': 40.4, 'C30J': 40.4,
    'C5M': 67.9, 'C5': 67.9, 'C160': 40.0, 'C27J': 28.7, 'C295': 25.8, 'CN35': 25.8,
    'K35R': 39.9, 'KC46': 47.5, 'KC10': 50.4, 'MRTT': 60.3,
    'E3CF': 44.4, 'E3TF': 44.4, 'P8': 37.6, 'P3': 30.4, 'ATL2': 37.4, 'C2': 24.6, 'V22': 25.8,
    'B1': 41.8, 'B2': 52.4, 'B52': 56.4, 'VULC': 33.8, 'U2': 31.4, 'SR71': 16.9,
    # Military Fighters, Attack & Trainers
    'RFAL': 10.9, 'MIR2': 9.1, 'M2000': 9.1, 'F1': 8.4,
    'EUFI': 11.0, 'EF2K': 11.0, 'GRIP': 8.4, 'JAS39': 8.4, 'TOR': 13.9,
    'F14': 19.5, 'F15': 13.1, 'F16': 10.0, 'F18': 13.6, 'FA18': 13.6, 'F18H': 12.3, 'F18S': 13.6,
    'F22': 13.6, 'F35': 10.7, 'F4': 11.7, 'F5': 8.1, 'F86': 11.3, 'F104': 6.6, 'F117': 13.2,
    'A10': 17.5, 'AV8B': 9.2, 'HAWK': 9.9, 'T45': 9.4, 'T38': 7.7, 'T6': 10.2,
    'PC21': 9.1, 'PC9': 10.2, 'PC7': 10.4, 'M346': 9.7, 'L39': 9.5, 'AJET': 9.1,
    'SU27': 14.7, 'MIG29': 11.4,
    # General Aviation (Piston, Single/Twin Props & Turboprops)
    'C150': 10.2, 'C152': 10.2, 'C172': 11.0, 'C177': 10.8, 'C182': 11.0, 'C206': 10.9, 'C210': 11.2,
    'C208': 15.9, 'C310': 11.3, 'C337': 11.6, 'C340': 11.6, 'C400': 11.0, 'COL3': 11.0, 'COL4': 11.0,
    'C402': 13.5, 'C404': 14.1, 'C408': 17.3, 'C414': 13.5, 'C421': 12.5, 'C441': 15.1,
    'SR20': 11.7, 'SR22': 11.7, 'S22T': 11.7, 'T22T': 11.7, 'SF50': 11.8,
    'DA20': 10.9, 'DA40': 11.9, 'DA42': 13.4, 'DA50': 13.4, 'DA62': 14.6,
    'PA18': 10.7, 'P28A': 10.7, 'P28B': 10.7, 'P28R': 10.8, 'P28T': 10.8, 'P28U': 10.8,
    'PA24': 11.0, 'PA27': 11.3, 'PA30': 11.3, 'PA31': 12.4, 'PA32': 11.0, 'PA34': 11.9,
    'PA38': 10.4, 'PA44': 11.8, 'PA46': 13.1, 'P46T': 13.1,
    'M20P': 11.0, 'M20T': 11.0,
    'BE33': 10.2, 'BE35': 10.2, 'BE36': 10.2, 'B36T': 10.2, 'BE55': 11.5, 'BE58': 11.5,
    'BE60': 12.0, 'BE76': 11.6, 'BE9L': 15.3, 'BE9T': 14.0, 'BE10': 14.0, 'BE20': 16.6, 'B350': 17.7,
    'TBM7': 12.7, 'TBM8': 12.7, 'TBM9': 12.8,
    'PC6': 15.9, 'PC12': 16.3, 'KODI': 13.7, 'BN2P': 14.9,
    'DHC2': 14.6, 'DHC3': 17.7, 'DHC6': 19.8,
    'DR40': 8.7, 'TB20': 9.8, 'TB21': 9.8, 'VL3': 8.4, 'RV10': 9.7, 'RV14': 8.2,
    'P06T': 11.4, 'P212': 14.0, 'G21': 14.9, 'G44': 12.2,
    # Business Jets (Very Light, Light, Midsize, Super-Midsize, Ultra-Long-Range)
    'EA50': 11.6, 'C510': 13.2, 'HDJT': 12.1, 'PRM1': 13.6,
    'E50P': 12.3, 'E55P': 15.9,
    'C500': 14.4, 'C501': 14.4, 'C525': 14.3, 'C25A': 15.2, 'C25B': 16.3, 'C25C': 15.5, 'C25M': 14.4,
    'C550': 15.9, 'C560': 15.9, 'C56X': 17.0, 'C650': 16.3, 'C680': 19.3, 'C68A': 22.1, 'C700': 21.0, 'C750': 21.1,
    'PC24': 17.0,
    'LJ24': 10.9, 'LJ25': 10.9, 'LJ31': 13.4, 'LJ35': 12.0, 'LJ40': 14.6, 'LJ45': 14.6, 'LJ60': 13.3, 'LJ70': 15.5, 'LJ75': 15.5,
    'H25B': 15.7, 'HA4T': 18.8, 'GALX': 17.7, 'ASTR': 16.1, 'G150': 16.9, 'G280': 19.2,
    'CL30': 19.5, 'CL35': 21.0, 'CL60': 19.6, 'CRJ1': 21.2,
    'E545': 20.2, 'E550': 21.5, 'E35L': 21.2,
    'FA10': 13.1, 'FA20': 16.3, 'FA50': 18.9, 'F900': 19.3, 'F2TH': 21.4, 'FA6X': 25.9, 'FA7X': 26.2, 'FA8X': 26.3,
    'GL5T': 28.7, 'GLEX': 28.7, 'BD70': 28.7, 'GL7T': 31.7,
    'GLF2': 21.0, 'GLF3': 23.7, 'GLF4': 23.7, 'GLF5': 28.5, 'GLF6': 30.4,
    'GA5C': 26.3, 'GA6C': 28.7, 'GA7C': 30.4, 'GA8C': 30.4,
    'BBJ': 35.8, 'BBJ2': 35.8, 'ACJ': 35.8
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
    "A19N": {"A19N", "A319"}, "A319": {"A19N", "A319"},
    "A20N": {"A20N", "A320"}, "A320": {"A20N", "A320"},
    "A21N": {"A21N", "A321"}, "A321": {"A321", "A21N"},
    "B38M": {"B38M", "B738"}, "B738": {"B738", "B38M"},
    "B39M": {"B39M", "B739"}, "B739": {"B739", "B39M"},
}

GA_LIGHT_AIRCRAFT_TYPES = {
    "C150", "C152", "C172", "C177", "C182", "C206", "C210", "C208",
    "C310", "C337", "C340", "C400", "COL3", "COL4", "C402", "C404", "C408", "C414", "C421", "C441",
    "SR20", "SR22", "S22T", "T22T", "SF50",
    "DA20", "DA40", "DA42", "DA50", "DA62",
    "PA18", "P28A", "P28B", "P28R", "P28T", "P28U", "PA24", "PA27", "PA30",
    "PA31", "PA32", "PA34", "PA38", "PA44", "PA46", "P46T",
    "M20P", "M20T",
    "BE33", "BE35", "BE36", "B36T", "BE55", "BE58", "BE60", "BE76",
    "BE9L", "BE9T", "BE10", "BE20", "B350",
    "TBM7", "TBM8", "TBM9",
    "PC6", "PC12", "KODI", "BN2P", "DHC2", "DHC3", "DHC6",
    "DR40", "TB20", "TB21", "VL3", "RV10", "RV14", "P06T", "P212", "G21", "G44",
}

BUSINESS_JET_AIRCRAFT_TYPES = {
    "EA50", "C510", "HDJT", "PRM1", "E50P", "E55P",
    "C500", "C501", "C525", "C25A", "C25B", "C25C", "C25M", "C550", "C560",
    "C56X", "C650", "C680", "C68A", "C700", "C750",
    "PC24",
    "LJ24", "LJ25", "LJ31", "LJ35", "LJ40", "LJ45", "LJ60", "LJ70", "LJ75",
    "H25B", "HA4T", "GALX", "ASTR", "G150", "G280",
    "CL30", "CL35", "CL60", "CRJ1",
    "E545", "E550", "E35L",
    "FA10", "FA20", "FA50", "F900", "F2TH", "FA6X", "FA7X", "FA8X",
    "GL5T", "GLEX", "BD70", "GL7T",
    "GLF2", "GLF3", "GLF4", "GLF5", "GLF6",
    "GA5C", "GA6C", "GA7C", "GA8C",
    "BBJ", "BBJ2", "ACJ",
}

BUSINESS_AVIATION_OPERATORS = {
    "NJE", "EJA", "VJT", "FLX", "LXJ", "FJO", "AHO", "GJE", "XRO", "JFA",
    "VVG", "ARL", "OJT", "WUP", "TWY", "PEG", "XJC", "EJM", "SJE",
    "GA", "BIZ",
}

CARGO_AIRLINE_OPERATORS = {
    "FDX", "UPS", "DHL", "DHK", "BCS", "DHA", "DAE", "DHX",
    "CLX", "ICV", "GEC", "BOX", "GTI", "PAC", "CKS", "NCA",
    "ABX", "AJK", "SQC", "CCG", "CKK", "MPH", "CMA", "FPO",
    "ABR", "TAY", "CJT", "SWT", "SWN", "NPT", "AZG", "AZQ",
    "ICL", "CHG", "SRR", "RUN", "MNB", "WGN", "NCR", "AJT",
    "CSS", "HYT", "YZR", "UTP", "ACP", "BBD", "SRN", "IMX",
    "CFS", "MTN", "MAL", "NAC", "KFS", "LYC", "TUP", "VDA",
    "ADB", "CSG", "CAO", "SHQ", "CAR",
}

MILITARY_FIGHTER_TRAINER_TYPES = {
    "RFAL", "MIR2", "M2000", "F1", "EUFI", "EF2K", "GRIP", "JAS39", "TOR",
    "F14", "F15", "F16", "F18", "FA18", "F18H", "F18S", "F22", "F35",
    "F4", "F5", "F86", "F104", "F117", "A10", "AV8B", "HAWK", "T45",
    "T38", "T6", "PC21", "PC9", "PC7", "M346", "L39", "AJET", "SU27", "MIG29",
}

MILITARY_TRANSPORT_HEAVY_TYPES = {
    "A400", "A40M", "C17", "C130", "C30J", "C5M", "C5", "C160",
    "C27J", "C295", "CN35", "K35R", "KC46", "KC10", "MRTT",
    "E3CF", "E3TF", "P8", "P3", "ATL2", "C2", "V22",
    "B1", "B2", "B52", "VULC", "U2", "SR71",
}

MILITARY_OPERATORS = {
    "CTM", "FAF", "FNY", "FMN", "RCH", "RRR", "ASC", "GAF", "BAF",
    "NAF", "IAM", "AME", "SUI", "CFC", "ASY", "KIW", "PLF", "HAF",
    "CNV", "OAN", "MIL",
}

ATC_CALLSIGN_TO_ICAO_MAP = {
    # Cargo Telephony Callsigns -> ICAO
    "FEDEX": "FDX", "FEDERAL EXPRESS": "FDX",
    "UPS": "UPS", "UNITED PARCEL": "UPS",
    "DHL": "DHK", "WORLD EXPRESS": "DHK", "EUROTRANS": "BCS", "POSTMAN": "BCS",
    "CARGOLUX": "CLX", "CARGOLUX ITALIA": "ICV",
    "GERMAN CARGO": "GEC", "LUFTHANSA CARGO": "GEC",
    "AERO LOGIC": "BOX", "AEROLOGIC": "BOX", "BOX KAR": "BOX",
    "GIANT": "GTI", "ATLAS AIR": "GTI",
    "POLAR": "PAC", "POLAR AIR": "PAC",
    "CONNIE": "CKS", "KALITTA": "CKS",
    "NIPPON CARGO": "NCA",
    "ABEX": "ABX",
    "SINGCARGO": "SQC", "SINGAPORE CARGO": "SQC",
    "CHINA CARGO": "CKK",
    "MARTINAIR": "MPH",
    "CMA CGM": "CMA", "FRENCH CARGO": "CMA",
    "FRENCH POST": "FPO", "ASL FRANCE": "FPO",
    "CONTRACT": "ABR", "QUALITY": "TAY",
    "CARGOJET": "CJT",
    "SWIFTAIR": "SWT", "SWIFT": "SWT",
    "AIR SWEDEN": "SWN", "ATLANTIC": "NPT",
    "SILK WEST": "AZG", "SILK LINE": "AZQ",
    "CHALLENGE CARGO": "ICL", "CHALLENGE": "ICL",
    "WHITESTAR": "SRR", "STAR AIR": "SRR", "MAERSK CARGO": "SRR",
    "CARGO TURK": "RUN", "BLACK SEA": "MNB",
    "WESTERN GLOBAL": "WGN", "NATIONAL CARGO": "NCR", "AMERIJET": "AJT",
    "SHUN FENG": "CSS", "ANTONOV BUREAU": "ADB", "VOLGA": "VDA",
    # Military Telephony Callsigns -> ICAO
    "COTAM": "CTM", "FRENCH AIR FORCE": "FAF", "ARMEE DE L AIR": "FAF",
    "FRENCH NAVY": "FNY", "AERONAVALE": "FNY",
    "REACH": "RCH", "AIR MOBILITY": "RCH", "USAF": "RCH",
    "ASCOT": "RRR", "RAFAIR": "RRR", "ROYAL AIR FORCE": "RRR",
    "GERMAN AIR FORCE": "GAF", "LUFTWAFFE": "GAF",
    "BELGIAN AIR FORCE": "BAF", "NETHERLANDS AIR FORCE": "NAF",
    "ITALIAN AIR FORCE": "IAM", "AIR MIL": "AME", "SWISS AIR FORCE": "SUI",
    "CANFORCE": "CFC", "AUSSIE": "ASY", "KIWI": "KIW", "POLISH AIRFORCE": "PLF",
    "HELLENIC AIR FORCE": "HAF", "CONVOY": "CNV", "NAVY": "CNV", "NATO": "OAN",
    # Major Passenger Telephony Callsigns -> ICAO (Live MSFS fallback)
    "AIRFRANS": "AFR", "AIR FRANCE": "AFR",
    "SPEEDBIRD": "BAW", "BRITISH": "BAW",
    "LUFTHANSA": "DLH",
    "KLM": "KLM",
    "SWISS": "SWR",
    "AUSTRIAN": "AUA",
    "BEE LINE": "BEL", "BEELINE": "BEL", "BRUSSELS": "BEL",
    "EUROWINGS": "EWG",
    "EASY": "EZY", "EASYJET": "EZY", "ALPINE": "EJU", "TOPSWISS": "EZS",
    "RYANAIR": "RYR", "MAGIC SUN": "RYS",
    "TRANSAVIA": "TRA", "FRANCE SOLEIL": "TVF",
    "VUELING": "VLG", "VOLOTEA": "VOE",
    "IBERIA": "IBE", "AIR PORTUGAL": "TAP",
    "SCANDINAVIAN": "SAS", "FINNAIR": "FIN", "SHAMROCK": "EIN",
    "TURKISH": "THY", "SUNTURK": "PGT",
    "EMIRATES": "UAE", "QATARI": "QTR", "ETIHAD": "ETD",
    "AMERICAN": "AAL", "DELTA": "DAL", "UNITED": "UAL", "SOUTHWEST": "SWA",
    "JETBLUE": "JBU", "AIR CANADA": "ACA",
    "SINGAPORE": "SIA", "CATHAY": "CPA", "QANTAS": "QFA",
    "ALL NIPPON": "ANA", "JAPANAIR": "JAL", "KOREANAIR": "KAL",
    "CORSAIR": "CRL", "FRENCH BEE": "FBU", "FRENCH WEST": "FWI",
}


def resolve_airline_or_callsign_to_icao(raw_val):
    if not raw_val:
        return ""
    s = re.sub(r"\s+", " ", str(raw_val).strip().upper())
    if not s:
        return ""
    if s in ATC_CALLSIGN_TO_ICAO_MAP:
        return ATC_CALLSIGN_TO_ICAO_MAP[s]
    for k, v in ATC_CALLSIGN_TO_ICAO_MAP.items():
        if len(k) >= 5 and k in s:
            return v
    if len(s) in (3, 4) and s.isalpha():
        return normalize_airline_icao(s)
    return ""


def is_military_aircraft_or_flight(ac_icao, ac_name="", base_type="", airline_code="", callsign="", reg="", wingspan=36.0, sim_title=""):
    """
    Detects whether an aircraft or flight is Military (Fighter/Trainer or Heavy Military Transport/Tanker)
    based on aircraft ICAO, base type, name, operator, callsign, and MSFS livery title.
    """
    icao_u = str(ac_icao or "").strip().upper()
    base_u = str(base_type or "").strip().upper()
    name_u = str(ac_name or "").strip().upper()
    title_u = str(sim_title or "").strip().upper()
    al_u = normalize_airline_icao(airline_code)
    cs_u = str(callsign or "").strip().upper()
    try:
        ws = float(wingspan or 36.0)
    except (ValueError, TypeError):
        ws = 36.0

    # If explicitly flying for a known civilian cargo operator (e.g. Lynden Air Cargo C-130), treat as civilian cargo
    if al_u in CARGO_AIRLINE_OPERATORS and al_u != "CAR":
        return {"is_military": False, "is_heavy_mil": False, "is_fighter_mil": False, "category": ""}

    is_fighter = False
    is_heavy = False

    if icao_u in MILITARY_FIGHTER_TRAINER_TYPES or base_u in MILITARY_FIGHTER_TRAINER_TYPES:
        is_fighter = True
    elif icao_u in MILITARY_TRANSPORT_HEAVY_TYPES or base_u in MILITARY_TRANSPORT_HEAVY_TYPES:
        is_heavy = True
    elif al_u in MILITARY_OPERATORS:
        if ws >= 24.0:
            is_heavy = True
        else:
            is_fighter = True

    if not is_fighter and not is_heavy:
        for cs_pfx in ("CTM", "FAF", "FNY", "RCH", "RRR", "ASC", "GAF", "BAF", "NAF", "IAM", "CNV", "OAN"):
            if cs_u.startswith(cs_pfx) and len(cs_u) > len(cs_pfx) and cs_u[len(cs_pfx)].isdigit():
                if ws >= 24.0:
                    is_heavy = True
                else:
                    is_fighter = True
                break

    combined_txt = f"{name_u} {title_u}".strip()
    if not is_fighter and not is_heavy and combined_txt:
        fighter_kw = (
            "RAFALE", "MIRAGE", "EUROFIGHTER", "TYPHOON", "GRIPEN", "TORNADO",
            "F-14", "F14", "TOMCAT", "F-15", "F15", "F-16", "F16", "F-18", "FA-18", "F/A-18", "HORNET",
            "F-22", "F22", "RAPTOR", "F-35", "F35", "LIGHTNING II", "A-10", "WARTHOG", "THUNDERBOLT II",
            "HARRIER", "AV-8B", "BAE HAWK", "T-45", "GOSHAWK", "T-38", "TALON", "PC-21", "PILATUS PC21",
            "ALPHA JET", "ALPHAJET", "M-346", "L-39", "ALBATROS", "SU-27", "MIG-29", "F-4 PHANTOM",
            "F-104", "STARFIGHTER", "F-117", "NIGHTHAWK",
        )
        heavy_mil_kw = (
            "A400M", "A-400M", "C-17", "GLOBEMASTER", "C-130", "HERCULES", "C-5", "GALAXY",
            "C-160", "TRANSALL", "C-27J", "SPARTAN", "C-295", "CN-235", "KC-135", "STRATOTANKER",
            "KC-46", "KC-10", "EXTENDER", "MRTT", "PHENIX", "VOYAGER KC", "E-3", "AWACS", "SENTRY",
            "P-8", "POSEIDON", "ATLANTIQUE 2", "V-22", "OSPREY", "B-1B", "LANCER", "B-2 SPIRIT",
            "B-52", "STRATOFORTRESS", "AVRO VULCAN", "SR-71", "BLACKBIRD",
        )
        mil_livery_kw = (
            "ARMEE DE L'AIR", "ARMÉE DE L'AIR", "FRENCH AIR FORCE", "AERONAVALE", "AÉRONAVALE",
            "FRENCH NAVY", "ROYAL AIR FORCE", "US AIR FORCE", "U.S. AIR FORCE", "USAF", "US NAVY",
            "U.S. NAVY", "USMC", "LUFTWAFFE", "GERMAN AIR FORCE", "BELGIAN AIR COMPONENT",
            "MILITARY", "COTAM", "ESCADRON", "SQUADRON",
        )
        if any(k in combined_txt for k in fighter_kw):
            is_fighter = True
        elif any(k in combined_txt for k in heavy_mil_kw):
            is_heavy = True
        elif any(k in combined_txt for k in mil_livery_kw):
            if ws >= 24.0:
                is_heavy = True
            else:
                is_fighter = True

    is_mil = bool(is_fighter or is_heavy)
    return {
        "is_military": is_mil,
        "is_heavy_mil": is_heavy,
        "is_fighter_mil": is_fighter,
        "category": "MIL" if is_mil else "",
    }


def is_military_stand_gate(name, terminal="", g_type="", is_military=False):
    if is_military:
        return True
    name_l = str(name or "").lower().strip()
    term_l = str(terminal or "").lower().strip()
    type_l = str(g_type or "").lower().strip()
    if "military" in name_l or "military" in term_l or "military" in type_l or "mil_" in type_l:
        return True
    mil_phrases = (
        "air base", "base aerienne", "base aérienne", "military apron", "mil apron",
        "mil ramp", "military ramp", "nato", "otan", "fighter", "squadron", "escadron", "cotam",
    )
    for text in (name_l, term_l):
        if any(p in text for p in mil_phrases):
            return True
        words = [w for w in re.split(r"[\s\-_/(),]+", text) if w]
        if "mil" in words or "mod" in words or "faf" in words or "usaf" in words or "raf" in words:
            return True
        for w in words:
            if w.startswith("mil") and len(w) > 3 and w[3].isdigit():
                return True
    return False


def is_ga_or_business_flight(ac_icao, ac_name="", base_type="", airline_code="", callsign="", reg="", wingspan=36.0):
    """
    Detects whether a flight is General Aviation (light piston / turboprop) or Business Aviation
    (executive jet / fractional operator) based on aircraft ICAO, base type, name, operator, and wingspan.
    """
    icao_u = str(ac_icao or "").strip().upper()
    base_u = str(base_type or "").strip().upper()
    name_u = str(ac_name or "").strip().upper()
    al_u = normalize_airline_icao(airline_code)
    cs_u = str(callsign or "").strip().upper()
    reg_u = str(reg or "").strip().upper()
    try:
        ws = float(wingspan or 36.0)
    except (ValueError, TypeError):
        ws = 36.0

    is_biz = False
    is_light = False

    if icao_u in BUSINESS_JET_AIRCRAFT_TYPES or base_u in BUSINESS_JET_AIRCRAFT_TYPES:
        is_biz = True
    elif icao_u in GA_LIGHT_AIRCRAFT_TYPES or base_u in GA_LIGHT_AIRCRAFT_TYPES:
        is_light = True
    elif al_u in BUSINESS_AVIATION_OPERATORS and al_u != "GA":
        is_biz = True
    elif al_u == "GA":
        is_light = True

    if not is_biz and not is_light and name_u:
        biz_kw = (
            "CITATION", "GULFSTREAM", "FALCON", "CHALLENGER", "GLOBAL 5", "GLOBAL 6",
            "GLOBAL 7", "GLOBAL EXPRESS", "LEARJET", "PHENOM", "PRAETOR", "LEGACY 4",
            "LEGACY 5", "LEGACY 6", "HONDAJET", "PC-24", "PC24", "HAWKER", "ECLIPSE 5",
            "PREMIER I", "BBJ", "ACJ3",
        )
        light_kw = (
            "CESSNA 1", "CESSNA 2", "CESSNA 3", "CESSNA 4", "SKYHAWK", "SKYLANE",
            "CARAVAN", "CIRRUS", "VISION JET", "PIPER", "CHEROKEE", "ARCHER",
            "WARRIOR", "SENECA", "SEMINOLE", "MALIBU", "MERIDIAN", "DIAMOND DA",
            "BONANZA", "BARON", "KING AIR", "TBM ", "TBM-", "PILATUS PC-12", "PC-12",
            "PC12", "KODIAK", "ISLANDER", "TWIN OTTER", "BEAVER", "ROBIN DR",
            "SOCATA", "MOONEY", "VAN'S RV",
        )
        if any(k in name_u for k in biz_kw):
            is_biz = True
        elif any(k in name_u for k in light_kw):
            is_light = True

    # Private / tail-number flight without commercial airline code and smaller wingspan
    if not is_biz and not is_light and not al_u:
        commercial_airliners = (
            TURBOPROP_TYPES
            | REGIONAL_JET_TYPES
            | STRETCHED_NARROWBODY_TYPES
            | {
                "A318", "A319", "A320", "A321", "A19N", "A20N", "A21N",
                "A332", "A333", "A338", "A339", "A343", "A346", "A359", "A35K", "A388",
                "B712", "B733", "B734", "B735", "B736", "B737", "B738", "B739",
                "B37M", "B38M", "B39M", "B3XM", "B744", "B748", "B752", "B753",
                "B762", "B763", "B764", "B772", "B773", "B77W", "B77L",
                "B788", "B789", "B78X", "MD11", "A306", "A310",
            }
        )
        if icao_u not in commercial_airliners and base_u not in commercial_airliners:
            if ws <= 18.5:
                is_light = True
            elif ws <= 32.5:
                is_biz = True
        elif reg_u and cs_u and cs_u.replace("-", "") == reg_u.replace("-", "") and ws < 30.0:
            is_biz = True

    is_any_ga = bool(is_biz or is_light)
    cat = "BIZ" if is_biz else ("GA" if is_light else "")
    return {
        "is_ga": is_any_ga,
        "is_bizjet": is_biz,
        "is_light_ga": is_light,
        "category": cat,
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

    if icao_u == "OEDF":
        if "royal" in cur_l:
            return "Royal Terminal (VIP)"
        if "aramco" in cur_l:
            return "Saudi Aramco Terminal (Private)"
        if cur_l in ("", "airport terminal", "main apron", "other"):
            return "Main Passenger Terminal"

    if icao_u == "OMDW":
        if let_val == "G" or cur_l == "apron g" or any(k in cur_l for k in ("jetex", "vip", "executive", "falcon", "dc aviation")):
            return "VIP / Executive Aviation Terminal"
        if let_val == "S" and num_val is not None:
            if 400 <= num_val <= 499:
                return "Passenger Terminal (Apron S4)"
            if 320 <= num_val <= 399:
                return "Passenger / Remote Apron (Apron S3)"
            if 200 <= num_val <= 319:
                return "Cargo Terminal (Apron S2)"

    if icao_u == "KMCI":
        if not cur or cur_l in ("main apron", "other"):
            if let_val == "A" or (num_val is not None and 1 <= num_val <= 30):
                return "Main Terminal (Concourse A)"
            if let_val in ("B", "C") or (num_val is not None and 31 <= num_val <= 99):
                return "Main Terminal (Concourse B)"

    if icao_u == "CYMX":
        if not cur or cur_l in ("main apron", "other"):
            return "Main Cargo & Charter Apron"

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
    "EJA": ("#0F172A", "#38BDF8", "#38BDF8", "1I"),
    "VJT": ("#991B1B", "#F8FAFC", "#DC2626", ""),
    "FLX": ("#064E3B", "#FDE047", "#10B981", ""),
    "LXJ": ("#064E3B", "#FDE047", "#10B981", ""),
    "FJO": ("#064E3B", "#FDE047", "#10B981", ""),
    "AHO": ("#1E3A8A", "#FFFFFF", "#3B82F6", ""),
    "GJE": ("#1E293B", "#38BDF8", "#0284C7", ""),
    "JFA": ("#0C4A6E", "#FFFFFF", "#38BDF8", ""),
    "VVG": ("#1E293B", "#F8FAFC", "#64748B", ""),
    "FNY": ("#0F172A", "#F8FAFC", "#38BDF8", ""),
    "ARL": ("#1E3A8A", "#FFFFFF", "#60A5FA", ""),
    "OJT": ("#1E293B", "#FFFFFF", "#38BDF8", ""),
    "WUP": ("#1E3A8A", "#FFFFFF", "#38BDF8", ""),
    "XJC": ("#0F172A", "#FACC15", "#EAB308", ""),
    "EJM": ("#0F172A", "#38BDF8", "#0284C7", ""),
    "TWY": ("#1E293B", "#FFFFFF", "#38BDF8", ""),
    "GA": ("#0369A1", "#FFFFFF", "#38BDF8", ""),
    "BIZ": ("#0F172A", "#38BDF8", "#0284C7", ""),
    "MIL": ("#365314", "#FFFFFF", "#84CC16", ""),
    "CAR": ("#9A3412", "#FFFFFF", "#F97316", ""),
    "CTM": ("#1E3A8A", "#FFFFFF", "#EF4444", ""),
    "FAF": ("#1E3A8A", "#FFFFFF", "#EF4444", ""),
    "RCH": ("#1E293B", "#FACC15", "#3B82F6", ""),
    "RRR": ("#1E3A8A", "#FFFFFF", "#DC2626", ""),
    "GAF": ("#1F2937", "#FACC15", "#E5E7EB", ""),
    "CMA": ("#00205B", "#FFFFFF", "#E30613", "2C"),
    "CJT": ("#B91C1C", "#FFFFFF", "#111827", "W8"),
    "GTI": ("#003087", "#FACC15", "#003087", "5Y"),
    "CKS": ("#7C2D12", "#FACC15", "#DC2626", "K4"),
    "PAC": ("#003087", "#FFFFFF", "#38BDF8", "PO"),
    "NCA": ("#00205B", "#FFFFFF", "#E60012", "KZ"),
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
    "EJA": "NetJets Aviation",
    "VJT": "VistaJet",
    "FLX": "Flexjet",
    "LXJ": "Flexjet",
    "FJO": "Flexjet Europe",
    "AHO": "Air Hamburg",
    "GJE": "Global Jet",
    "JFA": "Jetfly Aviation",
    "VVG": "Valljet",
    "FNY": "Aéronavale (French Navy)",
    "ARL": "Airlec Air Espace",
    "OJT": "Pan Européenne Air Service",
    "WUP": "Wheels Up",
    "XJC": "flyExclusive",
    "EJM": "Executive Jet Management",
    "TWY": "Solairus Aviation",
    "GA": "General Aviation",
    "BIZ": "Business Aviation",
    "MIL": "Military Aviation",
    "CAR": "Cargo Operations",
    "CTM": "Armée de l'Air (COTAM)",
    "FAF": "Armée de l'Air et de l'Espace",
    "RCH": "USAF Air Mobility (Reach)",
    "RRR": "Royal Air Force (Ascot)",
    "GAF": "German Air Force (Luftwaffe)",
    "BAF": "Belgian Air Component",
    "NAF": "Royal Netherlands Air Force",
    "IAM": "Italian Air Force",
    "AME": "Spanish Air Force",
    "SUI": "Swiss Air Force",
    "CFC": "Royal Canadian Air Force",
    "ASY": "Royal Australian Air Force",
    "CNV": "U.S. Navy Logistics",
    "OAN": "NATO Operations",
    "LOG": "Loganair",
    "AUR": "Aurigny Air Services",
    "FPO": "ASL Airlines France",
    "ABR": "ASL Airlines Ireland",
    "TAY": "ASL Airlines Belgium",
    "CMA": "CMA CGM Air Cargo",
    "CJT": "Cargojet Airways",
    "GTI": "Atlas Air",
    "PAC": "Polar Air Cargo",
    "CKS": "Kalitta Air",
    "NCA": "Nippon Cargo Airlines",
    "SQC": "Singapore Airlines Cargo",
    "CKK": "China Cargo Airlines",
    "MPH": "Martinair Cargo",
    "ICV": "Cargolux Italia",
    "SWT": "Swiftair",
    "SWN": "West Atlantic",
    "NPT": "West Atlantic UK",
    "AZG": "Silk Way West Airlines",
    "ICL": "Challenge Airlines",
    "SRR": "Maersk Air Cargo",
    "RUN": "ACT Airlines (myCARGO)",
    "MNB": "MNG Airlines",
    "WGN": "Western Global Airlines",
    "NCR": "National Airlines Cargo",
    "AJT": "Amerijet International",
    "CSS": "SF Airlines",
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

    cargo_only_set = CARGO_AIRLINE_OPERATORS

    # 2. Cargo / GA / Military
    if is_military or is_military_stand_gate(stand_ref, term_l, "", is_military):
        return ["MIL"]
    if is_cargo or "cargo" in term_l or "fret" in term_l:
        rw_cargo = [[c] for c, cnt in sorted(rw_map.items(), key=lambda x: -x[1]) if c in cargo_only_set and cnt > 0]
        cargo_pool = rw_cargo if len(rw_cargo) >= 2 else [["FDX"], ["DHK"], ["UPS"], ["CLX"], ["GEC"], ["BOX"]]
        return cargo_pool[blk % len(cargo_pool)]
    if is_ga or "general aviation" in term_l or "business" in term_l or "affaires" in term_l:
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


def is_freighter_aircraft(ac_icao, ac_name="", sim_title=""):
    if not ac_icao: ac_icao = ""
    if not ac_name: ac_name = ""
    if not sim_title: sim_title = ""
    ac_icao_u = str(ac_icao).upper().strip()
    ac_name_u = str(ac_name).upper().strip()
    title_u = str(sim_title).upper().strip()

    cargo_icaos = {
        "B77F", "A332F", "A333F", "B748F", "B744F", "B742F", "B74F", "B738F", "B738BCF", "B737F", "B733F", "B734F",
        "B722F", "B752F", "B763F", "B762F", "B76F", "MD11F", "A306F", "A310F", "A321F", "A320F", "A330F",
        "AN124", "AN225", "AN22", "AN12", "AN26", "AN72", "IL76", "AT7F", "AT4F", "C208F",
        "DC10F", "L1011F", "B707F", "DC8F", "B77L_F"
    }
    if ac_icao_u in cargo_icaos:
        return True

    if any(k in ac_icao_u for k in ("BCF", "P2F", "BDSF")) or re.match(r"^(?:A3\d\d|B7\d\d|MD11|DC\d\d|AT\d\d)F$", ac_icao_u):
        return True

    combined_u = f"{ac_name_u} {title_u}".strip()
    if not combined_u:
        return False

    explicit_freighter_models = (
        "777F", "777-F", "777-200LRF", "747-8F", "747-400F", "747-400ERF",
        "A300-600RF", "A300-600F", "A330-200F", "A321-200P2F", "A321P2F", "A320P2F",
        "MD-11F", "767-300F", "767-300ERF", "757-200F", "737-800F", "737-800BCF", "727-200F",
    )
    if any(m in combined_u for m in explicit_freighter_models):
        return True

    if re.search(r"\b(?:BCF|P2F|BDSF|FREIGHTER|FREIGHT|CARGO|SKYCARGO|ALL-CARGO|FEDEX|UPS|DHL|CARGOLUX|AEROLOGIC)\b", combined_u):
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

    ga_biz_phrases = (
        "general aviation", "aviation generale", "aviation générale",
        "business aviation", "aviation d'affaires", "affaires",
        "private", "small", "prop", "fbo", "vip", "executive",
        "royal terminal", "royal pavilion", "amiri", "presidential",
        "state terminal", "aramco", "jetex",
    )
    for text in (name_lower, term_lower):
        if any(p in text for p in ga_biz_phrases):
            return True
        words = re.split(r'[\s\-_]', text)
        if "ga" in words or "fbo" in words or "biz" in words:
            return True
        for w in words:
            if w.startswith("ga") and len(w) > 2 and w[2].isdigit():
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
        self.user_sim_wingspan = None
        self.user_title = ""
        self.user_atc_model = ""
        self.user_atc_type = ""
        self.user_atc_id = ""
        self.user_atc_airline = ""
        self.user_livery_name = ""
        self.user_camera_state = None
        self._tarmac_anchor_coords = None
        self._tarmac_stable_since = None
        self.tarmac_stable_duration = 0.0
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
        self._sim_quit_received = False
        self._last_proc_alive_check = 0.0

        self._log("SimConnectManager initialized.")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _on_sim_quit(self, recv) -> bool:
        self._log("Received SIMCONNECT_RECV_ID_QUIT from MSFS — closing SimConnect handle immediately.")
        self._sim_quit_received = True
        self.connected = False
        return True

    def _close_simconnect_handle(self):
        self.connected = False
        self.user_dd = None
        self.gsx_dd = None
        if self.sm is not None:
            try:
                self.sm.Close()
            except Exception:
                pass
            self.sm = None

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

    def _check_auto_quit_if_msfs_closed(self, force_on_sim_quit: bool = False):
        try:
            auto_quit_cfg = bool(self.backend.config.settings.get("auto_quit_with_msfs", True))
            launched_by_exexml = ("--silent" in sys.argv)
            if not auto_quit_cfg and not launched_by_exexml:
                return
            if force_on_sim_quit:
                self._log("MSFS sent SIMCONNECT_RECV_ID_QUIT; releasing handles and exiting GateFinder cleanly...")
                self._close_simconnect_handle()
                time.sleep(0.25)
                os._exit(0)
            if self._is_msfs_process_running():
                self._msfs_was_running = True
                return
            if self._msfs_was_running:
                self._close_simconnect_handle()
                time.sleep(0.6)
                if not self._is_msfs_process_running():
                    self._log("MSFS process closed. Exiting GateFinder cleanly so Gaming Services / Steam can release...")
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
                    self._sim_quit_received = False
                    self.sm = SC(name="GateFinder V2.0")
                    self.connected = True
                    self._msfs_was_running = True
                    self._last_proc_alive_check = time.time()
                    self._log("Connected to MSFS successfully!")
                    self.sm.add_receiver(RECV_QUIT, self._on_sim_quit)
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
                    
                    # Setup User Position & Telemetry subscription (PERIOD_SIM_FRAME w/ interval=4 -> ~15-30 Hz low-overhead updates)
                    user_simvars = [
                        {"name": "PLANE LATITUDE", "units": "degrees"},
                        {"name": "PLANE LONGITUDE", "units": "degrees"},
                        {"name": "PLANE HEADING DEGREES TRUE", "units": "degrees"},
                        {"name": "GROUND VELOCITY", "units": "knots"},
                        {"name": "SIM ON GROUND", "units": "bool"},
                        {"name": "GENERAL ENG COMBUSTION:1", "units": "bool"},
                        {"name": "GENERAL ENG COMBUSTION:2", "units": "bool"},
                        {"name": "WING SPAN", "units": "feet"},
                        {"name": "CAMERA STATE", "units": "Enum"}
                    ]
                    self.user_dd = self.sm.subscribe_simdata(user_simvars, period=PERIOD_SIM_FRAME, interval=4)
                    self._lvar_def_ids = {}
                    self._lvar_next_def_id = 900
                    try:
                        ac_str_defs = [
                            ("TITLE", None, DATATYPE_STRING256),
                            ("ATC MODEL", None, DATATYPE_STRING256),
                            ("ATC TYPE", None, DATATYPE_STRING256),
                            ("ATC ID", None, DATATYPE_STRING256),
                            ("ATC AIRLINE", None, DATATYPE_STRING256),
                        ]
                        for idx_s, (sv_n, sv_u, sv_dt) in enumerate(ac_str_defs):
                            self.sm.AddToDataDefinition(851, sv_n, sv_u, sv_dt, 0, idx_s)

                        def _on_ac_str_recv(recv):
                            if getattr(recv, "dwRequestID", None) != 851:
                                return False
                            try:
                                offset = RECV_SIMOBJECT_DATA.dwData.offset
                                vals = []
                                for _ in range(min(5, int(recv.dwDefineCount))):
                                    ptr = ctypes.cast(ctypes.byref(recv, offset), ctypes.POINTER(ctypes.c_char))
                                    chunk = ptr[:256]
                                    vals.append(chunk.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip())
                                    offset += 256
                                if len(vals) == 5:
                                    self.user_title = vals[0]
                                    self.user_atc_model = vals[1]
                                    self.user_atc_type = vals[2]
                                    self.user_atc_id = vals[3]
                                    self.user_atc_airline = vals[4]
                            except Exception:
                                pass
                            return True

                        self.sm.add_receiver(RECV_SIMOBJECT_DATA, _on_ac_str_recv)
                        self.sm.RequestDataOnSimObject(
                            851, 851, OBJECT_ID_USER, PERIOD_SECOND,
                            DATA_REQUEST_FLAG_CHANGED, 0, 2, 0
                        )
                    except Exception as ac_err:
                        self._log(f"Aircraft string SimVar subscription warning: {ac_err}")
                    try:
                        self.sm.AddToDataDefinition(852, "LIVERY NAME", None, DATATYPE_STRING256, 0, 0)

                        def _on_ac_liv_recv(recv):
                            if getattr(recv, "dwRequestID", None) != 852:
                                return False
                            try:
                                offset = RECV_SIMOBJECT_DATA.dwData.offset
                                ptr = ctypes.cast(ctypes.byref(recv, offset), ctypes.POINTER(ctypes.c_char))
                                chunk = ptr[:256]
                                self.user_livery_name = chunk.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
                            except Exception:
                                pass
                            return True

                        self.sm.add_receiver(RECV_SIMOBJECT_DATA, _on_ac_liv_recv)
                        self.sm.RequestDataOnSimObject(
                            852, 852, OBJECT_ID_USER, PERIOD_SECOND,
                            DATA_REQUEST_FLAG_CHANGED, 0, 2, 0
                        )
                    except Exception:
                        pass
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
                for _ in range(48):
                    if not (self.sm and self.sm.receive()):
                        break
                    if self._sim_quit_received:
                        break

                if self._sim_quit_received:
                    self._close_simconnect_handle()
                    self._check_auto_quit_if_msfs_closed(force_on_sim_quit=True)
                    time.sleep(2.0)
                    continue

                now_proc_chk = time.time()
                if (now_proc_chk - self._last_proc_alive_check) >= 2.0:
                    self._last_proc_alive_check = now_proc_chk
                    if not self._is_msfs_process_running():
                        self._log("MSFS process is no longer running; closing SimConnect handle.")
                        self._close_simconnect_handle()
                        self._check_auto_quit_if_msfs_closed()
                        time.sleep(2.0)
                        continue

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
                    raw_ws_ft = self.user_dd.simdata.get("WING SPAN")
                    if raw_ws_ft is not None:
                        try:
                            ws_m = float(raw_ws_ft) * 0.3048
                            if 4.0 <= ws_m <= 95.0:
                                self.user_sim_wingspan = round(ws_m, 1)
                        except Exception:
                            pass

                    gs_val = float(raw_gs or 0.0)
                    raw_cam = self.user_dd.simdata.get("CAMERA STATE")
                    cam_state = int(round(float(raw_cam))) if raw_cam is not None else None
                    self.user_camera_state = cam_state

                    # Detect MSFS 2020/2024 Main Menu / World Map / Pre-Flight / Loading state:
                    # - CAMERA STATE in (11..20) or >= 22 means World Map (11), Hangar/Menu RTC (12..18),
                    #   Pre-Flight Cinematic (14), or MSFS 2024 Menu/Briefing (24..35).
                    # - Active flight/tarmac cameras (including ChasePlane & Walkaround) are 2..9 and 21.
                    # - MSFS 2024 World Map / Menu also parks the preview SimObject at KBFI (Boeing Field, 47.53, -122.30) or (0, 0) / (0, 90).
                    # - Or SIM ON GROUND is False while stationary/slow (< 35 kt) with engines off.
                    is_menu_cam = bool(cam_state is not None and (cam_state == 11 or (12 <= cam_state <= 20) or cam_state >= 22))
                    is_kbfi_staging = False
                    if raw_lat is not None and raw_lon is not None:
                        try:
                            f_lat, f_lon = float(raw_lat), float(raw_lon)
                            if 47.510 <= f_lat <= 47.550 and -122.325 <= f_lon <= -122.285:
                                fd_cur = getattr(self.backend, "current_flight_data", None) or {}
                                dep_c = str((fd_cur.get("departure") or {}).get("icao") or "").upper()
                                arr_c = str((fd_cur.get("arrival") or {}).get("icao") or "").upper()
                                if "KBFI" not in (dep_c, arr_c) and cam_state != 2:
                                    is_kbfi_staging = True
                        except Exception:
                            pass
                    is_dummy_coords = (
                        raw_lat is None
                        or raw_lon is None
                        or (abs(float(raw_lat)) < 0.05 and (abs(float(raw_lon)) < 0.05 or abs(abs(float(raw_lon)) - 90.0) < 0.05))
                        or is_kbfi_staging
                    )
                    is_menu_state = bool(is_dummy_coords or is_menu_cam or (og_bool is False and gs_val < 35.0 and not eng_running))
                    self.in_menu = is_menu_state
                    # Pre-warm GPS airport resolution in background ONLY when stationary/slow on ground or during MSFS tarmac intro camera
                    if (
                        not is_dummy_coords
                        and raw_lat is not None
                        and raw_lon is not None
                        and self.backend
                        and gs_val <= 12.0
                        and (og_bool is not False or is_menu_cam)
                    ):
                        try:
                            gk = (round(float(raw_lat), 3), round(float(raw_lon), 3))
                            g_cache = getattr(self.backend, "_live_gps_airport_cache", None)
                            prewarm_set = getattr(self, "_prewarming_gps_keys", None)
                            if prewarm_set is None:
                                self._prewarming_gps_keys = set()
                                prewarm_set = self._prewarming_gps_keys
                            if (g_cache is None or gk not in g_cache) and gk not in prewarm_set:
                                prewarm_set.add(gk)
                                plat, plon = float(raw_lat), float(raw_lon)
                                threading.Thread(
                                    target=lambda: self.backend.detect_live_msfs_airport(plat, plon),
                                    daemon=True,
                                ).start()
                        except Exception:
                            pass
                    if is_menu_state:
                        self.user_lat = None
                        self.user_lon = None
                        self.user_hdg = raw_hdg
                        self.user_gs = 0.0
                        self.user_on_ground = None
                        self.user_engines_running = False
                        self._tarmac_anchor_coords = None
                        self._tarmac_stable_since = None
                        self.tarmac_stable_duration = 0.0
                        if self.backend and hasattr(self.backend, "_dismissed_airport_mismatches"):
                            self.backend._dismissed_airport_mismatches.clear()
                    else:
                        self.user_lat = raw_lat
                        self.user_lon = raw_lon
                        self.user_hdg = raw_hdg
                        self.user_gs = gs_val
                        self.user_on_ground = og_bool
                        self.user_engines_running = eng_running
                        if (
                            og_bool is True
                            and gs_val <= 10.0
                            and not is_menu_cam
                            and raw_lat is not None
                            and raw_lon is not None
                        ):
                            now_t = time.time()
                            cur_pt = (float(raw_lat), float(raw_lon))
                            if (
                                self._tarmac_anchor_coords is None
                                or self._tarmac_stable_since is None
                                or haversine(cur_pt[0], cur_pt[1], self._tarmac_anchor_coords[0], self._tarmac_anchor_coords[1]) > 35.0
                            ):
                                self._tarmac_anchor_coords = cur_pt
                                self._tarmac_stable_since = now_t
                                self.tarmac_stable_duration = 0.0
                            else:
                                self.tarmac_stable_duration = max(0.0, now_t - self._tarmac_stable_since)
                        else:
                            self._tarmac_anchor_coords = None
                            self._tarmac_stable_since = None
                            self.tarmac_stable_duration = 0.0
                else:
                    self.in_menu = False
                    self.user_lat = None
                    self.user_lon = None
                    self.user_hdg = None
                    self.user_gs = None
                    self.user_on_ground = None
                    self.user_engines_running = None
                    self._tarmac_anchor_coords = None
                    self._tarmac_stable_since = None
                    self.tarmac_stable_duration = 0.0

                self._tick()
                time.sleep(0.03 if (self.user_on_ground is not False and not self.in_menu) else 0.08)
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
        self.taxi_router.bgl_geometry_provider = self._fetch_msfs_bgl_airport_geometry
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
        if not c or c in ("ANY", "NONE", "GA", "BIZ"):
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
            if not c or c in ("ANY", "NONE", "GA", "BIZ", "MIL", "CAR") or c in self._logo_fetch_failed or c in self._logo_fetch_inflight:
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
        if c in ("GA", "BIZ", "MIL", "CAR"):
            has_raw = False
        else:
            has_raw = os.path.exists(raw_path) and os.path.getsize(raw_path) > 100

        if not has_raw and c not in ("GA", "BIZ", "MIL", "CAR"):
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
        if norm_assigned_al in ("", "ANY", "NONE", "GA", "BIZ"):
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
        self._static_builtin_icaos = set(self.builtin_data.keys())
        self._msfs_live_bgl_icaos = set()

    def _ensure_msfs_live_bgl_stands(self, icao):
        """
        Queries MSFS 2020/2024 directly in memory via SimConnect_RequestFacilityData
        (TAXI_PARKING) when `icao` is a small/default airport not present in GSX (`self.data`)
        and not already present in the 931 commercial airports of `default_airports_db.bin`.
        Guarantees 100% zero regression on existing commercial/GSX airports while providing
        all native MSFS white-dot parking positions (e.g. LFBJ's 3 stands, LFMD's 59 stands).
        """
        icao_u = str(icao or "").strip().upper()
        if not icao_u or len(icao_u) < 3:
            return False
        if not hasattr(self, "_static_builtin_icaos"):
            self._static_builtin_icaos = set(self.builtin_data.keys())
        if not hasattr(self, "_msfs_live_bgl_icaos"):
            self._msfs_live_bgl_icaos = set()
        if icao_u in self.data or icao_u in self._static_builtin_icaos:
            return False
        if icao_u in self._msfs_live_bgl_icaos:
            return True

        dll_path = self._get_resource_file("SimConnect_MSFS.dll")
        if not dll_path or not os.path.isfile(dll_path):
            for cand_dll in (
                os.path.expandvars(r"%LOCALAPPDATA%\LAND3.vRAAS\current\SDK2024\SimConnect.dll"),
                r"D:\MSFS_Utility\MSFS_Addons_Linker\Simconnect_2024\SimConnect.dll",
            ):
                if os.path.isfile(cand_dll):
                    dll_path = cand_dll
                    break
        if not dll_path or not os.path.isfile(dll_path):
            return False

        try:
            import math
            import struct
            from ctypes import wintypes

            if not hasattr(self, "_msfs_facility_dll") or self._msfs_facility_dll is None:
                self._msfs_facility_dll = ctypes.WinDLL(dll_path)
            sc = self._msfs_facility_dll

            h_sc = wintypes.HANDLE()
            hr = sc.SimConnect_Open(ctypes.byref(h_sc), b"GateFinder_Facility", None, 0, None, 0)
            if hr != 0:
                return False

            raw_parkings = []
            apt_lat, apt_lon = None, None
            try:
                def_id = 5001
                fields = (
                    b"OPEN AIRPORT",
                    b"LATITUDE",
                    b"LONGITUDE",
                    b"OPEN TAXI_PARKING",
                    b"TYPE",
                    b"NUMBER",
                    b"NAME",
                    b"BIAS_X",
                    b"BIAS_Z",
                    b"HEADING",
                    b"RADIUS",
                    b"CLOSE TAXI_PARKING",
                    b"CLOSE AIRPORT",
                )
                for fld in fields:
                    sc.SimConnect_AddToFacilityDefinition(h_sc, def_id, fld)
                if sc.SimConnect_RequestFacilityData(h_sc, def_id, 9001, icao_u.encode("ascii", errors="ignore"), b"") == 0:
                    class _SC_RECV(ctypes.Structure):
                        _fields_ = [
                            ("dwSize", wintypes.DWORD),
                            ("dwVersion", wintypes.DWORD),
                            ("dwID", wintypes.DWORD),
                        ]

                    p_data = ctypes.POINTER(_SC_RECV)()
                    cb_data = wintypes.DWORD()
                    t0 = time.time()
                    while time.time() - t0 < 0.65:
                        if sc.SimConnect_GetNextDispatch(h_sc, ctypes.byref(p_data), ctypes.byref(cb_data)) == 0:
                            dw_id = int(p_data.contents.dwID)
                            if dw_id == 28:  # SIMCONNECT_RECV_ID_FACILITY_DATA
                                raw = ctypes.string_at(p_data, int(p_data.contents.dwSize))
                                payload = raw[40:]
                                if len(payload) == 16:
                                    apt_lat, apt_lon = struct.unpack("<dd", payload)
                                elif len(payload) == 28 and apt_lat is not None and apt_lon is not None:
                                    ptype, pnum, pname, bx, bz, hdg, rad = struct.unpack("<iiiffff", payload)
                                    if ptype != 13:  # Exclude ground vehicle staging (13); keep aircraft & fuel box stands
                                        p_lat = apt_lat + (bz / 111111.0)
                                        p_lon = apt_lon + (bx / (111111.0 * max(0.1, math.cos(math.radians(apt_lat)))))
                                        raw_parkings.append((pname, pnum, ptype, rad, round(p_lat, 6), round(p_lon, 6), round(float(hdg) % 360.0, 1)))
                            elif dw_id == 29:  # SIMCONNECT_RECV_ID_FACILITY_DATA_END
                                break
                        else:
                            time.sleep(0.005)
            finally:
                try:
                    sc.SimConnect_Close(h_sc)
                except Exception:
                    pass

            if not raw_parkings:
                return False

            icao_dict = {"ANY": []}
            seen_names = set()
            # Sort so standard aircraft parking stands (ptype != 12) take name precedence over fuel boxes (ptype == 12)
            raw_parkings.sort(key=lambda x: (1 if x[2] == 12 else 0, x[1]))
            for pname, pnum, ptype, rad, p_lat, p_lon, p_hdg in raw_parkings:
                ptype_conv = 2 if ptype == 12 else ptype
                gate_info, _ = convert_bgl_entry_to_gate_info(
                    pname, pnum, ptype_conv, rad, p_lat, p_lon, False, []
                )
                if not gate_info:
                    continue
                g_name = str(gate_info["name"]).strip()
                if g_name in seen_names:
                    if ptype == 12:
                        g_name = f"FUEL {pnum}" if f"FUEL {pnum}" not in seen_names else f"{g_name}F"
                    else:
                        continue
                seen_names.add(g_name)
                gate_info["name"] = g_name
                gate_info["heading"] = p_hdg
                gate_info["is_fuel_box"] = bool(ptype == 12)
                icao_dict["ANY"].append(gate_info)

            if not icao_dict["ANY"]:
                return False

            self.builtin_data[icao_u] = icao_dict
            self._msfs_live_bgl_icaos.add(icao_u)
            for k_osm in [k for k in list(self.osm_cache.keys()) if k == icao_u or k.startswith(f"{icao_u}_")]:
                self.osm_cache.pop(k_osm, None)
            if hasattr(self, "coherent_airports"):
                self.coherent_airports.pop(icao_u, None)
            return True
        except Exception as e:
            print(f"[SimConnect Facility] Warning fetching parkings for {icao_u}: {e}")
            return False

    def _fetch_msfs_bgl_airport_geometry(self, icao):
        """
        Global native MSFS BGL / default DB fallback provider for TaxiRouter when OpenStreetMap
        geometry is missing or incomplete. Collects parking stands from GSX / default_airports_db.bin /
        live SimConnect TAXI_PARKING, and queries native MSFS BGL RUNWAY records when MSFS is active.
        """
        icao_u = str(icao or "").strip().upper()
        if not icao_u or len(icao_u) < 3:
            return None

        self._ensure_msfs_live_bgl_stands(icao_u)

        stands_out = []
        seen_st = set()
        for src_map in (self.data.get(icao_u) or {}, self.builtin_data.get(icao_u) or {}):
            for g_list in src_map.values():
                for g in g_list:
                    if g.get("lat") is not None and g.get("lon") is not None:
                        nm = str(g.get("name") or "").strip()
                        key = (nm.upper(), round(float(g["lat"]), 5), round(float(g["lon"]), 5))
                        if nm and key not in seen_st:
                            seen_st.add(key)
                            stands_out.append(dict(g))

        apt_lat, apt_lon = None, None
        runways_out = []
        dll_path = self._get_resource_file("SimConnect_MSFS.dll")
        if not dll_path or not os.path.isfile(dll_path):
            for cand_dll in (
                os.path.expandvars(r"%LOCALAPPDATA%\LAND3.vRAAS\current\SDK2024\SimConnect.dll"),
                r"D:\MSFS_Utility\MSFS_Addons_Linker\Simconnect_2024\SimConnect.dll",
            ):
                if os.path.isfile(cand_dll):
                    dll_path = cand_dll
                    break

        sc_mgr = getattr(self, "simconnect_manager", None)
        if dll_path and os.path.isfile(dll_path) and sc_mgr and getattr(sc_mgr, "connected", False):
            try:
                import math
                import struct
                from ctypes import wintypes

                if not hasattr(self, "_msfs_facility_dll") or self._msfs_facility_dll is None:
                    self._msfs_facility_dll = ctypes.WinDLL(dll_path)
                sc = self._msfs_facility_dll
                h_sc = wintypes.HANDLE()
                if sc.SimConnect_Open(ctypes.byref(h_sc), b"GateFinder_RwyFacility", None, 0, None, 0) == 0:
                    try:
                        def_id = 5002
                        rwy_fields = (
                            b"OPEN AIRPORT",
                            b"LATITUDE",
                            b"LONGITUDE",
                            b"OPEN RUNWAY",
                            b"LATITUDE",
                            b"LONGITUDE",
                            b"HEADING",
                            b"LENGTH",
                            b"WIDTH",
                            b"PRIMARY_NUMBER",
                            b"PRIMARY_DESIGNATOR",
                            b"SECONDARY_NUMBER",
                            b"SECONDARY_DESIGNATOR",
                            b"CLOSE RUNWAY",
                            b"CLOSE AIRPORT",
                        )
                        for fld in rwy_fields:
                            sc.SimConnect_AddToFacilityDefinition(h_sc, def_id, fld)
                        if sc.SimConnect_RequestFacilityData(h_sc, def_id, 9002, icao_u.encode("ascii", errors="ignore"), b"") == 0:
                            class _SC_RECV(ctypes.Structure):
                                _fields_ = [
                                    ("dwSize", wintypes.DWORD),
                                    ("dwVersion", wintypes.DWORD),
                                    ("dwID", wintypes.DWORD),
                                ]

                            p_data = ctypes.POINTER(_SC_RECV)()
                            cb_data = wintypes.DWORD()
                            desig_map = {0: "", 1: "L", 2: "R", 3: "C", 4: "W", 5: "A", 6: "B"}
                            t0 = time.time()
                            while time.time() - t0 < 0.55:
                                if sc.SimConnect_GetNextDispatch(h_sc, ctypes.byref(p_data), ctypes.byref(cb_data)) == 0:
                                    dw_id = int(p_data.contents.dwID)
                                    if dw_id == 28:
                                        raw = ctypes.string_at(p_data, int(p_data.contents.dwSize))
                                        payload = raw[40:]
                                        if len(payload) == 16:
                                            apt_lat, apt_lon = struct.unpack("<dd", payload)
                                        elif len(payload) == 44:
                                            rlat, rlon, rhdg, rlen, rwid, pnum, pdes, snum, sdes = struct.unpack("<ddfffiiii", payload)
                                            if rlen >= 250.0 and -90.0 <= rlat <= 90.0 and -180.0 <= rlon <= 180.0:
                                                half_m = float(rlen) * 0.5
                                                rad_h = math.radians(float(rhdg))
                                                cos_lat = max(0.1, math.cos(math.radians(rlat)))
                                                dlat = (half_m * math.cos(rad_h)) / 111320.0
                                                dlon = (half_m * math.sin(rad_h)) / (111320.0 * cos_lat)
                                                p1 = [round(rlat - dlat, 6), round(rlon - dlon, 6)]
                                                p2 = [round(rlat + dlat, 6), round(rlon + dlon, 6)]
                                                id1 = f"{int(pnum):02d}{desig_map.get(int(pdes), '')}" if 1 <= int(pnum) <= 36 else ""
                                                id2 = f"{int(snum):02d}{desig_map.get(int(sdes), '')}" if 1 <= int(snum) <= 36 else ""
                                                ref_s = f"{id1}/{id2}".strip("/")
                                                runways_out.append({
                                                    "ref": ref_s,
                                                    "width": round(max(18.0, float(rwid)), 1),
                                                    "length_m": round(float(rlen), 1),
                                                    "points": [p1, p2],
                                                })
                                    elif dw_id == 29:
                                        break
                                else:
                                    time.sleep(0.005)
                    finally:
                        try:
                            sc.SimConnect_Close(h_sc)
                        except Exception:
                            pass
            except Exception as e:
                print(f"[SimConnect Facility] Warning fetching BGL runways for {icao_u}: {e}")

        if apt_lat is None and stands_out:
            apt_lat = sum(float(s["lat"]) for s in stands_out) / len(stands_out)
            apt_lon = sum(float(s["lon"]) for s in stands_out) / len(stands_out)

        if not runways_out and not stands_out:
            return None
        return {
            "center_lat": apt_lat,
            "center_lon": apt_lon,
            "runways": runways_out,
            "stands": stands_out,
        }

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
        icao_u = str(icao or "").strip().upper()
        self._ensure_msfs_live_bgl_stands(icao_u)
        cache_key = f"{icao}_{lat}_{lon}" if (lat and lon) else icao
        if cache_key in self.osm_cache:
            return self.osm_cache[cache_key], None

        chart = self.taxi_router.fetch_airport_vector_data(icao, center_lat=lat, center_lon=lon)
        if (
            chart
            and icao_u in getattr(self, "_msfs_live_bgl_icaos", set())
            and icao_u in self.builtin_data
            and not chart.get("msfs_facility_stands")
        ):
            msfs_st = []
            seen_msfs = set()
            for al_l in self.builtin_data[icao_u].values():
                for bg in al_l:
                    ref_m = str(bg.get("name") or "").strip()
                    if ref_m and ref_m not in seen_msfs and bg.get("lat") is not None and bg.get("lon") is not None:
                        seen_msfs.add(ref_m)
                        msfs_st.append({
                            "ref": ref_m,
                            "lat": round(float(bg["lat"]), 6),
                            "lon": round(float(bg["lon"]), 6),
                            "heading": bg.get("heading"),
                            "terminal": bg.get("terminal") or "General Aviation Apron",
                            "has_jetway": bool(bg.get("has_jetway", False)),
                            "is_ga": bool(bg.get("is_ga", True)),
                            "wingspan": float(bg.get("wingspan", 20.0)),
                        })
            if msfs_st:
                chart["osm_stands"] = [dict(s) for s in msfs_st]
                chart["stands"] = [dict(s) for s in msfs_st]
                chart["msfs_facility_stands"] = True
                try:
                    self.taxi_router._save_disk_cache()
                except Exception:
                    pass
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

            is_ga = bool(p.get("is_ga", False))
            max_ws = float(p.get("wingspan") or (24.0 if is_ga else 36.0))
            if len_m >= 78.0:
                max_ws = 80.0
            elif len_m >= 68.0:
                max_ws = 68.5
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
                "terminal": p.get("terminal", ""),
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
        self._ensure_msfs_live_bgl_stands(icao_u)
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

            # Supplement GSX profiles that only define commercial terminal gates with any BGL/OSM GA stands (> 35m away)
            gsx_all = list(enriched_cache.values())
            if not any(g_item.get("is_ga") for g_item in gsx_all):
                gsx_tokens = {clean_gate_token(g_item.get("name", "")) for g_item in gsx_all}
                gsx_coords = [(g_item["lat"], g_item["lon"]) for g_item in gsx_all if g_item.get("lat") is not None and g_item.get("lon") is not None]
                if "ANY" not in coherent_db:
                    coherent_db["ANY"] = []
                bgl_db_a = self.builtin_data.get(icao_u) or {}
                seen_bgl_ga = set()
                for al_list_a in bgl_db_a.values():
                    for bg in al_list_a:
                        if not bg.get("is_ga") or bg.get("lat") is None or bg.get("lon") is None:
                            continue
                        b_key = (bg.get("name"), bg.get("lat"), bg.get("lon"))
                        if b_key in seen_bgl_ga:
                            continue
                        seen_bgl_ga.add(b_key)
                        min_d_gsx = min((haversine(bg["lat"], bg["lon"], glat, glon) for glat, glon in gsx_coords), default=9999.0)
                        if min_d_gsx <= 35.0:
                            continue
                        bg_name = str(bg.get("name") or "").strip()
                        bg_tok = clean_gate_token(bg_name)
                        if bg_tok in gsx_tokens:
                            bg_name = f"GA {bg_name}"
                            bg_tok = clean_gate_token(bg_name)
                        if bg_tok in gsx_tokens:
                            continue
                        gsx_tokens.add(bg_tok)
                        sp_t = _infer_spatial_terminal(bg["lat"], bg["lon"]) or "General Aviation Apron"
                        coherent_db["ANY"].append({
                            "name": bg_name,
                            "raw_name": bg.get("name", bg_name),
                            "osm_ref": "",
                            "py_aircraft_types": [],
                            "wingspan": float(bg.get("wingspan", 20.0)),
                            "terminal": sp_t,
                            "type": "STAND",
                            "lat": bg["lat"],
                            "lon": bg["lon"],
                            "heading": bg.get("heading"),
                            "no_pushback": False,
                            "has_jetway": False,
                            "is_cargo": False,
                            "is_ga": True,
                            "is_military": False,
                            "airlines": [],
                        })

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

            matched_bgl_ids = set()
            existing_coh_tokens = set()
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
                if matched_bgl is not None:
                    matched_bgl_ids.add(id(matched_bgl))
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
                    or any(
                        kw in sp_term_l
                        for kw in (
                            "affaires", "general aviation", "executive", "vip",
                            "royal terminal", "royal pavilion", "amiri", "presidential",
                            "state terminal", "aramco", "jetex", "fbo", "private",
                        )
                    )
                )
                is_cargo = bool(
                    (matched_bgl and matched_bgl.get("is_cargo", False))
                    or "cargo" in o_ref.lower()
                    or (("fret" in sp_term_l or "cargo" in sp_term_l) and "pax" not in sp_term_l and "passenger" not in sp_term_l and "charter" not in sp_term_l)
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
                existing_coh_tokens.add(clean_gate_token(gate_info["name"]))
                coherent_db["ANY"].append(gate_info)
                for a_c in al_set:
                    if a_c not in coherent_db:
                        coherent_db[a_c] = []
                    coherent_db[a_c].append(gate_info)

            # Also preserve unmatched BGL GA / non-jetway stands that were not drawn in OpenStreetMap
            for bg in bgl_unique:
                if id(bg) in matched_bgl_ids:
                    continue
                bg_lat = bg.get("lat")
                bg_lon = bg.get("lon")
                if bg_lat is None or bg_lon is None:
                    continue
                min_d_osm = min(
                    (haversine(bg_lat, bg_lon, o_inf["lat"], o_inf["lon"]) for o_inf in osm_dict.values()),
                    default=9999.0,
                )
                is_bg_ga = bool(bg.get("is_ga", False))
                if min_d_osm <= (11.0 if is_bg_ga else 28.0):
                    continue
                bg_name = str(bg.get("name") or "").strip()
                if not bg_name:
                    continue
                bg_tok = clean_gate_token(bg_name)
                if bg_tok in existing_coh_tokens:
                    if is_bg_ga and not bg_name.upper().startswith("GA"):
                        bg_name = f"GA {bg_name}"
                        bg_tok = clean_gate_token(bg_name)
                    elif not is_bg_ga and not bg_name.upper().startswith("GATE"):
                        bg_name = f"GATE {bg_name}"
                        bg_tok = clean_gate_token(bg_name)
                    if bg_tok in existing_coh_tokens:
                        continue
                sp_term = _infer_spatial_terminal(bg_lat, bg_lon)
                if is_bg_ga and (not sp_term or sp_term in ("Main Apron", "Other")):
                    sp_term = "General Aviation Apron"
                else:
                    sp_term = infer_airport_stand_terminal(icao_u, bg_name, sp_term)
                sp_term_l_bg = (sp_term or "").lower()
                is_bg_ga_final = bool(
                    is_bg_ga
                    or any(
                        kw in sp_term_l_bg
                        for kw in (
                            "affaires", "general aviation", "executive", "vip",
                            "royal terminal", "royal pavilion", "amiri", "presidential",
                            "state terminal", "aramco", "jetex", "fbo", "private",
                        )
                    )
                )
                is_bg_cargo_final = bool(
                    bg.get("is_cargo", False)
                    or (("fret" in sp_term_l_bg or "cargo" in sp_term_l_bg) and "pax" not in sp_term_l_bg and "passenger" not in sp_term_l_bg and "charter" not in sp_term_l_bg)
                )
                al_set = sorted(list(bg.get("airlines") or []))
                g_bgl_info = {
                    "name": bg_name,
                    "raw_name": bg.get("name", bg_name),
                    "osm_ref": "",
                    "py_aircraft_types": [],
                    "wingspan": float(bg.get("wingspan", 20.0 if is_bg_ga_final else 36.0)),
                    "terminal": sp_term,
                    "type": bg.get("type", "STAND"),
                    "lat": bg_lat,
                    "lon": bg_lon,
                    "heading": bg.get("heading"),
                    "no_pushback": False,
                    "has_jetway": bool(bg.get("has_jetway", False)),
                    "is_cargo": is_bg_cargo_final,
                    "is_ga": is_bg_ga_final,
                    "is_military": bool(bg.get("is_military", False)),
                    "airlines": al_set,
                }
                existing_coh_tokens.add(bg_tok)
                coherent_db["ANY"].append(g_bgl_info)
                for a_c in al_set:
                    if a_c not in coherent_db:
                        coherent_db[a_c] = []
                    coherent_db[a_c].append(g_bgl_info)

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
            aircraft_icao = str(ac_block.get('icaocode') or '').strip().upper()
            aircraft_base = str(ac_block.get('base_type') or '').strip().upper()
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
                "aircraft": aircraft,
                "aircraft_icao": aircraft_icao,
                "aircraft_base": aircraft_base,
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
        if ac_block.get('wingspan') is not None:
            try:
                ws_override = float(ac_block.get('wingspan'))
                if 4.0 <= ws_override <= 95.0:
                    wingspan = ws_override
            except Exception:
                pass

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
        if not airline_norm and airline:
            airline_norm = resolve_airline_or_callsign_to_icao(airline)
        if not airline_norm and ofp_callsign:
            cs_prefix = re.match(r"^([A-Z]{3})\d", str(ofp_callsign).strip().upper())
            if cs_prefix:
                cand_al = normalize_airline_icao(cs_prefix.group(1))
                if cand_al in CARGO_AIRLINE_OPERATORS or cand_al in MILITARY_OPERATORS or cand_al in AIRLINE_FULL_NAMES:
                    airline_norm = cand_al
                    if not airline:
                        airline = cand_al

        sc_live_match_title = ""
        sc_chk_title = getattr(self, "simconnect_manager", None)
        if sc_chk_title and (sc_chk_title.connected or getattr(sc_chk_title, "user_title", "")):
            raw_t = str(getattr(sc_chk_title, "user_title", "") or "").strip()
            if str(ofp_id or "").startswith("LIVE_MSFS_"):
                sc_live_match_title = raw_t
            elif raw_t and aircraft_icao and len(aircraft_icao) >= 3:
                # Only cross-check SimConnect livery title against SimBrief OFP if same aircraft family
                fam_prefix = aircraft_icao[:3].upper()
                if fam_prefix in raw_t.upper() or (base_type and base_type[:3].upper() in raw_t.upper()):
                    sc_live_match_title = raw_t

        mil_flight_info = is_military_aircraft_or_flight(
            aircraft_icao, aircraft_name, base_type, airline_norm, ofp_callsign, aircraft_reg, wingspan, sim_title=sc_live_match_title
        )
        force_cargo_global = bool(self.config.settings.get("force_cargo_mode", False))
        is_military_flight_global = bool(mil_flight_info["is_military"] and not force_cargo_global)
        is_cargo_aircraft_global = is_freighter_aircraft(aircraft_icao, aircraft_name, sim_title=sc_live_match_title)
        builtin_cargo_global = airline_norm in CARGO_AIRLINE_OPERATORS
        is_cargo_carrier_global = bool(
            (is_cargo_aircraft_global or builtin_cargo_global or ofp_is_all_cargo or force_cargo_global)
            and not is_military_flight_global
        )

        ga_flight_info = is_ga_or_business_flight(
            aircraft_icao, aircraft_name, base_type, airline_norm, ofp_callsign, aircraft_reg, wingspan
        )
        if is_military_flight_global or is_cargo_carrier_global:
            ga_flight_info["is_ga"] = False
            ga_flight_info["category"] = ""
        if (
            ga_flight_info["is_ga"]
            and ac_block.get("wingspan") is None
            and aircraft_icao.upper() not in AIRCRAFT_WINGSPANS
            and base_type.upper() not in AIRCRAFT_WINGSPANS
        ):
            if ga_flight_info["is_light_ga"]:
                wingspan = 12.0
            elif ga_flight_info["is_bizjet"]:
                wingspan = 21.0
            else:
                wingspan = 14.5
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
            
            is_military_flight = is_military_flight_global
            is_heavy_mil = bool(mil_flight_info.get("is_heavy_mil"))
            is_fighter_mil = bool(mil_flight_info.get("is_fighter_mil"))
            is_cargo_carrier = is_cargo_carrier_global
            is_a380 = is_a380_aircraft(aircraft_icao, aircraft_name, base_type)
            ga_profile = ga_flight_info
            is_ga_flight = bool(ga_profile["is_ga"] and not is_cargo_carrier and not is_military_flight and not is_a380)
            
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
                        if r_dict.get("gate") == "GA RAMP":
                            if phase_mode == "arrival" and chart_d.get("aprons"):
                                best_ap = max(chart_d["aprons"], key=lambda ap: len(ap.get("points") or []))
                                ap_pts = best_ap.get("points") or []
                                if ap_pts:
                                    r_dict["lat"] = sum(p[0] for p in ap_pts) / len(ap_pts)
                                    r_dict["lon"] = sum(p[1] for p in ap_pts) / len(ap_pts)
                            stands_list = chart_d.setdefault("stands", [])
                            if not any(str(s.get("ref") or "").upper() == "GA RAMP" for s in stands_list):
                                stands_list.append({
                                    "ref": "GA RAMP",
                                    "lat": r_dict.get("lat"),
                                    "lon": r_dict.get("lon"),
                                    "heading": r_dict.get("heading"),
                                    "has_jetway": False,
                                    "is_ga": True,
                                    "terminal": r_dict.get("terminal", "GENERAL AVIATION APRON"),
                                    "airlines": [],
                                })
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
                            if exclude_ga_ramp and (osm_dict[ref].get("is_ga") or is_ga_ramp_gate(ref)) and not is_cargo_carrier and not is_ga_flight and not is_military_flight:
                                continue
                            filtered_refs.append(ref)
                        if filtered_refs:
                            available_refs = filtered_refs
                            
                    # Universal Military / Cargo / GA Rule for OSM Airports:
                    if is_military_flight:
                        mil_osm_refs = [
                            ref for ref in available_refs
                            if osm_dict[ref].get("is_military") or is_military_stand_gate(ref, "", "")
                        ]
                        if not mil_osm_refs:
                            mil_osm_refs = [
                                ref for ref in available_refs
                                if not osm_dict[ref].get("has_jetway", False)
                                and (
                                    ("cargo" in ref.lower() or "ramp" in ref.lower())
                                    if is_heavy_mil
                                    else (osm_dict[ref].get("is_ga") or is_ga_ramp_gate(ref) or "ramp" in ref.lower())
                                )
                            ]
                        if not mil_osm_refs:
                            mil_osm_refs = [ref for ref in available_refs if not osm_dict[ref].get("has_jetway", False)]
                        if mil_osm_refs:
                            available_refs = mil_osm_refs
                    elif is_cargo_carrier:
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
                    elif is_ga_flight:
                        ga_osm_refs = [
                            ref for ref in available_refs
                            if (osm_dict[ref].get("is_ga") or is_ga_ramp_gate(ref))
                            and not osm_dict[ref].get("has_jetway", False)
                        ]
                        if not ga_osm_refs:
                            ga_osm_refs = [
                                ref for ref in available_refs
                                if not osm_dict[ref].get("has_jetway", False)
                                and "cargo" not in ref.lower()
                            ]
                        if ga_osm_refs:
                            ga_osm_refs.sort(key=lambda r: abs(float(osm_dict[r].get("wingspan", 24.0)) - wingspan))
                            available_refs = ga_osm_refs[:max(5, min(12, len(ga_osm_refs)))]

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
                    if is_military_flight or osm_dict[selected_gate_ref].get("is_military"):
                        res["terminal"] = f"MILITARY APRON ({raw_t})" if raw_t and raw_t not in ("Main Apron", "Other") else "MILITARY APRON"
                        res["is_military"] = True
                    elif is_cargo_carrier:
                        res["terminal"] = f"CARGO APRON ({raw_t})" if raw_t and raw_t not in ("Main Apron", "Other") else "CARGO APRON"
                        res["is_cargo"] = True
                    elif is_ga_flight:
                        ga_hdr = "BUSINESS AVIATION APRON" if ga_profile.get("is_bizjet") else "GENERAL AVIATION APRON"
                        res["terminal"] = f"{ga_hdr} ({raw_t})" if raw_t and raw_t not in ("Main Apron", "Other") else ga_hdr
                        res["is_ga"] = True
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
                        res["type"] = "RAMP" if (is_cargo_carrier or is_military_flight) else "GATE"
                else:
                    if (
                        phase_mode == "departure"
                        and u_lat_self is not None
                        and u_lon_self is not None
                        and (
                            default_lat is None
                            or default_lon is None
                            or haversine(float(u_lat_self), float(u_lon_self), float(default_lat), float(default_lon)) <= 5000.0
                        )
                    ):
                        res["osm"] = True
                        res["gate"] = "MIL RAMP" if is_military_flight else ("CARGO RAMP" if is_cargo_carrier else "GA RAMP")
                        res["terminal"] = "MILITARY APRON" if is_military_flight else ("CARGO APRON" if is_cargo_carrier else "GENERAL AVIATION APRON")
                        res["is_military"] = bool(is_military_flight)
                        res["is_cargo"] = bool(is_cargo_carrier)
                        res["is_ga"] = bool(not is_military_flight and not is_cargo_carrier)
                        res["lat"] = float(u_lat_self)
                        res["lon"] = float(u_lon_self)
                        res["heading"] = sc_self.user_hdg if sc_self else None
                        res["no_pushback"] = True
                        res["gate_coords_found"] = True
                        res["max_wingspan"] = max(24.0, float(wingspan))
                        res["has_jetway"] = False
                        res["type"] = "RAMP"
                        res["error"] = None
                    elif is_ga_flight and default_lat is not None and default_lon is not None:
                        res["osm"] = True
                        res["gate"] = "GA RAMP"
                        res["terminal"] = "GENERAL AVIATION APRON"
                        res["is_ga"] = True
                        res["lat"] = float(default_lat)
                        res["lon"] = float(default_lon)
                        res["no_pushback"] = True
                        res["gate_coords_found"] = True
                        res["max_wingspan"] = max(24.0, float(wingspan))
                        res["has_jetway"] = False
                        res["type"] = "RAMP"
                        res["error"] = None
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
                
                exclude_keywords = (
                    "cargo", "military", " general aviation", "private", "prop",
                    "business aviation", "vip", "executive", "royal terminal",
                    "royal pavilion", "aramco", "jetex", "fbo",
                )
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

            def is_military_gate(g):
                return is_military_stand_gate(g['name'], g.get('terminal'), g.get('type'), bool(g.get('is_military')))

            def is_ga_or_biz_stand(g):
                if is_cargo_gate(g) or is_military_gate(g) or g.get('has_jetway'):
                    return False
                if g.get('is_ga'):
                    return True
                if is_ga_ramp_gate(g['name'], g.get('terminal'), g.get('type')):
                    return True
                g_als_norm = g.get('_norm_airlines') or set()
                if g_als_norm and (g_als_norm & BUSINESS_AVIATION_OPERATORS):
                    return True
                return False

            preferred_gates = []
            if is_military_flight:
                # Priority 1: Dedicated Military ("Mil") stands (BGL MIL_CARGO / MIL_COMBAT, GSX mil, OSM military)
                for g in compatible_gates:
                    if is_military_gate(g):
                        preferred_gates.append(g)
                # Priority 2: Fallback if airport has no "Mil" stands -> Cargo/Remote Ramp for heavy transports, GA/FBO Ramp for fighters
                if not preferred_gates:
                    if is_heavy_mil:
                        for g in compatible_gates:
                            if not g.get('has_jetway') and (is_cargo_gate(g) or (not is_passenger_gate(g) and not g.get('is_ga'))):
                                preferred_gates.append(g)
                    else:
                        for g in compatible_gates:
                            if is_ga_or_biz_stand(g):
                                preferred_gates.append(g)
                # Priority 3: Any stand/ramp without jetway
                if not preferred_gates:
                    for g in compatible_gates:
                        if not g.get('has_jetway'):
                            preferred_gates.append(g)
            elif is_cargo_carrier:
                # Priority 1: Explicit cargo gates
                for g in compatible_gates:
                    if is_cargo_gate(g):
                        preferred_gates.append(g)
                # Priority 2: Ramps / Stands without jetways that are NOT passenger, NOT military, NOT GA
                if not preferred_gates:
                    for g in compatible_gates:
                        if not is_passenger_gate(g) and not is_military_gate(g) and not g.get('is_ga') and not g.get('has_jetway'):
                            preferred_gates.append(g)
                # Priority 3: Any stand/ramp without jetway
                if not preferred_gates:
                    for g in compatible_gates:
                        if not g.get('has_jetway'):
                            preferred_gates.append(g)
            elif is_ga_flight:
                # Priority 1: Explicit GA / Business Aviation / FBO / Ramp stands without jetways
                for g in compatible_gates:
                    if is_ga_or_biz_stand(g):
                        preferred_gates.append(g)
                # Priority 2: Unassigned or Business-Aviation-only remote stands without jetways (not cargo, not military)
                if not preferred_gates:
                    for g in compatible_gates:
                        if (
                            not g.get('has_jetway')
                            and not is_cargo_gate(g)
                            and not is_military_gate(g)
                            and not ((g.get('_norm_airlines') or set()) - BUSINESS_AVIATION_OPERATORS)
                        ):
                            preferred_gates.append(g)
                # Priority 3: Any non-jetway stand (not cargo, not military)
                if not preferred_gates:
                    for g in compatible_gates:
                        if not g.get('has_jetway') and not is_cargo_gate(g) and not is_military_gate(g):
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
                
                # Check Cargo: exclude cargo gates ONLY if user requested exclude_cargo AND this is NOT a cargo/heavy-mil flight
                is_cargo = g.get('is_cargo') or "cargo" in name_lower or "cargo" in term_lower or "cargo" in g_type_lower
                if exclude_cargo and is_cargo and not is_cargo_carrier and not is_military_flight:
                    continue
                    
                # Check GA/Ramp/Military: exclude GA ramps ONLY if user requested exclude_ga_ramp AND this is NOT a cargo/GA/military flight
                is_ga_ramp = g.get('is_ga') or is_military_gate(g) or is_ga_ramp_gate(g['name'], g.get('terminal'), g.get('type'), is_cargo=is_cargo)
                if exclude_ga_ramp and is_ga_ramp and not is_cargo_carrier and not is_ga_flight and not is_military_flight:
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

                if not is_cargo_carrier and not is_ga_flight and not is_military_flight and ("remote" in g_term_l or g_term_l.startswith("parking")):
                    if not (is_user_lcc and not has_jw):
                        score -= 95.0

                # 3. Geopolitical & Customs / Schengen Zone Intelligence (Origin <-> Destination)
                if not is_cargo_carrier and not is_ga_flight and not is_military_flight:
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
                if is_military_flight:
                    if is_military_gate(g):
                        score += 650.0
                    elif is_heavy_mil and is_cargo_gate(g):
                        score += 320.0
                    elif not is_heavy_mil and is_ga_or_biz_stand(g):
                        score += 320.0
                    score += 180.0 if not has_jw else -480.0
                elif is_cargo_carrier:
                    if is_cargo_gate(g):
                        score += 500.0
                    score += 120.0 if not has_jw else -250.0
                elif is_ga_flight:
                    if is_ga_or_biz_stand(g):
                        score += 480.0
                    elif not has_jw and not (g_als - BUSINESS_AVIATION_OPERATORS):
                        score += 240.0
                    score += 150.0 if not has_jw else -550.0
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
                if is_ga_flight or (is_military_flight and is_fighter_mil):
                    ws_margin = g_ws - wingspan
                    if ws_margin <= 6.0:
                        score += 160.0
                    elif ws_margin <= 12.0:
                        score += 125.0
                    elif ws_margin <= 20.0:
                        score += 75.0
                    elif g_ws <= 36.5:
                        score += 25.0
                    elif g_ws <= 46.0:
                        score -= 90.0
                    else:
                        score -= 240.0
                elif wingspan < 30.0:
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

            is_mil_gate_flag = is_military_gate(selected_gate)
            is_cargo_gate_flag = (
                selected_gate.get('is_cargo')
                or "cargo" in selected_gate['name'].lower()
                or (selected_gate.get('type') == 'RAMP' and not is_ga_flight and not is_military_flight and not selected_gate.get('is_ga') and not is_mil_gate_flag)
            )
            if is_military_flight or is_mil_gate_flag:
                res["is_military"] = True
                res["is_mil_stand_tagged"] = bool(is_mil_gate_flag)
                if not raw_term or raw_term in ("Main Apron", "Other"):
                    res["terminal"] = "MILITARY APRON"
                elif "military" in raw_term.lower() or "mil" in raw_term.lower():
                    res["terminal"] = raw_term.upper()
                else:
                    res["terminal"] = f"MILITARY APRON ({raw_term})"
            elif is_cargo_carrier or is_cargo_gate_flag:
                res["is_cargo"] = True
                if not raw_term or raw_term in ("Main Apron", "Other"):
                    res["terminal"] = "CARGO APRON"
                elif raw_term.startswith("Zone"):
                    res["terminal"] = f"CARGO APRON ({raw_term})"
                else:
                    res["terminal"] = f"CARGO APRON - {raw_term}"
            elif is_ga_flight or selected_gate.get('is_ga'):
                res["is_ga"] = True
                apron_lbl = "BUSINESS AVIATION APRON" if ga_profile.get("is_bizjet") else "GENERAL AVIATION APRON"
                if not raw_term or raw_term in ("Main Apron", "Other", "General Aviation"):
                    res["terminal"] = apron_lbl
                elif "general aviation" in raw_term.lower() or "business aviation" in raw_term.lower() or "fbo" in raw_term.lower():
                    res["terminal"] = raw_term.upper()
                else:
                    res["terminal"] = f"{apron_lbl} ({raw_term})"
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

        if not airline:
            if is_military_flight_global:
                airline = "MIL"
            elif is_cargo_carrier_global:
                airline = "CAR"
            elif ga_flight_info.get("is_ga"):
                airline = "BIZ" if ga_flight_info.get("is_bizjet") else "GA"
            elif str(ofp_id or "").startswith("LIVE_MSFS_"):
                airline = "PAX"

        al_name = self.airline_names.get(airline, '')
        if not al_name:
            code_u = airline.upper().strip()
            if code_u == "GA":
                al_name = "General Aviation"
            elif code_u == "BIZ":
                al_name = "Business Aviation"
            elif code_u == "MIL":
                al_name = "Military Aviation"
            elif code_u == "CAR":
                al_name = "Cargo Operations"
            elif code_u == "PAX":
                al_name = "Commercial Passenger"
            elif code_u.startswith("AF") or code_u.startswith("VAF"):
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
            aircraft_wingspan=wingspan,
            is_ga_flight=bool(ga_flight_info.get("is_ga")),
            is_military_flight=bool(is_military_flight_global),
            is_cargo_flight=bool(is_cargo_carrier_global),
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
        elif (
            str(ofp_id or "").startswith("LIVE_MSFS_")
            and dep_data
            and sc_live
            and sc_live.connected
            and not getattr(sc_live, "in_menu", False)
            and sc_live.user_on_ground is True
            and sc_live.user_lat is not None
            and sc_live.user_lon is not None
            and float(sc_live.user_gs or 0.0) <= 15.0
        ):
            dep_c_lat = (dep_data.get("chart_data") or {}).get("center_lat") or dep_data.get("lat")
            dep_c_lon = (dep_data.get("chart_data") or {}).get("center_lon") or dep_data.get("lon")
            if (
                dep_c_lat is None
                or dep_c_lon is None
                or haversine(float(sc_live.user_lat), float(sc_live.user_lon), float(dep_c_lat), float(dep_c_lon)) <= 4500.0
            ):
                if is_military_flight_global:
                    _fb_ramp_name = "MIL RAMP"
                    _fb_term_name = "MILITARY APRON"
                elif is_cargo_carrier_global:
                    _fb_ramp_name = "CARGO RAMP"
                    _fb_term_name = "CARGO APRON"
                else:
                    _fb_ramp_name = "GA RAMP"
                    _fb_term_name = "GENERAL AVIATION APRON"
                locked_turnaround_stand = {
                    "gate": _fb_ramp_name,
                    "lat": float(sc_live.user_lat),
                    "lon": float(sc_live.user_lon),
                    "heading": sc_live.user_hdg,
                    "no_pushback": True,
                    "terminal": _fb_term_name,
                    "has_jetway": False,
                    "max_wingspan": max(24.0, float(wingspan)),
                    "reason": "msfs_live",
                }
                if dep_data.get("chart_data"):
                    st_list = dep_data["chart_data"].setdefault("stands", [])
                    if not any(str(s.get("ref") or "").upper() == _fb_ramp_name for s in st_list):
                        st_list.append({
                            "ref": _fb_ramp_name,
                            "lat": float(sc_live.user_lat),
                            "lon": float(sc_live.user_lon),
                            "heading": sc_live.user_hdg,
                            "has_jetway": False,
                            "is_ga": not (is_military_flight_global or is_cargo_carrier_global),
                            "is_military": bool(is_military_flight_global),
                            "is_cargo": bool(is_cargo_carrier_global),
                            "terminal": _fb_term_name,
                            "airlines": ["MIL"] if is_military_flight_global else (["CAR"] if is_cargo_carrier_global else []),
                        })

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
        # Ensure routing graphs for both origin and destination are pre-warmed on this worker thread
        if hasattr(self, "taxi_router") and self.taxi_router:
            for _ph_apt in (dep_data, arr_data):
                _ch = (_ph_apt or {}).get("chart_data")
                if isinstance(_ch, dict) and "_routing_graph" not in _ch:
                    try:
                        self.taxi_router._get_or_build_graph(_ch)
                    except Exception:
                        pass
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
            "is_ga_flight": bool(ga_flight_info.get("is_ga")),
            "ga_category": ga_flight_info.get("category", ""),
            "is_cargo_flight": bool(is_cargo_carrier_global),
            "is_military_flight": bool(is_military_flight_global),
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
        if hasattr(self, "taxi_router") and self.taxi_router:
            mc = getattr(self.taxi_router, "memory_cache", {}) or {}
            if icao_u in mc and isinstance(mc[icao_u], dict):
                charts_to_check.append(mc[icao_u])
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
                            "terminal": st.get("terminal"),
                            "has_jetway": st.get("has_jetway", False),
                            "is_ga": st.get("is_ga", False),
                            "wingspan": st.get("wingspan", 999.0)
                        }

        max_match_d = 65.0 if (best_stand and best_stand.get("is_ga")) else 45.0
        if best_stand and best_dist <= max_match_d:
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

    def get_live_msfs_aircraft_profile(self):
        """
        Extracts clean live aircraft metadata (ICAO type, title, registration, airline,
        physical wingspan in meters, and GA classification) from SimConnect.
        """
        sc = getattr(self, "simconnect_manager", None)
        if not sc or (
            not sc.connected
            and not getattr(sc, "user_title", "")
            and not getattr(sc, "user_atc_model", "")
            and getattr(sc, "user_sim_wingspan", None) is None
        ):
            return {
                "icao": "GA",
                "name": "LIVE MSFS AIRCRAFT",
                "registration": "",
                "airline": "",
                "wingspan": 14.0,
                "is_ga": True,
                "ga_category": "GA",
            }

        def _clean_sim_loc(raw_s):
            s = str(raw_s or "").strip()
            if not s:
                return ""
            s = re.sub(r"^TT:\s*", "", s, flags=re.IGNORECASE)
            s = re.sub(r"^ATCCOM\.(?:AC_MODEL|ATC_NAME)[_.\s]*", "", s, flags=re.IGNORECASE)
            s = re.sub(r"\.\d+\.text$", "", s, flags=re.IGNORECASE)
            return s.replace("_", " ").strip()

        raw_model = _clean_sim_loc(getattr(sc, "user_atc_model", ""))
        raw_type = _clean_sim_loc(getattr(sc, "user_atc_type", ""))
        raw_title = _clean_sim_loc(getattr(sc, "user_title", ""))
        raw_livery = _clean_sim_loc(getattr(sc, "user_livery_name", ""))
        raw_reg = str(getattr(sc, "user_atc_id", "") or "").strip().upper()
        raw_al = _clean_sim_loc(getattr(sc, "user_atc_airline", "")).upper()
        sim_ws = getattr(sc, "user_sim_wingspan", None)

        # Match and normalize ICAO aircraft code across model, title, and manufacturer type
        # (handles e.g. 'BOEING' + '738', 'BOEING 738 (AUA)', 'FENIXA320 CFM WF', 'PMDG 737-800')
        ac_icao = ""
        for cand_src in (
            f"{raw_type} {raw_model}".strip(),
            raw_model,
            raw_title,
            raw_type,
        ):
            norm_ic = self._normalize_aircraft_icao(cand_src, manufacturer_hint=raw_type)
            if norm_ic:
                ac_icao = norm_ic
                break
        if not ac_icao:
            m_mod = re.sub(r"[^A-Z0-9]", "", re.sub(r"\([^)]*\)", "", raw_model.upper()))
            if 3 <= len(m_mod) <= 5:
                ac_icao = m_mod

        disp_name = raw_title or (f"{raw_type} {raw_model}".strip()) or ac_icao or "MSFS AIRCRAFT"
        disp_name = re.sub(r"\s+", " ", disp_name).strip().upper()
        if len(disp_name) > 28 and ac_icao:
            disp_name = f"{raw_type.upper()} {ac_icao}".strip() if raw_type else ac_icao

        ws_m = float(sim_ws) if (sim_ws is not None and 4.0 <= float(sim_ws) <= 95.0) else AIRCRAFT_WINGSPANS.get(ac_icao, 14.0)
        al_code = resolve_airline_or_callsign_to_icao(raw_al) if raw_al else ""
        if not al_code and (raw_livery or raw_title):
            al_code = self._resolve_airline_from_livery_text(f"{raw_livery} {raw_title}")

        # Prefer explicit tail registration embedded in livery/title if present (avoids stale default ATC ID)
        liv_reg_match = re.search(
            r"\b((?:OO|OE|HB|PH|EC|EI|CS|OY|SE|LN|OH|SP|OK|HA|YR|LZ|SX|TC|9H|YL|ES|JA|HL|VH|ZK|RP|VT|HS|9V|9M|A6|A7|HZ|SU|RA|PT|PR|PP|LV|CC|XA)-[A-Z0-9]{2,5}|(?:F|D|G|I|B|C)-[A-Z]{4}|N[1-9][0-9]{0,4}[A-Z]{0,2})\b",
            f"{raw_livery} {raw_title}".upper()
        )
        if liv_reg_match:
            raw_reg = liv_reg_match.group(1).upper()

        mil_info = is_military_aircraft_or_flight(
            ac_icao, disp_name, ac_icao, al_code, raw_al, raw_reg, ws_m, sim_title=f"{raw_title} {raw_livery}".strip()
        )
        is_mil_live = bool(mil_info.get("is_military"))
        is_cargo_live = (not is_mil_live) and (
            is_freighter_aircraft(ac_icao, disp_name, sim_title=f"{raw_title} {raw_livery}".strip())
            or (al_code in CARGO_AIRLINE_OPERATORS)
        )

        if is_mil_live:
            is_ga_flag = False
            ga_cat = "MIL"
            if not al_code:
                al_code = "MIL"
        elif is_cargo_live:
            is_ga_flag = False
            ga_cat = "CARGO"
            if not al_code:
                al_code = "CAR"
        else:
            ga_info = is_ga_or_business_flight(
                ac_icao, disp_name, ac_icao, al_code, raw_reg, raw_reg, ws_m
            )
            # If physical wingspan from MSFS is < 26m and no commercial airline is set, treat as GA/Business
            is_ga_flag = bool(ga_info.get("is_ga") or (ws_m < 26.0 and not al_code))
            ga_cat = ga_info.get("category") or ("BIZ" if ws_m >= 15.5 else "GA")

        return {
            "icao": ac_icao or ("MIL" if is_mil_live else ("BIZ" if ga_cat == "BIZ" else "GA")),
            "name": disp_name,
            "registration": raw_reg,
            "airline": al_code,
            "wingspan": round(ws_m, 1),
            "is_ga": is_ga_flag,
            "is_military": is_mil_live,
            "is_cargo": is_cargo_live,
            "ga_category": ga_cat if (is_ga_flag or is_mil_live or is_cargo_live) else "",
        }

    def resolve_airport_coords_by_icao(self, icao):
        """
        Resolves (lat, lon, display_name) for any ICAO code, checking in-memory databases,
        disk caches, and falling back to OpenStreetMap Overpass/Nominatim for unlisted VFR airfields.
        """
        icao_u = str(icao or "").strip().upper()
        if not icao_u or len(icao_u) < 3:
            return None, None, ""
        cache_map = getattr(self, "_icao_coords_cache", None)
        if cache_map is None:
            self._icao_coords_cache = {}
            cache_map = self._icao_coords_cache
        if icao_u in cache_map:
            return cache_map[icao_u]

        # 1. Check in-memory stand databases
        coherent_map = getattr(self, "coherent_airports", {}) or {}
        for db in (coherent_map.get(icao_u), self.data.get(icao_u), self.builtin_data.get(icao_u)):
            if not db or not isinstance(db, dict):
                continue
            for g_list in db.values():
                if not isinstance(g_list, list):
                    continue
                for g in g_list:
                    if g.get("lat") is not None and g.get("lon") is not None:
                        lat_v, lon_v = float(g["lat"]), float(g["lon"])
                        nm = self.get_airport_display_name(icao_u, self.airport_names.get(icao_u, ""))
                        res = (lat_v, lon_v, nm)
                        cache_map[icao_u] = res
                        return res

        # 2. Check TaxiRouter memory & disk cache
        if hasattr(self, "taxi_router") and self.taxi_router:
            mc = getattr(self.taxi_router, "memory_cache", {}) or {}
            if icao_u in mc and isinstance(mc[icao_u], dict):
                cd = mc[icao_u]
                if cd.get("center_lat") is not None and cd.get("center_lon") is not None:
                    nm = self.get_airport_display_name(icao_u, self.airport_names.get(icao_u, ""))
                    res = (float(cd["center_lat"]), float(cd["center_lon"]), nm)
                    cache_map[icao_u] = res
                    return res

        # 3. Query Nominatim / Overpass for small VFR airfields (e.g. LFPN, LFPZ)
        try:
            from urllib.parse import quote
            ua_hdr = {"User-Agent": "GateFinder/2.0 (https://github.com/wildbill75/gsx-gatefinder)"}
            nom_url = f"https://nominatim.openstreetmap.org/search?q={quote(icao_u)}&format=jsonv2&extratags=1&limit=3"
            req = urllib.request.Request(nom_url, headers=ua_hdr)
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                arr = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if isinstance(arr, list):
                aero_arr = [
                    x for x in arr
                    if isinstance(x, dict) and (
                        x.get("category") == "aeroway"
                        or (x.get("extratags") or {}).get("icao") == icao_u
                    )
                ]
                arr = aero_arr or arr
            if not arr:
                nom_url2 = f"https://nominatim.openstreetmap.org/search?q={quote(icao_u + ' airport')}&format=jsonv2&limit=3"
                req2 = urllib.request.Request(nom_url2, headers=ua_hdr)
                with urllib.request.urlopen(req2, timeout=3.5) as resp2:
                    arr = json.loads(resp2.read().decode("utf-8", errors="ignore"))
            if isinstance(arr, list) and arr:
                item = arr[0]
                lat_v = float(item["lat"])
                lon_v = float(item["lon"])
                raw_nm = str(item.get("name") or item.get("display_name", "").split(",")[0] or icao_u).strip()
                self.airport_names[icao_u] = raw_nm
                res = (lat_v, lon_v, raw_nm)
                cache_map[icao_u] = res
                return res
        except Exception:
            pass

        return None, None, self.airport_names.get(icao_u, icao_u)

    def _distance_to_chart_airfield(self, u_lat, u_lon, ch_d):
        if not isinstance(ch_d, dict):
            return None
        bbox = ch_d.get("_airfield_bbox")
        if bbox is None:
            pts_lat = []
            pts_lon = []
            for r in (ch_d.get("runways") or ()):
                la1, lo1 = r.get("lat1"), r.get("lon1")
                la2, lo2 = r.get("lat2"), r.get("lon2")
                if la1 is not None and lo1 is not None:
                    pts_lat.append(float(la1))
                    pts_lon.append(float(lo1))
                if la2 is not None and lo2 is not None:
                    pts_lat.append(float(la2))
                    pts_lon.append(float(lo2))
            for s in (ch_d.get("stands") or ()):
                sla, slo = s.get("lat"), s.get("lon")
                if sla is not None and slo is not None:
                    pts_lat.append(float(sla))
                    pts_lon.append(float(slo))
            clat = ch_d.get("center_lat")
            clon = ch_d.get("center_lon")
            if clat is not None and clon is not None:
                pts_lat.append(float(clat))
                pts_lon.append(float(clon))
            if pts_lat:
                c_la = float(clat) if clat is not None else (min(pts_lat) + max(pts_lat)) * 0.5
                c_lo = float(clon) if clon is not None else (min(pts_lon) + max(pts_lon)) * 0.5
                bbox = (min(pts_lat), max(pts_lat), min(pts_lon), max(pts_lon), c_la, c_lo)
                ch_d["_airfield_bbox"] = bbox
            else:
                return None
        min_la, max_la, min_lo, max_lo, c_la, c_lo = bbox
        if u_lat < min_la - 0.045 or u_lat > max_la + 0.045 or u_lon < min_lo - 0.065 or u_lon > max_lo + 0.065:
            return None
        d_min = haversine(u_lat, u_lon, c_la, c_lo)
        for r in (ch_d.get("runways") or ()):
            la1, lo1 = r.get("lat1"), r.get("lon1")
            la2, lo2 = r.get("lat2"), r.get("lon2")
            if la1 is not None and lo1 is not None and la2 is not None and lo2 is not None:
                fla1, flo1, fla2, flo2 = float(la1), float(lo1), float(la2), float(lo2)
                d1 = haversine(u_lat, u_lon, fla1, flo1)
                if d1 < d_min:
                    d_min = d1
                d2 = haversine(u_lat, u_lon, fla2, flo2)
                if d2 < d_min:
                    d_min = d2
                dm = haversine(u_lat, u_lon, (fla1 + fla2) * 0.5, (flo1 + flo2) * 0.5)
                if dm < d_min:
                    d_min = dm
        if d_min > 1800.0:
            for s in (ch_d.get("stands") or ()):
                sla, slo = s.get("lat"), s.get("lon")
                if sla is not None and slo is not None:
                    fsla, fslo = float(sla), float(slo)
                    if abs(fsla - u_lat) <= 0.032 and abs(fslo - u_lon) <= 0.045:
                        ds = haversine(u_lat, u_lon, fsla, fslo)
                        if ds < d_min:
                            d_min = ds
                            if d_min <= 400.0:
                                break
        return (d_min, c_la, c_lo)

    def _get_builtin_airport_spatial_index(self):
        b_db = self.builtin_data
        if not b_db or not isinstance(b_db, dict):
            return ()
        init_ready = bool(getattr(self, "_init_done", False))
        cached = getattr(self, "_fast_airport_coords_index", None)
        if cached is not None and init_ready and getattr(self, "_fast_airport_coords_len", -1) == len(b_db):
            return cached
        try:
            items_snap = list(b_db.items())
        except RuntimeError:
            return cached or ()
        idx = []
        for icao_k, al_map in items_snap:
            if not isinstance(al_map, dict):
                continue
            try:
                al_vals = list(al_map.values())
            except RuntimeError:
                continue
            min_la = 999.0
            max_la = -999.0
            min_lo = 999.0
            max_lo = -999.0
            found = False
            for g_list in al_vals:
                if not isinstance(g_list, list):
                    continue
                for g in g_list:
                    la = g.get("lat")
                    lo = g.get("lon")
                    if la is not None and lo is not None:
                        fla, flo = float(la), float(lo)
                        if fla < min_la:
                            min_la = fla
                        if fla > max_la:
                            max_la = fla
                        if flo < min_lo:
                            min_lo = flo
                        if flo > max_lo:
                            max_lo = flo
                        found = True
            if found:
                idx.append((
                    str(icao_k).strip().upper(),
                    min_la - 0.042,
                    max_la + 0.042,
                    min_lo - 0.060,
                    max_lo + 0.060,
                    min_la,
                    max_la,
                    min_lo,
                    max_lo,
                    (min_la + max_la) * 0.5,
                    (min_lo + max_lo) * 0.5,
                ))
        res_tuple = tuple(idx)
        if init_ready:
            self._fast_airport_coords_index = res_tuple
            self._fast_airport_coords_len = len(items_snap)
        return res_tuple

    def detect_live_msfs_airport(self, lat=None, lon=None):
        """
        Detects the airport (including small VFR/GA airfields like LFPN or LFPZ) where the
        aircraft is currently located in MSFS based on GPS coordinates.
        """
        sc = getattr(self, "simconnect_manager", None)
        u_lat = lat if lat is not None else (sc.user_lat if sc else None)
        u_lon = lon if lon is not None else (sc.user_lon if sc else None)
        if u_lat is None or u_lon is None:
            return None
        try:
            u_lat = float(u_lat)
            u_lon = float(u_lon)
        except (ValueError, TypeError):
            return None

        gps_cache = getattr(self, "_live_gps_airport_cache", None)
        if gps_cache is None:
            self._live_gps_airport_cache = {}
            gps_cache = self._live_gps_airport_cache
        grid_key = (round(u_lat, 3), round(u_lon, 3))
        if grid_key in gps_cache:
            return gps_cache[grid_key]

        best_icao = None
        best_dist = 999999.0
        best_lat = None
        best_lon = None
        best_name = ""

        # 0. Ultra-fast check against active flight's departure/arrival chart geometry (covers distant runways like EHAM 18R)
        fd_cur = self.current_flight_data
        if isinstance(fd_cur, dict):
            for ph_key in ("departure", "arrival"):
                apt_d = fd_cur.get(ph_key)
                if not isinstance(apt_d, dict) or not apt_d.get("icao"):
                    continue
                ch_d = apt_d.get("chart_data")
                hit = self._distance_to_chart_airfield(u_lat, u_lon, ch_d) if ch_d else None
                if hit is not None and hit[0] < best_dist:
                    best_dist = hit[0]
                    best_icao = str(apt_d["icao"]).strip().upper()
                    best_lat = hit[1]
                    best_lon = hit[2]

        # 1a. Check coherent_airports and already-loaded GSX profiles (without triggering lazy disk loads)
        coherent_map = getattr(self, "coherent_airports", {}) or {}
        loaded_gsx_items = dict.items(self.data) if isinstance(self.data, dict) else ()
        for src_items in (coherent_map.items(), loaded_gsx_items):
            for icao_k, al_map in src_items:
                if not isinstance(al_map, dict):
                    continue
                sample_g = None
                for g_list in al_map.values():
                    if isinstance(g_list, list) and g_list:
                        for g in g_list:
                            if g.get("lat") is not None and g.get("lon") is not None:
                                sample_g = g
                                break
                    if sample_g:
                        break
                if not sample_g:
                    continue
                glat, glon = float(sample_g["lat"]), float(sample_g["lon"])
                if abs(glat - u_lat) > 0.06 or abs(glon - u_lon) > 0.08:
                    continue
                d_m = haversine(u_lat, u_lon, glat, glon)
                if d_m < best_dist:
                    best_dist = d_m
                    best_icao = str(icao_k).strip().upper()
                    best_lat = glat
                    best_lon = glon

        # 1b. Fast flat spatial index scan of builtin_data (6,668 airports, < 0.2ms)
        near_mega_candidates = []
        for (
            icao_u, pad_min_la, pad_max_la, pad_min_lo, pad_max_lo,
            min_la, max_la, min_lo, max_lo, clat, clon
        ) in self._get_builtin_airport_spatial_index():
            if pad_min_la <= u_lat <= pad_max_la and pad_min_lo <= u_lon <= pad_max_lo:
                clamp_la = min_la if u_lat < min_la else (max_la if u_lat > max_la else u_lat)
                clamp_lo = min_lo if u_lon < min_lo else (max_lo if u_lon > max_lo else u_lon)
                d_m = haversine(u_lat, u_lon, clamp_la, clamp_lo)
                if d_m < best_dist:
                    best_dist = d_m
                    best_icao = icao_u
                    best_lat = clat
                    best_lon = clon
            elif abs(clat - u_lat) <= 0.095 and abs(clon - u_lon) <= 0.13:
                near_mega_candidates.append(icao_u)

        # 1c. Also check TaxiRouter memory_cache (and local disk cache for nearby mega-airports with distant runways)
        if hasattr(self, "taxi_router") and self.taxi_router:
            mc = getattr(self.taxi_router, "memory_cache", {}) or {}
            for icao_k, ch_d in list(mc.items()):
                hit = self._distance_to_chart_airfield(u_lat, u_lon, ch_d)
                if hit is not None and hit[0] < best_dist:
                    best_dist = hit[0]
                    best_icao = str(icao_k).strip().upper()
                    best_lat = hit[1]
                    best_lon = hit[2]
            if best_dist > 4500.0 and near_mega_candidates:
                for cand_ic in near_mega_candidates:
                    if cand_ic in mc:
                        continue
                    try:
                        disk_ch = self.taxi_router._load_from_disk(cand_ic)
                    except Exception:
                        disk_ch = None
                    if disk_ch:
                        hit = self._distance_to_chart_airfield(u_lat, u_lon, disk_ch)
                        if hit is not None and hit[0] < best_dist:
                            best_dist = hit[0]
                            best_icao = cand_ic
                            best_lat = hit[1]
                            best_lon = hit[2]

        if best_icao and best_dist <= 4500.0:
            best_name = self.get_airport_display_name(best_icao, self.airport_names.get(best_icao, ""))
            res = {
                "icao": best_icao,
                "name": best_name or best_icao,
                "lat": best_lat,
                "lon": best_lon,
                "dist_m": round(best_dist, 1),
            }
            gps_cache[grid_key] = res
            return res

        # 2. Fallback: query OpenStreetMap bounding box for VFR/GA airfields not in builtin_data (e.g. LFPN, LFPZ)
        try:
            bbox_url = (
                f"https://api.openstreetmap.org/api/0.6/map.json?"
                f"bbox={u_lon - 0.015:.5f},{u_lat - 0.012:.5f},{u_lon + 0.015:.5f},{u_lat + 0.012:.5f}"
            )
            req = urllib.request.Request(bbox_url, headers={"User-Agent": "GateFinder/2.0 (https://github.com/wildbill75/gsx-gatefinder)"})
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                osm_data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            elements = osm_data.get("elements") or []
            nodes_by_id = {
                el["id"]: (float(el["lat"]), float(el["lon"]))
                for el in elements
                if el.get("type") == "node" and "lat" in el and "lon" in el
            }
            for el in elements:
                tags = el.get("tags") or {}
                icao_tag = str(tags.get("icao") or tags.get("ref:icao") or "").strip().upper()
                if not (3 <= len(icao_tag) <= 4 and icao_tag.isalnum()):
                    continue
                el_lat, el_lon = u_lat, u_lon
                if "lat" in el and "lon" in el:
                    el_lat, el_lon = float(el["lat"]), float(el["lon"])
                elif el.get("nodes"):
                    coords_n = [nodes_by_id[nid] for nid in el["nodes"] if nid in nodes_by_id]
                    if coords_n:
                        el_lat = sum(c[0] for c in coords_n) / len(coords_n)
                        el_lon = sum(c[1] for c in coords_n) / len(coords_n)
                d_m = haversine(u_lat, u_lon, el_lat, el_lon)
                if d_m < best_dist:
                    best_dist = d_m
                    best_icao = icao_tag
                    best_lat = el_lat
                    best_lon = el_lon
                    best_name = str(tags.get("name") or tags.get("name:en") or icao_tag).strip()
            if best_icao and best_dist <= 5000.0:
                if best_name:
                    self.airport_names[best_icao] = best_name
                if not hasattr(self, "_icao_coords_cache"):
                    self._icao_coords_cache = {}
                self._icao_coords_cache[best_icao] = (best_lat, best_lon, best_name or best_icao)
                res = {
                    "icao": best_icao,
                    "name": best_name or best_icao,
                    "lat": best_lat,
                    "lon": best_lon,
                    "dist_m": round(best_dist, 1),
                }
                gps_cache[grid_key] = res
                return res
        except Exception:
            pass

        gps_cache[grid_key] = None
        return None

    def _resolve_airline_from_livery_text(self, raw_text):
        """
        Extracts a 3-letter commercial/cargo/military ICAO airline code from an MSFS livery
        name or aircraft title (e.g. 'Brussels Airlines OO-SNC' -> 'BEL', 'Air France' -> 'AFR').
        """
        if not raw_text:
            return ""
        txt_u = re.sub(r"[^A-Z0-9]+", " ", str(raw_text).upper()).strip()
        if not txt_u:
            return ""

        lookup = getattr(self, "_livery_airline_phrases", None)
        if lookup is None:
            phrases = {}
            for k, v in (getattr(self, "airline_names", None) or {}).items():
                if isinstance(k, str) and len(k) == 3 and k.isalpha() and v:
                    clean_v = re.sub(r"\s*\(.*?\)", "", str(v).upper())
                    clean_v = re.sub(r"[^A-Z0-9]+", " ", clean_v).strip()
                    if len(clean_v) >= 4 and clean_v not in ("GENERAL AVIATION", "BUSINESS AVIATION", "CARGO OPERATIONS", "MILITARY AVIATION"):
                        phrases[clean_v] = k.upper()
            for k, v in AIRLINE_FULL_NAMES.items():
                if isinstance(k, str) and len(k) == 3 and k.isalpha() and v:
                    clean_v = re.sub(r"\s*\(.*?\)", "", str(v).upper())
                    clean_v = re.sub(r"[^A-Z0-9]+", " ", clean_v).strip()
                    if len(clean_v) >= 4:
                        phrases[clean_v] = k.upper()
            phrases.update({
                "BRUSSELS AIRLINES": "BEL", "BRUSSELS": "BEL",
                "AIR FRANCE": "AFR", "AIRFRANCE": "AFR",
                "BRITISH AIRWAYS": "BAW", "SPEEDBIRD": "BAW",
                "LUFTHANSA": "DLH", "LUFTHANSA CITYLINE": "CLH",
                "KLM ROYAL DUTCH": "KLM", "KLM CITYHOPPER": "KLM", "KLM": "KLM",
                "EASYJET": "EZY", "EASY JET": "EZY",
                "RYANAIR": "RYR", "SWISS": "SWR", "EDELWEISS": "EDW",
                "AUSTRIAN": "AUA", "EUROWINGS": "EWG", "DISCOVER AIRLINES": "OCN",
                "IBERIA": "IBE", "VUELING": "VLG", "VOLOTEA": "VOE", "AIR EUROPA": "AEA",
                "TAP AIR PORTUGAL": "TAP", "TAP PORTUGAL": "TAP",
                "TRANSAVIA FRANCE": "TVF", "TRANSAVIA": "TRA",
                "WIZZ AIR": "WZZ", "WIZZAIR": "WZZ",
                "SAS SCANDINAVIAN": "SAS", "SCANDINAVIAN": "SAS",
                "FINNAIR": "FIN", "NORWEGIAN": "NAX", "AER LINGUS": "EIN",
                "ITA AIRWAYS": "ITY", "AEGEAN": "AEE", "LOT POLISH": "LOT",
                "TURKISH AIRLINES": "THY", "PEGASUS": "PGT", "SUNEXPRESS": "SXS",
                "JET2": "EXS", "TUI AIRWAYS": "TOM", "TUIFLY": "TUI",
                "VIRGIN ATLANTIC": "VIR", "CORSAIR": "CRL", "FRENCH BEE": "FBU", "AIR CARAIBES": "FWI",
                "EMIRATES": "UAE", "QATAR AIRWAYS": "QTR", "ETIHAD": "ETD", "SAUDIA": "SVA", "FLYDUBAI": "FDB",
                "DELTA AIR LINES": "DAL", "DELTA": "DAL",
                "AMERICAN AIRLINES": "AAL", "UNITED AIRLINES": "UAL", "SOUTHWEST": "SWA",
                "JETBLUE": "JBU", "ALASKA AIRLINES": "ASA", "SPIRIT AIRLINES": "NKS", "FRONTIER": "FFT",
                "AIR CANADA": "ACA", "WESTJET": "WJA", "AIR TRANSAT": "TSC",
                "SINGAPORE AIRLINES": "SIA", "CATHAY PACIFIC": "CPA", "QANTAS": "QFA",
                "ALL NIPPON": "ANA", "JAPAN AIRLINES": "JAL", "KOREAN AIR": "KAL", "EVA AIR": "EVA",
                "FEDEX": "FDX", "FEDERAL EXPRESS": "FDX", "CARGOLUX": "CLX", "AEROLOGIC": "BOX",
            })
            lookup = sorted(
                [(re.compile(rf"\b{re.escape(p)}\b"), code) for p, code in phrases.items() if len(p) >= 3],
                key=lambda item: len(item[0].pattern),
                reverse=True,
            )
            self._livery_airline_phrases = lookup

        padded = f" {txt_u} "
        for pat, code in lookup:
            if pat.search(padded):
                return code
        return ""

    @staticmethod
    def _normalize_aircraft_icao(raw_str, manufacturer_hint=""):
        """
        Normalizes MSFS / SimBrief aircraft strings into a canonical ICAO aircraft type code.
        Strips parenthetical livery suffixes like '(AUA)', manufacturer/studio prefixes like 'BOEING',
        'AIRBUS', 'PMDG', 'FENIX', and resolves bare 3-digit or hyphenated series (e.g. '738' -> 'B738',
        'BOEING 738 (AUA)' -> 'B738', 'AIRBUS 320' -> 'A320', '737-800' -> 'B738', '190' -> 'E190').
        """
        s = str(raw_str or "").strip().upper()
        if not s:
            return ""
        # Strip parenthetical or bracketed suffixes e.g. (AUA), (WL), [PMDG]
        s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", s)
        s = s.replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip()
        if not s or s in ("GA", "BIZ", "MIL", "CAR", "PAX", "MSFS AIRCRAFT", "UNKNOWN"):
            return ""

        hint_u = re.sub(r"\s+", " ", str(manufacturer_hint or "").upper()).strip()
        combined_mfr = f"{hint_u} {s}"

        # 1. Exact canonical check if already a clean known code
        s_alnum = re.sub(r"[^A-Z0-9]", "", s)
        known_sets = (
            AIRCRAFT_WINGSPANS,
            GA_LIGHT_AIRCRAFT_TYPES,
            BUSINESS_JET_AIRCRAFT_TYPES,
            MILITARY_FIGHTER_TRAINER_TYPES,
            MILITARY_TRANSPORT_HEAVY_TYPES,
        )
        if 2 <= len(s_alnum) <= 5 and any(s_alnum in ks for ks in known_sets):
            return s_alnum

        # 2. Strip full manufacturer & addon developer prefixes/words to isolate model core
        strip_phrases = (
            "THE BOEING COMPANY", "MCDONNELL DOUGLAS", "DE HAVILLAND CANADA", "DE HAVILLAND",
            "BRITISH AEROSPACE", "FLIGHTSIM STUDIO", "JUST FLIGHT", "CAPTAIN SIM", "BLACK SQUARE",
            "WORKING TITLE", "QUALITYWINGS", "FLYBYWIRE", "LATINVFR",
            "BOEING", "AIRBUS", "EMBRAER", "BOMBARDIER", "DOUGLAS", "CESSNA", "TEXTRON",
            "BEECHCRAFT", "HAWKER", "CIRRUS", "DAHER", "SOCATA", "PILATUS", "DASSAULT",
            "GULFSTREAM", "ANTONOV", "ILYUSHIN", "SUKHOI", "TUPOLEV", "SAAB", "FOKKER",
            "DORNIER", "LOCKHEED", "PMDG", "FENIX", "INIBUILDS", "FBW", "IFLY", "LVFR",
            "HORIZON", "HEADWIND", "AEROSOFT", "JUSTFLIGHT", "FSS", "TFDI", "LEONARDO",
            "MADDOG", "CARENADO", "A2A", "ASOBO", "MICROSOFT",
        )
        core = f" {s} "
        for ph in strip_phrases:
            core = re.sub(rf"\b{re.escape(ph)}\b", " ", core)
        core = re.sub(r"\s+", " ", core).strip()

        # 3. Specific multi-token & hyphenated family rules (evaluated before generic regexes)
        spec_patterns = (
            (r"\b(?:A319\s*NEO|319\s*NEO|A19N|19N)\b", "A19N"),
            (r"\b(?:A320\s*NEO|320\s*NEO|A32NX|A20N|20N)\b", "A20N"),
            (r"\b(?:A321\s*(?:NEO|NX|LR|XLR)|321\s*(?:NEO|NX|LR|XLR)|A21N|21N)\b", "A21N"),
            (r"\b(?:A?220[-\s]*100|CS100|BCS1|A221)\b", "BCS1"),
            (r"\b(?:A?220[-\s]*300|CS300|BCS3|A223|A220)\b", "BCS3"),
            (r"\b(?:A?300[-\s]*600\w*|A306\w*)\b", "A306"),
            (r"\b(?:A?330[-\s]*800|330[-\s]*800|A338)\b", "A338"),
            (r"\b(?:A?330[-\s]*900|330[-\s]*900|A330\s*NEO|A339)\b", "A339"),
            (r"\b(?:A?330[-\s]*2\d\d|330[-\s]*2\d\d|A332)\b", "A332"),
            (r"\b(?:A?330[-\s]*3\d\d|330[-\s]*3\d\d|A333)\b", "A333"),
            (r"\b(?:A?340[-\s]*3\d\d|340[-\s]*3\d\d|A343)\b", "A343"),
            (r"\b(?:A?340[-\s]*6\d\d|340[-\s]*6\d\d|A346)\b", "A346"),
            (r"\b(?:A?350[-\s]*1000|350[-\s]*1000|A35K|35K)\b", "A35K"),
            (r"\b(?:A?350[-\s]*9\d\d|350[-\s]*9\d\d|A359|A350)\b", "A359"),
            (r"\b(?:A?380(?:[-\s]*8\d\d)?|A388)\b", "A388"),
            (r"\b(?:B?737\s*MAX\s*7|737[-\s]*7\s*MAX|B37M|37M)\b", "B37M"),
            (r"\b(?:B?737\s*MAX\s*8|737[-\s]*8\b(?!\d)|737\s*MAX|738M|B38M|38M|MAX\s*8)\b", "B38M"),
            (r"\b(?:B?737\s*MAX\s*9|737[-\s]*9\b(?!\d)|739M|B39M|39M|MAX\s*9)\b", "B39M"),
            (r"\b(?:B?737\s*MAX\s*10|737[-\s]*10\b|B3XM|3XM|MAX\s*10)\b", "B3XM"),
            (r"\b(?:B?717(?:[-\s]*2\d\d)?|B712)\b", "B712"),
            (r"\b(?:B?737[-\s]*6\d\d|B736)\b", "B736"),
            (r"\b(?:B?737[-\s]*7\d\d|B737|73G|73W)\b", "B737"),
            (r"\b(?:B?737[-\s]*8\d\d\w*|B738\w*|738W|73H)\b", "B738"),
            (r"\b(?:B?737[-\s]*9\d\d\w*|B739\w*|73J)\b", "B739"),
            (r"\b(?:B?747[-\s]*8\w*|B748\w*|748I|748F)\b", "B748"),
            (r"\b(?:B?747[-\s]*4\d\d\w*|B744\w*|744F)\b", "B744"),
            (r"\b(?:B?757[-\s]*3\d\d|B753)\b", "B753"),
            (r"\b(?:B?757(?:[-\s]*2\d\d\w*)?|B752\w*)\b", "B752"),
            (r"\b(?:B?767[-\s]*4\d\d|B764)\b", "B764"),
            (r"\b(?:B?767[-\s]*2\d\d\w*|B762\w*)\b", "B762"),
            (r"\b(?:B?767(?:[-\s]*3\d\d\w*)?|B763\w*)\b", "B763"),
            (r"\b(?:B?777[-\s]*200\s*LR|B77L|77L)\b", "B77L"),
            (r"\b(?:B?777[-\s]*F\b|777F|B77F|77F)\b", "B77F"),
            (r"\b(?:B?777[-\s]*300\s*ER|777W|B77W|77W)\b", "B77W"),
            (r"\b(?:B?777[-\s]*3\d\d|B773)\b", "B773"),
            (r"\b(?:B?777[-\s]*2\d\d\w*|B772)\b", "B772"),
            (r"\b(?:B?787[-\s]*10|B78X|78X)\b", "B78X"),
            (r"\b(?:B?787[-\s]*9|B789)\b", "B789"),
            (r"\b(?:B?787[-\s]*8|B788)\b", "B788"),
            (r"\b(?:E190[-\s]*E2|190[-\s]*E2|E290)\b", "E290"),
            (r"\b(?:E195[-\s]*E2|195[-\s]*E2|E295)\b", "E295"),
            (r"\b(?:ERJ?[-\s]*170|E[-\s]*170)\b", "E170"),
            (r"\b(?:ERJ?[-\s]*175|E[-\s]*175)\b", "E175"),
            (r"\b(?:ERJ?[-\s]*190|E[-\s]*190)\b", "E190"),
            (r"\b(?:ERJ?[-\s]*195|E[-\s]*195)\b", "E195"),
            (r"\b(?:CRJ[-\s]*1000|CRJX)\b", "CRJX"),
            (r"\b(?:CRJ[-\s]*900|CRJ9)\b", "CRJ9"),
            (r"\b(?:CRJ[-\s]*(?:550|700)|CRJ7)\b", "CRJ7"),
            (r"\b(?:CRJ[-\s]*200|CRJ2)\b", "CRJ2"),
            (r"\b(?:ATR[-\s]*72[-\s]*600|ATR[-\s]*72|AT76)\b", "AT76"),
            (r"\b(?:ATR[-\s]*42[-\s]*600|ATR[-\s]*42|AT46)\b", "AT46"),
            (r"\b(?:DASH\s*8[-\s]*400|DHC[-\s]*8[-\s]*400|Q400|DH8D)\b", "DH8D"),
            (r"\b(?:MD[-\s]*11\w*|MD11\w*)\b", "MD11"),
            (r"\b(?:TBM[-\s]*9\d\d|TBM9)\b", "TBM9"),
            (r"\b(?:PC[-\s]*12|PC12)\b", "PC12"),
            (r"\b(?:PC[-\s]*24|PC24)\b", "PC24"),
        )
        for pat, canon in spec_patterns:
            if re.search(pat, core) or re.search(pat, s):
                return canon

        # 4. Embedded 4-char ICAO codes inside concatenated titles (e.g. FENIXA320, PMDGB738, INIA306)
        embedded_pat = re.compile(
            r"(A318|A319|A320|A321|A19N|A20N|A21N|A221|A223|BCS1|BCS3|A306|A310|A332|A333|A338|A339|"
            r"A343|A346|A359|A35K|A388|B712|B733|B734|B735|B736|B737|B738|B739|B37M|B38M|B39M|B3XM|"
            r"B744|B748|B752|B753|B762|B763|B764|B772|B77L|B773|B77W|B77F|B788|B789|B78X|MD11|"
            r"E135|E145|E170|E175|E190|E195|E290|E295|CRJ2|CRJ7|CRJ9|CRJX|AT45|AT46|AT72|AT75|AT76|"
            r"DH8D|C152|C172|C182|C208|C25C|C700|SR22|SF50|DA40|DA42|DA62|TBM9|PC12|PC24)"
        )
        m_emb = embedded_pat.search(s)
        if m_emb:
            return m_emb.group(1)

        # 5. Bare 3-character commercial/regional series codes (e.g. MSFS user_atc_model='738', '320', '190', '789')
        bare3_map = {
            "318": "A318", "319": "A319", "320": "A320", "321": "A321",
            "221": "BCS1", "223": "BCS3", "306": "A306", "310": "A310",
            "332": "A332", "333": "A333", "338": "A338", "339": "A339",
            "343": "A343", "346": "A346", "359": "A359", "350": "A359", "388": "A388", "380": "A388",
            "712": "B712", "717": "B712", "722": "B722",
            "733": "B733", "734": "B734", "735": "B735",
            "736": "B736", "737": "B737", "738": "B738", "739": "B739",
            "744": "B744", "747": "B744", "748": "B748",
            "752": "B752", "753": "B753", "757": "B752",
            "762": "B762", "763": "B763", "764": "B764", "767": "B763",
            "772": "B772", "773": "B773", "777": "B77W",
            "788": "B788", "789": "B789", "787": "B789",
            "170": "E170", "175": "E175", "190": "E190", "195": "E195",
        }
        # Check leading model token (e.g. '738' from 'BOEING 738' or '320-214' -> '320')
        for tok in re.findall(r"\b([A-Z0-9]{3,5})\b", core):
            if any(tok in ks for ks in known_sets):
                return tok
            if tok in bare3_map:
                if tok in ("152", "172", "182", "208"):
                    continue
                return bare3_map[tok]
            if "CESSNA" in combined_mfr and tok in ("150", "152", "172", "182", "206", "208", "210", "700"):
                cand_c = f"C{tok}"
                if any(cand_c in ks for ks in known_sets):
                    return cand_c

        m_lead3 = re.match(r"^(\d{3})(?:[-\s]\d+)?\b", core)
        if m_lead3 and m_lead3.group(1) in bare3_map:
            return bare3_map[m_lead3.group(1)]

        return ""

    @staticmethod
    def _are_aircraft_types_compatible(live_icao, sb_icao, sb_name="", live_ws=36.0, sb_ws=36.0, live_is_ga=False, sb_is_ga=False, live_name=""):
        """
        Determines whether the spawned MSFS aircraft type matches the SimBrief OFP aircraft type.
        Normalizes MSFS & SimBrief strings first (ignoring livery tags like '(AUA)' and manufacturer
        prefixes like 'BOEING') and treats CEO/NEO & sub-series equivalents (e.g. A320/A20N, B738/B38M)
        as compatible, while flagging distinct families/subtypes (e.g. A320 vs A359, A320 vs B738).
        """
        generic_tags = {"", "GA", "BIZ", "MIL", "CAR", "PAX"}
        raw_l = str(live_icao or "").strip().upper()
        raw_s = str(sb_icao or "").strip().upper()

        norm_l = (
            GateFinderBackend._normalize_aircraft_icao(raw_l)
            or GateFinderBackend._normalize_aircraft_icao(live_name)
        )
        norm_s = (
            GateFinderBackend._normalize_aircraft_icao(raw_s)
            or GateFinderBackend._normalize_aircraft_icao(sb_name)
        )

        l_u = norm_l or (re.sub(r"\([^)]*\)", "", raw_l).strip() if raw_l not in generic_tags else "")
        s_u = norm_s or (re.sub(r"\([^)]*\)", "", raw_s).strip() if raw_s not in generic_tags else "")

        if l_u not in generic_tags and s_u not in generic_tags:
            if l_u == s_u:
                return True
            equiv_groups = (
                {"A318"},
                {"A319", "A19N"},
                {"A320", "A20N"},
                {"A321", "A21N"},
                {"A221", "BCS1"},
                {"A223", "BCS3"},
                {"A332", "A330"},
                {"A333", "A330"},
                {"A338", "A330"},
                {"A339", "A330"},
                {"A359", "A350"},
                {"A35K", "A350"},
                {"A388", "A380"},
                {"B737", "B37M"},
                {"B738", "B38M"},
                {"B739", "B39M", "B3XM"},
                {"B744", "B748", "B747"},
                {"B752", "B753", "B757"},
                {"B762", "B763", "B764", "B767"},
                {"B772", "B77L", "B777"},
                {"B773", "B77W", "B777"},
                {"B788", "B789", "B78X", "B787"},
                {"AT72", "AT75", "AT76"},
                {"E190", "E290"},
                {"E195", "E295"},
            )
            for grp in equiv_groups:
                if l_u in grp and s_u in grp:
                    return True
            if l_u in AIRCRAFT_EQUIVALENT_FAMILIES and s_u in AIRCRAFT_EQUIVALENT_FAMILIES[l_u]:
                return True
            return False

        if live_is_ga != sb_is_ga and abs(float(live_ws or 36.0) - float(sb_ws or 36.0)) >= 4.0:
            return False
        if abs(float(live_ws or 36.0) - float(sb_ws or 36.0)) >= 6.5:
            return False
        return True

    def dismiss_simbrief_msfs_mismatch(self, mismatch_key):
        if not hasattr(self, "_dismissed_airport_mismatches"):
            self._dismissed_airport_mismatches = set()
        if mismatch_key:
            self._dismissed_airport_mismatches.add(str(mismatch_key))
        self.pending_simbrief_mismatch = None
        self._mismatch_check_memo = None

    def check_simbrief_vs_msfs_mismatch(self):
        """
        Compares the currently loaded (or latest SimBrief) flight plan (origin -> destination & aircraft)
        against the aircraft's actual on-tarmac state in MSFS AFTER clicking 'Start Flight'.
        """
        sc = getattr(self, "simconnect_manager", None)
        if (
            not sc
            or not sc.connected
            or getattr(sc, "in_menu", False)
            or sc.user_on_ground is not True
            or sc.user_lat is None
            or sc.user_lon is None
            or float(sc.user_gs or 0.0) > 10.0
        ):
            self.pending_simbrief_mismatch = None
            return None

        cam_st = getattr(sc, "user_camera_state", None)
        if cam_st is not None and (cam_st == 11 or (12 <= cam_st <= 20) or cam_st >= 22):
            self.pending_simbrief_mismatch = None
            return None

        stable_dur = float(getattr(sc, "tarmac_stable_duration", 0.0) or 0.0)
        if stable_dur < 1.0:
            return None

        u_lat = float(sc.user_lat)
        u_lon = float(sc.user_lon)

        # Extra safety against MSFS 2020/2024 default KBFI (Boeing Field, Seattle) staging coordinates
        if 47.510 <= u_lat <= 47.550 and -122.325 <= u_lon <= -122.285:
            if cam_st != 2 or stable_dur < 15.0:
                return None

        fd = self.current_flight_data
        dep_icao = ""
        arr_icao = ""
        ofp_id = "NO_OFP"
        sb_ac_name = ""
        cur_ac_type = ""
        sb_ws = 36.0
        sb_is_ga = False
        near_expected_airport = False
        peek_only = False

        if fd:
            dep = fd.get("departure") or {}
            arr = fd.get("arrival") or {}
            dep_icao = str(dep.get("icao") or "").strip().upper()
            arr_icao = str(arr.get("icao") or "").strip().upper()
            ofp_id = str(fd.get("ofp_id") or "")
            sb_ac_name = str(fd.get("aircraft") or "").strip()
            cur_ac_type = str(fd.get("aircraft_type") or "").strip().upper()
            sb_ws = float(fd.get("aircraft_wingspan") or 36.0)
            sb_is_ga = bool(fd.get("is_ga_flight", False))

            already_departed = bool(dep_icao and self.taxi_router.dep_runway_entered.get(dep_icao))
            valid_apts = (dep, arr) if (already_departed or str(ofp_id).startswith("LIVE_MSFS_")) else (dep,)
            for apt in valid_apts:
                alat = apt.get("lat")
                alon = apt.get("lon")
                if (alat is None or alon is None) and apt.get("chart_data"):
                    alat = apt["chart_data"].get("center_lat")
                    alon = apt["chart_data"].get("center_lon")
                if alat is not None and alon is not None:
                    if haversine(u_lat, u_lon, float(alat), float(alon)) <= 8500.0:
                        near_expected_airport = True
                        break
                if apt.get("chart_data"):
                    ch_hit = self._distance_to_chart_airfield(u_lat, u_lon, apt["chart_data"])
                    if ch_hit is not None and ch_hit[0] <= 3200.0:
                        near_expected_airport = True
                        break
        else:
            sb_user = str(self.config.settings.get("simbrief_username") or "").strip()
            if sb_user:
                now_p = time.time()
                cached_pk = getattr(self, "_cached_mismatch_sb_peek", None)
                if cached_pk is None or (now_p - cached_pk[0]) >= 25.0 or cached_pk[1] != sb_user:
                    pk_data = self.peek_latest_simbrief_ofp(sb_user)
                    self._cached_mismatch_sb_peek = (now_p, sb_user, pk_data)
                else:
                    pk_data = cached_pk[2]
                if isinstance(pk_data, dict) and pk_data.get("origin"):
                    peek_only = True
                    ofp_id = str(pk_data.get("ofp_id") or "PEEK_OFP")
                    dep_icao = str(pk_data.get("origin") or "").strip().upper()
                    arr_icao = str(pk_data.get("destination") or "").strip().upper()
                    sb_ac_name = str(pk_data.get("aircraft") or pk_data.get("aircraft_icao") or "").strip()
                    cur_ac_type = str(pk_data.get("aircraft_icao") or pk_data.get("aircraft_base") or "").strip().upper()
                    sb_ws = float(AIRCRAFT_WINGSPANS.get(cur_ac_type, 36.0))
                    sb_is_ga = bool(cur_ac_type in GA_LIGHT_AIRCRAFT_TYPES or cur_ac_type in BUSINESS_JET_AIRCRAFT_TYPES)

        ac_prof = self.get_live_msfs_aircraft_profile()
        has_live_ac_meta = bool(
            getattr(sc, "user_title", "")
            or getattr(sc, "user_atc_model", "")
            or getattr(sc, "user_sim_wingspan", None) is not None
        )
        aircraft_mismatch = False
        if (fd or peek_only) and has_live_ac_meta:
            live_is_ga = bool(ac_prof.get("is_ga", False))
            live_ws = float(ac_prof.get("wingspan") or sb_ws)
            live_ac_icao = str(ac_prof.get("icao") or "").strip().upper()
            live_ac_name = str(ac_prof.get("name") or "").strip()
            if str(ofp_id).startswith("LIVE_MSFS_"):
                if live_ac_icao and cur_ac_type and not self._are_aircraft_types_compatible(
                    live_ac_icao, cur_ac_type, sb_ac_name, live_ws, sb_ws, live_is_ga, sb_is_ga, live_name=live_ac_name
                ):
                    aircraft_mismatch = True
            else:
                if not self._are_aircraft_types_compatible(
                    live_ac_icao, cur_ac_type, sb_ac_name, live_ws, sb_ws, live_is_ga, sb_is_ga, live_name=live_ac_name
                ):
                    aircraft_mismatch = True

        if near_expected_airport and not aircraft_mismatch:
            self.pending_simbrief_mismatch = None
            return None

        dismissed = getattr(self, "_dismissed_airport_mismatches", set())
        memo_key = (
            round(u_lat, 4),
            round(u_lon, 4),
            ofp_id,
            dep_icao,
            arr_icao,
            sb_ac_name,
            cur_ac_type,
            round(sb_ws, 1),
            sb_is_ga,
            peek_only,
            has_live_ac_meta,
            str(ac_prof.get("icao") or ""),
            str(ac_prof.get("airline") or ""),
            round(float(ac_prof.get("wingspan") or 0.0), 1),
            bool(ac_prof.get("is_ga", False)),
            cam_st == 2,
            stable_dur >= 15.0,
            bool(getattr(self, "_init_done", False)),
            len(getattr(self, "coherent_airports", ()) or ()),
            len(dismissed),
        )
        prev_memo = getattr(self, "_mismatch_check_memo", None)
        if prev_memo is not None and prev_memo[0] == memo_key:
            self.pending_simbrief_mismatch = prev_memo[1]
            return prev_memo[1]

        live_apt = self.detect_live_msfs_airport(u_lat, u_lon)
        if not live_apt or not live_apt.get("icao"):
            self._mismatch_check_memo = (memo_key, None)
            self.pending_simbrief_mismatch = None
            return None

        live_icao = str(live_apt["icao"]).strip().upper()

        # Check if parked at a known stand
        live_stand_info = self.detect_live_msfs_parked_stand(
            live_icao,
            default_lat=live_apt.get("lat"),
            default_lon=live_apt.get("lon"),
            aircraft_wingspan=ac_prof.get("wingspan"),
            resolve_mars_variant=False,
        )
        live_stand_name = live_stand_info.get("gate") if isinstance(live_stand_info, dict) else None
        if live_icao == "KBFI" and dep_icao != "KBFI" and arr_icao != "KBFI":
            if cam_st != 2 or stable_dur < 15.0 or not live_stand_name:
                self._mismatch_check_memo = (memo_key, None)
                self.pending_simbrief_mismatch = None
                return None

        if fd:
            already_dep = bool(dep_icao and self.taxi_router.dep_runway_entered.get(dep_icao))
            valid_icaos = (dep_icao, arr_icao) if (already_dep or str(ofp_id).startswith("LIVE_MSFS_")) else (dep_icao,)
            airport_mismatch = bool(not dep_icao or live_icao not in valid_icaos)
        elif peek_only:
            airport_mismatch = bool(live_icao != dep_icao)
        else:
            airport_mismatch = True

        if not airport_mismatch and not aircraft_mismatch:
            self._mismatch_check_memo = (memo_key, None)
            self.pending_simbrief_mismatch = None
            return None

        if airport_mismatch and aircraft_mismatch:
            m_reason = "both"
        elif aircraft_mismatch:
            m_reason = "aircraft"
        else:
            m_reason = "airport"

        mismatch_key = f"{ofp_id}|{dep_icao}|{arr_icao}|{live_icao}|{ac_prof.get('icao') or ''}"
        if mismatch_key in dismissed:
            self._mismatch_check_memo = (memo_key, None)
            self.pending_simbrief_mismatch = None
            return None

        res_mismatch = {
            "mismatch_key": mismatch_key,
            "mismatch_reason": m_reason,
            "peek_only": peek_only,
            "ofp_id": ofp_id,
            "live_icao": live_icao,
            "live_name": live_apt.get("name") or live_icao,
            "live_stand": live_stand_name or "",
            "live_lat": live_apt.get("lat"),
            "live_lon": live_apt.get("lon"),
            "simbrief_origin": dep_icao,
            "simbrief_dest": arr_icao or dep_icao,
            "simbrief_aircraft": sb_ac_name,
            "simbrief_aircraft_icao": cur_ac_type,
            "live_aircraft": ac_prof,
        }
        self._mismatch_check_memo = (memo_key, res_mismatch)
        self.pending_simbrief_mismatch = res_mismatch
        return res_mismatch

    def load_live_msfs_flight(self, origin_icao, dest_icao="", progress_callback=None):
        """
        Loads a Direct Live MSFS Flight without requiring a matching SimBrief OFP,
        using the live aircraft telemetry from SimConnect and resolving airport stands/charts
        for `origin_icao` and `dest_icao` (defaults to `origin_icao` for local flights).
        """
        orig_u = str(origin_icao or "").strip().upper()
        dest_u = str(dest_icao or "").strip().upper() or orig_u

        orig_lat, orig_lon, orig_name = self.resolve_airport_coords_by_icao(orig_u)
        if orig_lat is None or orig_lon is None:
            sc = getattr(self, "simconnect_manager", None)
            if sc and sc.user_lat is not None and sc.user_lon is not None:
                orig_lat, orig_lon = float(sc.user_lat), float(sc.user_lon)

        if dest_u == orig_u:
            dest_lat, dest_lon, dest_name = orig_lat, orig_lon, orig_name
        else:
            dest_lat, dest_lon, dest_name = self.resolve_airport_coords_by_icao(dest_u)

        ac_prof = self.get_live_msfs_aircraft_profile()
        ac_icao = ac_prof.get("icao") or "GA"
        ac_name = ac_prof.get("name") or ac_icao
        ac_reg = ac_prof.get("registration") or ""
        ac_al = ac_prof.get("airline") or ""
        ac_ws = ac_prof.get("wingspan") or 14.0

        synthetic_ofp = {
            "origin": {
                "icao_code": orig_u,
                "name": orig_name or orig_u,
                "pos_lat": str(orig_lat) if orig_lat is not None else "",
                "pos_long": str(orig_lon) if orig_lon is not None else "",
                "plan_rwy": "",
            },
            "destination": {
                "icao_code": dest_u,
                "name": dest_name or dest_u,
                "pos_lat": str(dest_lat) if dest_lat is not None else "",
                "pos_long": str(dest_lon) if dest_lon is not None else "",
                "plan_rwy": "",
            },
            "params": {
                "request_id": f"LIVE_MSFS_{orig_u}_{dest_u}",
                "time_generated": str(int(time.time())),
            },
            "general": {
                "icao_airline": ac_al,
                "airline": ac_al,
                "flight_number": "",
            },
            "atc": {
                "callsign": ac_al if (ac_al and ac_al != ac_reg) else "",
            },
            "aircraft": {
                "icaocode": ac_icao,
                "base_type": ac_icao,
                "name": ac_name,
                "reg": ac_reg,
                "engines": "",
                "wingspan": ac_ws,
            },
        }
        self.pending_simbrief_mismatch = None
        return self.get_flight_data(
            username="",
            _mock_data=synthetic_ofp,
            turnaround_keep_gate=True,
            progress_callback=progress_callback,
        )

    def get_candidate_departure_stand(
        self,
        origin_icao,
        default_lat=None,
        default_lon=None,
        prev_flight_snapshot=None,
        fresh_dep_chart=None,
        aircraft_wingspan=None,
        is_ga_flight=None,
        is_military_flight=None,
        is_cargo_flight=None,
    ):
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

        # If the user is currently on the ground in MSFS at a different airport (> 9 km from `origin_icao`),
        # do NOT prompt to keep a historical turnaround stand at `origin_icao` (let the MSFS vs SimBrief mismatch modal handle it).
        sc_chk = getattr(self, "simconnect_manager", None)
        if (
            sc_chk
            and sc_chk.connected
            and not getattr(sc_chk, "in_menu", False)
            and sc_chk.user_on_ground is True
            and sc_chk.user_lat is not None
            and sc_chk.user_lon is not None
        ):
            chk_lat, chk_lon = default_lat, default_lon
            if (chk_lat is None or chk_lon is None) and fresh_dep_chart:
                chk_lat = fresh_dep_chart.get("center_lat")
                chk_lon = fresh_dep_chart.get("center_lon")
            if chk_lat is not None and chk_lon is not None:
                if haversine(float(sc_chk.user_lat), float(sc_chk.user_lon), float(chk_lat), float(chk_lon)) > 9000.0:
                    return None

        def _is_compatible_turnaround_stand(cand_dict):
            if not cand_dict or not cand_dict.get("gate"):
                return False
            _, _, g_meta = self.resolve_stand_in_airport_db(
                icao_u,
                cand_dict["gate"],
                fallback_lat=cand_dict.get("lat"),
                fallback_lon=cand_dict.get("lon"),
            )
            st_ws = float(
                (g_meta or {}).get("wingspan")
                or cand_dict.get("max_wingspan")
                or 999.0
            )
            if aircraft_wingspan is not None and st_ws < float(aircraft_wingspan) - 0.3:
                mars_alt = self.resolve_mars_stand_variant_for_aircraft(
                    icao_u,
                    cand_dict["gate"],
                    gate_lat=cand_dict.get("lat"),
                    gate_lon=cand_dict.get("lon"),
                    aircraft_wingspan=aircraft_wingspan,
                )
                if not mars_alt or float(mars_alt.get("wingspan") or 0.0) < float(aircraft_wingspan) - 0.3:
                    return False
            st_jw = bool(
                (g_meta or {}).get("has_jetway")
                if (g_meta and "has_jetway" in g_meta)
                else cand_dict.get("has_jetway", False)
            )
            st_term = str((g_meta or {}).get("terminal") or cand_dict.get("terminal") or "")
            st_type = str((g_meta or {}).get("type") or "")
            st_mil = is_military_stand_gate(
                cand_dict["gate"],
                st_term,
                st_type,
                bool((g_meta or {}).get("is_military")),
            )
            st_cargo = bool(
                (g_meta or {}).get("is_cargo")
                if (g_meta and "is_cargo" in g_meta)
                else is_cargo_ramp_gate(cand_dict["gate"], st_term, st_type)
            )
            if is_military_flight is not None:
                if is_military_flight and (st_jw or not (st_mil or st_cargo or not st_jw)):
                    return False
                if is_military_flight and not st_mil:
                    # Only keep non-mil stand if airport has no military stands at all AND it's not a jetway gate
                    return False
                if (not is_military_flight) and st_mil:
                    return False
            if is_cargo_flight is not None:
                if is_cargo_flight and not st_cargo:
                    return False
                if (not is_cargo_flight) and (not is_military_flight) and st_cargo:
                    return False
            if is_ga_flight is not None:
                st_ga = bool(
                    (g_meta or {}).get("is_ga")
                    if (g_meta and "is_ga" in g_meta)
                    else is_ga_ramp_gate(cand_dict["gate"], st_term, st_type)
                )
                if is_ga_flight and st_jw:
                    return False
                if (not is_ga_flight) and st_ga:
                    return False
            return True

        # 2 & 3. Previous in-memory flight data (arrival at `origin_icao` OR same departure `origin_icao`)
        fd_prev = prev_flight_snapshot if prev_flight_snapshot is not None else self.current_flight_data
        if fd_prev:
            for ph, r_tag in (("arrival", "turnaround_arrival"), ("departure", "same_departure")):
                apt = fd_prev.get(ph) or {}
                if str(apt.get("icao") or "").strip().upper() == icao_u:
                    g_val = str(apt.get("gate") or "").strip()
                    if g_val and g_val != "N/A":
                        cand = {
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
                        if _is_compatible_turnaround_stand(cand):
                            return cand

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
                            cand = {"gate": s_arr_g, "reason": "turnaround_arrival"}
                            if _is_compatible_turnaround_stand(cand):
                                return cand
                    if str(saved.get("origin") or "").strip().upper() == icao_u:
                        s_dep_g = str(saved.get("dep_gate") or "").strip()
                        if s_dep_g and s_dep_g != "N/A":
                            cand = {"gate": s_dep_g, "reason": "same_departure"}
                            if _is_compatible_turnaround_stand(cand):
                                return cand
                    by_icao = saved.get("last_stands_by_icao")
                    if isinstance(by_icao, dict) and icao_u in by_icao:
                        entry = by_icao[icao_u]
                        if isinstance(entry, dict) and (time.time() - float(entry.get("timestamp") or 0) <= 24 * 3600):
                            eg = str(entry.get("gate") or "").strip()
                            if eg and eg != "N/A":
                                cand = {
                                    "gate": eg,
                                    "lat": entry.get("lat"),
                                    "lon": entry.get("lon"),
                                    "reason": entry.get("reason", "turnaround_arrival")
                                }
                                if _is_compatible_turnaround_stand(cand):
                                    return cand
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
            dep = self.current_flight_data.get("departure") or {}
            arr = self.current_flight_data.get("arrival") or {}
            now_ts = time.time()
            session_sig = (
                p_path,
                self.current_flight_data.get("ofp_id"),
                dep.get("icao"),
                arr.get("icao"),
                self.current_flight_data.get("aircraft"),
                self.current_flight_data.get("airline"),
                dep.get("gate"),
                dep.get("gate_source"),
                dep.get("lat"),
                dep.get("lon"),
                dep.get("selected_runway"),
                dep.get("atc_runway"),
                dep.get("atc_runway_source"),
                arr.get("gate"),
                arr.get("gate_source"),
                arr.get("lat"),
                arr.get("lon"),
                arr.get("selected_runway"),
                arr.get("atc_runway"),
                arr.get("atc_runway_source"),
                tuple(sorted(self.taxi_router.dep_runway_entered.items())),
                tuple(sorted(self.taxi_router.arr_vacated_runway.items())),
                tuple(sorted((str(k), str(v)) for k, v in self.taxi_router.locked_arrival_exit.items())),
            )
            if (
                session_sig == getattr(self, "_last_saved_session_sig", None)
                and (now_ts - getattr(self, "_last_saved_session_ts", 0.0)) < 300.0
                and os.path.exists(p_path)
            ):
                return

            io_lock = getattr(self, "_session_io_lock", None)
            if io_lock is None:
                self._session_io_lock = threading.RLock()
                io_lock = self._session_io_lock

            with io_lock:
                cached_stands = getattr(self, "_cached_last_stands_by_icao", None)
                last_stands_by_icao = {}
                if isinstance(cached_stands, dict) and os.path.exists(p_path):
                    for k_icao, v_st in cached_stands.items():
                        if isinstance(v_st, dict) and (now_ts - float(v_st.get("timestamp") or 0) <= 24 * 3600):
                            last_stands_by_icao[k_icao] = v_st
                elif os.path.exists(p_path):
                    try:
                        with open(p_path, "r", encoding="utf-8") as rf:
                            prev_saved = json.load(rf)
                        if isinstance(prev_saved, dict) and isinstance(prev_saved.get("last_stands_by_icao"), dict):
                            for k_icao, v_st in prev_saved["last_stands_by_icao"].items():
                                if isinstance(v_st, dict) and (now_ts - float(v_st.get("timestamp") or 0) <= 24 * 3600):
                                    last_stands_by_icao[k_icao] = v_st
                    except Exception:
                        pass

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
                self._cached_last_stands_by_icao = dict(last_stands_by_icao)

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
                self._last_saved_session_sig = session_sig
                self._last_saved_session_ts = now_ts
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
                                s_src_u = s_src.upper()
                                batc_on = bool(hasattr(self, "interop_hub") and self.interop_hub and self.interop_hub.batc_watcher.is_process_running())
                                si_on = bool(hasattr(self, "interop_hub") and self.interop_hub and self.interop_hub.si_watcher.is_process_running())
                                if "LIVE" in s_src_u or "PARKED" in s_src_u:
                                    s_src = "GateFinder"
                                elif "BEYOND" in s_src_u and not batc_on:
                                    s_src = "GateFinder"
                                elif "SAYINTENTIONS" in s_src_u and not si_on:
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
                s_atc_src = str(saved.get(f"{prefix}_atc_runway_source") or "").strip()
                s_atc_src_u = s_atc_src.upper()
                batc_on = bool(hasattr(self, "interop_hub") and self.interop_hub and self.interop_hub.batc_watcher.is_process_running())
                si_on = bool(hasattr(self, "interop_hub") and self.interop_hub and self.interop_hub.si_watcher.is_process_running())
                atc_src_alive = bool(
                    s_atc_src
                    and (not ("BEYOND" in s_atc_src_u and not batc_on))
                    and (not ("SAYINTENTIONS" in s_atc_src_u and not si_on))
                )
                if atc_src_alive:
                    if saved.get(f"{prefix}_atc_runway"):
                        apt["atc_runway"] = saved[f"{prefix}_atc_runway"]
                    apt["atc_runway_source"] = s_atc_src
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
                candidates = []
                for al_list in db.values():
                    for g in al_list:
                        g_tok = clean_gate_token(g.get("name", ""))
                        r_tok = clean_gate_token(g.get("raw_name", ""))
                        o_tok = clean_gate_token(g.get("osm_ref", ""))
                        if bgl_type_stripped_tok and (
                            g_tok == bgl_type_stripped_tok or r_tok == bgl_type_stripped_tok or o_tok == bgl_type_stripped_tok
                        ):
                            candidates.append(g)
                            continue
                        if num_only and (g_tok == num_only or r_tok == num_only or o_tok == num_only):
                            candidates.append(g)
                            continue
                        if is_pure_num_target:
                            g_num = re.sub(r'^[A-Z]+', '', g_tok) if g_tok else ""
                            r_num = re.sub(r'^[A-Z]+', '', r_tok) if r_tok else ""
                            if g_num == target_tok or r_num == target_tok:
                                candidates.append(g)
                if candidates:
                    if fallback_lat is not None and fallback_lon is not None and len(candidates) > 1:
                        candidates.sort(
                            key=lambda c: haversine(float(fallback_lat), float(fallback_lon), float(c["lat"]), float(c["lon"]))
                            if (c.get("lat") is not None and c.get("lon") is not None) else 999999.0
                        )
                    best_g = candidates[0]
                    coords = (best_g["lat"], best_g["lon"]) if (best_g.get("lat") is not None and best_g.get("lon") is not None) else None
                    return best_g["name"], coords, best_g

        # 2. Search cached chart_data stands (OSM + BGL merged stands)
        if self.current_flight_data:
            for ph in ("departure", "arrival"):
                apt = self.current_flight_data.get(ph) or {}
                if apt.get("icao") == icao_u and apt.get("chart_data"):
                    st_candidates = []
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
                            st_candidates.append(st)
                    if st_candidates:
                        if fallback_lat is not None and fallback_lon is not None and len(st_candidates) > 1:
                            st_candidates.sort(
                                key=lambda s: haversine(float(fallback_lat), float(fallback_lon), float(s["lat"]), float(s["lon"]))
                                if (s.get("lat") is not None and s.get("lon") is not None) else 999999.0
                            )
                        best_st = st_candidates[0]
                        s_ref = str(best_st.get("ref") or "").strip()
                        return s_ref, (best_st.get("lat"), best_st.get("lon")), {
                            "name": s_ref,
                            "lat": best_st.get("lat"),
                            "lon": best_st.get("lon"),
                            "has_jetway": best_st.get("has_jetway", True),
                            "wingspan": best_st.get("wingspan", 999.0)
                        }

        # 2b. If GPS coordinates (fallback_lat/lon) were provided by SayIntentions, match nearest stand within 35m
        if fallback_lat is not None and fallback_lon is not None:
            best_prox_name = None
            best_prox_coords = None
            best_prox_meta = None
            best_prox_dist = 35.0
            for db in (coherent_map.get(icao_u), self.data.get(icao_u), self.builtin_data.get(icao_u)):
                if not db:
                    continue
                for al_list in db.values():
                    for g in al_list:
                        if g.get("lat") is not None and g.get("lon") is not None:
                            d = haversine(float(fallback_lat), float(fallback_lon), float(g["lat"]), float(g["lon"]))
                            if d < best_prox_dist:
                                best_prox_dist = d
                                best_prox_name = g["name"]
                                best_prox_coords = (g["lat"], g["lon"])
                                best_prox_meta = g
            if not best_prox_name and self.current_flight_data:
                for ph in ("departure", "arrival"):
                    apt = self.current_flight_data.get(ph) or {}
                    if apt.get("icao") == icao_u and apt.get("chart_data"):
                        for st in (apt["chart_data"].get("stands") or []):
                            if st.get("lat") is not None and st.get("lon") is not None:
                                d = haversine(float(fallback_lat), float(fallback_lon), float(st["lat"]), float(st["lon"]))
                                if d < best_prox_dist:
                                    best_prox_dist = d
                                    s_ref = str(st.get("ref") or "").strip()
                                    best_prox_name = s_ref
                                    best_prox_coords = (st.get("lat"), st.get("lon"))
                                    best_prox_meta = {
                                        "name": s_ref,
                                        "lat": st.get("lat"),
                                        "lon": st.get("lon"),
                                        "has_jetway": st.get("has_jetway", True),
                                        "wingspan": st.get("wingspan", 999.0)
                                    }
            if best_prox_name:
                return best_prox_name, best_prox_coords, best_prox_meta

        # 3. Fallback to cleaned label and provided coordinates
        pretty_label = re.sub(r'^.*?\b(GATE|STAND|PARKING|RAMP|DOCK|SPOT|BAY)[\s_\-]+', '', str(raw_gate).strip(), flags=re.IGNORECASE)
        pretty_label = re.sub(r'^(GATE|STAND|PARKING|RAMP|DOCK|SPOT|BAY)[\s_\-]*', '', pretty_label, flags=re.IGNORECASE)
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
            apt["custom_taxi_mode"] = False
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

    def set_custom_taxi_via(self, phase, action=None, toggle_twy=None, remove_twy=None, via_list=None):
        """
        Interactive Taxiway Route Builder:
          - action='auto': resets to automatic A* routing (custom_taxi_mode=False, atc_taxi_via=None)
          - action='clear': clears the taxi route so the pilot can click taxiway badges from scratch (custom_taxi_mode=True, atc_taxi_via=[])
          - toggle_twy='W2': when clicking a taxiway badge on the Lido map (starts fresh custom route on 1st click, then appends/toggles)
          - remove_twy='W2': when clicking a taxiway pill in the ATC TAXI CLEARANCE sidebar to remove it from the route
          - via_list=['W2', 'LJS']: sets an explicit custom taxiway list
        """
        if not self.current_flight_data or phase not in ("departure", "arrival"):
            return None
        apt = self.current_flight_data.get(phase)
        if not apt:
            return None

        act = str(action or "").strip().lower()
        if act == "auto":
            apt["custom_taxi_mode"] = False
            apt["atc_taxi_via"] = None
        elif act == "clear":
            apt["custom_taxi_mode"] = True
            apt["atc_taxi_via"] = []
        elif via_list is not None:
            apt["custom_taxi_mode"] = True
            apt["atc_taxi_via"] = [str(x).strip().upper() for x in via_list if str(x).strip()]
        elif remove_twy:
            twy_u = str(remove_twy).strip().upper()
            twy_norm = re.sub(r'[\s_\-]+', '', twy_u)
            if apt.get("custom_taxi_mode") and isinstance(apt.get("atc_taxi_via"), list):
                cur_list = list(apt["atc_taxi_via"])
            else:
                cur_list = list((apt.get("taxi_route") or {}).get("taxiway_sequence") or apt.get("atc_taxi_via") or [])
            apt["custom_taxi_mode"] = True
            apt["atc_taxi_via"] = [t for t in cur_list if re.sub(r'[\s_\-]+', '', str(t).upper()) != twy_norm]
        elif toggle_twy:
            twy_u = str(toggle_twy).strip().upper()
            twy_norm = re.sub(r'[\s_\-]+', '', twy_u)
            if not apt.get("custom_taxi_mode") or not isinstance(apt.get("atc_taxi_via"), list):
                apt["custom_taxi_mode"] = True
                apt["atc_taxi_via"] = [twy_u]
            else:
                cur_list = list(apt["atc_taxi_via"])
                existing_norms = [re.sub(r'[\s_\-]+', '', str(t).upper()) for t in cur_list]
                if twy_norm in existing_norms:
                    apt["atc_taxi_via"] = [t for t in cur_list if re.sub(r'[\s_\-]+', '', str(t).upper()) != twy_norm]
                else:
                    if apt.get("chart_data") and apt.get("lat") is not None:
                        u_lat = self.simconnect_manager.user_lat if hasattr(self, "simconnect_manager") else None
                        u_lon = self.simconnect_manager.user_lon if hasattr(self, "simconnect_manager") else None
                        u_og = self.simconnect_manager.user_on_ground if hasattr(self, "simconnect_manager") else None
                        apt["atc_taxi_via"] = self.taxi_router.prune_conflicting_taxi_via(
                            apt["chart_data"], phase, apt["lat"], apt["lon"],
                            apt.get("selected_runway"), cur_list, twy_u,
                            user_lat=u_lat, user_lon=u_lon, user_on_ground=u_og,
                            gate_hdg=apt.get("heading"), no_pushback=apt.get("no_pushback", False)
                        )
                    else:
                        cur_list.append(twy_u)
                        apt["atc_taxi_via"] = cur_list

        if phase == "departure":
            self.taxi_router.dep_runway_entered.pop(apt.get("icao", ""), None)
            self._last_dep_route_key = None
        else:
            self._last_arr_route_key = None

        if apt.get("chart_data") and apt.get("gate") and apt.get("lat") is not None:
            u_lat = self.simconnect_manager.user_lat if hasattr(self, "simconnect_manager") else None
            u_lon = self.simconnect_manager.user_lon if hasattr(self, "simconnect_manager") else None
            u_hdg = self.simconnect_manager.user_hdg if hasattr(self, "simconnect_manager") else None
            u_gs = self.simconnect_manager.user_gs if hasattr(self, "simconnect_manager") else None
            u_og = self.simconnect_manager.user_on_ground if hasattr(self, "simconnect_manager") else None
            t_route = self.taxi_router.compute_taxi_route(
                apt["chart_data"], phase, apt["lat"], apt["lon"], apt["gate"],
                runway_id=apt.get("selected_runway"), user_lat=u_lat, user_lon=u_lon,
                user_hdg=u_hdg, user_gs=u_gs, user_on_ground=u_og,
                gate_hdg=apt.get("heading"), no_pushback=apt.get("no_pushback", False),
                atc_taxi_via=apt.get("atc_taxi_via")
            )
            apt["taxi_route"] = t_route
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

        is_ga_fl = bool(self.current_flight_data.get("is_ga_flight"))
        is_mil_fl = bool(self.current_flight_data.get("is_military_flight"))
        viable = [
            g for g in free_stands
            if clean_gate_token(g["name"]) != cur_tok
            and float(g.get("wingspan") or 36.0) >= ac_ws
            and (is_ga_fl or not g.get("is_ga"))
            and (is_mil_fl or not g.get("is_military"))
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
            if is_airborne or (u_gs or 0.0) > 10.0:
                self.pending_simbrief_mismatch = None
            if is_airborne:
                fd["recommended_phase"] = "arrival"
            elif in_menu:
                fd["recommended_phase"] = "departure"
            fd["user_aircraft"] = {
                "connected": sc_conn,
                "in_menu": in_menu,
                "lat": round(u_lat, 7) if u_lat is not None else None,
                "lon": round(u_lon, 7) if u_lon is not None else None,
                "heading": round(u_hdg, 2) if u_hdg is not None else 0.0,
                "gs": round(u_gs, 2) if u_gs is not None else 0.0,
                "on_ground": u_og,
                "engines_running": getattr(sc, "user_engines_running", None)
            }
            try:
                fd["map_follow_refresh_hz"] = int(self.config.settings.get("map_follow_refresh_hz", 10) or 10)
            except Exception:
                fd["map_follow_refresh_hz"] = 10
            d_dep = float('inf')
            d_arr = float('inf')
            if sc_conn and u_lat is not None:
                if "departure" in fd and fd["departure"] and fd["departure"].get("lat") is not None:
                    d_dep = haversine(u_lat, u_lon, fd["departure"]["lat"], fd["departure"]["lon"])
                if "arrival" in fd and fd["arrival"] and fd["arrival"].get("lat") is not None:
                    d_arr = haversine(u_lat, u_lon, fd["arrival"]["lat"], fd["arrival"]["lon"])
            fd["d_dep_m"] = d_dep if d_dep != float('inf') else None
            fd["d_arr_m"] = d_arr if d_arr != float('inf') else None
            route_lock = getattr(self, "_route_calc_lock", None)
            if route_lock is None:
                self._route_calc_lock = threading.RLock()
                route_lock = self._route_calc_lock
            if "departure" in fd and fd["departure"]:
                dep = dict(fd["departure"])
                dep["ai_cleared"] = sc.dep_cleared
                dep["ai_active"] = sc.dep_loop_active and sc_conn
                dep["simconnect_connected"] = sc_conn
                if sc_conn and u_lat is not None and dep.get("chart_data") and dep.get("lat") is not None:
                    if d_dep < 6500.0:
                        with route_lock:
                            cur_dep_live = self.current_flight_data.get("departure") or dep
                            dep["taxi_route"] = cur_dep_live.get("taxi_route", dep.get("taxi_route"))
                            prev_pos = getattr(self, "_last_dep_route_pos", None)
                            prev_key = getattr(self, "_last_dep_route_key", None)
                            dep_via_k = None if dep.get("atc_taxi_via") is None else tuple(dep.get("atc_taxi_via"))
                            cur_key = (dep.get("icao"), dep.get("gate"), dep.get("selected_runway"), dep_via_k, bool(dep.get("custom_taxi_mode")), bool(u_og))
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
                            with route_lock:
                                if not self.taxi_router.dep_runway_entered.get(dep_icao):
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
                        with route_lock:
                            cur_arr_live = self.current_flight_data.get("arrival") or arr
                            arr["taxi_route"] = cur_arr_live.get("taxi_route", arr.get("taxi_route"))
                            arr["selected_runway"] = cur_arr_live.get("selected_runway", arr.get("selected_runway"))
                            prev_pos = getattr(self, "_last_arr_route_pos", None)
                            prev_key = getattr(self, "_last_arr_route_key", None)
                            arr_via_k = None if arr.get("atc_taxi_via") is None else tuple(arr.get("atc_taxi_via"))
                            cur_key = (arr.get("icao"), arr.get("gate"), arr.get("selected_runway"), arr_via_k, bool(arr.get("custom_taxi_mode")), bool(u_og))
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
        fd["pending_simbrief_mismatch"] = getattr(self, "pending_simbrief_mismatch", None)
        fd["suppress_popups_in_cockpit"] = bool(self.config.settings.get("suppress_popups_in_cockpit", False))
        al_code_cam = fd.get("airline_code") or (fd.get("departure") or {}).get("airline_code") or ""
        if not al_code_cam and fd.get("airline"):
            raw_al_s = str(fd["airline"])
            al_code_cam = raw_al_s.split("-")[0].strip().upper() if "-" in raw_al_s else raw_al_s.strip().upper()[:3]
        if fd.get("aircraft_version") and "•" in str(fd["aircraft_version"]):
            fd["aircraft_version"] = re.sub(r"\s*•\s*", " - ", str(fd["aircraft_version"]))
        fd["camaieu_palette"] = self.get_airline_camaieu_palette(al_code_cam)
        fd["app_version"] = "2.0.6"
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
    <title>GateFinder V2.0.6 - Live Web EFB</title>
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
    <script type="text/javascript" src="/GateFinderPanel.js?v=206"></script>
</head>
<body class="border-box color-white">
    <gsx-gatefinder-panel>
        <ingame-ui id="GSX_GateFinder" panel-id="PANEL_GATEFINDER" title="GATEFINDER V2.0.6">
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
                            raw_bytes = raw_bytes.replace(b'?v=206', b'?v=' + ts_b).replace(b'?v=205', b'?v=' + ts_b).replace(b'?v=204', b'?v=' + ts_b).replace(b'?v=203', b'?v=' + ts_b)
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
                    bi = APIHandler.backend_instance
                    now_api_t = time.time()
                    if (now_api_t - getattr(bi, "_last_api_mismatch_check_ts", 0.0)) >= 2.0:
                        bi._last_api_mismatch_check_ts = now_api_t
                        try:
                            bi.check_simbrief_vs_msfs_mismatch()
                        except Exception:
                            pass
                    fd = bi.get_dynamic_flight_data()
                    if fd:
                        if have_dep and fd.get("departure") and fd["departure"].get("icao") == have_dep:
                            dep_copy = dict(fd["departure"])
                            dep_copy.pop("chart_data", None)
                            fd["departure"] = dep_copy
                        if have_arr and fd.get("arrival") and fd["arrival"].get("icao") == have_arr:
                            arr_copy = dict(fd["arrival"])
                            arr_copy.pop("chart_data", None)
                            fd["arrival"] = arr_copy
                    else:
                        pmm = getattr(bi, "pending_simbrief_mismatch", None)
                        if pmm:
                            sc_now = getattr(bi, "simconnect_manager", None)
                            fd = {
                                "pending_simbrief_mismatch": pmm,
                                "suppress_popups_in_cockpit": bool(bi.config.settings.get("suppress_popups_in_cockpit", False)),
                                "is_airborne": False,
                                "user_aircraft": {
                                    "connected": bool(sc_now and sc_now.connected),
                                    "on_ground": bool(sc_now and sc_now.user_on_ground),
                                    "gs": round(float(getattr(sc_now, "user_gs", 0.0) or 0.0), 2) if sc_now else 0.0,
                                },
                            }
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

                if parsed.path == '/api/set_taxi_via':
                    query = parse_qs(parsed.query)
                    phase = query.get('phase', ['departure'])[0].strip().lower()
                    action = query.get('action', [''])[0].strip().lower() or None
                    toggle_twy = query.get('toggle', [''])[0].strip().upper() or None
                    remove_twy = query.get('remove', [''])[0].strip().upper() or None
                    via_raw = query.get('via', [''])[0].strip()
                    via_list = [x.strip().upper() for x in via_raw.split(',') if x.strip()] if 'via' in query else None
                    APIHandler.backend_instance.set_custom_taxi_via(
                        phase,
                        action=action,
                        toggle_twy=toggle_twy,
                        remove_twy=remove_twy,
                        via_list=via_list
                    )
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

                if parsed.path == '/api/open_simbrief_dispatch':
                    try:
                        import webbrowser
                        webbrowser.open("https://dispatch.simbrief.com/home")
                    except Exception:
                        pass
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True}).encode('utf-8'))
                    return

                if parsed.path == '/api/peek_simbrief':
                    bi = APIHandler.backend_instance
                    sb_u = bi.config.settings.get("simbrief_username", "").strip()
                    pk = bi.peek_latest_simbrief_ofp(sb_u) if sb_u else None
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(json.dumps(pk or {}).encode('utf-8'))
                    return

                if parsed.path == '/api/resolve_mismatch':
                    query = parse_qs(parsed.query)
                    action = query.get('action', ['keep_simbrief'])[0].strip().lower()
                    dest_q = re.sub(r'[^A-Z0-9]', '', query.get('dest', [''])[0].strip().upper())[:4]
                    mkey_q = query.get('key', [''])[0].strip()
                    live_q = re.sub(r'[^A-Z0-9]', '', query.get('live_icao', [''])[0].strip().upper())[:4]
                    bi = APIHandler.backend_instance
                    pmm = getattr(bi, "pending_simbrief_mismatch", None) or {}
                    eff_key = mkey_q or pmm.get("mismatch_key")
                    eff_live = live_q or str(pmm.get("live_icao") or "").strip().upper()
                    try:
                        if action == 'use_msfs':
                            bi.dismiss_simbrief_msfs_mismatch(eff_key)
                            if eff_live:
                                bi.load_live_msfs_flight(eff_live, dest_q or eff_live)
                        elif action == 'import_simbrief':
                            bi._cached_mismatch_sb_peek = None
                            bi._mismatch_check_memo = None
                            bi.pending_simbrief_mismatch = None
                            sb_u = bi.config.settings.get("simbrief_username", "").strip()
                            if sb_u:
                                bi.get_flight_data(sb_u)
                        else:
                            bi.dismiss_simbrief_msfs_mismatch(eff_key)
                            if not bi.current_flight_data:
                                sb_u = bi.config.settings.get("simbrief_username", "").strip()
                                if sb_u:
                                    bi.get_flight_data(sb_u)
                        bi._gui_close_mismatch_modal = True
                        bi._gui_sync_needed = True
                        self.send_response(200)
                        self.end_headers()
                        fd = bi.get_dynamic_flight_data()
                        self.wfile.write(json.dumps(fd).encode('utf-8'))
                    except Exception as e:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
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
