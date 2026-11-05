"""Testes do estado compartilhado. Nenhuma janela e aberta."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import core
from sessao import Sessao


class FakeCore:
    """Substitui as funcoes do core que a Sessao chama."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def montar(tmp, nome, config=None, colecoes=None, erro=None, badges=("zerado",)):
    d = tmp / nome
    (d / "badges").mkdir(parents=True, exist_ok=True)
    for b in badges:
        (d / "badges" / f"{b}.png").write_bytes(b"x")
    if config is not None:
        (d / "config.json").write_text(json.dumps(config), encoding="utf-8")
    s = Sessao(base_dir=d)
    return s, d


def com_core(fn, **subs):
    """Roda fn com o core remendado, e devolve tudo ao normal depois."""
    orig = {k: getattr(core, k) for k in subs}
    for k, v in subs.items():
        setattr(core, k, v)
    try:
        return fn()
    finally:
        for k, v in orig.items():
            setattr(core, k, v)


# ---- carga --------------------------------------------------------------

def t_carrega_steam_config_e_listas(tmp):
    s, d = montar(tmp, "a", {"user": "99", "moldura": False})
    lista = [{"nome": "zerado", "appids": {1, 2, 3}, "ordem": 1}]
    com_core(lambda: s.carregar(),
             find_steam_path=lambda o=None: Path("/steam"),
             find_grid_dir=lambda p, u=None: Path("/steam/userdata/99/config/grid"),
             listas_das_colecoes=lambda *a: lista)
    assert s.tem_steam and s.user == "99"
    assert s.listas == lista and s.tem_listas
    assert s.appids_com_badge() == {1, 2, 3}
    return "carrega Steam, config e listas numa passada so"


def t_steam_ausente_nao_levanta(tmp):
    s, d = montar(tmp, "b", {})
    def explode(o=None):
        raise core.ErroCore("nao achei o Steam")
    com_core(lambda: s.carregar(), find_steam_path=explode)
    assert s.tem_steam is False
    assert "nao achei" in s.erro_steam
    assert s.listas == []
    return "Steam ausente vira erro guardado, nao excecao"


def t_erro_nas_listas_nao_derruba_o_resto(tmp):
    s, d = montar(tmp, "c", {"user": "9"})
    def explode(*a):
        raise core.ErroCore("colecoes ilegiveis")
    com_core(lambda: s.carregar(),
             find_steam_path=lambda o=None: Path("/s"),
             find_grid_dir=lambda p, u=None: Path("/s/userdata/9/config/grid"),
             listas_das_colecoes=explode)
    assert s.tem_steam is True, "o Steam foi achado mesmo assim"
    assert s.tem_listas is False and "ilegiveis" in s.erro_listas
    return "falha nas colecoes nao apaga o que ja foi descoberto"


def t_user_sai_do_grid_quando_o_config_nao_diz(tmp):
    s, d = montar(tmp, "d", {})
    com_core(lambda: s.carregar(),
             find_steam_path=lambda o=None: Path("/s"),
             find_grid_dir=lambda p, u=None: Path("/s/userdata/12345678/config/grid"),
             listas_das_colecoes=lambda *a: [])
    assert s.user == "12345678"
    return "sem 'user' no config, deduz da pasta do grid"


# ---- ouvintes -----------------------------------------------------------

def t_ouvintes_sao_avisados(tmp):
    s, d = montar(tmp, "e", {})
    vistos = []
    s.ao_mudar(lambda x: vistos.append(x))
    com_core(lambda: s.carregar(),
             find_steam_path=lambda o=None: Path("/s"),
             find_grid_dir=lambda p, u=None: Path("/s/userdata/9/config/grid"),
             listas_das_colecoes=lambda *a: [])
    assert vistos == [s]
    return "quem registrou interesse e avisado ao recarregar"


def t_ouvinte_quebrado_nao_derruba_os_outros(tmp):
    s, d = montar(tmp, "f", {})
    ok = []
    s.ao_mudar(lambda x: (_ for _ in ()).throw(RuntimeError("quebrei")))
    s.ao_mudar(lambda x: ok.append(1))
    s._avisar()
    assert ok == [1], "o segundo ouvinte rodou mesmo com o primeiro quebrado"
    return "ouvinte que explode nao impede os demais"


def t_cancelar_inscricao(tmp):
    s, d = montar(tmp, "g", {})
    n = []
    cancelar = s.ao_mudar(lambda x: n.append(1))
    s._avisar(); cancelar(); s._avisar()
    assert len(n) == 1
    return "da pra cancelar a inscricao de um ouvinte"


# ---- pre-condicoes ------------------------------------------------------

def t_moldura_desligada_conta_como_pronta(tmp):
    s, d = montar(tmp, "h", {"moldura": False})
    s.config = {"moldura": False}
    assert s.moldura is False and s.moldura_pronta is True
    return "moldura desligada nao bloqueia nada"


def t_moldura_ligada_sem_arquivos(tmp):
    s, d = montar(tmp, "i", {"moldura": True})
    s.config = {"moldura": True}
    r = com_core(lambda: s.moldura_pronta, geometria_moldura=lambda: None)
    assert r is False
    r = com_core(lambda: s.moldura_pronta, geometria_moldura=lambda: {"x": 1})
    assert r is True
    return "moldura ligada exige os arquivos em molduras/"


# ---- lista de verificacao -----------------------------------------------

def t_conferir_para_no_steam_ausente(tmp):
    s, d = montar(tmp, "j", {})
    s.steam = None; s.erro_steam = "nao achei o Steam\nsegunda linha"
    itens = s.conferir()
    assert len(itens) == 1 and itens[0][0] is False
    assert "segunda linha" not in itens[0][2], "so a primeira linha do erro"
    return "sem Steam, a conferencia para ali - o resto nao faz sentido"


def t_conferir_distingue_impeditivo_de_aviso(tmp):
    s, d = montar(tmp, "k", {})
    s.steam = Path("/s"); s.config = {"moldura": False}
    s.listas = [{"nome": "zerado", "appids": {1}}]
    s.sgdb_key = None
    itens = com_core(s.conferir, load_state=lambda: {"aplicados": []})
    estados = [i[0] for i in itens]
    assert False not in estados, "nada impeditivo aqui"
    assert None in estados, "a falta de chave e aviso, nao erro"
    return "conferencia separa o que impede do que so merece atencao"


def t_conferir_cobra_colecao_mapeada(tmp):
    s, d = montar(tmp, "l", {})
    s.steam = Path("/s"); s.config = {}; s.listas = []
    itens = com_core(s.conferir, load_state=lambda: {"aplicados": []})
    impeditivos = [i for i in itens if i[0] is False]
    assert any("coleção" in i[1] for i in impeditivos), itens
    return "sem colecao mapeada, a conferencia marca como impeditivo"


def t_appids_todos_junta_colecoes_e_grid(tmp):
    s, d = montar(tmp, "m", {})
    g = d / "grid"; g.mkdir()
    for n in (777, 888):
        (g / f"{n}p.png").write_bytes(b"x")
    (g / "lixo.png").write_bytes(b"x")
    s.steam = Path("/s"); s.grid = g
    s.listas = [{"nome": "zerado", "appids": {1}}]
    r = com_core(lambda: s.appids_todos(),
                 ler_colecoes=lambda *a: ([{"nome": "X", "appids": {2, 3},
                                            "dinamica": False},
                                           {"nome": "D", "appids": {9},
                                            "dinamica": True}], []))
    assert set(r) == {1, 2, 3, 777, 888}, r
    assert 9 not in r, "colecao dinamica nao entra"
    return "universo do --todos junta colecoes e grid, sem as dinamicas"


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
