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

    rest_sensor = PowerSenseRestSensor(analyzer)
    efficiency_sensor = PowerSenseEfficiencySensor(analyzer)
    async_add_entities([rest_sensor, efficiency_sensor])

    async def _async_p1_state_changed(event):
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            current_power = float(new_state.state)
            active_isolated, unknown_rest = analyzer.process_reading(current_power)
            
            rest_sensor.update_value(unknown_rest, current_power)
            efficiency_sensor.update_efficiency(active_isolated, current_power)
            
        except ValueError as e:
            _LOGGER.error(f"[PowerSense] Fout bij parsen sensorwaarde '{new_state.state}': {e}")

    async_track_state_change_event(hass, [p1_sensor_id], _async_p1_state_changed)
    _LOGGER.info(f"[PowerSense] Live tracking gestart op sensor: {p1_sensor_id}")


class PowerSenseRestSensor(SensorEntity):
    def __init__(self, analyzer):
        self._analyzer = analyzer
        self._state = 0
        self._current_total = 0

    @property
    def name(self):
        return "PowerSense Unknown Restwaarde"

    @property
    def unique_id(self):
        return "powersense_unknown_restwaarde"

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return "W"

    @property
    def extra_state_attributes(self):
        return {
            "baseload": int(round(self._analyzer.baseload)),
            "total_power": int(round(self._current_total)),
            "registered_appliances": self._analyzer.registered_appliances,
            "temporary_clusters": self._analyzer.temporary_clusters,
            "boost_active": self._analyzer.boost_active
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
