"""Testes da galeria. Nenhuma chamada de rede e nenhuma janela."""
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import core
import galeria as G
from PIL import Image


def png(w=600, h=900, cor=(40, 80, 160)):
    b = io.BytesIO()
    Image.new("RGB", (w, h), cor).save(b, "PNG")
    return b.getvalue()


def jpg(w=600, h=900):
    b = io.BytesIO()
    Image.new("RGB", (w, h), (10, 150, 90)).save(b, "JPEG")
    return b.getvalue()


# ---- miniatura e conversao ---------------------------------------------

def t_miniatura_sai_em_png_base64(tmp):
    import base64
    b64 = G.miniatura(jpg(600, 900), largura=100)
    bruto = base64.b64decode(b64)
    assert bruto[:8] == b"\x89PNG\r\n\x1a\n", "tk so le PNG"
    im = Image.open(io.BytesIO(bruto))
    assert im.size == (100, 150), im.size
    return "miniatura sai PNG em base64, na proporcao, pronta pro Tk"


def t_converte_jpg_e_webp(tmp):
    for dados in (jpg(), png()):
        saida = G._png(dados)
        assert saida[:8] == b"\x89PNG\r\n\x1a\n"
    return "jpg da SGDB e convertido pra PNG ao adotar"


# ---- adocao -------------------------------------------------------------

def t_adotar_grava_em_capas(tmp):
    d = tmp / "a"
    f = G.adotar_bytes(440, jpg(600, 900), pasta=d)
    assert f == d / "440.png" and f.exists()
    assert f.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    return "adotar grava capas/<appid>.png convertido"


def t_recusa_imagem_que_nao_e_capa(tmp):
    d = tmp / "b"
    for w, h in ((900, 600), (64, 64)):
        try:
            G.adotar_bytes(440, png(w, h), pasta=d)
        except ValueError as e:
            assert "vertical" in str(e), e
        else:
            raise AssertionError(f"{w}x{h} devia ter sido recusada")
    assert not (d / "440.png").exists()
    return "imagem horizontal ou quadrada e recusada antes de gravar"


def t_recusa_lixo(tmp):
    try:
        G.adotar_bytes(440, b"isto nao e imagem", pasta=tmp / "c")
    except (ValueError, Exception):
        return "arquivo que nao e imagem nao entra"
    raise AssertionError("devia ter recusado")


def t_adotar_remove_extensao_antiga(tmp):
    d = tmp / "d"; d.mkdir(parents=True)
    (d / "440.jpg").write_bytes(jpg())
    G.adotar_bytes(440, png(), pasta=d)
    assert (d / "440.png").exists()
    assert not (d / "440.jpg").exists(), "duas capas pro mesmo appid e ambiguo"
    return "adotar limpa a capa antiga em outra extensao"


def t_adotar_url_usa_o_baixador_injetado(tmp):
    chamadas = []
    def baixar(url, timeout=None, headers=None):
        chamadas.append(url)
        return jpg()
    f = G.adotar_url(440, "https://exemplo/x.jpg", pasta=tmp / "e", baixar=baixar)
    assert f.exists() and chamadas == ["https://exemplo/x.jpg"]
    return "adotar por url usa o baixador injetado (teste sem rede)"


def t_adotar_arquivo_do_disco(tmp):
    d = tmp / "f"; d.mkdir(parents=True)
    orig = d / "minha.png"; orig.write_bytes(png())
    f = G.adotar_arquivo(440, orig, pasta=d / "capas")
    assert f.exists()
    try:
        G.adotar_arquivo(440, d / "nao_existe.png", pasta=d / "capas")
    except ValueError as e:
        assert "nao achei" in str(e)
    return "adotar arquivo do disco valida existencia e formato"


def t_esquecer(tmp):
    d = tmp / "g"; d.mkdir(parents=True)
    (d / "440.png").write_bytes(png())
    (d / "440.jpg").write_bytes(jpg())
    assert G.esquecer(440, pasta=d) == 2
    assert G.esquecer(440, pasta=d) == 0
    return "esquecer tira a capa manual e e idempotente"


# ---- candidatos ---------------------------------------------------------

def t_candidatos_ordena_por_score(tmp):
    def buscar(appid, key, **kw):
        return [
            {"url": "u1", "thumb": "t1", "score": 2, "width": 600, "height": 900,
             "author": {"name": "ana"}, "style": "alternate"},
            {"url": "u2", "thumb": "t2", "score": 9, "width": 660, "height": 930,
             "author": {"name": "bia"}},
            {"url": None, "thumb": "t3", "score": 99},        # sem url: fora
        ], None
    lista, erro = G.candidatos(440, "chave", buscar=buscar)
    assert erro is None
    assert [c["url"] for c in lista] == ["u2", "u1"], lista
    assert lista[0]["autor"] == "bia" and lista[0]["largura"] == 660
    return "candidatos saem ordenados por pontuacao, sem os quebrados"


def t_candidatos_propaga_erro(tmp):
    def buscar(appid, key, **kw):
        return [], "HTTP 401: chave invalida ou expirada"
    lista, erro = G.candidatos(440, "ruim", buscar=buscar)
    assert lista == [] and "401" in erro
    return "erro da SteamGridDB chega inteiro na tela"


def t_candidatos_limita(tmp):
    def buscar(appid, key, **kw):
        return [{"url": f"u{i}", "score": i} for i in range(80)], None
    lista, _ = G.candidatos(440, "k", buscar=buscar, limite=10)
    assert len(lista) == 10
    return "lista de candidatos e limitada"


# ---- nomear -------------------------------------------------------------

def t_nomear_em_lote(tmp):
    itens = [{"appid": 440, "nome": None}, {"appid": 630, "nome": None}]
    def carregar(ids, verbose=False):
        assert set(ids) == {440, 630}
        return {440: {"name": "Team Fortress 2"}, 630: {"name": "Alien Swarm"}}
    G.nomear(itens, carregar=carregar)
    assert itens[0]["nome"] == "Team Fortress 2"
    return "nomes vem em uma chamada so, nao uma por jogo"


def t_nomear_sobrevive_a_falha(tmp):
    itens = [{"appid": 440, "nome": None}]
    def carregar(ids, verbose=False):
        raise OSError("sem rede")
    G.nomear(itens, carregar=carregar)
    assert itens[0]["nome"] is None, "sem nome, mas sem explodir"
    return "falha ao buscar nomes nao derruba a galeria"


# ---- varredura ----------------------------------------------------------

def t_varrer_filtra_e_informa_progresso(tmp):
    chamadas = []
    def falso(appid, steam, grid, nos=False, limiar=0.45):
        return ({440: (G.FABRICADA, None, None),
                 630: (None, None, 0.9),
                 8930: (G.SEM_CAPA, None, None),
                 70: (G.MANUAL, None, None)}[appid])
    orig = G.diagnosticar
    G.diagnosticar = falso
    try:
        vistos = []
        itens = G.varrer([440, 630, 8930, 70], "s", "g",
                         progresso=lambda i, t, a: vistos.append(a))
    finally:
        G.diagnosticar = orig
    assert [i["appid"] for i in itens] == [440, 8930], itens
    assert vistos == [440, 630, 8930, 70], "progresso em todos"
    return "varredura devolve so os problematicos e reporta progresso"


def t_varrer_pode_ser_cancelada(tmp):
    orig = G.diagnosticar
    G.diagnosticar = lambda *a, **k: (G.SEM_CAPA, None, None)
    try:
        n = []
        itens = G.varrer(list(range(100)), "s", "g",
                         progresso=lambda i, t, a: n.append(i),
                         parar=lambda: len(n) >= 5)
    finally:
        G.diagnosticar = orig
    assert len(itens) <= 6, len(itens)
    assert len(n) <= 6, "parou cedo"
    return "varredura longa pode ser cancelada no meio"


def t_varrer_sobrevive_a_jogo_quebrado(tmp):
    def explode(appid, *a, **k):
        if appid == 630:
            raise RuntimeError("capa corrompida")
        return (G.FABRICADA, None, None)
    orig = G.diagnosticar
    G.diagnosticar = explode
    try:
        itens = G.varrer([440, 630, 8930], "s", "g")
    finally:
        G.diagnosticar = orig
    assert len(itens) == 3, "o quebrado entra como 'sem capa', nao derruba"
    return "um jogo quebrado nao interrompe a varredura inteira"


def t_toda_razao_tem_explicacao(tmp):
    for m in (G.SEM_CAPA, G.FABRICADA, G.SEM_PAGINA, G.FRACA, G.MANUAL):
        assert m in G.EXPLICACAO and len(G.EXPLICACAO[m]) > 20
    return "todo motivo tem texto explicando o usuario"


def t_capa_atual_prefere_o_caminho_conhecido(tmp):
    d = tmp / "ca"; d.mkdir(parents=True)
    f = d / "capa.png"; f.write_bytes(png(600, 900, (1, 2, 3)))
    dados = G.capa_atual({"appid": 440, "caminho": f}, "s", None)
    assert dados == f.read_bytes()
    return "capa atual usa o arquivo que a varredura ja achou"


def t_capa_atual_cai_pro_grid(tmp):
    d = tmp / "cb"; d.mkdir(parents=True)
    (d / "440p.png").write_bytes(png(600, 900, (9, 9, 9)))
    dados = G.capa_atual({"appid": 440, "caminho": None}, "s", d)
    assert dados is not None and dados[:8] == b"\x89PNG\r\n\x1a\n"
    return "sem caminho conhecido, mostra o que esta no grid hoje"


def t_capa_atual_cai_pra_api(tmp):
    chamadas = []
    def baixar(url, timeout=None, headers=None):
        chamadas.append(url); return png()
    orig = core.url_capa_pela_api
    core.url_capa_pela_api = lambda a: "https://exemplo/capa.png"
    try:
        dados = G.capa_atual({"appid": 440, "caminho": None}, "s",
                             tmp / "vazio", baixar=baixar)
    finally:
        core.url_capa_pela_api = orig
    assert dados is not None and chamadas == ["https://exemplo/capa.png"]
    return "sem nada local, busca a capa da API pra comparar"


def t_capa_atual_sem_nada(tmp):
    orig = core.url_capa_pela_api
    core.url_capa_pela_api = lambda a: None
    try:
        assert G.capa_atual({"appid": 1, "caminho": None}, "s",
                            tmp / "nada") is None
    finally:
        core.url_capa_pela_api = orig
    return "quando nao ha capa alguma, devolve None em vez de explodir"


def t_gravar_e_ler_chave(tmp):
    f = tmp / "k" / "sgdb_key.txt"
    f.parent.mkdir(parents=True)
    G.gravar_chave("  0123456789abcdef0123456789abcdef  ", caminho=f)
    assert f.read_text(encoding="utf-8").strip() == "0123456789abcdef0123456789abcdef"
    assert G.ler_chave(f) == "0123456789abcdef0123456789abcdef"
    return "chave e gravada sem espacos e lida de volta"


def t_chave_com_aspas_e_limpa(tmp):
    f = tmp / "k2" / "sgdb_key.txt"; f.parent.mkdir(parents=True)
    G.gravar_chave('"abcdefgh12345"', caminho=f)
    assert G.ler_chave(f) == "abcdefgh12345"
    return "aspas coladas na chave sao removidas"


def t_chave_invalida_recusada(tmp):
    f = tmp / "k3" / "sgdb_key.txt"; f.parent.mkdir(parents=True)
    for ruim in ("", "   ", "curta", "com espaco no meio"):
        try:
            G.gravar_chave(ruim, caminho=f)
        except ValueError:
            continue
        raise AssertionError(f"devia recusar: {ruim!r}")
    assert not f.exists()
    return "chave vazia, curta ou com espaco e recusada antes de gravar"


def main():
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
    print(f"\n{len(testes) - falhas}/{len(testes)} passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
