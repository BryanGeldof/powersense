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

    # MODERNE ASYNC FRONTEND REGISTRATIE (Voorkomt crashes en laadt de card correct)
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.components.frontend import add_extra_js_url

    try:
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                "/powersense/card.js",
                hass.config.path("custom_components/powersense/card.js"),
                cache_headers=False
            )
        ])
        add_extra_js_url(hass, "/powersense/card.js")
        _LOGGER.info("[PowerSense] Frontend kaart succesvol geregistreerd.")
    except Exception as e:
        _LOGGER.error(f"[PowerSense] Fout bij registreren frontend kaart: {e}")

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
                _LOGGER.error("[PowerSense] Kan boost-modus niet starten: Analyzer niet gevonden.")
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

    # ---- 1b. SERVICES VOOR DE CARD (LABEL / NEGEER ONBEKEND APPARAAT) ----
    async def label_cluster(call: ServiceCall):
        cluster_id = call.data.get("cluster_id")
        name = call.data.get("name")
        active_analyzer = hass.data[DOMAIN].get("analyzer")
        if active_analyzer and cluster_id in active_analyzer.temporary_clusters:
            mean_wattage = active_analyzer.temporary_clusters[cluster_id]["mean_watt"]
            active_analyzer.save_appliance(name, mean_wattage)
            del active_analyzer.temporary_clusters[cluster_id]
            _LOGGER.info(f"[PowerSense] Cluster {cluster_id} gelabeld als {name} via card.")
        else:
            _LOGGER.warning(f"[PowerSense] label_cluster: cluster {cluster_id} niet gevonden.")

    async def ignore_cluster(call: ServiceCall):
        cluster_id = call.data.get("cluster_id")
        active_analyzer = hass.data[DOMAIN].get("analyzer")
        if active_analyzer and cluster_id in active_analyzer.temporary_clusters:
            active_analyzer.temporary_clusters[cluster_id]["notified"] = True
            active_analyzer.temporary_clusters[cluster_id]["count"] = -999  # voorkomt herhaalde meldingen
            _LOGGER.info(f"[PowerSense] Cluster {cluster_id} gemarkeerd als 'onbekend/genegeerd'.")
        else:
            _LOGGER.warning(f"[PowerSense] ignore_cluster: cluster {cluster_id} niet gevonden.")

    hass.services.async_register(DOMAIN, "label_cluster", label_cluster)
    hass.services.async_register(DOMAIN, "ignore_cluster", ignore_cluster)

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

    hass.bus.async_listen("mobile_app_notification_action", handle_notification_action)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop("analyzer", None)
    return unload_ok
