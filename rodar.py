"""
O laco que monta e grava as capas.

Extraido de vitrine.py pra que a CLI e a tela rodem exatamente o mesmo
codigo - duas copias do mesmo laco iriam divergir no primeiro conserto.

Nada aqui imprime nem pergunta por conta propria:
  rel        objeto Relatorio do core, que decide onde a mensagem aparece;
  confirmar  pergunta de sim/nao (a CLI usa input, a tela usa um dialogo);
  parar      consultado a cada jogo, pra dar pra cancelar no meio.
"""
import shutil
import time
from pathlib import Path

from core import (BASE_DIR, BACKUP_DIR, MANUAL_DIR_NAME, Relatorio,
                  apply_badges, compor_com_moldura, geometria_moldura,
                  get_base_cover, load_state, resolver_badge,
                  resolver_camadas, save_state)


class Opcoes:
    """Tudo que o laco precisa decidir. Os nomes batem com os da CLI."""

    def __init__(self, **kw):
        self.dry_run = False
        self.out = "preview"
        self.moldura = False
        self.todos = False
        self.force = False
        self.sgdb_key = None
        self.melhorar = False
        self.limiar = 0.45
        self.verbose = False
        self.exigir_ganho = False
        self.variante = 0
        self.so_auto = False
        self.forcar_auto = None
        self.trocar_auto = False
        for k, v in kw.items():
            setattr(self, k, v)


def _sempre(_msg):
    return True


def _nunca():
    return False


def executar(op, appids, listas, steam_path, grid_dir, universo_completo,
             alvo=None, rel=None, confirmar=None, parar=None):
    rel = rel or Relatorio()
    confirmar = confirmar or _sempre
    parar = parar or _nunca
    # emoldurar amplia a arte: exige resolucao a altura da janela
    min_larg = 0
    if op.moldura:
        g = geometria_moldura()
        min_larg = g["janela"][2] - g["janela"][0]
        rel.info(f"Moldura ligada: exigindo capas de pelo menos {min_larg}px de largura.\n")

    destino_dir = (BASE_DIR / op.out) if op.dry_run else grid_dir
    if op.dry_run:
        destino_dir.mkdir(exist_ok=True)
        rel.info(f"MODO DRY-RUN: nada sera escrito no Steam. Saida em {destino_dir}\n")

    state = load_state()
    ja_aplicados = set(state.get("aplicados", []))   # escritos por nos antes
    aplicados = set(ja_aplicados)
    custom_previa = set(state.get("custom_previa", []))
    ok = falhou = 0
    feias, sem_capa, conflitos, trocadas = [], [], [], []

    for i, appid in enumerate(appids, 1):
        if parar():
            rel.aviso(f"interrompido em {i} de {len(appids)}")
            break
        prefixo = f"[{i}/{len(appids)}] {appid}"
        base, origem = get_base_cover(appid, steam_path, grid_dir,
                                      op.force, op.sgdb_key,
                                      escrito_por_nos=(appid in ja_aplicados),
                                      melhorar=op.melhorar, limiar=op.limiar,
                                      verbose=op.verbose,
                                      exigir_ganho=op.exigir_ganho,
                                      variante=op.variante,
                                      min_larg=min_larg,
                                      arte_crua=op.moldura,
                                      trocar_auto=op.trocar_auto)
        if base is None:
            rel.info(f"{prefixo}: SEM CAPA - nenhuma fonte funcionou")
            sem_capa.append(appid)
            falhou += 1
            continue

        if origem == "GERADA do header":
            feias.append(appid)
        if origem.startswith("SteamGridDB (trocou"):
            trocadas.append(appid)

        if (BACKUP_DIR / f"{appid}.era-custom").exists():
            custom_previa.add(appid)

        if op.moldura:
            camadas, usados, perdidos = resolver_camadas(appid, listas)
            if camadas is None:
                if not op.todos:
                    continue
                camadas = {"caixa": None, "cantos": [], "adesivos": [], "badge": None}
                usados, perdidos = [], []
            if perdidos:
                conflitos.append((appid, "+".join(usados) or "moldura", perdidos))
            try:
                final = compor_com_moldura(base, camadas)
            except Exception as e:
                rel.info(f"{prefixo}: erro ao compor - {e}")
                falhou += 1
                continue
            rotulo = "+".join(usados) or "(so moldura)"
        else:
            escolhida, perdedoras = resolver_badge(appid, listas)
            if escolhida is None:
                continue
            perdidos = [l["nome"] for l in perdedoras]
            if perdidos:
                conflitos.append((appid, escolhida["nome"], perdidos))
            try:
                final = apply_badges(base, [escolhida])
            except Exception as e:
                rel.info(f"{prefixo}: erro ao compor - {e}")
                falhou += 1
                continue
            rotulo = escolhida["nome"]

        saida = destino_dir / f"{appid}p.png"
        final.save(saida, "PNG")

        if not op.dry_run:
            # remove variantes .jpg do mesmo slot pro Steam nao pegar a errada
            for outro in grid_dir.glob(f"{appid}p.*"):
                if outro != saida:
                    outro.unlink(missing_ok=True)
            aplicados.add(appid)

        aviso = ("  <- tambem em: " + ", ".join(perdidos)) if perdidos else ""
        rel.item(i, len(appids), appid, rotulo, origem, aviso)
        ok += 1
        if origem in ("CDN", "API da loja", "SteamGridDB", "GERADA do header"):
            time.sleep(0.3)  # nao martelar o CDN da Valve

    # Jogos que estavam badgeados e sairam de TODAS as listas: a capa antiga
    # ficaria parada no grid pra sempre. Remove e devolve a arte limpa.
    em_alguma_lista = universo_completo if op.todos else {
        a for l in listas for a in l["appids"]}
    orfaos = ja_aplicados - em_alguma_lista
    if alvo is not None:
        orfaos &= alvo          # com --only, nao mexe no que voce nao pediu
    if op.so_auto or op.forcar_auto:
        orfaos = set()          # execucao parcial nunca limpa nada

    if orfaos and not op.dry_run and len(orfaos) > max(25, len(ja_aplicados) // 10):
        rel.info(f"\n[!] {len(orfaos)} capas seriam removidas de uma vez "
              f"({len(orfaos) * 100 // max(1, len(ja_aplicados))}% do que ja foi "
              f"aplicado).")
        rel.info("[!] Isso costuma indicar configuracao trocada, nao intencao.")
        resp = confirmar(f"{len(orfaos)} capas serao removidas de uma vez "
                         f"({len(orfaos) * 100 // max(1, len(ja_aplicados))}% do "
                         f"que ja foi aplicado). Isso costuma indicar "
                         f"configuracao trocada. Confirmar a remocao?")
        if not resp:
            rel.info("    Pulado. Nenhuma capa removida.")
            orfaos = set()

    if orfaos and not op.dry_run:
        rel.info()
        for appid in sorted(orfaos):
            for f in grid_dir.glob(f"{appid}p.*"):
                f.unlink(missing_ok=True)
            aplicados.discard(appid)
            if appid in custom_previa:
                for ext in (".png", ".jpg", ".jpeg"):
                    b = BACKUP_DIR / f"{appid}{ext}"
                    if b.exists():
                        shutil.copy2(b, grid_dir / f"{appid}p{ext}")
                        break
            rel.info(f"{appid}: saiu de todas as listas, badge removido")
    elif orfaos:
        rel.info(f"\n{len(orfaos)} jogo(s) sairam das listas e teriam o badge "
              f"removido: {sorted(orfaos)}")

    if not op.dry_run:
        save_state({"aplicados": sorted(aplicados),
                    "custom_previa": sorted(custom_previa)})

    rel.info(f"\n{ok} aplicados, {falhou} falharam.")

    if trocadas:
        rel.info(f"\n{len(trocadas)} capa(s) fabricadas pela Steam foram trocadas "
              f"por arte da SteamGridDB.")

    if conflitos:
        rel.info("\n" + "-" * 60)
        rel.info(f"{len(conflitos)} jogo(s) estao em mais de uma colecao mapeada.")
        # sobreposicao e normal e proposital (zerado+platinado, free+online...);
        # a hierarquia resolve e nao ha nada a corrigir no Steam
        rel.info("A hierarquia decidiu:")
        for appid, venceu, perdeu in conflitos[:20]:
            rel.info(f"  {appid}: usou '{venceu}', ignorou {', '.join(perdeu)}")
        if len(conflitos) > 20:
            rel.info(f"  ... e mais {len(conflitos) - 20}")
        rel.info("-" * 60)

    if feias or sem_capa:
        pasta_manual = BASE_DIR / MANUAL_DIR_NAME
        rel.info("\n" + "-" * 60)
        if feias:
            rel.info("Estes nao tem capa vertical oficial. A capa foi GERADA a partir")
            rel.info("da arte horizontal e provavelmente ficou feia:")
            for a in feias:
                rel.info(f"  {a}   https://store.steampowered.com/app/{a}/")
        if sem_capa:
            rel.info("Estes nao renderam imagem nenhuma:")
            for a in sem_capa:
                rel.info(f"  {a}   https://store.steampowered.com/app/{a}/")
        rel.info(f"\nPra resolver: baixe uma capa 600x900 (steamgriddb.com tem quase tudo),")
        rel.info(f"salve como <appid>.png em  {pasta_manual}")
        rel.info(f"e rode de novo. Ou use --sgdb-key pra buscar automatico.")
        rel.info("-" * 60)
    if op.dry_run:
        rel.info(f"Confira {destino_dir} e rode sem --dry-run quando gostar do resultado.")
    elif ok:
        rel.info("Feche e reabra o Steam pra ver as capas novas.")

    return {"ok": ok, "falhou": falhou, "feias": feias, "sem_capa": sem_capa,
            "conflitos": conflitos, "trocadas": trocadas,
            "destino": destino_dir, "aplicados": sorted(aplicados),
            "orfaos": sorted(orfaos)}
