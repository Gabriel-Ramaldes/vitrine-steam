"""
As cores e os estilos, num lugar so.

As tres telas repetiam o mesmo bloco de ttk.Style - mesmas cores, mesmos
nomes. Repetido, divergia: o mesmo 'Alerta.TLabel' tinha fundo diferente
em duas telas, porque numa ele vivia sobre o painel e na outra sobre o
fundo. Aqui os dois casos tem nome proprio.

A casca aplica isto uma vez; as etapas so usam os nomes.
"""

FUNDO = "#1b2838"        # azul escuro da Steam
PAINEL = "#2a3f5a"       # blocos sobre o fundo
CARTAO = "#16202d"       # campos e cartoes, mais escuros que o painel
TEXTO = "#c7d5e0"
FRACO = "#8ba1b5"
ACENTO = "#66c0f4"
ALERTA = "#e8a33d"
ERRO = "#d9534f"
OK = "#5ba32b"
SOBRE_ACENTO = "#0b1620"  # texto sobre o azul claro

FONTE = "Segoe UI"
FONTE_MONO = "Consolas"


def aplicar(root):
    """Configura o ttk.Style da janela e devolve o objeto Style."""
    from tkinter import ttk
    import tkinter as tk

    s = ttk.Style(root)
    try:
        s.theme_use("clam")      # o unico tema que aceita recolorir tudo
    except tk.TclError:
        pass

    root.configure(bg=FUNDO)
    s.configure(".", background=FUNDO, foreground=TEXTO, borderwidth=0)

    # --- containers ---
    s.configure("TFrame", background=FUNDO)
    s.configure("Painel.TFrame", background=PAINEL)
    s.configure("Cartao.TFrame", background=CARTAO)

    # --- textos: um por fundo em que o rotulo pode cair ---
    for sufixo, fundo in (("", FUNDO), ("Painel.", PAINEL), ("Cartao.", CARTAO)):
        s.configure(f"{sufixo}TLabel", background=fundo, foreground=TEXTO)
        s.configure(f"{sufixo}Fraco.TLabel", background=fundo, foreground=FRACO)
        s.configure(f"{sufixo}Alerta.TLabel", background=fundo, foreground=ALERTA)
        s.configure(f"{sufixo}Erro.TLabel", background=fundo, foreground=ERRO)
        s.configure(f"{sufixo}Ok.TLabel", background=fundo, foreground=OK)
    s.configure("Titulo.TLabel", background=FUNDO, foreground="#ffffff",
                font=(FONTE, 16, "bold"))
    s.configure("Painel.Titulo.TLabel", background=PAINEL, foreground="#ffffff",
                font=(FONTE, 16, "bold"))
    s.configure("Sub.TLabel", background=FUNDO, foreground=FRACO,
                font=(FONTE, 10))

    # --- botoes ---
    s.configure("TButton", background=PAINEL, foreground=TEXTO,
                padding=(12, 6), font=(FONTE, 10))
    s.map("TButton", background=[("active", ACENTO), ("disabled", CARTAO)],
          foreground=[("active", SOBRE_ACENTO), ("disabled", FRACO)])
    s.configure("Forte.TButton", background=ACENTO, foreground=SOBRE_ACENTO,
                font=(FONTE, 10, "bold"))
    s.map("Forte.TButton", background=[("active", "#8fd3ff"),
                                       ("disabled", CARTAO)],
          foreground=[("disabled", FRACO)])
    s.configure("Perigo.TButton", background="#8c3b38", foreground="#ffffff",
                font=(FONTE, 10, "bold"))
    s.map("Perigo.TButton", background=[("active", ERRO), ("disabled", CARTAO)],
          foreground=[("disabled", FRACO)])

    # --- campos ---
    # o estado readonly do Combobox tem cores proprias no clam: sem mapear,
    # fica texto claro sobre fundo claro
    s.configure("TCombobox", arrowcolor=TEXTO, borderwidth=0)
    s.map("TCombobox",
          fieldbackground=[("readonly", CARTAO), ("!readonly", CARTAO)],
          background=[("readonly", CARTAO)],
          foreground=[("readonly", TEXTO), ("disabled", FRACO)],
          selectbackground=[("readonly", CARTAO)],
          selectforeground=[("readonly", TEXTO)],
          arrowcolor=[("active", ACENTO)])
    s.configure("Vazio.TCombobox", foreground=FRACO)
    s.map("Vazio.TCombobox",
          fieldbackground=[("readonly", CARTAO)],
          foreground=[("readonly", FRACO)],
          selectbackground=[("readonly", CARTAO)],
          selectforeground=[("readonly", FRACO)])
    s.configure("TEntry", fieldbackground=CARTAO, foreground=TEXTO,
                insertcolor=TEXTO, borderwidth=0)

    for sufixo, fundo in (("", FUNDO), ("Painel.", PAINEL)):
        for w in ("TCheckbutton", "TRadiobutton"):
            s.configure(f"{sufixo}{w}", background=fundo, foreground=TEXTO)
            s.map(f"{sufixo}{w}", background=[("active", fundo)],
                  indicatorcolor=[("selected", ACENTO), ("!selected", CARTAO)])

    s.configure("TProgressbar", background=ACENTO, troughcolor=CARTAO,
                borderwidth=0)
    s.configure("Vertical.TScrollbar", background=PAINEL, troughcolor=FUNDO,
                arrowcolor=TEXTO, borderwidth=0)

    # --- a barra de etapas ---
    s.configure("Etapa.TLabel", background=PAINEL, foreground=FRACO,
                padding=(14, 9), font=(FONTE, 10))
    s.configure("EtapaAtual.TLabel", background=ACENTO,
                foreground=SOBRE_ACENTO, padding=(14, 9),
                font=(FONTE, 10, "bold"))
    s.configure("EtapaFeita.TLabel", background=PAINEL, foreground=OK,
                padding=(14, 9), font=(FONTE, 10))
    s.configure("EtapaTrancada.TLabel", background=PAINEL, foreground="#54657a",
                padding=(14, 9), font=(FONTE, 10))

    # a lista suspensa do Combobox e um widget Tk classico, nao ttk
    root.option_add("*TCombobox*Listbox.background", CARTAO)
    root.option_add("*TCombobox*Listbox.foreground", TEXTO)
    root.option_add("*TCombobox*Listbox.selectBackground", ACENTO)
    root.option_add("*TCombobox*Listbox.selectForeground", SOBRE_ACENTO)
    return s
