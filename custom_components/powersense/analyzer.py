import logging
import math
import time
import os
import json
import statistics
from .const import (
    DOMAIN,
    MATCH_TOLERANCE_PERCENT,
    CLUSTER_MAX_AGE_SECONDS,
    APPLIANCE_SUGGESTIONS,
    MIN_REPETITIONS_CLEAR,
    MIN_REPETITIONS_VAGUE,
    CLEAR_PEAK_CV_THRESHOLD,
    MIN_ACTIVE_DURATION_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class PeakSenseClusterAnalyzer:
    def __init__(self, hass):
        self.hass = hass
        self.last_total_power = None
        self.last_change_time = None
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
                _LOGGER.info(f"[PowerSense] {len(self.registered_appliances)} apparaten geladen uit opslag.")
            except Exception as e:
                _LOGGER.error(f"[PowerSense] Database laad-fout: {e}")

    def save_appliance(self, name, mean_watt):
        self.registered_appliances[str(name)] = {
            "mean_watt": int(round(float(mean_watt))),
            "active": False,
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
        return "Onbekend Apparaat"

    def process_reading(self, current_total):
        try:
            current_total = float(current_total)
        except (ValueError, TypeError):
            return 0, 0

        now = time.time()

        if self.last_total_power is None:
            self.last_total_power = current_total
            self.last_change_time = now
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
                        app["active_since"] = now
                        active_isolated_wattage += float(app["mean_watt"])

        if delta_p < -5 and best_negative_match:
            app = self.registered_appliances[best_negative_match]
            app["active"] = False
            app.pop("active_since", None)
            active_isolated_wattage = max(0, active_isolated_wattage - float(app["mean_watt"]))

        unknown_rest = current_total - active_isolated_wattage - self.baseload
        if unknown_rest < 0:
            unknown_rest = 0

        if abs(delta_p) >= 5:
            self._analyze_unknown_flank(abs(delta_p), now)

        return int(active_isolated_wattage), int(unknown_rest)

    def _analyze_unknown_flank(self, flank_value, now):
        flank_value = float(flank_value)
        match_found = False

        for cluster_id, data in self.temporary_clusters.items():
            if math.isclose(flank_value, float(data["mean_watt"]), rel_tol=MATCH_TOLERANCE_PERCENT):
                # Controleer minimale actieve duur: flank moet minstens MIN_ACTIVE_DURATION_SECONDS
                # na de vorige flank komen (apparaat was lang genoeg aan)
                time_since_last = now - data["last_seen"]
                if time_since_last < MIN_ACTIVE_DURATION_SECONDS:
                    _LOGGER.debug(
                        f"[PowerSense] Cluster {cluster_id} te snel herhaald "
                        f"({time_since_last:.1f}s < {MIN_ACTIVE_DURATION_SECONDS}s) — genegeerd."
                    )
                    data["last_seen"] = now  # reset timer maar tel niet mee
                    match_found = True
                    break

                # Bijhouden van alle gemeten flanken voor variatieberekening
                data["samples"].append(flank_value)
                data["count"] += 1
                data["mean_watt"] = round(0.9 * float(data["mean_watt"]) + 0.1 * flank_value)
                data["last_seen"] = now
                match_found = True

                # Bepaal drempel op basis van consistentie (variatiecoëfficiënt)
                required = self._required_repetitions(data["samples"])
                data["required"] = required

                if data["count"] >= required and not data["notified"]:
                    data["notified"] = True
                    self._auto_register_cluster(cluster_id, int(data["mean_watt"]))
                else:
                    _LOGGER.debug(
                        f"[PowerSense] Cluster {cluster_id}: {data['count']}/{required} herhalingen "
                        f"(CV={self._cv(data['samples']):.3f})"
                    )
                break

        if not match_found:
            new_id = f"cluster_{int(now)}_{round(flank_value)}"
            self.temporary_clusters[new_id] = {
                "mean_watt": int(round(flank_value)),
                "count": 1,
                "samples": [flank_value],
                "notified": False,
                "last_seen": now,
                "required": MIN_REPETITIONS_VAGUE,  # start conservatief
            }
            if self.boost_active:
                self.temporary_clusters[new_id]["notified"] = True
                self._auto_register_cluster(new_id, int(round(flank_value)))

    def _cv(self, samples):
        """Variatiecoëfficiënt: standaardafwijking / gemiddelde. Lager = consistenter."""
        if len(samples) < 2:
            return 1.0  # onbekend → conservatief behandelen
        mean = statistics.mean(samples)
        if mean == 0:
            return 1.0
        return statistics.stdev(samples) / mean

    def _required_repetitions(self, samples):
        """Bepaal vereist aantal herhalingen op basis van consistentie."""
        cv = self._cv(samples)
        if cv < CLEAR_PEAK_CV_THRESHOLD:
            return MIN_REPETITIONS_CLEAR   # consistent signaal → 3
        return MIN_REPETITIONS_VAGUE       # variabel signaal → 25

    def _auto_register_cluster(self, cluster_id, wattage):
        """Registreert automatisch een apparaat na voldoende bewijs.
        
        Geen HA-notificatie — de aanmaak van sensor.power_<naam> is het signaal.
        """
        suggestion = self._get_suggestion(wattage)
        existing_count = sum(
            1 for name in self.registered_appliances.keys()
            if name.startswith(suggestion)
        )
        suffix = f" #{existing_count + 1}" if existing_count > 0 else ""
        auto_name = f"{suggestion}{suffix} ({wattage}W)"

        self.save_appliance(auto_name, wattage)

        if cluster_id in self.temporary_clusters:
            del self.temporary_clusters[cluster_id]

        _LOGGER.info(
            f"[PowerSense] Nieuw apparaat ingeleerd: '{auto_name}' — "
            f"sensor.power_{self._slugify(auto_name)} wordt aangemaakt."
        )

    def _slugify(self, name: str) -> str:
        import re
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        return slug.strip("_")

    def _garbage_collection(self):
        current_time = time.time()
        to_delete = [
            cid for cid, d in self.temporary_clusters.items()
            if (current_time - d["last_seen"]) > CLUSTER_MAX_AGE_SECONDS
        ]
        for cid in to_delete:
            del self.temporary_clusters[cid]
