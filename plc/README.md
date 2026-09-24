# OpenPLC como CLP de controle (mestre Modbus)

O OpenPLC roda o programa `npp_control.st` e atua como **mestre Modbus**, lendo os
sensores e escrevendo as demandas de atuador no simulador da planta
(`172.28.10.10:502`). Isto coloca o CLP "no laço" — e o torna um alvo realista de
exercício (comprometer o CLP = assumir o controle da planta). Ver `docs/04` e `docs/07`.

## 1. Acessar o OpenPLC

```
http://localhost:8082      (login padrão: openplc / openplc — troque depois)
```

## 2. Carregar o programa

1. **Programs → Upload Program** → envie `plc/npp_control.st` (tipo: Structured Text).
2. **Compile**. Corrija endereços se a UI acusar divergência (ver passo 4).
3. Ainda **não** dê *Start* — configure primeiro o dispositivo escravo.

## 3. Colocar o simulador em modo MANUAL

O programa do CLP já força `cmd_auto_control = 0` (coil 10). Você também pode
garantir pela HMI (http://localhost:5000) clicando em **"Habilita controle auto"**
para desligá-lo. Em manual, a planta obedece às demandas dos *holding registers*
que o CLP escreve.

## 4. Adicionar o Slave Device (o simulador)

**Slave Devices → Add new device**:

| Campo | Valor |
|---|---|
| Device Name | `NPP_PLANT` |
| Device Protocol | `Modbus TCP` |
| IP Address | `172.28.10.10` |
| IP Port | `502` |
| Slave ID | `1` |

Configuração de I/O (contagem e endereço inicial 0), casando com o `iomap`:

| Tipo Modbus | Início | Qtde | Vira no OpenPLC |
|---|---|---|---|
| Discrete Inputs (read) | 0 | 27 | `%IX100.0`+ |
| Coils (write) | 0 | 17 | `%QX100.0`+ |
| Input Registers (read) | 0 | 34 | `%IW100`+ |
| Holding Registers - Read | 0 | 12 | `%IW…` |
| Holding Registers - Write | 0 | 12 | `%QW100`+ |

> Os endereços `%IW100 / %IX100.0 / %QW100 / %QX100.0` usados no `.st` assumem que
> este é o **primeiro** dispositivo remoto (base 100). Se a UI atribuir outra base,
> ajuste os `AT %…` no programa. A UI mostra o endereço atribuído a cada ponto.

## 5. Iniciar

**Programs → Start PLC**. Observe na HMI do simulador (porta 5000) o CLP assumindo:
`auto_control_active` fica **desligado** e as demandas passam a vir do OpenPLC.

## 6. Validar o laço

- Suba/derrube o setpoint interno editando `sp_power` no `.st` e recompile, ou
- Force um transiente (ex.: pela HMI, reduza `dmd_turbine_valve`) e veja o CLP
  reagir mantendo Tavg/nível.

## Nota de segurança (cyber range)

O OpenPLC expõe seu próprio servidor Modbus (`172.28.10.20:502`, host `5021`) e a
web de engenharia (`8082`) — **ambos sem hardening** por padrão. São superfícies de
ataque tratadas em `docs/07` (ex.: upload de lógica maliciosa, escrita direta nos
registradores). Trate este ambiente como laboratório isolado.
