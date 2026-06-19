def _trigger_hass_notification(self, cluster_id, wattage):
        config_entry = self.hass.config_entries.async_entries(DOMAIN)[0]
        notify_device = config_entry.data.get("notification_device", "none")
        suggestion = self._get_suggestion(wattage)

        # ---- MELDING 1: ALTIJD IN DE HOME ASSISTANT UI ----
        self.hass.components.persistent_notification.create(
            title="🤖 PowerSense: Nieuw Apparaat!",
            message=(
                f"Ik heb een herkenbaar verbruik gevonden van circa **{wattage}W**.<br>"
                f"**Vermoedelijk:** {suggestion}.<br><br>"
                f"Als je de notificatie op je gsm invult, wordt dit apparaat automatisch opgeslagen!"
            ),
            notification_id=f"powersense_{cluster_id}"
        )

        # ---- MELDING 2: OOK OP JE GSM (ALS DEZE IS GESELECTEERD) ----
        if notify_device and notify_device != "none":
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "notify",
                    notify_device.split(".")[1],
                    {
                        "title": "🤖 PowerSense: Nieuw Apparaat!",
                        "message": f"Verbruik van {wattage}W ontdekt.\nSuggestie: {suggestion}",
                        "data": {
                            "actions": [
                                {
                                    "action": f"POWERSENSE_LABEL_{cluster_id}",
                                    "title": "Geef naam",
                                    "behavior": "text_input",
                                    "text_input_button_title": "Opslaan"
                                }
                            ]
                        }
                    }
                )
            )
