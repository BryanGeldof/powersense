DOMAIN = "powersense"
CONF_P1_SENSOR = "p1_total_power_sensor"

# Wiskundige toleranties V0.2.0
FLANK_THRESHOLD_WATT = 5  # Extreem gevoelig voor sluipverbruik
MATCH_TOLERANCE_PERCENT = 0.06  # 6% foutmarge voor fuzzy matching
MIN_REPETITIONS_FOR_NOTIF = 3  

# Database & Boost beheer
CLUSTER_MAX_AGE_SECONDS = 172800  # 48 uur bewaartijd voor ongetrainde clusters

# Universele Wattage Suggesties Matrix
APPLIANCE_SUGGESTIONS = [
    {"min": 5, "max": 30, "labels": "Modem/Router, LED verlichting, Stand-by apparaat"},
    {"min": 31, "max": 120, "labels": "Koelkast, Diepvriezer, Ventilatiesysteem"},
    {"min": 121, "max": 400, "labels": "Televisie, Desktop PC, Wasmachine (Trommel motor)"},
    {"min": 401, "max": 900, "labels": "Magnetron, Grote Audioversterker, Vijverpomp"},
    {"min": 901, "max": 1600, "labels": "Koffiezetapparaat, Haardroger (Lage stand), Stofzuiger"},
    {"min": 1601, "max": 3000, "labels": "Waterkoker, Oven, Vaatwasser, Wasmachine (Verwarming)"},
    {"min": 3001, "max": 8000, "labels": "Laadpaal EV, Thuisbatterij (Snel laden), Inductiekookplaat"},
]