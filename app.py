"""
Vitrine - a aplicacao.

Uma janela so, conduzindo por etapas. A casca e dona do root, do tema, do
estado compartilhado e da ponte com as threads; cada etapa e um ttk.Frame
que so desenha o seu pedaco.

    python app.py
"""
import queue
import sys
import threading
import traceback

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    sys.exit("Esta aplicacao precisa do tkinter.\n"
             "No Windows ele vem com o Python de python.org - reinstale\n"
             "marcando 'tcl/tk and IDLE'. No Linux: apt install python3-tk.")

import core
import tema
from sessao import Sessao


class Passo(ttk.Frame):
    """
    Uma etapa. Subclasses mexem so no proprio conteudo.

    titulo     aparece na barra lateral
    precisa    funcao(sessao) -> True quando a etapa pode ser aberta
    """
    titulo = "Etapa"
    resumo = ""

    @staticmethod
    def precisa(sessao):
        return True

    def __init__(self, master, app):
        super().__init__(master, style="TFrame", padding=(20, 16))
        self.app = app
        self.sessao = app.sessao
        self.montar()

    def montar(self):
        """Chamada uma vez, na criacao."""

    def ao_entrar(self):
        """Toda vez que a etapa aparece. Bom lugar pra reler o estado."""

    def ao_sair(self):
        """False impede a navegacao (ex.: alteracoes nao salvas)."""
        return True

    def concluida(self):
        """True marca a etapa como feita na barra lateral."""
        return False


class App(tk.Tk):
    def __init__(self, passos=None):
        super().__init__()
        self.title("Vitrine")
        self.geometry("1120x760")
        self.minsize(900, 620)
        tema.aplicar(self)

        self.fila = queue.Queue()
        self.resposta = queue.Queue()
        self.sessao = Sessao()
        self.passos = []
        self.atual = -1
        self._instancias = {}

        self._agendados = []
        self._vivo = True
        self._monta()
        for classe in (passos if passos is not None else PASSOS):
            self.registrar(classe)
        self.agendar(60, self._bombear)
        self.agendar(100, self.primeira_carga)
        self.protocol("WM_DELETE_WINDOW", self.fechar)

    # ---- agenda ----------------------------------------------------------

    def agendar(self, ms, fn):
        """
        after() que lembra o que agendou.

        Sem isto, um callback agendado dispara depois que a janela ja foi
        destruida e o Tk reclama de "invalid command name" - acontece ao
        fechar durante a carga inicial.
        """
        if not self._vivo:
            return None
        ident = self.after(ms, fn)
        self._agendados.append(ident)
        return ident

    def destroy(self):
        self._vivo = False
        for ident in self._agendados:
            try:
                self.after_cancel(ident)
            except Exception:
                pass
        self._agendados.clear()
        super().destroy()

    # ---- estrutura -------------------------------------------------------

    def _monta(self):
        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True)

        lateral = ttk.Frame(corpo, style="Painel.TFrame", padding=(0, 14))
        lateral.pack(side="left", fill="y")
        ttk.Label(lateral, text="  Vitrine", style="Painel.Titulo.TLabel"
                  ).pack(anchor="w", padx=10, pady=(0, 12))
        self.barra = ttk.Frame(lateral, style="Painel.TFrame")
        self.barra.pack(fill="x")

        self.area = ttk.Frame(corpo)
        self.area.pack(side="left", fill="both", expand=True)

        pe = ttk.Frame(self, padding=(20, 10, 20, 14))
        pe.pack(fill="x")
        self.lb_estado = ttk.Label(pe, style="Fraco.TLabel", text="")
        self.lb_estado.pack(side="left")
        self.bt_proximo = ttk.Button(pe, text="Avancar  >",
                                     style="Forte.TButton",
                                     command=self.proximo)
        self.bt_proximo.pack(side="right")
        self.bt_anterior = ttk.Button(pe, text="<  Voltar",
                                      command=self.anterior)
        self.bt_anterior.pack(side="right", padx=8)

    def registrar(self, classe):
        self.passos.append(classe)

    # ---- navegacao -------------------------------------------------------

    def _frame(self, i):
        classe = self.passos[i]
        if classe not in self._instancias:
            self._instancias[classe] = classe(self.area, self)
        return self._instancias[classe]

    def ir(self, i, forcado=False):
        if not 0 <= i < len(self.passos):
            return
        if i == self.atual:
            return
        if self.atual >= 0:
            if not self._frame(self.atual).ao_sair():
                return
            self._frame(self.atual).pack_forget()
        if not forcado and not self.passos[i].precisa(self.sessao):
            self.estado(f"'{self.passos[i].titulo}' ainda nao esta liberada")
            if self.atual >= 0:
                self._frame(self.atual).pack(fill="both", expand=True)
            return
        self.atual = i
        f = self._frame(i)
        f.pack(fill="both", expand=True)
        f.ao_entrar()
        self.desenhar_barra()
        self.bt_anterior.configure(
            state="normal" if i > 0 else "disabled")
        self.bt_proximo.configure(
            text="Avancar  >" if i < len(self.passos) - 1 else "Concluir",
            state="normal" if i < len(self.passos) - 1 else "disabled")

    def proximo(self):
        self.ir(self.atual + 1)

    def anterior(self):
        self.ir(self.atual - 1)

    def desenhar_barra(self):
        for w in self.barra.winfo_children():
            w.destroy()
        for i, classe in enumerate(self.passos):
            liberada = classe.precisa(self.sessao)
            if i == self.atual:
                estilo = "EtapaAtual.TLabel"
            elif not liberada:
                estilo = "EtapaTrancada.TLabel"
            elif classe in self._instancias and \
                    self._instancias[classe].concluida():
                estilo = "EtapaFeita.TLabel"
            else:
                estilo = "Etapa.TLabel"
            lb = ttk.Label(self.barra, text=f"  {i + 1}. {classe.titulo}",
                           style=estilo, width=22, anchor="w")
            lb.pack(fill="x")
            if liberada:
                lb.configure(cursor="hand2")
                lb.bind("<Button-1>", lambda e, k=i: self.ir(k))

    # ---- carga inicial ---------------------------------------------------

    def primeira_carga(self):
        self.estado("lendo o Steam...")

        def trabalho():
            try:
                self.sessao.carregar(avisar=False)
            except Exception:
                tb = traceback.format_exc(limit=3)
                self.na_janela(lambda: messagebox.showerror("Vitrine", tb))
            self.na_janela(self._carregou)

        self.em_thread(trabalho)

    def _carregou(self):
        self.sessao._avisar()
        self.ir(0, forcado=True)
        self.estado("")

    # ---- ponte com as threads -------------------------------------------

    def _bombear(self):
        """
        tkinter nao e seguro fora da thread da janela. Tudo que uma thread
        quer desenhar passa por aqui.
        """
        try:
            while True:
                fn = self.fila.get_nowait()
                try:
                    fn()
                except Exception:
                    self.estado(traceback.format_exc(limit=2)
                                .strip().splitlines()[-1][:110])
        except queue.Empty:
            pass
        self.agendar(60, self._bombear)

    def na_janela(self, fn):
        if self._vivo:
            self.fila.put(fn)

    def em_thread(self, alvo):
        t = threading.Thread(target=alvo, daemon=True)
        t.start()
        return t

    def perguntar(self, msg):
        """
        Sim/nao a partir de uma thread. O dialogo abre na thread da janela
        e a chamadora espera - abrir de fora trava a aplicacao.
        """
        self.na_janela(lambda: self.resposta.put(
            messagebox.askokcancel("Vitrine", msg)))
        return bool(self.resposta.get())

    # ---- utilidades para as etapas --------------------------------------

    def estado(self, txt):
        self.lb_estado.configure(text=txt)

    def recarregar(self):
        """Uma etapa mudou o config: relê e redesenha a barra."""
        def trabalho():
            self.sessao.carregar(avisar=False)
            self.na_janela(lambda: (self.sessao._avisar(),
                                    self.desenhar_barra()))
        self.em_thread(trabalho)

    def fechar(self):
        if self.atual >= 0 and not self._frame(self.atual).ao_sair():
            return
        self.destroy()


class RelatorioTela(core.Relatorio):
    """O motor fala com a tela por aqui, sem saber que ha uma tela."""

    def __init__(self, enviar, verboso=False):
        self.enviar = enviar
        self.verboso = verboso

    def info(self, msg):
        self.enviar(("linha", str(msg), None))

    def aviso(self, msg):
        self.enviar(("linha", str(msg), "aviso"))

    def detalhe(self, msg):
        if self.verboso:
            self.enviar(("linha", str(msg), "fraco"))

    def item(self, i, total, appid, rotulo, origem, extra=""):
        self.enviar(("item", (i, total, appid, rotulo, origem, extra), None))


# As etapas, na ordem. Preenchido pelos modulos de passos.
PASSOS = []


def carregar_passos():
    global PASSOS
    from passos import ORDEM
    PASSOS = list(ORDEM)
    return PASSOS


def main():
    try:
        carregar_passos()
    except ImportError as e:
        sys.exit(f"nao achei as etapas: {e}")
    try:
        App().mainloop()
    except tk.TclError as e:
        sys.exit(f"Nao consegui abrir a janela: {e}")


if __name__ == "__main__":
    main()
