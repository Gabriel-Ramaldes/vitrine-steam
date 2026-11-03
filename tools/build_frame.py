#!/usr/bin/env python3
"""
Molduras do steam_badge. Arte original, licenca MIT.

Referencia: caixa plastica de jogo com acabamento "2.5D" - o volume nao vem
de perspectiva, e sim de biseis glossy (faixas claras simulando luz em
plastico arredondado) nas quatro bordas, mais meio-tom na faixa superior.
Tudo desenhado por codigo; nenhum pixel vem de outro arquivo.

    molduras/case.png       caixa normal
    molduras/case_ouro.png  caixa dourada (platinado)
    molduras/scrim.png      degrade na base, contraste para os badges
    molduras/ribbon.png     fita de 100%
    molduras/family.png     canto da biblioteca Family

molduras/logo.png e opcional e NAO acompanha o projeto.
"""
import math
import os
from PIL import Image, ImageChops, ImageDraw, ImageFilter

SIZE = (600, 900)
K = 3

HEADER = 90          # do topo ate o inicio da arte
BORDA = 13           # borda externa, igual nos quatro lados
BASE = 18            # borda inferior
RAIO = 14

AJUSTE_2_3 = False   # True: arte em 2:3 exato, com margem; False: preenche

PONTO_PASSO = 9      # meio-tom do header
PONTO_R = 3.3
PONTO_ALCANCE = 215  # ate onde os pontos aparecem, a partir da esquerda

AZUL = dict(corpo=(0x07, 0x26, 0x67), corpo2=(0x05, 0x35, 0x64),
            glow=(0x00, 0xa2, 0xff), brilho=(0x89, 0xd9, 0xea),
            escuro=(0x01, 0x00, 0x97), ponto=(0x2f, 0x7f, 0xc4),
            vinco=(0x03, 0x12, 0x3a))
OURO = dict(corpo=(0x6a, 0x4c, 0x05), corpo2=(0x7d, 0x5d, 0x08),
            glow=(0xff, 0xd0, 0x3a), brilho=(0xff, 0xf0, 0xbe),
            escuro=(0x4a, 0x31, 0x00), ponto=(0xc9, 0xa2, 0x3e),
            vinco=(0x2e, 0x1f, 0x01))

LOGO = "molduras/logo.png"
SCRIM = 240


def janela():
    """Area da arte, sempre centralizada na horizontal."""
    y0, y1 = HEADER, SIZE[1] - BASE
    larg = SIZE[0] - 2 * BORDA
    if AJUSTE_2_3:
        larg = min(larg, round((y1 - y0) * 2 / 3))
    x0 = (SIZE[0] - larg) // 2
    return (x0, y0, x0 + larg, y1)


def _mask(tam, raio, escala=K):
    m = Image.new("L", (tam[0] * escala, tam[1] * escala), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        [0, 0, tam[0] * escala - 1, tam[1] * escala - 1], radius=raio * escala, fill=255)
    return m.resize(tam, Image.LANCZOS)


def _rampa(n, paradas):
    """Lista de n cores interpolando entre (posicao 0..1, cor)."""
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        for j in range(len(paradas) - 1):
            p0, c0 = paradas[j]
            p1, c1 = paradas[j + 1]
            if p0 <= t <= p1:
                u = (t - p0) / max(1e-6, p1 - p0)
                out.append(tuple(round(c0[k] * (1 - u) + c1[k] * u) for k in range(3)))
                break
        else:
            out.append(paradas[-1][1])
    return out


def _bisel(largura, cor, invertido=False):
    """
    Perfil de luz de uma aresta de plastico arredondada: escuro na quina,
    pico claro no meio, escuro de novo. E isso que da a sensacao de volume.
    """
    paradas = [(0.00, cor["escuro"]), (0.18, (4, 40, 150) if "0" else cor["escuro"]),
               (0.45, cor["glow"]), (0.62, cor["brilho"]),
               (0.78, cor["glow"]), (1.00, cor["corpo"])]
    cores = _rampa(largura, paradas)
    return cores[::-1] if invertido else cores


def _meio_tom(d, cor, altura):
    """Pontos que vao sumindo da esquerda para a direita."""
    for gx in range(0, PONTO_ALCANCE * K, PONTO_PASSO * K):
        t = gx / (PONTO_ALCANCE * K)
        queda = max(0.0, 1 - t) ** 1.35
        a = round(165 * queda)
        if a <= 2:
            continue
        r = PONTO_R * K * (0.45 + 0.55 * queda)      # o ponto encolhe junto
        for gy in range(PONTO_PASSO * K // 2, altura * K, PONTO_PASSO * K):
            desloc = (PONTO_PASSO * K // 2) if (gy // (PONTO_PASSO * K)) % 2 else 0
            x = gx + desloc
            d.ellipse([x - r, gy - r, x + r, gy + r], fill=cor["ponto"] + (a,))


def build_case(cor=None):
    """
    A caixa inteira. O bisel e feito de retangulos arredondados concentricos,
    um por pixel de profundidade: assim ele da a volta e se encontra em
    meia-esquadria nos cantos, sem as emendas duras que tiras independentes
    deixavam na juncao da lateral com o header e com a base.
    """
    cor = cor or AZUL
    w, h = SIZE[0] * K, SIZE[1] * K
    im = Image.new("RGBA", (w, h), cor["corpo"] + (255,))
    d = ImageDraw.Draw(im)

    jx0, jy0, jx1, jy1 = [v * K for v in janela()]

    # ---- faixa superior ----
    topo_y = BORDA * K
    for y, c in enumerate(_rampa(jy0 - topo_y, [(0, cor["corpo"]), (1, cor["corpo2"])])):
        d.line([(0, topo_y + y), (w, topo_y + y)], fill=c + (255,))

    pontos = Image.new("RGBA", (w, jy0 - topo_y), (0, 0, 0, 0))
    _meio_tom(ImageDraw.Draw(pontos), cor, (jy0 - topo_y) // K)
    im.alpha_composite(pontos, (0, topo_y))

    # clareia para a direita
    veu = Image.new("RGBA", (w, jy0 - topo_y), cor["glow"] + (0,))
    fx = Image.new("L", (w, 1))
    for x in range(w):
        fx.putpixel((x, 0), round(64 * (x / (w - 1)) ** 0.75))
    veu.putalpha(fx.resize((w, jy0 - topo_y)))
    im.alpha_composite(veu, (0, topo_y))

    if os.path.exists(LOGO):
        logo = Image.open(LOGO).convert("RGBA")
        alt = 40 * K
        larg = max(1, round(logo.width * alt / logo.height))
        im.alpha_composite(logo.resize((larg, alt), Image.LANCZOS),
                           ((w - larg) // 2, topo_y + (jy0 - topo_y - alt) // 2))

    # ---- bisel externo: da a volta inteira ----
    larg_b = BORDA * K
    for i, c in enumerate(_bisel(larg_b, cor)):
        r = max(1, RAIO * K - i)
        d.rounded_rectangle([i, i, w - 1 - i, h - 1 - i], radius=r,
                            outline=c + (255,), width=1)

    # ---- bisel interno: desce para a arte, sem risco preto ----
    # escurecimento curto e suave: sugere que a arte esta por baixo do
    # plastico, sem virar um risco preto na juncao
    prof = 4 * K
    dentro = _rampa(prof, [(0, cor["corpo"]),
                           (1, tuple(max(0, v - 30) for v in cor["corpo"]))])
    for i, c in enumerate(dentro):
        j = prof - 1 - i
        d.rounded_rectangle([jx0 - 1 - j, jy0 - 1 - j, jx1 + j, jy1 + j],
                            radius=max(1, 4 * K - j // 2), outline=c + (255,), width=1)

    # fio de luz na divisa header/arte: e o que separa os dois blocos sem
    # precisar de sombra escura
    d.rectangle([jx0 - 2 * K, jy0 - 3 * K, jx1 + 2 * K - 1, jy0 - 1],
                fill=cor["glow"] + (255,))

    im = im.resize(SIZE, Image.LANCZOS)
    im.putalpha(_mask(SIZE, RAIO))

    x0, y0, x1, y1 = janela()
    buraco = Image.new("L", SIZE, 255)
    ImageDraw.Draw(buraco).rectangle([x0, y0, x1 - 1, y1 - 1], fill=0)
    im.putalpha(ImageChops.multiply(im.getchannel("A"), buraco))
    return im


def build_scrim():
    x0, y0, x1, y1 = janela()
    im = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    col = Image.new("L", (1, SCRIM))
    for i in range(SCRIM):
        col.putpixel((0, i), round(215 * ((i / (SCRIM - 1)) ** 0.85)))
    bloco = Image.new("RGBA", (x1 - x0, SCRIM), (0, 0, 0, 0))
    bloco.putalpha(col.resize((x1 - x0, SCRIM)))
    im.alpha_composite(bloco, (x0, y1 - SCRIM))
    return im


RIBBON_TEXTO = "100%"
FONTES = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
          "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf")


def _fonte(t):
    from PIL import ImageFont
    for c in FONTES:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, t)
            except Exception:
                pass
    return None


# paletas do ribbon
RIB_STEAM = dict(corpo=(0x1a, 0x9f, 0xff), ponta=(0x14, 0x77, 0xdb),
                 topo=(0x5c, 0xbb, 0xff), sombra=(0, 0x3c, 0x70))
RIB_OURO = dict(corpo=(0xe8, 0xb4, 0x2a), ponta=(0xa8, 0x76, 0x08),
                topo=(0xff, 0xe2, 0x8a), sombra=(0x5e, 0x3f, 0x02))


def build_ribbon(pal=None, icone=None):
    """
    Fita de 100%, nas cores da Steam. A ponta esquerda e desenhada uma vez
    e espelhada para a direita - garante simetria exata, que e onde a
    versao anterior errava.
    """
    w, alt = SIZE[0], 82
    cy0, cy1 = 16 * K, 66 * K
    aba, dobra, entalhe = 56 * K, 11 * K, 22 * K

    # --- ponta esquerda, num quadro proprio ---
    pal = pal or RIB_STEAM
    ponta = Image.new("RGBA", (aba, alt * K), (0, 0, 0, 0))
    ImageDraw.Draw(ponta).polygon(
        [(0, cy0 - dobra), (aba, cy0), (aba, cy1), (0, cy1 + dobra),
         (entalhe, (cy0 + cy1) // 2)], fill=pal["ponta"] + (255,))

    im = Image.new("RGBA", (w * K, alt * K), (0, 0, 0, 0))
    im.alpha_composite(ponta, (0, 0))
    im.alpha_composite(ponta.transpose(Image.FLIP_LEFT_RIGHT), (w * K - aba, 0))

    # --- corpo ---
    d = ImageDraw.Draw(im)
    x0, x1 = aba - 16 * K, w * K - aba + 16 * K
    for i, c in enumerate(_rampa(cy1 - cy0, [(0, pal["topo"]), (0.35, pal["corpo"]),
                                             (1, pal["ponta"])])):
        d.line([(x0, cy0 + i), (x1, cy0 + i)], fill=c + (255,))
    d.rectangle([x0, cy0, x1, cy0 + 3 * K], fill=(255, 255, 255, 120))

    f = _fonte(34 * K)
    if f:
        cx, cy = w * K // 2, (cy0 + cy1) // 2
        d.text((cx, cy + 2 * K), RIBBON_TEXTO, font=f, anchor="mm",
               fill=pal["sombra"] + (110,))
        d.text((cx, cy), RIBBON_TEXTO, font=f, anchor="mm", fill=(255, 255, 255, 255))

    im = im.resize((w, alt), Image.LANCZOS)

    # icone do platinado na ponta esquerda, como a roseta que a Steam poe
    if icone and os.path.exists(icone):
        ic = Image.open(icone).convert("RGBA")
        lado = alt + 14                       # transborda um pouco a fita
        ic = ic.resize((lado, lado), Image.LANCZOS)
        im_maior = Image.new("RGBA", (w, lado), (0, 0, 0, 0))
        im_maior.alpha_composite(im, (0, (lado - alt) // 2))
        im_maior.alpha_composite(ic, (10, 0))
        return im_maior
    return im


def build_corner(cor, canto="tl", lado=150):
    """
    Triangulo de canto, no estilo do canto Family. `canto`: tl, tr, bl, br.
    O icone e composto por cima depois, pelo chamador.
    """
    w, h = SIZE
    im = Image.new("RGBA", (w * K, h * K), (0, 0, 0, 0))
    L = lado * K
    pts = {"tl": [(0, 0), (L, 0), (0, L)],
           "tr": [(w * K, 0), (w * K - L, 0), (w * K, L)],
           "bl": [(0, h * K), (L, h * K), (0, h * K - L)],
           "br": [(w * K, h * K), (w * K - L, h * K), (w * K, h * K - L)]}[canto]
    ImageDraw.Draw(im).polygon(pts, fill=tuple(cor) + (255,))
    im = im.resize(SIZE, Image.LANCZOS)
    im.putalpha(ImageChops.multiply(im.getchannel("A"), _mask(SIZE, RAIO)))
    return im


def ponto_icone_canto(canto="tl", lado=150, tam=56):
    """
    Canto superior esquerdo do icone, para que o CENTRO dele caia no
    miolo do triangulo (a 0.30 do vertice nos dois eixos). Sem isso o
    icone escorrega para fora da hipotenusa.
    """
    w, h = SIZE
    d = lado * 0.30
    cx, cy = {"tl": (d, d), "tr": (w - d, d),
              "bl": (d, h - d), "br": (w - d, h - d)}[canto]
    return (round(cx - tam / 2), round(cy - tam / 2))


def build_family():
    w, h = SIZE
    im = Image.new("RGBA", (w * K, h * K), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lado = 150 * K
    d.polygon([(0, 0), (lado, 0), (0, lado)], fill=(0x2e, 0x7d, 0x32, 255))

    def fig(cx, cy, r):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255))
        d.pieslice([cx - r * 1.6, cy + r * 0.2, cx + r * 1.6, cy + r * 3.4], 180, 360,
                   fill=(255, 255, 255, 255))
    fig(42 * K, 40 * K, 11 * K)
    fig(74 * K, 32 * K, 9 * K)
    fig(26 * K, 66 * K, 9 * K)
    im = im.resize(SIZE, Image.LANCZOS)
    im.putalpha(ImageChops.multiply(im.getchannel("A"), _mask(SIZE, RAIO)))
    return im


def escrever_geometria(caminho="molduras/geometria.json"):
    """
    Publica as medidas para o steam_badge.py consumir, para que o script
    nao precise reimplementar nem adivinhar a geometria da moldura.
    """
    import json
    x0, y0, x1, y1 = janela()
    dados = {
        "tamanho": list(SIZE),
        "janela": [x0, y0, x1, y1],
        "header": HEADER,
        "canto_lado": 164,
        "canto_icone": 60,
        "badge_lado": 104,
        "badge_margem": 22,
        "ajuste_2_3": AJUSTE_2_3,
    }
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)
    return dados


def gerar(destino="molduras"):
    """
    Escreve as molduras em `destino` e devolve os nomes gerados.

    Existe pra que a aplicacao chame isto direto, com caminho absoluto, em
    vez de depender do diretorio corrente - rodar via subprocesso quebra
    quando o programa esta congelado pelo PyInstaller.
    """
    d = str(destino)
    os.makedirs(d, exist_ok=True)
    feitos = []
    build_case(AZUL).save(os.path.join(d, "case.png")); feitos.append("case")
    build_case(OURO).save(os.path.join(d, "case_ouro.png")); feitos.append("case_ouro")
    build_scrim().save(os.path.join(d, "scrim.png")); feitos.append("scrim")
    # icone da fita de 100%: o seu primeiro, o do conjunto padrao depois.
    # Sem o fallback, um clone limpo ficaria com a fita sem icone, porque
    # icone_ribbon.png e copia de um badge pessoal e nao vai no repo.
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ic = None
    for cand in (os.path.join(d, "icone_ribbon.png"),
                 os.path.join(raiz, "badges", "platinado.png"),
                 os.path.join(raiz, "badges_padrao", "platinado.png")):
        if os.path.exists(cand):
            ic = cand
            break
    build_ribbon(RIB_STEAM, ic).save(
        os.path.join(d, "ribbon.png")); feitos.append("ribbon")
    build_family().save(os.path.join(d, "family.png")); feitos.append("family")
    escrever_geometria(os.path.join(d, "geometria.json")); feitos.append("geometria.json")
    return feitos


if __name__ == "__main__":
    feitos = gerar()
    print("gerados:", ", ".join(feitos))
    j = janela()
    print("janela:", j, "->", j[2]-j[0], "x", j[3]-j[1],
          "proporcao", round((j[2]-j[0])/(j[3]-j[1]), 4),
          "| 2:3 exato" if AJUSTE_2_3 else "| preenche (corta a arte)")
