import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_state_change_event
from .const import DOMAIN, CONF_P1_SENSOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Zet de PowerSense sensoren op."""
    p1_sensor_id = config_entry.data.get(CONF_P1_SENSOR)
    analyzer = hass.data[DOMAIN]["analyzer"]

    if not p1_sensor_id:
        _LOGGER.error("[PowerSense] P1-sensor ID mist in de configuratie!")
        return

    overig_sensor = PowerSenseOverigSensor(analyzer)
    efficiency_sensor = PowerSenseEfficiencySensor(analyzer)

    # Sla referentie op zodat analyzer nieuwe sensoren kan registreren
    hass.data[DOMAIN]["overig_sensor"] = overig_sensor
    hass.data[DOMAIN]["async_add_entities"] = async_add_entities
    hass.data[DOMAIN]["device_sensors"] = {}

    async_add_entities([overig_sensor, efficiency_sensor])

    # Maak sensoren aan voor reeds bekende apparaten (geladen uit opslag)
    for name, app_data in analyzer.registered_appliances.items():
        await _ensure_device_sensor(hass, async_add_entities, analyzer, name, app_data["mean_watt"])

    async def _async_p1_state_changed(event):
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            current_power = float(new_state.state)
            active_isolated, unknown_rest = analyzer.process_reading(current_power)

            # Nieuwe apparaten die zojuist geregistreerd werden → sensor aanmaken
            for name, app_data in analyzer.registered_appliances.items():
                await _ensure_device_sensor(hass, async_add_entities, analyzer, name, app_data["mean_watt"])

            # Bijwerken van alle apparaatsensoren
            for name, sensor in hass.data[DOMAIN]["device_sensors"].items():
                app = analyzer.registered_appliances.get(name)
                if app:
                    sensor.update_state(app.get("active", False), app["mean_watt"])

            overig_sensor.update_value(unknown_rest, current_power)
            efficiency_sensor.update_efficiency(active_isolated, current_power)

        except ValueError as e:
            _LOGGER.error(f"[PowerSense] Fout bij parsen sensorwaarde '{new_state.state}': {e}")

    async_track_state_change_event(hass, [p1_sensor_id], _async_p1_state_changed)
    _LOGGER.info(f"[PowerSense] Live tracking gestart op sensor: {p1_sensor_id}")


async def _ensure_device_sensor(hass, async_add_entities, analyzer, name, mean_watt):
    """Maak een apparaatsensor aan als die nog niet bestaat."""
    device_sensors = hass.data[DOMAIN]["device_sensors"]
    if name not in device_sensors:
        sensor = PowerSenseDeviceSensor(analyzer, name, mean_watt)
        device_sensors[name] = sensor
        async_add_entities([sensor])
        _LOGGER.info(f"[PowerSense] Nieuwe sensor aangemaakt: sensor.power_{_slugify(name)}")


def _slugify(name: str) -> str:
    """Zet apparaatnaam om naar een geldige entity slug."""
    import re
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug


class PowerSenseDeviceSensor(SensorEntity):
    """Sensor per herkend apparaat — toont actief vermogen of 0 W."""

    def __init__(self, analyzer, device_name: str, mean_watt: int):
        self._analyzer = analyzer
        self._device_name = device_name
        self._mean_watt = mean_watt
        self._active = False
        self._slug = _slugify(device_name)

    @property
    def name(self):
        return f"Power {self._device_name}"

    @property
    def unique_id(self):
        return f"powersense_device_{self._slug}"

    @property
    def state(self):
        # Toont huidig geschat vermogen: mean_watt als actief, anders 0
        return self._mean_watt if self._active else 0

    @property
    def unit_of_measurement(self):
        return "W"

    @property
    def icon(self):
        return "mdi:power-plug" if self._active else "mdi:power-plug-off"

    @property
    def extra_state_attributes(self):
        return {
            "device_name": self._device_name,
            "mean_watt": self._mean_watt,
            "active": self._active,
        }

    def update_state(self, active: bool, mean_watt: int):
        self._active = active
        self._mean_watt = mean_watt
        self.async_write_ha_state()


class PowerSenseOverigSensor(SensorEntity):
    """Toont het vermogen dat nog niet aan een bekend apparaat is toegewezen."""

    def __init__(self, analyzer):
        self._analyzer = analyzer
        self._state = 0
        self._current_total = 0

    @property
    def name(self):
        return "PowerSense Overig"

    @property
    def unique_id(self):
        return "powersense_overig"

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return "W"

    @property
    def icon(self):
        return "mdi:help-circle-outline"

    @property
    def extra_state_attributes(self):
        return {
            "baseload": int(round(self._analyzer.baseload)),
            "total_power": int(round(self._current_total)),
            "registered_appliances": self._analyzer.registered_appliances,
            "temporary_clusters": self._analyzer.temporary_clusters,
            "boost_active": self._analyzer.boost_active,
        }

    def update_value(self, value, current_total):
        self._state = value
        self._current_total = current_total
        self.async_write_ha_state()


class PowerSenseEfficiencySensor(SensorEntity):
    def __init__(self, analyzer):
        self._analyzer = analyzer
        self._state = 100

    @property
    def name(self):
        return "PowerSense Deconstructie Efficiency"

    @property
    def unique_id(self):
        return "powersense_deconstructie_efficiency"

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return "%"

    def update_efficiency(self, active_isolated, current_total):
        if current_total <= 0:
            self._state = 100
        else:
            efficiency = (active_isolated / current_total) * 100
            self._state = min(100, max(0, round(efficiency)))
        self.async_write_ha_state()
