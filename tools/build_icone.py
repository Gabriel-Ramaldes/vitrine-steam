"""
Gera o icone da aplicacao, em assets/icone/.

Dois modos:

    python tools/build_icone.py                 # desenha assets/icone/padrao.*
    python tools/build_icone.py minha_arte.png  # converte pra assets/icone/vitrine.*

O VITRINE e o icone de verdade, e o que vai pro repositorio: qualquer
imagem entra, sai quadrada e nos sete tamanhos que o Windows pede.

O PADRAO e uma rede de seguranca desenhada aqui, do zero, com o mesmo
Bootstrap Icons (MIT) dos badges - util pra quem fizer um fork e quiser
o proprio icone sem desenhar nada. Nao acompanha o repositorio; quando
existe, perde pro vitrine.

Os dois saem como .png (a janela do tkinter) e .ico (o arquivo do exe e a
barra de tarefas).
"""
import io
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFilter

# o unico gerador que depende de outro: o badge do icone e o mesmo dos
# badges. Os dois caminhos existem porque isto roda tanto como script
# solto (python tools/build_icone.py) quanto importado como tools.*
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from build_badges import CORES, badge                     # noqa: E402
except ImportError:                                           # pragma: no cover
    from tools.build_badges import CORES, badge               # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
DESTINO = os.path.join(RAIZ, "assets", "icone")

MESTRE = 1024                    # desenha grande, reduz depois
JANELA = 256                     # o .png que o tkinter usa
NO_ICO = (256, 128, 64, 48, 32, 24, 16)

FUNDO_ALTO = (0x2a, 0x3f, 0x5a)  # o PAINEL do tema
FUNDO_BAIXO = (0x14, 0x1e, 0x2b)
CASE_CLARO = (0xd6, 0xdf, 0xe8)
CASE_ESCURO = (0xa8, 0xb6, 0xc4)
LOMBADA = (0x8b, 0x9b, 0xad)


# --------------------------------------------------------------- formas

def _squircle(lado, n=4.2):
    """
    A silhueta de icone que todo sistema usa hoje: nem quadrado, nem
    retangulo arredondado. E uma superelipse |x|^n + |y|^n = 1 - a curva
    entra no canto antes e sai depois, sem a emenda visivel que o raio
    constante deixa.
    """
    m = Image.new("L", (lado, lado), 0)
    px = m.load()
    r = lado / 2.0
    for y in range(lado):
        v = abs((y + 0.5 - r) / r) ** n
        if v >= 1.0:
            continue
        # resolve pra x: o quanto da linha cabe dentro da curva
        meia = r * (1.0 - v) ** (1.0 / n)
        a = int(round(r - meia))
        b = int(round(r + meia))
        for x in range(max(0, a), min(lado, b)):
            px[x, y] = 255
    return m


def _degrade(lado, alto, baixo):
    """Um degrade vertical simples, de `alto` pra `baixo`."""
    g = Image.new("RGB", (1, lado))
    gp = g.load()
    for y in range(lado):
        t = y / max(1, lado - 1)
        gp[0, y] = tuple(round(alto[i] + (baixo[i] - alto[i]) * t) for i in range(3))
    return g.resize((lado, lado))


def _case(larg, alt):
    """
    Uma caixa de jogo vista de frente: capa clara, lombada na esquerda.

    E o que o programa faz, resumido num desenho: ele trata a capa da
    Steam como se fosse uma caixa de prateleira.
    """
    im = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    raio = round(larg * 0.06)
    d.rounded_rectangle([0, 0, larg - 1, alt - 1], raio, fill=CASE_CLARO)

    # sombreado: a capa escurece um pouco pra direita, dando volume
    sombra = _degrade(alt, CASE_CLARO, CASE_ESCURO).rotate(90).resize((larg, alt))
    mask = Image.new("L", (larg, alt), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, larg - 1, alt - 1], raio, fill=110)
    im.paste(sombra, (0, 0), mask)

    # lombada
    lom = round(larg * 0.17)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, lom, alt - 1], raio, fill=LOMBADA)
    d.rectangle([lom - raio, 0, lom, alt - 1], fill=LOMBADA)
    d.line([(lom + 1, 0), (lom + 1, alt - 1)], fill=(0x74, 0x84, 0x96), width=max(1, larg // 90))
    return im


# --------------------------------------------------------------- padrao

def desenhar_padrao(lado=MESTRE):
    """O icone do repositorio: a caixa, com um badge no canto."""
    im = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    im.paste(_degrade(lado, FUNDO_ALTO, FUNDO_BAIXO), (0, 0))

    # um brilho suave no alto, pra chapa nao ficar morta
    brilho = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(brilho).ellipse(
        [-lado * 0.3, -lado * 0.9, lado * 1.3, lado * 0.45], fill=38)
    im.paste(Image.new("RGB", (lado, lado), (0xff, 0xff, 0xff)),
             (0, 0), brilho.filter(ImageFilter.GaussianBlur(lado * 0.05)))

    cl = round(lado * 0.38)
    ca = round(cl * 1.45)
    cx = round(lado * 0.211)
    cy = round(lado * 0.160)
    case = _case(cl, ca)

    sombra = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    sombra.paste((0, 0, 0, 125), (cx, cy + round(lado * 0.022)),
                 case.getchannel("A"))
    im.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(lado * 0.024)))
    im.alpha_composite(case, (cx, cy))

    # o badge monta no canto da caixa, como ele monta na capa de verdade
    bl = round(lado * 0.36)
    b = badge("platinado", CORES["platinado"], lado=bl)
    im.alpha_composite(b, (cx + cl - bl // 2, cy + ca - bl // 2))

    im.putalpha(_squircle(lado))
    return im


# ------------------------------------------------------------- a sua arte

def quadrar(caminho, lado=MESTRE):
    """
    Deixa uma imagem qualquer pronta pra virar icone.

    Tira o fundo branco das bordas (um PNG exportado de editor quase
    sempre vem com ele), e so entao mede: se o desenho nao for quadrado,
    a diferenca e dividida nos dois eixos, metade pra cada. Esticar so um
    lado deforma circulo; dividir deixa o erro pela metade e invisivel.
    """
    from collections import deque

    im = Image.open(caminho).convert("RGBA")
    W, H = im.size
    px = im.load()

    def claro(p):
        return p[3] > 10 and p[0] >= 238 and p[1] >= 238 and p[2] >= 238

    # alagamento a partir das bordas: so o branco de FORA sai. O branco de
    # dentro do desenho (um check, um brilho) nao e alcancado e fica.
    visto = bytearray(W * H)
    dq = deque()
    for x in range(W):
        for y in (0, H - 1):
            if claro(px[x, y]) and not visto[y * W + x]:
                visto[y * W + x] = 1
                dq.append((x, y))
    for y in range(H):
        for x in (0, W - 1):
            if claro(px[x, y]) and not visto[y * W + x]:
                visto[y * W + x] = 1
                dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and not visto[ny * W + nx] and claro(px[nx, ny]):
                visto[ny * W + nx] = 1
                dq.append((nx, ny))
    for y in range(H):
        base = y * W
        for x in range(W):
            if visto[base + x]:
                px[x, y] = (0, 0, 0, 0)

    corte = im.getbbox()
    if corte:
        im = im.crop(corte)
    return im.resize((lado, lado), Image.LANCZOS)


# --------------------------------------------------------------- gravar

def _ico(im, caminho, tamanhos=NO_ICO):
    """
    Monta o .ico na mao.

    O Pillow sabe gravar ICO, mas grava TODOS os tamanhos como PNG - e a
    convencao do formato e outra: so o de 256 vai comprimido, os menores
    vao como DIB, bitmap cru. Um .ico todo em PNG abre num visualizador e
    parece certo, e por isso o erro passa despercebido; o que acontece e
    o Windows nao desenhar o icone em parte dos lugares.

    `bitmap_format="bmp"` resolveria metade do problema, mas aplica a
    todos os tamanhos: o de 256 sairia cru, com uns 260 KB so dele.
    """
    quadros = []
    for s in sorted(set(tamanhos)):
        buf = io.BytesIO()
        quadro = im.resize((s, s), Image.LANCZOS)
        if s >= 256:
            quadro.save(buf, "png")
            corpo = buf.getvalue()
        else:
            quadro.save(buf, "dib")
            cru = buf.getvalue()
            # dentro do .ico a altura do cabecalho conta a mascara AND
            # junto, entao vai dobrada. Com 32 bits o alfa ja diz o que e
            # transparente e a mascara nao precisa existir.
            corpo = cru[:8] + struct.pack("<I", s * 2) + cru[12:]
        quadros.append((s, corpo))

    with open(caminho, "wb") as fp:
        fp.write(struct.pack("<HHH", 0, 1, len(quadros)))   # ICONDIR
        pos = 6 + 16 * len(quadros)
        for s, corpo in quadros:
            lado = 0 if s >= 256 else s                     # 0 quer dizer 256
            fp.write(struct.pack("<BBBBHHII",
                                 lado, lado, 0, 0, 1, 32, len(corpo), pos))
            pos += len(corpo)
        for _, corpo in quadros:
            fp.write(corpo)
    return caminho


def gravar(im, nome, destino=DESTINO):
    os.makedirs(destino, exist_ok=True)
    png = os.path.join(destino, f"{nome}.png")
    ico = os.path.join(destino, f"{nome}.ico")
    im.resize((JANELA, JANELA), Image.LANCZOS).save(png)
    _ico(im, ico)
    return png, ico


def main(argv):
    if len(argv) > 1:
        origem = argv[1]
        if not os.path.exists(origem):
            print(f"nao achei: {origem}")
            return 1
        png, ico = gravar(quadrar(origem), "vitrine")
        print(f"a sua arte virou icone:\n  {png}\n  {ico}")
        print("\nEla vence o padrao na janela e no exe, e fica fora do git.")
    else:
        png, ico = gravar(desenhar_padrao(), "padrao")
        print(f"icone padrao desenhado:\n  {png}\n  {ico}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
