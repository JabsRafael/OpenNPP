"use strict";

const SYS_LABELS = {
  nucleo: "Reator / núcleo", primario: "Primário (RCS)", pxs: "Salvaguardas (PXS)",
  gv1: "Gerador de Vapor 1", gv2: "Gerador de Vapor 2", turbina: "Turbina / geração", geral: "Geral",
};
const PRIMARY_SYS = ["nucleo", "primario", "pxs"];
const SECONDARY_SYS = ["gv1", "gv2", "turbina"];
const TIMESCALES = [1, 10, 60, 300, 720, 3600];
const NS = "http://www.w3.org/2000/svg";

// chips de leitura posicionados ao lado de cada componente do P&ID
const CHIP_LABEL = {
  reactor_power_pct: "Potência", fuel_temp_c: "T. comb.", rod_position_pct: "Barras",
  primary_inventory_pct: "Invent. RCS", coolant_tavg_c: "Tavg", coolant_thot_c: "T. quente",
  przr_pressure_bar: "PZR pressão", przr_level_pct: "PZR nível", sg1_level_pct: "GV1 nível",
  sg1_pressure_bar: "GV1 press.", sg1_steam_flow_kgs: "GV1 vapor", sg2_level_pct: "GV2 nível",
  sg2_pressure_bar: "GV2 press.", sg2_steam_flow_kgs: "GV2 vapor", gen_power_mwe: "Geração",
  turbine_rpm: "Rotação", cmt1_level_pct: "CMT", accum_press_bar: "ACUM", prhr_flow_pct: "PRHR",
  containment_press_bar: "Cont. P", containment_rad_msvh: "Cont. rad",
};
const CHIPS = [
  { x: 34, y: 500, k: "reactor_power_pct", big: 1 }, { x: 126, y: 500, k: "fuel_temp_c" },
  { x: 34, y: 540, k: "rod_position_pct" }, { x: 126, y: 540, k: "primary_inventory_pct" },
  { x: 196, y: 352, k: "coolant_tavg_c", sm: 1 }, { x: 302, y: 300, k: "coolant_thot_c", sm: 1 },
  { x: 120, y: 92, k: "przr_pressure_bar" }, { x: 120, y: 124, k: "przr_level_pct" },
  { x: 478, y: 164, k: "sg1_level_pct" }, { x: 478, y: 196, k: "sg1_pressure_bar" }, { x: 478, y: 228, k: "sg1_steam_flow_kgs" },
  { x: 478, y: 404, k: "sg2_level_pct" }, { x: 478, y: 436, k: "sg2_pressure_bar" }, { x: 478, y: 468, k: "sg2_steam_flow_kgs" },
  { x: 686, y: 208, k: "gen_power_mwe", big: 1 }, { x: 686, y: 248, k: "turbine_rpm" },
  { x: 28, y: 164, k: "cmt1_level_pct", sm: 1 }, { x: 28, y: 256, k: "accum_press_bar", sm: 1 }, { x: 28, y: 352, k: "prhr_flow_pct", sm: 1 },
  { x: 516, y: 72, k: "containment_press_bar", sm: 1 }, { x: 576, y: 72, k: "containment_rad_msvh", sm: 1 },
];
// vasos com nível de água animado: [id, chave, yCheio, yVazio]
const FILLS = [
  ["rpvFill", "primary_inventory_pct", 305, 470], ["pzrFill", "przr_level_pct", 126, 213],
  ["sg1Fill", "sg1_level_pct", 158, 280], ["sg2Fill", "sg2_level_pct", 400, 522],
];

let META = null, IR = {}, DI = {}, HR = {};
const fmt = (v, u) => (u === "rpm" || u === "ppm" || u === "" ? `${Math.round(v)}${u ? " " + u : ""}` : `${v.toFixed(1)} ${u}`);
const fmtSigned = v => `${v >= 0 ? "+" : ""}${Math.round(v)} pcm`;

function panelOf(system, key) {
  if (key === "cmd_feed_pump_start") return "secondary";
  if (PRIMARY_SYS.includes(system) || key === "cmd_reset_trip" || key === "cmd_auto_control") return "primary";
  if (SECONDARY_SYS.includes(system)) return "secondary";
  return "primary";
}

async function init() {
  META = await (await fetch("/api/meta")).json();
  META.ir.forEach(p => IR[p.key] = p);
  META.di.forEach(p => DI[p.key] = p);
  META.hr.forEach(p => HR[p.key] = p);
  buildChips();
  buildAlarms();
  buildControls();
  buildTimescale();
  const lr = document.getElementById("loca-range");
  lr.oninput = e => document.getElementById("loca-val").textContent = e.target.value + " %";
  lr.onchange = e => setLoca(+e.target.value);
  connect();
}

/* -------- chips no SVG -------- */
function buildChips() {
  const svg = document.getElementById("mimic");
  for (const c of CHIPS) {
    const w = c.sm ? 58 : (c.big ? 96 : 86), h = c.big ? 36 : (c.sm ? 26 : 30);
    const g = document.createElementNS(NS, "g");
    g.setAttribute("class", "chip"); g.setAttribute("transform", `translate(${c.x},${c.y})`);
    const r = document.createElementNS(NS, "rect");
    r.setAttribute("width", w); r.setAttribute("height", h); r.setAttribute("rx", 4); g.appendChild(r);
    const cl = document.createElementNS(NS, "text");
    cl.setAttribute("class", "cl"); cl.setAttribute("x", 6); cl.setAttribute("y", 11);
    cl.textContent = CHIP_LABEL[c.k] || IR[c.k].label; g.appendChild(cl);
    const cv = document.createElementNS(NS, "text");
    cv.setAttribute("class", "cv" + (c.big ? " big" : "")); cv.setAttribute("x", 6);
    cv.setAttribute("y", c.big ? 29 : 23); cv.setAttribute("data-k", c.k); cv.textContent = "--";
    g.appendChild(cv); svg.appendChild(g);
  }
}

/* -------- alarmes -------- */
const TRIP_KEYS = new Set(["reactor_tripped", "turbine_tripped", "safety_blocked", "alm_hi_cont_rad", "alm_hi_cont_press"]);
function buildAlarms() {
  const box = document.getElementById("alarms");
  META.di.forEach(p => {
    const row = document.createElement("div");
    row.className = "alarm-row" + (TRIP_KEYS.has(p.key) ? " trip" : ""); row.id = "di-" + p.key;
    row.innerHTML = `<span class="dot"></span><span>${p.label}</span>`; box.appendChild(row);
  });
}

/* -------- controles -------- */
function buildControls() {
  const panels = { primary: {}, secondary: {} };
  const add = (pan, sys, kind, p) => (panels[pan][sys] = panels[pan][sys] || { co: [], hr: [] })[kind].push(p);
  META.co.forEach(p => add(panelOf(p.system, p.key), p.system === "geral" ? (p.key === "cmd_feed_pump_start" ? "gv1" : "primario") : p.system, "co", p));
  META.hr.forEach(p => add(panelOf(p.system, p.key), p.system, "hr", p));
  for (const [pan, elId] of [["primary", "ctl-primary"], ["secondary", "ctl-secondary"]]) {
    const box = document.getElementById(elId);
    const order = pan === "primary" ? ["nucleo", "primario", "pxs"] : ["gv1", "gv2", "turbina"];
    for (const sys of order) {
      const grp = panels[pan][sys]; if (!grp) continue;
      const g = document.createElement("div"); g.className = "ctl-group";
      g.innerHTML = `<h4>${SYS_LABELS[sys] || sys}</h4>`;
      if (grp.co.length) {
        const coils = document.createElement("div"); coils.className = "coils";
        grp.co.forEach(p => {
          const b = document.createElement("button");
          b.className = "btn" + (/scram|trip|block|ads|manual_si/.test(p.key) ? " danger" : "");
          b.id = "co-" + p.key; b.textContent = p.label;
          b.onclick = () => cmd("coil", p.key, b.classList.contains("on") ? 0 : 1);
          coils.appendChild(b);
        });
        g.appendChild(coils);
      }
      grp.hr.forEach(p => {
        const w = document.createElement("div"); w.className = "slider";
        w.innerHTML = `<label>${p.label}</label>`;
        const r = document.createElement("input");
        r.type = "range"; r.min = p.lo; r.max = p.hi; r.step = (p.hi - p.lo) > 200 ? 10 : 1; r.id = "hr-" + p.key;
        const n = document.createElement("span"); n.className = "num"; n.id = "hrv-" + p.key;
        r.oninput = () => n.textContent = fmt(+r.value, p.unit);
        r.onchange = () => cmd("hr", p.key, +r.value);
        w.appendChild(r); w.appendChild(n); g.appendChild(w);
      });
      box.appendChild(g);
    }
  }
}

function buildTimescale() {
  const box = document.getElementById("timescale-btns");
  TIMESCALES.forEach(ts => {
    const b = document.createElement("button"); b.className = "btn"; b.id = "ts-" + ts;
    b.textContent = ts + "×"; b.onclick = () => cmd("timescale", null, ts); box.appendChild(b);
  });
}

/* -------- comandos -------- */
async function cmd(kind, key, value) {
  await fetch("/api/command", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, key, value }) });
}
function setLoca(pct) {
  document.getElementById("loca-range").value = pct;
  document.getElementById("loca-val").textContent = pct + " %";
  cmd("loca", null, pct / 100);
}
window.setLoca = setLoca;

/* -------- stream -------- */
let lastState = null;
const hist = { p: [], g: [], t: [], x: [] }, HMAX = 240;
function connect() { new EventSource("/api/stream").onmessage = e => update(JSON.parse(e.data)); }
const setCls = (id, cls, on) => { const el = document.getElementById(id); if (el) el.classList.toggle(cls, on); };
const setFlow = (id, on) => setCls(id, "flow", on);

function setLevel(id, pct, yFull, yEmpty) {
  const el = document.getElementById(id); if (!el) return;
  const top = yEmpty - (Math.max(0, Math.min(100, pct)) / 100) * (yEmpty - yFull);
  el.setAttribute("y", top.toFixed(1)); el.setAttribute("height", (yEmpty - top).toFixed(1));
}
function setRods(rodPos) {
  const y2 = 372 + ((100 - rodPos) / 100) * 74;   // núcleo 372..446
  ["rod0", "rod1", "rod2"].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.setAttribute("y2", y2.toFixed(0)); el.classList.toggle("deep", rodPos < 30); }
  });
}

function update(st) {
  lastState = st;
  const ir = st.ir, di = st.di, co = st.co, hr = st.hr;

  document.getElementById("s-power").textContent = fmt(ir.reactor_power_pct, "%");
  document.getElementById("s-mwe").textContent = fmt(ir.gen_power_mwe, "MWe");
  document.getElementById("s-tavg").textContent = fmt(ir.coolant_tavg_c, "°C");
  document.getElementById("s-przr").textContent = fmt(ir.przr_pressure_bar, "bar");
  document.getElementById("s-clock").textContent = st.rh < 1 ? `${(st.rh * 60).toFixed(0)} min` : `${st.rh.toFixed(1)} h`;
  document.getElementById("s-speed").textContent = st.ts + "×";

  const anyAlarm = META.di.some(p => p.key.startsWith("alm_") && di[p.key]);
  const badge = document.getElementById("s-status");
  if (di.reactor_tripped) { badge.textContent = "SCRAM / TRIP"; badge.className = "status-badge trip"; }
  else if (anyAlarm) { badge.textContent = "ALARME"; badge.className = "status-badge alarm"; }
  else { badge.textContent = "NORMAL"; badge.className = "status-badge"; }

  // chips e leituras
  document.querySelectorAll("[data-k]").forEach(el => {
    const k = el.getAttribute("data-k"); if (k in ir) el.textContent = fmt(ir[k], IR[k].unit);
  });
  document.querySelectorAll("[data-r]").forEach(el => {
    const k = el.getAttribute("data-r");
    el.textContent = IR[k].unit === "pcm" ? fmtSigned(ir[k]) : fmt(ir[k], IR[k].unit);
  });
  document.getElementById("r-xei").textContent = `${ir.xenon_pct.toFixed(0)}% / ${ir.iodine_pct.toFixed(0)}%`;

  // níveis de água + barras
  FILLS.forEach(([id, key, yf, ye]) => setLevel(id, ir[key], yf, ye));
  setRods(ir.rod_position_pct);

  // estados de componentes
  setCls("core", "trip", di.reactor_tripped);
  setCls("turbine", "trip", di.turbine_tripped);
  setCls("gen", "off", di.turbine_tripped);
  [1, 2, 3, 4].forEach(i => { setCls("rcp" + i, "on", di["rcp" + i + "_running"]); setCls("rcp" + i, "off", !di["rcp" + i + "_running"]); });
  setCls("cmt", "act", di.cmt_injecting); setCls("prhr", "act", di.prhr_actuated);
  setCls("accum", "act", di.accum_injecting); setCls("ads", "act", di.ads_actuated);

  // fluxos
  const flow = ir.rcp_flow_pct > 5;
  ["hot1", "hot2", "cold1", "cold2"].forEach(p => setFlow(p, flow));
  setFlow("steam1", ir.sg1_steam_flow_kgs > 10); setFlow("steam2", ir.sg2_steam_flow_kgs > 10);
  setFlow("feed", di.feedwater_running);

  META.di.forEach(p => { const r = document.getElementById("di-" + p.key); if (r) r.classList.toggle("on", di[p.key]); });
  META.co.forEach(p => { const b = document.getElementById("co-" + p.key); if (b) b.classList.toggle("on", co[p.key]); });
  META.hr.forEach(p => {
    const r = document.getElementById("hr-" + p.key), n = document.getElementById("hrv-" + p.key);
    if (r && document.activeElement !== r) { r.value = hr[p.key]; n.textContent = fmt(hr[p.key], p.unit); }
  });
  TIMESCALES.forEach(ts => setCls("ts-" + ts, "on", st.ts === ts));

  pushHist(ir);
}

/* -------- sparkline -------- */
function pushHist(ir) {
  hist.p.push(ir.reactor_power_pct); hist.g.push(ir.gen_power_mwe / 12);
  hist.t.push(ir.coolant_tavg_c); hist.x.push(ir.xenon_pct);
  for (const k of ["p", "g", "t", "x"]) if (hist[k].length > HMAX) hist[k].shift();
  drawSpark();
}
function drawSpark() {
  const c = document.getElementById("spark"); const w = c.clientWidth, h = c.clientHeight;
  if (c.width !== w) c.width = w; if (c.height !== h) c.height = h;
  const ctx = c.getContext("2d"); ctx.clearRect(0, 0, w, h);
  for (const [key, color, lo, hi] of [["p", "#3fb950", 0, 130], ["g", "#58a6ff", 0, 130], ["t", "#f0883e", 150, 340], ["x", "#bc8cff", 0, 300]]) {
    const d = hist[key]; if (d.length < 2) continue;
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath();
    d.forEach((v, i) => {
      const x = (i / (HMAX - 1)) * w;
      const y = h - ((Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * (h - 6) - 3;
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.stroke();
  }
}

init();
