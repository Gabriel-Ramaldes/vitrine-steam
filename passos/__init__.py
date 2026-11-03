"""
As etapas, na ordem em que a aplicacao conduz.

Cada uma e um Passo (ttk.Frame) com um titulo e uma pre-condicao. A
pre-condicao olha a Sessao, nao "por onde voce ja passou": quem ja mapeou
e so quer rodar de novo nao e obrigado a refazer o caminho.

A ordem reflete a dependencia real: so da pra simular depois de mapear,
e so da pra aplicar depois de simular.
"""
from passos.inicio import Inicio
from passos.aparencia import Aparencia
from passos.colecoes import Colecoes
from passos.family import Family
from passos.capas import Capas
from passos.simular import Simular
from passos.aplicar import Aplicar

ORDEM = [
    Inicio,
    Aparencia,
    Colecoes,
    Family,
    Capas,
    Simular,
    Aplicar,
]
