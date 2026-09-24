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

## 1. Neutrônica — cinética pontual

Potência neutronica `n` (normalizada, 1,0 = 100%) por **cinética pontual com 6
grupos de neutrons atrasados**:

```
dn/dt   = (ρ − β)/Λ · n + Σ λ_i·C_i
dC_i/dt = β_i/Λ · n − λ_i·C_i          (i = 1..6)
```

- `β_i`, `λ_i`: frações e constantes de decaimento dos precursores (U-235 térmico).
- `β_total ≈ 0,0065`; `Λ = 2×10⁻⁵ s` (tempo de geração de neutrons prontos).
- Integração **subpassada** (200 subpassos por passo de 0,1 s) por estabilidade
  numérica (o sistema é rígido). Há *clamp* de segurança em `n` e em `ρ`.

## 2. Reatividade — realimentação

`ρ` (Δk/k) é a soma de contribuições, **todas com coeficientes negativos**
(reator auto-regulado, como PWRs comerciais):

```
ρ = ρ_barras + α_Doppler·(T_comb − T_ref) + α_moderador·(T_refrig − T_ref) + α_boro·(C_boro − C_ref)
```

| Termo | Coeficiente | Efeito |
|---|---|---|
| Barras de controle | 6000 pcm de curso total | atuação direta |
| Doppler (combustível) | −2,5 pcm/K | negativo, rápido |
| Moderador (refrigerante, MTC) | −15 pcm/K | negativo |
| Boro | −0,8 pcm/ppm | ajuste lento de reatividade |

Na condição nominal (barras a 75% retiradas, temperaturas de referência,
800 ppm de boro) `ρ = 0` → **crítico a 100%**. Qualquer perturbação gera
realimentação estabilizante. `1 pcm = 10⁻⁵`.

## 3. Termohidráulica

**Combustível** (nó concentrado):
```
C_comb · dT_comb/dt = P_fissão − h_fc·(T_comb − T_refrig)
```

**Primário** (Tavg concentrado; entra calor do núcleo, saem os GVs e o PRHR):
```
C_refrig · dTavg/dt = Q_núcleo − Σ Q_GV − Q_PRHR   (− resfriamento por injeção de segurança)
```

**Thot / Tcold** derivam da elevação no núcleo, função da potência e da vazão das
bombas — se a vazão cai (RCP desligada), a elevação dispara → alta temperatura:
```
ΔT_núcleo = P_th / (W · cp)      Thot = Tavg + ΔT/2      Tcold = Tavg − ΔT/2
```

**Gerador de vapor** (cada um, secundário):
```
C_GV · dT_GV/dt = Q_primário − Q_vapor
Q_vapor = vazão_vapor · calor_latente
pressão = P_nom + inclinação·(T_GV − T_nom)          (saturação linearizada)
nível  += (vazão_alim − vazão_vapor) · ganho · dt     (balanço de massa)
```

**Turbina/gerador**: potência elétrica limitada pelo vapor disponível **e** pela
potência térmica × rendimento; rotação com inércia; desarme por sobrevelocidade
(3300 rpm).

## 4. Pressurizador

Pressão do primário controlada por expansão térmica (insurge/outsurge),
aquecedor (sobe), spray (desce) e válvula de alívio (PORV, abre em 172 bar):
```
dP = expansão·dTavg + aquecedor − spray − alívio
```
Nível acompanha a densidade (Tavg) e a reposição de inventário por injeção.

## 5. Calor de decaimento

Dois polos exponenciais (rápido τ≈15 s, lento τ≈400 s) alimentados pela potência
de fissão; após o SCRAM, a potência de fissão colapsa em segundos e o **calor de
decaimento** (~6,5% inicial) domina, caindo devagar. A potência térmica total é
`max(fissão, decaimento)`.

## 6. Proteção e segurança passiva

- **RPS** (`protection.py`): desarma o reator (barras caem por gravidade, ~30%/s)
  em fluxo alto, pressão PZR alta/baixa, nível baixo de GV, temperatura alta,
  vazão baixa ou pressão de contenção alta.
- **ESFAS**: atua as salvaguardas passivas por baixa pressão do PZR ("sinal S"),
  alta pressão de contenção ou nível baixo de GV.
- **PXS passiva** (`safety.py`): **PRHR** remove calor residual de forma
  proporcional ao superaquecimento (auto-limitante → estabiliza em parada quente);
  **CMT** e **acumuladores** injetam água borada; **ADS** despressuriza em 4
  estágios; **contenção** pressuriza/irradia se houver dano ao combustível.

## 7. Validação (comportamento observado)

Resultados do teste `plant.py` (passo 0,1 s, modo automático):

| Cenário | Resultado |
|---|---|
| Regime permanente 100% | P=100%, Tavg=304 °C, PZR=155 bar, ~1111 MWe, ρ≈0 — estável |
| Redução de carga p/ 80% | P segue a 80,2%, Tavg cai (reator segue turbina), ~895 MWe |
| SCRAM manual | P → decaimento em segundos; estabiliza em **parada quente ~287 °C** com alívio dos GVs removendo o calor residual |
| Perda das 4 RCPs | Vazão cai → RPS desarma por baixa vazão; Thot dispara (consequência severa) |
| 10 min pós-SCRAM | Planta estável ~287 °C, PZR 154 bar, decaimento 0,6% — sem divergência numérica |

Sem NaN/Inf em nenhum cenário. Detalhes de parâmetros: `simulator/npp/config.py`.
