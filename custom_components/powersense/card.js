class PowerSenseCard extends HTMLElement {
  set hass(hass) {
    if (!this.content) {
      this.innerHTML = `
        <ha-card header="🤖 PowerSense AI Matrix Overzicht">
          <div class="card-content" style="padding: 16px; font-family: sans-serif;">
            <div id="total-banner" style="font-size: 24px; font-weight: bold; margin-bottom: 15px; text-align: center; color: var(--primary-color);">-- W</div>
            
            <div class="progress-bar-container" style="display: flex; height: 24px; width: 100%; border-radius: 12px; overflow: hidden; background-color: var(--secondary-background-color); margin-bottom: 20px;">
              <div id="bar-known" style="background-color: #4CAF50; transition: width 0.5s ease;"></div>
              <div id="bar-baseload" style="background-color: #FFC107; transition: width 0.5s ease;"></div>
              <div id="bar-unknown" style="background-color: #2196F3; transition: width 0.5s ease;"></div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; font-size: 14px;">
              <div style="color: #4CAF50;">● Geregistreerd Actief: <span id="txt-known">0W</span></div>
              <div style="color: #FFC107;">● Baseload (Sluimer): <span id="txt-base">0W</span></div>
              <div style="color: #2196F3;">● Onbekend Restant: <span id="txt-unknown">0W</span></div>
              <div style="color: var(--primary-text-color);">● AI Efficiëntie: <span id="txt-eff">100%</span></div>
            </div>

            <hr style="border: 0; border-top: 1px solid var(--divider-color); margin: 15px 0;">
            
            <div style="font-weight: bold; margin-bottom: 8px; color: var(--primary-text-color);">⚡ Live Status Apparaten:</div>
            <div id="active-list" style="font-size: 14px; line-height: 1.6; margin-bottom: 15px;"></div>

            <hr style="border: 0; border-top: 1px solid var(--divider-color); margin: 15px 0;">

            <div style="font-weight: bold; margin-bottom: 8px; color: var(--primary-text-color);">📦 Gekoppelde AI Database (Power Stamps):</div>
            <div id="database-list" style="font-size: 13px; max-height: 250px; overflow-y: auto; background: var(--table-row-alternative-background-color); padding: 8px; border-radius: 6px;"></div>
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
      this.querySelector('#total-banner').innerText = "Wachten op AI data...";
      return;
    }

    const attrs = stateObj.attributes;
    const total = attrs.total_power || 0;
    const baseload = attrs.baseload || 0;
    const unknown = parseInt(stateObj.state) || 0;
    
    let known = total - baseload - unknown;
    if (known < 0) known = 0;

    this.querySelector('#total-banner').innerText = `${total} W`;
    this.querySelector('#txt-known').innerText = `${known} W`;
    this.querySelector('#txt-base').innerText = `${baseload} W`;
    this.querySelector('#txt-unknown').innerText = `${unknown} W`;
    if (effObj) this.querySelector('#txt-eff').innerText = `${effObj.state}%`;

    const maxVal = total > 0 ? total : 1;
    this.querySelector('#bar-known').style.width = `${(known / maxVal) * 100}%`;
    this.querySelector('#bar-baseload').style.width = `${(baseload / maxVal) * 100}%`;
    this.querySelector('#bar-unknown').style.width = `${(unknown / maxVal) * 100}%`;

    // 1. Live Actieve Apparaten
    let activeHtml = "";
    let dbHtml = `<table style="width:100%; text-align:left; border-collapse: collapse;">
                    <tr style="border-bottom: 1px solid var(--divider-color); font-weight:bold;">
                      <th style="padding:4px;">Apparaat</th>
                      <th style="padding:4px; text-align:right;">Power Stamp</th>
                    </tr>`;

    if (attrs.registered_appliances && Object.keys(attrs.registered_appliances).length > 0) {
      for (const [name, app] of Object.entries(attrs.registered_appliances)) {
        // Toevoegen aan database tabel
        dbHtml += `<tr style="border-bottom: 1px solid rgba(0,0,0,0.05);">
                    <td style="padding:6px 4px;">🔹 ${name}</td>
                    <td style="padding:6px 4px; text-align:right; font-weight:bold; color:#4CAF50;">${app.mean_watt} W</td>
                   </tr>`;

        // Toevoegen aan live-lijst indien actief
        if (app.active) {
          activeHtml += `<div style="display: flex; justify-content: space-between; background: rgba(76, 175, 80, 0.1); padding: 6px 10px; border-radius: 6px; margin-bottom: 5px; border-left: 4px solid #4CAF50;">
            <span>🟢 <b>${name}</b></span>
            <span style="font-weight:bold;">${app.mean_watt} W</span>
          </div>`;
        }
      }
    } else {
      dbHtml += `<tr><td colspan="2" style="padding:10px; text-align:center; color:var(--secondary-text-color); font-style:italic;">Nog geen apparaten getraind. Start de boost-modus!</td></tr>`;
    }
    dbHtml += `</table>`;

    if (!activeHtml) {
      activeHtml = `<div style="color: var(--secondary-text-color); font-style: italic; padding: 4px;">Alle bekende apparaten staan momenteek uit.</div>`;
    }

    this.querySelector('#active-list').innerHTML = activeHtml;
    this.querySelector('#database-list').innerHTML = dbHtml;
  }

  getCardSize() {
    return 4;
  }
}

customElements.define('powersense-card', PowerSenseCard);

window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === 'powersense-card')) {
  window.customCards.push({
    type: "powersense-card",
    name: "PowerSense AI Matrix Card",
    description: "Toont de live stroom-deconstructie en alle opgeslagen power stamps.",
    preview: true
  });
}
