"""
A base das etapas Simular e Aplicar.

As duas sao a mesma operacao - rodar.executar(), o mesmo que a CLI usa -
com dry_run diferente. O que muda e a conducao: simular escreve em
preview/ e nao toca no Steam; aplicar escreve na biblioteca e so libera
depois que houve uma simulacao.
"""
import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

import core
import tema
import rodar
from app import Passo, RelatorioTela


def steam_rodando():
    """
    True/False/None. None = nao da pra saber nesta plataforma.

    Importa porque o cliente reescreve o grid ao fechar: aplicar com ele
    aberto costuma dar a impressao de que nada funcionou.
    """
    try:
        if os.name == "nt":
            saida = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq steam.exe", "/NH"],
                capture_output=True, text=True, timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return "steam.exe" in (saida.stdout or "").lower()
        saida = subprocess.run(["pgrep", "-x", "steam"],
                               capture_output=True, timeout=8)
        return saida.returncode == 0
    except Exception:
        return None


class BaseRodar(Passo):
    """
    O que Simular e Aplicar tem em comum: a lista de verificacao, o log,
    a barra de progresso e a chamada a rodar.executar().

    As duas sao a mesma operacao com dry_run diferente. Separa-las em
    etapas e uma decisao de conducao - simular primeiro, conferir, so
    entao aplicar - e nao de comportamento.
    """
    simular = True

    @staticmethod
    def precisa(sessao):
        return sessao.tem_steam and sessao.tem_listas

    def montar(self):
        self.parar = threading.Event()
        self.trabalhando = False
        self.pronto = False
        self.ultimo = None
        self._monta()
        self.sessao.ao_mudar(lambda s: self.conferir())

    def ao_entrar(self):
        self.conferir()

    def ao_sair(self):
        if self.trabalhando:
            if not messagebox.askokcancel(
                    "Vitrine", "Ainda está rodando. Sair e parar?"):
                return False
            self.parar.set()
        return True

    def concluida(self):
        return bool(self.ultimo)

    # ---- o que vem da Sessao --------------------------------------------

    @property
    def steam(self):
        return self.sessao.steam

    @property
    def grid(self):
        return self.sessao.grid

    @property
    def user(self):
        return self.sessao.user

    @property
    def listas(self):
        return self.sessao.listas

    @property
    def moldura(self):
        return self.sessao.moldura

    def conferir(self):
        """A lista de verificacao, agora vinda da Sessao."""
        for w in self.checklist.winfo_children():
            w.destroy()
        itens = self.sessao.conferir()
        self.pronto = not any(ok is False for ok, _, _ in itens)
        for ok, texto, detalhe in itens:
            estilo = {True: "Painel.Ok.TLabel", False: "Painel.Erro.TLabel",
                      None: "Painel.Alerta.TLabel"}[ok]
            marca = {True: "ok ", False: "X  ", None: "!  "}[ok]
            f = ttk.Frame(self.checklist, style="Painel.TFrame")
            f.pack(fill="x", pady=1)
            ttk.Label(f, text=marca, style=estilo, width=4).pack(side="left")
            ttk.Label(f, text=texto, style="Painel.TLabel").pack(side="left")
            if detalhe:
                ttk.Label(f, text=detalhe, style="Painel.Fraco.TLabel"
                          ).pack(side="left", padx=8)
        r = steam_rodando()
        if r is True:
            f = ttk.Frame(self.checklist, style="Painel.TFrame")
            f.pack(fill="x", pady=1)
            ttk.Label(f, text="!  ", style="Painel.Alerta.TLabel", width=4
                      ).pack(side="left")
            ttk.Label(f, text="o Steam está aberto", style="Painel.TLabel"
                      ).pack(side="left")
            ttk.Label(f, text="feche antes de aplicar - ele reescreve o grid "
                              "ao sair", style="Painel.Fraco.TLabel"
                      ).pack(side="left", padx=8)
        self.bt_acao.configure(state="normal" if self.liberado() else "disabled")

    def _enviar(self, msg):
        """
        Recado do motor -> fila da casca.

        A casca aceita funcoes, nao tuplas: traduzir aqui mantem ela
        generica e deixa o formato do recado junto de quem o entende.
        """
        self.app.na_janela(lambda m=msg: self._recado(m))

    def _recado(self, msg):
        tipo, dado, tag = msg
        if tipo == "linha":
            self._escrever(dado, tag)
        elif tipo == "item":
            i, total, appid, rotulo, origem, extra = dado
            self.prog.configure(maximum=total, value=i)
            self.lb_prog.configure(text=f"{i}/{total}")
            self._escrever(f"[{i}/{total}] {appid}: {rotulo}"
                           f"  (capa via {origem}){extra}", "ok")
        elif tipo == "fim":
            self._terminou(dado)
        elif tipo == "fn":
            dado()

    def montar_acoes(self, barra):
        """A subclasse acrescenta os proprios botoes."""

    def liberado(self):
        """Se a acao principal pode rodar agora."""
        return self.pronto

    def acionar(self):
        self.rodar(self.simular)

    def _confirmar(self, msg):
        """A guarda contra remocao em massa, vinda da thread do motor."""
        return self.app.perguntar(msg)

    def _monta(self):
        topo = ttk.Frame(self, padding=(16, 14, 16, 6))
        topo.pack(fill="x")
        ttk.Label(topo, text="Rodar", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(topo, style="Fraco.TLabel",
                  text="Simule primeiro, confira a pasta preview, e só então "
                       "aplique.").pack(anchor="w")

        self.checklist = ttk.Frame(self, style="Painel.TFrame",
                                   padding=(12, 10))
        self.checklist.pack(fill="x", padx=16, pady=(8, 4))

        op = ttk.Frame(self, padding=(16, 2, 16, 6))
        op.pack(fill="x")
        self.var_todos = tk.BooleanVar(value=True)
        ttk.Checkbutton(op, text="emoldurar a biblioteca inteira "
                                 "(badge só em quem tem coleção)",
                        variable=self.var_todos).pack(side="left")
        self.var_verbose = tk.BooleanVar(value=False)
        ttk.Checkbutton(op, text="detalhar", variable=self.var_verbose
                        ).pack(side="left", padx=16)

        self.barra = ttk.Frame(self, padding=(16, 2, 16, 8))
        self.barra.pack(fill="x")
        self.bt_acao = ttk.Button(self.barra, text="...", command=self.acionar)
        self.bt_acao.pack(side="left")
        self.bt_parar = ttk.Button(self.barra, text="Parar",
                                   command=self.cancelar, state="disabled")
        self.bt_parar.pack(side="left", padx=8)
        self.montar_acoes(self.barra)

        prog = ttk.Frame(self, padding=(16, 0, 16, 6))
        prog.pack(fill="x")
        self.prog = ttk.Progressbar(prog, mode="determinate")
        self.prog.pack(side="left", fill="x", expand=True)
        self.lb_prog = ttk.Label(prog, style="Fraco.TLabel", text="", width=16,
                                 anchor="e")
        self.lb_prog.pack(side="left", padx=8)

        caixa = ttk.Frame(self, padding=(16, 0, 16, 6))
        caixa.pack(fill="both", expand=True)
        self.log = tk.Text(caixa, bg=tema.CARTAO, fg=tema.TEXTO, borderwidth=0,
                           highlightthickness=0, wrap="none",
                           font=("Consolas", 9))
        rol = ttk.Scrollbar(caixa, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=rol.set)
        self.log.pack(side="left", fill="both", expand=True)
        rol.pack(side="right", fill="y")
        self.log.tag_configure("aviso", foreground=tema.ALERTA)
        self.log.tag_configure("fraco", foreground=tema.FRACO)
        self.log.tag_configure("ok", foreground=tema.OK)
        self.log.tag_configure("erro", foreground=tema.ERRO)
        self.log.configure(state="disabled")


    # ---- ponte com as threads -------------------------------------------

    def _escrever(self, txt, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", txt + "\n", tag or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def limpar_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    # ---- conferencia inicial --------------------------------------------

    def rodar(self, simular=None):
        if self.trabalhando:
            return
        simular = self.simular if simular is None else simular
        if not simular:
            if steam_rodando() is True and not messagebox.askokcancel(
                    "Vitrine", "O Steam parece estar aberto. Ele reescreve as "
                               "capas ao fechar, então o resultado pode sumir.\n\n"
                               "Continuar mesmo assim?"):
                return
            if not messagebox.askokcancel(
                    "Vitrine", "Isto escreve as capas na sua biblioteca Steam.\n"
                               "Da para desfazer depois com 'Desfazer tudo'.\n\n"
                               "Aplicar agora?"):
                return

        self.trabalhando = True
        self.parar.clear()
        self.limpar_log()
        self.prog.configure(value=0)
        self.bt_acao.configure(state="disabled")
        self.bt_parar.configure(state="normal")
        self.estado("simulando..." if simular else "aplicando...")

        todos = self.var_todos.get()
        verbose = self.var_verbose.get()

        def trabalho():
            try:
                resumo = self._trabalho(simular, todos, verbose)
                self._enviar(("fim", (resumo, simular), None))
            except core.ErroCore as e:
                msg = str(e)
                self._enviar(("linha", msg, "erro"))
                self._enviar(("fim", (None, simular), None))
            except Exception:
                tb = traceback.format_exc(limit=4)
                self._enviar(("linha", tb, "erro"))
                self._enviar(("fim", (None, simular), None))

        self.app.em_thread(trabalho)

    def _trabalho(self, simular, todos, verbose):
        rel = RelatorioTela(self._enviar, verboso=verbose)
        core.definir_relatorio(rel)

        listas = self.sessao.listas
        appids = (self.sessao.appids_todos() if todos
                  else sorted(self.sessao.appids_com_badge()))
        universo_completo = set(appids)
        rel.info(f"{len(appids)} jogos nesta execução.\n")

        op = rodar.Opcoes(dry_run=simular, out="preview", moldura=self.moldura,
                          todos=todos, verbose=verbose,
                          sgdb_key=self.sessao.sgdb_key)
        return rodar.executar(op, appids, listas, self.steam, self.grid,
                              universo_completo, None, rel=rel,
                              confirmar=self._confirmar,
                              parar=self.parar.is_set)

    def cancelar(self):
        self.parar.set()
        self.estado("parando no próximo jogo...")

    def _terminou(self, dado):
        resumo, simular = dado
        self.trabalhando = False
        self.bt_parar.configure(state="disabled")
        self.bt_acao.configure(state="normal" if self.liberado() else "disabled")
        if resumo is None:
            self.estado("terminou com erro - veja o log")
            return
        self.ultimo = resumo
        if simular:
            self.sessao.ultima_simulacao = resumo
            self.app.desenhar_barra()
            self.estado(f"{resumo['ok']} geradas, {resumo['falhou']} falharam "
                        f"- confira a pasta preview e aplique se gostar")
        else:
            self.estado(f"{resumo['ok']} aplicadas, {resumo['falhou']} falharam "
                        f"- feche e reabra o Steam pra ver")
            self.app.recarregar()

    def abrir_preview(self):
        pasta = core.BASE_DIR / "preview"
        if not pasta.is_dir():
            return
        try:
            if os.name == "nt":
                os.startfile(pasta)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(pasta)])
            else:
                subprocess.Popen(["xdg-open", str(pasta)])
        except Exception as e:
            messagebox.showinfo("Vitrine", f"A pasta está em:\n{pasta}\n\n({e})")

    def desfazer(self):
        if self.trabalhando:
            return
        if not messagebox.askokcancel(
                "Vitrine", "Isto remove as capas que aplicamos e devolve as "
                           "originais.\n\nContinuar?"):
            return
        self.limpar_log()
        core.definir_relatorio(RelatorioTela(self._enviar))

        def trabalho():
            try:
                core.restore(self.grid)
            except Exception:
                self._enviar(("linha", traceback.format_exc(limit=3), "erro"))
            self._enviar(("fn", self.conferir, None))

        self.app.em_thread(trabalho)
        self.estado("desfazendo...")

    def estado(self, txt):
        # um rodape so, o da casca
        self.app.estado(txt)
