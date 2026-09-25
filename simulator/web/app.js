"use strict";

const SYS_LABELS = {
  nucleo: "Reator / núcleo", primario: "Primário (RCS)", pxs: "Salvaguardas (PXS)",
  gv1: "Gerador de Vapor 1", gv2: "Gerador de Vapor 2", turbina: "Turbina / geração", geral: "Geral",
};
const PRIMARY_SYS = ["nucleo", "primario", "pxs"];
const SECONDARY_SYS = ["gv1", "gv2", "turbina"];
const TIMESCALES = [1, 10, 60, 300, 720, 3600];
const SPEEDS = [1, 2, 5, 10];
const LOCA_SIZES = [
  { v: 0, label: "Sem LOCA" }, { v: 1, label: "Pequeno (1%)", d: 1 },
  { v: 10, label: "Médio (10%)", d: 1 }, { v: 100, label: "Grande (100%)", d: 1 },
];
const SCENARIOS = [
  { k: "at_power", label: "Operando 100%" }, { k: "hot_standby", label: "Parada quente" },
  { k: "cold_shutdown", label: "Desligado a frio" }, { k: "first_startup", label: "1ª partida pós-manut." },
];
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
  { x: 196, y: 352, k: "coolant_tavg_c", sm: 1 }, { x: 322, y: 300, k: "coolant_thot_c", sm: 1 },
  { x: 120, y: 92, k: "przr_pressure_bar" }, { x: 120, y: 124, k: "przr_level_pct" },
  { x: 578, y: 164, k: "sg1_level_pct" }, { x: 578, y: 196, k: "sg1_pressure_bar" }, { x: 578, y: 228, k: "sg1_steam_flow_kgs" },
  { x: 578, y: 404, k: "sg2_level_pct" }, { x: 578, y: 436, k: "sg2_pressure_bar" }, { x: 578, y: 468, k: "sg2_steam_flow_kgs" },
  { x: 866, y: 208, k: "gen_power_mwe", big: 1 }, { x: 866, y: 248, k: "turbine_rpm" },
  { x: 28, y: 164, k: "cmt1_level_pct", sm: 1 }, { x: 28, y: 256, k: "accum_press_bar", sm: 1 }, { x: 28, y: 352, k: "prhr_flow_pct", sm: 1 },
  { x: 620, y: 72, k: "containment_press_bar", sm: 1 }, { x: 684, y: 72, k: "containment_rad_msvh", sm: 1 },
];
// ---------------------------------------------------------------- painel
// Categoria (cor da lampada, padrao de painel de reator):
//   trip = vermelho (reator/turbina DESARMADOS) · warn = ambar (alarme,
//   salvaguarda atuando, bypass anormal) · info = branco (estado normal:
//   equipamento ligado, permissivo, bloqueio de trip de partida)
// actual = DI que mostra o estado REAL do equipamento (o botao acende pelo
// estado real; se comandado mas nao efetivo, fica tracejado = "comandado").
// pulse = botoeira momentanea (o simulador consome o pulso).
const COIL_INFO = {
  cmd_manual_scram: { cat: "trip", actual: "reactor_tripped", pulse: 1, label: "SCRAM",
    desc: "Botoeira: desarma o reator (barras caem em ~2 s). Acende enquanto o reator estiver desarmado; só apaga com o Rearmar." },
  cmd_block_sr_trip: { cat: "info", actual: "sr_trip_blocked", pulse: 1,
    label: "Trip faixa-fonte", labelOn: "Trip faixa-fonte: BLOQUEADO", labelOff: "Trip faixa-fonte: EM SERVIÇO",
    desc: "Trip de 1e5 cps, usado só na partida. Na subida de potência, clique para BLOQUEAR quando P-6 acender (antes de 1e5 cps). Acima de P-10 fica bloqueado sozinho (normal em potência). Clicar de novo com ele bloqueado o coloca de volta em serviço — só possível abaixo de P-10." },
  cmd_block_lowpower_trips: { cat: "info", actual: "lowpower_trips_blocked", pulse: 1,
    label: "Trips IR/PR-baixo", labelOn: "Trips IR/PR-baixo: BLOQUEADOS", labelOff: "Trips IR/PR-baixo: EM SERVIÇO",
    desc: "Trips de 25% (faixa intermediária e potência-baixo), usados só na partida. Clique para BLOQUEAR quando P-10 acender (> 10%, antes de 25%). Em potência ficam bloqueados (normal). Voltam sozinhos quando a potência cai abaixo de 10%." },
  cmd_rcp1_start: { cat: "info", actual: "rcp1_running", label: "RCP1", desc: "Liga/desliga a bomba de refrigerante 1. Aceso = girando com vazão." },
  cmd_rcp2_start: { cat: "info", actual: "rcp2_running", label: "RCP2", desc: "Liga/desliga a bomba de refrigerante 2." },
  cmd_rcp3_start: { cat: "info", actual: "rcp3_running", label: "RCP3", desc: "Liga/desliga a bomba de refrigerante 3." },
  cmd_rcp4_start: { cat: "info", actual: "rcp4_running", label: "RCP4", desc: "Liga/desliga a bomba de refrigerante 4." },
  cmd_przr_heater: { cat: "info", actual: "przr_heater_on", label: "Aquecedores",
    desc: "Aquecedores do PZR (sobem a pressão, ~0,3 bar/s). Só em MANUAL; cortam com nível < 17%. Aceso = energizados." },
  cmd_przr_spray: { cat: "info", actual: "przr_spray_on", label: "Spray",
    desc: "Spray do PZR (baixa a pressão, ~1,5 bar/s). Só em MANUAL. Aceso = aberto." },
  cmd_boron_charge: { cat: "info", label: "Borar",
    desc: "CVS injeta ácido bórico (4000 ppm): boro sobe devagar (exponencial). Reatividade negativa." },
  cmd_boron_dilute: { cat: "info", label: "Diluir",
    desc: "CVS injeta água desmineralizada: boro cai devagar (exponencial). Reatividade positiva." },
  cmd_manual_si: { cat: "warn", actual: "cmt_injecting", label: "Injeção seg. (SI)",
    desc: "Gera sinal S: CMT injeta água borada, PRHR atua e o reator desarma. Aceso = CMT injetando." },
  cmd_manual_prhr: { cat: "warn", actual: "prhr_actuated", label: "PRHR",
    desc: "Abre o trocador passivo de calor residual (primário → IRWST). Aceso = atuado." },
  cmd_manual_ads: { cat: "warn", actual: "ads_actuated", label: "ADS",
    desc: "Despressurização automática em 4 estágios (ventila vapor do RCS). Irreversível na prática." },
  cmd_block_safety: { cat: "warn", actual: "safety_blocked", label: "Bloquear salvaguardas",
    desc: "BYPASS de manutenção: inibe CMT/ADS/PRHR/acumuladores/IRWST. Nunca deveria estar ativo em operação (alvo de ataque)." },
  cmd_feed_pump_start: { cat: "info", actual: "main_feed_flowing", label: "Bomba alim. principal",
    desc: "Liga a bomba de alimentação principal. Aceso = entregando água (precisa das válvulas abertas e sem isolamento P-4/P-14)." },
  cmd_turbine_trip: { cat: "trip", actual: "turbine_tripped", pulse: 1, label: "Desarme turbina",
    desc: "Botoeira: desarma a turbina (válvulas fecham). Acende enquanto desarmada; rearma junto com o Rearmar reator." },
};
// estacoes AUTO/MANUAL de cada subsistema (coil = 1 -> MANUAL)
const STATIONS = {
  cmd_przr_press_manual: "AUTO: aquecedores/spray seguem o setpoint de pressão. MAN: você liga aquecedores e spray.",
  cmd_cvs_manual: "AUTO: o CVS segura o nível do PZR no programa (25% sem carga → 55% a 100%). MAN: você define a vazão de carga (+) / descarga (−).",
  cmd_steam_dump_manual: "AUTO: despejo ao condensador segura o Tavg no programa após trip/baixa carga. MAN: você define a abertura.",
  cmd_sfw_manual: "AUTO: a alimentação de partida segura o nível dos GVs quando a principal não entrega. MAN: você define a vazão (% de 2×60 kg/s).",
};
// demandas travadas com o modo MESTRE em AUTO (o controle automatico escreve)
const MANUAL_KEYS = ["dmd_rod_pct", "dmd_turbine_valve_pct", "dmd_sg1_feed_valve_pct", "dmd_sg2_feed_valve_pct"];
// passos [fino, grosso] dos botoes -/+
const STEPS = {
  sp_power_pct: [1, 10], dmd_rcp_speed_pct: [1, 10], sp_przr_pressure_bar: [0.5, 5],
  dmd_turbine_valve_pct: [0.5, 5], sp_sg1_level_pct: [1, 5], sp_sg2_level_pct: [1, 5],
  dmd_sg1_feed_valve_pct: [0.5, 5], dmd_sg2_feed_valve_pct: [0.5, 5],
  dmd_cvs_flow_kgs: [1, 5], dmd_steam_dump_pct: [1, 10], dmd_sfw_pct: [1, 10],
};
const HR_INFO = {
  dmd_rod_pct: "Alavanca IN-HOLD-OUT: segure INSERIR/RETIRAR para mover o banco (48 passos/min), solte para parar. ±5 passos = ajuste fino. Travado em AUTO.",
  sp_power_pct: "Setpoint de CARGA da turbina (usado só em AUTO): a turbina vai até ele em rampa de 5%/min e as barras seguem o Tavg.",
  dmd_rcp_speed_pct: "Rotação comum das RCPs. Abaixo de 87% de vazão (acima de P-7) o reator desarma.",
  sp_przr_pressure_bar: "Setpoint da pressão do PZR (estação de pressão em AUTO).",
  dmd_cvs_flow_kgs: "Vazão líquida do CVS: + carrega (sobe o nível do PZR), − descarrega. Capacidade ±20 kg/s. Só em MAN.",
  sp_sg1_level_pct: "Setpoint de nível do GV1 (controle de alimentação em AUTO).",
  sp_sg2_level_pct: "Setpoint de nível do GV2 (controle de alimentação em AUTO).",
  dmd_sg1_feed_valve_pct: "Abertura da válvula de alimentação principal do GV1 (MANUAL).",
  dmd_sg2_feed_valve_pct: "Abertura da válvula de alimentação principal do GV2 (MANUAL).",
  dmd_sfw_pct: "Vazão da alimentação de partida (% de 60 kg/s por GV). Só em MAN.",
  dmd_turbine_valve_pct: "Abertura das válvulas de admissão da turbina (MANUAL). Com o reator em baixa potência, abrir demais super-resfria o primário.",
  dmd_steam_dump_pct: "Abertura do despejo de vapor ao condensador (40% da vazão nominal a 100%). Só em MAN.",
};
// layout dos paineis: grupos por subsistema
const LAYOUT = {
  "ctl-primary": [
    { t: "Reator / núcleo", co: ["cmd_manual_scram", "cmd_block_sr_trip", "cmd_block_lowpower_trips"], hr: ["dmd_rod_pct", "sp_power_pct"] },
    { t: "Bombas do primário (RCP)", co: ["cmd_rcp1_start", "cmd_rcp2_start", "cmd_rcp3_start", "cmd_rcp4_start"], hr: ["dmd_rcp_speed_pct"] },
    { t: "Pressurizador — pressão", st: "cmd_przr_press_manual", co: ["cmd_przr_heater", "cmd_przr_spray"], hr: ["sp_przr_pressure_bar"],
      ro: ir => `Pressão ${ir.przr_pressure_bar.toFixed(1)} bar` },
    { t: "Pressurizador — nível (CVS)", st: "cmd_cvs_manual", hr: ["dmd_cvs_flow_kgs"],
      ro: ir => `Nível ${ir.przr_level_pct.toFixed(1)}% · programa ${ir.przr_level_program_pct.toFixed(1)}% · CVS ${ir.cvs_flow_kgs >= 0 ? "+" : ""}${ir.cvs_flow_kgs.toFixed(1)} kg/s` },
    { t: "Química — boro (CVS)", co: ["cmd_boron_charge", "cmd_boron_dilute"], ro: ir => `Boro ${Math.round(ir.boron_ppm)} ppm` },
    { t: "Salvaguardas (PXS)", co: ["cmd_manual_si", "cmd_manual_prhr", "cmd_manual_ads", "cmd_block_safety"] },
  ],
  "ctl-secondary": [
    { t: "Alimentação principal", co: ["cmd_feed_pump_start"], hr: ["sp_sg1_level_pct", "dmd_sg1_feed_valve_pct", "sp_sg2_level_pct", "dmd_sg2_feed_valve_pct"],
      ro: ir => `GV1 ${ir.sg1_level_pct.toFixed(1)}% · GV2 ${ir.sg2_level_pct.toFixed(1)}%` },
    { t: "Alimentação de partida (SFW)", st: "cmd_sfw_manual", hr: ["dmd_sfw_pct"], ro: ir => `SFW ${Math.round(ir.sfw_flow_kgs)} kg/s` },
    { t: "Turbina / gerador", co: ["cmd_turbine_trip"], hr: ["dmd_turbine_valve_pct"],
      ro: ir => `${Math.round(ir.gen_power_mwe)} MWe · ${Math.round(ir.turbine_rpm)} rpm` },
    { t: "Despejo de vapor ao condensador", st: "cmd_steam_dump_manual", hr: ["dmd_steam_dump_pct"],
      ro: ir => `Abertura ${ir.steam_dump_pct.toFixed(1)}% · Tavg ${ir.coolant_tavg_c.toFixed(1)} °C` },
  ],
};
// em qual estacao cada controle fica travado quando ela esta em AUTO
const STATION_OF = {
  cmd_przr_heater: "cmd_przr_press_manual", cmd_przr_spray: "cmd_przr_press_manual",
  dmd_cvs_flow_kgs: "cmd_cvs_manual", dmd_sfw_pct: "cmd_sfw_manual", dmd_steam_dump_pct: "cmd_steam_dump_manual",
};
const ROD_STEPS = 228;
const fmtPeriod = v => Math.abs(v) >= 999 ? "estável" : `${v > 0 ? "+" : ""}${Math.round(v)} s`;
const fmtExp = (v, u) => `${Math.pow(10, v).toExponential(1).replace("e+", "e")} ${u}`;
const fmtNum = v => (Math.abs(v) >= 100 || Number.isInteger(v)) ? String(Math.round(v * 10) / 10) : v.toFixed(1);
const fmtT = t => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
let LAST_EV = 0;
function updateEvents(evs) {
  if (!evs) return;
  evs.forEach(e => {
    if (e.id > LAST_EV) {
      LAST_EV = e.id;
      const tag = e.lvl === "trip" ? "🔴" : e.lvl === "warn" ? "🟠" : "⚪";
      console.log(`${tag} [OpenNPP ${fmtT(e.t)}] ${e.msg}`);
    }
  });
  document.getElementById("eventlog").innerHTML = evs.slice().reverse()
    .map(e => `<div class="ev ${e.lvl}"><span class="t">${fmtT(e.t)}</span>${e.msg}</div>`).join("");
}
// vasos com nível de água animado: [id, chave, yCheio, yVazio]
const FILLS = [
  ["rpvFill", "primary_inventory_pct", 305, 470], ["pzrFill", "przr_level_pct", 126, 213],
  ["sg1Fill", "sg1_level_pct", 158, 280], ["sg2Fill", "sg2_level_pct", 400, 522],
];

let META = null, IR = {}, DI = {}, HR = {};
const fmt = (v, u) => (u === "rpm" || u === "ppm" || u === "" ? `${Math.round(v)}${u ? " " + u : ""}` : `${v.toFixed(1)} ${u}`);
const fmtSigned = v => `${v >= 0 ? "+" : ""}${Math.round(v)} pcm`;

async function init() {
  META = await (await fetch("/api/meta")).json();
  META.ir.forEach(p => IR[p.key] = p);
  META.di.forEach(p => DI[p.key] = p);
  META.hr.forEach(p => HR[p.key] = p);
  buildChips();
  buildAlarms();
  buildControls();
  buildTimescale();
  buildSpeed();
  buildLoca();
  buildScenarios();
  window.addEventListener("blur", () => rodLever("hold"));   // solta a alavanca
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
// anunciador: vermelho = trip/bloqueio de trip · ambar = alarme/salvaguarda · branco = status
const DI_TRIP = new Set(["reactor_tripped", "turbine_tripped", "alm_hi_cont_rad", "alm_hi_cont_press"]);
const DI_WARN = new Set(["alm_hi_flux", "alm_hi_przr_press", "alm_lo_przr_press", "alm_sg1_lo_level", "alm_sg2_lo_level",
  "alm_hi_coolant_temp", "alm_lo_flow", "przr_relief_open", "esfas_actuated", "cmt_injecting", "prhr_actuated",
  "accum_injecting", "ads_actuated", "sg1_relief_open", "sg2_relief_open", "rod_withdrawal_block", "feedwater_isolated",
  "safety_blocked"]);
const diLevel = k => DI_TRIP.has(k) ? "trip" : DI_WARN.has(k) ? "warn" : "info";
function buildAlarms() {
  const box = document.getElementById("alarms");
  META.di.forEach(p => {
    const row = document.createElement("div");
    row.className = "alarm-row " + diLevel(p.key); row.id = "di-" + p.key;
    row.innerHTML = `<span class="dot"></span><span>${p.label}</span>`; box.appendChild(row);
  });
}

/* -------- controles (somente botoes) -------- */
// botao com repeticao enquanto pressionado (como um botao de painel)
function holdButton(label, cls, title, fn) {
  const b = document.createElement("button");
  b.className = "btn " + cls; b.textContent = label; if (title) b.title = title;
  let t1 = null, t2 = null;
  const stop = () => { clearTimeout(t1); clearInterval(t2); t1 = t2 = null; };
  b.addEventListener("pointerdown", e => {
    if (b.disabled) return;
    e.preventDefault(); fn(); stop();
    t1 = setTimeout(() => { t2 = setInterval(fn, 150); }, 450);
  });
  ["pointerup", "pointerleave", "pointercancel"].forEach(ev => b.addEventListener(ev, stop));
  return b;
}

function stepperRow(p) {
  const [fine, coarse] = STEPS[p.key] || [1, 10];
  const w = document.createElement("div"); w.className = "stepper"; w.id = "st-" + p.key;
  w.title = HR_INFO[p.key] || "";
  const lbl = document.createElement("label"); lbl.textContent = p.label; w.appendChild(lbl);
  const row = document.createElement("div"); row.className = "stepper-row";
  const u = p.unit ? " " + p.unit : "";
  row.appendChild(holdButton("−" + fmtNum(coarse), "step", `−${coarse}${u}`, () => cmd("hr_step", p.key, -coarse)));
  row.appendChild(holdButton("−" + fmtNum(fine), "step", `−${fine}${u}`, () => cmd("hr_step", p.key, -fine)));
  const n = document.createElement("span"); n.className = "num"; n.id = "hrv-" + p.key; n.textContent = "--";
  row.appendChild(n);
  row.appendChild(holdButton("+" + fmtNum(fine), "step", `+${fine}${u}`, () => cmd("hr_step", p.key, fine)));
  row.appendChild(holdButton("+" + fmtNum(coarse), "step", `+${coarse}${u}`, () => cmd("hr_step", p.key, coarse)));
  w.appendChild(row);
  return w;
}

// alavanca IN-HOLD-OUT: enquanto segurada, reenvia o comando (homem-morto no
// servidor); ao soltar, HOLD. A demanda mostrada acompanha a posicao real.
let ROD_MOVING = null, ROD_TIMER = null;
function rodLever(dir) {
  clearInterval(ROD_TIMER); ROD_TIMER = null;
  if (dir === "hold") { if (!ROD_MOVING) return; ROD_MOVING = null; cmd("rod", null, "hold"); return; }
  ROD_MOVING = dir; cmd("rod", null, dir);
  ROD_TIMER = setInterval(() => cmd("rod", null, dir), 250);
}
function rodControl(p) {
  const w = document.createElement("div"); w.className = "stepper rods"; w.id = "st-" + p.key;
  w.title = HR_INFO[p.key];
  w.innerHTML = `<label>Barras de controle (demanda)</label>`;
  const row = document.createElement("div"); row.className = "stepper-row";
  const lever = (label, dir, cls) => {
    const b = document.createElement("button"); b.className = "btn lever " + cls; b.textContent = label; b.id = "lever-" + dir;
    b.addEventListener("pointerdown", e => { if (b.disabled) return; e.preventDefault(); rodLever(dir); });
    ["pointerup", "pointerleave", "pointercancel"].forEach(ev => b.addEventListener(ev, () => rodLever("hold")));
    return b;
  };
  const stepPct = 5 * 100 / ROD_STEPS;
  row.appendChild(lever("▼ INSERIR", "in", ""));
  row.appendChild(holdButton("−5p", "step", "Inserir 5 passos", () => cmd("hr_step", p.key, -stepPct)));
  const n = document.createElement("span"); n.className = "num wide"; n.id = "hrv-" + p.key; n.textContent = "--";
  row.appendChild(n);
  row.appendChild(holdButton("+5p", "step", "Retirar 5 passos", () => cmd("hr_step", p.key, stepPct)));
  row.appendChild(lever("▲ RETIRAR", "out", ""));
  w.appendChild(row);
  return w;
}

function lampButton(key) {
  const info = COIL_INFO[key] || { cat: "info", label: key };
  const b = document.createElement("button");
  b.className = `btn lamp cat-${info.cat}`; b.id = "co-" + key; b.textContent = info.label;
  b.title = (info.pulse ? "[botoeira momentânea] " : "[liga/desliga] ") + (info.desc || "");
  b.onclick = () => { if (!b.disabled) cmd("coil", key, info.pulse ? 1 : (LAST_CO[key] ? 0 : 1)); };
  return b;
}
function stationSelector(key) {
  const w = document.createElement("div"); w.className = "station"; w.title = STATIONS[key];
  [["AUTO", 0], ["MAN", 1]].forEach(([label, v]) => {
    const b = document.createElement("button"); b.className = "btn am"; b.id = `am-${key}-${v}`; b.textContent = label;
    b.onclick = () => cmd("coil", key, v); w.appendChild(b);
  });
  return w;
}

let LAST_CO = {};
function buildControls() {
  const HR_BY = {}; META.hr.forEach(p => HR_BY[p.key] = p);
  // seletor do modo MESTRE (dois botoes, como uma chave de painel)
  const mode = document.createElement("div"); mode.className = "ctl-group";
  mode.innerHTML = `<h4 title="MESTRE — MANUAL: você comanda barras, turbina e válvulas de alimentação.&#10;AUTOMÁTICO: turbina em rampa até o setpoint de carga (5%/min), barras no programa de Tavg, nível dos GVs automático. Só retira barras sozinho com a turbina ≥ 15% (C-5).&#10;Todo trip do reator volta para MANUAL.&#10;Pressurizador, CVS, despejo de vapor e SFW têm estações AUTO/MAN próprias.">Modo de operação (mestre) &#9432;</h4>`;
  const mc = document.createElement("div"); mc.className = "coils mode-select";
  [["MANUAL", 0, "mode-man"], ["AUTOMÁTICO", 1, "mode-auto"]].forEach(([label, v, id]) => {
    const b = document.createElement("button"); b.className = "btn mode"; b.id = id; b.textContent = label;
    b.onclick = () => cmd("coil", "cmd_auto_control", v); mc.appendChild(b);
  });
  mode.appendChild(mc);
  document.getElementById("ctl-primary").appendChild(mode);

  for (const [elId, groups] of Object.entries(LAYOUT)) {
    const box = document.getElementById(elId);
    groups.forEach((grp, gi) => {
      const g = document.createElement("div"); g.className = "ctl-group";
      const h = document.createElement("div"); h.className = "grp-head";
      h.innerHTML = `<h4>${grp.t}</h4>`;
      if (grp.st) h.appendChild(stationSelector(grp.st));
      g.appendChild(h);
      if (grp.ro) { const r = document.createElement("div"); r.className = "grp-ro"; r.id = `ro-${elId}-${gi}`; g.appendChild(r); grp._ro = r.id; }
      if (grp.co) {
        const coils = document.createElement("div"); coils.className = "coils";
        grp.co.forEach(k => coils.appendChild(lampButton(k)));
        g.appendChild(coils);
      }
      if (grp.hr) {
        const grid = document.createElement("div"); grid.className = "stepper-grid";
        grp.hr.forEach(k => { const p = HR_BY[k]; if (p) grid.appendChild(k === "dmd_rod_pct" ? rodControl(p) : stepperRow(p)); });
        g.appendChild(grid);
      }
      box.appendChild(g);
    });
  }
}

function buildScenarios() {
  const box = document.getElementById("scenario-btns");
  SCENARIOS.forEach(s => {
    const b = document.createElement("button");
    b.className = "btn"; b.id = "scn-" + s.k; b.textContent = s.label;
    b.onclick = () => { if (confirm(`Recarregar a planta no cenário "${s.label}"? O estado atual será perdido.`)) cmd("scenario", null, s.k); };
    box.appendChild(b);
  });
}

function buildTimescale() {
  const box = document.getElementById("timescale-btns");
  TIMESCALES.forEach(ts => {
    const b = document.createElement("button"); b.className = "btn"; b.id = "ts-" + ts;
    b.textContent = ts + "×"; b.onclick = () => cmd("timescale", null, ts); box.appendChild(b);
  });
}
function buildSpeed() {
  const box = document.getElementById("speed-btns");
  SPEEDS.forEach(v => {
    const b = document.createElement("button"); b.className = "btn"; b.id = "sp-" + v;
    b.textContent = v + "×"; b.onclick = () => cmd("speed", null, v); box.appendChild(b);
  });
}
function buildLoca() {
  const box = document.getElementById("loca-btns");
  LOCA_SIZES.forEach(l => {
    const b = document.createElement("button"); b.className = "btn" + (l.d ? " danger" : ""); b.id = "loca-" + l.v;
    b.textContent = l.label; b.onclick = () => cmd("loca", null, l.v / 100); box.appendChild(b);
  });
}

/* -------- comandos -------- */
async function cmd(kind, key, value) {
  const r = await fetch("/api/command", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, key, value }) });
  return r.json();
}
// Rearme apos SCRAM: o servidor solta o SCRAM manual, pulsa o reset e diz se
// passou — e, se nao, POR QUE (condicoes de trip presentes). Vai para o console.
async function restart() {
  const r = await cmd("reset", null, null);
  const box = document.getElementById("reset-msg");
  if (!r.ok) { console.error("[OpenNPP] Falha no rearme:", r.error); return; }
  if (!r.tripped) {
    console.info("[OpenNPP] Rearme: o reator já está armado (sem trip).");
  } else if (r.reset) {
    console.info("%c[OpenNPP] ✅ Reator REARMADO — nenhuma condição de trip presente.", "color:#3fb950;font-weight:bold");
  } else {
    console.group(`%c[OpenNPP] ⛔ Rearme NEGADO — ${r.reasons.length} condição(ões) de trip presente(s):`, "color:#f85149;font-weight:bold");
    r.reasons.forEach(x => console.warn(`• ${x.label}: ${x.detail}`));
    console.groupEnd();
  }
  box.classList.toggle("flash", true); setTimeout(() => box.classList.remove("flash"), 600);
}
window.restart = restart;

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
  const sp = document.getElementById("s-period");
  sp.textContent = fmtPeriod(ir.reactor_period_s);
  sp.style.color = (ir.reactor_period_s > 0 && ir.reactor_period_s < 30) ? "var(--warn)" : "";
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
    el.textContent = k === "reactor_period_s" ? fmtPeriod(ir[k])
      : k === "mtc_pcm_per_c" ? `${ir[k] >= 0 ? "+" : ""}${ir[k].toFixed(1)} pcm/°C`
      : (IR[k].unit === "pcm" ? fmtSigned(ir[k]) : fmt(ir[k], IR[k].unit));
  });
  document.getElementById("r-xei").textContent = `${ir.xenon_pct.toFixed(0)}% / ${ir.iodine_pct.toFixed(0)}%`;
  document.getElementById("r-sr").textContent = ir.sr_log_cps > 5.99 ? "fora de escala" : fmtExp(ir.sr_log_cps, "cps");
  document.getElementById("r-ir").textContent = fmtExp(ir.ir_log_amps, "A");
  const sur = document.getElementById("r-sur");
  sur.textContent = `${ir.startup_rate_dpm >= 0 ? "+" : ""}${ir.startup_rate_dpm.toFixed(2)} dpm`;
  sur.style.color = ir.startup_rate_dpm > 1 ? "var(--warn)" : "";
  document.getElementById("r-rods").textContent = `${ir.rod_position_pct.toFixed(1)}% · ${Math.round(ir.rod_steps)} passos`;

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
  setFlow("feed", di.feedwater_running); setFlow("feed2", di.feedwater_running);

  META.di.forEach(p => { const r = document.getElementById("di-" + p.key); if (r) r.classList.toggle("on", di[p.key]); });
  LAST_CO = co;
  for (const [key, info] of Object.entries(COIL_INFO)) {
    const b = document.getElementById("co-" + key); if (!b) continue;
    const actual = info.actual ? di[info.actual] : co[key];
    b.classList.toggle("on", !!actual);
    if (info.labelOn) b.textContent = actual ? info.labelOn : info.labelOff;
    b.classList.toggle("cmd", !info.pulse && co[key] && !actual);     // comandado, sem efeito
  }
  // bloqueios: so' operaveis com o permissivo presente
  const dis = (id, off, why) => { const b = document.getElementById(id); if (!b) return;
    b.disabled = off; b.dataset.why = off ? why : ""; };
  // bloqueio de partida: so' mexe quando faz sentido (como a chave do painel)
  const srCps = Math.pow(10, ir.sr_log_cps), pw = ir.reactor_power_pct;
  dis("co-cmd_block_sr_trip",
      di.p10_permissive || !di.p6_permissive || (di.sr_trip_blocked && srCps >= 1e5),
      di.p10_permissive ? "acima de P-10: bloqueado automaticamente (normal em potência)"
        : !di.p6_permissive ? "requer P-6 (IR > 1e-10 A)" : "acima de 1e5 cps o bloqueio é obrigatório");
  dis("co-cmd_block_lowpower_trips",
      !di.p10_permissive || (di.lowpower_trips_blocked && pw >= 25),
      !di.p10_permissive ? "requer P-10 (potência > 10%)" : "acima de 25% o bloqueio é obrigatório (normal em potência)");
  ["co-cmd_block_sr_trip", "co-cmd_block_lowpower_trips"].forEach(id => {
    const b = document.getElementById(id); if (b) b.title = COIL_INFO[id.slice(3)].desc + (b.dataset.why ? `\n\n⊘ ${b.dataset.why}` : "");
  });
  for (const key of Object.keys(STATIONS)) {
    setCls(`am-${key}-0`, "on", !co[key]); setCls(`am-${key}-1`, "on", !!co[key]);
  }
  for (const [ctl, station] of Object.entries(STATION_OF)) {
    const locked = !co[station];
    const el = document.getElementById("st-" + ctl) || document.getElementById("co-" + ctl); if (!el) continue;
    el.classList.toggle("locked", locked);
    (el.tagName === "BUTTON" ? [el] : el.querySelectorAll("button")).forEach(b => b.disabled = locked);
  }
  for (const [elId, groups] of Object.entries(LAYOUT)) groups.forEach(g => {
    if (g._ro) document.getElementById(g._ro).textContent = g.ro(ir, di);
  });
  META.hr.forEach(p => {
    const n = document.getElementById("hrv-" + p.key); if (!n) return;
    n.textContent = p.key === "dmd_rod_pct"
      ? `${ir.rod_position_pct.toFixed(1)}% · ${Math.round(ir.rod_steps)}p${st.rod_motion ? (st.rod_motion === "out" ? " ▲" : " ▼") : ""}`
      : fmt(hr[p.key], p.unit);
  });

  // modo MESTRE AUTO x MANUAL: trava as demandas manuais em AUTO
  const auto = co.cmd_auto_control;
  setCls("mode-auto", "on", auto); setCls("mode-man", "on", !auto);
  const mh = document.getElementById("mode-hint");
  mh.textContent = auto ? `Modo: AUTOMÁTICO — carga em rampa até o setpoint; barras seguem Tref ${st.tref.toFixed(1)} °C`
    : "Modo: MANUAL — você comanda barras, turbina e válvulas de alimentação";
  mh.classList.toggle("mode-auto", auto);
  MANUAL_KEYS.forEach(k => {
    const s = document.getElementById("st-" + k); if (!s) return;
    s.classList.toggle("locked", auto);
    s.querySelectorAll("button").forEach(b => b.disabled = auto);
  });
  if (auto && ROD_MOVING) rodLever("hold");
  // por que nao da' para rearmar (ao vivo)
  const rm = document.getElementById("reset-msg");
  if (!di.reactor_tripped) { rm.className = "reset-msg ok"; rm.textContent = "Reator armado."; }
  else if (st.reset_blockers.length) {
    rm.className = "reset-msg blocked";
    rm.innerHTML = "<b>Rearme bloqueado:</b><br>" + st.reset_blockers.map(x => "• " + x).join("<br>");
  } else { rm.className = "reset-msg ready"; rm.textContent = "Pronto para rearmar — nenhuma condição de trip presente."; }
  TIMESCALES.forEach(ts => setCls("ts-" + ts, "on", st.ts === ts));
  SPEEDS.forEach(v => setCls("sp-" + v, "on", st.speed === v));
  LOCA_SIZES.forEach(l => setCls("loca-" + l.v, "on", Math.abs(st.loca * 100 - l.v) < 0.5));
  SCENARIOS.forEach(s => setCls("scn-" + s.k, "on", st.scenario === s.k));

  updateEvents(st.events);
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
