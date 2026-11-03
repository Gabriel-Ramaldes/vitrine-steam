"""
Procura, nos arquivos do Steam, qualquer vestigio da lista do Steam Family.

So LE. Nao altera nada, nao acessa a rede, e nao imprime conteudo de
arquivo: so caminhos, nomes de chave e contagens. A ideia e descobrir se
a lista de 470 jogos do "STEAM FAMILY" da barra lateral existe em disco
ou se o cliente a mantem so na memoria.

Uso:
    python sonda_family.py
    python sonda_family.py --steam "D:\\Steam"
"""
import argparse
import json
import os
import re
import struct
import sys
from pathlib import Path

LIMITE_ARQUIVO = 80 << 20        # nao abre nada acima de 80 MB
TOPO = 12                        # quantos resultados mostrar por secao

# Termos que apareceriam num arquivo que guarde a lista de emprestados.
TERMOS = [b"familygroup", b"FamilyGroup", b"family_group",
          b"SharedLibrary", b"shared_library", b"rgSharedLibrary",
          b"sharedlibrary", b"FamilyGroups", b"IFamilyGroups",
          b"borrow", b"Borrow", b"lender", b"Lender",
          b"shared_apps", b"SharedApps", b"excluded_apps"]


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
        if (c / "userdata").is_dir() or (c / "steamapps").is_dir():
            return c
    return None


def contas(steam):
    ud = steam / "userdata"
    if not ud.is_dir():
        return []
    return [d for d in ud.iterdir() if d.is_dir() and d.name.isdigit()]


# ---------------------------------------------------------------------

def secao_cloudstorage(steam, conta):
    print(f"\n[1] cloudstorage de {conta.name}")
    pasta = conta / "config" / "cloudstorage"
    if not pasta.is_dir():
        print("    (pasta nao existe)")
        return
    for f in sorted(pasta.iterdir()):
        if not f.is_file():
            continue
        print(f"    {f.name}  ({f.stat().st_size:,} bytes)")
        try:
            dados = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"        nao e JSON legivel ({type(e).__name__})")
            continue
        if not isinstance(dados, list):
            print(f"        forma inesperada: {type(dados).__name__}")
            continue
        familias = collections_count = 0
        prefixos = {}
        for par in dados:
            if not (isinstance(par, list) and len(par) == 2):
                continue
            chave = str(par[0])
            pref = chave.split(".")[0] if "." in chave else re.sub(r"[-_]?\d+$", "", chave)
            prefixos[pref] = prefixos.get(pref, 0) + 1
            baixa = chave.lower()
            if "family" in baixa or "shared" in baixa or "borrow" in baixa:
                familias += 1
                print(f"        >>> CHAVE INTERESSANTE: {chave}")
            if baixa.startswith("user-collections."):
                collections_count += 1
        print(f"        {len(dados)} pares | {collections_count} colecoes "
              f"| {familias} chaves com family/shared")
        top = sorted(prefixos.items(), key=lambda kv: -kv[1])[:8]
        print("        prefixos: " + ", ".join(f"{k}={v}" for k, v in top))


def secao_manifestos(steam):
    print("\n[2] appmanifest instalados (SharedDepots = emprestado e instalado)")
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
    total = compartilhados = 0
    exemplos = []
    for r in raizes:
        if not r.is_dir():
            continue
        for f in r.glob("appmanifest_*.acf"):
            total += 1
            try:
                t = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "SharedDepots" in t:
                compartilhados += 1
                m = re.search(r'"appid"\s+"(\d+)"', t)
                if m and len(exemplos) < TOPO:
                    exemplos.append(m.group(1))
    print(f"    {total} jogos instalados, {compartilhados} com SharedDepots")
    if exemplos:
        print(f"    exemplos: {', '.join(exemplos)}")
    print("    (so pega emprestado E instalado - parcial por natureza)")


def secao_librarycache(steam):
    print("\n[3] appcache/librarycache (a 'biblioteca que o cliente conhece')")
    cache = steam / "appcache" / "librarycache"
    if not cache.is_dir():
        print("    (nao existe)")
        return
    pastas = arquivos = 0
    try:
        for item in cache.iterdir():
            if item.is_dir() and item.name.isdigit():
                pastas += 1
            elif item.is_file() and re.match(r"^\d{1,10}_library_", item.name):
                arquivos += 1
    except OSError as e:
        print(f"    erro ao listar: {e}")
        return
    print(f"    {pastas} pastas por appid, {arquivos} arquivos no layout antigo")
    pkg = steam / "appcache" / "packageinfo.vdf"
    if pkg.is_file():
        dados = pkg.read_bytes()[:4]
        magia = struct.unpack_from("<I", dados, 0)[0] if len(dados) == 4 else 0
        conhecida = magia in (0x06565527, 0x06565528)
        print(f"    packageinfo.vdf: {pkg.stat().st_size:,} bytes, "
              f"magia 0x{magia:08X} {'(conhecida)' if conhecida else '(DESCONHECIDA)'}")
    else:
        print("    packageinfo.vdf: NAO EXISTE")


def secao_varredura(steam):
    print("\n[4] varredura por termos de family/shared")
    print("    (config, userdata e appcache; pula arte e pastas de jogo)")
    pulares = {"librarycache", "steamapps", "depotcache", "music", "logs",
               "dumps", "steamui", "tenfoot", "resource", "public", "bin",
               "controller_base", "graphics", "friends", "package"}
    achados = []
    vistos = 0
    for base in (steam / "config", steam / "userdata", steam / "appcache"):
        if not base.is_dir():
            continue
        for raiz, dirs, arqs in os.walk(base):
            dirs[:] = [d for d in dirs if d.lower() not in pulares]
            for nome in arqs:
                f = Path(raiz) / nome
                try:
                    tam = f.stat().st_size
                except OSError:
                    continue
                if tam == 0 or tam > LIMITE_ARQUIVO:
                    continue
                if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp",
                                        ".ico", ".mp3", ".webm", ".tga"):
                    continue
                vistos += 1
                try:
                    dados = f.read_bytes()
                except OSError:
                    continue
                batidas = [t.decode() for t in TERMOS if t in dados]
                if batidas:
                    achados.append((len(batidas), f, tam, sorted(set(batidas))[:5]))
    print(f"    {vistos} arquivos lidos")
    if not achados:
        print("    NADA encontrado: nenhum arquivo menciona family/shared.")
        return
    achados.sort(key=lambda x: -x[0])
    for _, f, tam, termos in achados[:TOPO]:
        try:
            rel = f.relative_to(steam)
        except ValueError:
            rel = f
        print(f"    >>> {rel}  ({tam:,} bytes)")
        print(f"        termos: {', '.join(termos)}")
    if len(achados) > TOPO:
        print(f"    ... e mais {len(achados) - TOPO} arquivos")


def secao_bancos(steam):
    print("\n[5] bancos locais do cliente (leveldb/indexeddb)")
    alvos = []
    for base in (steam / "config", steam / "userdata"):
        if not base.is_dir():
            continue
        for raiz, dirs, _ in os.walk(base):
            for d in dirs:
                if d.lower() in ("leveldb", "indexeddb", "local storage",
                                 "session storage", "databases"):
                    alvos.append(Path(raiz) / d)
    if not alvos:
        print("    nenhum encontrado")
        return
    for a in alvos[:TOPO]:
        try:
            n = sum(1 for _ in a.rglob("*") if _.is_file())
            tam = sum(f.stat().st_size for f in a.rglob("*") if f.is_file())
        except OSError:
            n = tam = 0
        try:
            rel = a.relative_to(steam)
        except ValueError:
            rel = a
        print(f"    {rel}  ({n} arquivos, {tam:,} bytes)")


def secao_licencas(steam, cs):
    """
    A parte que falta pra dispensar o userdata.json: a lista do que e SEU.
    Se alguma licenca/pacote estiver em disco, da pra fazer a subtracao
    inteira offline. Procura em config.vdf e localconfig.vdf.
    """
    print("\n[6] licencas/pacotes em disco (dispensaria o userdata.json?)")
    alvos = [steam / "config" / "config.vdf"]
    for c in cs:
        alvos.append(c / "config" / "localconfig.vdf")
    chaves = (b"Licenses", b"licenses", b"OwnedApps", b"rgLicenses",
              b"PackageID", b"packageid", b"owned", b"Owned",
              b"apptickets", b"AppTickets", b"LicenseFlags")
    for f in alvos:
        if not f.is_file():
            print(f"    {f.name}: nao existe")
            continue
        try:
            dados = f.read_bytes()
        except OSError as e:
            print(f"    {f.name}: nao deu pra ler ({e})")
            continue
        achou = sorted({k.decode() for k in chaves if k in dados})
        print(f"    {f.name}  ({len(dados):,} bytes)")
        if achou:
            print(f"        >>> contem: {', '.join(achou)}")
        else:
            print("        nada sobre licenca/propriedade")


def secao_showcases(steam, conta):
    """
    Os nos embutidos da barra lateral. O 'STEAM FAMILY' aparece aqui como
    strCollectionId = shared-familygroup. A pergunta e se junto vem a
    lista de jogos ou so a aparencia do no.
    """
    print(f"\n[7] showcases da barra lateral ({conta.name})")
    f = conta / "config" / "cloudstorage"
    achou_family = False
    if not f.is_dir():
        print("    (pasta nao existe)")
        return
    for arq in sorted(f.glob("cloud-storage-namespace-*.json")):
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(dados, list):
            continue
        for par in dados:
            if not (isinstance(par, list) and len(par) == 2):
                continue
            chave, reg = str(par[0]), par[1]
            if not isinstance(reg, dict):
                continue
            val = reg.get("value")
            if not val:
                continue
            if not chave.startswith("showcases."):
                # tambem procura uma colecao embutida de family
                if "familygroup" in str(val).lower() and chave.startswith("user-collections."):
                    print(f"    >>> COLECAO DE FAMILY: {chave}")
                    achou_family = True
                continue
            try:
                sc = json.loads(val)
            except (ValueError, TypeError):
                continue
            cid = str(sc.get("strCollectionId", ""))
            if not cid:
                continue
            campos = sorted(sc.keys())
            tem_lista = any(c in sc for c in ("added", "rgApps", "apps", "appids"))
            marca = ""
            if "family" in cid.lower() or "shared" in cid.lower():
                marca = "   <<< este e o STEAM FAMILY"
                achou_family = True
            print(f"    {cid:<28} lista de jogos: "
                  f"{'SIM' if tem_lista else 'nao'}{marca}")
            if marca:
                print(f"        campos: {', '.join(campos)}")
    if not achou_family:
        print("    nenhum showcase de family encontrado")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steam", help="caminho do Steam, se a deteccao falhar")
    args = ap.parse_args()

    steam = achar_steam(args.steam)
    if steam is None or not steam.is_dir():
        sys.exit("Nao achei o Steam. Rode com --steam \"C:\\caminho\\Steam\".")
    print("=" * 66)
    print("SONDA: a lista do Steam Family existe em disco?")
    print("=" * 66)
    print(f"Steam: {steam}")

    cs = contas(steam)
    print(f"Contas em userdata: {', '.join(c.name for c in cs) or 'nenhuma'}")
    for c in cs:
        secao_cloudstorage(steam, c)
    secao_manifestos(steam)
    secao_librarycache(steam)
    secao_varredura(steam)
    secao_bancos(steam)
    secao_licencas(steam, cs)
    for c in cs:
        secao_showcases(steam, c)

    print("\n" + "=" * 66)
    print("Pronto. Nada foi alterado. Me mande esta saida inteira.")
    print("=" * 66)


if __name__ == "__main__":
    main()
