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

def _primeira_fonte(candidatas, reserva):
    """
    A primeira fonte da lista que existe nesta maquina.

    'Segoe UI' e 'Consolas' so existem no Windows. No Linux o Tk cai numa
    fonte qualquer, que muda de distro pra distro - no Steam Deck dava
    uma coisa, em outra maquina dava outra. Pedindo em ordem, a cara do
    programa fica estavel em qualquer lugar.
    """
    try:
        from tkinter import font as _f
        existentes = {n.lower() for n in _f.families()}
        for c in candidatas:
            if c.lower() in existentes:
                return c
    except Exception:
        pass
    return reserva


# preenchidas por aplicar(), que e quando ja existe um root pra perguntar
FONTE = "Segoe UI"
FONTE_MONO = "Consolas"

RAIO = 10                # o quanto o canto do botao e arredondado
_IMAGENS = []            # o Tk nao segura PhotoImage; se soltar, some


# --------------------------------------------------------------------------
# Botoes
#
# O ttk desenha botao com um elemento de borda que nao sabe fazer canto
# redondo - em tema nenhum. O jeito de ter canto redondo e trocar esse
# elemento por uma IMAGEM, fatiada em nove (os quatro cantos ficam fixos,
# as bordas e o meio esticam). Dai um PNG de 36x36 serve pra botao de
# qualquer largura.
#
# As imagens sao desenhadas aqui, na hora, com o Pillow - que o programa
# ja exige. Nao viram arquivo: a cor sai das constantes la de cima, entao
# mexer numa cor muda o botao junto, sem ninguem precisar regerar nada.
# --------------------------------------------------------------------------

def _rgb(cor):
    """Aceita '#rrggbb' ou (r, g, b); devolve sempre a tupla."""
    if isinstance(cor, str):
        return tuple(int(cor[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(cor)


def _mistura(cor, com, quanto):
    """Interpola duas cores. quanto=0 e `cor`, 1 e `com`."""
    a, b = _rgb(cor), _rgb(com)
    return tuple(round(x + (y - x) * quanto) for x, y in zip(a, b))


def _pilula(cor, raio=RAIO, lado=36, rebaixo=True, afundado=False,
            brilho=True):
    """
    Um retangulo de cantos redondos, pronto pra virar elemento ttk.

    rebaixo  uma faixa mais escura embaixo, como a lateral de uma tecla
    afundado sem o rebaixo e com sombra no alto: o botao apertado
    brilho   a linha clara no topo; botao desligado nao reflete luz

    Desenha em 4x e reduz: e o que tira a escada do canto curvo.
    """
    from io import BytesIO
    from base64 import b64encode
    from PIL import Image, ImageDraw

    import tkinter as tk
    k = 4
    cor = _rgb(cor)
    r, L = raio * k, lado * k
    im = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    if rebaixo and not afundado:
        # o corpo inteiro na cor escura, e o de cima por cima: sobra uma
        # faixa embaixo, que e o que da o volume
        d.rounded_rectangle([0, 0, L - 1, L - 1], r,
                            fill=_mistura(cor, "#000000", 0.45) + (255,))
        d.rounded_rectangle([0, 0, L - 1, L - 1 - 3 * k], r, fill=cor + (255,))
    else:
        d.rounded_rectangle([0, 0, L - 1, L - 1], r, fill=cor + (255,))

    if afundado:
        # sombra fina no alto, por dentro: a leitura de "afundou"
        d.rounded_rectangle([0, 0, L - 1, L - 1], r,
                            outline=_mistura(cor, "#000000", 0.35) + (255,),
                            width=2 * k)
    elif brilho:
        # brilho de 1px no topo, como em qualquer tecla iluminada de cima
        d.line([(r, 1 * k), (L - r, 1 * k)],
               fill=_mistura(cor, "#ffffff", 0.13) + (255,), width=1 * k)

    im = im.resize((lado, lado), Image.LANCZOS)
    buf = BytesIO()
    im.save(buf, "PNG")
    foto = tk.PhotoImage(data=b64encode(buf.getvalue()).decode("ascii"))
    _IMAGENS.append(foto)                      # segurando a referencia
    return foto


def _variante(s, nome, cor, texto, negrito=False, atras=None):
    """
    Cria o elemento de imagem e o layout de uma familia de botao.

    `atras` e a cor que aparece no canto arredondado. O Tk nao compoe o
    alfa da imagem contra o que esta desenhado embaixo - ele compoe
    contra o `background` do proprio estilo, e sem dizer nada esse fundo
    e o cinza claro que o clam traz de fabrica. O resultado sao quatro
    cunhas claras nos cantos. Por isso existe uma variante por fundo,
    como ja acontece com os rotulos.
    """
    elem = f"{nome}.corpo"
    s.element_create(
        elem, "image", _pilula(cor),
        ("pressed", _pilula(_mistura(cor, "#000000", 0.22), afundado=True)),
        ("active", _pilula(_mistura(cor, "#ffffff", 0.14))),
        ("disabled", _pilula(CARTAO, rebaixo=False, brilho=False)),
        border=RAIO + 2, sticky="nsew")
    s.layout(nome, [(elem, {"sticky": "nsew", "children": [
        ("Button.padding", {"sticky": "nsew", "children": [
            ("Button.label", {"sticky": "nsew"})]})]})])
    s.configure(nome, padding=(14, 7), anchor="center", borderwidth=0,
                background=atras or FUNDO, foreground=texto,
                font=(FONTE, 10, "bold") if negrito else (FONTE, 10))
    s.map(nome, foreground=[("disabled", "#5d7084")],
          background=[("active", atras or FUNDO),
                      ("pressed", atras or FUNDO),
                      ("disabled", atras or FUNDO)])


def _botoes(s, root):
    """
    Os tres tipos de botao. Se o Pillow faltar, cai no botao quadrado do
    clam - feio, mas o programa abre.
    """
    try:
        corpo = _mistura(PAINEL, "#ffffff", 0.06)
        # uma familia por fundo em que o botao pode cair
        for prefixo, atras in (("", FUNDO), ("Painel.", PAINEL),
                               ("Cartao.", CARTAO)):
            _variante(s, f"{prefixo}TButton", corpo, TEXTO, atras=atras)
            _variante(s, f"{prefixo}Forte.TButton", ACENTO, SOBRE_ACENTO,
                      negrito=True, atras=atras)
            _variante(s, f"{prefixo}Perigo.TButton", "#b14a45", "#ffffff",
                      negrito=True, atras=atras)
    except Exception:
        s.configure("TButton", background=PAINEL, foreground=TEXTO,
                    padding=(12, 6), font=(FONTE, 10))
        s.map("TButton", background=[("active", ACENTO), ("disabled", CARTAO)],
              foreground=[("active", SOBRE_ACENTO), ("disabled", FRACO)])
        s.configure("Forte.TButton", background=ACENTO,
                    foreground=SOBRE_ACENTO, font=(FONTE, 10, "bold"))
        s.configure("Perigo.TButton", background="#8c3b38",
                    foreground="#ffffff", font=(FONTE, 10, "bold"))


def aplicar(root):
    """Configura o ttk.Style da janela e devolve o objeto Style."""
    from tkinter import ttk
    import tkinter as tk

    global FONTE, FONTE_MONO
    # a familia so da pra consultar com um root de pe, entao e aqui
    FONTE = _primeira_fonte(
        ["Segoe UI", "Inter", "Noto Sans", "Cantarell", "DejaVu Sans",
         "Liberation Sans"], "TkDefaultFont")
    FONTE_MONO = _primeira_fonte(
        ["Consolas", "Cascadia Mono", "JetBrains Mono", "Noto Sans Mono",
         "DejaVu Sans Mono", "Liberation Mono"], "TkFixedFont")

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
    _botoes(s, root)

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
