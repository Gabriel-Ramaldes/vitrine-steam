"""
Etapa - Colecoes.

Liga cada Colecao do Steam a um status, sem editar o config.json a mao.
A regra toda mora em mapa.py; aqui so tem tkinter.

Convertida de vitrine_gui.py: o conteudo e o mesmo, o que mudou e quem e
dono da janela. Antes era um tk.Tk com mainloop proprio; agora e um
ttk.Frame dentro da casca, que cuida do tema, do agendamento e das
threads.
"""
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

import core
import tema
from app import Passo
from mapa import Mapa, NADA, STATUS, ADESIVOS, DESCRICAO


class Colecoes(Passo):
    titulo = "Coleções"

    @staticmethod
    def precisa(sessao):
        return sessao.tem_steam

    def montar(self):
        self.mapa = None
        self.caminho_config = self.sessao.caminho_config
        self.combos = {}
        self._monta()
        self.app.agendar(60, self.carregar)

    def ao_entrar(self):
        # a etapa Family grava no mesmo config. Reler na entrada, menos
        # quando ha edicao em curso aqui - essa ninguem pode atropelar.
        if self.mapa is None or not self.mapa.sujo:
            self.carregar()

    def ao_sair(self):
        if self.mapa is not None and self.mapa.sujo:
            return messagebox.askokcancel(
                "Vitrine", "Ha alterações não salvas no mapeamento.\n"
                           "Sair sem salvar?")
        return True

    def concluida(self):
        return bool(self.sessao.tem_listas)

    def _monta(self):
        topo = ttk.Frame(self, padding=(16, 14, 16, 8))
        topo.pack(fill="x")
        ttk.Label(topo, text="Mapear coleções", style="Titulo.TLabel").pack(anchor="w")
        self.lb_sub = ttk.Label(
            topo, style="Fraco.TLabel", wraplength=860, justify="left",
            text="Status: um por jogo, no canto inferior da capa.    "
                 "Adesivo: FREE ou DEMO.    Nada é gravado até você salvar.\n"
                 "Os jogos emprestados da família ficam na etapa seguinte.")
        self.lb_sub.pack(anchor="w", pady=(2, 0))

        corpo = ttk.Frame(self, padding=(16, 0, 16, 0))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=4)
        corpo.columnconfigure(1, weight=0, minsize=200)
        corpo.rowconfigure(0, weight=1)

        # --- tabela de colecoes, com rolagem ---
        caixa = ttk.Frame(corpo, style="Painel.TFrame")
        caixa.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.canvas = tk.Canvas(caixa, bg=tema.PAINEL, highlightthickness=0)
        rol = ttk.Scrollbar(caixa, orient="vertical", command=self.canvas.yview)
        self.lista = ttk.Frame(self.canvas, style="Painel.TFrame")
        self.lista.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.janela_lista = self.canvas.create_window((0, 0), window=self.lista,
                                                      anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self.janela_lista, width=e.width))
        self.canvas.configure(yscrollcommand=rol.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        rol.pack(side="right", fill="y")
        for alvo in (self.canvas, self.lista):
            alvo.bind("<MouseWheel>", self._roda)
            alvo.bind("<Button-4>", self._roda)
            alvo.bind("<Button-5>", self._roda)

        # --- legenda ---
        # ocupa o lugar que era da hierarquia. A ordem saiu de editavel
        # porque nunca foi de verdade: encaixes diferentes nao disputam
        # entre si. O que falta aqui e saber o que cada status quer dizer.
        lado = ttk.Frame(corpo)
        lado.grid(row=0, column=1, sticky="nsew")
        ttk.Label(lado, text="O que cada um quer dizer").pack(anchor="w")
        cx = ttk.Frame(lado, style="Painel.TFrame", padding=(10, 8))
        cx.pack(fill="both", expand=True, pady=(4, 0))
        for nome in STATUS:
            f = ttk.Frame(cx, style="Painel.TFrame")
            f.pack(fill="x", pady=(0, 5))
            ttk.Label(f, text=nome, style="Painel.TLabel",
                      font=(tema.FONTE, 9, "bold")).pack(anchor="w")
            ttk.Label(f, text=DESCRICAO.get(nome, ""), style="Painel.Fraco.TLabel",
                      wraplength=190, justify="left").pack(anchor="w")
        ttk.Label(cx, text="\u2014" * 3, style="Painel.Fraco.TLabel"
                  ).pack(anchor="w", pady=(2, 4))
        ttk.Label(cx, style="Painel.Fraco.TLabel", wraplength=190,
                  justify="left",
                  text="Um jogo em duas coleções de status fica com o que "
                       "estiver mais acima nesta lista.").pack(anchor="w")
        ttk.Label(cx, style="Painel.Fraco.TLabel", wraplength=190,
                  justify="left", text="family e adesivo não disputam: são "
                                       "lugares próprios na capa."
                  ).pack(anchor="w", pady=(5, 0))

        # --- avisos ---
        self.avisos = tk.Text(self, height=3, bg=tema.PAINEL, fg=tema.ALERTA,
                              borderwidth=0, highlightthickness=0, wrap="word",
                              font=("Segoe UI", 9))
        self.avisos.pack(fill="x", padx=16, pady=(10, 0))
        self.avisos.configure(state="disabled")

        # --- rodape ---
        pe = ttk.Frame(self, padding=(16, 10, 16, 14))
        pe.pack(fill="x")
        ttk.Button(pe, text="Salvar", style="Forte.TButton",
                   command=self.salvar).pack(side="right")
        ttk.Button(pe, text="Recarregar",
                   command=self.carregar).pack(side="right", padx=8)

    def _roda(self, e):
        d = 1 if getattr(e, "num", 0) == 5 else -1 if getattr(e, "num", 0) == 4 \
            else (-1 if e.delta > 0 else 1)
        self.canvas.yview_scroll(d, "units")

    # ---- dados ----------------------------------------------------------

    def carregar(self):
        self.estado("lendo as coleções do Steam...")
        self.update_idletasks()
        try:
            steam = core.find_steam_path()
            config = core.carregar_config(self.caminho_config)
            user = config.get("user")
            grid = core.find_grid_dir(steam, user)
            user = user or grid.parent.parent.name
            colecoes, avisos = core.ler_colecoes(steam, user)
        except core.ErroCore as e:
            self.estado("não consegui ler o Steam")
            messagebox.showerror("Vitrine", str(e))
            return
        except Exception:
            self.estado("erro inesperado")
            messagebox.showerror("Vitrine", traceback.format_exc(limit=3))
            return

        self.mapa = Mapa(colecoes, config, core.BASE_DIR / "badges")
        self.extra = list(avisos)
        self.desenhar()
        self.estado(f"{len(colecoes)} coleções - Steam em {steam}")

    def desenhar(self):
        for w in self.lista.winfo_children():
            w.destroy()
        self.combos.clear()
        op_status = [NADA] + list(STATUS)
        op_adesivo = [NADA] + list(ADESIVOS)

        # Tres encaixes independentes, uma coluna cada. O vocabulario e
        # fechado: nao existe campo livre pra inventar status.
        self.lista.columnconfigure(0, weight=1, minsize=230)
        self.lista.columnconfigure(1, minsize=52)
        self.lista.columnconfigure(2, minsize=150)
        self.lista.columnconfigure(3, minsize=130)

        cabecalho = ((0, "coleção", "w"), (1, "jogos", "e"),
                     (2, "status", "w"), (3, "adesivo", "w"))
        for col, txt, anc in cabecalho:
            ttk.Label(self.lista, text=txt, style="Fraco.TLabel",
                      background=tema.PAINEL, anchor=anc).grid(
                row=0, column=col, sticky="ew",
                padx=(12 if col == 0 else 6, 6), pady=(10, 6))

        for i, linha in enumerate(self.mapa.linhas(), start=1):
            nome = linha["nome"]
            txt = nome if len(nome) <= 26 else nome[:25] + "\u2026"
            ttk.Label(self.lista, text=txt, background=tema.PAINEL,
                      anchor="w").grid(row=i, column=0, sticky="ew",
                                       padx=(12, 6), pady=2)
            ttk.Label(self.lista, text=str(linha["jogos"]),
                      background=tema.PAINEL, style="Fraco.TLabel",
                      anchor="e").grid(row=i, column=1, sticky="ew",
                                       padx=6, pady=2)

            if linha["dinamica"]:
                ttk.Label(self.lista, text="dinâmica — sem lista de jogos",
                          background=tema.PAINEL, style="Fraco.TLabel",
                          anchor="w").grid(row=i, column=2, columnspan=2,
                                           sticky="ew", padx=6, pady=2)
                continue

            st = tk.StringVar(value=linha["status"] or NADA)
            ad = tk.StringVar(value=linha["adesivo"] or NADA)
            # o family e escolhido na etapa Family; aqui so viaja junto
            # pra nao ser apagado quando esta tela salvar
            self.combos[nome] = (st, linha["family"], ad)

            cb = ttk.Combobox(self.lista, textvariable=st, values=op_status,
                              state="readonly", width=13,
                              style="Vazio.TCombobox" if not linha["status"]
                              else "TCombobox")
            cb.grid(row=i, column=2, sticky="ew", padx=6, pady=2)

            cb2 = ttk.Combobox(self.lista, textvariable=ad, values=op_adesivo,
                               state="readonly", width=11,
                               style="Vazio.TCombobox" if not linha["adesivo"]
                               else "TCombobox")
            cb2.grid(row=i, column=3, sticky="ew", padx=(6, 12), pady=2)

            for w in (cb, cb2):
                w.bind("<<ComboboxSelected>>",
                       lambda e, n=nome, a=cb, b=cb2: self.mudou(n, a, b))

            if linha["legado"]:
                ttk.Label(self.lista, text="!", background=tema.PAINEL,
                          style="Alerta.TLabel").grid(row=i, column=1,
                                                      sticky="w", padx=2)

        self.desenhar_avisos()

    def desenhar_avisos(self):
        linhas = list(getattr(self, "extra", [])) + self.mapa.avisos()
        self.avisos.configure(state="normal")
        self.avisos.delete("1.0", "end")
        if linhas:
            self.avisos.insert("1.0", "\n".join(f"• {a}" for a in linhas))
        else:
            self.avisos.insert("1.0", "Nenhum problema encontrado.")
        self.avisos.configure(state="disabled")

    # ---- acoes ----------------------------------------------------------

    def mudou(self, nome, cb, cb2):
        st, family, ad = self.combos[nome]
        status = st.get() if st.get() != NADA else None
        adesivo = ad.get() if ad.get() != NADA else None
        # combo vazio fica apagado, pra vista bater o que esta e o que nao esta
        cb.configure(style="Vazio.TCombobox" if status is None else "TCombobox")
        cb2.configure(style="Vazio.TCombobox" if adesivo is None else "TCombobox")
        self.mapa.definir(nome, status=status, family=family,
                          adesivo=adesivo)
        self.desenhar_avisos()
        self.estado("alterações não salvas", alerta=True)

    def salvar(self):
        if self.mapa is None:
            return
        podadas = self.mapa.podadas()
        try:
            caminho = self.mapa.salvar(self.caminho_config)
        except OSError as e:
            messagebox.showerror("Vitrine", f"Não consegui gravar:\n{e}")
            return
        extra = ""
        if podadas:
            extra = (f" - {podadas} coleção(oes) que não existem mais no "
                     f"Steam sairam do arquivo")
        self.estado(f"salvo em {caminho.name} (o anterior virou "
                    f"{caminho.name}.bak){extra}")
        self.desenhar()
        # o mapeamento mudou: as etapas seguintes precisam reler
        self.app.recarregar()

    def estado(self, txt, alerta=False):
        # um rodape so, o da casca - dois contadores divergiriam
        self.app.estado(txt)
