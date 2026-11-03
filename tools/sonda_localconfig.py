"""
Abre o localconfig.vdf e mostra TUDO que fala de Family, com cuidado.

A sonda anterior achou os termos "FamilyGroup"/"familygroup" dentro de
userdata/<conta>/config/localconfig.vdf. Se a lista dos jogos emprestados
estiver ai, a deteccao de Family Share passa a funcionar 100% offline e o
download manual do userdata.json morre.

Este script so LE. E ele NAO despeja o arquivo: localconfig.vdf tem
coisas suas que nao interessam a ninguem (amigos, tokens, configuracoes
por jogo). Ele imprime apenas:
  - a arvore de chaves abaixo de qualquer no que mencione family;
  - os valores que parecem appid ou contagem;
  - um resumo das listas grandes de numeros que achar.
Qualquer valor longo, hexadecimal ou com cara de credencial vira [oculto].

Uso:
    python sonda_localconfig.py
    python sonda_localconfig.py --steam "D:\\Steam"
"""
import argparse
import os
import re
import sys
from pathlib import Path

MAX_PROF = 6
MAX_FILHOS = 40


# ---- parser tolerante de VDF texto --------------------------------------

_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|//[^\n]*|\s+')


def vdf_parse(texto):
    """Arvore de dicts a partir de um VDF texto. Tolera lixo no fim."""
    pos, n = 0, len(texto)
    pilha = [{}]
    chave_pendente = None
    while pos < n:
        m = _TOKEN.match(texto, pos)
        if not m:
            pos += 1
            continue
        pos = m.end()
        if m.group(1) is not None:
            tok = m.group(1).replace('\\"', '"').replace("\\\\", "\\")
            if chave_pendente is None:
                chave_pendente = tok
            else:
                pilha[-1][chave_pendente] = tok
                chave_pendente = None
        elif m.group(2) == "{":
            novo = {}
            if chave_pendente is not None:
                # chave repetida nao pode sumir: vira chave#2
                base, k, alvo = chave_pendente, 2, pilha[-1]
                while chave_pendente in alvo:
                    chave_pendente = f"{base}#{k}"
                    k += 1
                alvo[chave_pendente] = novo
                chave_pendente = None
            pilha.append(novo)
        elif m.group(2) == "}":
            if len(pilha) > 1:
                pilha.pop()
    return pilha[0]


# ---- impressao com cuidado ----------------------------------------------

_HEX = re.compile(r"^[0-9a-fA-F]{16,}$")
_APPID = re.compile(r"^\d{1,10}$")


def seguro(valor):
    """Devolve o valor se for inofensivo; senao, descreve sem mostrar."""
    if not isinstance(valor, str):
        return str(valor)
    if valor == "":
        return '""'
    if _APPID.match(valor):
        return valor
    if _HEX.match(valor) or len(valor) > 48:
        return f"[oculto: {len(valor)} caracteres]"
    if re.search(r"(token|secret|password|ticket|key)", valor, re.I):
        return "[oculto]"
    return f'"{valor}"'


def resumo_numeros(d):
    """Se o no for um monte de numeros, descreve em vez de listar tudo."""
    chaves = list(d.keys())
    if len(chaves) < 8:
        return None
    appids = [k for k in chaves if _APPID.match(k)]
    if len(appids) < 0.8 * len(chaves):
        return None
    nums = sorted(int(a) for a in appids)
    return (f"{len(nums)} entradas com cara de appid "
            f"(de {nums[0]} a {nums[-1]}); primeiros: "
            f"{', '.join(str(x) for x in nums[:10])}")


def mostrar(no, nome, prof=0, prefixo=""):
    pad = "    " * prof
    if not isinstance(no, dict):
        print(f"{pad}{nome} = {seguro(no)}")
        return
    r = resumo_numeros(no)
    if r:
        print(f"{pad}{nome}/   -> {r}")
        return
    print(f"{pad}{nome}/   ({len(no)} filhos)")
    if prof >= MAX_PROF:
        print(f"{pad}    ... (fundo demais, parei aqui)")
        return
    for i, (k, v) in enumerate(no.items()):
        if i >= MAX_FILHOS:
            print(f"{pad}    ... e mais {len(no) - MAX_FILHOS} chaves")
            break
        mostrar(v, k, prof + 1)


def caminhos_family(no, caminho=()):
    """Todo no cuja chave mencione family/shared/borrow."""
    if not isinstance(no, dict):
        return
    for k, v in no.items():
        baixa = k.lower()
        if any(t in baixa for t in ("family", "shared", "borrow", "lend")):
            yield caminho + (k,), v
        yield from caminhos_family(v, caminho + (k,))


def chaves_de_propriedade(no, caminho=()):
    """Qualquer no que cheire a licenca/pacote/propriedade."""
    alvos = ("licen", "package", "owned", "subscription", "apptick")
    if not isinstance(no, dict):
        return
    for k, v in no.items():
        baixa = k.lower()
        if any(t in baixa for t in alvos):
            yield caminho + (k,), v
        yield from chaves_de_propriedade(v, caminho + (k,))


def achar_steam(forcado=None):
    if forcado:
        return Path(forcado)
    cands = []
    if os.name == "nt":
        try:
            import winreg
            for raiz, chave in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
                try:
                    with winreg.OpenKey(raiz, chave) as k:
                        for nome in ("SteamPath", "InstallPath"):
                            try:
                                cands.append(Path(winreg.QueryValueEx(k, nome)[0]))
                            except OSError:
                                pass
                except OSError:
                    pass
        except ImportError:
            pass
        cands += [Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Steam")]
    else:
        cands += [Path.home() / ".steam/steam", Path.home() / ".local/share/Steam",
                  Path.home() / "Library/Application Support/Steam"]
    for c in cands:
        if (c / "userdata").is_dir():
            return c
    return None


def analisar(f):
    print("=" * 70)
    print(f"ARQUIVO: {f}")
    print(f"tamanho: {f.stat().st_size:,} bytes")
    print("=" * 70)
    try:
        texto = f.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"nao deu pra ler: {e}")
        return
    arvore = vdf_parse(texto)
    if not arvore:
        print("nao consegui interpretar como VDF texto.")
        return
    raiz = next(iter(arvore)) if len(arvore) == 1 else "(varias raizes)"
    print(f"raiz: {raiz}")
    topo = arvore[raiz] if len(arvore) == 1 and isinstance(arvore[raiz], dict) else arvore
    print(f"secoes de primeiro nivel: {', '.join(list(topo)[:25])}")

    print("\n--- nos que mencionam FAMILY / SHARED / BORROW ---")
    achou = False
    for caminho, no in caminhos_family(arvore):
        achou = True
        print(f"\n  >>> {' > '.join(caminho)}")
        mostrar(no, caminho[-1], 2)
    if not achou:
        print("  nenhum (o termo deve estar dentro de um VALOR, nao de uma chave)")
        for linha in texto.splitlines():
            if "family" in linha.lower():
                corte = linha.strip()[:160]
                print(f"  linha: {corte}")

    print("\n--- nos que mencionam LICENCA / PACOTE / PROPRIEDADE ---")
    achou = False
    for caminho, no in chaves_de_propriedade(arvore):
        achou = True
        print(f"\n  >>> {' > '.join(caminho)}")
        mostrar(no, caminho[-1], 2)
    if not achou:
        print("  nenhum")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steam", help="caminho do Steam, se a deteccao falhar")
    ap.add_argument("--conta", help="so esta conta (nome da pasta em userdata)")
    args = ap.parse_args()

    steam = achar_steam(args.steam)
    if steam is None:
        sys.exit("Nao achei o Steam. Rode com --steam \"C:\\caminho\\Steam\".")

    alvos = []
    ud = steam / "userdata"
    if ud.is_dir():
        for d in sorted(ud.iterdir()):
            if not (d.is_dir() and d.name.isdigit()):
                continue
            if args.conta and d.name != args.conta:
                continue
            f = d / "config" / "localconfig.vdf"
            if f.is_file():
                alvos.append(f)
    g = steam / "config" / "config.vdf"
    if g.is_file():
        alvos.append(g)

    if not alvos:
        sys.exit("Nenhum localconfig.vdf encontrado.")
    for f in alvos:
        analisar(f)
    print("Pronto. Nada foi alterado. Me mande esta saida inteira.")


if __name__ == "__main__":
    main()
