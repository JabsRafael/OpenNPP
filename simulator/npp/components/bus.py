"""
Barramento de processo — variaveis de acoplamento entre os modulos fisicos.

Cada componente le do bus o que precisa e escreve suas saidas. Isso mantem os
modulos desacoplados (o nucleo nao conhece o gerador de vapor; ambos so' falam
com o bus), espelhando as interfaces fisicas reais entre sistemas da planta.
"""

from dataclasses import dataclass, field

from .. import config as C


@dataclass
class ProcessBus:
    # -- neutronica / potencia
    fission_frac: float = 1.0        # fracao de potencia de fissao
    power_frac: float = 1.0          # fracao termica total (fissao ou decaimento)
    decay_frac: float = 0.0
    P_th: float = C.RATED_MWTH       # potencia termica entregue ao primario (MW)
    reactivity: float = 0.0          # Delta-k/k (total)
    rho_poison: float = 0.0          # Delta-k/k dos venenos (Xe+Sm+queimavel)
    burnup: float = 0.0              # % do ciclo (afeta o MTC)

    # -- temperaturas / vazao primaria
    T_fuel: float = C.FUEL_TEMP_REF
    T_coolant: float = C.COOLANT_TEMP_REF   # Tavg
    T_hot: float = C.COOLANT_TEMP_REF
    T_cold: float = C.COOLANT_TEMP_REF
    core_dt: float = 0.0
    flow_frac: float = 1.0           # vazao primaria (0..~1.1)
    boron: float = C.BORON_REF

    # -- calor removido (somado no primario)
    Q_core: float = 0.0              # combustivel -> refrigerante (MW)
    Q_sg_total: float = 0.0          # primario -> geradores de vapor (MW)
    Q_prhr: float = 0.0              # primario -> PRHR (MW)
    Q_ads: float = 0.0               # vapor ventilado pelo ADS (MW)
    Q_break: float = 0.0             # energia levada pela ruptura (MW)
    ads_mass_flow: float = 0.0       # kg/s de vapor saindo pelo ADS

    # -- vapor / turbina
    steam_flow_total: float = 0.0    # kg/s (turbina + despejo + alivio)
    turbine_steam: float = 0.0       # kg/s admitidos na turbina
    steam_dump_frac: float = 0.0     # abertura do despejo de vapor (0..1)
    feed_isolated: bool = False      # isolamento da alimentacao principal

    # -- injecao de inventario (seguranca passiva)
    si_flow: float = 0.0             # kg/s de injecao no primario

    # -- LOCA / inventario do primario
    cooling_factor: float = 1.0      # 1,0 = nucleo coberto; <1 = descoberto (LOCA)

    # -- trips
    tripped: bool = False
    turbine_tripped: bool = False
