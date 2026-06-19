import logging
import math
import time
from .const import (
    DOMAIN, 
    MATCH_TOLERANCE_PERCENT, 
    MIN_REPETITIONS_FOR_NOTIF, 
    CLUSTER_MAX_AGE_SECONDS, 
    APPLIANCE_SUGGESTIONS
)

_LOGGER = logging.getLogger(__name__)

class PeakSenseClusterAnalyzer:
    def __init__(self, hass):
        self.hass = hass
        self.last_total_power = None
        self.baseload = 0  # Start op 0 om directe aanpassing aan de sensor te garanderen
        self.temporary_clusters = {}
        self.registered_appliances = {}
        self.boost_active = False
        
    def set_boost_mode(self, active: bool):
        self.boost_active = active
        _LOGGER.info(f"[PowerSense] Boost-modus status gewijzigd naar: {active}")

    def _get_suggestion(self, wattage):
        for item in APPLIANCE_SUGGESTIONS:
            if item["min"] <= wattage <= item["max"]:
                return item["labels"]
        return "Onbekend type apparaat"

    def process_reading(self, current_total):
        if self.last_total_power is None:
            self.last_total_power = current_total
            return 0, current_total

        # 1. Bereken de Flank (Delta P)
        delta_p = current_total - self.last_total_power
        self.last_total_power = current_total

        self._garbage_collection()

        # Dynamische baseload bijstelling (past zich aan bij lagere netbelasting)
        if current_total < self.baseload or self.baseload == 0:
            self.baseload = current_total

        # 2. Controleer actieve bekende apparaten via pariteit-matching
        active_isolated_wattage = 0
        for name, app in self.registered_appliances.items():
            if app["active"]:
                # Uitschakeldetectie (Negatieve flank)
                if delta_p <= -(app["mean_watt"] * (1 - MATCH_TOLERANCE_PERCENT)) and delta_p >= -(app["mean_watt"] * (1 + MATCH_TOLERANCE_PERCENT)):
                    app["active"] = False
                    _LOGGER.info(f"[PowerSense] Apparaat uitgeschakeld: {name}")
                else:
                    active_isolated_wattage += app["mean_watt"]
            else:
                # Inschakeldetectie (Positieve flank)
                if delta_p >= (app["mean_watt"] * (1 - MATCH_TOLERANCE_PERCENT)) and delta_p <= (app["mean_watt"] * (1 + MATCH_TOLERANCE_PERCENT)):
                    app["active"] = True
                    active_isolated_wattage += app["mean_watt"]
                    _LOGGER.info(f"[PowerSense] Apparaat ingeschakeld: {name}")

        # 3. Bereken restwaarde (mag ook negatief zijn bij teruglevering!)
        unknown_rest = current_total - active_isolated_wattage - self.baseload

        # 4. Gecorrigeerde Analyse: Reageer ALTIJD als de sprong groter is dan 5 Watt, ongeacht zonnepanelen!
        if abs(delta_p) >= 5:
            self._analyze_unknown_flank(abs(delta_p))

        return active_isolated_wattage, unknown_rest

    def _analyze_unknown_flank(self, flank_value):
        match_found = False
        
        for cluster_id, data in self.temporary_clusters.items():
            if math.isclose(flank_value, data["mean_watt"], rel_tol=MATCH_TOLERANCE_PERCENT):
                data["count"] += 1
                data["mean_watt"] = round(0.9 * data["mean_watt"] + 0.1 * flank_value)
                data["last_seen"] = time.time()
                match_found = True
                
                _LOGGER.info(f"[PowerSense] Cluster {cluster_id} herhaald! Teller: {data['count']}")
                
                target_repetitions = 1 if self.boost_active else MIN_REPETITIONS_FOR_NOTIF
                if data["count"] >= target_repetitions and not data["notified"]:
                    data["notified"] = True
                    self._trigger_hass_notification(cluster_id, data["mean_watt"])
                break

        if not match_found:
            new_id = f"cluster_{int(time.time())}_{round(flank_value)}"
            self.temporary_clusters[new_id] = {
                "mean_watt": flank_value,
                "count": 1,
                "notified": False,
                "last_seen": time.time()
            }
            _LOGGER.info(f"[PowerSense] Nieuw patroon opgemerkt: {flank_value}W")
            
            if self.boost_active:
                self.temporary_clusters[new_id]["notified"] = True
                self._trigger_hass_notification(new_id, flank_value)

    def _garbage_collection(self):
        current_time = time.time()
        to_delete = []
        for cluster_id, data in self.temporary_clusters.items():
            if (current_time - data["last_seen"]) > CLUSTER_MAX_AGE_SECONDS and data["count"] < MIN_REPETITIONS_FOR_NOTIF:
                to_delete.append(cluster_id)
        for cluster_id in to_delete:
            del self.temporary_clusters[cluster_id]

    def _trigger_hass_notification(self, cluster_id, wattage):
        config_entry = self.hass.config_entries.async_entries(DOMAIN)[0]
        notify_device = config_entry.data.get("notification_device", "none")
        suggestion = self._get_suggestion(wattage)

        if notify_device and notify_device != "none":
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "notify",
                    notify_device.split(".")[1],
                    {
                        "title": "🤖 PowerSense: Nieuw Apparaat!",
                        "message": f"Verbruik van {wattage}W ontdekt.\nSuggestie: {suggestion}",
                        "data": {
                            "actions": [
                                {
                                    "action": f"POWERSENSE_LABEL_{cluster_id}",
                                    "title": "Geef naam",
                                    "behavior": "text_input",
                                    "text_input_button_title": "Opslaan"
                                }
                            ]
                        }
                    }
                )
            )
        else:
            self.hass.components.persistent_notification.create(
                title="🤖 PowerSense: Nieuw Apparaat!",
                message=(
                    f"Ik heb een herkenbaar verbruik gevonden van circa **{wattage}W**.<br>"
                    f"**Vermoedelijk:** {suggestion}.<br><br>"
                    f"Geef dit apparaat een naam in je instellingen."
                ),
                notification_id=f"powersense_{cluster_id}"
            )
