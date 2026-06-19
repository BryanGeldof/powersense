import logging
import math
import time
import os
import json
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
        self.baseload = 0
        self.temporary_clusters = {}
        self.registered_appliances = {}
        self.boost_active = False
        
        # Bepaal het opslagpad in de Home Assistant config map
        self.storage_path = hass.config.path("powersense_data.json")
        self._load_appliances_from_storage()
        
    def set_boost_mode(self, active: bool):
        self.boost_active = active
        _LOGGER.info(f"[PowerSense] Boost-modus status gewijzigd naar: {active}")

    def _load_appliances_from_storage(self):
        """Laadt getrainde apparaten in bij een herstart van HA."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    self.registered_appliances = json.load(f)
                _LOGGER.info(f"[PowerSense] {len(self.registered_appliances)} apparaten succesvol ingeladen uit database.")
            except Exception as e:
                _LOGGER.error(f"[PowerSense] Fout bij laden database: {e}")

    def save_appliance(self, name, mean_watt):
        """Slaat een nieuw apparaat permanent op."""
        self.registered_appliances[name] = {
            "mean_watt": mean_watt,
            "active": False
        }
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.registered_appliances, f, indent=4)
            _LOGGER.info(f"[PowerSense] Apparaat '{name}' permanent opgeslagen in database.")
        except Exception as e:
            _LOGGER.error(f"[PowerSense] Fout bij opslaan database: {e}")

    def _get_suggestion(self, wattage):
        for item in APPLIANCE_SUGGESTIONS:
            if item["min"] <= wattage <= item["max"]:
                return item["labels"]
        return "Onbekend type apparaat"

    def process_reading(self, current_total):
        if self.last_total_power is None:
            self.last_total_power = current_total
            return 0, current_total

        delta_p = current_total - self.last_total_power
        self.last_total_power = current_total

        self._garbage_collection()

        if current_total < self.baseload or self.baseload == 0:
            self.baseload = current_total

        active_isolated_wattage = 0
        best_negative_match = None
        best_negative_diff = float("inf")

        # Eerste ronde: Bereken verbruik van actieve apparaten & zoek naar uitschakelingen
        for name, app in self.registered_appliances.items():
            if app["active"]:
                # Upgrade 1: Fuzzy matching voor uitschakeling (staat ook kleine afwijkingen toe bij spanningsval)
                expected_drop = -app["mean_watt"]
                diff = abs(delta_p - expected_drop)
                
                # Check of het binnen een ruime foutmarge valt (bijv. max 15% of 50W afwijking bij uitschakelen)
                if diff < best_negative_diff and (diff <= (app["mean_watt"] * 0.15) or diff <= 50):
                    best_negative_diff = diff
                    best_negative_match = name
                
                active_isolated_wattage += app["mean_watt"]
            else:
                # Inschakeldetectie (blijft strak op de 6% const.py tolerantie)
                if delta_p >= (app["mean_watt"] * (1 - MATCH_TOLERANCE_PERCENT)) and delta_p <= (app["mean_watt"] * (1 + MATCH_TOLERANCE_PERCENT)):
                    app["active"] = True
                    active_isolated_wattage += app["mean_watt"]
                    _LOGGER.info(f"[PowerSense] Apparaat ingeschakeld: {name}")

        # Als er een duidelijke negatieve flank was, schakel het best passende apparaat uit
        if delta_p < -5 and best_negative_match:
            app = self.registered_appliances[best_negative_match]
            app["active"] = False
            active_isolated_wattage = max(0, active_isolated_wattage - app["mean_watt"])
            _LOGGER.info(f"[PowerSense] Apparaat uitgeschakeld (Fuzzy Match): {best_negative_match}")

        unknown_rest = current_total - active_isolated_wattage - self.baseload

        # Reageer op elke pure vermogenssprong boven de 5 Watt
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

        self.hass.components.persistent_notification.create(
            title="🤖 PowerSense: Nieuw Apparaat!",
            message=(
                f"Ik heb een herkenbaar verbruik gevonden van circa **{wattage}W**.<br>"
                f"**Vermoedelijk:** {suggestion}.<br><br>"
                f"Als je de notificatie op je gsm invult, wordt dit apparaat automatisch opgeslagen!"
            ),
            notification_id=f"powersense_{cluster_id}"
        )

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
