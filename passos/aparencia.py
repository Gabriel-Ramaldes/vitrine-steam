"""
Etapa - Aparencia.

Escolhe entre a capa emoldurada como caixa de jogo e o badge solto sobre
a arte original, e gera os arquivos de que a moldura precisa.

Existe porque isso era um ponto cego: `"moldura": true` so se descobria
lendo o config.json, e a tela de rodar apenas reclamava quando faltavam
os arquivos, sem oferecer um jeito de resolver.
"""
import json
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

import core
import tema
from app import Passo


class Aparencia(Passo):
    titulo = "Aparencia"

    @staticmethod
    def precisa(sessao):
        return sessao.tem_steam

    def montar(self):
        self.imagens = {}
        self.gerando = False

        ttk.Label(self, text="Aparencia", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(self, style="Sub.TLabel", wraplength=700, justify="left",
                  text="Como a capa de cada jogo e montada."
                  ).pack(anchor="w", pady=(2, 14))

        self.var_moldura = tk.BooleanVar(value=False)
        escolhas = ttk.Frame(self)
        escolhas.pack(fill="x")
        for valor, titulo, txt in (
            (True, "Caixa de jogo",
             "A arte vira a capa de uma caixa fisica: moldura azul, logo da "
             "Steam no topo e o badge na base. Platinado troca a caixa pela "
             "dourada e ganha a fita de 100%."),
            (False, "Badge solto",
             "A arte original fica como esta, com o badge colado num canto. "
             "Nao precisa de nenhum arquivo extra."),
        ):
            cx = ttk.Frame(escolhas, style="Painel.TFrame", padding=(12, 10))
            cx.pack(fill="x", pady=(0, 8))
            ttk.Radiobutton(cx, text=titulo, value=valor,
                            variable=self.var_moldura, command=self.escolheu,
                            style="Painel.TRadiobutton").pack(anchor="w")
            ttk.Label(cx, text=txt, style="Painel.Fraco.TLabel",
                      wraplength=620, justify="left").pack(anchor="w", padx=22)

        self.cx_moldura = ttk.Frame(self)
        self.cx_moldura.pack(fill="x", pady=(6, 0))
        self.lb_arquivos = ttk.Label(self.cx_moldura, style="Fraco.TLabel",
                                     text="")
        self.lb_arquivos.pack(anchor="w")
        linha = ttk.Frame(self.cx_moldura)
        linha.pack(fill="x", pady=(6, 0))
        self.bt_gerar = ttk.Button(linha, text="Gerar as molduras",
                                   command=self.gerar)
        self.bt_gerar.pack(side="left")
        ttk.Label(linha, style="Fraco.TLabel", wraplength=460, justify="left",
                  text="As molduras sao desenhadas por codigo, nao baixadas. "
                       "Gere de novo depois de mexer em tools/build_frame.py."
                  ).pack(side="left", padx=12)

        self.previa = ttk.Frame(self, style="Painel.TFrame", padding=10)
        self.previa.pack(fill="x", pady=(12, 0))

    # ---- estado ----------------------------------------------------------

    def ao_entrar(self):
        self.var_moldura.set(self.sessao.moldura)
        self.atualizar()

    def atualizar(self):
        d = core.molduras_dir()
        # quem responde e o core: a peca pode estar na sua pasta ou ter
        # vindo em assets/molduras/, e as duas contam como pronta
        faltando = core.molduras_faltando()
        if self.var_moldura.get():
            self.cx_moldura.pack(fill="x", pady=(6, 0))
            if faltando:
                self.lb_arquivos.configure(
                    text=f"faltam {len(faltando)} arquivo(s) em "
                         f"{d.name}/: {', '.join(faltando[:3])}"
                         f"{'...' if len(faltando) > 3 else ''}",
                    style="Erro.TLabel")
            else:
                proprias = (d / "case.png").exists()
                self.lb_arquivos.configure(
                    text="molduras prontas em "
                         + (f"{d.name}/" if proprias
                            else f"{core.ASSETS_DIR_NAME}/{d.name}/"),
                    style="Ok.TLabel")
        else:
            self.cx_moldura.pack_forget()
        self.desenhar_previa(faltando)

    def desenhar_previa(self, faltando):
        for w in self.previa.winfo_children():
            w.destroy()
        if not self.var_moldura.get():
            ttk.Label(self.previa, style="Painel.Fraco.TLabel",
                      text="Sem moldura, a capa fica como a Steam serve, so "
                           "com o badge por cima.").pack(anchor="w")
            return
        if faltando:
            ttk.Label(self.previa, style="Painel.Fraco.TLabel",
                      text="Gere as molduras para ver a previa."
                      ).pack(anchor="w")
            return
        faixa = ttk.Frame(self.previa, style="Painel.TFrame")
        faixa.pack(anchor="w")
        for nome, rotulo in (("case.png", "normal"),
                             ("case_ouro.png", "platinado"),
                             ("family.png", "canto family")):
            try:
                import galeria
                f = core.peca_moldura(nome)       # a que vale, nao a sua
                b64 = galeria.miniatura(f.read_bytes(), 96)
                img = tk.PhotoImage(data=b64)
            except Exception:
                continue
            self.imagens[nome] = img
            cel = ttk.Frame(faixa, style="Painel.TFrame")
            cel.pack(side="left", padx=(0, 14))
            ttk.Label(cel, image=img, background=tema.PAINEL).pack()
            ttk.Label(cel, text=rotulo, style="Painel.Fraco.TLabel"
                      ).pack(anchor="center")

    # ---- acoes -----------------------------------------------------------

    def escolheu(self):
        """
        Grava a escolha na hora. Deixar pra depois criaria um estado em
        que a tela diz uma coisa e o config diz outra.
        """
        caminho = self.sessao.caminho_config
        try:
            cfg = json.loads(caminho.read_text(encoding="utf-8-sig")) \
                if caminho.exists() else {}
        except (OSError, ValueError) as e:
            messagebox.showerror("Vitrine", f"nao consegui ler o config:\n{e}")
            return
        cfg["moldura"] = bool(self.var_moldura.get())
        tmp = caminho.with_suffix(caminho.suffix + ".tmp")
        try:
            tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
            if caminho.exists():
                caminho.with_suffix(caminho.suffix + ".bak").write_bytes(
                    caminho.read_bytes())
            tmp.replace(caminho)
        except OSError as e:
            messagebox.showerror("Vitrine", f"nao consegui gravar:\n{e}")
            return
        self.atualizar()
        self.app.estado("formato salvo em config.json")
        self.app.recarregar()

    def gerar(self):
        if self.gerando:
            return
        self.gerando = True
        self.bt_gerar.configure(state="disabled")
        self.app.estado("desenhando as molduras...")

        def trabalho():
            try:
                import sys
                raiz = str(core.BASE_DIR)
                if raiz not in sys.path:
                    sys.path.insert(0, raiz)
                from tools import build_frame, build_stickers
                feitos = build_frame.gerar(core.molduras_dir())
                try:
                    build_stickers.gerar_do_config(
                        str(self.sessao.caminho_config),
                        str(core.BASE_DIR / "adesivos"))
                except Exception:
                    pass          # sem adesivo no config, nao e erro
                msg = f"molduras geradas: {', '.join(feitos)}"
            except Exception:
                msg = traceback.format_exc(limit=3)
            self.app.na_janela(lambda: self._gerou(msg))

        self.app.em_thread(trabalho)

    def _gerou(self, msg):
        self.gerando = False
        self.bt_gerar.configure(state="normal")
        if msg.startswith("molduras geradas"):
            self.app.estado(msg)
        else:
            messagebox.showerror("Vitrine", msg)
            self.app.estado("falhou ao gerar - veja a mensagem")
        self.atualizar()
        self.app.recarregar()

    def concluida(self):
        return self.sessao.moldura_pronta
