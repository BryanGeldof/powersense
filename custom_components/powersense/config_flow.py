import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import DOMAIN, CONF_P1_SENSOR

class PowerSenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PowerSense AI Engine."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="PowerSense AI Engine", data=user_input)

        # Haal alle notificatiediensten op uit Home Assistant
        all_services = self.hass.services.async_services().get("notify", {})
        
        notify_options = [
            {"value": "persistent_notification", "label": "Home Assistant UI (Meldingenpaneel)"}
        ]
        
        for service_name in all_services.keys():
            if "mobile_app" in service_name or service_name.startswith("notify_"):
                label = service_name.replace("mobile_app_", "GSM/Tablet: ").replace("_", " ").title()
                notify_options.append({"value": f"notify.{service_name}", "label": label})

        data_schema = vol.Schema({
            vol.Required(CONF_P1_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            # CRITIEKE UPGRADE: multiple=True zorgt voor de selectielijst
            vol.Required("notification_devices", default=["persistent_notification"]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=notify_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True
                )
            ),
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
