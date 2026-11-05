"""
Testes da escada de assets.

badges, molduras, adesivos e icone seguem todos a mesma regra:

    <subpasta>/          a sua, ao lado do programa - vence
    assets/<subpasta>/   a que vem no repositorio
    assets/<subpasta>/   embutida no exe (sys._MEIPASS)

E uma regra facil de quebrar sem ninguem notar: o degrau embutido so
existe quando o programa esta congelado, entao um erro ali passa batido
em todo teste feito a partir do codigo-fonte e so aparece pra quem
baixou o exe.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import core


def arrumar(raiz, propria=(), assets=(), embutido=()):
    """
    Monta os tres degraus e aponta o core pra eles.

    propria   o que o usuario poe ao lado do programa  -> raiz/<rel>
    assets    o que vem no repositorio                 -> raiz/assets/<rel>
    embutido  o que viaja dentro do exe                -> meipass/assets/<rel>
    """
    raiz.mkdir(parents=True, exist_ok=True)
    meipass = raiz / "_meipass"
    grupos = ((propria, raiz), (assets, raiz / "assets"),
              (embutido, meipass / "assets"))
    for arquivos, base in grupos:
        for rel in arquivos:
            p = base / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"conteudo")

    core.BASE_DIR = raiz
    if embutido:
        sys._MEIPASS = str(meipass)
    elif hasattr(sys, "_MEIPASS"):
        del sys._MEIPASS
    # as leituras de moldura e adesivo sao cacheadas; trocar de raiz sem
    # limpar faria um teste enxergar o arquivo do anterior
    core.geometria_moldura.cache_clear()
    core._peca.cache_clear()
    core._adesivo.cache_clear()
    return raiz


# ------------------------------------------------------------------ badges

def t_badge_sua_pasta_vence(tmp):
    raiz = arrumar(tmp / "b1",
                   propria=["badges/zerado.png"],
                   assets=["badges/zerado.png"])
    achado = core.achar_badge(raiz / "badges", "zerado")
    assert achado.parent.name == "badges" and "assets" not in str(achado), achado
    return "badge: a sua pasta vence o repositorio"


def t_badge_cai_no_assets(tmp):
    raiz = arrumar(tmp / "b2", assets=["badges/zerado.png"])
    (raiz / "badges").mkdir(exist_ok=True)
    achado = core.achar_badge(raiz / "badges", "zerado")
    assert achado is not None and "assets" in str(achado), achado
    return "badge: sem a sua, usa assets/badges"


def t_badge_embutido(tmp):
    """O caso do exe solto: nenhuma pasta ao lado, so o que esta dentro."""
    raiz = arrumar(tmp / "b3", embutido=["badges/platinado.png"])
    achado = core.achar_badge(raiz / "badges", "platinado")
    assert achado is not None and "_meipass" in str(achado), achado
    return "badge: sem pasta ao lado, acha o embutido no exe"


def t_badge_aceita_webp(tmp):
    raiz = arrumar(tmp / "b4", assets=["badges/online.webp"])
    assert core.achar_badge(raiz / "badges", "online") is not None
    return "badge: webp e gif tambem valem"


# ------------------------------------------------------------------ icone

def t_icone_vitrine_vence_padrao(tmp):
    arrumar(tmp / "i1", assets=["icone/vitrine.png", "icone/padrao.png"])
    assert core.achar_icone(".png").name == "vitrine.png"
    return "icone: vitrine vence padrao"


def t_icone_extensao_separada(tmp):
    """Pedir .ico nao pode devolver .png: o Windows rejeita."""
    arrumar(tmp / "i2", assets=["icone/vitrine.png"])
    assert core.achar_icone(".png") is not None
    assert core.achar_icone(".ico") is None, "devolveu png quando pediram ico"
    return "icone: .ico e .png nao se misturam"


def t_icone_ausente_nao_quebra(tmp):
    arrumar(tmp / "i3")
    assert core.achar_icone(".png") is None
    assert core.achar_icone(".ico") is None
    return "icone: ausencia devolve None, sem excecao"


# --------------------------------------------------------------- molduras

def t_moldura_sua_pasta_vence(tmp):
    arrumar(tmp / "m1",
            propria=["molduras/case.png"],
            assets=["molduras/case.png"])
    achado = core.peca_moldura("case.png")
    assert "assets" not in str(achado), achado
    return "moldura: a sua pasta vence o repositorio"


def t_moldura_peca_a_peca(tmp):
    """
    A escada e por ARQUIVO, nao por pasta: quem gerou so metade das
    pecas continua usando as que vieram no repositorio pro resto.
    """
    arrumar(tmp / "m2",
            propria=["molduras/case.png"],
            assets=["molduras/case.png", "molduras/scrim.png"])
    assert "assets" not in str(core.peca_moldura("case.png"))
    assert "assets" in str(core.peca_moldura("scrim.png"))
    return "moldura: mistura a sua peca com a do repositorio"


def t_moldura_faltando_olha_os_dois(tmp):
    arrumar(tmp / "m3", assets=[f"molduras/{n}" for n in core.PECAS_MOLDURA])
    assert core.molduras_faltando() == [], core.molduras_faltando()
    arrumar(tmp / "m4", assets=["molduras/case.png"])
    faltam = core.molduras_faltando()
    assert "case.png" not in faltam and "scrim.png" in faltam, faltam
    return "moldura: o que falta conta os dois degraus"


def t_geometria_do_assets(tmp):
    raiz = arrumar(tmp / "m5")
    (raiz / "assets" / "molduras").mkdir(parents=True)
    (raiz / "assets" / "molduras" / "geometria.json").write_text(
        json.dumps({"tamanho": [600, 900]}), encoding="utf-8")
    core.geometria_moldura.cache_clear()
    g = core.geometria_moldura()
    assert g and g["tamanho"] == [600, 900], g
    return "moldura: geometria.json tambem desce a escada"


# --------------------------------------------------------------- adesivos

def t_adesivo_desce_a_escada(tmp):
    arrumar(tmp / "a1", assets=["adesivos/free.png"])
    assert core.achar_arte("adesivos", "free") is not None
    assert core.achar_arte("adesivos", "demo") is None
    return "adesivo: cai no assets quando a sua pasta nao tem"


def main():
    base = core.BASE_DIR
    testes = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    falhas = 0
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for t in testes:
            try:
                print(f"  ok   {t(tmp)}")
            except Exception as e:
                falhas += 1
                print(f"  FALHA {t.__name__}: {type(e).__name__}: {e}")
    core.BASE_DIR = base
    if hasattr(sys, "_MEIPASS"):
        del sys._MEIPASS
    print(f"\n{len(testes) - falhas}/{len(testes)} passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
