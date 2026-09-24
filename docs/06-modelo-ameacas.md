# Modelo de ameaças

> **Escopo e ética.** Ambiente 100% simulado e isolado, para treino **defensivo**
> (red/blue team) de segurança de OT/ICS. As vulnerabilidades são intencionais e
> reproduzem sistemas industriais legados. Use apenas neste laboratório, na sua
> própria infraestrutura. O objetivo é **entender ataques para detectá-los e
> mitigá-los** — não atacar sistemas reais.

## Por que OT/ICS é diferente de TI

| | TI | OT/ICS |
|---|---|---|
| Prioridade | Confidencialidade | **Disponibilidade e segurança física** |
| Protocolos | TLS, autenticação | Modbus/DNP3 **sem autenticação/cifra** |
| Ciclo de vida | anos | décadas (equipamentos legados) |
| Patch | frequente | raro (janelas de parada) |
| Impacto | dados | **dano físico, segurança de vidas** |

Neste range o "dano físico" é simulado: SCRAM indevido, superaquecimento,
sobrevelocidade de turbina, esvaziamento de GV, dano ao combustível na contenção.

## Superfície de ataque (por nível Purdue)

```
Nível 2  ScadaLTS (:8080, Tomcat/Java legado)  ── HMI/supervisão
Nível 2  HMI web do simulador (:5000, API HTTP) ── operação
Nível 1  OpenPLC (:8082 web eng., :502 Modbus)  ── CLP de controle
Nível 1  Simulador Modbus (:502, SEM auth)      ── barramento de campo
Nível 3  MySQL (backend ScadaLTS)               ── historiador/credenciais
Rede     172.28.10.0/24 PLANA (sem segmentação) ── movimento lateral livre
```

### Vulnerabilidades intencionais (por design)

1. **Modbus sem autenticação nem integridade** — qualquer host da rede lê e
   **escreve** coils/registradores. Não há sessão, assinatura ou controle de acesso.
2. **Sem allow-list de mestres** — o escravo aceita escrita de qualquer origem.
3. **Rede plana** — TI e OT no mesmo domínio de broadcast; sem firewall/DMZ.
4. **CLP sem hardening** — OpenPLC permite upload de lógica e escrita remota.
5. **HMI e rede OT compartilham estado** — comando de operador e escrita de
   atacante são indistinguíveis no nível do registrador.
6. **Salvaguardas com bypass** — `cmd_block_safety` simula um bypass de manutenção
   que, se acionado por um atacante, derruba a camada DID de salvaguardas.
7. **Proteção confia nos sensores** — RPS/ESFAS agem sobre valores de sensor; um
   valor **falsificado** engana a proteção (base do ataque tipo Stuxnet).

## Perfis de adversário

| Perfil | Acesso | Objetivo |
|---|---|---|
| Insider / estação de engenharia | Rede OT direta | Sabotagem, alteração de lógica |
| Pivô de TI → OT | Comprometeu TI, atravessou rede plana | Alcançar o CLP/SCADA |
| Ransomware OT | Qualquer host | Parada forçada (SCRAM em massa), extorsão |

## Mapeamento MITRE ATT&CK for ICS

| Tática | Técnica (ID) | No range |
|---|---|---|
| Initial Access | Exploit Public-Facing App (T0819) | ScadaLTS/OpenPLC web expostos |
| Discovery | Remote System Discovery (T0846) | varredura Modbus na /24 |
| Collection | Point & Tag ID (T0861) | ler mapa de registradores |
| Inhibit Response Function | Block Reporting Message (T0804); Modify Alarm Settings (T0835) | `cmd_block_safety`, mascarar alarmes |
| Impair Process Control | Unauthorized Command Message (T0855); Modify Parameter (T0836); Spoof Reporting Message (T0856) | escrita de coil/HR; injeção de sensor |
| Damage/Impact | Loss of Control (T0827); Manipulation of Control (T0831); Loss of Safety (T0880) | SCRAM, superaquecimento, bypass de salvaguarda |

## Defense-in-Depth (barreiras)

O simulador modela camadas DID independentes (IAEA):

| Nível DID | No simulador | Ataque precisa vencer |
|---|---|---|
| 1 Prevenção (projeto) | coeficientes de reatividade negativos | física — não atacável |
| 2 Controle da operação | `controllers/` / OpenPLC | escrita de comando/parâmetro |
| 3 Proteção | RPS (trip) | falsificar sensor de trip |
| 3 Salvaguardas | ESFAS + PXS passiva | `cmd_block_safety` ou spoof |
| 4 Mitigação | contenção | dano físico sustentado |

**Lição central:** vencer o controle (nível 2) **não** causa dano se proteção e
salvaguardas (nível 3) atuam. Por isso os ataques de maior impacto combinam
manipulação de controle **com** inibição/engano da proteção — exatamente o que os
playbooks (`docs/07`) exercitam, e onde a detecção do blue team é mais valiosa.

## Princípios de defesa (o que o range ensina a construir)

- **Segmentação** OT/IT (firewall, DMZ de dados, idealmente diodo de dados).
- **Allow-list de mestres Modbus** e monitoração de escritas anômalas.
- **Detecção baseada em processo**: alarmar quando sensores/atuadores violam a
  física esperada (ex.: potência cai sem comando de barras; GV1 e GV2 divergem).
- **Integridade da proteção**: RPS/ESFAS em rede isolada; `cmd_block_safety`
  jamais ativo em operação — alarme imediato.
- **Baseline de tráfego Modbus** (função, origem, frequência) e IDS de OT.
- **Registro imutável** de comandos com origem, para diferenciar operador de atacante.
