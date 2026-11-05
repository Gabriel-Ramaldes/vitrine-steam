"""
Etapa 1 - Comecar.

Diz o que a ferramenta faz, onde achou o Steam, o que vai mexer e que da
pra desfazer. E mostra a lista de verificacao: o que ja esta pronto e o
que falta, com a etapa que resolve cada pendencia.
"""
from tkinter import ttk

import tema
from app import Passo


class Inicio(Passo):
    titulo = "Começar"

    def montar(self):
        ttk.Label(self, text="Vitrine", style="Titulo.TLabel"
                  ).pack(anchor="w")
        ttk.Label(self, style="Sub.TLabel", justify="left", wraplength=700,
                  text="Transforma a sua biblioteca Steam numa estante de "
                       "caixas de jogo: cada capa ganha uma moldura e um "
                       "badge dizendo em que pé está aquele jogo."
                  ).pack(anchor="w", pady=(2, 14))

        cx = ttk.Frame(self, style="Painel.TFrame", padding=(16, 12))
        cx.pack(fill="x")
        ttk.Label(cx, text="O que vai acontecer", style="Painel.TLabel",
                  font=(tema.FONTE, 11, "bold")).pack(anchor="w")
        for linha in (
            "O status de cada jogo sai das suas Coleções do Steam. "
            "Nenhuma lista pra manter à mão.",
            "As capas originais são guardadas em originais/ antes de "
            "qualquer troca. Dá pra desfazer tudo a qualquer momento.",
            "Você simula primeiro, confere numa pasta, e só então aplica.",
        ):
            f = ttk.Frame(cx, style="Painel.TFrame")
            f.pack(fill="x", pady=2)
            ttk.Label(f, text="• ", style="Painel.Fraco.TLabel"
                      ).pack(side="left", anchor="n")
            ttk.Label(f, text=linha, style="Painel.Fraco.TLabel",
                      wraplength=640, justify="left").pack(side="left")

        ttk.Label(self, text="Antes de aplicar, feche o Steam.",
                  style="Alerta.TLabel").pack(anchor="w", pady=(12, 2))
        ttk.Label(self, style="Sub.TLabel", wraplength=700, justify="left",
                  text="O cliente reescreve as capas ao sair. Com ele aberto, "
                       "o resultado some e parece que nada funcionou."
                  ).pack(anchor="w")

        ttk.Label(self, text="Como está agora", style="TLabel",
                  font=(tema.FONTE, 11, "bold")).pack(anchor="w", pady=(18, 4))
        self.lista = ttk.Frame(self, style="Painel.TFrame", padding=(14, 10))
        self.lista.pack(fill="x")

        rodape = ttk.Frame(self)
        rodape.pack(fill="x", pady=(12, 0))
        self.bt_reler = ttk.Button(rodape, text="Conferir de novo",
                                   command=self.app.recarregar)
        self.bt_reler.pack(side="left")
        ttk.Label(rodape, style="Fraco.TLabel", wraplength=560,
                  justify="left",
                  text="Sem fins lucrativos, feito por hobby. Logo da Steam "
                       "da Valve. Icons created by Magnific - Flaticon. "
                       "Capas da SteamGridDB."
                  ).pack(side="left", padx=14)

        self.sessao.ao_mudar(lambda s: self.desenhar())

    def ao_entrar(self):
        self.desenhar()

    def desenhar(self):
        for w in self.lista.winfo_children():
            w.destroy()
        itens = self.sessao.conferir()
        if not itens:
            ttk.Label(self.lista, text="lendo...", style="Painel.Fraco.TLabel"
                      ).pack(anchor="w")
            return
        for ok, texto, detalhe in itens:
            estilo = {True: "Painel.Ok.TLabel", False: "Painel.Erro.TLabel",
                      None: "Painel.Alerta.TLabel"}[ok]
            marca = {True: "ok", False: "X", None: "!"}[ok]
            f = ttk.Frame(self.lista, style="Painel.TFrame")
            f.pack(fill="x", pady=1)
            ttk.Label(f, text=marca, style=estilo, width=4).pack(side="left")
            ttk.Label(f, text=texto, style="Painel.TLabel").pack(side="left")
            if detalhe:
                ttk.Label(f, text=detalhe, style="Painel.Fraco.TLabel"
                          ).pack(side="left", padx=10)

    def concluida(self):
        return self.sessao.tem_steam
