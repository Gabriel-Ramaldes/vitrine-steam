"""
A logica da galeria de capas problematicas.

Sem tkinter e sem rede obrigatoria: quem chama injeta o buscador, entao da
pra testar tudo com dados de mentira. A tela em vitrine_galeria.py so
desenha o que sai daqui.

Tres coisas moram aqui:
  - achar quais jogos tem capa ruim, e dizer POR QUE cada um e ruim;
  - listar as alternativas da SteamGridDB pra um jogo;
  - adotar uma alternativa, gravando em capas/<appid>.png.

A pasta capas/ e a de maior prioridade no core: o que estiver la ganha de
tudo. Entao adotar aqui e definitivo ate voce apagar o arquivo.
"""
import base64
import io
import re
import shutil
from pathlib import Path

import core

# Por que uma capa entrou na lista. A ordem e a de gravidade: sem capa
# alguma e pior que capa fraca, e so o primeiro motivo e mostrado.
SEM_CAPA = "sem capa"
FABRICADA = "fabricada pela Steam"
SEM_PAGINA = "sem página na loja"
FRACA = "capa fraca"
MANUAL = "já resolvida por você"

EXPLICACAO = {
    SEM_CAPA: "não existe arte vertical em lugar nenhum",
    FABRICADA: "a Steam colou o banner horizontal no meio e borrou o resto",
    SEM_PAGINA: "saiu da loja e perdeu a página, então a API não responde",
    FRACA: "a medida de nitidez ficou baixa - pode ser header colado, mas "
           "também pode ser arte minimalista legítima",
    MANUAL: "você já colocou uma capa em capas/",
}


def _png(dados):
    """Bytes de imagem -> PNG. Normaliza o que vier da SGDB (jpg, webp)."""
    from PIL import Image
    im = Image.open(io.BytesIO(dados))
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    saida = io.BytesIO()
    im.save(saida, "PNG")
    return saida.getvalue()


def miniatura(dados, largura=150):
    """
    PNG pequeno, em base64, pronto pro tk.PhotoImage(data=...).

    Usa o PNG direto em vez do PIL.ImageTk porque o ImageTk depende de
    como o Pillow foi compilado, e o Tk 8.6 le PNG sozinho. Menos coisa
    pra dar errado na maquina do usuario.
    """
    from PIL import Image
    im = Image.open(io.BytesIO(dados))
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    alt = max(1, round(im.height * largura / im.width))
    im = im.resize((largura, alt), Image.LANCZOS)
    saida = io.BytesIO()
    im.save(saida, "PNG")
    return base64.b64encode(saida.getvalue())


def diagnosticar(appid, steam_path, grid_dir, escrito_por_nos=False,
                 limiar=0.45):
    """
    (motivo, caminho_da_capa, nitidez) para um jogo. motivo None = esta boa.

    Nao baixa nada da SteamGridDB: so olha o que ja existe. A chamada e
    barata o bastante pra rodar na biblioteca inteira.
    """
    if core.find_manual_cover(appid):
        return MANUAL, core.find_manual_cover(appid), None

    auto = core.arte_automatica(appid)
    base, _origem = core._buscar_capa_base(
        appid, steam_path, grid_dir, False, None, escrito_por_nos,
        0, True, False)
    if base is None:
        return SEM_CAPA, None, None
    if auto is True:
        return FABRICADA, base, None
    nitidez = core.analisar_nitidez(base)
    if auto is None:
        # sem pagina na loja a deteccao exata nao funciona; so sinaliza
        # quando a capa tambem esta ruim, pra nao encher a lista
        if nitidez < limiar:
            return SEM_PAGINA, base, nitidez
        return None, base, nitidez
    if nitidez < limiar:
        return FRACA, base, nitidez
    return None, base, nitidez


def varrer(appids, steam_path, grid_dir, aplicados=(), limiar=0.45,
           progresso=None, parar=None):
    """
    Passa por todos os appids e devolve so os problematicos.

    progresso(i, total, appid) e chamado a cada jogo, pra tela nao parecer
    travada. parar() devolvendo True aborta no meio - uma varredura de
    2800 jogos precisa poder ser cancelada.
    """
    aplicados = set(aplicados)
    saida = []
    total = len(appids)
    for i, appid in enumerate(appids, 1):
        if parar is not None and parar():
            break
        try:
            motivo, caminho, nitidez = diagnosticar(
                appid, steam_path, grid_dir, appid in aplicados, limiar)
        except Exception as e:                  # um jogo ruim nao para a lista
            motivo, caminho, nitidez = SEM_CAPA, None, None
            _ = e
        if motivo and motivo != MANUAL:
            saida.append({"appid": appid, "motivo": motivo,
                          "caminho": caminho, "nitidez": nitidez,
                          "nome": None})
        if progresso is not None:
            progresso(i, total, appid)
    return saida


def nomear(itens, carregar=None):
    """Preenche o nome de cada jogo pela API da loja, em lote."""
    carregar = carregar or core.carregar_assets
    ids = [i["appid"] for i in itens if not i.get("nome")]
    if not ids:
        return itens
    try:
        assets = carregar(ids) or {}
    except Exception:
        return itens
    for i in itens:
        info = assets.get(i["appid"]) or assets.get(str(i["appid"])) or {}
        if isinstance(info, dict) and info.get("name"):
            i["nome"] = info["name"]
    return itens


def candidatos(appid, sgdb_key, buscar=None, limite=24):
    """
    (lista, erro) de alternativas da SteamGridDB, da melhor pontuada pra pior.

    Cada item traz o que a tela precisa pra decidir sem baixar tudo: a
    miniatura, as dimensoes, a pontuacao da comunidade e o autor.
    """
    buscar = buscar or core.sgdb_buscar_grids
    itens, erro = buscar(appid, sgdb_key)
    if erro:
        return [], erro
    saida = []
    for it in itens:
        if not it.get("url"):
            continue
        autor = it.get("author") or {}
        saida.append({
            "url": it["url"],
            "thumb": it.get("thumb") or it["url"],
            "largura": it.get("width"),
            "altura": it.get("height"),
            "score": it.get("score") or 0,
            "autor": autor.get("name") if isinstance(autor, dict) else None,
            "estilo": it.get("style"),
        })
    saida.sort(key=lambda c: -(c["score"] or 0))
    return saida[:limite], None


def adotar_bytes(appid, dados, pasta=None):
    """
    Grava a capa escolhida em capas/<appid>.png.

    Valida antes: arquivo que nao e imagem vertical plausivel nao entra,
    senao o erro so apareceria la na frente, na hora de montar a capa.
    """
    if not core.eh_capa_valida(dados):
        raise ValueError("isso não parece uma capa vertical valida "
                         "(esperado algo próximo de 2:3, como 600x900)")
    pasta = Path(pasta or (core.BASE_DIR / core.MANUAL_DIR_NAME))
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{appid}.png"
    # o core aceita varias extensoes; manter duas pro mesmo appid seria
    # ambiguo, entao as outras saem
    for ext in (".jpg", ".jpeg", ".webp"):
        antiga = pasta / f"{appid}{ext}"
        if antiga.exists():
            antiga.unlink()
    destino.write_bytes(_png(dados))
    return destino


def adotar_url(appid, url, pasta=None, baixar=None):
    baixar = baixar or core.http_get
    return adotar_bytes(appid, baixar(url, timeout=30), pasta)


def adotar_arquivo(appid, caminho, pasta=None):
    """Capa que o usuario escolheu no disco dele."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ValueError(f"não achei {caminho}")
    if caminho.stat().st_size > 48 << 20:
        raise ValueError("arquivo grande demais pra ser uma capa")
    return adotar_bytes(appid, caminho.read_bytes(), pasta)


def esquecer(appid, pasta=None):
    """Tira a capa manual, voltando o jogo pro fluxo normal."""
    pasta = Path(pasta or (core.BASE_DIR / core.MANUAL_DIR_NAME))
    n = 0
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        f = pasta / f"{appid}{ext}"
        if f.exists():
            f.unlink()
            n += 1
    return n


def capa_atual(item, steam_path, grid_dir, baixar=None):
    """
    Bytes da capa que o jogo mostra hoje. None quando nao ha nenhuma.

    E o que permite comparar antes de trocar: sem ver a atual ao lado das
    alternativas, escolher e chute. A ordem segue a do core, com o grid
    como ultimo recurso - mesmo que la esteja uma capa nossa com badge,
    e o que o usuario ve na biblioteca agora.
    """
    caminho = item.get("caminho")
    if caminho:
        try:
            return Path(caminho).read_bytes()
        except OSError:
            pass
    appid = item["appid"]
    if grid_dir:
        for ext in (".png", ".jpg", ".jpeg"):
            f = Path(grid_dir) / f"{appid}p{ext}"
            if f.is_file():
                try:
                    return f.read_bytes()
                except OSError:
                    pass
    try:
        url = core.url_capa_pela_api(appid)
    except Exception:
        url = None
    if url:
        baixar = baixar or core.http_get
        try:
            return baixar(url, timeout=15)
        except Exception:
            return None
    return None


def gravar_chave(chave, caminho=None):
    """
    Guarda a chave da SteamGridDB em sgdb_key.txt.

    Em arquivo, e nao na linha de comando, pra nao ficar no historico do
    terminal. O arquivo esta no .gitignore.
    """
    chave = (chave or "").strip().strip('"').strip("'")
    if not chave:
        raise ValueError("chave vazia")
    if len(chave) < 8 or any(c.isspace() for c in chave):
        raise ValueError("isso não parece uma chave da SteamGridDB")
    caminho = Path(caminho or (core.BASE_DIR / "sgdb_key.txt"))
    caminho.write_text(chave + "\n", encoding="utf-8")
    return caminho


def ler_chave(caminho=None):
    """A chave salva, do arquivo ou da variavel de ambiente."""
    import os
    caminho = Path(caminho or (core.BASE_DIR / "sgdb_key.txt"))
    try:
        if caminho.is_file():
            k = caminho.read_text(encoding="utf-8").strip().strip('"').strip("'")
            if k:
                return k
    except OSError:
        pass
    return (os.environ.get("SGDB_KEY") or "").strip() or None


def link_sgdb(appid):
    return f"https://www.steamgriddb.com/steam/{appid}/grids"
