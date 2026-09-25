# HMI web do simulador — OpenNPP

HMI custom servida pelo próprio simulador (Nível Purdue 2 — supervisão).
Acesse em **http://localhost:5000** com o ambiente de pé (`docker compose up`).

> Ambiente 100% SIMULADO (AP1000-like) para treino de defesa de OT/ICS. Nenhuma
> planta física real é controlada.

Código-fonte: `simulator/web/index.html`, `simulator/web/app.js`,
`simulator/npp/api.py`. A HMI é montada dinamicamente a partir de `/api/meta`
(mesmos pontos do `iomap.py`).

## 1. Layout da tela (estilo sala de controle)

A tela imita uma sala de controle: **situação em cima**, **controles embaixo**.

**Header (barra superior)** — indicadores ao vivo e badge de status:

| Elemento | Origem | Observação |
|---|---|---|
| Potência reator | `ir.reactor_power_pct` | potência térmica (%) |
| Geração MWe | `ir.gen_power_mwe` | geração no gerador |
| Tavg | `ir.coolant_tavg_c` | temperatura média do primário |
| Pressão RCS | `ir.przr_pressure_bar` | pressão do primário/pressurizador |
| Tempo reator | `st.rh` | relógio do reator (min/h, acelerado pela escala de tempo) |
| Escala tempo | `st.ts` | fator de aceleração ativo (1×…3600×) |
| Badge | derivado | `NORMAL` / `ALARME` / `SCRAM / TRIP` |

**Painel de situação (topo)** — três blocos:

- **Mímico P&ID** (`svg.mimic`): diagrama com símbolos de processo:
  - **RPV** (vaso de pressão) com **núcleo** hachurado e **barras de controle**
    (`rod0..rod2`) que **inserem/retiram graficamente** conforme
    `rod_position_pct` (ficam âmbar quando profundamente inseridas), CRDM no topo.
  - **PZR** com serpentina de aquecedor, **4× RCP** (`rcp1..rcp4`, símbolo de
    bomba), **GV1/GV2** (vaso com feixe em U), **Turbina** (símbolo de expansão) +
    **Gerador** (`gen`), **Condensador** e a **Contenção** (pressão/radiação).
  - **PXS** (segurança passiva): **CMT**, **ACUM**, **PRHR**, **ADS** — acendem
    (verde) quando atuando. **Inventário RCS** (`primary_inventory_pct`) exibido.
  - Tubulações (`hot1/2`, `cold1/2`, `steam1/2`, `feed`) animam quando há fluxo.
- **Núcleo & reatividade**: tabela com reatividade total, **reativ. Xenônio**,
  **Xe-135 / I-135**, **reativ. Samário**, veneno queimável, burnup, posição de
  barras e calor de decaimento (`ir.*`).
- **Alarmes & status** e **Tendências** (sparkline: potência %, MWe/12, Tavg,
  **Xe %**; até 240 amostras).

**Painéis de controle (base)** — três colunas:

- **Painel do Primário & Reator**: sistemas `nucleo`, `primario`, `pxs` — setpoint
  de potência, barras, RCPs, pressurizador, boro, salvaguardas, SCRAM.
- **Painel do Secundário & Turbina**: sistemas `gv1`, `gv2`, `turbina` — válvula da
  turbina/desarme, nível e água de alimentação de cada GV.
- **Simulação & Malfunções**: **escala de tempo** (botões 1×…3600×, aceleram os
  venenos/Xenônio) e **LOCA** (slider de área de rompimento + botões
  Pequeno/Médio/Grande). Esses dois usam a API de meta-simulação (não são Modbus).

Cada botão reflete o estado do *coil* (`co.*`); cada slider reflete o *holding
register* (`hr.*`), sem sobrescrever enquanto está em foco.

## 2. Como operar

- **Setpoints (sliders):** arraste; ao soltar (`onchange`) a HMI envia um POST
  `hr`. Ex.: `sp_power_pct`, `sp_przr_pressure_bar`, `sp_sg1_level_pct`. Enquanto
  o slider está em foco, o stream não sobrescreve o valor.
- **Comandos (botões coil):** clique alterna o coil (0↔1). Ex.: `cmd_manual_scram`
  (SCRAM), `cmd_rcp1_start`..`cmd_rcp4_start` (bombas), `cmd_auto_control`
  (auto/manual), `cmd_turbine_trip`, salvaguardas `cmd_manual_si`,
  `cmd_manual_prhr`, `cmd_manual_ads`, `cmd_block_safety`. Botões considerados
  perigosos (`scram|trip|block|ads|si`) ganham estilo `danger`.

**Interpretação de cores:**
- **Verde** = normal / ligado (RCP rodando, turbina/gerador ativos, coil `on`).
- **Âmbar** = alarme ativo.
- **Vermelho** = trip / desarmado (núcleo em SCRAM `di.reactor_tripped`, turbina
  desarmada `di.turbine_tripped`).
- Nós **PXS** ficam **verdes quando atuando** (`cmt_injecting`, `prhr_actuated`,
  `accum_injecting`, `ads_actuated`).
- **Tubulações animam** quando há fluxo: primário quando `rcp_flow_pct > 5`;
  `steam1/2` quando `sg1/sg2_steam_flow_kgs > 10`; `feed` quando
  `di.feedwater_running`.

## 3. API HTTP + SSE (rotas reais)

Servida por `simulator/npp/api.py` na porta 5000.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` (e `/index.html`) | HMI (HTML) |
| GET | `/app.js` | lógica da HMI |
| GET | `/style.css` | estilos |
| GET | `/api/meta` | metadados dos pontos: `{ir, di, co, hr}`, cada item `{key,label,unit,lo,hi,system}` |
| GET | `/api/state` | snapshot único em JSON |
| GET | `/api/stream` | **SSE** (~4 Hz, um evento a cada 0,25 s) com o estado ao vivo |
| POST | `/api/command` | `{"kind":"coil"\|"hr","key":...,"value":...}` ou meta-sim `{"kind":"timescale"\|"loca","value":...}` (sem `key`) |

O snapshot (`/api/state` e cada evento SSE) tem a forma
`{"t":<s>, "rh":<h reator>, "ts":<escala>, "loca":<0..1>, "ir":{...}, "di":{...},
"co":{...}, "hr":{...}}`, com os valores já em unidades de engenharia (a escala do
Modbus já foi desfeita).

**Exemplos com curl:**

```bash
# metadados dos pontos
curl -s http://localhost:5000/api/meta | jq .

# snapshot único do estado
curl -s http://localhost:5000/api/state | jq '.ir.reactor_power_pct'

# acompanhar o stream SSE ao vivo (~4 Hz)
curl -N http://localhost:5000/api/stream

# comando de coil: disparar SCRAM manual
curl -s -X POST http://localhost:5000/api/command \
  -H 'Content-Type: application/json' \
  -d '{"kind":"coil","key":"cmd_manual_scram","value":1}'

# comando de coil: ligar a bomba RCP1
curl -s -X POST http://localhost:5000/api/command \
  -H 'Content-Type: application/json' \
  -d '{"kind":"coil","key":"cmd_rcp1_start","value":1}'

# setpoint (holding register): potência-alvo em 80%
curl -s -X POST http://localhost:5000/api/command \
  -H 'Content-Type: application/json' \
  -d '{"kind":"hr","key":"sp_power_pct","value":80}'

# meta-simulação: acelerar o tempo 720× (observar Xenônio)
curl -s -X POST http://localhost:5000/api/command \
  -H 'Content-Type: application/json' \
  -d '{"kind":"timescale","value":720}'

# meta-simulação: inserir LOCA de 60% de área
curl -s -X POST http://localhost:5000/api/command \
  -H 'Content-Type: application/json' \
  -d '{"kind":"loca","value":0.6}'
```

Para `kind:"coil"` o valor é tratado como booleano; para `kind:"hr"` como float
(em unidade de engenharia). Resposta `{"ok":true}` em sucesso, `400` com
`{"ok":false,"error":...}` em falha.

## 4. Ponto de segurança (didático)

Os comandos da HMI escrevem nos **MESMOS registradores Modbus** expostos na rede
OT (porta 502 do simulador — `172.28.10.10:502`, publicada no host em `5020`).
Um **operador legítimo** clicando num botão e um **atacante Modbus** escrevendo
no mesmo coil/holding register têm **efeito idêntico** sobre o processo: não há
autenticação e a HMI não é um controle de acesso. Isso é intencional — serve
para exercícios de detecção e resposta. Ver `docs/07` para os cenários de ataque.
