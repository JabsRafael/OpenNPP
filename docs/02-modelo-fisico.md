# Modelo físico — PWR classe AP1000

O simulador reproduz a **dinâmica** de uma usina PWR classe AP1000 (Westinghouse
Gen III+) com fidelidade **intermediária**: suficiente para controle, operação e
demonstração de ataques/defesa, sem ser um código de reator validado.

> Todos os parâmetros vêm de dados de **domínio público** do AP1000 (3400 MWth,
> ~1117 MWe, 2 geradores de vapor, 4 bombas de refrigerante, segurança passiva).
> Calibrados para dinâmica estável e didática. Não é modelo licenciado de nenhuma
> unidade real. Parâmetros em `simulator/npp/config.py`.

## Organização modular

Cada sistema é um componente Python independente que só troca dados pelo
`ProcessBus` (`components/bus.py`). Ordem de avaliação por passo (fluxo de energia):

```
ReactorCore → SteamGenerator×2 → PrimarySystem → Turbine → Proteção(RPS/ESFAS) → PassiveSafety
```

| Componente | Arquivo | Modela |
|---|---|---|
| Núcleo (reator) | `components/core.py` | Neutrônica, reatividade, temp. combustível, decaimento |
| Primário | `components/primary.py` | Tavg, Thot/Tcold, 4 RCPs, pressurizador |
| Gerador de vapor (×2) | `components/steam_generator.py` | Secundário: T, pressão, nível, vapor, alívio |
| Turbina/gerador | `components/turbine.py` | Rotação, potência elétrica, sobrevelocidade |
| Segurança passiva | `components/safety.py` | CMT, acumuladores, PRHR, ADS, IRWST, contenção |

## 1. Neutrônica — cinética pontual com fonte

Potência neutrônica `n` (normalizada, 1,0 = 100%) por **cinética pontual com 6
grupos de nêutrons atrasados** e **fonte de nêutrons de partida** `S`:

```
dn/dt   = (ρ − β)/Λ · n + Σ λ_i·C_i + S
dC_i/dt = β_i/Λ · n − λ_i·C_i          (i = 1..6)
```

- `β_total ≈ 0,0065`; `Λ = 2×10⁻⁵ s`.
- **Fonte** (Cf-252/Sb-Be): o núcleo desligado tem população finita
  (`n = S·Λ/|ρ|`, ~20–30 cps a −5000 pcm). Retirar barras abaixo da
  criticalidade dá um período positivo *transitório* que depois estabiliza
  (multiplicação subcrítica) — exatamente o que o operador vê na aproximação.
- Integração **Euler implícito** (50 subpassos por 0,1 s): estável mesmo com
  −10000 pcm (parada fria), sem o *clamp* em zero que o esquema explícito exigia.
- **Instrumentação nuclear (NIS)** em três faixas: fonte (SR, cps), intermediária
  (IR, A) e potência (PR, %); **SUR** (décadas/min) e período filtrados.

## 2. Reatividade — realimentação

```
ρ = ρ_barras(curva S) + ρ_Doppler(√T) + ∫MTC(T,B,burnup)dT + α_B·ΔB + ρ_venenos
```

| Termo | Modelo | Valores |
|---|---|---|
| Barras | valor **integral em curva S** (`x − sin(2πx)/2π`); 228 passos | 6000 pcm; 48 passos/min manual, 72 em AUTO; SCRAM ~2,2 s |
| Doppler | `−A·(√T_comb − √T_ref)` (K absolutos) | −2,5 pcm/K a 900 °C, maior a frio |
| Moderador (MTC) | `MTC = −20 − 0,078·ΔT + 0,008·ΔB − 0,3·burnup` pcm/K | ~0 a frio; −20 BOC a plena carga; ~−55 fim de ciclo; **positivo** a frio com boro alto |
| Boro | −10 pcm/ppm a quente (termo cruzado → ~−12 a frio) | CVS exponencial (feed & bleed) |

Referência: barras 75%, Tavg 305 °C, 800 ppm, combustível 900 °C → `ρ = 0` a 100%.
Defeito de potência HZP→HFP ≈ 1900 pcm. Parada fria (1900 ppm): ≈ −10800 pcm.

## 3. Termohidráulica

Capacidades térmicas com a massa real: **combustível 38 MJ/K** (τ ≈ 6,7 s),
**RCS 1300 MJ/K** (~190 t de água + metal), **cada GV 500 MJ/K**. Aquecimento com
o calor das 4 RCPs (20 MW) ≈ **40 °C/h** — ~6 h de 50 °C a 292 °C (use a
velocidade da simulação).

- **Potência térmica** = fissão "pronta" `(1 − 6,6%)·n` + calor de decaimento.
- **GV**: pressão = **saturação** da água do GV (tabela de vapor, `water.py`):
  ~57 bar a plena carga, ~77 bar sem carga. Saídas: turbina, **despejo de vapor
  ao condensador** (40%, automático: segura Tavg no programa após trip/baixa
  carga) e alívio (80 bar). Entradas: alimentação principal (isolável por P-4/
  P-14) e **alimentação de partida (SFW, ~6%)**, automática quando a principal não
  entrega.
- **Turbina**: só o vapor admitido gera potência; o despejado vai ao condensador.

## 4. Pressurizador e balanço de massa

- **Massa**: o loop fica cheio enquanto o PZR tem água. Perda (LOCA/ADS) esvazia
  primeiro o PZR, depois o loop; injeção enche o loop e depois o PZR.
- **Nível** dinâmico: expansão térmica (1,3%/K) + **CVS** automático que segura o
  programa (25% sem carga → 55% a plena carga) com capacidade limitada (20 kg/s).
- **Pressão**: `dP = 0,9 bar/% · dNível + aquecedores (0,3 bar/s) − spray (1,5 bar/s) − PORV`;
  aquecedores cortam com nível < 17%. Nunca abaixo da saturação do ramo quente;
  com o PZR vazio o RCS é saturado (`P = Psat(Thot)`).

## 5. Calor de decaimento

**7 grupos exponenciais** ajustados à curva ANS-5.1 (após operação longa), com
memória do histórico de potência: 1 s ≈ 6,2% · 100 s ≈ 3,2% · 1 h ≈ 1,4% ·
1 dia ≈ 0,5% · 12 dias ≈ 0,2%. Núcleo novo (1ª partida) não tem calor residual.

## 6. Proteção, permissivos e segurança passiva

- **RPS**: PR alto 109%, PR baixo 25% e IR 25% (bloqueáveis acima de **P-10**),
  faixa-fonte 1e5 cps (bloqueável acima de **P-6**), taxa positiva de fluxo
  (+5% em 2 s), pressão PZR alta 168 / baixa 128 bar, nível PZR alto 92%, vazão
  baixa 87% (os três últimos bloqueados abaixo de **P-7**, 10%), nível baixo de GV,
  sobretemperatura do combustível, contenção alta e **sinal S** (SI → trip).
  Os bloqueios de P-6/P-10 são **manuais** (botões) e se reinstalam sozinhos
  quando a potência cai.
- **C-1/C-2**: bloqueiam a retirada de barras (IR alta / 103%). **C-5**: AUTO não
  retira barras com a turbina < 15%.
- **Rearme**: só com nenhuma condição de trip presente. A HMI/API devolve cada
  condição com valor medido e setpoint (painel + console do navegador + log).
- **Controle AUTO** (Westinghouse): turbina em rampa de 5%/min até o setpoint de
  carga; barras seguem **Tref** (292 °C sem carga → 305 °C a 100%) + canal de
  descasamento potência×carga.
- **PXS**: PRHR (auto-limitante); **CMT** 2×70 t; **acumuladores** 2×57 t com N₂ a
  48 bar (isolados abaixo de P-11); **ADS** em sequência AP1000 (ADS-1 com CMT <
  67,5%, ADS-2/3 temporizados, ADS-4 com CMT < 20%), ventilando vapor; **IRWST**
  por gravidade com o RCS despressurizado; contenção pressuriza com o vapor
  liberado e é resfriada pelo PCS.

## 7. Venenos e escala de tempo (`components/reactor_poisons.py`)

Produtos de fissão que absorvem neutrons e inserem reatividade negativa. A
dinâmica é lenta (horas a meses), integrada com passo acelerado
`dt_acel = dt × escala_de_tempo` — assim dá para observar o Xenônio em minutos.

Concentrações normalizadas (1,0 = equilíbrio a 100%); reatividade em **desvio** do
equilíbrio (zero no início → preserva a criticalidade).

- **Iodo-135 / Xenônio-135** (T½ 6,6 h / 9,1 h): estoque de iodo `I_eq = 2,3×` o
  Xenônio → após o SCRAM o Xe **sobe** (o I continua decaindo mas a queima por
  fluxo cessa), atinge **pico em ~9–11 h (≈147%, −1300 pcm)** e depois decai. Esse
  "poço de iodo" pode **impedir a repartida** (xenon precluded start).
- **Promécio-149 / Samário-149** (permanente): após desligar, o Sm sobe para um
  novo equilíbrio e **fica** (não decai).
- **Veneno queimável / burnup**: depleta muito devagar com o burnup do ciclo,
  liberando reatividade positiva (compensada pelo controle de barras).

**Escala de tempo** (`escala_de_tempo`, 1×–3600×): acelera **apenas** os venenos e
o burnup, não a dinâmica rápida (potência/térmica). O relógio do reator (`rh`, em
horas) avança na taxa acelerada. Ajustável pela HMI. Use 1× para transientes
térmicos; alto para observar Xenônio.

## 8. LOCA — perda de refrigerante (`primary.py`)

Área da ruptura 0–100% de uma guilhotina dupla (~12 t/s a 155 bar), vazão
`∝ área·√ΔP`. Sequência física: o PZR esvazia (a pressão cai) → trip + sinal S →
o RCS satura e a pressão **"pendura" na saturação** → a energia sai pela ruptura,
GVs e PRHR → CMT → ADS → acumuladores → IRWST. Com o RCS na pressão da contenção
só escoa a água acima do bocal da ruptura. Com o RCS aberto e saturado o calor
residual **ferve** a água (*boil-off*). Núcleo seco → resfriamento só por vapor →
combustível aquece ~1,5–2 K/s.

## 9. Validação (comportamento observado)

| Cenário | Resultado |
|---|---|
| Regime permanente 100% | P=100%, Tavg=305 °C, PZR=155 bar, ~1115 MWe, ρ≈0 |
| AUTO 100→50→100% | rampa de 5%/min, Tavg no programa (298 °C a 50%), sem overshoot |
| SCRAM a 100% | despejo de vapor segura Tavg ~293 °C, PZR ~140 bar (sem SI), GV 77 bar; decaimento 1,4% em 1 h; **rearme liberado** |
| Parada quente → crítico | ECP ~150 passos a 880 ppm; o Xe pós-trip tira reatividade se o operador não compensar |
| Subida de potência | trip da faixa-fonte se não bloqueado acima de P-6; ponto de adição de calor ~1%; SFW não segura os GVs acima de ~6% sem a alimentação principal |
| Perda de 1 RCP a 100% | vazão 75% < 87% → trip |
| Partida a frio | 4 RCPs + aquecedor: ~40 °C/h, ~6 h até 292 °C |
| LOCA 1% / 10% / 100% **com** salvaguardas | núcleo permanece coberto, combustível < 350 °C após o trip |
| LOCA 10% / 100% **sem** salvaguardas | núcleo seca, combustível > 1200 °C (dano) e contenção pressuriza |
