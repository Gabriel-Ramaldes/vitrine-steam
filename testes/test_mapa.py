"""Testes do modelo da tela de mapeamento. Nenhuma janela e aberta."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mapa import (Mapa, NADA, STATUS, ADESIVOS, MODIFICADOR,
                  TODOS, HIERARQUIA, DESCRICAO)


def cols(*nomes):
    saida = []
    for i, n in enumerate(nomes):
        din = n.startswith("*")
        saida.append({"id": f"uc-{i}", "nome": n.lstrip("*"), "slug": n.lower(),
                      "appids": set(range(10 + i)), "dinamica": din})
    return saida


def badges(tmp, *nomes):
    d = tmp / "badges"
    d.mkdir(parents=True, exist_ok=True)
    for n in nomes:
        (d / f"{n}.png").write_bytes(b"x")
    return d


def t_linhas_refletem_o_config(tmp):
    m = Mapa(cols("03-zerados", "10-Free", "*Dinamica"),
             {"colecoes": {"03-zerados": "zerado"}}, badges(tmp / "a", "zerado"))
    ls = {l["nome"]: l for l in m.linhas()}
    assert ls["03-zerados"]["status"] == "zerado"
    assert ls["03-zerados"]["family"] is False
    assert ls["03-zerados"]["adesivo"] is None
    assert ls["10-Free"]["status"] is None
    assert ls["Dinamica"]["dinamica"] is True
    assert ls["03-zerados"]["jogos"] == 10
    return "tabela reflete o config e marca as dinamicas"


def t_tres_encaixes_convivem(tmp):
    """family soma a tudo; status e adesivo sao um so cada."""
    m = Mapa(cols("X"), {"colecoes": {"X": ["zerado", "family", "free"]}},
             badges(tmp / "b", "zerado", "family"))
    l = m.linhas()[0]
    assert (l["status"], l["family"], l["adesivo"]) == ("zerado", True, "free")
    m.definir("X", status="pausado", family=True, adesivo="demo")
    assert m.para_config()["colecoes"]["X"] == ["pausado", "family", "demo"]
    m.definir("X", status="pausado")
    assert m.para_config()["colecoes"]["X"] == "pausado", "um so vira string"
    return "status, family e adesivo convivem e sao independentes"


def t_so_family_sem_status(tmp):
    m = Mapa(cols("X"), {}, badges(tmp / "b2", "family"))
    m.definir("X", family=True)
    assert m.para_config()["colecoes"]["X"] == "family"
    assert m.linhas()[0]["status"] is None
    return "family sozinho, sem status, e valido"


def t_nada_remove(tmp):
    m = Mapa(cols("X"), {"colecoes": {"X": "zerado"}}, badges(tmp / "c", "zerado"))
    m.definir("X")
    assert "X" not in m.para_config()["colecoes"]
    assert m.sujo is True
    return "deixar os tres vazios tira a colecao do mapa"


def t_preserva_o_resto_do_config(tmp):
    original = {
        "moldura": True, "user": "12345678",
        "colecoes": {"X": "zerado"},
        "hierarquia": ["platinado", "zerado"],
        "camadas": {"family": {"tipo": "canto", "cor": [46, 125, 50]}},
        "padrao": {"scale": 0.22},
        "_chave_que_eu_nao_conheco": {"a": [1, 2, 3]},
    }
    m = Mapa(cols("X", "Y"), original, badges(tmp / "d", "zerado"))
    m.definir("Y", status="pausado")
    saida = m.para_config()
    for k in ("moldura", "user", "camadas", "padrao", "_chave_que_eu_nao_conheco"):
        assert saida[k] == original[k], k
    assert saida["colecoes"] == {"X": "zerado", "Y": "pausado"}
    return "salvar nao destroi nada que a tela nao edita"


def t_vocabulario_e_fechado(tmp):
    """Nao da pra inventar status pela tela: valor estranho e recusado."""
    m = Mapa(cols("X"), {}, badges(tmp / "e"))
    m.definir("X", status="meu_status_inventado")
    assert "X" not in m.para_config()["colecoes"]
    m.definir("X", adesivo="zerado")      # zerado nao e adesivo
    assert "X" not in m.para_config()["colecoes"]
    m.definir("X", status="zerado", adesivo="free")
    assert m.para_config()["colecoes"]["X"] == ["zerado", "free"]
    return "status fora do vocabulario e recusado"


def t_hierarquia_e_fixa(tmp):
    """
    Ela deixou de ser editavel, e config antigo com outra ordem e
    ignorado - respeita-lo produziria resultado errado.
    """
    m = Mapa(cols(), {"hierarquia": ["demo", "online", "platinado"]},
             badges(tmp / "f"))
    assert m.hierarquia == list(HIERARQUIA), m.hierarquia
    assert not hasattr(m, "mover"), "a edicao da hierarquia saiu"
    return "hierarquia e sempre a canonica, ignorando o que o config diga"


def t_a_ordem_que_importa(tmp):
    """
    So a ordem DENTRO de um encaixe tem efeito. Dentro de STATUS ela
    descreve quanto do jogo foi consumido; dentro de ADESIVOS, free
    vence demo.
    """
    assert HIERARQUIA.index("platinado") < HIERARQUIA.index("zerado")
    assert HIERARQUIA.index("zerado") < HIERARQUIA.index("suficiente")
    assert HIERARQUIA.index("suficiente") < HIERARQUIA.index("abandonado")
    assert HIERARQUIA.index("abandonado") < HIERARQUIA.index("pausado")
    assert HIERARQUIA.index("pausado") < HIERARQUIA.index("online")
    assert HIERARQUIA.index("free") < HIERARQUIA.index("demo")
    assert set(HIERARQUIA) == set(TODOS) and len(HIERARQUIA) == len(TODOS)
    return "a ordem dentro de status e de adesivos e a que faz sentido"


def t_todo_status_tem_descricao(tmp):
    """A tela explica cada um; sem texto, a legenda fica vazia."""
    for n in TODOS:
        assert n in DESCRICAO and len(DESCRICAO[n]) > 10, n
    return "todo item do vocabulario tem uma descricao pra tela"



def t_avisa_badge_faltando(tmp):
    m = Mapa(cols("X"), {"colecoes": {"X": "zerado"}}, badges(tmp / "g"))
    assert any("zerado.png" in a for a in m.avisos()), m.avisos()
    return "avisa quando falta o PNG do status"


def t_nao_cobra_png_de_caixa_nem_adesivo(tmp):
    m = Mapa(cols("P", "F"),
             {"colecoes": {"P": "platinado", "F": "free"},
              "camadas": {"platinado": {"tipo": "caixa"},
                          "free": {"tipo": "adesivo"}}},
             badges(tmp / "h"))
    assert not any(".png" in a for a in m.avisos()), m.avisos()
    return "caixa e adesivo nao precisam de PNG em badges/"


def t_orfa_e_podada_ao_salvar(tmp):
    """Colecao que nao existe mais no Steam sai do config sozinha."""
    m = Mapa(cols("A", "B", "C"),
             {"colecoes": {"A": "zerado", "B": "pausado", "Sumida": "online"}},
             badges(tmp / "i", "zerado", "pausado", "online"))
    assert m.orfas() == ["Sumida"]
    assert m.podadas() == 1
    assert any("serão removidas" in a for a in m.avisos()), m.avisos()
    assert "Sumida" not in m.para_config()["colecoes"]
    assert set(m.para_config()["colecoes"]) == {"A", "B"}
    return "colecao que sumiu do Steam e removida ao salvar"


def t_trava_quando_nao_leu_colecao_nenhuma(tmp):
    """
    Steam aberto segurando o arquivo, ou caminho errado: a leitura vem
    vazia. Apagar o mapa inteiro aqui seria desastre.
    """
    m = Mapa([], {"colecoes": {"A": "zerado", "B": "pausado"}},
             badges(tmp / "j2", "zerado", "pausado"))
    pode, porque = m.pode_podar()
    assert pode is False and "nenhuma coleção" in porque, porque
    assert m.podadas() == 0
    assert m.para_config()["colecoes"] == {"A": "zerado", "B": "pausado"}
    return "leitura vazia nao apaga nada"


def t_trava_quando_leu_a_conta_errada(tmp):
    """
    Duas contas no mesmo PC: a secundaria tem poucas colecoes. Se mais da
    metade do mapa sumiu, e leitura errada, nao colecao apagada.
    """
    m = Mapa(cols("A"),
             {"colecoes": {"A": "zerado", "B": "pausado", "C": "online",
                           "D": "demo"}},
             badges(tmp / "k2", "zerado", "pausado", "online", "demo"))
    pode, porque = m.pode_podar()
    assert pode is False and "conta errada" in porque, porque
    assert m.podadas() == 0
    assert set(m.para_config()["colecoes"]) == {"A", "B", "C", "D"}
    assert any("conta errada" in a for a in m.avisos()), m.avisos()
    return "sumir mais da metade trava a poda (conta errada)"


def t_poda_no_limite_nao_dispara(tmp):
    """Exatamente metade ainda poda; mais da metade nao."""
    m = Mapa(cols("A", "B"),
             {"colecoes": {"A": "zerado", "B": "pausado", "X": "online",
                           "Y": "demo"}},
             badges(tmp / "l2", "zerado", "pausado", "online", "demo"))
    assert m.podadas() == 2, "2 de 4 e metade: pode"
    assert set(m.para_config()["colecoes"]) == {"A", "B"}
    return "metade sumida ainda poda; o limite e passar da metade"


def t_aposentado_sai_com_aviso(tmp):
    """boardgame e shovelware sairam: o config e limpo, com aviso antes."""
    m = Mapa(cols("BOARDGAMES", "09-SHOVELWARE", "03-zerados"),
             {"colecoes": {"BOARDGAMES": "boardgame",
                           "09-SHOVELWARE": "shovelware",
                           "03-zerados": "zerado"}},
             badges(tmp / "j", "zerado"))
    leg = m.legados()
    assert set(leg) == {"boardgame", "shovelware"}, leg
    assert leg["boardgame"] == ["BOARDGAMES"]
    avisos = " ".join(m.avisos())
    assert "boardgame" in avisos and "sem status" in avisos, avisos
    saida = m.para_config()["colecoes"]
    assert saida == {"03-zerados": "zerado"}, saida
    return "status aposentado some do config, com aviso antes"


def t_salvar_faz_backup_e_e_atomico(tmp):
    d = tmp / "k"; d.mkdir(parents=True, exist_ok=True)
    cfg = d / "config.json"
    cfg.write_text(json.dumps({"colecoes": {"X": "zerado"}, "moldura": True}),
                   encoding="utf-8")
    m = Mapa(cols("X", "Y"), json.loads(cfg.read_text()), badges(d, "zerado"))
    m.definir("Y", status="pausado")
    m.salvar(cfg)
    novo = json.loads(cfg.read_text(encoding="utf-8"))
    assert novo["colecoes"] == {"X": "zerado", "Y": "pausado"}
    assert novo["moldura"] is True
    velho = json.loads((d / "config.json.bak").read_text(encoding="utf-8"))
    assert velho["colecoes"] == {"X": "zerado"}, "o .bak tem que ser o ANTERIOR"
    assert not (d / "config.json.tmp").exists(), "o temporario tem que sumir"
    assert m.sujo is False
    return "salva com backup do anterior e sem deixar temporario"


def t_status_disponiveis_e_fixo(tmp):
    m = Mapa(cols("X"), {"colecoes": {"X": "boardgame"}},
             badges(tmp / "l", "qualquer_coisa"))
    d = m.status_disponiveis()
    assert d == TODOS, d
    assert "boardgame" not in d and "qualquer_coisa" not in d
    return "o vocabulario oferecido e fixo, nao cresce com a pasta"


def t_ordem_das_colecoes_segue_o_steam(tmp):
    m = Mapa(cols("B", "A", "C"), {"colecoes": {"C": "zerado", "A": "pausado"}},
             badges(tmp / "m", "zerado", "pausado"))
    assert list(m.para_config()["colecoes"]) == ["A", "C"]
    return "config sai na ordem em que o Steam lista as colecoes"


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
