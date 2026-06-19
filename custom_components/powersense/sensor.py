import logging
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event
from .const import DOMAIN, CONF_P1_SENSOR

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    p1_sensor_id = config_entry.data.get(CONF_P1_SENSOR)
    analyzer = hass.data[DOMAIN]["analyzer"]

    unknown_sensor = PowerSenseUnknownSensor(analyzer, p1_sensor_id)
    efficiency_sensor = PowerSenseEfficiencySensor(analyzer, p1_sensor_id)

    async_add_entities([unknown_sensor, efficiency_sensor])

    async def _async_p1_state_changed(event):
        new_state = event.data.get("new_state")
        if new_state and new_state.state not in ['unknown', 'unavailable']:
            try:
                total_power = float(new_state.state)
                _, unknown_rest = analyzer.process_reading(total_power)
                
                unknown_sensor.update_value(unknown_rest)
                efficiency_sensor.update_value(total_power, unknown_rest)
            except ValueError:
                pass

    async_track_state_change_event(hass, [p1_sensor_id], _async_p1_state_changed)


class PowerSenseUnknownSensor(Entity):
    def __init__(self, analyzer, p1_sensor_id):
        self._analyzer = analyzer
        self._state = 0

    @property
    def name(self): return "PowerSense Unknown Restwaarde"
    @property
    def unique_id(self): return "powersense_unknown_restwaarde"
    @property
    def state(self): return self._state
    @property
    def unit_of_measurement(self): return "W"
    @property
    def icon(self): return "mdi:help-circle-outline"
    @property
    def should_poll(self): return False

    def update_value(self, value):
        self._state = value
        self.async_write_ha_state()


class PowerSenseEfficiencySensor(Entity):
    def __init__(self, analyzer, p1_sensor_id):
        self._analyzer = analyzer
        self._state = 100

    @property
    def name(self): return "PowerSense Deconstructie Efficiëntie"
    @property
    def unique_id(self): return "powersense_deconstructie_efficiency"
    @property
    def state(self): return self._state
    @property
    def unit_of_measurement(self): return "%"
    @property
    def icon(self): return "mdi:shield-check"
    @property
    def should_poll(self): return False

    def update_value(self, total_grid, unknown_rest):
        if total_grid > 0:
            acc = 1 - (unknown_rest / (2 * total_grid))
            self._state = min(100, max(0, round(acc * 100)))
        else:
            self._state = 100
        self.async_write_ha_state()