"""
Etapa - Aplicar.

Escreve as capas na biblioteca. So libera depois de uma simulacao: o
caminho "gerou, olhou, aplicou" e o que impede aplicar 2.800 capas e so
entao descobrir que o mapeamento estava trocado.

Tambem e aqui que mora o Desfazer, porque e aqui que ha o que desfazer.
"""
from tkinter import ttk

import core
from passos.base_rodar import BaseRodar


class Aplicar(BaseRodar):
    titulo = "Aplicar"
    simular = False

    @staticmethod
    def precisa(sessao):
        return sessao.tem_steam and sessao.tem_listas and sessao.simulou

    def montar_acoes(self, barra):
        self.bt_acao.configure(text="APLICAR", style="Perigo.TButton")
        self.bt_desfazer = ttk.Button(barra, text="Desfazer tudo",
                                      command=self.desfazer)
        self.bt_desfazer.pack(side="right")

    def liberado(self):
        return self.pronto and self.sessao.simulou

    def ao_entrar(self):
        super().ao_entrar()
        if not self.sessao.simulou:
            self.estado("simule primeiro - a etapa anterior gera em preview/")

    def _terminou(self, dado):
        super()._terminou(dado)
        self.bt_desfazer.configure(state="normal")

    def concluida(self):
        return bool(self.sessao.ja_aplicados())
