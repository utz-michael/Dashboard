// Einfache, abhängigkeitsfreie Canvas-Gauges für das Motor-Dashboard.
// Funktioniert komplett offline (kein CDN, kein Internet nötig).

function fitCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(1, Math.round(rect.width * dpr));
  const h = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w: rect.width, h: rect.height };
}

function deg2rad(d) { return (d * Math.PI) / 180; }
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

// ---------- Radiales Rundinstrument (RPM, Speed, Öldruck, Temperatur, Spannung) ----------
class RadialGauge {
  constructor(canvas, cfg) {
    this.canvas = canvas;
    this.cfg = Object.assign({
      min: 0, max: 100, unit: "", label: "",
      decimals: 0, majorStep: 10, zones: [],
      startAngle: 135, sweep: 270,
      needleColor: "#e8edf2", valueNoData: "--",
    }, cfg);
    this.value = null;
  }

  setValue(v) { this.value = v; }

  render() {
    const { ctx, w, h } = fitCanvas(this.canvas);
    const cfg = this.cfg;
    ctx.clearRect(0, 0, w, h);

    const cx = w / 2, cy = h / 2 + h * 0.05;
    const radius = Math.min(w, h) * 0.42;
    const startRad = deg2rad(cfg.startAngle);
    const endRad = deg2rad(cfg.startAngle + cfg.sweep);
    const valToAngle = (v) => deg2rad(cfg.startAngle + cfg.sweep * (clamp(v, cfg.min, cfg.max) - cfg.min) / (cfg.max - cfg.min));

    // Hintergrund-Track
    ctx.lineWidth = radius * 0.14;
    ctx.strokeStyle = "#1c232c";
    ctx.lineCap = "butt";
    ctx.beginPath();
    ctx.arc(cx, cy, radius, startRad, endRad, false);
    ctx.stroke();

    // Farbzonen (z.B. rot im Grenzbereich)
    cfg.zones.forEach(z => {
      ctx.strokeStyle = z.color;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, valToAngle(z.from), valToAngle(z.to), false);
      ctx.stroke();
    });

    // Ticks + Labels
    ctx.fillStyle = "#93a0ad";
    ctx.font = `${Math.round(radius * 0.14)}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (let v = cfg.min; v <= cfg.max + 1e-9; v += cfg.majorStep) {
      const a = valToAngle(v);
      const r1 = radius * 1.12, r2 = radius * 1.28;
      ctx.strokeStyle = "#4a5560";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(cx + r1 * Math.cos(a), cy + r1 * Math.sin(a));
      ctx.lineTo(cx + radius * 1.0 * Math.cos(a), cy + radius * 1.0 * Math.sin(a));
      ctx.stroke();
      const lx = cx + r2 * Math.cos(a), ly = cy + r2 * Math.sin(a);
      ctx.fillText(cfg.tickFormat ? cfg.tickFormat(v) : String(Math.round(v)), lx, ly);
    }

    // Nadel
    if (this.value !== null && this.value !== undefined) {
      const a = valToAngle(this.value);
      ctx.strokeStyle = cfg.needleColor;
      ctx.lineWidth = Math.max(3, radius * 0.045);
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(cx - radius * 0.12 * Math.cos(a), cy - radius * 0.12 * Math.sin(a));
      ctx.lineTo(cx + radius * 0.92 * Math.cos(a), cy + radius * 0.92 * Math.sin(a));
      ctx.stroke();
    }
    ctx.fillStyle = "#e8edf2";
    ctx.beginPath();
    ctx.arc(cx, cy, radius * 0.07, 0, Math.PI * 2);
    ctx.fill();

    // Zahlenwert in der Mitte
    const valText = (this.value === null || this.value === undefined)
      ? cfg.valueNoData
      : this.value.toFixed(cfg.decimals);
    ctx.fillStyle = "#f5f8fa";
    ctx.font = `bold ${Math.round(radius * 0.42)}px sans-serif`;
    ctx.fillText(valText, cx, cy - radius * 0.42);
    ctx.fillStyle = "#93a0ad";
    ctx.font = `${Math.round(radius * 0.16)}px sans-serif`;
    ctx.fillText(cfg.unit, cx, cy - radius * 0.10);
    ctx.font = `${Math.round(radius * 0.15)}px sans-serif`;
    ctx.fillText(cfg.label, cx, cy + radius * 0.55);
  }
}

// ---------- Vertikaler Tankbalken ----------
class TankBar {
  constructor(canvas, cfg) {
    this.canvas = canvas;
    this.cfg = Object.assign({ color: "#3aa0ff" }, cfg);
    this.value = null; // 0-100
  }
  setValue(v) { this.value = v; }
  render() {
    const { ctx, w, h } = fitCanvas(this.canvas);
    ctx.clearRect(0, 0, w, h);
    const padX = w * 0.28, padTop = h * 0.08, padBottom = h * 0.10;
    const barW = w - padX * 2;
    const barH = h - padTop - padBottom;
    const x = padX, y = padTop;

    ctx.strokeStyle = "#4a5560";
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, barW, barH);

    const pct = this.value === null || this.value === undefined ? null : clamp(this.value, 0, 100);
    if (pct !== null) {
      const fillH = (barH - 4) * (pct / 100);
      ctx.fillStyle = this.cfg.color;
      ctx.fillRect(x + 2, y + barH - 2 - fillH, barW - 4, fillH);
    }

    ctx.fillStyle = "#f5f8fa";
    ctx.font = `bold ${Math.round(w * 0.20)}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(pct === null ? "--" : `${Math.round(pct)}%`, w / 2, y + barH / 2);
  }
}

// ---------- Ruderlage (horizontal, Mitte = geradeaus) ----------
class RudderGauge {
  constructor(canvas, cfg) {
    this.canvas = canvas;
    this.cfg = Object.assign({ range: 40 }, cfg); // +/- Grad
    this.value = null;
  }
  setValue(v) { this.value = v; }
  render() {
    const { ctx, w, h } = fitCanvas(this.canvas);
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h * 0.55;
    const trackW = w * 0.8, trackH = h * 0.18;
    const x0 = cx - trackW / 2;

    ctx.strokeStyle = "#4a5560";
    ctx.lineWidth = 2;
    ctx.strokeRect(x0, cy - trackH / 2, trackW, trackH);
    // Mittelmarkierung
    ctx.beginPath();
    ctx.moveTo(cx, cy - trackH / 2 - 6);
    ctx.lineTo(cx, cy + trackH / 2 + 6);
    ctx.strokeStyle = "#6b7684";
    ctx.stroke();

    const v = this.value === null || this.value === undefined ? null : clamp(this.value, -this.cfg.range, this.cfg.range);
    if (v !== null) {
      const px = cx + (v / this.cfg.range) * (trackW / 2);
      ctx.fillStyle = "#ffb020";
      ctx.beginPath();
      ctx.moveTo(px, cy - trackH / 2 - 10);
      ctx.lineTo(px - 8, cy - trackH / 2 - 22);
      ctx.lineTo(px + 8, cy - trackH / 2 - 22);
      ctx.closePath();
      ctx.fill();
    }

    ctx.fillStyle = "#93a0ad";
    ctx.font = `${Math.round(h * 0.14)}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("P", x0 - 14, cy);
    ctx.fillText("S", x0 + trackW + 14, cy);

    ctx.fillStyle = "#f5f8fa";
    ctx.font = `bold ${Math.round(h * 0.22)}px sans-serif`;
    ctx.fillText(v === null ? "--" : `${v.toFixed(0)}°`, cx, cy + h * 0.30);
  }
}

// ---------- Kompass ----------
class CompassGauge {
  constructor(canvas) {
    this.canvas = canvas;
    this.heading = null;
    this.ref = "";
  }
  setValue(heading, ref) { this.heading = heading; this.ref = ref || ""; }
  render() {
    const { ctx, w, h } = fitCanvas(this.canvas);
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h / 2 + h * 0.02;
    const radius = Math.min(w, h) * 0.38;

    ctx.strokeStyle = "#1c232c";
    ctx.lineWidth = radius * 0.10;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.stroke();

    const dirs = [["N", 0], ["E", 90], ["S", 180], ["W", 270]];
    ctx.fillStyle = "#93a0ad";
    ctx.font = `${Math.round(radius * 0.22)}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    dirs.forEach(([label, deg]) => {
      const a = deg2rad(deg - 90);
      const r = radius * 1.22;
      ctx.fillText(label, cx + r * Math.cos(a), cy + r * Math.sin(a));
    });
    for (let deg = 0; deg < 360; deg += 30) {
      const a = deg2rad(deg - 90);
      const r1 = radius * 0.95, r2 = radius * 1.05;
      ctx.strokeStyle = "#4a5560";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(cx + r1 * Math.cos(a), cy + r1 * Math.sin(a));
      ctx.lineTo(cx + r2 * Math.cos(a), cy + r2 * Math.sin(a));
      ctx.stroke();
    }

    if (this.heading !== null && this.heading !== undefined) {
      const a = deg2rad(this.heading - 90);
      ctx.fillStyle = "#ff5a5a";
      ctx.beginPath();
      ctx.moveTo(cx + radius * 0.85 * Math.cos(a), cy + radius * 0.85 * Math.sin(a));
      ctx.lineTo(cx + radius * 0.15 * Math.cos(a + 2.9), cy + radius * 0.15 * Math.sin(a + 2.9));
      ctx.lineTo(cx + radius * 0.15 * Math.cos(a - 2.9), cy + radius * 0.15 * Math.sin(a - 2.9));
      ctx.closePath();
      ctx.fill();
    }

    const txt = (this.heading === null || this.heading === undefined) ? "--" : `${Math.round(this.heading)}°`;
    ctx.fillStyle = "#f5f8fa";
    ctx.font = `bold ${Math.round(radius * 0.42)}px sans-serif`;
    ctx.fillText(txt, cx, cy - radius * 0.02);
    ctx.fillStyle = "#93a0ad";
    ctx.font = `${Math.round(radius * 0.16)}px sans-serif`;
    ctx.fillText(this.ref === "magnetic" ? "MAG" : this.ref === "true" ? "TRUE" : "", cx, cy + radius * 0.32);
    ctx.font = `${Math.round(radius * 0.15)}px sans-serif`;
    ctx.fillStyle = "#93a0ad";
    ctx.fillText("Kompass", cx, cy + radius * 0.60);
  }
}
