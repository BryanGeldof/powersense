class PowerSenseCard extends HTMLElement {
  set hass(hass) {
    if (!this.content) {
      this.innerHTML = `
        <ha-card header="🤖 PowerSense Realtime Status">
          <div class="card-content" style="padding: 16px; font-family: sans-serif;">
            <div id="total-banner" style="font-size: 24px; font-weight: bold; margin-bottom: 15px; text-align: center;">-- W</div>
            
            <div class="progress-bar-container" style="display: flex; height: 24px; width: 100%; border-radius: 12px; overflow: hidden; background-color: var(--secondary-background-color); margin-bottom: 20px;">
              <div id="bar-known" style="background-color: #4CAF50; transition: width 0.5s ease;"></div>
              <div id="bar-baseload" style="background-color: #FFC107; transition: width 0.5s ease;"></div>
              <div id="bar-unknown" style="background-color: #2196F3; transition: width 0.5s ease;"></div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; font-size: 14px;">
              <div style="color: #4CAF50;">● Bekende Apparaten: <span id="txt-known">0W</span></div>
              <div style="color: #FFC107;">● Baseload (Sluimer): <span id="txt-base">0W</span></div>
              <div style="color: #2196F3;">● Onbekend Restant: <span id="txt-unknown">0W</span></div>
              <div style="color: var(--primary-text-color);">● AI Herkenning: <span id="txt-eff">100%</span></div>
            </div>

            <hr style="border: 0; border-top: 1px solid var(--divider-color); margin: 15px 0;">
            
            <div style="font-weight: bold; margin-bottom: 8px;">Actieve Gedetecteerde Apparaten:</div>
            <div id="active-list" style="font-size: 14px; line-height: 1.6;"></div>
          </div>
        </ha-card>
      `;
      this.content = this.querySelector('.card-content');
    }

    const entityId = 'sensor.powersense_unknown_restwaarde';
    const effEntityId = 'sensor.powersense_deconstructie_efficiency';
    const stateObj = hass.states[entityId];
    const effObj = hass.states[effEntityId];

    if (!stateObj) {
      this.querySelector('#total-banner').innerText = "Sensor niet gevonden";
      return;
    }

    const attrs = stateObj.attributes;
    const total = attrs.total_power || 0;
    const baseload = attrs.baseload || 0;
    const unknown = parseInt(stateObj.state) || 0;
    
    let known = total - baseload - unknown;
    if (known < 0) known = 0;

    this.querySelector('#total-banner').innerText = `Live Huisverbruik: ${total} W`;
    this.querySelector('#txt-known').innerText = `${known} W`;
    this.querySelector('#txt-base').innerText = `${baseload} W`;
    this.querySelector('#txt-unknown').innerText = `${unknown} W`;
    if (effObj) this.querySelector('#txt-eff').innerText = `${effObj.state}%`;

    const maxVal = total > 0 ? total : 1;
    const pctKnown = (known / maxVal) * 100;
    const pctBase = (baseload / maxVal) * 100;
    const pctUnknown = (unknown / maxVal) * 100;

    this.querySelector('#bar-known').style.width = `${pctKnown}%`;
    this.querySelector('#bar-baseload').style.width = `${pctBase}%`;
    this.querySelector('#bar-unknown').style.width = `${pctUnknown}%`;

    let listHtml = "";
    let activeCount = 0;
    if (attrs.registered_appliances) {
      for (const [name, app] of Object.entries(attrs.registered_appliances)) {
        if (app.active) {
          activeCount++;
          listHtml += `<div style="display: flex; justify-content: space-between; background: rgba(76, 175, 80, 0.1); padding: 4px 8px; border-radius: 4px; margin-bottom: 4px;">
            <span>⚡ <b>${name}</b></span>
            <span>${app.mean_watt} W</span>
          </div>`;
        }
      }
    }

    if (activeCount === 0) {
      listHtml = `<div style="color: var(--secondary-text-color); font-style: italic;">Geen specifieke apparaten actief gedetecteerd.</div>`;
    }

    this.querySelector('#active-list').innerHTML = listHtml;
  }

  getCardSize() {
    return 3;
  }
}

customElements.define('powersense-card', PowerSenseCard);

window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === 'powersense-card')) {
  window.customCards.push({
    type: "powersense-card",
    name: "PowerSense AI Matrix Card",
    description: "Toont realtime welke apparaten stroom verbruiken en wat nog onbekend is.",
    preview: true
  });
}
