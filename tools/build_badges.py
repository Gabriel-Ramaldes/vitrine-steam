"""
Gera o conjunto padrao de badges, em badges_padrao/.

Por que existe: os icones que eu uso no dia a dia sao do Flaticon, cuja
licenca gratuita exige atribuicao e NAO permite redistribuir os arquivos.
Entao eles ficam so na minha maquina. Sem um conjunto proprio, quem
clonasse o repositorio nao conseguiria gerar capa nenhuma com status.

Este conjunto resolve isso: parte do Bootstrap Icons (MIT, redistribuicao
permitida), que vive em tools/icones/ como SVG - a fonte de verdade - e
como PNG branco ja rasterizado, para o gerador nao precisar de nenhuma
biblioteca de SVG.

Os PNG saem em badges_padrao/, NAO em badges/. Assim quem quiser usar os
proprios icones poe em badges/ e eles vencem, sem o git ficar acusando
diferenca nos arquivos padrao.

    python tools/build_badges.py
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

K = 4                      # supersampling: desenha grande e reduz
LADO = 256

# Estilo adesivo: contorno escuro grosso, cor chapada, brilho no alto e o
# glifo branco com borda escura. Mexer aqui muda o conjunto inteiro.
CONTORNO = (0x12, 0x18, 0x22)   # a cor do aro e da borda do glifo
ESPESSURA = 0.075               # do aro, em fracao do diametro
GLIFO = 0.54                    # quanto do disco o glifo ocupa
BORDA_GLIFO = 9                 # espessura da borda escura do glifo, em px
BRILHO = 46                     # alfa do brilho no alto (0 desliga)

# Cada badge: a cor do disco. family e a excecao - ele nao ganha disco,
# porque e colado sobre o triangulo verde do canto e precisa ser so o
# glifo branco.
CORES = {
    "platinado":  (0xc9, 0x97, 0x1f),   # ouro
    "zerado":     (0x3a, 0x8a, 0x3f),   # verde
    "suficiente": (0x2f, 0x7d, 0x86),   # azul petroleo
    "abandonado": (0xa3, 0x3b, 0x35),   # tijolo
    "pausado":    (0xc4, 0x7a, 0x1a),   # ambar
    "online":     (0x2d, 0x6c, 0xb5),   # azul
}
SO_GLIFO = ("family",)

AQUI = os.path.dirname(os.path.abspath(__file__))
ICONES = os.path.join(AQUI, "icones")


def _glifo(nome, lado):
    """O PNG branco do Bootstrap Icons, encaixado num quadrado de `lado`."""
    caminho = os.path.join(ICONES, f"{nome}.png")
    if not os.path.exists(caminho):
        return None
    im = Image.open(caminho).convert("RGBA")
    corte = im.getbbox()           # tira a folga em volta do desenho
    if corte:
        im = im.crop(corte)
    escala = min(lado / im.width, lado / im.height)
    novo = (max(1, round(im.width * escala)), max(1, round(im.height * escala)))
    im = im.resize(novo, Image.LANCZOS)
    tela = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    tela.alpha_composite(im, ((lado - novo[0]) // 2, (lado - novo[1]) // 2))
    return tela


def badge(nome, cor=None, lado=LADO):
    """
    Um badge no estilo adesivo: disco colorido com aro escuro e o glifo
    branco por cima, tambem contornado.

    Com cor=None sai so o glifo branco, sem disco nem contorno - e o caso
    do family, que e colado sobre o triangulo verde do canto e ja tem
    contraste de sobra.
    """
    if cor is None:
        g = _glifo(nome, lado * K)
        return g.resize((lado, lado), Image.LANCZOS) if g else None

    r = lado * K
    tela = Image.new("RGBA", (r, r), (0, 0, 0, 0))
    d = ImageDraw.Draw(tela)
    esp = r * ESPESSURA

    d.ellipse([0, 0, r - 1, r - 1], fill=tuple(CONTORNO) + (255,))
    d.ellipse([esp, esp, r - esp, r - esp], fill=tuple(cor) + (255,))

    if BRILHO:
        # meia-lua clara no alto: o que da a cara de adesivo impresso
        luz = Image.new("RGBA", (r, r), (0, 0, 0, 0))
        ImageDraw.Draw(luz).ellipse(
            [esp * 1.8, esp * 1.6, r - esp * 1.8, r * 0.52],
            fill=(255, 255, 255, BRILHO))
        tela = Image.alpha_composite(tela, luz)

    g = _glifo(nome, int(r * GLIFO))
    if g is None:
        return None
    # a borda escura e o glifo dilatado: sem ela o branco some sobre as
    # cores claras, como o ambar do pausado
    borda = Image.new("RGBA", g.size, tuple(CONTORNO) + (255,))
    borda.putalpha(g.getchannel("A").filter(
        ImageFilter.MaxFilter(BORDA_GLIFO)))
    pos = ((r - g.width) // 2, (r - g.height) // 2)
    tela.alpha_composite(borda, pos)
    tela.alpha_composite(g, pos)
    return tela.resize((lado, lado), Image.LANCZOS)


def gerar(destino=None):
    """Escreve o conjunto inteiro e devolve os nomes gerados."""
    destino = destino or os.path.join(os.path.dirname(AQUI), "badges_padrao")
    os.makedirs(destino, exist_ok=True)
    feitos = []
    for nome, cor in CORES.items():
        im = badge(nome, cor)
        if im is None:
            continue
        im.save(os.path.join(destino, f"{nome}.png"))
        feitos.append(nome)
    for nome in SO_GLIFO:
        im = badge(nome, None)
        if im is None:
            continue
        im.save(os.path.join(destino, f"{nome}.png"))
        feitos.append(nome)
    return feitos


if __name__ == "__main__":
    alvo = sys.argv[1] if len(sys.argv) > 1 else None
    feitos = gerar(alvo)
    print("badges gerados:", ", ".join(feitos) or "(nenhum)")
