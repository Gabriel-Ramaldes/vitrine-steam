"""
Etapa - Family Share.

A parte mais confusa do produto.

A lista dos jogos emprestados NÃO existe no seu computador, e nenhuma
lista que a Steam serve na web separa o que é seu do que é emprestado -
isso foi medido, não suposto (ver docs/family-share.md). O único
caminho que dá a lista completa é deixar o próprio cliente materializá-la
numa Coleção.

Por isso a escolha mora aqui e não na etapa Coleções: antes, o passo a
passo terminava mandando voltar uma tela para marcar uma caixinha. Quem
explica é quem deve deixar fazer.
"""
import traceback
import webbrowser

import tkinter as tk
from tkinter import ttk, messagebox

import core
import tema
from app import Passo
from mapa import Mapa

URL_FAMILY = "https://store.steampowered.com/account/familymanagement"

PASSOS = (
    "Na biblioteca do Steam, clique em STEAM FAMILY na barra lateral.",
    "Selecione tudo: clique no primeiro jogo e Shift+clique no último.",
    "Botão direito → Adicionar a → nova coleção, chamada FAMILY.",
    "Feche o Steam (ele só grava as coleções ao sair).",
    "Volte aqui e marque essa coleção na lista acima.",
)


class Family(Passo):
    titulo = "Family Share"

    @staticmethod
    def precisa(sessao):
        return sessao.tem_steam

    def montar(self):
        self.lido = False
        self.mapa = None
        self.marcas = {}

        ttk.Label(self, text="Family Share", style="Titulo.TLabel"
                  ).pack(anchor="w")
        ttk.Label(self, style="Sub.TLabel", wraplength=760, justify="left",
                  text="O canto verde marca os jogos que estão na sua "
                       "biblioteca por empréstimo de alguém da família."
                  ).pack(anchor="w", pady=(2, 14))

        # ---- a escolha ---------------------------------------------------
        ttk.Label(self, text="Qual Coleção lista os jogos emprestados?",
                  font=(tema.FONTE, 11, "bold")).pack(anchor="w")
        ttk.Label(self, style="Sub.TLabel", wraplength=760, justify="left",
                  text="Marque a Coleção que reúne o que é emprestado. "
                       "Normalmente é uma só. Grava na hora."
                  ).pack(anchor="w", pady=(2, 6))

        self.escolha_cx = ttk.Frame(self, style="Painel.TFrame",
                                    padding=(14, 10))
        self.escolha_cx.pack(fill="x")

        # ---- o que eu encontrei ------------------------------------------
        ttk.Label(self, text="O que eu encontrei",
                  font=(tema.FONTE, 11, "bold")).pack(anchor="w", pady=(16, 4))
        self.estado_cx = ttk.Frame(self, style="Painel.TFrame",
                                   padding=(14, 11))
        self.estado_cx.pack(fill="x")

        # ---- como criar ---------------------------------------------------
        self.criar_bt = ttk.Button(self, text="Ainda não tenho essa Coleção  ▾",
                                   command=self.alternar_passos)
        self.criar_bt.pack(anchor="w", pady=(16, 0))

        self.passos_cx = ttk.Frame(self, style="Painel.TFrame",
                                   padding=(14, 11))
        for n, txt in enumerate(PASSOS, 1):
            f = ttk.Frame(self.passos_cx, style="Painel.TFrame")
            f.pack(fill="x", pady=2)
            ttk.Label(f, text=f"{n}.", style="Painel.Fraco.TLabel", width=3
                      ).pack(side="left", anchor="n")
            ttk.Label(f, text=txt, style="Painel.TLabel", wraplength=660,
                      justify="left").pack(side="left")
        ttk.Label(self.passos_cx, style="Painel.Fraco.TLabel", wraplength=660,
                  justify="left",
                  text="A lista não existe em disco: o cliente pede os appids "
                       "ao servidor e os mantém na memória. Mas ele sabe quais "
                       "são — então peça a ele."
                  ).pack(anchor="w", pady=(8, 0))

        rodape = ttk.Frame(self)
        rodape.pack(fill="x", pady=(14, 0))
        ttk.Button(rodape, text="Conferir de novo", command=self.ler
                   ).pack(side="left")
        ttk.Button(rodape, text="Abrir a página da família",
                   command=lambda: webbrowser.open(URL_FAMILY)
                   ).pack(side="left", padx=8)

        ttk.Label(self, style="Fraco.TLabel", wraplength=760, justify="left",
                  text="Por que não dá para detectar sozinho: as listas que a "
                       "Steam serve na web dizem o que você PODE JOGAR, e "
                       "desde o Steam Families isso inclui o emprestado. "
                       "Medido contra os jogos que o appmanifest prova serem "
                       "emprestados, subtrair essas listas acerta 6%. O "
                       "appmanifest é exato, mas só cobre o que está "
                       "instalado."
                  ).pack(anchor="w", pady=(14, 0))

    # ---- ciclo de vida ---------------------------------------------------

    def ao_entrar(self):
        self.carregar_mapa()
        if not self.lido:
            self.ler()

    def concluida(self):
        return any(l["nome"] == "family" and l["appids"]
                   for l in self.sessao.listas)

    def alternar_passos(self):
        if self.passos_cx.winfo_ismapped():
            self.passos_cx.pack_forget()
            self.criar_bt.configure(text="Ainda não tenho essa Coleção  ▾")
        else:
            self.passos_cx.pack(fill="x", pady=(6, 0), after=self.criar_bt)
            self.criar_bt.configure(text="Ainda não tenho essa Coleção  ▴")

    # ---- a escolha -------------------------------------------------------

    def carregar_mapa(self):
        """
        Relê o mapeamento do disco toda vez que a etapa abre.

        Duas telas mexem no mesmo config. Reler na entrada é o que evita
        marcar aqui em cima de uma versão velha e apagar o que a outra
        gravou.
        """
        s = self.sessao
        if not s.tem_steam:
            return
        try:
            colecoes, _ = core.ler_colecoes(s.steam, s.user)
            config = core.carregar_config(s.caminho_config)
        except Exception:
            self.mapa = None
            return
        self.mapa = Mapa(colecoes, config, s.badges_dir)
        self.desenhar_escolha()

    def desenhar_escolha(self):
        for w in self.escolha_cx.winfo_children():
            w.destroy()
        self.marcas.clear()
        if self.mapa is None:
            ttk.Label(self.escolha_cx, style="Painel.Erro.TLabel",
                      text="não consegui ler as Coleções do Steam"
                      ).pack(anchor="w")
            return

        linhas = [l for l in self.mapa.linhas() if not l["dinamica"]]
        if not linhas:
            ttk.Label(self.escolha_cx, style="Painel.Fraco.TLabel",
                      text="nenhuma Coleção manual nesta conta"
                      ).pack(anchor="w")
            return

        # uma Coleção por linha, em colunas, pra caber sem rolagem
        colunas = 3 if len(linhas) > 8 else 2
        grade = ttk.Frame(self.escolha_cx, style="Painel.TFrame")
        grade.pack(fill="x")
        for c in range(colunas):
            grade.columnconfigure(c, weight=1, uniform="col")

        for i, linha in enumerate(linhas):
            nome = linha["nome"]
            var = tk.BooleanVar(value=linha["family"])
            self.marcas[nome] = var
            rotulo = nome if len(nome) <= 24 else nome[:23] + "…"
            ttk.Checkbutton(
                grade, text=f"{rotulo}  ({linha['jogos']})", variable=var,
                style="Painel.TCheckbutton",
                command=lambda n=nome: self.marcou(n)
            ).grid(row=i // colunas, column=i % colunas, sticky="w",
                   padx=(0, 14), pady=2)

    def marcou(self, nome):
        """Marcar grava na hora: é uma caixinha só, não vale um botão."""
        if self.mapa is None:
            return
        atual = {l["nome"]: l for l in self.mapa.linhas()}[nome]
        self.mapa.definir(nome, status=atual["status"],
                          family=self.marcas[nome].get(),
                          adesivo=atual["adesivo"])
        try:
            self.mapa.salvar(self.sessao.caminho_config)
        except OSError as e:
            messagebox.showerror("Vitrine", f"não consegui gravar:\n{e}")
            return
        marcadas = [n for n, v in self.marcas.items() if v.get()]
        self.app.estado(
            f"family: {', '.join(marcadas)}" if marcadas
            else "nenhuma Coleção marcada como family")
        self.app.recarregar()
        self.ler()

    # ---- diagnóstico -----------------------------------------------------

    def ler(self):
        for w in self.estado_cx.winfo_children():
            w.destroy()
        ttk.Label(self.estado_cx, text="lendo…", style="Painel.Fraco.TLabel"
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
            marca = {True: "ok", False: "✕", None: "!"}[estado]
            f = ttk.Frame(self.estado_cx, style="Painel.TFrame")
            f.pack(fill="x", pady=1)
            ttk.Label(f, text=marca, style=estilo, width=4).pack(side="left")
            ttk.Label(f, text=texto, style="Painel.TLabel").pack(side="left")
            if detalhe:
                ttk.Label(f, text=detalhe, style="Painel.Fraco.TLabel",
                          wraplength=430, justify="left"
                          ).pack(side="left", padx=8)

        if d.get("erro"):
            linha(False, "não consegui ler", d["erro"].splitlines()[-1][:80])
            return

        if d.get("grupo"):
            linha(True, "Steam Family configurada",
                  f"grupo {d['grupo']}, {len(d.get('membros') or [])} membros")
        else:
            linha(None, "nenhuma Steam Family nesta conta",
                  "se você não usa Family Share, pode pular esta etapa")
            return

        n = d.get("colecao", 0)
        if n:
            linha(True, f"{n} jogos vêm da Coleção que você marcou",
                  "esta é a fonte boa")
        else:
            linha(None, "nenhuma Coleção marcada acima",
                  "é o único jeito de ter a lista completa — se você ainda "
                  "não tem essa Coleção, o botão abaixo explica como criar")

        linha(True, f"{d.get('appmanifest', 0)} confirmados pelo appmanifest",
              "exato, mas só vale para os jogos instalados")

        ws = d.get("cache") or {}
        por = ws.get("por_membro") or {}
        if por:
            linha(None, f"{d.get('uniao', 0)} jogos no cache dos membros",
                  f"{len(por)} membro(s) em cache — incompleto, "
                  f"medido em 23% de acerto")
        if ws.get("sem_cache"):
            linha(None, f"{len(ws['sem_cache'])} membro(s) sem cache local",
                  "jogos emprestados só por eles escapam da dedução")
