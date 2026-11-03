"""
Etapa - Family Share.

A parte mais confusa do produto, e ate aqui explicada so no README.

A lista dos jogos emprestados NAO existe no seu computador, e nenhuma
lista que a Steam serve na web separa o que e seu do que e emprestado -
isso foi medido, nao suposto (ver DESENVOLVIMENTO.md, secao 7). Entao
esta etapa faz duas coisas: mostra de onde o canto verde esta saindo
hoje, e ensina o unico caminho que da a lista completa - deixar o proprio
cliente materializa-la numa Colecao.
"""
import traceback
import webbrowser

import tkinter as tk
from tkinter import ttk

import core
import tema
from app import Passo

URL_FAMILY = "https://store.steampowered.com/account/familymanagement"


class Family(Passo):
    titulo = "Family Share"

    @staticmethod
    def precisa(sessao):
        return sessao.tem_steam

    def montar(self):
        self.lido = False
        ttk.Label(self, text="Family Share", style="Titulo.TLabel"
                  ).pack(anchor="w")
        ttk.Label(self, style="Sub.TLabel", wraplength=720, justify="left",
                  text="O canto verde marca os jogos que estao na sua "
                       "biblioteca por emprestimo."
                  ).pack(anchor="w", pady=(2, 12))

        self.estado_cx = ttk.Frame(self, style="Painel.TFrame", padding=(14, 11))
        self.estado_cx.pack(fill="x")

        ttk.Label(self, text="Como ter a lista completa",
                  font=(tema.FONTE, 11, "bold")).pack(anchor="w", pady=(16, 2))
        ttk.Label(self, style="Sub.TLabel", wraplength=720, justify="left",
                  text="A lista nao existe em disco: o cliente pede os "
                       "appids ao servidor e os mantem na memoria. Mas ele "
                       "sabe quais sao - entao peca a ele."
                  ).pack(anchor="w", pady=(0, 8))

        passos_cx = ttk.Frame(self, style="Painel.TFrame", padding=(14, 11))
        passos_cx.pack(fill="x")
        for n, txt in enumerate((
            "Na biblioteca do Steam, clique em STEAM FAMILY na barra lateral.",
            "Selecione tudo: clique no primeiro jogo e Shift+clique no ultimo.",
            "Botao direito -> Adicionar a -> nova colecao, chamada FAMILY.",
            "Feche o Steam (ele so grava as colecoes ao sair).",
            "Volte na etapa Colecoes e marque a caixa 'family' na linha FAMILY.",
        ), 1):
            f = ttk.Frame(passos_cx, style="Painel.TFrame")
            f.pack(fill="x", pady=2)
            ttk.Label(f, text=f"{n}.", style="Painel.Fraco.TLabel", width=3
                      ).pack(side="left", anchor="n")
            ttk.Label(f, text=txt, style="Painel.TLabel", wraplength=640,
                      justify="left").pack(side="left")

        rodape = ttk.Frame(self)
        rodape.pack(fill="x", pady=(12, 0))
        ttk.Button(rodape, text="Conferir de novo", command=self.ler
                   ).pack(side="left")
        ttk.Button(rodape, text="Abrir a pagina da familia",
                   command=lambda: webbrowser.open(URL_FAMILY)
                   ).pack(side="left", padx=8)

        ttk.Label(self, style="Fraco.TLabel", wraplength=720, justify="left",
                  text="Por que nao da pra detectar sozinho: as listas que a "
                       "Steam serve na web dizem o que voce PODE JOGAR, e "
                       "desde o Steam Families isso inclui o emprestado. "
                       "Medido contra os jogos que o appmanifest prova serem "
                       "emprestados, subtrair essas listas acerta 6%. O "
                       "appmanifest e exato, mas so cobre o que esta "
                       "instalado."
                  ).pack(anchor="w", pady=(12, 0))

    def ao_entrar(self):
        if not self.lido:
            self.ler()

    def ler(self):
        for w in self.estado_cx.winfo_children():
            w.destroy()
        ttk.Label(self.estado_cx, text="lendo...", style="Painel.Fraco.TLabel"
                  ).pack(anchor="w")
        s = self.sessao
        if not s.tem_steam:
            return

        def trabalho():
            dados = {}
            try:
                grupo, membros = core.grupo_family(s.steam, s.user)
                dados["grupo"] = grupo
                dados["membros"] = sorted(membros)
                uniao, diag = core.apps_dos_membros(s.steam, s.user)
                dados["cache"] = diag
                dados["uniao"] = len(uniao)
                certos, _ = core.instalados_por_origem(s.steam)
                dados["appmanifest"] = len(certos)
            except Exception:
                dados["erro"] = traceback.format_exc(limit=2)
            dados["colecao"] = len({a for l in s.listas
                                    if l["nome"] == "family"
                                    for a in l["appids"]})
            self.app.na_janela(lambda: self.mostrar(dados))

        self.app.em_thread(trabalho)

    def mostrar(self, d):
        self.lido = True
        for w in self.estado_cx.winfo_children():
            w.destroy()

        def linha(estado, texto, detalhe=""):
            estilo = {True: "Painel.Ok.TLabel", False: "Painel.Erro.TLabel",
                      None: "Painel.Alerta.TLabel"}[estado]
            marca = {True: "ok ", False: "X  ", None: "!  "}[estado]
            f = ttk.Frame(self.estado_cx, style="Painel.TFrame")
            f.pack(fill="x", pady=1)
            ttk.Label(f, text=marca, style=estilo, width=4).pack(side="left")
            ttk.Label(f, text=texto, style="Painel.TLabel").pack(side="left")
            if detalhe:
                ttk.Label(f, text=detalhe, style="Painel.Fraco.TLabel",
                          wraplength=420, justify="left"
                          ).pack(side="left", padx=8)

        if d.get("erro"):
            linha(False, "nao consegui ler", d["erro"].splitlines()[-1][:80])
            return

        if d.get("grupo"):
            linha(True, f"Steam Family configurada",
                  f"grupo {d['grupo']}, {len(d.get('membros') or [])} membros")
        else:
            linha(None, "nenhuma Steam Family nesta conta",
                  "se voce nao usa Family Share, pode pular esta etapa")
            return

        n = d.get("colecao", 0)
        if n:
            linha(True, f"{n} jogos vem de uma Colecao mapeada pra family",
                  "esta e a fonte boa")
        else:
            linha(None, "nenhuma Colecao mapeada pra family",
                  "siga os passos abaixo - e o unico jeito de ter a lista "
                  "completa")

        linha(True, f"{d.get('appmanifest', 0)} confirmados pelo appmanifest",
              "exato, mas so vale pros jogos instalados")

        ws = d.get("cache") or {}
        por = ws.get("por_membro") or {}
        if por:
            linha(None, f"{d.get('uniao', 0)} jogos no cache dos membros",
                  f"{len(por)} membro(s) cacheados - incompleto, "
                  f"medido em 23% de acerto")
        if ws.get("sem_cache"):
            linha(None, f"{len(ws['sem_cache'])} membro(s) sem cache local",
                  "jogos emprestados so por eles escapam da deducao")

    def concluida(self):
        return any(l["nome"] == "family" and l["appids"]
                   for l in self.sessao.listas)
