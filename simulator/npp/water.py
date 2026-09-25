"""
Propriedades da agua — curva de saturacao (tabela de vapor IAPWS, interpolada
em log(P)). Usada pelos geradores de vapor: a pressao do secundario e' a pressao
de saturacao da agua do GV, e nao uma reta calibrada.
"""

from bisect import bisect_left
from math import exp, log

# degC -> bar (tabela de vapor saturado)
_T = [20, 50, 100, 150, 200, 250, 270, 280, 290, 300, 310, 320, 330, 340, 350, 360, 370, 373.9]
_P = [0.02339, 0.1235, 1.0142, 4.7617, 15.549, 39.762, 55.058, 64.202, 74.461, 85.927,
      98.700, 112.89, 128.63, 146.05, 165.35, 186.75, 210.54, 220.64]
_LP = [log(p) for p in _P]


def psat(t_c):
    """Pressao de saturacao (bar) a t_c (degC)."""
    t = max(_T[0], min(_T[-1], t_c))
    i = max(1, bisect_left(_T, t))
    f = (t - _T[i - 1]) / (_T[i] - _T[i - 1])
    return exp(_LP[i - 1] + f * (_LP[i] - _LP[i - 1]))


def tsat(p_bar):
    """Temperatura de saturacao (degC) a p_bar (bar)."""
    lp = log(max(_P[0], min(_P[-1], p_bar)))
    i = max(1, bisect_left(_LP, lp))
    f = (lp - _LP[i - 1]) / (_LP[i] - _LP[i - 1])
    return _T[i - 1] + f * (_T[i] - _T[i - 1])
