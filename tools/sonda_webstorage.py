"""
Decodifica os FriendsOwnedGames_storage_* do localconfig.vdf.

A sonda anterior achou, dentro de WebStorage, uma entrada por membro da
sua Steam Family - exatamente os accountids que aparecem em FamilyGroup.
Se essas entradas guardarem os jogos que cada membro possui, da pra
calcular o Family Share sem baixar nada.

Este script so LE e nao altera nada. Ele NAO despeja o conteudo: imprime
como conseguiu decodificar, quantos appids achou, os primeiros, e avisa
se houver texto (nome de pessoa, por exemplo) sem mostrar o texto.

Uso:
    python sonda_webstorage.py
    python sonda_webstorage.py --steam "D:\\Steam"
"""
import argparse
import base64
import binascii
import gzip
import json
import os
import re
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from sonda_localconfig import vdf_parse, achar_steam
except ImportError:
    sys.exit("Deixe sonda_localconfig.py na mesma pasta deste arquivo.")

APPID = re.compile(r"^\d{1,10}$")


def tentativas(bruto):
    """Varias formas de decodificar. Devolve (descricao, objeto) ou None."""
    s = bruto.strip()

    # 1. JSON direto
    for _ in range(2):                      # as vezes vem JSON dentro de string
        try:
            obj = json.loads(s)
        except (ValueError, TypeError):
            break
        if isinstance(obj, str):
            s = obj
            continue
        return "JSON", obj

    # 2. base64 -> (zlib/gzip) -> JSON
    try:
        cru = base64.b64decode(s, validate=True)
    except (binascii.Error, ValueError):
        cru = None
    if cru:
        for nome, f in (("base64", lambda b: b),
                        ("base64+zlib", zlib.decompress),
                        ("base64+gzip", gzip.decompress),
                        ("base64+raw-deflate", lambda b: zlib.decompress(b, -15))):
            try:
                dados = f(cru)
            except (zlib.error, OSError, ValueError):
                continue
            try:
                return nome + "+JSON", json.loads(dados.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                pass
            if nome != "base64":
                return nome, dados[:200]
    return None


def numeros(obj, saida=None, textos=None, prof=0):
    """Colhe inteiros com cara de appid e conta campos de texto."""
    if saida is None:
        saida, textos = set(), []
    if prof > 8:
        return saida, textos
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and APPID.match(k):
                saida.add(int(k))
            numeros(v, saida, textos, prof + 1)
    elif isinstance(obj, list):
        for v in obj:
            numeros(v, saida, textos, prof + 1)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, int):
        if 0 < obj < 2 ** 32:
            saida.add(obj)
    elif isinstance(obj, str):
        if APPID.match(obj):
            saida.add(int(obj))
        elif obj:
            textos.append(len(obj))
    return saida, textos


def librarycache(steam):
    cache = Path(steam) / "appcache" / "librarycache"
    achados = set()
    if not cache.is_dir():
        return achados
    try:
        for item in cache.iterdir():
            if item.is_dir() and item.name.isdigit():
                achados.add(int(item.name))
    except OSError:
        pass
    return achados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steam")
    args = ap.parse_args()
    steam = achar_steam(args.steam)
    if steam is None:
        sys.exit("Nao achei o Steam. Use --steam.")

    conhecidos = librarycache(steam)
    print(f"Steam: {steam}")
    print(f"librarycache: {len(conhecidos)} appids (a biblioteca que o cliente conhece)\n")

    ud = Path(steam) / "userdata"
    for conta in sorted(p for p in ud.iterdir() if p.is_dir() and p.name.isdigit()):
        f = conta / "config" / "localconfig.vdf"
        if not f.is_file():
            continue
        print("=" * 70)
        print(f"CONTA {conta.name}")
        print("=" * 70)
        arvore = vdf_parse(f.read_text(encoding="utf-8", errors="replace"))
        raiz = arvore.get("UserLocalConfigStore", {})
        ws = raiz.get("WebStorage", {})
        if not isinstance(ws, dict):
            print("  sem WebStorage\n")
            continue

        # membros da familia, pra cruzar
        fg = raiz.get("FamilyGroup", {})
        membros = set()
        if isinstance(fg.get("members"), dict):
            for m in fg["members"].values():
                if isinstance(m, dict) and str(m.get("accountid", "")).isdigit():
                    membros.add(int(m["accountid"]))
        print(f"  membros da family: {sorted(membros) or 'nenhum'}")

        alvos = {k: v for k, v in ws.items()
                 if "ownedgames" in k.lower() or "owned" in k.lower()}
        if not alvos:
            print("  nenhuma chave de 'owned' em WebStorage\n")
            continue

        uniao = set()
        for chave, valor in sorted(alvos.items()):
            print(f"\n  --- {chave}")
            if not isinstance(valor, str):
                print(f"      tipo inesperado: {type(valor).__name__}")
                continue
            print(f"      {len(valor)} caracteres crus")
            r = tentativas(valor)
            if r is None:
                amostra = re.sub(r"[^\x20-\x7e]", ".", valor[:70])
                print(f"      NAO decodifiquei. inicio: {amostra}")
                continue
            como, obj = r
            print(f"      decodificado como: {como}")
            if isinstance(obj, (bytes, bytearray)):
                print(f"      binario, {len(obj)} bytes")
                continue
            if isinstance(obj, dict):
                print(f"      chaves de topo: {', '.join(list(obj)[:12])}")
            apps, textos = numeros(obj)
            print(f"      {len(apps)} valores com cara de appid")
            if apps:
                ordenados = sorted(apps)
                print(f"      primeiros: {', '.join(str(a) for a in ordenados[:15])}")
                print(f"      no librarycache: {len(apps & conhecidos)} de {len(apps)}")
            if textos:
                print(f"      {len(textos)} campos de texto (nao exibidos)")
            m = re.search(r"_(\d+)$", chave)
            if m and int(m.group(1)) in membros:
                uniao |= apps
                print("      ^ este e um membro da sua family")

        if uniao:
            print(f"\n  UNIAO dos membros da family: {len(uniao)} appids")
            print(f"  destes, no librarycache: {len(uniao & conhecidos)}")
            print("  (compare com os 470 que a barra lateral mostra)")
        print()

    print("Pronto. Nada foi alterado. Me mande esta saida inteira.")


if __name__ == "__main__":
    main()
