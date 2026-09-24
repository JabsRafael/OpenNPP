# HMI web do simulador — OpenNPP

HMI custom servida pelo próprio simulador (Nível Purdue 2 — supervisão).
Acesse em **http://localhost:5000** com o ambiente de pé (`docker compose up`).

> Ambiente 100% SIMULADO (AP1000-like) para treino de defesa de OT/ICS. Nenhuma
> planta física real é controlada.

Código-fonte: `simulator/web/index.html`, `simulator/web/app.js`,
`simulator/npp/api.py`. A HMI é montada dinamicamente a partir de `/api/meta`
(mesmos pontos do `iomap.py`).

## 1. Layout da tela

**Header (barra superior)** — indicadores ao vivo e badge de status:

| Elemento | Campo (`ir.*`) | Observação |
|---|---|---|
| Potência | `reactor_power_pct` | potência térmica do reator (%) |
| MW elétrico | `gen_power_mwe` | geração no gerador (MWe) |
| Tavg | `coolant_tavg_c` | temperatura média do primário (°C) |
| Pressão PZR | `przr_pressure_bar` | pressão do pressurizador (bar) |
| Tempo sim | `st.t` | tempo de simulação em segundos |
| Badge | derivado | `NORMAL` / `ALARME` / `SCRAM / TRIP` |

O badge fica em `SCRAM / TRIP` quando `di.reactor_tripped`; em `ALARME` quando
qualquer `di.alm_*` está ativo; senão `NORMAL`.

**Mímico SVG da planta** — diagrama com: núcleo do **Reator**, **PZR**
(pressurizador), **4× RCP** (bombas do primário `rcp1`..`rcp4`), **Gerador de
Vapor 1/2** (GV1/GV2), **Turbina / Gerador** (nó `gen`), **Condensador** e o
retângulo de **Contenção** (pressão/radiação no canto). Dentro da contenção está
o grupo **PXS** de segurança passiva: **CMT**, **PRHR**, **ACUM** (acumulador) e
**ADS**. As tubulações (`hot1/2`, `cold1/2`, `steam1/2`, `feed`) animam quando há
fluxo.

**Tendências** — sparkline (`canvas#spark`) com três séries: Potência do reator
(%), Geração (MWe/12) e Tavg (°C). Histórico de até 240 amostras.

**Painel lateral** (`col-side`):
- **Alarmes & status** — uma linha por *discrete input* (`di.*`); acende quando
  o bit está ativo. Chaves de trip (`reactor_tripped`, `turbine_tripped`,
  `safety_blocked`, `alm_hi_cont_rad`, `alm_hi_cont_press`) recebem destaque.
- **Controle do operador** — gerado de `/api/meta`, agrupado por sistema: um
  **botão** por *coil* (`co.*`) e um **slider** por *holding register* (`hr.*`).
- **Leituras por sistema** — abas (nucleo, primario, gv1, gv2, turbina, pxs,
  contencao) com a tabela de *input registers* daquele sistema.

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
| POST | `/api/command` | corpo `{"kind":"coil"\|"hr","key":...,"value":...}` |

O snapshot (`/api/state` e cada evento SSE) tem a forma
`{"t": <s>, "ir": {...}, "di": {...}, "co": {...}, "hr": {...}}`, com os valores
já em unidades de engenharia (a escala do Modbus já foi desfeita).

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
