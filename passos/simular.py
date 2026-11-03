"""
Etapa - Simular.

Gera todas as capas em preview/ sem encostar no Steam. E o passo que
deixa conferir antes de mexer na biblioteca, e por isso vem separado de
Aplicar: ver o resultado e barato, desfazer nao e.
"""
from tkinter import ttk

from passos.base_rodar import BaseRodar


class Simular(BaseRodar):
    titulo = "Simular"
    simular = True

    def montar_acoes(self, barra):
        self.bt_acao.configure(text="Simular", style="Forte.TButton")
        self.bt_abrir = ttk.Button(barra, text="Abrir preview",
                                   command=self.abrir_preview,
                                   state="disabled")
        self.bt_abrir.pack(side="right")

    def _terminou(self, dado):
        super()._terminou(dado)
        if dado[0] is not None:
            self.bt_abrir.configure(state="normal")

    def concluida(self):
        return bool(self.sessao.ultima_simulacao)
