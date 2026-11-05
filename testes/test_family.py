"""
Testa a deteccao de Family Share sem precisar de um Steam real.

Monta um appcache/packageinfo.vdf sintetico nos dois formatos que o
cliente usa, mais um librarycache de mentira, e confere que a subtracao
"biblioteca - meus" chega no resultado certo - e que nos casos duvidosos
a resposta e "nao sei" em vez de chute.
"""
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import core

# o monolito antigo encerra com sys.exit; o core novo levanta ErroCore.
# o mesmo teste serve pros dois.
ERRO = getattr(core, "ErroCore", SystemExit)


# ---- escritor de KV binaria, so pra gerar os fixtures -------------------

def kv(pares):
    """dict -> bytes de uma arvore KV binaria (sem o 0x08 final)."""
    saida = b""
    for chave, valor in pares.items():
        k = chave.encode() + b"\0"
        if isinstance(valor, dict):
            saida += b"\x00" + k + kv(valor) + b"\x08"
        elif isinstance(valor, str):
            saida += b"\x01" + k + valor.encode() + b"\0"
        else:
            saida += b"\x02" + k + struct.pack("<i", valor)
    return saida


def packageinfo(pacotes, magia=0x06565527):
    """{pid: [appids]} -> bytes de um packageinfo.vdf."""
    out = struct.pack("<II", magia, 1)
    extra = b"\xaa" * 8 if magia == 0x06565528 else b""
    for pid, apps in pacotes.items():
        out += struct.pack("<I", pid)
        out += b"\x11" * 20 + struct.pack("<I", 7) + extra
        corpo = {str(pid): {"appids": {str(i): a for i, a in enumerate(apps)}}}
        out += kv(corpo) + b"\x08"
    out += struct.pack("<I", 0xFFFFFFFF)
    return out


def localconfig(tmp, membros=(), caches=None, user="9"):
    """
    Escreve um localconfig.vdf com FamilyGroup e o cache WebStorage, na
    mesma forma que o cliente usa:
      FriendsOwnedGames_storage              -> {"m_rgStorageKeys":[...]}
      FriendsOwnedGames_storage_<accountid>  -> {"version":1,
                                                 "data":{"setApps":[...]},
                                                 "lastFetchTimeMS":ms}
    """
    import time
    caches = caches or {}
    def esc(v):
        return v.replace("\\", "\\\\").replace('"', '\\"')
    L = ['"UserLocalConfigStore"', "{"]
    if membros:
        L += ['\t"FamilyGroup"', "\t{", '\t\t"groupid"\t"999999"',
              '\t\t"members"', "\t\t{"]
        for i, a in enumerate(membros):
            L += [f'\t\t\t"{i}"', "\t\t\t{",
                  f'\t\t\t\t"accountid"\t"{a}"', '\t\t\t\t"role"\t"1"',
                  "\t\t\t}"]
        L += ["\t\t}", "\t}"]
    L += ['\t"WebStorage"', "\t{"]
    if caches:
        idx = json.dumps({"m_rgStorageKeys": sorted(caches)})
        L.append(f'\t\t"FriendsOwnedGames_storage"\t"{esc(idx)}"')
        for conta, apps in sorted(caches.items()):
            v = json.dumps({"version": 1, "data": {"setApps": sorted(apps)},
                            "lastFetchTimeMS": int(time.time() * 1000)})
            L.append(f'\t\t"FriendsOwnedGames_storage_{conta}"\t"{esc(v)}"')
    L += ["\t}", "}"]
    d = tmp / "userdata" / user / "config"
    d.mkdir(parents=True, exist_ok=True)
    (d / "localconfig.vdf").write_text("\n".join(L) + "\n", encoding="utf-8")
    return d / "localconfig.vdf"


def montar_steam(tmp, pacotes, cache_appids, magia=0x06565527, antigo=False):
    ap = tmp / "appcache"
    (ap / "librarycache").mkdir(parents=True, exist_ok=True)
    if pacotes is not None:
        (ap / "packageinfo.vdf").write_bytes(packageinfo(pacotes, magia))
    for a in cache_appids:
        if antigo:
            (ap / "librarycache" / f"{a}_library_600x900.jpg").write_bytes(b"x")
        else:
            (ap / "librarycache" / str(a)).mkdir(exist_ok=True)
    return tmp


def userdata(tmp, apps, pacotes, nome="userdata.json"):
    p = tmp / nome
    p.write_text(json.dumps({"rgOwnedApps": sorted(apps),
                             "rgOwnedPackages": sorted(pacotes)}))
    return p


# ---- testes -------------------------------------------------------------

def t_parser_dois_formatos(tmp):
    for magia in (0x06565527, 0x06565528):
        s = montar_steam(tmp / f"m{magia}", {10: [440, 570], 20: [730]}, [])
        got = core.apps_dos_pacotes(s, [10, 20])
        assert got == {440, 570, 730}, (hex(magia), got)
    return "parser le os dois formatos de cabecalho"


def t_subtracao(tmp):
    # tenho o pacote 10 (= apps 440, 570) e o app solto 620.
    # o cache conhece 440, 570, 620, 8930 e 250180 -> os dois ultimos
    # estao na biblioteca sem serem meus: emprestados.
    s = montar_steam(tmp / "sub", {10: [440, 570]},
                     [440, 570, 620, 8930, 250180])
    ud = userdata(tmp / "sub", [620], [10])
    fam, motivo, _ = core.detectar_family(s, 9, ud, "subtracao")
    assert fam == {8930, 250180}, fam
    assert motivo == "", motivo
    return "subtracao acha so os emprestados"


def t_pacote_cobre_jogo_gratuito(tmp):
    # 620 so existe dentro do pacote, nunca em rgOwnedApps. Se o parser de
    # pacote falhasse, ele seria acusado de emprestado. Esse e o bug que o
    # rgOwnedPackages existe pra evitar.
    s = montar_steam(tmp / "free", {10: [620]}, [620, 8930])
    ud = userdata(tmp / "free", [], [10])
    fam, _, _ = core.detectar_family(s, 9, ud, "subtracao")
    assert fam == {8930}, fam
    return "jogo que so vive em pacote nao vira emprestado"


def t_layout_antigo_do_cache(tmp):
    s = montar_steam(tmp / "velho", {10: [440]}, [440, 8930], antigo=True)
    ud = userdata(tmp / "velho", [], [10])
    fam, _, _ = core.detectar_family(s, 9, ud, "subtracao")
    assert fam == {8930}, fam
    return "cache no layout antigo (arquivos soltos) tambem e lido"


def t_sem_packageinfo_nao_chuta(tmp):
    s = montar_steam(tmp / "nopkg", None, [440, 8930])
    ud = userdata(tmp / "nopkg", [440], [10])
    fam, motivo, _ = core.detectar_family(s, 9, ud, "subtracao")
    assert fam == set(), fam
    assert "packageinfo" in motivo, motivo
    return "sem packageinfo.vdf devolve 'nao sei', nao chute"


def t_cache_de_outra_conta_nao_chuta(tmp):
    # tenho 10 pacotes, o arquivo so conhece 1: cache de outra conta.
    s = montar_steam(tmp / "outra", {10: [440]}, [440, 8930])
    ud = userdata(tmp / "outra", [], list(range(10, 20)))
    fam, motivo, _ = core.detectar_family(s, 9, ud, "subtracao")
    assert fam == set(), fam
    assert "outra conta" in motivo, motivo
    return "cache de outra conta devolve 'nao sei'"


def t_magia_desconhecida_nao_chuta(tmp):
    s = montar_steam(tmp / "magia", {10: [440]}, [440, 8930], magia=0x06565599)
    ud = userdata(tmp / "magia", [], [10])
    fam, _, _ = core.detectar_family(s, 9, ud)
    assert fam == set(), fam
    return "cabecalho desconhecido devolve 'nao sei'"


def t_userdata_sem_login(tmp):
    s = montar_steam(tmp / "login", {10: [440]}, [440])
    p = (tmp / "login" / "vazio.json")
    p.write_text(json.dumps({"rgOwnedApps": [], "rgOwnedPackages": []}))
    try:
        core.detectar_family(s, 9, p, "subtracao")
    except ERRO as e:
        assert "logado" in str(e), e
        return "userdata vazio explica que faltou login"
    raise AssertionError("deveria ter recusado o arquivo")


def t_userdata_html(tmp):
    s = montar_steam(tmp / "html", {10: [440]}, [440])
    p = tmp / "html" / "pagina.json"
    p.write_text("<!DOCTYPE html><html><body>Sign in</body></html>")
    try:
        core.detectar_family(s, 9, p, "subtracao")
    except ERRO as e:
        assert "HTML" in str(e), e
        return "pagina HTML salva por engano da erro explicado"
    raise AssertionError("deveria ter recusado o arquivo")


def t_cache_vazio(tmp):
    s = montar_steam(tmp / "vazio", {10: [440]}, [])
    ud = userdata(tmp / "vazio", [440], [10])
    fam, motivo, _ = core.detectar_family(s, 9, ud)
    assert fam == set() and "librarycache" in motivo, (fam, motivo)
    return "librarycache vazio devolve 'nao sei'"


def t_lista_family_substituida(tmp):
    """family_automatico troca os appids de uma lista que veio de colecao."""
    badges = Path(__file__).resolve().parent.parent / "badges"
    listas = [{"nome": "family", "ordem": 1, "appids": {1, 2, 3},
               "origens": ["04-Zerados (Family)"], "img": None,
               "camada": {"tipo": "canto"}}]
    core.family_automatico(listas, {99, 100}, badges, {})
    assert listas[0]["appids"] == {99, 100}, listas[0]["appids"]
    assert listas[0]["origens"] == ["Family Share (detectado)"]
    return "deteccao substitui a lista que vinha da colecao"


def t_lista_family_criada(tmp):
    """Sem colecao mapeando family, a lista nasce da deteccao."""
    badges = Path(__file__).resolve().parent.parent / "badges"
    if not (badges / "family.png").exists():
        return "SKIP: badges/family.png nao esta aqui"
    cfg = {"hierarquia": ["platinado", "family", "zerado"],
           "camadas": {"family": {"tipo": "canto", "canto": "tl"}}}
    listas = [{"nome": "zerado", "ordem": 2, "appids": {7}, "origens": [],
               "img": None, "camada": {}}]
    core.family_automatico(listas, {99}, badges, cfg)
    fam = [l for l in listas if l["nome"] == "family"]
    assert len(fam) == 1, listas
    assert fam[0]["appids"] == {99}
    assert fam[0]["ordem"] == 1, fam[0]["ordem"]
    assert fam[0]["camada"]["tipo"] == "canto"
    assert listas[0]["nome"] == "family", "deve vir antes de zerado"
    return "lista de family nasce da deteccao, na ordem da hierarquia"



# ---- cache dos membros da family (WebStorage) ---------------------------

def t_ws_le_cache_dos_membros(tmp):
    s = montar_steam(tmp / "ws1", {10: [440]}, [])
    localconfig(s, membros=[9, 111, 222],
                caches={111: [440, 8930], 222: [250180, 8930]})
    uniao, diag = core.apps_dos_membros(s, 9)
    assert uniao == {440, 8930, 250180}, uniao
    assert diag["por_membro"][111][0] == 2
    assert diag["sem_cache"] == [], diag["sem_cache"]
    assert diag["grupo"] == "999999", diag["grupo"]
    return "le o cache de cada membro e une"


def t_ws_ignora_version_e_timestamp(tmp):
    """O bug que a sonda revelou: raspar inteiros pega version=1 como appid."""
    s = montar_steam(tmp / "ws2", {10: [440]}, [])
    localconfig(s, membros=[9, 111], caches={111: [440, 8930]})
    uniao, _ = core.apps_dos_membros(s, 9)
    assert 1 not in uniao, "version=1 vazou como appid"
    assert all(a > 100 for a in uniao), uniao
    return "le data.setApps, nao raspa version nem lastFetchTimeMS"


def t_ws_membro_sem_cache_e_avisado(tmp):
    s = montar_steam(tmp / "ws3", {10: [440]}, [])
    localconfig(s, membros=[9, 111, 222, 333], caches={111: [440]})
    _, diag = core.apps_dos_membros(s, 9)
    assert diag["sem_cache"] == [222, 333], diag["sem_cache"]
    return "membro sem cache vira aviso (ponto cego declarado)"


def t_ws_sem_family_nao_inventa(tmp):
    s = montar_steam(tmp / "ws4", {10: [440]}, [])
    localconfig(s, membros=[], caches={})
    uniao, diag = core.apps_dos_membros(s, 9)
    assert uniao == set() and diag["grupo"] is None
    return "sem FamilyGroup devolve vazio, nao chute"


def t_loja_inclui_emprestado_entao_subtracao_falha(tmp):
    """
    A descoberta que derrubou o metodo antigo, virada em teste.

    A lista da loja (rgOwnedApps e rgOwnedPackages) diz o que voce PODE
    JOGAR. Com o Steam Families o emprestado entra nela. Entao subtrair a
    lista da loja apaga exatamente o que se procura.

    Aqui 250180 e emprestado E aparece na lista da loja, como acontece de
    verdade. A subtracao o perde; o padrao (cache dos membros) o acha.
    """
    base = tmp / "loja"
    montar_steam(base, {10: [440, 630, 250180]},
                 [440, 630, 250180, 8930])
    localconfig(base, membros=[9, 111], caches={111: [250180, 8930]})
    ud = userdata(base, [250180], [10])      # a loja o lista como "seu"

    sub, _, _ = core.detectar_family(base, 9, ud, "subtracao")
    assert 250180 not in sub, "a subtracao deveria perde-lo (e esse e o bug)"

    auto, _, diag = core.detectar_family(base, 9, ud, "auto")
    assert 250180 in auto, auto
    assert diag["metodo"] == "membros", diag["metodo"]
    return "subtracao perde emprestado que a loja lista como seu; auto nao"



def t_auto_cai_pra_membros_sem_userdata(tmp):
    s = montar_steam(tmp / "au1", {10: [440]}, [440, 8930, 250180])
    localconfig(s, membros=[9, 111], caches={111: [8930, 250180]})
    fam, motivo, diag = core.detectar_family(s, 9, None, "auto")
    assert fam == {8930, 250180}, fam
    assert diag["metodo"] == "membros", diag["metodo"]
    assert motivo == ""
    return "sem userdata.json, auto usa o cache local sozinho"


def t_auto_prefere_appmanifest_a_subtracao(tmp):
    """Sem cache de membros, auto usa o appmanifest - nao a subtracao."""
    base = tmp / "au2"
    montar_steam(base, {10: [440]}, [440, 8930])
    sa = base / "steamapps"; sa.mkdir(parents=True, exist_ok=True)
    (sa / "appmanifest_8930.acf").write_text(
        '"AppState"\n{\n\t"appid"\t"8930"\n\t"SharedDepots"\n\t{\n\t\t"1"\t"2"\n\t}\n}\n')
    ud = userdata(base, [], [10])
    fam, _, diag = core.detectar_family(base, 9, ud, "auto")
    assert fam == {8930}, fam
    assert diag["metodo"] == "appmanifest", diag["metodo"]
    return "sem cache de membros, auto usa o appmanifest"



def t_sem_nada_explica(tmp):
    s = montar_steam(tmp / "nada", {10: [440]}, [440, 8930])
    fam, motivo, _ = core.detectar_family(s, 9, None, "auto")
    assert fam == set()
    assert "Family" in motivo or "userdata" in motivo, motivo
    return "sem userdata e sem family, explica em vez de chutar"


def t_resumo_nao_explode(tmp):
    s = montar_steam(tmp / "rz", {10: [440]}, [440, 8930, 250180])
    localconfig(s, membros=[9, 111, 222], caches={111: [8930]})
    ud = userdata(tmp / "rz", [], [10])
    _, _, diag = core.detectar_family(s, 9, ud, "auto")
    linhas = core.resumo_family(diag)
    assert any("cache local dos membros" in l for l in linhas), linhas
    assert any("SEM cache" in l for l in linhas), linhas
    return "resumo descreve o metodo e declara o ponto cego"


def t_appmanifest_sobrepoe_deducao(tmp):
    """
    SharedDepots e exato: entra no resultado mesmo que a deducao nao veja.
    E o inverso tambem: instalado sem SharedDepots e seu, sai do resultado
    mesmo que a deducao o tenha marcado.
    """
    base = tmp / "amf"
    s = montar_steam(base, {10: [440]}, [440, 8930, 250180, 555, 666])
    sa = base / "steamapps"; sa.mkdir(parents=True, exist_ok=True)
    # 555 instalado e emprestado -> tem que entrar
    (sa / "appmanifest_555.acf").write_text(
        '"AppState"\n{\n\t"appid"\t"555"\n\t"SharedDepots"\n\t{\n\t\t"556"\t"7656119"\n\t}\n}\n')
    # 666 instalado e seu -> tem que sair
    (sa / "appmanifest_666.acf").write_text('"AppState"\n{\n\t"appid"\t"666"\n}\n')
    emprestados, proprios = core.instalados_por_origem(base)
    assert emprestados == {555}, emprestados
    assert proprios == {666}, proprios

    # a deducao sozinha nao veria 555 (nenhum membro cacheado o tem)
    localconfig(base, membros=[9, 111], caches={111: [8930, 250180, 666]})
    ud = userdata(base, [], [10])
    fam, _, diag = core.detectar_family(base, 9, ud, "auto")
    assert 555 in fam, "SharedDepots deveria ter entrado"
    assert 666 not in fam, "instalado sem SharedDepots deveria ter saido"
    assert diag["certos"] == 1, diag["certos"]
    return "appmanifest sobrepoe a deducao nos dois sentidos"


def t_conferencia_nao_e_circular(tmp):
    """
    A armadilha: o resultado final injeta os SharedDepots a forca. Se a
    conferencia medisse o resultado final, daria 100% por construcao e
    nao diria nada. Ela tem que medir a DEDUCAO com o sinal exato
    desligado.

    Montagem: 555 e 777 sao emprestados e instalados, mas so o 555 esta
    no cache de um membro. A deducao sozinha enxerga o 555 e perde o 777.
    O 666 e seu e instalado, e nenhum sinal o marca.
    """
    base = tmp / "cf"
    montar_steam(base, {10: [440]}, [440, 8930, 555, 666, 777])
    sa = base / "steamapps"; sa.mkdir(parents=True, exist_ok=True)
    for a in (555, 777):
        (sa / f"appmanifest_{a}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t"{a}"\n\t"SharedDepots"\n\t{{\n\t\t"1"\t"2"\n\t}}\n}}\n')
    (sa / "appmanifest_666.acf").write_text('"AppState"\n{\n\t"appid"\t"666"\n}\n')
    localconfig(base, membros=[9, 111], caches={111: [8930, 555]})
    ud = userdata(base, [], [10])

    final, linhas = core.conferir_family(base, 9, ud, "auto")
    txt = "\n".join(linhas)
    assert "emprestados instalados    : 2" in txt, txt
    # a deducao pega so o 555 -> 50%, nao 100%
    assert "a dedução sozinha pegou   : 1 (50%)" in txt, txt
    assert "PERDEU 1: 777" in txt, txt
    # mas o resultado final resgata o 777 pelo appmanifest
    assert 777 in final and 555 in final, final
    assert 666 not in final, final
    # e o aviso de extrapolacao aparece
    assert "o appmanifest não resgata" in txt, txt
    return "conferencia mede a deducao, nao o sinal exato (nao e circular)"


def t_usar_exatos_desliga(tmp):
    base = tmp / "ux"
    montar_steam(base, {10: [440]}, [440, 555])
    sa = base / "steamapps"; sa.mkdir(parents=True, exist_ok=True)
    (sa / "appmanifest_555.acf").write_text(
        '"AppState"\n{\n\t"appid"\t"555"\n\t"SharedDepots"\n\t{\n\t\t"1"\t"2"\n\t}\n}\n')
    localconfig(base, membros=[9, 111], caches={111: [999]})
    ud = userdata(base, [], [10])
    com, _, _ = core.detectar_family(base, 9, ud, "auto", usar_exatos=True)
    sem, _, _ = core.detectar_family(base, 9, ud, "auto", usar_exatos=False)
    assert 555 in com, com
    assert 555 not in sem, sem
    return "usar_exatos=False tira mesmo o appmanifest da conta"


def t_libraryfolders_outros_discos(tmp):
    base = tmp / "lf"
    s = montar_steam(base, {10: [440]}, [440])
    sa = base / "steamapps"; sa.mkdir(parents=True, exist_ok=True)
    outro = tmp / "D_Games"; (outro / "steamapps").mkdir(parents=True, exist_ok=True)
    (sa / "libraryfolders.vdf").write_text(
        '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t"%s"\n\t}\n}\n'
        % str(outro).replace("\\", "\\\\"))
    (outro / "steamapps" / "appmanifest_999.acf").write_text(
        '"AppState"\n{\n\t"appid"\t"999"\n\t"SharedDepots"\n\t{\n\t\t"1"\t"2"\n\t}\n}\n')
    emprestados, _ = core.instalados_por_origem(base)
    assert 999 in emprestados, emprestados
    return "acha jogos instalados em biblioteca de outro disco"


def main():
    import tempfile
    testes = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        falhas = 0
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
