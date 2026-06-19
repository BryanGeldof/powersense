elif device.startswith("notify."):
                try:
                    domain_service = device.split(".")
                    self.hass.async_create_task(
                        self.hass.services.async_call(
                            domain_service[0],  # "notify"
                            domain_service[1],  # "mobile_app_..."
                            {
                                "title": "🤖 PowerSense: Nieuw Apparaat!",
                                "message": f"Verbruik van {wattage}W ontdekt.\nSuggestie: {suggestion}",
                                "data": {
                                    # Dwing de app om bij een klik naar het notificaties-overzicht te gaan
                                    "clickAction": "/lovelace/powersense", # Voor Android (of bijv. /config/integrations)
                                    "url": "/lovelace/powersense",         # Voor iOS (Apple)
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
                    _LOGGER.info(f"[PowerSense] Pushbericht inclusief clickAction gestuurd naar {device}")
                except Exception as e:
                    _LOGGER.error(f"[PowerSense] GSM notificatie-fout naar {device}: {e}")
