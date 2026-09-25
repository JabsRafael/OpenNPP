"use strict";

const SYS_LABELS = {
  nucleo: "Reator / núcleo", primario: "Primário (RCS)", pxs: "Salvaguardas (PXS)",
  gv1: "Gerador de Vapor 1", gv2: "Gerador de Vapor 2", turbina: "Turbina / geração",
  geral: "Geral",
};
const PRIMARY_SYS = ["nucleo", "primario", "pxs"];
const SECONDARY_SYS = ["gv1", "gv2", "turbina"];
const TIMESCALES = [1, 10, 60, 300, 720, 3600];

let META = null, IR = {}, DI = {}, HR = {};

const fmt = (v, u) => (u === "rpm" || u === "ppm" || u === "" ? `${Math.round(v)}${u ? " " + u : ""}` : `${v.toFixed(1)} ${u}`);
const fmtSigned = (v) => `${v >= 0 ? "+" : ""}${Math.round(v)} pcm`;

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
  buildAlarms();
  buildControls();
  buildTimescale();
  document.getElementById("loca-range").oninput = e => {
    document.getElementById("loca-val").textContent = e.target.value + " %";
  };
  document.getElementById("loca-range").onchange = e => setLoca(+e.target.value);
  connect();
}

/* -------- alarmes -------- */
const TRIP_KEYS = new Set(["reactor_tripped", "turbine_tripped", "safety_blocked", "alm_hi_cont_rad", "alm_hi_cont_press"]);
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

/* -------- controles (primário / secundário) -------- */
function buildControls() {
  const panels = { primary: {}, secondary: {} };
  const add = (pan, sys, kind, p) => {
    (panels[pan][sys] = panels[pan][sys] || { co: [], hr: [] })[kind].push(p);
  };
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
          b.className = "btn" + (/scram|trip|block|ads|_si\b|manual_si/.test(p.key) ? " danger" : "");
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
    const b = document.createElement("button");
    b.className = "btn"; b.id = "ts-" + ts; b.textContent = ts + "×";
    b.onclick = () => cmd("timescale", null, ts);
    box.appendChild(b);
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
function connect() {
  const es = new EventSource("/api/stream");
  es.onmessage = e => update(JSON.parse(e.data));
}
const setCls = (id, cls, on) => { const el = document.getElementById(id); if (el) el.classList.toggle(cls, on); };
const setFlow = (id, on) => setCls(id, "flow", on);

function setRods(rodPos) {
  const y2 = 345 + ((100 - rodPos) / 100) * 70;
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

  // mímico: leituras
  document.querySelectorAll("[data-k]").forEach(el => {
    const k = el.getAttribute("data-k"); if (k in ir) el.textContent = fmt(ir[k], IR[k].unit);
  });
  // núcleo & reatividade
  document.querySelectorAll("[data-r]").forEach(el => {
    const k = el.getAttribute("data-r");
    el.textContent = IR[k].unit === "pcm" ? fmtSigned(ir[k]) : fmt(ir[k], IR[k].unit);
  });
  document.getElementById("r-xei").textContent = `${ir.xenon_pct.toFixed(0)}% / ${ir.iodine_pct.toFixed(0)}%`;

  // estados de componentes
  setCls("core", "trip", di.reactor_tripped);
  setCls("turbine", "trip", di.turbine_tripped);
  setCls("gen", "off", di.turbine_tripped);
  [1, 2, 3, 4].forEach(i => { setCls("rcp" + i, "on", di["rcp" + i + "_running"]); setCls("rcp" + i, "off", !di["rcp" + i + "_running"]); });
  setCls("cmt", "act", di.cmt_injecting);
  setCls("prhr", "act", di.prhr_actuated);
  setCls("accum", "act", di.accum_injecting);
  setCls("ads", "act", di.ads_actuated);
  setRods(ir.rod_position_pct);

  // fluxos
  const flow = ir.rcp_flow_pct > 5;
  ["hot1", "hot2", "cold1", "cold2"].forEach(p => setFlow(p, flow));
  setFlow("steam1", ir.sg1_steam_flow_kgs > 10);
  setFlow("steam2", ir.sg2_steam_flow_kgs > 10);
  setFlow("feed", di.feedwater_running);

  // alarmes
  META.di.forEach(p => { const r = document.getElementById("di-" + p.key); if (r) r.classList.toggle("on", di[p.key]); });

  // reflete controles
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
  const series = [["p", "#3fb950", 0, 130], ["g", "#58a6ff", 0, 130], ["t", "#f0883e", 150, 340], ["x", "#bc8cff", 0, 300]];
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
