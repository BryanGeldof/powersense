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

        # Haal alle mobiele apparaten op
        notify_entities = [
            entity_id for entity_id in self.hass.states.async_entity_ids("notify")
            if "mobile_app" in entity_id
        ]

        if not notify_entities:
            notify_options = [{"value": "none", "label": "Alleen Home Assistant UI meldingen"}]
        else:
            notify_options = [{"value": ent, "label": ent.replace("notify.mobile_app_", "GSM: ")} for ent in notify_entities]
            notify_options.append({"value": "none", "label": "Alleen Home Assistant UI meldingen"})

        data_schema = vol.Schema({
            vol.Required(CONF_P1_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("notification_device", default="none"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=notify_options,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)