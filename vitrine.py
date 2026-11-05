#!/usr/bin/env python3
"""
cli: a linha de comando.

Camada fina sobre core.py. Toda a decisao de o que fazer esta no core;
aqui ficam apenas o parsing dos argumentos, a impressao e as perguntas
de confirmacao. A interface grafica sera outro cliente do mesmo core.
"""
import argparse
import os
import re
import sys

from core import *
import rodar
from core import _assets_de, _buscar_capa_base, _FORCADOS


class RelatorioConsole(Relatorio):
    """Implementacao do canal de saida do core para o terminal."""

    def __init__(self, verboso=False):
        self.verboso = verboso

    def info(self, msg):
        print(msg)

    def aviso(self, msg):
        print(f"[!] {msg}" if not str(msg).startswith("[!]") else msg)

    def detalhe(self, msg):
        if self.verboso:
            print(msg)

    def item(self, i, total, appid, rotulo, origem, extra=""):
        print(f"[{i}/{total}] {appid}: {rotulo}  (capa via {origem}){extra}")


def _comando():
    """
    Como o usuario invocou isto, pra que as dicas de comando sejam
    copiaveis tanto rodando pelo Python quanto pelo executavel.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).name
    return f"python {Path(sys.argv[0]).name}"


def _confirmar_terminal(msg):
    """A guarda contra remocao em massa, na CLI."""
    print(f"\n[!] {msg}")
    return input("    Digite REMOVER para confirmar, ou Enter para pular: "
                 ).strip().upper() == "REMOVER"


def aplicar_family(listas, args, steam_path, user_id, badges_dir, config):
    """
    Resolve de onde sai o status 'family'.

    Ordem de confianca, e ela e empirica:

      1. uma Colecao mapeada pra 'family'. Voce a monta na propria tela
         do Steam, que sabe exatamente quais jogos sao emprestados. E a
         unica fonte completa que existe - veja o README.
      2. o appmanifest dos instalados (SharedDepots). Exato, mas so
         cobre o que esta instalado.
      3. o cache local da biblioteca dos membros. Incompleto: medido em
         23% de acerto com --comparar-family.

    Nao existe fonte melhor em disco. Toda lista que a Steam serve na
    web - dynamicstore, pagina do perfil - diz o que voce PODE JOGAR, e
    inclui o emprestado. Isso foi medido, nao suposto.
    """
    if args.sem_family or config.get("family_auto") is False:
        return listas

    da_colecao = {a for l in listas if l["nome"] == "family" for a in l["appids"]}
    fonte = config.get("family_fonte", "auto")
    if args.family_metodo != "auto":
        fonte = "deteccao"

    if da_colecao and fonte in ("auto", "colecao"):
        conhecidos = biblioteca_do_cache(steam_path)
        exatos, meus = instalados_por_origem(steam_path)
        fam = (da_colecao | (exatos & conhecidos)) - meus
        listas = family_automatico(listas, fam, badges_dir, config)
        for l in listas:
            if l["nome"] == "family":
                l["origens"] = ["Coleção do Steam + appmanifest"]
        print(f"Family Share: {len(fam)} jogos, da sua Coleção de Family.")
        novos = len(fam - da_colecao)
        if novos:
            print(f"  (+{novos} que o appmanifest confirmou e a coleção não tinha)")
        print("")
        return listas

    metodo = "auto" if args.family_metodo == "cruzado" else args.family_metodo
    caminho = Path(args.userdata) if args.userdata else achar_userdata_json()
    try:
        fam, motivo, diag = detectar_family(steam_path, user_id, caminho, metodo)
    except ErroCore as e:
        print(f"[!] Family Share: {e}\n    Seguindo com o que vier das Coleções.\n")
        return listas

    if not fam:
        print(f"[!] Family Share não detectado: {motivo}")
        print("    Seguindo com o que vier das Coleções.\n")
        return listas

    listas = family_automatico(listas, fam, badges_dir, config)
    print(f"Family Share: {len(fam)} jogos deduzidos.")
    for linha in resumo_family(diag):
        print(f"  {linha}")
    print("  [!] a dedução e incompleta. A lista completa de emprestados não")
    print("      existe em disco: a Steam a serve do servidor. O jeito certo e")
    print("      criar uma Coleção a partir da aba STEAM FAMILY da biblioteca")
    print("      e mapea-la pra 'family' no config.json. Veja o README.")
    print("")
    return listas


def _comando():
    """
    Como o usuario invocou isto, pra que as dicas de comando sejam
    copiaveis tanto rodando pelo Python quanto pelo executavel.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).name
    return f"python {Path(sys.argv[0]).name}"


def main():
    ap = argparse.ArgumentParser(
        description="Aplica um badge PNG sobre as capas da biblioteca Steam.")
    ap.add_argument("--badges", default=BADGES_DIR_NAME,
                    help=f"pasta com os PNG dos badges (padrão: {BADGES_DIR_NAME}/)")
    ap.add_argument("--moldura", action="store_true",
                    help="monta as capas no formato caixa (molduras/)")
    ap.add_argument("--diag-auto", metavar="APPIDS",
                    help="diagnostico: o que a API da loja diz sobre a capa destes jogos")
    ap.add_argument("--forcar-auto", metavar="APPIDS",
                    help="trata estes appids como capa fabricada, mesmo sem a API confirmar")
    ap.add_argument("--todos", action="store_true",
                    help="emoldura a biblioteca inteira; badge só em quem tem coleção")
    ap.add_argument("--limpar-sobras", action="store_true",
                    help="remove do grid as capas verticais que não foram feitas por nos")
    ap.add_argument("--trocar-auto", action="store_true",
                    help="troca capas que a Steam fabricou do header por arte da SteamGridDB")
    ap.add_argument("--so-auto", action="store_true",
                    help="processa apenas os jogos com capa fabricada pela Steam")
    ap.add_argument("--sem-moldura", action="store_true",
                    help="ignora \"moldura\": true do config e usa badge solto")
    ap.add_argument("--colecoes", action="store_true",
                    help="aceito por compatibilidade; as Coleções já são a única fonte")
    ap.add_argument("--listar-colecoes", action="store_true",
                    help="mostra as Coleções do Steam encontradas e sai")
    ap.add_argument("--userdata", metavar="ARQUIVO",
                    help="userdata.json da loja, para detectar Family Share "
                         "(padrão: procura nesta pasta, em Downloads e na Área de Trabalho)")
    ap.add_argument("--sem-family", action="store_true",
                    help="não detecta Family Share; usa só o que vier das Coleções")
    ap.add_argument("--family-metodo", choices=("auto", "cruzado", "subtracao", "membros"),
                    default="auto",
                    help="como detectar Family Share: auto usa o cache local "
                         "dos membros mais o appmanifest; subtração usa a lista "
                         "da loja (medido em 6% de acerto, não recomendado)")
    ap.add_argument("--listar-family", action="store_true",
                    help="mostra os jogos detectados como emprestados e sai")
    ap.add_argument("--conferir-family", action="store_true",
                    help="mede a detecção contra os jogos instalados, onde o "
                         "appmanifest da a resposta exata")
    ap.add_argument("--comparar-family", action="store_true",
                    help="mede varias formas de deduzir Family Share contra o "
                         "mesmo gabarito, pra escolher a certa")
    ap.add_argument("--config", default="config.json", help="config opcional: hierarquia e ajustes por lista")
    ap.add_argument("--dry-run", action="store_true",
                    help="não toca no Steam; salva os resultados em ./preview/")
    ap.add_argument("--out", default="preview", help="pasta do --dry-run")
    ap.add_argument("--pos", default=None, choices=CORNERS,
                    help="canto: br=inferior dir, bl=inferior esq, tr=superior dir, tl=superior esq")
    ap.add_argument("--scale", type=float, default=None, help="tamanho do badge (fracao da largura)")
    ap.add_argument("--margin", type=float, default=None, help="margem da borda (fracao da largura)")
    ap.add_argument("--opacity", type=float, default=None, help="opacidade do badge (0.0 a 1.0)")
    ap.add_argument("--sgdb-key", default=os.environ.get("SGDB_KEY"),
                    help="chave da API do SteamGridDB (ou variável SGDB_KEY)")
    ap.add_argument("--only", help="processa só estes appids, separados por virgula")
    ap.add_argument("--force", action="store_true",
                    help="rebaixa a capa original ignorando o backup")
    ap.add_argument("--restore", action="store_true", help="desfaz: remove os badges aplicados")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="mostra cada chamada a SteamGridDB e o porque das decisoes")
    ap.add_argument("--testar-sgdb", metavar="APPID",
                    help="diagnostico: consulta a SteamGridDB para um appid e sai")
    ap.add_argument("--auditar", action="store_true",
                    help="só mede a qualidade das capas e lista as fracas, sem alterar nada")
    ap.add_argument("--melhorar", action="store_true",
                    help="troca capas fracas por versoes da SteamGridDB (precisa de chave)")
    ap.add_argument("--exigir-ganho", action="store_true",
                    help="só troca se a nova capa tiver nitidez maior (estrito)")
    ap.add_argument("--variante", type=int, default=0,
                    help="pula as N primeiras artes da SteamGridDB (0 = a melhor)")
    ap.add_argument("--limiar", type=float, default=0.45,
                    help="abaixo disso a capa e considerada fraca (padrão: 0.45)")
    ap.add_argument("--reset-backups", action="store_true",
                    help="apaga originais/ para rebaixar todas as capas do zero")
    ap.add_argument("--steam-path", help="caminho do Steam, se a detecção falhar")
    ap.add_argument("--user", help="steamID3 (nome da pasta em userdata/) se tiver varias contas")
    args = ap.parse_args()
    args.pos_set = args.pos is not None
    definir_relatorio(RelatorioConsole(verboso=args.verbose))

    steam_path = find_steam_path(args.steam_path)
    _cfg_inicial = carregar_config(BASE_DIR / args.config)
    grid_dir = find_grid_dir(steam_path, args.user or _cfg_inicial.get("user"))
    user_id = grid_dir.parent.parent.name
    print(f"Steam: {steam_path}")
    print(f"Grid : {grid_dir}\n")

    if args.diag_auto:
        alvo = [int(x) for x in re.findall(r"\d+", args.diag_auto)]
        print(f"Consultando a API da loja para {len(alvo)} jogo(s)...\n")
        carregar_assets(alvo, verbose=args.verbose)
        print(f"{'appid':>9}  {'veredito':<22} arquivo da capa")
        print("-" * 72)
        desconhecidos = []
        for a in alvo:
            ativos = _assets_de(a)
            nome = ativos.get("library_capsule_2x") or ativos.get("library_capsule")
            auto = arte_automatica(a)
            if auto is None:
                veredito = "DESCONHECIDO"
                desconhecidos.append(a)
            elif auto:
                veredito = "fabricada do header"
            else:
                veredito = "capa própria"
            print(f"{a:>9}  {veredito:<22} {nome or '(a API não devolveu assets)'}")
        if desconhecidos:
            print("\n" + "-" * 72)
            print("DESCONHECIDO quer dizer que a API não tem assets para o jogo -")
            print("tipicamente jogos removidos da loja, que perderam a página.")
            print("Nesses casos a detecção não tem como funcionar. Para tratar")
            print("mesmo assim como capa fabricada:")
            print(f"  {_comando()} --todos --só-auto \\")
            print(f"      --forcar-auto {','.join(map(str, desconhecidos))}")
        return

    if args.limpar_sobras:
        # capas verticais no grid que nao constam como nossas: sobras de
        # outra ferramenta. Removidas, a Steam volta a capa oficial.
        nossos = set(load_state().get("aplicados", []))
        sobras = []
        for f in list(grid_dir.glob("*p.png")) + list(grid_dir.glob("*p.jpg")) \
                + list(grid_dir.glob("*p.jpeg")):
            base = f.stem[:-1]
            if base.isdigit() and int(base) not in nossos:
                sobras.append(f)
        if not sobras:
            print("Nenhuma sobra: todas as capas verticais do grid são nossas.")
            return
        print(f"{len(sobras)} capa(s) vertical(is) no grid não foram feitas por nos.")
        print("Removidas, a Steam volta a usar a arte oficial de cada jogo.")
        print("Hero, logo, ícone e banner horizontal NÃO são tocados.\n")
        for f in sobras[:12]:
            print(f"  {f.name}")
        if len(sobras) > 12:
            print(f"  ... e mais {len(sobras) - 12}")
        if args.dry_run:
            print("\n--dry-run: nada foi removido.")
            return
        resp = input("\nDigite REMOVER para confirmar: ").strip()
        if resp.upper() != "REMOVER":
            print("Cancelado.")
            return
        n = 0
        for f in sobras:
            f.unlink(missing_ok=True)
            n += 1
        print(f"{n} removidas. Reinicie o Steam.")
        return

    if args.listar_colecoes:
        colecoes, avisos = ler_colecoes(steam_path, user_id)
        for a in avisos:
            print(f"[!] {a}")
        if not colecoes:
            print("\nNenhuma coleção encontrada. Feche o Steam e tente de novo:")
            print("ele só grava o arquivo de coleções ao sincronizar/sair.")
            return

        print(f"{'coleção':<24} {'nome de lista':<18} jogos")
        print("-" * 52)
        for c in colecoes:
            marca = "  (dinâmica, ignorada)" if c["dinamica"] else ""
            print(f"{c['nome'][:23]:<24} {c['slug'][:21]:<22} "
                  f"{len(c['appids']):>5}{marca}")

        print(f"\nPara usar: {_comando()}          (le as Coleções direto)")
        return

    if args.comparar_family:
        caminho = Path(args.userdata) if args.userdata else achar_userdata_json()
        for l in comparar_family(steam_path, user_id, caminho):
            print(l)
        return

    if args.conferir_family:
        caminho = Path(args.userdata) if args.userdata else achar_userdata_json()
        metodo = "auto" if args.family_metodo == "cruzado" else args.family_metodo
        fam, linhas = conferir_family(steam_path, user_id, caminho, metodo)
        print(f"Detecção: {len(fam)} jogos\n")
        for l in linhas:
            print(l)
        return

    if args.listar_family:
        caminho = Path(args.userdata) if args.userdata else achar_userdata_json()
        metodo = "auto" if args.family_metodo == "cruzado" else args.family_metodo
        if caminho:
            print(f"Lista de propriedade: {caminho}")
        else:
            print("Sem userdata.json: uso só o cache local dos membros.")
        grupo, membros = grupo_family(steam_path, user_id)
        if grupo:
            print(f"Steam Family: grupo {grupo}, {len(membros)} membros")
        print("")
        fam, motivo, diag = detectar_family(steam_path, user_id, caminho, metodo)
        for linha in resumo_family(diag):
            print(f"  {linha}")
        print("")
        if not fam:
            print(f"Não da pra determinar: {motivo}")
            return
        nomes = carregar_assets(sorted(fam)[:60]) or {}
        print(f"{len(fam)} jogos vieram por Family Share:\n")
        for a in sorted(fam)[:60]:
            info = nomes.get(a) or nomes.get(str(a)) or {}
            nome = info.get("name") if isinstance(info, dict) else None
            print(f"  {a:<10} {nome or ''}")
        if len(fam) > 60:
            print(f"  ... e mais {len(fam) - 60}")
        print("\nEstes recebem o canto verde. Jogo seu que aparecer aqui quer")
        print("dizer que a lista de propriedade está velha: baixe de novo.")
        return

    if args.restore:
        restore(grid_dir)
        return

    if args.testar_sgdb:
        appid = int(re.findall(r"\d+", args.testar_sgdb)[0])
        print(f"=== diagnostico SteamGridDB para appid {appid} ===\n")

        if not args.sgdb_key:
            print("SEM CHAVE. Defina SGDB_KEY ou passe --sgdb-key.")
            return
        print(f"chave: ...{args.sgdb_key[-4:]} ({len(args.sgdb_key)} caracteres) - validada\n")

        print("1) capa que o script usaria hoje:")
        base, origem = _buscar_capa_base(appid, steam_path, grid_dir,
                                         args.force, args.sgdb_key, False)
        if base is None:
            print("   nenhuma encontrada")
            nitidez = 0.0
        else:
            img = Image.open(base)
            nitidez = analisar_nitidez(base)
            print(f"   {origem}  {img.size}  nitidez={nitidez:.2f}")
            print(f"   {'ABAIXO' if nitidez < args.limiar else 'acima'} "
                  f"do limiar {args.limiar}")

        print("\n2) consulta a SteamGridDB:")
        urls = url_capa_steamgriddb(appid, args.sgdb_key, verbose=True)

        if not urls:
            print("\n   Nenhuma arte utilizavel. Confira manualmente em:")
            print(f"   https://www.steamgriddb.com/steam/{appid}/grids")
            return

        print("\n3) avaliando candidatas:")
        dados, nova = buscar_capa_melhor(appid, args.sgdb_key, nitidez,
                                         verbose=True,
                                         exigir_ganho=args.exigir_ganho,
                                         variante=args.variante)
        if dados:
            print(f"\n   TROCARIA: {nitidez:.2f} -> {nova:.2f}")
            print(f"   Rode: {_comando()} --melhorar --only {appid}")
        else:
            print("\n   NÃO trocaria: nenhuma arte utilizavel voltou.")
            print(f"   Se você discorda, baixe a que quiser de")
            print(f"   https://www.steamgriddb.com/steam/{appid}/grids")
            print(f"   e salve como capas/{appid}.png")
        return

    if args.reset_backups:
        if BACKUP_DIR.exists():
            n = len(list(BACKUP_DIR.glob("*")))
            shutil.rmtree(BACKUP_DIR)
            print(f"originais/ apagada ({n} arquivos). As capas serão rebaixadas.")
        else:
            print("originais/ não existe, nada a fazer.")
        print("Rode o script normalmente agora.")
        return

    # config pode ligar a moldura sem precisar da flag toda vez
    if _cfg_inicial.get("moldura") and not args.sem_moldura:
        args.moldura = True

    if args.moldura and geometria_moldura() is None:
        sys.exit("--moldura precisa dos arquivos em molduras/.\n"
                 "Gere com:  python tools/build_frame.py")

    if args.melhorar and not args.sgdb_key:
        sys.exit("--melhorar precisa de uma chave: use SGDB_KEY ou --sgdb-key.")

    if args.sgdb_key:
        args.sgdb_key = args.sgdb_key.strip().strip('"').strip("'")
        ok, msg = validar_chave_sgdb(args.sgdb_key)
        if not ok:
            print(f"[!] Chave da SteamGridDB não funciona.\n  {msg}")
            if args.melhorar or args.testar_sgdb:
                sys.exit(1)
            print("[!] Seguindo sem a SteamGridDB.\n")
            args.sgdb_key = None
        elif args.verbose:
            print("Chave da SteamGridDB validada.\n")

    config = carregar_config(BASE_DIR / args.config)
    badges_dir = BASE_DIR / args.badges

    listas = listas_das_colecoes(steam_path, user_id, badges_dir, config)
    listas = aplicar_family(listas, args, steam_path, user_id, badges_dir, config)

    if not listas:
        sys.exit("Nenhuma lista utilizavel.\n"
                 "Mapeie suas Coleções em config.json -> \"coleções\" e\n"
                 f"coloque o ícone de cada uma em {badges_dir.name}/<nome>.png.")

    # overrides globais da linha de comando valem pra todas as listas
    for l in listas:
        if args.pos_set:
            l["pos"] = args.pos
        if args.scale is not None:
            l["scale"] = args.scale
        if args.margin is not None:
            l["margin"] = args.margin
        if args.opacity is not None:
            l["opacity"] = args.opacity

    print("Listas carregadas (em ordem de precedencia):")
    for i, l in enumerate(listas, 1):
        origem = ""
        if l.get("origens"):
            origem = "  <- " + ", ".join(l["origens"])
        cam = l.get("camada") or {}
        tipo = cam.get("tipo", "badge")
        # cada tipo ocupa um slot diferente da moldura: mostrar o slot real
        # evita a impressao de que tudo disputa o mesmo canto
        onde = {"caixa": "moldura inteira",
                "canto": f"canto {cam.get('canto', 'tl')}",
                "adesivo": f"adesivo {cam.get('pos', 'tr')}"}.get(
                    tipo, f"badge {l['pos']}")
        print(f"  {i}. {l['nome']:<12} {len(l['appids']):>4} jogos"
              f"  {onde:<16}{origem}")
    print()

    appids = sorted({a for l in listas for a in l["appids"]})

    if args.todos:
        # universo = tudo que aparece em qualquer colecao (inclusive as fora
        # do mapa) mais o que ja tem capa no grid. Sem badge, so a moldura.
        universo = set(appids)
        colecoes_todas, _ = ler_colecoes(steam_path, user_id)
        for c in colecoes_todas:
            if not c["dinamica"]:
                universo.update(c["appids"])
        for f in grid_dir.glob("*p.png"):
            if f.stem[:-1].isdigit():
                universo.add(int(f.stem[:-1]))
        for f in grid_dir.glob("*p.jpg"):
            if f.stem[:-1].isdigit():
                universo.add(int(f.stem[:-1]))
        extras = len(universo) - len(appids)
        appids = sorted(universo)
        print(f"Modo --todos: {len(appids)} jogos ({extras} sem badge, só moldura).\n")

    # O universo e definido aqui, antes de --so-auto ou --only estreitarem a
    # lista. A limpeza de orfaos precisa dele: sem isso, uma execucao
    # parcial trataria toda a biblioteca como orfa.
    universo_completo = set(appids)
    alvo = None
    if args.only:
        alvo = {int(x) for x in re.findall(r"\d+", args.only)}
        appids = [a for a in appids if a in alvo]
        print(f"Processando apenas: {appids}\n")

    if args.auditar:
        ja_aplicados = set(load_state().get("aplicados", []))
        print("Medindo qualidade das capas. Nada será alterado.\n")
        placar = []
        for i, appid in enumerate(appids, 1):
            base, origem = get_base_cover(appid, steam_path, grid_dir,
                                          args.force, args.sgdb_key,
                                          escrito_por_nos=(appid in ja_aplicados))
            if base is None:
                placar.append((0.0, appid, "SEM CAPA"))
                continue
            placar.append((analisar_nitidez(base), appid, origem))
            print(f"  {i}/{len(appids)}", end="\r", flush=True)

        placar.sort()
        print(f"{'nitidez':>8}  {'appid':>8}  fonte")
        print("-" * 58)
        for nit, appid, origem in placar:
            marca = "  <- FRACA" if nit < args.limiar else ""
            print(f"{nit:>8.2f}  {appid:>8}  {origem}{marca}")

        fracas = [a for n, a, o in placar if n < args.limiar and o != "SEM CAPA"]
        nenhuma = [a for n, a, o in placar if o == "SEM CAPA"]
        if nenhuma:
            print(f"\n{len(nenhuma)} sem capa alguma: {nenhuma}")
        print("-" * 58)
        print(f"{len(fracas)} de {len(placar)} abaixo do limiar {args.limiar}.")
        if fracas:
            print("\nCUIDADO: a metrica confunde 'header colado' com capa")
            print("minimalista legítima. Confira as capas antes de trocar:")
            for a in fracas[:15]:
                print(f"  https://www.steamgriddb.com/steam/{a}/grids")
            print(f"\nPra trocar só as que você aprovou:")
            print(f"  {_comando()} --melhorar --only {','.join(map(str, fracas[:5]))}")
        return

    # troca de arte automatica: precisa de chave, porque a alternativa vem
    # da SteamGridDB
    pediu_auto = args.trocar_auto or args.so_auto or args.forcar_auto
    trocar_auto = bool(pediu_auto) and bool(args.sgdb_key)
    if pediu_auto and not args.sgdb_key:
        sys.exit("--trocar-auto precisa de uma chave: use SGDB_KEY ou --sgdb-key.")

    if args.forcar_auto:
        _FORCADOS.update(int(x) for x in re.findall(r"\d+", args.forcar_auto))
        print(f"Tratando {len(_FORCADOS)} jogo(s) como capa fabricada por ordem sua.")

    if trocar_auto:
        print("Consultando a API da loja para achar capas fabricadas pela Steam...")
        carregar_assets(appids, verbose=args.verbose)
        auto = [a for a in appids if arte_automatica(a) is True]
        print(f"{len(auto)} de {len(appids)} jogos tem capa fabricada do header.\n")
        if args.so_auto:
            appids = sorted(set(auto) | (_FORCADOS & set(appids)))
            if not appids:
                print("Nenhum jogo para consertar.")
                return

    resumo = rodar.executar(
        rodar.Opcoes(dry_run=args.dry_run, out=args.out, moldura=args.moldura,
                     todos=args.todos, force=args.force, sgdb_key=args.sgdb_key,
                     melhorar=args.melhorar, limiar=args.limiar,
                     verbose=args.verbose, exigir_ganho=args.exigir_ganho,
                     variante=args.variante, so_auto=args.so_auto,
                     trocar_auto=trocar_auto,
                     forcar_auto=args.forcar_auto),
        appids, listas, steam_path, grid_dir, universo_completo, alvo,
        rel=RelatorioConsole(verboso=args.verbose),
        confirmar=_confirmar_terminal)
    return resumo




if __name__ == "__main__":
    try:
        main()
    except ErroCore as e:
        sys.exit(f"\n{e}")
    except KeyboardInterrupt:
        sys.exit("\nInterrompido.")
