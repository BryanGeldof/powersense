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
        
        self.storage_path = hass.config.path("powersense_data.json")
        self._load_appliances_from_storage()
        
    def set_boost_mode(self, active: bool):
        self.boost_active = active
        _LOGGER.info(f"[PowerSense] Boost-modus status gewijzigd naar: {active}")

    def _load_appliances_from_storage(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    self.registered_appliances = json.load(f)
                _LOGGER.info(f"[PowerSense] {len(self.registered_appliances)} apparaten geladen.")
            except Exception as e:
                _LOGGER.error(f"[PowerSense] Database laad-fout: {e}")

    def save_appliance(self, name, mean_watt):
        self.registered_appliances[str(name)] = {
            "mean_watt": int(round(float(mean_watt))),
            "active": False
        }
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.registered_appliances, f, indent=4)
        except Exception as e:
            _LOGGER.error(f"[PowerSense] JSON opslag-fout: {e}")

    def _get_suggestion(self, wattage):
        for item in APPLIANCE_SUGGESTIONS:
            if item["min"] <= wattage <= item["max"]:
                return item["labels"]
        return "Onbekend type apparaat"

    def process_reading(self, current_total):
        try:
            current_total = float(current_total)
        except (ValueError, TypeError):
            return 0, 0

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

        if self.registered_appliances:
            for name, app in self.registered_appliances.items():
                if app.get("active", False):
                    expected_drop = -float(app["mean_watt"])
                    diff = abs(delta_p - expected_drop)
                    if diff < best_negative_diff and (diff <= (float(app["mean_watt"]) * 0.15) or diff <= 50):
                        best_negative_diff = diff
                        best_negative_match = name
                    active_isolated_wattage += float(app["mean_watt"])
                else:
                    min_marge = float(app["mean_watt"]) * (1 - MATCH_TOLERANCE_PERCENT)
                    max_marge = float(app["mean_watt"]) * (1 + MATCH_TOLERANCE_PERCENT)
                    if min_marge <= delta_p <= max_marge:
                        app["active"] = True
                        active_isolated_wattage += float(app["mean_watt"])
                        _LOGGER.info(f"[PowerSense] Ingeschakeld: {name}")

        if delta_p < -5 and best_negative_match:
            app = self.registered_appliances[best_negative_match]
            app["active"] = False
            active_isolated_wattage = max(0, active_isolated_wattage - float(app["mean_watt"]))
            _LOGGER.info(f"[PowerSense] Uitgeschakeld: {best_negative_match}")

        unknown_rest = current_total - active_isolated_wattage - self.baseload

        if abs(delta_p) >= 5:
            self._analyze_unknown_flank(abs(delta_p))

        return int(active_isolated_wattage), int(unknown_rest)

    def _analyze_unknown_flank(self, flank_value):
        match_found = False
        flank_value = float(flank_value)
        
        for cluster_id, data in self.temporary_clusters.items():
            if math.isclose(flank_value, float(data["mean_watt"]), rel_tol=MATCH_TOLERANCE_PERCENT):
                data["count"] += 1
                data["mean_watt"] = round(0.9 * float(data["mean_watt"]) + 0.1 * flank_value)
                data["last_seen"] = time.time()
                match_found = True
                
                target_repetitions = 1 if self.boost_active else MIN_REPETITIONS_FOR_NOTIF
                if data["count"] >= target_repetitions and not data["notified"]:
                    data["notified"] = True
                    self._trigger_hass_notification(cluster_id, int(data["mean_watt"]))
                break

        if not match_found:
            new_id = f"cluster_{int(time.time())}_{round(flank_value)}"
            self.temporary_clusters[new_id] = {
                "mean_watt": int(round(flank_value)),
                "count": 1,
                "notified": False,
                "last_seen": time.time()
            }
            if self.boost_active:
                self.temporary_clusters[new_id]["notified"] = True
                self._trigger_hass_notification(new_id, int(round(flank_value)))

    def _garbage_collection(self):
        current_time = time.time()
        to_delete = []
        for cluster_id, data in self.temporary_clusters.items():
            if (current_time - data["last_seen"]) > CLUSTER_MAX_AGE_SECONDS and data["count"] < MIN_REPETITIONS_FOR_NOTIF:
                to_delete.append(cluster_id)
        for cluster_id in to_delete:
            del self.temporary_clusters[cluster_id]

    def _trigger_hass_notification(self, cluster_id, wattage):
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return
        config_entry = entries[0]
        
        # Verkrijg de lijst met geselecteerde apparaten (valt terug op UI als lijst leeg is)
        devices = config_entry.data.get("notification_devices", ["persistent_notification"])
        suggestion = self._get_suggestion(wattage)

        # Loop door ELK geselecteerd notificatie-apparaat heen!
        for device in devices:
            if device == "persistent_notification":
                # Stuur naar de UI
                self.hass.components.persistent_notification.create(
                    title="🤖 PowerSense: Nieuw Apparaat!",
                    message=f"Verbruik van circa **{wattage}W** ontdekt.<br>**Vermoedelijk:** {suggestion}.",
                    notification_id=f"powersense_{cluster_id}"
                )
            elif device.startswith("notify."):
                # Stuur naar de gsm/tablet service
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        "notify",
                        device.split(".")[1],
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
