DOMAIN = "powersense"

# Vaste configuratiesleutel voor de energiemeter
CONF_P1_SENSOR = "selected_p1_sensor"

# AI Toleranties
MATCH_TOLERANCE_PERCENT = 0.06

# Drempel: aantal herhalingen voor sensor aangemaakt wordt
# Duidelijke pieken (lage variatiecoëfficiënt): 3 herhalingen
# Vage pieken (hoge variatie, bv. dimbare lichten): 25 herhalingen
MIN_REPETITIONS_CLEAR = 3
MIN_REPETITIONS_VAGUE = 25

# Variatiecoëfficiënt grens: onder deze waarde = "duidelijk signaal"
# CV = standaardafwijking / gemiddelde; 0.05 = max 5% variatie
CLEAR_PEAK_CV_THRESHOLD = 0.05

# Minimale tijd (seconden) tussen twee flanken van hetzelfde cluster
# om als geldige herhaling te tellen — filtert kortsluitige pieken
MIN_ACTIVE_DURATION_SECONDS = 30

CLUSTER_MAX_AGE_SECONDS = 172800  # 48 uur

# Suggesties matrix voor apparaten
APPLIANCE_SUGGESTIONS = [
    {"min": 5,    "max": 25,   "labels": "Modem / Router / Stand-by apparatuur"},
    {"min": 26,   "max": 100,  "labels": "Televisie / Sfeerverlichting / Laptop lader"},
    {"min": 101,  "max": 300,  "labels": "Koelkast / Computer / Geluidsinstallatie"},
    {"min": 301,  "max": 800,  "labels": "Magnetron / Wasmachine (spoelfase) / Diepvries"},
    {"min": 801,  "max": 1500, "labels": "Vaatwasser / Koffiezetapparaat (warmhouden) / Stofzuiger"},
    {"min": 1501, "max": 2500, "labels": "Waterkoker / Oven / Wasmachine (verwarmen)"},
    {"min": 2501, "max": 4000, "labels": "Laadpaal EV / Inductiekookplaat / Warmtepomp"},
]
