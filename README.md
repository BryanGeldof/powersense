# 🚀 PowerSense AI Engine (V0.2.0)

PowerSense is een geavanceerde, lokale Non-Intrusive Load Monitoring (NILM) AI-engine voor Home Assistant. De integratie analyseert live de schommelingen op je P1-meter om individuele apparaten in huis te herkennen op basis van hun unieke wattage-voetafdruk.

## ✨ Nieuw in V0.2.0b1
* **Ultra-gevoelig:** Detecteert nu vermogensflanken vanaf **5 Watt** (perfect voor sluipverbruik en stand-by apparaten).
* **Interactieve GSM Notificaties:** Stuurt direct een pushnotificatie naar je smartphone zodra een nieuw apparaat is geïsoleerd. Je kunt de naam van het apparaat rechtstreeks vanuit de notificatie typen en opslaan!
* **Interactieve Boost-modus:** Activeer de snelle leermodus voor 60 minuten waarin elk apparaat dat je aan- of uitzet direct wordt geregistreerd.
* **Uitschakeldetectie:** Herkent nu ook wanneer actieve apparaten weer uitschakelen (negatieve flanken).
* **Automatische Opschoning:** Verwijdert ongetrainde patronen automatisch na 48 uur om je database schoon te houden.

---

## 📂 Installatie via HACS

1. Ga in Home Assistant naar **HACS** > **Integraties**.
2. Klik rechtsboven op de drie puntjes en kies **Aangepaste repositories** (Custom repositories).
3. Plak de URL van deze GitHub repository in het veld.
4. Selecteer bij categorie: **Integratie** en klik op **Toevoegen**.
5. Klik op **PowerSense AI Engine**, kies **Downloaden** (schakel 'Toon bètaversies' in en kies `v0.2.0b1`).
6. **Herstart Home Assistant volledig.**

---

## ⚙️ Configuratie

1. Ga naar **Instellingen** > **Apparaten & Diensten**.
2. Klik rechtsonder op **Integratie toevoegen** en zoek naar **PowerSense**.
3. Selecteer je **P1 Totaal Vermogen Sensor** (kW of W).
4. Kies je smartphone in de dropdown-menu als je interactieve pushnotificaties wilt ontvangen (optioneel).

---

## 🏎️ Handige Functies

### 🚀 Boost-modus (Snelle leermodus)
Wil je niet wachten tot apparaten 3 keer zijn herhaald? Activeer de Boost-modus om apparaten direct bij de eerste klik te trainen:
1. Ga naar **Ontwikkelaarstools** > **Services** (Diensten).
2. Selecteer de service `powersense.start_boost_mode` en klik op **Service uitvoeren**.
3. Loop door je huis en zet de apparaten die je wilt trainen één voor één **AAN** en na een minuutje weer **UIT**. Je gsm trilt direct om de naam te vragen!

---

## 📊 Sensoren
De integratie maakt automatisch twee sensoren aan:
1. `sensor.powersense_unknown_restwaarde`: Het overige live verbruik in huis dat nog niet aan een specifiek apparaat is gekoppeld.
2. `sensor.powersense_deconstructie_efficiency`: Een percentage dat aangeeft hoe goed de AI-engine in staat is om je huidige stroomnet te ontleden (streeft naar 100%).
