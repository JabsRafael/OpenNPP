# HMI web do simulador — OpenNPP

HMI custom servida pelo próprio simulador (Nível Purdue 2 — supervisão).
Acesse em **http://localhost:5000** com o ambiente de pé (`docker compose up`).

> Ambiente 100% SIMULADO (AP1000-like) para treino de defesa de OT/ICS. Nenhuma
> planta física real é controlada.

Código-fonte: `simulator/web/index.html`, `simulator/web/app.js`,
`simulator/npp/api.py`. A HMI é montada dinamicamente a partir de `/api/meta`
(mesmos pontos do `iomap.py`).

Manual do operador (significados de P-4…P-14, C-1/C-2/C-5, trips, siglas, cores e procedimento): botão **📖 Manual** no cabeçalho → `/help`.

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
- **Núcleo & instrumentação nuclear**: faixa-fonte (cps), intermediária (A), de
  potência (%), potência térmica, calor de decaimento, SUR, período, barras
  (% e passos) e a **decomposição da reatividade** (barras, Doppler, moderador,
  MTC, boro, Xenônio, Samário, veneno queimável, burnup).
- **Alarmes & status** e **Tendências** (sparkline: potência %, MWe/12, Tavg,
  **Xe %**; até 240 amostras).

**Painéis de controle (base)** — três colunas:

- **Painel do Primário & Reator**: sistemas `nucleo`, `primario`, `pxs` — setpoint
  de potência, barras, RCPs, pressurizador, boro, salvaguardas, SCRAM.
- **Painel do Secundário & Turbina**: sistemas `gv1`, `gv2`, `turbina` — válvula da
  turbina/desarme, nível e água de alimentação de cada GV.
- **Simulação & Malfunções**: cenário inicial, **rearme** (com o diagnóstico ao
  vivo do que impede o rearme), **velocidade da simulação** (1×/2×/5×/10×, planta
  inteira), **escala de tempo dos venenos** (1×…3600×) e **LOCA** (botões Sem /
  1% / 10% / 100%). Velocidade, escala e LOCA usam a API de meta-simulação (não
  são Modbus).

Cada botão reflete o estado do *coil* (`co.*`); cada campo de valor reflete o
*holding register* (`hr.*`).

## 2. Como operar

- **Somente botões (sem sliders):**
  - **Modo de operação**: seletor de dois botões **MANUAL / AUTOMÁTICO**.
  - **Barras**: alavanca **▼ INSERIR / ▲ RETIRAR** — *segure* para mover o banco
    (48 passos/min em manual), solte para parar (`kind: "rod"`, `in|out|hold`);
    **±5 passos** para ajuste fino.
  - **Setpoints/válvulas**: botões **−grosso −fino [valor] +fino +grosso**;
    segurar repete (`kind: "hr_step"`, incremento atômico no servidor).
  - Em AUTO as demandas manuais (barras, válvulas de turbina e alimentação) ficam
    travadas.
- **Comandos (botões coil):** clique alterna o coil (0↔1). Os bloqueios de trip
  de baixa potência (`cmd_block_sr_trip` acima de P-6, `cmd_block_lowpower_trips`
  acima de P-10) são **pulsos**; o botão acende enquanto o bloqueio está ativo.
- **Rearmar reator**: `kind: "reset"`. Se houver condição de trip presente o
  rearme é **negado** e o motivo (valor medido × setpoint) aparece no painel
  (ao vivo), no registro de eventos e no **console do navegador (F12)**.

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

# meta-simulação: inserir LOCA de 60% de área (a HMI usa 1% / 10% / 100%)
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

## 5. Operação: cenários, modos e repartida

O simulador imita um reator real — **nada é facilitado**.

### Cenários iniciais (painel Simulação → "Cenário inicial")
Recarregam a planta numa condição de partida realista:

| Cenário | Estado | Modo | Dificuldade |
|---|---|---|---|
| **Operando 100%** | Em potência, quente, crítico | **AUTO** | operar/atacar a partir de potência |
| **Parada quente** | Subcrítico, barras dentro, ~290 °C, pressurizado | MANUAL | rearmar e subir barras |
| **Desligado a frio** | ~50 °C, 28 bar, boro ~1900 ppm, bombas off | MANUAL | aquecer + pressurizar + partida completa |
| **1ª partida pós-manut.** | Frio, núcleo novo (sem Xe/Sm), boro ~2100 ppm | MANUAL | a partida mais difícil |

### Modo AUTO × MANUAL (AUTO é opt-in)
- "Operando 100%" já vem em **AUTO**: turbina em rampa de 5%/min até o setpoint de carga, barras seguindo o programa de Tavg (Tref).
- Cenários de **partida** iniciam em **MANUAL**. **Ao tripar, a planta sempre cai para MANUAL**; a demanda das barras acompanha as barras no fundo e as válvulas de turbina/alimentação fecham — nada volta sozinho ao rearmar.
- **C-5**: em AUTO as barras só retiram sozinhas com a turbina ≥ 15%.

### Procedimento de repartida (MANUAL, após SCRAM ou a frio)
0. (A frio) 4 RCPs + aquecedor do PZR; aquecer com o calor das bombas (~40 °C/h — use a **velocidade da simulação** 5–10×).
1. **Rearmar** — só passa sem condição de trip presente; o painel diz o que falta.
2. **Aquecedor do PZR** para levar a pressão a 155 bar; turbina fechada (o **despejo de vapor** segura o Tavg em 292 °C).
3. **Diluir o boro** (a frio) e **retirar as barras devagar** olhando a **SUR ≤ 1 dpm** (a ECP em parada quente é ~150 passos; o Xe pós-trip vai tirando reatividade).
4. Acima de **P-6** (IR > 1e-10 A): **bloquear o trip da faixa-fonte** antes de 1e5 cps.
5. ~1%: ponto de adição de calor (o Doppler freia). ~3–5%: **ligar a bomba de alimentação principal** — a SFW só dá ~6%.
6. Acima de **P-10** (10%): **bloquear os trips de IR/PR-baixo** antes de 25%. Abrir a turbina; AUTO com carga ≥ 15%.

### Período e SUR
Cabeçalho e painel "Núcleo & instrumentação nuclear": período (e-folding) e SUR (décadas/min). Positivo curto = subindo rápido; o painel também mostra SR (cps), IR (A), potência térmica, MTC e a decomposição da reatividade.

### Registro de eventos
A faixa **"Registro de eventos"** (e o **console do navegador, F12**) mostram o que aconteceu com a causa: `SCRAM — causa: …`, `ESFAS atuado`, `CMT injetando`, `ADS atuado`, `Salvaguardas BLOQUEADAS`, `LOCA iniciado`, `Controle transferido para MANUAL`, etc. É o guia para entender cada transiente.
