import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Zet de integratie op vanuit een config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Initialiseer de analyzer centraal
    from .analyzer import PeakSenseClusterAnalyzer
    analyzer = PeakSenseClusterAnalyzer(hass)
    hass.data[DOMAIN]["analyzer"] = analyzer

    # ---- 1. SERVICE REGISTRATIE (BOOST MODUS) ----
    async def start_boost(call: ServiceCall):
        try:
            active_analyzer = hass.data[DOMAIN].get("analyzer")
            if active_analyzer:
                active_analyzer.set_boost_mode(True)
                
                hass.components.persistent_notification.create(
                    title="🚀 PowerSense: Boost-modus Actief",
                    message="De snelle leermodus staat aan voor 60 minuten. Elk apparaat dat je nu aan/uit zet, triggert direct een melding!",
                    notification_id="powersense_boost_status"
                )
                _LOGGER.info("[PowerSense] Boost-modus handmatig geactiveerd via service.")
            else:
                _LOGGER.error("[PowerSense] Kan boost-modus niet starten: Analyzer niet gevonden in hass.data.")
        except Exception as e:
            _LOGGER.error(f"[PowerSense] Fout in start_boost_mode service: {e}")

        async def auto_stop_boost(_):
            active_analyzer = hass.data[DOMAIN].get("analyzer")
            if active_analyzer:
                active_analyzer.set_boost_mode(False)
            _LOGGER.info("[PowerSense] Boost-modus automatisch beëindigd na 60 minuten.")
        
        from homeassistant.helpers.event import async_call_later
        async_call_later(hass, 3600, auto_stop_boost)

    async def stop_boost(call: ServiceCall):
        try:
            active_analyzer = hass.data[DOMAIN].get("analyzer")
            if active_analyzer:
                active_analyzer.set_boost_mode(False)
            _LOGGER.info("[PowerSense] Boost-modus handmatig uitgeschakeld.")
        except Exception as e:
            _LOGGER.error(f"[PowerSense] Fout in stop_boost_mode service: {e}")

    hass.services.async_register(DOMAIN, "start_boost_mode", start_boost)
    hass.services.async_register(DOMAIN, "stop_boost_mode", stop_boost)

    # ---- 2. EVENT LISTENER (GSM PUSHNOTIFICATIE INPUT) ----
    async def handle_notification_action(event):
        action = event.data.get("action", "")
        
        if action.startswith("POWERSENSE_LABEL_"):
            cluster_id = action.replace("POWERSENSE_LABEL_", "")
            user_response = event.data.get("text_input", "").strip()
            
            active_analyzer = hass.data[DOMAIN].get("analyzer")
            if user_response and active_analyzer:
                _LOGGER.info(f"[PowerSense] GSM Input ontvangen voor {cluster_id}: {user_response}")
                
                if cluster_id in active_analyzer.temporary_clusters:
                    mean_wattage = active_analyzer.temporary_clusters[cluster_id]["mean_watt"]
                    active_analyzer.save_appliance(user_response, mean_wattage)
                    del active_analyzer.temporary_clusters[cluster_id]
                else:
                    _LOGGER.warning(f"[PowerSense] Cluster {cluster_id} niet gevonden in tijdelijk geheugen.")

    hass.bus.async_listen("mobile_app_notification_action", handle_notification_action)

    # Laad het sensorplatform in (slechts eenmalig onderaan!)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Netjes opruimen wanneer de integratie wordt verwijderd."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop("analyzer", None)
    return unload_ok
