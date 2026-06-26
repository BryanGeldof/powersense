import logging
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN, CONF_P1_SENSOR

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    analyzer = hass.data[DOMAIN]["analyzer"]
    
    # De "Overig" / "Onbekend" sensor
    unknown_sensor = PowerSenseUnknownSensor(analyzer)
    
    # Dynamische sensoren voor bekende apparaten
    device_sensors = []
    for name in analyzer.registered_appliances:
        device_sensors.append(PowerSenseDeviceSensor(analyzer, name))
        
    async_add_entities([unknown_sensor] + device_sensors)
    
    # Store ref voor latere updates
    hass.data[DOMAIN]["sensors"] = {"unknown": unknown_sensor, "devices": device_sensors}
    _LOGGER.info("[PowerSense] Sensoren geïnitialiseerd.")

class PowerSenseUnknownSensor(SensorEntity):
    def __init__(self, analyzer):
        self._analyzer = analyzer
    @property
    def name(self): return "PowerSense Overig (Onbekend)"
    @property
    def unique_id(self): return "powersense_unknown_total"
    @property
    def state(self): return self._analyzer.unknown_rest
    @property
    def unit_of_measurement(self): return "W"

class PowerSenseDeviceSensor(SensorEntity):
    def __init__(self, analyzer, device_name):
        self._analyzer = analyzer
        self._name = device_name
    @property
    def name(self): return f"PowerSense {self._name}"
    @property
    def unique_id(self): return f"powersense_{self._name.lower().replace(' ', '_')}"
    @property
    def state(self): 
        # Geef wattage terug als apparaat actief is
        return self._analyzer.registered_appliances.get(self._name, {}).get("mean_watt", 0) if self._analyzer.registered_appliances.get(self._name, {}).get("active") else 0
    @property
    def unit_of_measurement(self): return "W"
