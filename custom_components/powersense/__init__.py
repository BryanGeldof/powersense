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

    # Initialiseer de analyzer
    from .analyzer import PeakSenseClusterAnalyzer
    analyzer = PeakSenseClusterAnalyzer(hass)
    hass.data[DOMAIN]["analyzer"] = analyzer

    # ---- 1. SERVICE REGISTRATIE (BOOST MODUS) ----
    async def start_boost(call: ServiceCall):
        analyzer.set_boost_mode(True)
        hass.components.persistent_notification.create(
            title="🚀 PowerSense: Boost-modus Actief",
            message="De snelle leermodus staat aan voor 60 minuten. Elk apparaat dat je nu aan/uit zet, triggert direct een melding!",
            notification_id="powersense_boost_status"
        )
        
        async def auto_stop_boost(_):
            analyzer.set_boost_mode(False)
            _LOGGER.info("[PowerSense] Boost-modus automatisch beëindigd na 60 minuten.")
        
        from homeassistant.helpers.event import async_call_later
        async_call_later(hass, 3600, auto_stop_boost)

    async def stop_boost(call: ServiceCall):
        analyzer.set_boost_mode(False)
        _LOGGER.info("[PowerSense] Boost-modus handmatig uitgeschakeld.")

    hass.services.async_register(DOMAIN, "start_boost_mode", start_boost)
    hass.services.async_register(DOMAIN, "stop_boost_mode", stop_boost)

    # ---- 2. EVENT LISTENER (INTERACTIEVE GSM PUSHNOTIFICATIE) ----
    async def handle_notification_action(event):
        action = event.data.get("action", "")
        
        if action.startswith("POWERSENSE_LABEL_"):
            cluster_id = action.replace("POWERSENSE_LABEL_", "")
            user_response = event.data.get("text_input", "").strip()
            
            if user_response:
                _LOGGER.info(f"[PowerSense] GSM Input ontvangen voor {cluster_id}: {user_response}")
                
                # Sla het apparaat nu permanent op via de nieuwe database-functie!
                mean_wattage = analyzer.temporary_clusters[cluster_id]["mean_watt"]
                analyzer.save_appliance(user_response, mean_wattage)
                
                # Ruim het tijdelijke cluster op
                if cluster_id in analyzer.temporary_clusters:
                    del analyzer.temporary_clusters[cluster_id]

    hass.bus.async_listen("mobile_app_notification_action", handle_notification_action)

    # Dit is de ENIGE plek waar deze regel hoort te staan!
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Netjes opruimen wanneer de integratie wordt verwijderd."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop("analyzer", None)
    return unload_ok
