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

    from .analyzer import PeakSenseClusterAnalyzer
    analyzer = PeakSenseClusterAnalyzer(hass)
    hass.data[DOMAIN]["analyzer"] = analyzer

    # Waterdichte registratie van de kaart via de HTTP-component
    try:
        hass.http.register_static_path(
            "/powersense/card.js",
            hass.config.path("custom_components/powersense/card.js"),
            cache_headers=False
        )
        from homeassistant.components.frontend import add_extra_js_url
        add_extra_js_url(hass, "/powersense/card.js")
        _LOGGER.info("[PowerSense] Frontend kaart succesvol geregistreerd via static path.")
    except Exception as e:
        _LOGGER.error(f"[PowerSense] Fout bij registreren frontend kaart: {e}")

    # SERVICES
    async def start_boost(call: ServiceCall):
        active_analyzer = hass.data[DOMAIN].get("analyzer")
        if active_analyzer:
            active_analyzer.set_boost_mode(True)
            hass.components.persistent_notification.create(
                title="🚀 PowerSense: Boost-modus Actief",
                message="De snelle leermodus staat aan voor 60 minuten. Apparaten worden nu direct automatisch herkend en gelabeld!",
                notification_id="powersense_boost_status"
            )

    async def stop_boost(call: ServiceCall):
        active_analyzer = hass.data[DOMAIN].get("analyzer")
        if active_analyzer:
            active_analyzer.set_boost_mode(False)

    async def label_cluster(call: ServiceCall):
        cluster_id = call.data.get("cluster_id")
        name = call.data.get("name")
        active_analyzer = hass.data[DOMAIN].get("analyzer")
        if active_analyzer and cluster_id in active_analyzer.temporary_clusters:
            mean_wattage = active_analyzer.temporary_clusters[cluster_id]["mean_watt"]
            active_analyzer.save_appliance(name, mean_wattage)
            del active_analyzer.temporary_clusters[cluster_id]

    async def ignore_cluster(call: ServiceCall):
        cluster_id = call.data.get("cluster_id")
        active_analyzer = hass.data[DOMAIN].get("analyzer")
        if active_analyzer and cluster_id in active_analyzer.temporary_clusters:
            active_analyzer.temporary_clusters[cluster_id]["count"] = -999

    hass.services.async_register(DOMAIN, "start_boost_mode", start_boost)
    hass.services.async_register(DOMAIN, "stop_boost_mode", stop_boost)
    hass.services.async_register(DOMAIN, "label_cluster", label_cluster)
    hass.services.async_register(DOMAIN, "ignore_cluster", ignore_cluster)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop("analyzer", None)
    return unload_ok
