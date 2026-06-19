DOMAIN = "powersense"

# Vaste configuratiesleutel voor de energiemeter
CONF_P1_SENSOR = "selected_p1_sensor"

# AI Toleranties
MATCH_TOLERANCE_PERCENT = 0.06
MIN_REPETITIONS_FOR_NOTIF = 3
CLUSTER_MAX_AGE_SECONDS = 172800  # 48 uur

# Suggesties matrix voor apparaten
APPLIANCE_SUGGESTIONS = [
    {"min": 5, "max": 25, "labels": "Modem / Router / Stand-by apparatuur"},
    {"min": 26, "max": 100, "labels": "Televisie / Sfeerverlichting / Laptop lader"},
    {"min": 101, "max": 300, "labels": "Koelkast / Computer / Geluidsinstallatie"},
    {"min": 301, "max": 800, "labels": "Magnetron / Wasmachine (spoelfase) / Diepvries"},
    {"min": 801, "max": 1500, "labels": "Vaatwasser / Koffiezetapparaat (warmhouden) / Stofzuiger"},
    {"min": 1501, "max": 2500, "labels": "Waterkoker / Oven / Wasmachine (verwarmen)"},
    {"min": 2501, "max": 4000, "labels": "Laadpaal EV / Inductiekookplaat / Warmtepomp"}
]
