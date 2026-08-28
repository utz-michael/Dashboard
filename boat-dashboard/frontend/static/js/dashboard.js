const gRpm = new RadialGauge(document.getElementById("gauge-rpm"), {
  min: 0, max: 5000, majorStep: 500, unit: "RPM", label: "Drehzahl", decimals: 0,
  zones: [{ from: 4500, to: 5000, color: "#c0392b" }],
});
const gSpeed = new RadialGauge(document.getElementById("gauge-speed"), {
  min: 0, max: 60, majorStep: 10, unit: "km/h", label: "Geschwindigkeit", decimals: 1,
});
const gOil = new RadialGauge(document.getElementById("gauge-oil"), {
  min: 0, max: 10, majorStep: 2, unit: "bar", label: "Öldruck", decimals: 2,
  zones: [{ from: 0, to: 0.8, color: "#c0392b" }],
});
const gTemp = new RadialGauge(document.getElementById("gauge-temp"), {
  min: 100, max: 250, majorStep: 25, unit: "°F", label: "Kühlwasser", decimals: 0,
  zones: [{ from: 220, to: 250, color: "#c0392b" }],
});
const gVolt = new RadialGauge(document.getElementById("gauge-volt"), {
  min: 10, max: 16, majorStep: 1, unit: "V", label: "Bordspannung", decimals: 2,
  zones: [{ from: 10, to: 11.5, color: "#c0392b" }, { from: 14.8, to: 16, color: "#c0392b" }],
});
const gCompass = new CompassGauge(document.getElementById("gauge-compass"));
const gRudder = new RudderGauge(document.getElementById("gauge-rudder"), { range: 40 });

const tFuel = new TankBar(document.getElementById("tank-fuel"), { color: "#d4870f" });
const tFresh = new TankBar(document.getElementById("tank-fresh"), { color: "#0b7fb0" });
const tBlack = new TankBar(document.getElementById("tank-black"), { color: "#6b5636" });

const allGauges = [gRpm, gSpeed, gOil, gTemp, gVolt, gCompass, gRudder, tFuel, tFresh, tBlack];

function renderAll() {
  allGauges.forEach(g => g.render());
}

function applySnapshot(d) {
  gRpm.setValue(d.rpm);
  gSpeed.setValue(d.speed_kmh);
  gOil.setValue(d.oil_pressure_bar);
  gTemp.setValue(d.coolant_temp_f);
  gVolt.setValue(d.battery_voltage);
  gCompass.setValue(d.heading_deg, d.heading_ref);
  gRudder.setValue(d.rudder_deg);
  tFuel.setValue(d.tank_fuel_pct);
  tFresh.setValue(d.tank_fresh_pct);
  tBlack.setValue(d.tank_black_pct);
  renderAll();
}

// ---------- WebSocket mit Auto-Reconnect ----------
const banner = document.getElementById("conn-banner");
let lastMessageAt = 0;

function setBanner(visible) {
  banner.classList.toggle("hidden", !visible);
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => setBanner(false);
  ws.onmessage = (ev) => {
    lastMessageAt = Date.now();
    try {
      applySnapshot(JSON.parse(ev.data));
    } catch (e) { /* ignore malformed frame */ }
  };
  ws.onclose = () => {
    setBanner(true);
    setTimeout(connect, 2000);
  };
  ws.onerror = () => ws.close();
}
connect();

// Banner zeigen, falls seit 6s keine Daten mehr kamen (z.B. UDP-Quelle weg)
setInterval(() => {
  if (lastMessageAt && Date.now() - lastMessageAt > 6000) setBanner(true);
}, 2000);

// Neu zeichnen bei Größenänderung (Fenster/Bildschirm-Rotation)
window.addEventListener("resize", () => requestAnimationFrame(renderAll));
renderAll();
