#!/usr/bin/env python3
"""
Adesivos de qualificador (free, demo, trial). Arte original, MIT.

Quatro formatos, todos desenhados por codigo para escalar sem perder nitidez:
    selo       - circulo serrilhado, estilo carimbo de promocao
    faixa      - faixa diagonal atravessando o canto
    etiqueta   - retangulo arredondado, estilo etiqueta de preco
    rosacea    - circulo com fita horizontal atravessando
"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter

K = 4
FONTES = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
          "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf")


def _fonte(tam):
    from PIL import ImageFont
    for c in FONTES:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, tam)
            except Exception:
                pass
    return None


def _cabe(d, texto, largura, teto):
    """Maior corpo de fonte em que `texto` cabe em `largura`."""
    for tam in range(teto, 8, -2):
        f = _fonte(tam)
        if f is None:
            return None, 0
        if d.textlength(texto, font=f) <= largura:
            return f, tam
    return _fonte(10), 10


def _sombra(im, raio=6, desloc=(0, 5), forca=120):
    """Sombra projetada: e o que faz parecer colado por cima, nao impresso."""
    a = im.getchannel("A").filter(ImageFilter.GaussianBlur(raio))
    a = a.point(lambda v: min(255, v * forca // 100))
    s = Image.new("RGBA", im.size, (0, 0, 0, 0))
    s.putalpha(a)
    fora = Image.new("RGBA", im.size, (0, 0, 0, 0))
    fora.alpha_composite(s, desloc)
    fora.alpha_composite(im)
    return fora


def selo(texto="FREE", cor=(0x1f, 0x1f, 0x1f), tinta=(255, 255, 255),
         tam=170, pontas=12, giro=-12):
    """Circulo serrilhado com o texto no meio."""
    S = tam * K
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = cy = S / 2
    r_out, r_in = S * 0.48, S * 0.405
    pts = []
    passos = pontas * 2
    for i in range(passos):
        ang = 2 * math.pi * i / passos - math.pi / 2
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d.polygon(pts, fill=tuple(cor) + (255,))

    f, _ = _cabe(d, texto, S * 0.68, int(S * 0.30))
    if f:
        d.text((cx, cy), texto, font=f, anchor="mm", fill=tuple(tinta) + (255,))
    im = im.resize((tam, tam), Image.LANCZOS)
    if giro:
        im = im.rotate(giro, resample=Image.BICUBIC, expand=True)
    return _sombra(im)


def etiqueta(texto="FREE", cor=(0x1f, 0x7a, 0x4d), tinta=(255, 255, 255),
             larg=184, alt=72, giro=-8):
    """Retangulo arredondado, estilo etiqueta adesiva."""
    W, H = larg * K, alt * K
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=H * 0.26,
                        fill=tuple(cor) + (255,))
    d.rounded_rectangle([W * 0.035, H * 0.07, W * 0.965, H * 0.93],
                        radius=H * 0.20, outline=(255, 255, 255, 110),
                        width=max(2, K))
    f, _ = _cabe(d, texto, W * 0.80, int(H * 0.62))
    if f:
        d.text((W / 2, H / 2), texto, font=f, anchor="mm", fill=tuple(tinta) + (255,))
    im = im.resize((larg, alt), Image.LANCZOS)
    if giro:
        im = im.rotate(giro, resample=Image.BICUBIC, expand=True)
    return _sombra(im)


def faixa_diagonal(texto="FREE", cor=(0xf2, 0x8b, 0x50), tinta=(255, 255, 255),
                   tam=210, canto="tr"):
    """
    Faixa atravessando o canto, de uma borda a outra - como as cintas de
    promocao que vem coladas na caixa. Sai sempre a 45 graus.
    """
    S = tam * K
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d1, d2 = S * 0.40, S * 0.76          # onde a faixa cruza cada borda
    d.polygon([(S - d2, 0), (S - d1, 0), (S, d1), (S, d2)],
              fill=tuple(cor) + (255,))
    # fio claro nas duas bordas da faixa, para destacar da arte
    for a, b in (((S - d2, 0), (S, d2)), ((S - d1, 0), (S, d1))):
        d.line([a, b], fill=(255, 255, 255, 90), width=max(2, K))

    larg_faixa = (d2 - d1) / math.sqrt(2)
    comp = math.hypot(S, S) * 0.62
    txt = Image.new("RGBA", (int(comp), int(larg_faixa)), (0, 0, 0, 0))
    td = ImageDraw.Draw(txt)
    f, _ = _cabe(td, texto, comp * 0.80, int(larg_faixa * 0.70))
    if f:
        td.text((comp / 2, larg_faixa / 2), texto, font=f, anchor="mm",
                fill=tuple(tinta) + (255,))
    txt = txt.rotate(-45, resample=Image.BICUBIC, expand=True)
    # centro geometrico da faixa fica na diagonal, a meio caminho
    cx, cy = S - (d1 + d2) / 4, (d1 + d2) / 4
    im.alpha_composite(txt, (int(cx - txt.width / 2), int(cy - txt.height / 2)))

    out = im.resize((tam, tam), Image.LANCZOS)
    if canto == "tl":
        out = out.transpose(Image.FLIP_LEFT_RIGHT)
    return _sombra(out, desloc=(0, 4), forca=80)


def rosacea(texto="FREE", cor=(0x8b, 0x5c, 0xd6), fita=(0x6d, 0x3f, 0xc0),
            tinta=(255, 255, 255), tam=180, giro=-10):
    """Disco com uma fita horizontal atravessando, estilo medalha."""
    S = tam * K
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = cy = S / 2
    r = S * 0.44
    pts = []
    passos = 36
    for i in range(passos):
        ang = 2 * math.pi * i / passos
        rr = r if i % 2 == 0 else r * 0.93
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d.polygon(pts, fill=tuple(cor) + (255,))
    d.ellipse([cx - r * 0.80, cy - r * 0.80, cx + r * 0.80, cy + r * 0.80],
              fill=tuple(c + 18 if c + 18 < 255 else 255 for c in cor) + (255,))
    fh = S * 0.30
    d.polygon([(0, cy - fh / 2), (S, cy - fh / 2), (S, cy + fh / 2), (0, cy + fh / 2)],
              fill=tuple(fita) + (255,))
    f, _ = _cabe(d, texto, S * 0.86, int(fh * 0.72))
    if f:
        d.text((cx, cy), texto, font=f, anchor="mm", fill=tuple(tinta) + (255,))
    im = im.resize((tam, tam), Image.LANCZOS)
    if giro:
        im = im.rotate(giro, resample=Image.BICUBIC, expand=True)
    return _sombra(im)


FORMATOS = {"selo": selo, "etiqueta": etiqueta,
            "faixa": faixa_diagonal, "rosacea": rosacea}


def construir(formato, texto, **kw):
    return FORMATOS[formato](texto=texto, **kw)


def gerar_do_config(caminho="config.json", saida="adesivos"):
    """
    Le config.json e gera um PNG para cada camada do tipo "adesivo".
    Uma fonte de verdade so: o config manda, o gerador obedece.
    """
    import json
    with open(caminho, encoding="utf-8-sig") as f:
        cfg = json.load(f)
    os.makedirs(saida, exist_ok=True)
    feitos = []
    for nome, c in (cfg.get("camadas") or {}).items():
        if not isinstance(c, dict) or c.get("tipo") != "adesivo":
            continue
        formato = c.get("formato", "selo")
        if formato not in FORMATOS:
            print(f"[!] {nome}: formato '{formato}' nao existe; usando selo")
            formato = "selo"
        kw = {}
        for k in ("cor", "tinta", "tam", "giro", "pontas", "larg", "alt", "fita"):
            if k in c:
                kw[k] = tuple(c[k]) if isinstance(c[k], list) else c[k]
        img = FORMATOS[formato](texto=c.get("texto", nome.upper()), **kw)
        img.save(f"{saida}/{nome}.png")
        feitos.append(f"{nome} ({formato}, {img.width}x{img.height})")
    return feitos


if __name__ == "__main__":
    feitos = gerar_do_config()
    if feitos:
        print("adesivos gerados:", ", ".join(feitos))
    else:
        print("nenhuma camada do tipo 'adesivo' no config.json")
        os.makedirs("adesivos", exist_ok=True)
        for nome, fn in FORMATOS.items():
            fn(texto="FREE").save(f"adesivos/exemplo_{nome}.png")
        print("gravei exemplos em adesivos/ para voce comparar os formatos")
