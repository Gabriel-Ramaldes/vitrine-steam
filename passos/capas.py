"""
Etapa - Capas.

Mostra os jogos cuja capa esta ruim, diz por que, e deixa trocar: ou por
uma arte da SteamGridDB, ou por um arquivo seu.

Convertida de vitrine_galeria.py. O conteudo e o mesmo; o que saiu foi o
que a casca passou a fazer: tema, agenda, fila de recados entre threads e
descoberta do Steam (que agora vem da Sessao).
"""
import os
import queue
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import core
import tema
import galeria as G
from app import Passo

CARTAO_W = 150


class Capas(Passo):
    titulo = "Capas"

    @staticmethod
    def precisa(sessao):
        return sessao.tem_steam

    def montar(self):
        self.parar = threading.Event()
        self.trabalhando = False
        self.itens = []
        self.selecionado = None
        self.imagens = {}
        self._monta()
        self.sessao.ao_mudar(lambda s: self._do_estado())

    def ao_entrar(self):
        self._do_estado()

    def _do_estado(self):
        """Pega da Sessao o que a tela antiga descobria sozinha."""
        s = self.sessao
        self.steam, self.grid, self.user = s.steam, s.grid, s.user
        self.config_json = s.config
        self.sgdb_key = s.sgdb_key
        if self.sgdb_key:
            self.var_chave.set(self.sgdb_key)
            self._chave_estado("chave carregada - clique em Salvar chave "
                               "para conferir", "Fraco.TLabel")
        else:
            self._chave_estado("sem chave: a busca de artes fica desligada",
                               "Alerta.TLabel")

    def ao_sair(self):
        if self.trabalhando:
            if not messagebox.askokcancel(
                    "Vitrine", "A varredura ainda esta rodando. Sair e parar?"):
                return False
            self.parar.set()
        return True

    def concluida(self):
        return bool(self.itens) is False and self.estado_varrido()

    def estado_varrido(self):
        return getattr(self, "_varreu", False)

    def _monta(self):
        topo = ttk.Frame(self, padding=(16, 14, 16, 8))
        topo.pack(fill="x")
        ttk.Label(topo, text="Capas problematicas",
                  style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(topo, style="Fraco.TLabel",
                  text="Jogos sem capa propria, com capa fabricada pela Steam "
                       "ou com arte fraca. Escolha uma alternativa; ela vai "
                       "pra capas/ e passa a valer sempre.").pack(anchor="w")

        chave = ttk.Frame(self, padding=(16, 4, 16, 4))
        chave.pack(fill="x")
        ttk.Label(chave, text="Chave da SteamGridDB:").pack(side="left")
        self.var_chave = tk.StringVar()
        self.ent_chave = ttk.Entry(chave, textvariable=self.var_chave,
                                   show="\u2022", width=40)
        self.ent_chave.pack(side="left", padx=8)
        self.var_ver = tk.BooleanVar(value=False)
        ttk.Checkbutton(chave, text="mostrar", variable=self.var_ver,
                        command=self._ver_chave).pack(side="left")
        ttk.Button(chave, text="Salvar chave",
                   command=self.salvar_chave).pack(side="left", padx=8)
        ttk.Button(chave, text="Pegar a minha",
                   command=self.abrir_chave).pack(side="left")
        self.lb_chave = ttk.Label(chave, style="Fraco.TLabel", text="")
        self.lb_chave.pack(side="left", padx=10)

        barra = ttk.Frame(self, padding=(16, 4, 16, 8))
        barra.pack(fill="x")
        self.bt_varrer = ttk.Button(barra, text="Varrer biblioteca",
                                    style="Forte.TButton", command=self.varrer)
        self.bt_varrer.pack(side="left")
        self.bt_parar = ttk.Button(barra, text="Parar", command=self.cancelar,
                                   state="disabled")
        self.bt_parar.pack(side="left", padx=8)
        self.prog = ttk.Progressbar(barra, mode="determinate", length=260)
        self.prog.pack(side="left", padx=12)
        self.lb_prog = ttk.Label(barra, style="Fraco.TLabel", text="")
        self.lb_prog.pack(side="left")

        corpo = ttk.Frame(self, padding=(16, 0, 16, 0))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=2)
        corpo.columnconfigure(1, weight=3)
        corpo.rowconfigure(0, weight=1)

        # --- esquerda: lista dos problemas ---
        esq = ttk.Frame(corpo, style="Painel.TFrame")
        esq.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.canvas = tk.Canvas(esq, bg=tema.PAINEL, highlightthickness=0)
        rol = ttk.Scrollbar(esq, orient="vertical", command=self.canvas.yview)
        self.lista = ttk.Frame(self.canvas, style="Painel.TFrame")
        self.lista.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.jan = self.canvas.create_window((0, 0), window=self.lista,
                                             anchor="nw")
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self.jan,
                                                             width=e.width))
        self.canvas.configure(yscrollcommand=rol.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        rol.pack(side="right", fill="y")
        for alvo in (self.canvas, self.lista):
            for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                alvo.bind(ev, self._roda)

        # --- direita: o jogo escolhido e as alternativas ---
        dir_ = ttk.Frame(corpo, style="Painel.TFrame", padding=12)
        dir_.grid(row=0, column=1, sticky="nsew")

        # a capa de hoje fica ao lado do titulo: sem ela na frente, escolher
        # entre as alternativas e chute
        cabeca = ttk.Frame(dir_, style="Painel.TFrame")
        cabeca.pack(fill="x")
        atual = ttk.Frame(cabeca, style="Cartao.TFrame", padding=4)
        atual.pack(side="left", padx=(0, 12))
        self.lb_atual = ttk.Label(atual, background=tema.CARTAO,
                                  style="Cartao.Fraco.TLabel",
                                  text="sem\ncapa", justify="center",
                                  width=16, anchor="center")
        self.lb_atual.pack()
        ttk.Label(atual, text="como esta hoje", style="Cartao.Fraco.TLabel",
                  anchor="center").pack(fill="x")

        texto = ttk.Frame(cabeca, style="Painel.TFrame")
        texto.pack(side="left", fill="both", expand=True)
        self.lb_jogo = ttk.Label(texto, text="Selecione um jogo a esquerda",
                                 background=tema.PAINEL,
                                 font=("Segoe UI", 11, "bold"))
        self.lb_jogo.pack(anchor="w")
        self.lb_motivo = ttk.Label(texto, style="Fraco.TLabel",
                                   background=tema.PAINEL, wraplength=420,
                                   justify="left", text="")
        self.lb_motivo.pack(anchor="w", pady=(2, 8))

        acoes = ttk.Frame(texto, style="Painel.TFrame")
        acoes.pack(fill="x", pady=(0, 8))
        self.bt_sgdb = ttk.Button(acoes, text="Buscar na SteamGridDB",
                                  command=self.buscar, state="disabled")
        self.bt_sgdb.pack(side="left")
        self.bt_arquivo = ttk.Button(acoes, text="Usar arquivo meu...",
                                     command=self.escolher_arquivo,
                                     state="disabled")
        self.bt_arquivo.pack(side="left", padx=8)
        self.bt_site = ttk.Button(acoes, text="Abrir no site",
                                  command=self.abrir_site, state="disabled")
        self.bt_site.pack(side="left")

        ttk.Label(dir_, text="alternativas", style="Fraco.TLabel",
                  background=tema.PAINEL).pack(anchor="w", pady=(8, 2))
        cx = ttk.Frame(dir_, style="Painel.TFrame")
        cx.pack(fill="both", expand=True)
        self.canvas2 = tk.Canvas(cx, bg=tema.PAINEL, highlightthickness=0)
        rol2 = ttk.Scrollbar(cx, orient="vertical", command=self.canvas2.yview)
        self.cands = ttk.Frame(self.canvas2, style="Painel.TFrame")
        self.cands.bind("<Configure>", lambda e: self.canvas2.configure(
            scrollregion=self.canvas2.bbox("all")))
        self.jan2 = self.canvas2.create_window((0, 0), window=self.cands,
                                               anchor="nw")
        self.canvas2.bind("<Configure>",
                          lambda e: self.canvas2.itemconfigure(self.jan2,
                                                               width=e.width))
        self.canvas2.configure(yscrollcommand=rol2.set)
        self.canvas2.pack(side="left", fill="both", expand=True)
        rol2.pack(side="right", fill="y")
        for alvo in (self.canvas2, self.cands):
            for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                alvo.bind(ev, self._roda2)


    def _roda(self, e):
        self.canvas.yview_scroll(self._delta(e), "units")

    def _roda2(self, e):
        self.canvas2.yview_scroll(self._delta(e), "units")

    @staticmethod
    def _delta(e):
        if getattr(e, "num", 0) == 5:
            return 1
        if getattr(e, "num", 0) == 4:
            return -1
        return -1 if e.delta > 0 else 1

    # ---- trabalho em segundo plano --------------------------------------

    def _ver_chave(self):
        self.ent_chave.configure(show="" if self.var_ver.get() else "\u2022")

    def _chave_estado(self, txt, estilo="Fraco.TLabel"):
        self.lb_chave.configure(text=txt, style=estilo)

    def abrir_chave(self):
        import webbrowser
        webbrowser.open("https://www.steamgriddb.com/profile/preferences/api")
        self._chave_estado("copie a chave do site e cole aqui")

    def salvar_chave(self):
        try:
            caminho = G.gravar_chave(self.var_chave.get())
        except ValueError as e:
            self._chave_estado(str(e), "Alerta.TLabel")
            return
        chave = G.ler_chave(caminho)
        self.sgdb_key = chave
        self.sessao.sgdb_key = chave
        self.var_chave.set(chave)
        self._chave_estado("conferindo com a SteamGridDB...")
        if self.selecionado:
            self.bt_sgdb.configure(state="normal")

        def trabalho():
            ok, msg = core.validar_chave_sgdb(chave)
            def pronto():
                if ok:
                    self._chave_estado(f"chave valida, salva em "
                                       f"{caminho.name}", "Ok.TLabel")
                    if self.selecionado:
                        self.buscar()
                else:
                    self._chave_estado(msg.splitlines()[0], "Alerta.TLabel")
            self.app.na_janela(pronto)

        self.app.em_thread(trabalho)

    # ---- varredura -------------------------------------------------------

    def varrer(self):
        if self.trabalhando:
            return
        self.trabalhando = True
        self.parar.clear()
        self.bt_varrer.configure(state="disabled")
        self.bt_parar.configure(state="normal")
        for w in self.lista.winfo_children():
            w.destroy()
        self.itens = []
        self.estado("lendo as colecoes...")

        def trabalho():
            try:
                colecoes, _ = core.ler_colecoes(self.steam, self.user)
                universo = set()
                for c in colecoes:
                    if not c["dinamica"]:
                        universo.update(c["appids"])
                for padrao in ("*p.png", "*p.jpg"):
                    for f in self.grid.glob(padrao):
                        if f.stem[:-1].isdigit():
                            universo.add(int(f.stem[:-1]))
                appids = sorted(universo)
                aplicados = set(core.load_state().get("aplicados", []))

                def progresso(i, total, appid):
                    if i % 10 == 0 or i == total:
                        self.app.na_janela(lambda: self._progresso(i, total))

                itens = G.varrer(appids, self.steam, self.grid, aplicados,
                                 progresso=progresso,
                                 parar=self.parar.is_set)
                G.nomear(itens)
                self.app.na_janela(lambda: self._mostrar(itens))
            except Exception:
                tb = traceback.format_exc(limit=3)
                self.app.na_janela(lambda: self._falhou(tb))

        self.app.em_thread(trabalho)

    def _progresso(self, i, total):
        self.prog.configure(maximum=total, value=i)
        self.lb_prog.configure(text=f"{i}/{total}")

    def _falhou(self, tb):
        self.trabalhando = False
        self.bt_varrer.configure(state="normal")
        self.bt_parar.configure(state="disabled")
        messagebox.showerror("Vitrine", tb)

    def cancelar(self):
        self.parar.set()
        self.estado("parando...")

    def _mostrar(self, itens):
        self.trabalhando = False
        self._varreu = True
        self.bt_varrer.configure(state="normal")
        self.bt_parar.configure(state="disabled")
        self.itens = itens
        for w in self.lista.winfo_children():
            w.destroy()
        if not itens:
            ttk.Label(self.lista, text="Nenhuma capa problematica. ",
                      background=tema.PAINEL, style="Ok.TLabel",
                      padding=12).pack(anchor="w")
            self.estado("biblioteca limpa")
            return
        porque = {}
        for it in itens:
            porque[it["motivo"]] = porque.get(it["motivo"], 0) + 1
        for i, it in enumerate(itens):
            self._linha(i, it)
        resumo = ", ".join(f"{v} {k}" for k, v in sorted(porque.items()))
        self.estado(f"{len(itens)} com problema - {resumo}")

    def _linha(self, i, it):
        f = ttk.Frame(self.lista, style="Painel.TFrame", padding=(10, 5))
        f.pack(fill="x")
        nome = it.get("nome") or f"appid {it['appid']}"
        txt = nome if len(nome) <= 38 else nome[:37] + "…"
        lb = ttk.Label(f, text=txt, background=tema.PAINEL, anchor="w")
        lb.pack(side="left", fill="x", expand=True)
        ttk.Label(f, text=it["motivo"], background=tema.PAINEL,
                  style="Fraco.TLabel").pack(side="right")
        for w in (f, lb):
            w.bind("<Button-1>", lambda e, x=it: self.selecionar(x))
            w.configure(cursor="hand2")

    # ---- selecao e candidatos -------------------------------------------

    def selecionar(self, it):
        self.selecionado = it
        nome = it.get("nome") or f"appid {it['appid']}"
        self.lb_jogo.configure(text=f"{nome}  ({it['appid']})")
        self.lb_motivo.configure(
            text=f"{it['motivo']}: {G.EXPLICACAO.get(it['motivo'], '')}")
        for b in (self.bt_arquivo, self.bt_site):
            b.configure(state="normal")
        self.bt_sgdb.configure(state="normal" if self.sgdb_key else "disabled")
        for w in self.cands.winfo_children():
            w.destroy()
        self._carregar_atual(it)
        if self.sgdb_key:
            self.buscar()
        else:
            ttk.Label(self.cands, style="Alerta.TLabel", background=tema.PAINEL,
                      wraplength=480, justify="left",
                      text="Sem chave da SteamGridDB nao da pra buscar artes. "
                           "Cole a chave la em cima, ou use 'Usar arquivo "
                           "meu...' com uma imagem sua."
                      ).pack(anchor="w", pady=8)

    def _carregar_atual(self, it):
        """A capa de hoje, carregada em segundo plano."""
        self.lb_atual.configure(image="", text="carregando...")
        appid = it["appid"]

        def trabalho():
            dados = None
            try:
                dados = G.capa_atual(it, self.steam, self.grid)
            except Exception:
                dados = None
            b64 = None
            if dados:
                try:
                    b64 = G.miniatura(dados, 150)
                except Exception:
                    b64 = None
            self.app.na_janela(lambda: self._mostrar_atual(appid, b64))

        self.app.em_thread(trabalho)

    def _mostrar_atual(self, appid, b64):
        if not self.selecionado or self.selecionado["appid"] != appid:
            return
        if not b64:
            self.lb_atual.configure(image="", text="nao existe\ncapa hoje")
            return
        img = tk.PhotoImage(data=b64)
        self.imagens[("atual", appid)] = img
        self.lb_atual.configure(image=img, text="")

    def buscar(self):
        it = self.selecionado
        if not it or not self.sgdb_key:
            return
        for w in self.cands.winfo_children():
            w.destroy()
        ttk.Label(self.cands, text="procurando...", background=tema.PAINEL,
                  style="Fraco.TLabel").pack(anchor="w", pady=8)
        appid = it["appid"]

        def trabalho():
            lista, erro = G.candidatos(appid, self.sgdb_key)
            miniaturas = []
            for c in lista[:12]:
                try:
                    dados = core.http_get(c["thumb"], timeout=15)
                    miniaturas.append((c, G.miniatura(dados, CARTAO_W)))
                except Exception:
                    continue
            self.app.na_janela(lambda: self._mostrar_candidatos(
                appid, miniaturas, erro))

        self.app.em_thread(trabalho)

    def _mostrar_candidatos(self, appid, miniaturas, erro):
        if not self.selecionado or self.selecionado["appid"] != appid:
            return                       # o usuario ja clicou em outro jogo
        for w in self.cands.winfo_children():
            w.destroy()
        if erro:
            ttk.Label(self.cands, text=f"SteamGridDB: {erro}",
                      background=tema.PAINEL, style="Alerta.TLabel",
                      wraplength=520, justify="left").pack(anchor="w", pady=8)
            return
        if not miniaturas:
            ttk.Label(self.cands, text="Nenhuma arte utilizavel voltou.",
                      background=tema.PAINEL, style="Fraco.TLabel"
                      ).pack(anchor="w", pady=8)
            return
        colunas = 3
        for i, (c, b64) in enumerate(miniaturas):
            img = tk.PhotoImage(data=b64)
            self.imagens[(appid, i)] = img          # segura a referencia
            cartao = ttk.Frame(self.cands, style="Cartao.TFrame", padding=6)
            cartao.grid(row=i // colunas, column=i % colunas, padx=6, pady=6,
                        sticky="n")
            lb = ttk.Label(cartao, image=img, background=tema.CARTAO)
            lb.pack()
            dims = (f"{c['largura']}x{c['altura']}"
                    if c.get("largura") else "?")
            ttk.Label(cartao, text=f"{dims}  ★{c['score']}",
                      style="Cartao.Fraco.TLabel").pack(anchor="w")
            if c.get("autor"):
                ttk.Label(cartao, text=c["autor"][:18],
                          style="Cartao.Fraco.TLabel").pack(anchor="w")
            ttk.Button(cartao, text="Usar esta",
                       command=lambda u=c["url"]: self.adotar(u)).pack(
                fill="x", pady=(4, 0))
            for w in (cartao, lb):
                w.bind("<Double-Button-1>",
                       lambda e, u=c["url"]: self.adotar(u))

    # ---- adocao ----------------------------------------------------------

    def adotar(self, url):
        it = self.selecionado
        if not it:
            return
        appid = it["appid"]
        self.estado("baixando...")

        def trabalho():
            try:
                destino = G.adotar_url(appid, url)
            except Exception as e:
                msg = str(e)
                self.app.na_janela(lambda: self.estado(
                    f"nao deu: {msg}", "Alerta.TLabel"))
                return
            self.app.na_janela(lambda: self._adotou(appid, destino))

        self.app.em_thread(trabalho)

    def escolher_arquivo(self):
        it = self.selecionado
        if not it:
            return
        caminho = filedialog.askopenfilename(
            title=f"Capa para {it.get('nome') or it['appid']}",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp"),
                       ("Todos", "*.*")])
        if not caminho:
            return
        try:
            destino = G.adotar_arquivo(it["appid"], caminho)
        except Exception as e:
            messagebox.showerror("Vitrine", str(e))
            return
        self._adotou(it["appid"], destino)

    def _adotou(self, appid, destino):
        self.itens = [i for i in self.itens if i["appid"] != appid]
        self.selecionado = None
        for w in self.lista.winfo_children():
            w.destroy()
        for i, it in enumerate(self.itens):
            self._linha(i, it)
        for w in self.cands.winfo_children():
            w.destroy()
        self.lb_jogo.configure(text="Selecione um jogo a esquerda")
        self.lb_motivo.configure(text="")
        self.lb_atual.configure(image="", text="sem\ncapa")
        for b in (self.bt_sgdb, self.bt_arquivo, self.bt_site):
            b.configure(state="disabled")
        self.estado(f"capa salva em {destino.parent.name}/{destino.name} - "
                    f"faltam {len(self.itens)}", "Ok.TLabel")
        self.app.desenhar_barra()

    def abrir_site(self):
        if not self.selecionado:
            return
        import webbrowser
        webbrowser.open(G.link_sgdb(self.selecionado["appid"]))

    # ---- rodape ----------------------------------------------------------

    def estado(self, txt, estilo="Fraco.TLabel"):
        # um rodape so, o da casca
        self.app.estado(txt)
