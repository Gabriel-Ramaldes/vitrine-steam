#!/usr/bin/env python3
"""
core: a logica, sem interface.

Nada aqui imprime nem encerra o processo. O progresso sai por um objeto
Relatorio, que o chamador define, e os erros sobem como ErroCore. E isso
que permite a mesma logica servir a linha de comando e a uma interface
grafica sem duplicacao.

As listas em .txt sairam: a fonte de verdade agora sao as Colecoes do Steam.
"""


import io
import functools
import json
import os
import platform
import unicodedata
import re
import shutil
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat
except ImportError:                      # quem importa o core decide o que fazer
    raise ImportError("Pillow nao encontrado. Rode:  pip install Pillow")

def _base_dir():
    """
    A pasta que contem badges/, adesivos/, molduras/, capas/ e config.json.

    Rodando como .py e a pasta do proprio arquivo. Mas congelado pelo
    PyInstaller, __file__ aponta para a pasta TEMPORARIA onde o exe se
    descompacta (_MEIxxxx), que some ao fechar - os badges e backups
    precisam ficar ao lado do executavel, nao la.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = _base_dir()


# --------------------------------------------------------------------------
# Como o core fala com quem o chama
# --------------------------------------------------------------------------

class ErroCore(Exception):
    """Falha que o chamador precisa mostrar ao usuario. Mensagem ja pronta."""


class Relatorio:
    """
    Canal de saida do core. A CLI implementa imprimindo; a interface
    grafica implementa atualizando widgets. O padrao e mudo, para que
    importar o core nunca escreva nada por conta propria.
    """

    def info(self, msg):
        """Andamento normal."""

    def aviso(self, msg):
        """Algo que merece atencao mas nao impede continuar."""

    def detalhe(self, msg):
        """Diagnostico fino; so aparece em modo verboso."""

    def item(self, i, total, appid, rotulo, origem, extra=""):
        """Um jogo processado."""


_rel = Relatorio()


def definir_relatorio(relatorio):
    """
    Troca o canal de saida. E global de proposito: as funcoes de composicao
    sao chamadas em cadeia e passar o relatorio por todas elas sujaria as
    assinaturas sem ganho - o core roda uma operacao por vez.
    """
    global _rel
    _rel = relatorio or Relatorio()

BACKUP_DIR = BASE_DIR / "originais"
STATE_FILE = BASE_DIR / "estado.json"

USER_AGENT = "Mozilla/5.0 (vitrine)"
CORNERS = ("br", "bl", "tr", "tl")

# Caminho LEGADO. Funciona pra maior parte do catalogo, mas falha em jogos
# novos ou com pagina de loja atualizada, que migraram pro formato com hash.
CDN_TEMPLATES = [
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900_2x.jpg",
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg",
    "https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900_2x.jpg",
]

# API publica da loja: devolve o hash necessario pra montar a URL do formato novo.
STORE_API = ("https://api.steampowered.com/IStoreBrowseService/GetItems/v1/"
             "?input_json={payload}")
STORE_ASSET_BASE = "https://shared.cloudflare.steamstatic.com/store_item_assets/"

# Ultimo recurso: capa gerada a partir de arte horizontal. Fica feio, e por isso
# o script avisa no final quais jogos cairam aqui.
HEADER_TEMPLATES = [
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg",
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_hero.jpg",
]

SGDB_API = "https://www.steamgriddb.com/api/v2"
# A SGDB hospeda mais de um tamanho vertical. Pedir so 600x900 faz muito jogo
# voltar vazio, entao pedimos os tres e filtramos por proporcao depois.
SGDB_DIMENSOES = "600x900,342x482,660x930"

# Uma library capsule e 2:3 (0.667). Qualquer coisa fora dessa faixa nao e capa.
RATIO_MIN, RATIO_MAX = 0.55, 0.80

MANUAL_DIR_NAME = "capas"
BADGES_DIR_NAME = "badges"
# conjunto que vem no repositorio, usado quando badges/ nao tem o arquivo.
# Os seus em badges/ sempre vencem - trocar um icone e so pôr o seu la.
BADGES_PADRAO_DIR_NAME = "badges_padrao"


# --------------------------------------------------------------------------
# Descoberta da instalacao do Steam
# --------------------------------------------------------------------------

def find_steam_path(override=None):
    """Localiza a pasta raiz do Steam."""
    if override:
        p = Path(override).expanduser()
        if not (p / "userdata").is_dir():
            raise ErroCore(f"'{p}' nao parece a pasta do Steam (nao tem 'userdata/').")
        return p.resolve()

    candidates = []
    system = platform.system()

    if system == "Windows":
        try:
            import winreg
            for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                              (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        for name in ("SteamPath", "InstallPath"):
                            try:
                                candidates.append(Path(winreg.QueryValueEx(k, name)[0]))
                            except FileNotFoundError:
                                pass
                except OSError:
                    pass
        except ImportError:
            pass
        candidates += [Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Steam")]
    elif system == "Darwin":
        candidates.append(Path.home() / "Library/Application Support/Steam")
    else:
        candidates += [Path.home() / ".steam/steam",
                       Path.home() / ".local/share/Steam",
                       Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam"]

    for c in candidates:
        if (c / "userdata").is_dir():
            return c.resolve()

    raise ErroCore("Nao achei o Steam. Passe o caminho manualmente com --steam-path")


def find_grid_dir(steam_path, user_id=None):
    """Devolve a pasta grid/ do usuario (cria se nao existir)."""
    userdata = steam_path / "userdata"
    users = [d for d in userdata.iterdir() if d.is_dir() and d.name.isdigit() and d.name != "0"]
    if not users:
        raise ErroCore(f"Nenhum usuario encontrado em {userdata}")

    if user_id:
        chosen = userdata / str(user_id)
        if not chosen.is_dir():
            raise ErroCore(f"Usuario {user_id} nao existe. Disponiveis: {[u.name for u in users]}")
    elif len(users) == 1:
        chosen = users[0]
    else:
        # Mais de uma conta: pega a de config mais recente e avisa.
        chosen = max(users, key=lambda d: (d / "config").stat().st_mtime
                     if (d / "config").exists() else 0)
        _rel.aviso(f"[!] Varias contas encontradas: {[u.name for u in users]}")
        _rel.aviso(f"[!] Usando a mais recente: {chosen.name}  (troque com --user)")

    grid = chosen / "config" / "grid"
    grid.mkdir(parents=True, exist_ok=True)
    return grid


# --------------------------------------------------------------------------
# Lista de appids
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Obtencao da capa original
# --------------------------------------------------------------------------

def http_get(url, timeout=20, headers=None):
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if r.status != 200:
            raise urllib.error.HTTPError(url, r.status, "nao ok", r.headers, None)
        return r.read()


def eh_capa_valida(dados):
    """
    Confere se os bytes sao mesmo uma capa vertical.
    Sem isso, qualquer header horizontal que o CDN devolva vira 'capa'.
    """
    try:
        img = Image.open(io.BytesIO(dados))
        img.verify()
        img = Image.open(io.BytesIO(dados))
    except Exception:
        return False
    if img.width < 200 or img.height < 300:
        return False
    return RATIO_MIN <= (img.width / img.height) <= RATIO_MAX


def arquivo_eh_capa_valida(caminho):
    try:
        return eh_capa_valida(Path(caminho).read_bytes())
    except Exception:
        return False


# --------------------------------------------------------------------------
# Arte automatica da Steam
#
# Quando um jogo nao tem capa vertical propria, a Steam fabrica uma a partir
# do header: a tira do banner no meio e o resto preenchido com uma copia
# borrada e esticada. A API da loja marca esses arquivos - o nome termina em
# "portrait.png". E sinal exato, nao heuristica de pixel.
# --------------------------------------------------------------------------

_ASSETS = {}


def carregar_assets(appids, verbose=False):
    """Consulta a API da loja em lotes de 100 e guarda o resultado."""
    faltam = [a for a in appids if a not in _ASSETS]
    for i in range(0, len(faltam), 100):
        lote = faltam[i:i + 100]
        payload = json.dumps({
            "ids": [{"appid": int(a)} for a in lote],
            "context": {"country_code": "BR", "language": "portuguese"},
            "data_request": {"include_assets": True},
        }, separators=(",", ":"))
        try:
            resp = json.loads(http_get(STORE_API.format(
                payload=urllib.parse.quote(payload)), timeout=25).decode("utf-8"))
            itens = resp.get("response", {}).get("store_items") or []
        except Exception as e:
            if verbose:
                _rel.detalhe(f"    lote de assets falhou: {e}")
            itens = []
        for a, it in zip(lote, itens):
            _ASSETS[a] = it or {}
        for a in lote:
            _ASSETS.setdefault(a, {})
        if verbose:
            _rel.detalhe(f"    assets: {min(i + 100, len(faltam))}/{len(faltam)}")
    return _ASSETS


def _assets_de(appid):
    if appid not in _ASSETS:
        carregar_assets([appid])
    return (_ASSETS.get(appid) or {}).get("assets") or {}


_FORCADOS = set()


def arte_automatica(appid):
    """
    True se a capa que a Steam serve foi fabricada por ela a partir do
    header. None quando a API nao respondeu ou o jogo nao tem assets -
    o que acontece com jogos removidos da loja, que nao tem mais pagina.
    """
    if appid in _FORCADOS:
        return True
    a = _assets_de(appid)
    for chave in ("library_capsule_2x", "library_capsule"):
        nome = a.get(chave)
        if nome:
            return str(nome).endswith("portrait.png")
    return None


def urls_da_api(appid):
    """URLs da capa vertical segundo a API, da maior para a menor."""
    a = _assets_de(appid)
    fmt = a.get("asset_url_format")
    if not fmt:
        return []
    urls = []
    for chave in ("library_capsule_2x", "library_capsule"):
        nome = a.get(chave)
        if nome:
            urls.append(STORE_ASSET_BASE + fmt.replace("${FILENAME}", nome))
    return urls


def url_capa_pela_api(appid):
    """
    Pergunta pra API da loja onde esta a capa. Necessario pros jogos que
    migraram pro formato /store_item_assets/<appid>/<hash>/, que e o caso
    de lancamentos recentes. Nao precisa de chave.
    """
    payload = json.dumps({
        "ids": [{"appid": int(appid)}],
        "context": {"country_code": "BR", "language": "portuguese"},
        "data_request": {"include_assets": True},
    }, separators=(",", ":"))
    url = STORE_API.format(payload=urllib.parse.quote(payload))

    try:
        resp = json.loads(http_get(url, timeout=15).decode("utf-8"))
        itens = resp.get("response", {}).get("store_items") or []
        if not itens:
            return []
        assets = itens[0].get("assets") or {}
        fmt = assets.get("asset_url_format")
        if not fmt:
            return []
        urls = []
        for chave in ("library_capsule_2x", "library_capsule"):
            nome = assets.get(chave)
            if nome:
                urls.append(STORE_ASSET_BASE + fmt.replace("${FILENAME}", nome))
        return urls
    except Exception:
        return []


def sgdb_buscar_grids(appid, api_key, dimensoes=SGDB_DIMENSOES, verbose=False):
    """
    Consulta a SteamGridDB. Devolve (itens, erro).

    Nunca engole erro em silencio: se a chave for invalida ou o jogo nao
    existir la, isso precisa aparecer. Filtro estreito demais devolve zero
    resultado, entao 600x900 sozinho nao serve - a SGDB tambem hospeda
    342x482 e 660x930, que sao verticais e servem igual.
    """
    if not api_key:
        return [], "sem chave da SteamGridDB"

    params = ["types=static", "nsfw=false", "humor=false"]
    if dimensoes:
        params.append(f"dimensions={dimensoes}")
    url = f"{SGDB_API}/grids/steam/{appid}?" + "&".join(params)

    if verbose:
        _rel.detalhe(f"    GET {url}")

    try:
        bruto = http_get(url, timeout=15,
                         headers={"Authorization": f"Bearer {api_key}"})
    except urllib.error.HTTPError as e:
        motivos = {401: "chave invalida ou expirada",
                   403: "chave sem permissao",
                   404: "jogo nao encontrado na SteamGridDB",
                   429: "limite de requisicoes atingido"}
        return [], f"HTTP {e.code}: {motivos.get(e.code, e.reason)}"
    except Exception as e:
        return [], f"falha de rede: {e}"

    try:
        resp = json.loads(bruto.decode("utf-8"))
    except Exception as e:
        return [], f"resposta ilegivel: {e}"

    if not resp.get("success"):
        return [], f"API respondeu erro: {resp.get('errors') or resp}"

    itens = [i for i in resp.get("data", []) if i.get("url")]
    if not itens:
        return [], "nenhuma arte com esse filtro"
    return itens, None


def url_capa_steamgriddb(appid, api_key, verbose=False):
    """URLs candidatas, da melhor pontuada para a pior."""
    itens, erro = sgdb_buscar_grids(appid, api_key, verbose=verbose)

    # Filtro estreito nao achou nada: tenta de novo sem restricao de tamanho.
    if not itens:
        if verbose and erro:
            _rel.detalhe(f"    filtro padrao: {erro} - tentando sem filtro de dimensao")
        itens, erro = sgdb_buscar_grids(appid, api_key, dimensoes=None,
                                        verbose=verbose)

    if not itens:
        if verbose:
            _rel.detalhe(f"    SteamGridDB: {erro}")
        return []

    # so verticais, ordenadas pela pontuacao da comunidade
    verticais = [i for i in itens
                 if i.get("height") and i.get("width")
                 and RATIO_MIN <= i["width"] / i["height"] <= RATIO_MAX]
    verticais = verticais or itens
    verticais.sort(key=lambda i: i.get("score", 0), reverse=True)

    if verbose:
        _rel.detalhe(f"    {len(verticais)} arte(s) vertical(is) encontrada(s)")
        for i in verticais[:5]:
            _rel.detalhe(f"      {i.get('width')}x{i.get('height')} "
                  f"score={i.get('score')} {i['url']}")

    return [i["url"] for i in verticais[:5]]


def find_local_cover(steam_path, appid):
    """Procura a capa no cache local do Steam (layout novo e antigo)."""
    cache = steam_path / "appcache" / "librarycache"
    for pasta in (cache / str(appid), cache):
        if not pasta.is_dir():
            continue
        for padrao in (f"{appid}_library_600x900*", "library_600x900*"):
            for f in sorted(pasta.glob(padrao)):
                if f.suffix.lower() in (".jpg", ".jpeg", ".png") and arquivo_eh_capa_valida(f):
                    return f
        # Steam recente as vezes salva com nome de hash: varre por proporcao.
        if pasta.name == str(appid):
            for f in sorted(pasta.iterdir()):
                if f.suffix.lower() in (".jpg", ".jpeg", ".png") and arquivo_eh_capa_valida(f):
                    return f
    return None


def analisar_nitidez(caminho_ou_bytes):
    """
    Mede que fracao da altura da capa tem detalhe real.

    Muitas capas 600x900 "oficiais" sao so o header horizontal colado no topo
    com fundo borrado embaixo. A proporcao esta certa, entao eh_capa_valida()
    aprova, mas visualmente e ruim. Aqui a gente olha o CONTEUDO: mede energia
    de borda linha a linha e ve quanto da imagem realmente tem informacao.

    Devolve float de 0.0 a 1.0. Capa boa passa de ~0.7; header colado fica
    perto de 0.3.
    """
    try:
        if isinstance(caminho_ou_bytes, (bytes, bytearray)):
            img = Image.open(io.BytesIO(caminho_ou_bytes))
        else:
            img = Image.open(caminho_ou_bytes)
        g = img.convert("L").resize((150, 225), Image.LANCZOS)
    except Exception:
        return 1.0   # na duvida, nao mexe

    bordas = g.filter(ImageFilter.FIND_EDGES)
    linhas = [ImageStat.Stat(bordas.crop((0, y, 150, y + 1))).mean[0]
              for y in range(225)]

    pico = sorted(linhas)[int(225 * 0.9)]
    if pico < 1.0:
        return 1.0   # imagem chapada inteira: nao da pra julgar, deixa quieto

    limiar = pico * 0.25
    return sum(1 for v in linhas if v > limiar) / len(linhas)


def validar_chave_sgdb(api_key):
    """
    Confere a chave UMA vez, antes de processar o acervo.

    Sem isso, uma chave morta faz o script dizer "sem alternativa" em todos
    os jogos, sem nunca mencionar que o problema e a credencial.
    Devolve (ok, mensagem).
    """
    if not api_key:
        return False, "nenhuma chave informada"

    chave = api_key.strip()
    if chave != api_key:
        return False, "a chave tem espaco ou quebra de linha nas pontas"

    # 440 = Team Fortress 2, sempre existe na base.
    try:
        http_get(f"{SGDB_API}/grids/steam/440?types=static", timeout=15,
                 headers={"Authorization": f"Bearer {chave}"})
        return True, "ok"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, (
                f"HTTP {e.code}: a SteamGridDB recusou a chave.\n"
                "  Gere uma nova em https://www.steamgriddb.com/profile/preferences/api\n"
                "  Se voce regerou a chave recentemente, a anterior foi invalidada."
            )
        if e.code == 404:
            return True, "ok"   # chave passou, so o jogo de teste que faltou
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, f"falha de rede: {e}"


def buscar_capa_melhor(appid, sgdb_key, nitidez_atual, verbose=False,
                       exigir_ganho=False, variante=0):
    """
    Pega arte da SteamGridDB, da mais bem pontuada pela comunidade para a pior.

    IMPORTANTE: nao usa a nitidez como criterio de aceite. A nitidez detecta
    "header colado sobre preenchimento", mas nao mede qualidade - arte de
    estilo limpo, com logo centralizado em fundo liso, pontua baixo e ainda
    assim e uma capa otima. Quem ordena aqui e o score da comunidade.

    exigir_ganho=True volta ao comportamento estrito (util em lote).
    variante=N pula as N primeiras, pra quando voce nao gostou da escolha.
    """
    if not sgdb_key:
        return None, None

    urls = url_capa_steamgriddb(appid, sgdb_key, verbose=verbose)
    pulados = 0

    for url in urls:
        try:
            dados = http_get(url)
        except Exception as e:
            if verbose:
                _rel.detalhe(f"      download falhou: {e}")
            continue

        if not eh_capa_valida(dados):
            if verbose:
                try:
                    _rel.detalhe(f"      {Image.open(io.BytesIO(dados)).size} rejeitada: "
                          f"proporcao fora de {RATIO_MIN}-{RATIO_MAX}")
                except Exception:
                    _rel.detalhe("      rejeitada: nao e imagem valida")
            continue

        nova = analisar_nitidez(dados)

        if exigir_ganho and nova <= nitidez_atual + 0.10:
            if verbose:
                _rel.detalhe(f"      nitidez={nova:.2f} descartada "
                      f"(--exigir-ganho pede > {nitidez_atual + 0.10:.2f})")
            continue

        if pulados < variante:
            pulados += 1
            if verbose:
                _rel.detalhe(f"      nitidez={nova:.2f} pulada (--variante {variante})")
            continue

        if verbose:
            _rel.detalhe(f"      aceita: nitidez {nitidez_atual:.2f} -> {nova:.2f}")
        return dados, nova

    return None, None


def find_manual_cover(appid):
    """Capa que voce mesmo colocou em capas/<appid>.png - tem prioridade maxima."""
    pasta = BASE_DIR / MANUAL_DIR_NAME
    if not pasta.is_dir():
        return None
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        f = pasta / f"{appid}{ext}"
        if f.exists():
            return f
    return None


def cover_from_header(dados):
    """Gera uma 600x900 a partir de um header/hero horizontal, com fundo borrado."""
    src = Image.open(io.BytesIO(dados)).convert("RGB")
    alvo = (600, 900)

    # fundo: preenche o quadro inteiro e borra
    escala = max(alvo[0] / src.width, alvo[1] / src.height)
    fundo = src.resize((int(src.width * escala) + 1, int(src.height * escala) + 1), Image.LANCZOS)
    esq = (fundo.width - alvo[0]) // 2
    topo = (fundo.height - alvo[1]) // 2
    fundo = fundo.crop((esq, topo, esq + alvo[0], topo + alvo[1]))
    fundo = fundo.filter(ImageFilter.GaussianBlur(28))

    # frente: header inteiro, centralizado
    largura = int(alvo[0] * 0.92)
    altura = int(src.height * (largura / src.width))
    frente = src.resize((largura, altura), Image.LANCZOS)
    fundo.paste(frente, ((alvo[0] - largura) // 2, (alvo[1] - altura) // 2))
    return fundo


def get_base_cover(appid, steam_path, grid_dir, force=False, sgdb_key=None,
                   escrito_por_nos=False, melhorar=False, limiar=0.45,
                   verbose=False, exigir_ganho=False, variante=0, min_larg=0,
                   arte_crua=False, trocar_auto=False):
    """
    Devolve (caminho da capa LIMPA, nome da fonte).

    escrito_por_nos: o arquivo que esta em grid/<appid>p.png foi produzido por
    este script numa execucao anterior, ou seja, JA TEM BADGE. Nesse caso ele
    nunca pode ser usado como base, senao o badge velho fica queimado na capa.
    """
    resultado = _buscar_capa_base(appid, steam_path, grid_dir, force,
                                  sgdb_key, escrito_por_nos, min_larg, arte_crua,
                                  trocar_auto)
    base, origem = resultado
    if base is None or origem == "capas/ (manual)":
        return resultado

    # A capa passou na proporcao, mas o conteudo pode ser so um header colado
    # no topo com preenchimento borrado. Mede e sinaliza sempre.
    nitidez = analisar_nitidez(base)
    if nitidez >= limiar:
        return resultado
    if not melhorar:
        return base, f"{origem} [FRACA {nitidez:.2f}]"

    dados, nova_nitidez = buscar_capa_melhor(appid, sgdb_key, nitidez,
                                            verbose=verbose,
                                            exigir_ganho=exigir_ganho,
                                            variante=variante)
    if dados is None:
        return base, f"{origem} [FRACA {nitidez:.2f}, sem alternativa]"

    pasta = BASE_DIR / MANUAL_DIR_NAME
    pasta.mkdir(exist_ok=True)
    destino_manual = pasta / f"{appid}.png"
    Image.open(io.BytesIO(dados)).convert("RGB").save(destino_manual, "PNG")

    destino = BACKUP_DIR / f"{appid}.jpg"
    Image.open(io.BytesIO(dados)).convert("RGB").save(destino, "JPEG", quality=95)
    return destino, f"SteamGridDB [upgrade {nitidez:.2f}->{nova_nitidez:.2f}]"


def _larga_o_bastante(caminho_ou_bytes, min_larg):
    """A capa tem pixels suficientes? Emoldurada, uma 300x450 sai borrada."""
    if not min_larg:
        return True
    try:
        if isinstance(caminho_ou_bytes, (bytes, bytearray)):
            im = Image.open(io.BytesIO(caminho_ou_bytes))
        else:
            im = Image.open(caminho_ou_bytes)
        return im.width >= min_larg
    except Exception:
        return False


def _buscar_capa_base(appid, steam_path, grid_dir, force, sgdb_key, escrito_por_nos,
                      min_larg=0, arte_crua=False, trocar_auto=False):
    """
    Cadeia de fontes, sem julgar qualidade de conteudo.

    arte_crua=True (modo moldura): recusa qualquer capa que ja seja uma capa
    PRONTA de outra ferramenta. Emoldurar uma capa emoldurada produz duas
    molduras empilhadas. O sinal e exato, nao heuristico: capas vindas do
    grid/ ficam marcadas com <appid>.era-custom quando sao copiadas.
    """
    BACKUP_DIR.mkdir(exist_ok=True)

    # 1. Capa manual sua: sempre vence, e sempre re-lida (voce pode trocar).
    manual = find_manual_cover(appid)
    if manual:
        img = Image.open(manual).convert("RGB")
        destino = BACKUP_DIR / f"{appid}.jpg"
        img.save(destino, "JPEG", quality=95)
        return destino, "capas/ (manual)"

    # 2. Backup de execucao anterior. E o que impede empilhar badge em badge.
    era_custom = (BACKUP_DIR / f"{appid}.era-custom").exists()
    ja_trocada = (BACKUP_DIR / f"{appid}.sgdb").exists()

    # O backup de um jogo com arte fabricada e a propria arte borrada.
    # Ignora ele, a menos que ja tenhamos trocado numa execucao anterior.
    pular_backup = (trocar_auto and not ja_trocada
                    and arte_automatica(appid) is True)

    # Modo moldura com backup "custom": aquela arte e uma capa pronta de
    # outra ferramenta. Guarda de lado (o --restore ainda a devolve) e
    # libera o slot para baixar arte crua.
    if arte_crua and era_custom:
        guardado = BACKUP_DIR / "custom"
        guardado.mkdir(exist_ok=True)
        for ext in (".png", ".jpg", ".jpeg"):
            b = BACKUP_DIR / f"{appid}{ext}"
            if b.exists():
                destino = guardado / f"{appid}{ext}"
                if not destino.exists():
                    shutil.move(str(b), str(destino))
                else:
                    b.unlink()
                break
        (BACKUP_DIR / f"{appid}.era-custom").unlink(missing_ok=True)
        (guardado / f"{appid}.era-custom").touch()
        era_custom = False

    if not force and not (arte_crua and era_custom) and not pular_backup:
        for ext in (".png", ".jpg", ".jpeg"):
            b = BACKUP_DIR / f"{appid}{ext}"
            if b.exists():
                if _larga_o_bastante(b, min_larg):
                    return b, "backup"
                break      # backup pequeno demais: busca uma maior online

    # 3. Arte customizada que VOCE ja tinha posto no grid antes do script existir.
    #    Se o arquivo de la e nosso, pula: seria realimentar o badge antigo.
    if not escrito_por_nos and not arte_crua:
        for f in sorted(grid_dir.glob(f"{appid}p.*")):
            if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
                destino = BACKUP_DIR / f"{appid}{f.suffix.lower()}"
                shutil.copy2(f, destino)
                # marcador: esse jogo JA tinha arte customizada antes de eu mexer,
                # entao o --restore precisa devolve-la em vez de so apagar.
                (BACKUP_DIR / f"{appid}.era-custom").touch()
                return destino, "arte custom existente"

    # 3b. A Steam fabricou essa capa a partir do header? Entao a arte dela
    #     e ruim por construcao, e a SteamGridDB vem antes de tudo.
    if trocar_auto and arte_automatica(appid) is True:
        for url in url_capa_steamgriddb(appid, sgdb_key):
            try:
                dados = http_get(url)
            except Exception:
                continue
            if not eh_capa_valida(dados) or not _larga_o_bastante(dados, min_larg):
                continue
            destino = BACKUP_DIR / f"{appid}.jpg"
            Image.open(io.BytesIO(dados)).convert("RGB").save(destino, "JPEG", quality=95)
            for outro in (".png", ".jpeg"):
                (BACKUP_DIR / f"{appid}{outro}").unlink(missing_ok=True)
            (BACKUP_DIR / f"{appid}.sgdb").touch()   # nao rebaixar na proxima
            return destino, "SteamGridDB (trocou arte automatica)"

    # 4. Cache local do Steam. Se a arte e fabricada, o cache tem a mesma
    #    imagem borrada: so serve se a SteamGridDB nao tiver alternativa.
    local = None if pular_backup else find_local_cover(steam_path, appid)
    if local and _larga_o_bastante(local, min_larg):
        destino = BACKUP_DIR / f"{appid}{local.suffix.lower()}"
        shutil.copy2(local, destino)
        return destino, "cache local"

    # 5. CDN legado, 6. API da loja (formato novo com hash), 7. SteamGridDB.
    tentativas = [
        ("CDN", [t.format(appid=appid) for t in CDN_TEMPLATES]),
        ("API da loja", url_capa_pela_api(appid)),
        ("SteamGridDB", url_capa_steamgriddb(appid, sgdb_key)),
    ]
    for nome_fonte, urls in tentativas:
        for url in urls:
            try:
                dados = http_get(url)
            except Exception:
                continue
            if not eh_capa_valida(dados):
                continue  # veio header horizontal ou placeholder: descarta
            if not _larga_o_bastante(dados, min_larg):
                continue  # resolucao baixa demais para emoldurar
            destino = BACKUP_DIR / f"{appid}.jpg"
            Image.open(io.BytesIO(dados)).convert("RGB").save(destino, "JPEG", quality=95)
            return destino, nome_fonte

    # 7b. Nada atingiu a resolucao pedida: repete sem a exigencia, para nao
    #     deixar o jogo sem capa so porque a versao grande nao existe.
    if min_larg:
        return _buscar_capa_base(appid, steam_path, grid_dir, force, sgdb_key,
                                 escrito_por_nos, min_larg=0, arte_crua=arte_crua,
                                 trocar_auto=trocar_auto)

    # 8. Ultimo recurso: montar a partir da arte horizontal. Fica feio.
    for tpl in HEADER_TEMPLATES:
        try:
            dados = http_get(tpl.format(appid=appid))
            img = cover_from_header(dados)
            destino = BACKUP_DIR / f"{appid}.jpg"
            img.save(destino, "JPEG", quality=92)
            return destino, "GERADA do header"
        except Exception:
            continue

    return None, None


# --------------------------------------------------------------------------
# Composicao
# --------------------------------------------------------------------------

def apply_badges(capa_path, itens):
    """
    Compoe varios badges na capa.

    itens: lista de dicts com img, pos, scale, margin, opacity, gap, empilhar.
    Badges no mesmo canto se enfileiram; em cantos diferentes sao independentes.
    """
    capa = Image.open(capa_path).convert("RGBA")

    por_canto = {}
    for it in itens:
        por_canto.setdefault(it["pos"], []).append(it)

    for pos, grupo in por_canto.items():
        offset = 0
        for it in grupo:
            badge = it["img"]
            lado = max(1, int(capa.width * it["scale"]))
            prop = badge.height / badge.width
            badge = badge.resize((lado, max(1, int(lado * prop))), Image.LANCZOS)

            if it["opacity"] < 1.0:
                alpha = badge.getchannel("A").point(lambda v: int(v * it["opacity"]))
                badge = badge.copy()
                badge.putalpha(alpha)

            m = int(capa.width * it["margin"])
            gap = int(capa.width * it["gap"])
            vertical = it["empilhar"] == "vertical"

            dx = 0 if vertical else offset
            dy = offset if vertical else 0

            x = (m + dx) if pos in ("bl", "tl") else (capa.width - badge.width - m - dx)
            y = (m + dy) if pos in ("tl", "tr") else (capa.height - badge.height - m - dy)

            capa.alpha_composite(badge, (x, y))
            offset += (badge.height if vertical else badge.width) + gap

    return capa


# --------------------------------------------------------------------------
# Colecoes do Steam
#
# Clientes modernos gravam as colecoes como JSON puro em
#     <Steam>/userdata/<id>/config/cloudstorage/cloud-storage-namespace-*.json
# O formato e um array de pares [chave, registro], e o 'value' do registro e
# JSON stringificado. Colecoes apagadas vem com value=null.
# --------------------------------------------------------------------------

import json
import re
import unicodedata
from pathlib import Path


def _slug(nome):
    """'Só Online' -> 'so_online'. Vira nome de arquivo de lista."""
    n = unicodedata.normalize("NFKD", nome)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r"[^a-zA-Z0-9]+", "_", n).strip("_").lower()
    return n or "sem_nome"


def achar_arquivos_colecoes(steam_path, user_id):
    """Os JSON de colecoes daquele usuario, mais recente primeiro."""
    pasta = Path(steam_path) / "userdata" / str(user_id) / "config" / "cloudstorage"
    if not pasta.is_dir():
        return []
    arquivos = sorted(pasta.glob("cloud-storage-namespace-*.json"),
                      key=lambda f: f.stat().st_mtime, reverse=True)
    return arquivos


def ler_colecoes(steam_path, user_id):
    """
    Devolve (colecoes, avisos).
    colecoes: lista de dicts {id, nome, slug, appids, dinamica}
    """
    arquivos = achar_arquivos_colecoes(steam_path, user_id)
    if not arquivos:
        return [], [f"nenhum cloud-storage-namespace-*.json em "
                    f"userdata/{user_id}/config/cloudstorage/"]

    avisos = []
    por_id = {}

    for arq in arquivos:
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
        except Exception as e:
            avisos.append(f"{arq.name}: ilegivel ({e})")
            continue

        if not isinstance(dados, list):
            continue

        for par in dados:
            if not isinstance(par, list) or len(par) != 2:
                continue
            chave, registro = par
            if not isinstance(chave, str) or not chave.startswith("user-collections."):
                continue
            if not isinstance(registro, dict):
                continue

            bruto = registro.get("value")
            if bruto is None:
                continue   # colecao apagada

            try:
                val = json.loads(bruto) if isinstance(bruto, str) else bruto
            except Exception:
                avisos.append(f"{chave}: value nao e JSON valido")
                continue

            cid = val.get("id") or chave.split(".", 1)[1]
            if cid in por_id:
                continue   # ja peguei de um arquivo mais recente

            nome = val.get("name") or cid
            added = [a for a in (val.get("added") or []) if isinstance(a, int)]
            removed = set(a for a in (val.get("removed") or []) if isinstance(a, int))
            appids = sorted(set(added) - removed)

            dinamica = bool(val.get("filterSpec")) and not added

            por_id[cid] = {
                "id": cid,
                "nome": nome,
                "slug": _slug(nome),
                "appids": appids,
                "dinamica": dinamica,
            }

    colecoes = sorted(por_id.values(), key=lambda c: c["nome"].lower())

    return colecoes, avisos


# --------------------------------------------------------------------------
# Family Share: descobrir o que e emprestado
# --------------------------------------------------------------------------
#
# O cliente Steam sabe quais jogos voce pode jogar por emprestimo, mas nao
# grava essa lista em disco de forma direta. O que da pra fazer e uma
# subtracao:
#
#     biblioteca que o cliente conhece  -  o que e seu  =  emprestado
#
# O lado esquerdo sai do cache de arte: o Steam baixa capa de tudo que
# aparece na sua biblioteca, inclusive do que e emprestado, e guarda em
# appcache/librarycache/.
#
# "O que e seu" nao fica em disco - propriedade mora no servidor. A pagina
# store.steampowered.com/dynamicstore/userdata/ devolve isso em JSON quando
# voce esta logado no navegador: rgOwnedApps (os jogos) e rgOwnedPackages
# (os pacotes). O segundo e indispensavel: jogo gratuito, de bundle ou
# antigo costuma estar num pacote seu SEM aparecer em rgOwnedApps, e sem
# expandir os pacotes esses jogos seriam acusados de emprestados. A
# expansao sai de appcache/packageinfo.vdf, mantido pelo proprio cliente.
#
# Quando qualquer peca falta, a resposta e "nao sei" - nunca um chute.
# Marcar um jogo seu como emprestado e pior do que nao marcar nada.

URL_USERDATA = "https://store.steampowered.com/dynamicstore/userdata/"

COMO_BAIXAR_USERDATA = (
    "Para detectar Family Share eu preciso saber o que e seu, e isso nao\n"
    "fica em disco. Faca uma vez:\n"
    f"  1. abra {URL_USERDATA}\n"
    "     no navegador em que voce usa a Steam (logado);\n"
    "  2. salve a pagina como userdata.json (Ctrl+S);\n"
    "  3. ponha o arquivo nesta pasta, ou passe --userdata CAMINHO.\n"
    "Refaca quando comprar jogos novos. O arquivo nao sai da sua maquina."
)

# packageinfo.vdf comeca com uma destas assinaturas. O valor e quantos
# bytes extras de token o formato carrega no cabecalho de cada pacote.
_PKG_MAGIA = {0x06565527: 0, 0x06565528: 8}

_KV_FIM = 8                      # byte de tipo que encerra uma arvore
_PKG_FIM = 0xFFFFFFFF            # pseudo-pacote que encerra o arquivo
_PKG_TAM_MAX = 64 << 20          # o real tem poucos MB; acima disso desconfio
_USERDATA_TAM_MAX = 32 << 20
_APPID_MAX = 2 ** 32

# Tipos de valor da KV binaria da Valve que tem tamanho fixo.
# O 5 (wstring) nao aparece nestes arquivos; a convencao e tratar como int32.
_KV_FIXOS = {2: "<i", 3: "<f", 4: "<i", 5: "<i", 6: "<I", 7: "<Q", 10: "<q"}


def _kv_binario(dados, pos, prof=0):
    """
    Le uma arvore key-value binaria da Valve a partir de dados[pos].
    Devolve (dict, posicao logo depois da arvore).

    O formato e publico e sempre o mesmo: cada no e um byte de tipo, uma
    chave terminada em NUL e um valor. Tipo 0 abre sub-arvore, 1 e string
    terminada em NUL, 8 fecha a arvore e nao tem chave nem valor, e o
    resto tem tamanho fixo (_KV_FIXOS). Qualquer tipo fora disso levanta,
    porque seguir lendo um arquivo que eu nao entendo da lixo silencioso.
    """
    if prof > 8:
        raise ValueError("arvore fundo demais")
    arvore = {}
    while True:
        tipo = dados[pos]
        pos += 1
        if tipo == _KV_FIM:
            return arvore, pos
        fim = dados.index(b"\0", pos)
        chave = dados[pos:fim].decode("utf-8", "replace")
        pos = fim + 1
        if tipo == 0:
            arvore[chave], pos = _kv_binario(dados, pos, prof + 1)
        elif tipo == 1:
            fim = dados.index(b"\0", pos)
            arvore[chave] = dados[pos:fim].decode("utf-8", "replace")
            pos = fim + 1
        elif tipo in _KV_FIXOS:
            forma = _KV_FIXOS[tipo]
            arvore[chave] = struct.unpack_from(forma, dados, pos)[0]
            pos += struct.calcsize(forma)
        else:
            raise ValueError(f"tipo de valor desconhecido: {tipo}")


def apps_dos_pacotes(steam_path, pacotes):
    """
    Todo appid que vive dentro dos pacotes informados, lido do cache do
    proprio cliente (appcache/packageinfo.vdf).

    Devolve None - "nao da pra saber" - quando o arquivo nao existe, tem
    cabecalho estranho, ou e de outra conta. O ultimo caso se reconhece
    pela cobertura: se menos de 90% dos SEUS pacotes aparecem no arquivo,
    o cache nao corresponde a esta conta, e expandir o que esta la daria
    uma resposta pior do que nao responder.
    """
    caminho = Path(steam_path) / "appcache" / "packageinfo.vdf"
    procurados = {int(p) for p in pacotes if isinstance(p, int) and p >= 0}
    if not procurados or not caminho.is_file():
        return None
    try:
        if caminho.stat().st_size > _PKG_TAM_MAX:
            return None
        dados = caminho.read_bytes()
        magia = struct.unpack_from("<I", dados, 0)[0]
        if magia not in _PKG_MAGIA:
            return None
        extra = _PKG_MAGIA[magia]
        pos, apps, achados = 8, set(), 0     # pula magia (4) + universo (4)
        while True:
            pid = struct.unpack_from("<I", dados, pos)[0]
            pos += 4
            if pid == _PKG_FIM:
                break
            pos += 24 + extra                # sha1 (20) + change (4) [+ token]
            arvore, pos = _kv_binario(dados, pos)
            if pid not in procurados:
                continue
            reg = arvore.get(str(pid))
            if not isinstance(reg, dict):
                continue
            achados += 1
            ids = reg.get("appids")
            if isinstance(ids, dict):
                apps.update(v for v in ids.values()
                            if isinstance(v, int) and 0 < v < _APPID_MAX)
    except (OSError, ValueError, struct.error, IndexError,
            RecursionError, MemoryError):
        return None
    if achados < 0.9 * len(procurados):
        return None
    return apps


def _inteiros(valor):
    """So os inteiros plausiveis de uma lista vinda de JSON."""
    if not isinstance(valor, list):
        return set()
    saida = set()
    for i in valor:
        if isinstance(i, bool):
            continue
        if isinstance(i, int):
            n = i
        elif isinstance(i, str) and i.isdigit():
            n = int(i)
        else:
            continue
        if 0 <= n < _APPID_MAX:
            saida.add(n)
    return saida


def ler_userdata_loja(caminho):
    """
    (seus apps, seus pacotes) do JSON da loja. Levanta ErroCore com a
    instrucao de como refazer quando o arquivo nao serve.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroCore(f"Nao achei {caminho}.\n\n{COMO_BAIXAR_USERDATA}")
    if caminho.stat().st_size > _USERDATA_TAM_MAX:
        raise ErroCore(f"{caminho.name} tem "
                       f"{caminho.stat().st_size >> 20} MB - grande demais "
                       f"para ser a lista da loja. Salvou a pagina errada?")
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise ErroCore(f"Nao consegui ler {caminho.name} como JSON "
                       f"({type(e).__name__}). Provavelmente o navegador "
                       f"salvou a pagina como HTML em vez do JSON cru.\n\n"
                       f"{COMO_BAIXAR_USERDATA}")
    if not isinstance(bruto, dict):
        raise ErroCore(f"{caminho.name} nao tem a forma da lista da loja.\n\n"
                       f"{COMO_BAIXAR_USERDATA}")
    apps = _inteiros(bruto.get("rgOwnedApps"))
    pacotes = _inteiros(bruto.get("rgOwnedPackages"))
    if not apps and not pacotes:
        raise ErroCore(
            f"{caminho.name} veio sem jogos nem pacotes. Isso quer dizer que "
            f"voce nao estava logado na Steam no navegador quando salvou.\n"
            f"Abra {URL_USERDATA}, faca login, de F5 e salve de novo.")
    return apps, pacotes


def biblioteca_do_cache(steam_path):
    """
    Appids que o cliente conhece, deduzidos do cache de arte. O Steam cria
    appcache/librarycache/<appid>/ para tudo que aparece na sua biblioteca,
    inclusive o que e emprestado. O layout antigo guardava os arquivos
    soltos como <appid>_library_600x900.jpg, entao os dois sao varridos.
    """
    cache = Path(steam_path) / "appcache" / "librarycache"
    achados = set()
    if not cache.is_dir():
        return achados
    try:
        for item in cache.iterdir():
            if item.is_symlink():
                continue
            if item.is_dir() and item.name.isdigit():
                achados.add(int(item.name))
            elif item.is_file():
                m = re.match(r"^(\d{1,10})_library_", item.name)
                if m:
                    achados.add(int(m.group(1)))
    except OSError:
        pass
    return {a for a in achados if 0 < a < _APPID_MAX}


# --- cache local dos jogos de cada membro da Family -----------------------
#
# O cliente guarda, no localconfig.vdf da sua conta, a lista de jogos que
# cada membro da sua Steam Family possui:
#
#   WebStorage > FriendsOwnedGames_storage              <- indice
#       {"m_rgStorageKeys": [accountid, ...]}
#   WebStorage > FriendsOwnedGames_storage_<accountid>
#       {"version":1,"data":{"setApps":[appid,...]},"lastFetchTimeMS":ms}
#
# Isso e um sinal POSITIVO: "este jogo pertence a um membro da familia".
# A subtracao do userdata.json e um sinal NEGATIVO: "este jogo nao e seu".
# Os dois erram em direcoes opostas, entao cruzar os dois e melhor que
# qualquer um sozinho. Veja detectar_family().

_VDF_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|//[^\n]*|\s+')


def ler_vdf_texto(texto):
    """
    VDF texto (localconfig.vdf, config.vdf) -> arvore de dicts.
    Tolerante: lixo no fim nao derruba, e chave repetida vira 'chave#2'
    em vez de sumir.
    """
    pos, n = 0, len(texto)
    pilha = [{}]
    pendente = None
    while pos < n:
        m = _VDF_TOKEN.match(texto, pos)
        if not m:
            pos += 1
            continue
        pos = m.end()
        if m.group(1) is not None:
            tok = m.group(1).replace('\\"', '"').replace("\\\\", "\\")
            if pendente is None:
                pendente = tok
            else:
                pilha[-1][pendente] = tok
                pendente = None
        elif m.group(2) == "{":
            novo = {}
            if pendente is not None:
                base, k = pendente, 2
                while pendente in pilha[-1]:
                    pendente = f"{base}#{k}"
                    k += 1
                pilha[-1][pendente] = novo
                pendente = None
            pilha.append(novo)
        elif m.group(2) == "}" and len(pilha) > 1:
            pilha.pop()
    return pilha[0]


def _localconfig(steam_path, user_id):
    """A raiz UserLocalConfigStore da conta, ou None."""
    f = (Path(steam_path) / "userdata" / str(user_id) / "config" / "localconfig.vdf")
    if not f.is_file():
        return None
    try:
        if f.stat().st_size > 32 << 20:
            return None
        arvore = ler_vdf_texto(f.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError, RecursionError, MemoryError):
        return None
    raiz = arvore.get("UserLocalConfigStore")
    return raiz if isinstance(raiz, dict) else None


def grupo_family(steam_path, user_id):
    """
    (groupid, membros) do FamilyGroup que o cliente grava em disco.
    Traz so os metadados: o Steam nao guarda a lista de jogos aqui.
    """
    raiz = _localconfig(steam_path, user_id)
    if not raiz:
        return None, set()
    fg = raiz.get("FamilyGroup")
    if not isinstance(fg, dict):
        return None, set()
    membros = set()
    ms = fg.get("members")
    if isinstance(ms, dict):
        for m in ms.values():
            if isinstance(m, dict):
                a = str(m.get("accountid", ""))
                if a.isdigit():
                    membros.add(int(a))
    return fg.get("groupid"), membros


def apps_dos_membros(steam_path, user_id):
    """
    (uniao dos jogos dos membros da family, diagnostico).

    Le o cache que o proprio cliente mantem. Devolve set() quando nao ha
    cache nenhum - nunca inventa. O diagnostico traz quantos jogos por
    membro, quando cada cache foi atualizado, e quais membros estao sem
    cache (esses sao o ponto cego: jogos deles nao entram na uniao).
    """
    diag = {"por_membro": {}, "sem_cache": [], "mais_velho": None,
            "indice": [], "grupo": None}
    raiz = _localconfig(steam_path, user_id)
    if not raiz:
        return set(), diag

    grupo, membros = grupo_family(steam_path, user_id)
    diag["grupo"] = grupo
    ws = raiz.get("WebStorage")
    if not isinstance(ws, dict):
        diag["sem_cache"] = sorted(membros - {int(user_id)})
        return set(), diag

    # o indice diz quem tem cache gravado; se faltar, varre as chaves
    indice = set()
    bruto = ws.get("FriendsOwnedGames_storage")
    if isinstance(bruto, str):
        try:
            d = json.loads(bruto)
            if isinstance(d, dict):
                indice = {int(x) for x in d.get("m_rgStorageKeys") or []
                          if isinstance(x, int) and not isinstance(x, bool)}
        except (ValueError, TypeError):
            pass
    if not indice:
        for chave in ws:
            m = re.fullmatch(r"FriendsOwnedGames_storage_(\d+)", chave)
            if m:
                indice.add(int(m.group(1)))
    diag["indice"] = sorted(indice)

    uniao = set()
    for conta in sorted(indice):
        bruto = ws.get(f"FriendsOwnedGames_storage_{conta}")
        if not isinstance(bruto, str):
            continue
        try:
            d = json.loads(bruto)
        except (ValueError, TypeError):
            continue
        if not isinstance(d, dict):
            continue
        dados = d.get("data")
        apps = dados.get("setApps") if isinstance(dados, dict) else None
        if not isinstance(apps, list):
            continue
        limpos = {a for a in apps
                  if isinstance(a, int) and not isinstance(a, bool)
                  and 0 < a < _APPID_MAX}
        if not limpos:
            continue
        uniao |= limpos
        ts = d.get("lastFetchTimeMS")
        ts = int(ts) if isinstance(ts, int) and not isinstance(ts, bool) else None
        diag["por_membro"][conta] = (len(limpos), ts)
        if ts and (diag["mais_velho"] is None or ts < diag["mais_velho"]):
            diag["mais_velho"] = ts

    # membro da family sem cache = jogos dele nao entram na uniao
    cobertos = set(diag["por_membro"])
    diag["sem_cache"] = sorted(membros - cobertos - {int(user_id)})
    return uniao, diag


def raizes_steamapps(steam_path):
    """Todas as pastas steamapps, inclusive bibliotecas em outros discos."""
    steam = Path(steam_path)
    raizes = [steam / "steamapps"]
    lvf = steam / "steamapps" / "libraryfolders.vdf"
    if lvf.is_file():
        try:
            texto = lvf.read_text(encoding="utf-8", errors="replace")
            for caminho in re.findall(r'"path"\s+"([^"]+)"', texto):
                p = Path(caminho.replace("\\\\", "\\")) / "steamapps"
                if p.is_dir() and p not in raizes:
                    raizes.append(p)
        except OSError:
            pass
    return [r for r in raizes if r.is_dir()]


def instalados_por_origem(steam_path):
    """
    (emprestados, proprios) entre os jogos INSTALADOS.

    Verdade de campo: o appmanifest de um jogo que voce esta jogando
    emprestado carrega "SharedDepots", com o dono de cada depot. Nao ha
    deducao envolvida - ou o campo esta la, ou nao esta.

    So vale pra instalados, entao nao serve de fonte principal. Serve pra
    duas coisas: garantir que esses entrem no resultado, e medir o acerto
    da deducao no pedaco onde da pra conferir.
    """
    emprestados, proprios = set(), set()
    for raiz in raizes_steamapps(steam_path):
        for f in raiz.glob("appmanifest_*.acf"):
            m = re.match(r"appmanifest_(\d+)\.acf$", f.name)
            if not m:
                continue
            appid = int(m.group(1))
            try:
                if f.stat().st_size > 4 << 20:
                    continue
                texto = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(r'"SharedDepots"\s*\{', texto):
                emprestados.add(appid)
            else:
                proprios.add(appid)
    return emprestados, proprios




def detectar_family(steam_path, user_id, caminho_userdata=None, metodo="auto",
                    usar_exatos=True):
    """
    (appids emprestados, motivo, diagnostico).

    Dois sinais independentes, que erram em direcoes opostas:

      subtracao  (precisa do userdata.json)
          librarycache - (seus apps + apps dos seus pacotes)
          Sinal negativo: "isto nao e seu". Marca demais - qualquer coisa
          que entrou no cache de arte sem ser sua nem emprestada (jogo
          removido da conta, demo, playtest) vira falso positivo.

      membros    (nao precisa de nada: le o cache do proprio cliente)
          librarycache & uniao dos jogos dos membros da family
          Sinal positivo: "isto pertence a um membro". Marca demais pelo
          outro lado - jogo que voce E um membro possuem aparece aqui,
          mas o Steam nao o conta como Family, porque e seu.

    Cruzando os dois sobra o que esta na sua biblioteca, nao e seu, e
    pertence a um membro: a definicao de Family Share. metodo="auto" faz
    isso quando da, e cai no que estiver disponivel quando nao da.

    O set vem vazio quando nao da pra saber, e o motivo diz o que faltou.
    """
    diag = {"metodo": None, "subtracao": None, "membros": None,
            "conhecidos": 0, "ws": {}}

    conhecidos = biblioteca_do_cache(steam_path)
    diag["conhecidos"] = len(conhecidos)
    if not conhecidos:
        return set(), ("appcache/librarycache esta vazio. Abra a biblioteca "
                       "no cliente uma vez para ele baixar as capas."), diag

    # --- sinal positivo: cache dos membros --------------------------------
    por_membros = None
    if metodo in ("auto", "membros"):
        uniao, ws = apps_dos_membros(steam_path, user_id)
        diag["ws"] = ws
        if uniao:
            por_membros = conhecidos & uniao
            diag["membros"] = len(por_membros)

    # --- sinal negativo: subtracao pela lista da loja ---------------------
    por_subtracao = None
    if metodo == "subtracao" and caminho_userdata:
        meus_apps, meus_pacotes = ler_userdata_loja(caminho_userdata)
        dos_pacotes = apps_dos_pacotes(steam_path, meus_pacotes)
        if dos_pacotes is None:
            diag["pacotes_falhou"] = True
        else:
            por_subtracao = conhecidos - (dos_pacotes | meus_apps)
            diag["subtracao"] = len(por_subtracao)

    # --- sinais exatos, pros jogos instalados -----------------------------
    # appmanifest com SharedDepots e emprestado sem margem de duvida; sem o
    # campo, o jogo e seu. Vale so pros instalados, mas onde vale, manda.
    if usar_exatos:
        certos, meus_instalados = instalados_por_origem(steam_path)
    else:
        # usado pela conferencia: sem isto a medida seria circular, porque
        # estariamos conferindo o sinal exato contra ele mesmo.
        certos, meus_instalados = set(), set()
    diag["certos"] = len(certos)
    diag["meus_instalados"] = len(meus_instalados)

    def _ajusta(conjunto):
        if conjunto is None:
            return None
        return (conjunto | (certos & conhecidos)) - meus_instalados

    por_membros = _ajusta(por_membros)
    por_subtracao = _ajusta(por_subtracao)
    if por_membros is not None:
        diag["membros"] = len(por_membros)
    if por_subtracao is not None:
        diag["subtracao"] = len(por_subtracao)

    # --- decide -----------------------------------------------------------
    if metodo == "subtracao":
        if por_subtracao is None:
            return set(), _porque_sem_subtracao(caminho_userdata, diag), diag
        diag["metodo"] = "subtracao"
        return por_subtracao, "", diag

    if metodo == "membros":
        if por_membros is None:
            return set(), _porque_sem_membros(diag), diag
        diag["metodo"] = "membros"
        return por_membros, "", diag

    # auto
    #
    # A subtracao pela lista da loja saiu do padrao, e a razao esta medida:
    # rodando --comparar-family contra os jogos instalados, ela acerta 6%.
    # O motivo e que rgOwnedApps e rgOwnedPackages dizem o que voce PODE
    # JOGAR, nao o que e seu - com o Steam Families o emprestado entra nos
    # dois. Subtrair isso apaga exatamente o alvo. Fica disponivel em
    # --family-metodo subtracao, para quem quiser medir, mas nao manda mais.
    if por_membros is not None:
        diag["metodo"] = "membros"
        return por_membros, "", diag
    if certos & conhecidos:
        diag["metodo"] = "appmanifest"
        return certos & conhecidos, "", diag
    if por_subtracao is not None:
        diag["metodo"] = "subtracao"
        return por_subtracao, "", diag

    if caminho_userdata:
        return set(), _porque_sem_subtracao(caminho_userdata, diag), diag
    return set(), _porque_sem_membros(diag), diag


def conferir_family(steam_path, user_id, caminho_userdata=None, metodo="auto"):
    """
    Mede a deducao contra os jogos instalados. Devolve (resultado, linhas).

    A medida so vale se a deducao for calculada SEM os sinais exatos: do
    contrario estariamos conferindo o appmanifest contra ele mesmo, e o
    acerto daria 100% por construcao, sem significar nada. Entao aqui a
    deteccao roda com usar_exatos=False, e o appmanifest entra so como
    gabarito.
    """
    reais, meus = instalados_por_origem(steam_path)
    cego, _, diag = detectar_family(steam_path, user_id, caminho_userdata,
                                    metodo, usar_exatos=False)
    final, motivo, _ = detectar_family(steam_path, user_id, caminho_userdata,
                                       metodo, usar_exatos=True)
    linhas = []
    if not reais and not meus:
        linhas.append("Nenhum jogo instalado: nao da pra conferir nada.")
        return final, linhas

    linhas.append(f"Gabarito: os {len(reais) + len(meus)} jogos instalados.")
    linhas.append("O appmanifest com SharedDepots diz quem e emprestado sem")
    linhas.append("margem de duvida. A deducao abaixo roda SEM olhar pra ele,")
    linhas.append("senao a conta seria circular.")
    linhas.append("")

    if reais:
        pegos = reais & cego
        pct = 100 * len(pegos) // len(reais)
        linhas.append(f"  emprestados instalados    : {len(reais)}")
        linhas.append(f"  a deducao sozinha pegou   : {len(pegos)} ({pct}%)")
        perdidos = sorted(reais - cego)
        if perdidos:
            linhas.append(f"  PERDEU {len(perdidos)}: "
                          f"{', '.join(str(a) for a in perdidos[:20])}"
                          f"{'...' if len(perdidos) > 20 else ''}")
            linhas.append("    (no resultado final estes entram pelo appmanifest,")
            linhas.append("     mas um emprestado NAO instalado assim escaparia)")
    if meus:
        falsos = sorted(meus & cego)
        linhas.append(f"  seus instalados           : {len(meus)}")
        linhas.append(f"  a deducao marcou a toa    : {len(falsos)}")
        if falsos:
            linhas.append(f"  FALSO POSITIVO: "
                          f"{', '.join(str(a) for a in falsos[:20])}"
                          f"{'...' if len(falsos) > 20 else ''}")

    linhas.append("")
    linhas.append(f"  deducao sozinha : {len(cego)} jogos")
    linhas.append(f"  resultado final : {len(final)} jogos "
                  f"(deducao + appmanifest)")
    if reais and len(reais & cego) < len(reais):
        falta = len(reais) - len(reais & cego)
        linhas.append("")
        linhas.append(f"  A deducao perde {falta} de {len(reais)} nos instalados. "
                      f"Na mesma proporcao,")
        linhas.append(f"  ela perderia jogos emprestados que voce NAO tem "
                      f"instalados - e esses")
        linhas.append(f"  o appmanifest nao resgata.")
    if motivo:
        linhas.append("")
        linhas.append(f"  (deteccao vazia: {motivo})")
    return final, linhas


def comparar_family(steam_path, user_id, caminho_userdata=None):
    """
    Mede varias formas de deduzir Family Share contra o mesmo gabarito.

    Existe uma duvida de fundo que so um numero resolve: o que
    rgOwnedApps quer dizer. Se for "jogos que voce possui", subtrai-lo
    acha os emprestados. Se for "jogos que voce pode jogar" - e com o
    Steam Families isso inclui o que te emprestaram - subtrai-lo APAGA
    exatamente o que procuramos.

    rgOwnedPackages nao tem essa ambiguidade: pacote e licenca, e voce
    nao tem licenca do que te emprestaram.

    Esta funcao roda cada variante e mostra quanto cada uma acerta nos
    jogos instalados, onde o appmanifest da a resposta certa. Nenhuma
    variante enxerga o appmanifest: ele e so o gabarito.
    """
    reais, meus_inst = instalados_por_origem(steam_path)
    conhecidos = biblioteca_do_cache(steam_path)
    uniao, ws = apps_dos_membros(steam_path, user_id)
    membros = (conhecidos & uniao) if uniao else None

    apps_loja = pacotes_loja = None
    if caminho_userdata:
        meus_apps, meus_pacotes = ler_userdata_loja(caminho_userdata)
        apps_loja = set(meus_apps)
        exp = apps_dos_pacotes(steam_path, meus_pacotes)
        pacotes_loja = exp if exp is not None else None

    variantes = []
    if membros is not None:
        variantes.append(("membros (cache local, sem filtro)", membros))
        if pacotes_loja is not None:
            variantes.append(("membros - pacotes", membros - pacotes_loja))
        if apps_loja is not None:
            variantes.append(("membros - rgOwnedApps", membros - apps_loja))
        if pacotes_loja is not None and apps_loja is not None:
            variantes.append(("membros - (pacotes + rgOwnedApps)  [atual]",
                              membros - pacotes_loja - apps_loja))
    if pacotes_loja is not None:
        variantes.append(("librarycache - pacotes", conhecidos - pacotes_loja))
    if pacotes_loja is not None and apps_loja is not None:
        variantes.append(("librarycache - (pacotes + rgOwnedApps)",
                          conhecidos - pacotes_loja - apps_loja))

    linhas = []
    linhas.append(f"Gabarito: {len(reais)} emprestados e {len(meus_inst)} seus, "
                  f"entre os instalados.")
    linhas.append("Nenhuma variante abaixo olha pro appmanifest.")
    linhas.append("")
    linhas.append(f"  {'variante':<42} {'total':>6} {'pega':>9} {'erra':>6}")
    linhas.append(f"  {'-' * 42} {'-' * 6} {'-' * 9} {'-' * 6}")
    for nome, conj in variantes:
        pega = len(reais & conj)
        pct = (100 * pega // len(reais)) if reais else 0
        erra = len(meus_inst & conj)
        linhas.append(f"  {nome:<42} {len(conj):>6} {pega:>4}/{len(reais):<4} "
                      f"{pct:>3}% {erra:>5}")
    linhas.append("")
    linhas.append("  total = quantos jogos a variante marcaria na biblioteca toda")
    linhas.append("  pega  = dos emprestados instalados, quantos ela acha (recall)")
    linhas.append("  erra  = dos SEUS instalados, quantos ela marca a toa")
    linhas.append("")
    if apps_loja is not None and reais:
        dentro = len(reais & apps_loja)
        linhas.append(f"  Dos {len(reais)} emprestados instalados, {dentro} estao "
                      f"em rgOwnedApps.")
        if dentro > len(reais) * 0.5:
            linhas.append("  >>> rgOwnedApps INCLUI o que te emprestaram: ele diz")
            linhas.append("      'pode jogar', nao 'e seu'. Subtrai-lo apaga o alvo.")
    if pacotes_loja is not None and reais:
        dentro = len(reais & pacotes_loja)
        linhas.append(f"  Dos {len(reais)} emprestados instalados, {dentro} estao "
                      f"nos seus pacotes.")
        if dentro == 0:
            linhas.append("  >>> rgOwnedPackages NAO inclui emprestado: e o sinal")
            linhas.append("      de posse confiavel.")
    if ws.get("sem_cache"):
        linhas.append("")
        linhas.append(f"  [!] membros sem cache: "
                      f"{', '.join(str(x) for x in ws['sem_cache'])}")
    return linhas


def _porque_sem_subtracao(caminho, diag):
    if not caminho:
        return ("sem o userdata.json eu nao sei o que e seu. "
                f"{COMO_BAIXAR_USERDATA}")
    if diag.get("pacotes_falhou"):
        return ("nao consegui expandir seus pacotes. O "
                "appcache/packageinfo.vdf esta ausente, num formato que eu "
                "nao conheco, ou e de outra conta. Sem ele, jogo gratuito e "
                "de bundle seria acusado de emprestado, entao prefiro nao "
                "marcar nada.")
    return "a subtracao nao deu resultado."


def _porque_sem_membros(diag):
    ws = diag.get("ws") or {}
    if not ws.get("grupo"):
        return ("este Steam nao tem uma Steam Family configurada nesta conta "
                "(nao achei FamilyGroup no localconfig.vdf).")
    if not ws.get("indice"):
        return ("a Family existe, mas o cliente ainda nao cacheou a "
                "biblioteca de nenhum membro. Abra a aba STEAM FAMILY na "
                "biblioteca uma vez e feche o Steam.")
    return "o cache dos membros veio vazio."


def resumo_family(diag):
    """Linhas legiveis sobre como a deteccao chegou no resultado."""
    import datetime
    linhas = []
    ws = diag.get("ws") or {}
    met = {"cruzado": "cruzamento dos dois sinais",
           "subtracao": "subtracao pela lista da loja (6% de acerto medido)",
           "appmanifest": "so os instalados, pelo appmanifest",
           "membros": "cache local dos membros + appmanifest"}.get(
               diag.get("metodo"), "?")
    linhas.append(f"metodo: {met}")
    linhas.append(f"  biblioteca que o cliente conhece: {diag['conhecidos']}")
    if diag.get("subtracao") is not None:
        linhas.append(f"  nao e seu (subtracao):           {diag['subtracao']}")
    if diag.get("membros") is not None:
        linhas.append(f"  e de um membro (cache local):    {diag['membros']}")
    for conta, (n, ts) in sorted((ws.get("por_membro") or {}).items()):
        quando = ""
        if ts:
            try:
                d = datetime.datetime.fromtimestamp(ts / 1000)
                dias = (datetime.datetime.now() - d).days
                quando = f", atualizado ha {dias} dia(s)"
            except (OverflowError, OSError, ValueError):
                pass
        linhas.append(f"    membro {conta}: {n} jogos{quando}")
    if diag.get("certos"):
        linhas.append(f"  confirmados pelo appmanifest:    {diag['certos']} "
                      f"(instalados, sinal exato)")
    if ws.get("sem_cache"):
        linhas.append(f"  [!] membros SEM cache: "
                      f"{', '.join(str(x) for x in ws['sem_cache'])}")
        linhas.append("      jogos emprestados so por eles podem escapar.")
    return linhas


def achar_userdata_json():
    """O userdata.json da loja, se estiver num lugar obvio."""
    for pasta in (BASE_DIR, Path.home() / "Downloads", Path.home() / "Desktop"):
        for nome in ("userdata.json", "userdata.txt"):
            cand = pasta / nome
            try:
                if cand.is_file():
                    return cand
            except OSError:
                continue
    return None


def family_automatico(listas, appids, badges_dir, config):
    """
    Troca a fonte do status 'family': em vez de sair de uma Colecao, sai da
    deteccao. Se nenhuma colecao criou a lista, ela e montada aqui.
    """
    nome = "family"
    for l in listas:
        if l["nome"] == nome:
            l["appids"] = set(appids)
            l["origens"] = ["Family Share (detectado)"]
            return listas

    badge = achar_badge(badges_dir, nome)
    if badge is None:
        _rel.aviso(f"[!] {badges_dir.name}/{nome}.png nao existe: "
                   f"o canto de Family Share nao sera desenhado.")
        return listas

    hier = [normaliza(x) for x in config.get("hierarquia", HIERARQUIA_PADRAO)]
    chave = normaliza(nome)
    estilo = {**PADRAO_LISTA, **config.get("padrao", {}),
              **(config.get("listas") or {}).get(nome, {})}
    listas.append({
        "nome": nome,
        "ordem": hier.index(chave) if chave in hier else len(hier) + 1,
        "appids": set(appids),
        "img": Image.open(badge).convert("RGBA"),
        "origens": ["Family Share (detectado)"],
        "camada": (config.get("camadas") or {}).get(nome, CAMADA_PADRAO),
        **estilo,
    })
    listas.sort(key=lambda l: (l["ordem"], l["nome"]))
    return listas


def listas_das_colecoes(steam_path, user_id, badges_dir, config):
    """
    Monta as listas de badges a partir das Colecoes do Steam.

    O mapa config["colecoes"] liga Colecao -> badge. Varias colecoes podem
    apontar para o mesmo badge ("07-platinado" e "08-Platinado falta dlc"
    viram ambos 'platinado'); nesse caso os appids sao unidos numa lista so.

    Com o mapa presente, colecoes fora dele sao IGNORADAS de proposito -
    anos, pessoas e generos nao viram badge, e sem isso o script reclamaria
    de dezenas de badges faltando.
    """
    colecoes, avisos = ler_colecoes(steam_path, user_id)
    for a in avisos:
        _rel.aviso(f"[!] {a}")
    if not colecoes:
        return []

    mapa = {k.lower(): v for k, v in (config.get("colecoes") or {}).items()}
    cfg_padrao = {**PADRAO_LISTA, **config.get("padrao", {})}
    cfg_listas = config.get("listas", {})
    hierarquia = [normaliza(x) for x in config.get("hierarquia", HIERARQUIA_PADRAO)]

    # 1. agrupa as colecoes por badge de destino
    grupos, ignoradas, dinamicas = {}, [], []
    for c in colecoes:
        if c["dinamica"]:
            dinamicas.append(c["nome"])
            continue
        if mapa:
            destino = mapa.get(c["nome"].lower())
            if destino is None:
                ignoradas.append(c["nome"])
                continue
            # uma colecao pode alimentar varios badges: "04-Zerados (Family)"
            # vira o status 'zerado' E o canto 'family'
            nomes = [destino] if isinstance(destino, str) else list(destino)
        else:
            nomes = [c["slug"]]
        for nome in nomes:
            g = grupos.setdefault(nome, {"appids": set(), "origens": []})
            g["appids"].update(c["appids"])
            if c["nome"] not in g["origens"]:
                g["origens"].append(c["nome"])

    # 2. cada grupo vira uma lista, se tiver badge desenhado
    listas, sem_badge = [], []
    for nome, g in grupos.items():
        badge_path = achar_badge(badges_dir, nome)
        if badge_path is None:
            sem_badge.append((nome, g["origens"]))
            continue

        chave = normaliza(nome)
        ordem = hierarquia.index(chave) if chave in hierarquia else len(hierarquia) + 1

        cfg = {**cfg_padrao, **cfg_listas.get(nome, {})}
        listas.append({
            "nome": nome,
            "ordem": ordem,
            "appids": g["appids"],
            "img": Image.open(badge_path).convert("RGBA"),
            "origens": g["origens"],
            "camada": (config.get("camadas") or {}).get(nome, CAMADA_PADRAO),
            **cfg,
        })

    if sem_badge:
        _rel.aviso("[!] Badge faltando - nem em badges/ nem em "
                   f"{BADGES_PADRAO_DIR_NAME}/. Estas colecoes ficaram de fora:")
        for nome, origens in sem_badge:
            _rel.info(f"      {badges_dir.name}/{nome}.png  <- {', '.join(origens)}")
        _rel.info("")

    if ignoradas:
        _rel.info(f"Ignoradas ({len(ignoradas)} fora do mapa): "
              f"{', '.join(sorted(ignoradas)[:8])}"
              f"{'...' if len(ignoradas) > 8 else ''}")
    if dinamicas:
        _rel.info(f"Dinamicas ({len(dinamicas)}, nao tem lista de jogos): "
              f"{', '.join(sorted(dinamicas)[:6])}"
              f"{'...' if len(dinamicas) > 6 else ''}")
    if ignoradas or dinamicas:
        _rel.info("")

    listas.sort(key=lambda l: (l["ordem"], l["nome"]))
    return listas


# --------------------------------------------------------------------------
# Listas, badges e grupos
# --------------------------------------------------------------------------

# Ordem de precedencia. O primeiro que casar vence; os outros sao descartados.
# Cada jogo recebe UM badge, sempre.
# O vocabulario fechado, em ordem de precedencia. Tres encaixes que
# convivem na mesma capa, e so a ordem DENTRO de um encaixe tem efeito:
#   status (os seis primeiros) - um so por jogo, disputa resolvida aqui;
#   family - um canto proprio, booleano, nao disputa com nada;
#   adesivo (free, demo) - categoria a parte, free vence demo.
# A ordem nao e editavel pela tela: ver mapa.HIERARQUIA.
HIERARQUIA_PADRAO = [
    "platinado",
    "zerado",
    "suficiente",
    "abandonado",
    "pausado",
    "online",
    "family",
    "free",
    "demo",
]

# valores de estilo herdados por toda lista; config["padrao"] sobrescreve
PADRAO_LISTA = {
    "pos": "br",
    "scale": 0.22,
    "margin": 0.05,
    "opacity": 1.0,
    "gap": 0.025,
    "empilhar": "horizontal",
}


def achar_badge(badges_dir, nome):
    """
    O PNG de um status: o seu primeiro, o do repositorio depois.

    Os icones que eu uso sao do Flaticon e a licenca deles nao permite
    redistribuir, entao badges/ fica fora do repositorio. Sem este
    fallback, quem clonasse nao conseguiria gerar capa nenhuma com
    status.
    """
    pastas = [Path(badges_dir)]
    padrao = BASE_DIR / BADGES_PADRAO_DIR_NAME
    if padrao != pastas[0]:
        pastas.append(padrao)
    for pasta in pastas:
        for ext in (".png", ".webp", ".gif"):
            cand = pasta / f"{nome}{ext}"
            if cand.exists():
                return cand
    return None


def normaliza(nome):
    """'zerados' e 'zerado' sao a mesma coisa. Evita pegadinha de plural."""
    n = nome.strip().lower()
    return n[:-1] if n.endswith("s") else n


def carregar_config(caminho):
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8-sig"))
    except Exception as e:
        raise ErroCore(f"config.json invalido: {e}")


def resolver_badge(appid, listas):
    """
    Devolve (lista_escolhida, outras_que_tambem_continham).
    Um jogo recebe no maximo um badge; a hierarquia desempata.
    """
    candidatas = [l for l in listas if appid in l["appids"]]
    if not candidatas:
        return None, []
    candidatas.sort(key=lambda l: l["ordem"])
    return candidatas[0], candidatas[1:]


# --------------------------------------------------------------------------
# Moldura de caixa (opcional)
#
# Os PNG da moldura sao gerados por tools/build_frame.py, que tambem grava
# molduras/geometria.json. Aqui a gente so consome: assim o script nao
# reimplementa nem adivinha as medidas.
#
# Cada badge pertence a uma CAMADA, declarada em config["camadas"]:
#   {"tipo": "caixa"}  -> troca a moldura e aplica a fita (platinado)
#   {"tipo": "canto"}  -> triangulo num canto, com o icone dentro
#   {"tipo": "badge"}  -> icone solto (padrao, canto inferior direito)
# Dentro de cada slot a hierarquia desempata, como sempre.
# --------------------------------------------------------------------------

MOLDURAS_DIR_NAME = "molduras"
CAMADA_PADRAO = {"tipo": "badge"}


def molduras_dir():
    return BASE_DIR / MOLDURAS_DIR_NAME


@functools.lru_cache(maxsize=1)
def geometria_moldura():
    """Medidas publicadas pelo gerador; None se a moldura nao foi gerada."""
    f = molduras_dir() / "geometria.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None


@functools.lru_cache(maxsize=8)
def _peca(nome):
    """Carrega molduras/<nome>.png uma vez so."""
    f = molduras_dir() / f"{nome}.png"
    if not f.exists():
        return None
    return Image.open(f).convert("RGBA")


ADESIVOS_DIR_NAME = "adesivos"


@functools.lru_cache(maxsize=16)
def _adesivo(nome):
    """Carrega adesivos/<nome>.png, gerado por tools/build_stickers.py."""
    f = BASE_DIR / ADESIVOS_DIR_NAME / f"{nome}.png"
    if not f.exists():
        return None
    return Image.open(f).convert("RGBA")


def _ponto_adesivo(pos, tam_ad, tamanho, janela, margem=26, topo=18):
    """Onde o adesivo cola, relativo a janela da arte."""
    x0, y0, x1, y1 = janela
    w, h = tam_ad
    return {"tr": (tamanho[0] - w - margem, y0 + topo),
            "tl": (margem, y0 + topo),
            "br": (tamanho[0] - w - margem, y1 - h - topo),
            "bl": (margem, y1 - h - topo)}[pos]


def _triangulo_canto(cor, canto, lado, tamanho):
    """Triangulo de canto desenhado na hora (sem asset)."""
    k = 3
    w, h = tamanho
    im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    L = lado * k
    pts = {"tl": [(0, 0), (L, 0), (0, L)],
           "tr": [(w * k, 0), (w * k - L, 0), (w * k, L)],
           "bl": [(0, h * k), (L, h * k), (0, h * k - L)],
           "br": [(w * k, h * k), (w * k - L, h * k), (w * k, h * k - L)]}[canto]
    ImageDraw.Draw(im).polygon(pts, fill=tuple(cor) + (255,))
    return im.resize(tamanho, Image.LANCZOS)


def _ponto_icone(canto, lado, tam, tamanho):
    w, h = tamanho
    d = lado * 0.30
    cx, cy = {"tl": (d, d), "tr": (w - d, d),
              "bl": (d, h - d), "br": (w - d, h - d)}[canto]
    return (round(cx - tam / 2), round(cy - tam / 2))


def compor_com_moldura(capa_path, camadas):
    """
    Monta a capa final no formato caixa.
    `camadas`: {"caixa": lista|None, "cantos": [lista...], "badge": lista|None}
    """
    g = geometria_moldura()
    tam = tuple(g["tamanho"])
    x0, y0, x1, y1 = g["janela"]
    ww, wh = x1 - x0, y1 - y0

    caixa_l = camadas.get("caixa")
    base_nome = "case_ouro" if (caixa_l and caixa_l.get("caixa_ouro", True)) else "case"
    mold = _peca(base_nome) or _peca("case")
    if mold is None:
        raise SteamcaseErro("molduras/case.png nao existe. "
                            "Rode: python tools/build_frame.py")

    # arte escalada para cobrir a janela, com corte centralizado
    art = Image.open(capa_path).convert("RGBA")
    s = max(ww / art.width, wh / art.height)
    art = art.resize((max(ww, round(art.width * s)), max(wh, round(art.height * s))),
                     Image.LANCZOS)
    cx, cy = (art.width - ww) // 2, (art.height - wh) // 2
    art = art.crop((cx, cy, cx + ww, cy + wh))

    tela = Image.new("RGBA", tam, (0, 0, 0, 0))
    tela.paste(art, (x0, y0))
    capa = Image.alpha_composite(tela, mold)

    scrim = _peca("scrim")
    if scrim is not None:
        capa = Image.alpha_composite(capa, scrim)

    # cantos (family, qualificadores)
    for l in camadas.get("cantos", []):
        cfg = l["camada"]
        canto = cfg.get("canto", "tl")
        lado = cfg.get("lado", g["canto_lado"])
        cor = cfg.get("cor") or [0x44, 0x44, 0x44]
        capa = Image.alpha_composite(capa, _triangulo_canto(cor, canto, lado, tam))
        itam = cfg.get("icone", g["canto_icone"])
        icone = l["img"].resize((itam, itam), Image.LANCZOS)
        capa.alpha_composite(icone, _ponto_icone(canto, lado, itam, tam))

    # adesivos (free, demo): colados por cima da arte
    for l in camadas.get("adesivos", []):
        cfg = l["camada"]
        ad = _adesivo(l["nome"])
        if ad is None:
            continue
        capa.alpha_composite(ad, _ponto_adesivo(cfg.get("pos", "tr"), ad.size,
                                                tam, (x0, y0, x1, y1),
                                                cfg.get("margem", 26),
                                                cfg.get("topo", 18)))

    # fita de 100% na base da arte
    lado_b, marg = g["badge_lado"], g["badge_margem"]
    y_badge = y1 - lado_b - marg
    if caixa_l is not None:
        rib = _peca("ribbon")
        if rib is not None:
            capa.alpha_composite(rib, (0, y1 - rib.height + 4))
            y_badge = y1 - rib.height - lado_b + 6

    # badge de status, canto inferior direito
    badge_l = camadas.get("badge")
    if badge_l is not None:
        capa.alpha_composite(badge_l["img"].resize((lado_b, lado_b), Image.LANCZOS),
                             (x1 - marg - lado_b, y_badge))
    return capa


class SteamcaseErro(Exception):
    pass


def resolver_camadas(appid, listas):
    """
    Distribui as listas do jogo pelos slots da moldura.
    Devolve (camadas, nomes_usados, nomes_preteridos).
    """
    cand = sorted([l for l in listas if appid in l["appids"]],
                  key=lambda l: l["ordem"])
    if not cand:
        return None, [], []

    camadas = {"caixa": None, "cantos": [], "adesivos": [], "badge": None}
    usados, preteridos = [], []
    cantos_ocupados = set()
    adesivos_ocupados = set()

    for l in cand:
        cfg = l.get("camada") or CAMADA_PADRAO
        tipo = cfg.get("tipo", "badge")
        if tipo == "caixa":
            if camadas["caixa"] is None:
                camadas["caixa"] = {**cfg, "nome": l["nome"]}
                usados.append(l["nome"])
            else:
                preteridos.append(l["nome"])
        elif tipo == "adesivo":
            pos = cfg.get("pos", "tr")
            if pos in adesivos_ocupados:
                preteridos.append(l["nome"])
            else:
                adesivos_ocupados.add(pos)
                camadas["adesivos"].append({**l, "camada": cfg})
                usados.append(l["nome"])
        elif tipo == "canto":
            c = cfg.get("canto", "tl")
            if c in cantos_ocupados:
                preteridos.append(l["nome"])
            else:
                cantos_ocupados.add(c)
                camadas["cantos"].append({**l, "camada": cfg})
                usados.append(l["nome"])
        else:
            if camadas["badge"] is None:
                camadas["badge"] = l
                usados.append(l["nome"])
            else:
                preteridos.append(l["nome"])

    # a caixa dourada mais a fita ja dizem "platinado": o status vira ruido
    if camadas["caixa"] is not None and camadas["caixa"].get("suprime_badge", True):
        if camadas["badge"] is not None:
            preteridos.append(camadas["badge"]["nome"])
            usados = [u for u in usados if u != camadas["badge"]["nome"]]
            camadas["badge"] = None

    return camadas, usados, preteridos

# --------------------------------------------------------------------------
# Estado (pra saber o que limpar no --restore)
# --------------------------------------------------------------------------

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"aplicados": [], "custom_previa": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def restore(grid_dir):
    state = load_state()
    aplicados = state.get("aplicados", [])
    tinha_custom = set(state.get("custom_previa", []))
    for pasta in (BACKUP_DIR, BACKUP_DIR / "custom"):
        if pasta.is_dir():
            for marcador in pasta.glob("*.era-custom"):
                if marcador.stem.isdigit():
                    tinha_custom.add(int(marcador.stem))
    if not aplicados:
        _rel.info("Nada registrado pra restaurar.")
        return

    removidos = devolvidos = 0
    for appid in aplicados:
        alvo = grid_dir / f"{appid}p.png"
        if alvo.exists():
            alvo.unlink()
            removidos += 1

        # So devolve arte pro grid se o jogo JA tinha capa customizada antes
        # de eu mexer. Se a capa veio do CDN, apagar basta: o Steam volta
        # a usar a arte oficial sozinho.
        if appid in tinha_custom:
            for pasta in (BACKUP_DIR / "custom", BACKUP_DIR):
                achou = False
                for ext in (".png", ".jpg", ".jpeg"):
                    b = pasta / f"{appid}{ext}"
                    if b.exists():
                        shutil.copy2(b, grid_dir / f"{appid}p{ext}")
                        devolvidos += 1
                        achou = True
                        break
                if achou:
                    break

    save_state({"aplicados": [], "custom_previa": sorted(tinha_custom)})
    _rel.info(f"{removidos} badges removidos, {devolvidos} artes customizadas devolvidas.")
    _rel.info("Reinicie o Steam.")


# --------------------------------------------------------------------------

