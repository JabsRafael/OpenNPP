"use strict";

const SYS_LABELS = {
  nucleo: "Reator", primario: "Primário", gv1: "Gerador Vapor 1",
  gv2: "Gerador Vapor 2", turbina: "Turbina", pxs: "Segurança (PXS)",
  contencao: "Contenção", geral: "Geral",
};
let META = null, IR = {}, DI = {}, CO = {}, HR = {};

const fmt = (v, unit) => {
  if (unit === "rpm" || unit === "ppm" || unit === "") return `${Math.round(v)}${unit ? " " + unit : ""}`;
  return `${v.toFixed(1)} ${unit}`;
};

// ---------------------------------------------------------------- inicializa
async function init() {
  META = await (await fetch("/api/meta")).json();
  META.ir.forEach(p => IR[p.key] = p);
  META.di.forEach(p => DI[p.key] = p);
  META.co.forEach(p => CO[p.key] = p);
  META.hr.forEach(p => HR[p.key] = p);
  buildAlarms();
  buildControls();
  buildReadings();
  connect();
}

// ---------------------------------------------------------------- alarmes
const TRIP_KEYS = new Set(["reactor_tripped", "turbine_tripped", "safety_blocked",
  "alm_hi_cont_rad", "alm_hi_cont_press"]);
function buildAlarms() {
  const box = document.getElementById("alarms");
  META.di.forEach(p => {
    const row = document.createElement("div");
    row.className = "alarm-row" + (TRIP_KEYS.has(p.key) ? " trip" : "");
    row.id = "di-" + p.key;
    row.innerHTML = `<span class="dot"></span><span>${p.label}</span>`;
    box.appendChild(row);
  });
}

// ---------------------------------------------------------------- controles
function buildControls() {
  const box = document.getElementById("controls");
  const bySys = {};
  META.co.forEach(p => (bySys[p.system] = bySys[p.system] || { co: [], hr: [] }).co.push(p));
  META.hr.forEach(p => (bySys[p.system] = bySys[p.system] || { co: [], hr: [] }).hr.push(p));

  for (const sys of Object.keys(bySys)) {
    const g = document.createElement("div");
    g.className = "ctl-group";
    g.innerHTML = `<h4>${SYS_LABELS[sys] || sys}</h4>`;
    const coils = document.createElement("div");
    coils.className = "coils";
    bySys[sys].co.forEach(p => {
      const b = document.createElement("button");
      const danger = /scram|trip|block|ads|si/.test(p.key);
      b.className = "btn" + (danger ? " danger" : "");
      b.id = "co-" + p.key;
      b.textContent = p.label;
      b.onclick = () => cmd("coil", p.key, b.classList.contains("on") ? 0 : 1);
      coils.appendChild(b);
    });
    if (bySys[sys].co.length) g.appendChild(coils);
    bySys[sys].hr.forEach(p => {
      const wrap = document.createElement("div");
      wrap.className = "slider";
      wrap.innerHTML = `<label>${p.label}</label>`;
      const range = document.createElement("input");
      range.type = "range"; range.min = p.lo; range.max = p.hi;
      range.step = (p.hi - p.lo) > 200 ? 10 : 1; range.id = "hr-" + p.key;
      const num = document.createElement("span");
      num.className = "num"; num.id = "hrv-" + p.key;
      range.oninput = () => { num.textContent = fmt(+range.value, p.unit); };
      range.onchange = () => cmd("hr", p.key, +range.value);
      wrap.appendChild(range); wrap.appendChild(num);
      g.appendChild(wrap);
    });
    box.appendChild(g);
  }
}

// ---------------------------------------------------------------- leituras
let activeTab = "nucleo";
function buildReadings() {
  const tabs = document.getElementById("tabs");
  const systems = [...new Set(META.ir.map(p => p.system))];
  systems.forEach(sys => {
    const t = document.createElement("div");
    t.className = "tab" + (sys === activeTab ? " active" : "");
    t.textContent = SYS_LABELS[sys] || sys;
    t.onclick = () => { activeTab = sys; document.querySelectorAll(".tab").forEach(x => x.classList.remove("active")); t.classList.add("active"); renderReadings(lastState); };
    tabs.appendChild(t);
  });
}
function renderReadings(st) {
  if (!st) return;
  const box = document.getElementById("readings");
  box.innerHTML = "";
  META.ir.filter(p => p.system === activeTab).forEach(p => {
    box.insertAdjacentHTML("beforeend",
      `<div class="rk">${p.label}</div><div class="rv">${fmt(st.ir[p.key], p.unit)}</div>`);
  });
}

// ---------------------------------------------------------------- comando
async function cmd(kind, key, value) {
  await fetch("/api/command", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, key, value }),
  });
}

// ---------------------------------------------------------------- stream
let lastState = null;
const hist = { p: [], g: [], t: [] }, HMAX = 240;
function connect() {
  const es = new EventSource("/api/stream");
  es.onmessage = e => update(JSON.parse(e.data));
  es.onerror = () => { /* EventSource reconecta sozinho */ };
}

function setNode(id, cls, on) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle(cls, on);
}
function setFlow(id, on) { const el = document.getElementById(id); if (el) el.classList.toggle("flow", on); }

function update(st) {
  lastState = st;
  const ir = st.ir, di = st.di, co = st.co, hr = st.hr;

  // header
  document.getElementById("s-power").textContent = fmt(ir.reactor_power_pct, "%");
  document.getElementById("s-mwe").textContent = fmt(ir.gen_power_mwe, "MWe");
  document.getElementById("s-tavg").textContent = fmt(ir.coolant_tavg_c, "°C");
  document.getElementById("s-przr").textContent = fmt(ir.przr_pressure_bar, "bar");
  document.getElementById("s-time").textContent = st.t + " s";

  const anyAlarm = META.di.some(p => p.key.startsWith("alm_") && di[p.key]);
  const badge = document.getElementById("s-status");
  if (di.reactor_tripped) { badge.textContent = "SCRAM / TRIP"; badge.className = "status-badge trip"; }
  else if (anyAlarm) { badge.textContent = "ALARME"; badge.className = "status-badge alarm"; }
  else { badge.textContent = "NORMAL"; badge.className = "status-badge"; }

  // mímico: leituras
  document.querySelectorAll("[data-k]").forEach(el => {
    const k = el.getAttribute("data-k");
    if (k in ir) el.textContent = fmt(ir[k], IR[k].unit);
  });
  // mímico: estados de componentes
  setNode("core", "trip", di.reactor_tripped);
  setNode("turbine", "off", di.turbine_tripped);
  setNode("turbine", "on", !di.turbine_tripped);
  setNode("gen", "on", !di.turbine_tripped);
  setNode("gen", "off", di.turbine_tripped);
  [1, 2, 3, 4].forEach(i => { setNode("rcp" + i, "on", di["rcp" + i + "_running"]); setNode("rcp" + i, "off", !di["rcp" + i + "_running"]); });
  setNode("cmt", "act", di.cmt_injecting);
  setNode("prhr", "act", di.prhr_actuated);
  setNode("accum", "act", di.accum_injecting);
  setNode("ads", "act", di.ads_actuated);
  // fluxos
  const flowing = ir.rcp_flow_pct > 5;
  ["hot1", "hot2", "cold1", "cold2"].forEach(p => setFlow(p, flowing));
  setFlow("steam1", ir.sg1_steam_flow_kgs > 10);
  setFlow("steam2", ir.sg2_steam_flow_kgs > 10);
  setFlow("feed", di.feedwater_running);

  // alarmes
  META.di.forEach(p => {
    const row = document.getElementById("di-" + p.key);
    if (row) row.classList.toggle("on", di[p.key]);
  });

  // controles (reflete estado; nao mexe em slider em foco)
  META.co.forEach(p => { const b = document.getElementById("co-" + p.key); if (b) b.classList.toggle("on", co[p.key]); });
  META.hr.forEach(p => {
    const r = document.getElementById("hr-" + p.key), n = document.getElementById("hrv-" + p.key);
    if (r && document.activeElement !== r) { r.value = hr[p.key]; n.textContent = fmt(hr[p.key], p.unit); }
  });

  renderReadings(st);
  pushHist(ir);
}

// ---------------------------------------------------------------- sparkline
function pushHist(ir) {
  hist.p.push(ir.reactor_power_pct);
  hist.g.push(ir.gen_power_mwe / 12);
  hist.t.push(ir.coolant_tavg_c);
  for (const k of ["p", "g", "t"]) if (hist[k].length > HMAX) hist[k].shift();
  drawSpark();
}
function drawSpark() {
  const c = document.getElementById("spark");
  const w = c.clientWidth, h = c.clientHeight;
  if (c.width !== w) c.width = w; if (c.height !== h) c.height = h;
  const ctx = c.getContext("2d");
  ctx.clearRect(0, 0, w, h);
  const series = [["p", "#3fb950", 0, 120], ["g", "#58a6ff", 0, 120], ["t", "#f0883e", 150, 340]];
  for (const [key, color, lo, hi] of series) {
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
