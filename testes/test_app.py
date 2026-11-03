"""
Testes da casca: navegacao, pre-condicoes e a ponte com as threads.

Precisa de um display. Sem um, pula com aviso em vez de falhar - no
Windows do usuario ele roda normalmente.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import tkinter as tk
except ImportError:
    print("tkinter ausente: pulando os testes da casca")
    sys.exit(0)

try:
    _r = tk.Tk(); _r.destroy()
except tk.TclError as e:
    print(f"sem display ({e}): pulando os testes da casca")
    sys.exit(0)

import core
import app as A


class Livre(A.Passo):
    titulo = "Livre"
    def montar(self):
        self.entrou = 0
        self.bloquear = False
    def ao_entrar(self):
        self.entrou += 1
    def ao_sair(self):
        return not self.bloquear


class Segunda(Livre):
    titulo = "Segunda"


class Trancada(A.Passo):
    titulo = "Trancada"
    @staticmethod
    def precisa(sessao):
        return sessao.tem_listas


def nova(*passos):
    """Uma App sem carga de disco: a Sessao e preenchida a mao."""
    a = A.App(passos=list(passos))
    a.after_cancel_all = None
    a.sessao.steam = Path("/steam")
    a.sessao.user = "9"
    a.sessao.config = {}
    a.sessao.listas = []
    a.ir(0, forcado=True)
    a.update()
    return a


def t_abre_na_primeira(_):
    a = nova(Livre, Segunda)
    try:
        assert a.atual == 0
        assert a._frame(0).entrou == 1, "ao_entrar chamado uma vez"
        assert str(a.bt_anterior.cget("state")) == "disabled"
        assert str(a.bt_proximo.cget("state")) == "normal"
    finally:
        a.destroy()
    return "abre na primeira etapa, com Voltar desabilitado"


def t_avanca_e_volta(_):
    a = nova(Livre, Segunda)
    try:
        a.proximo(); a.update()
        assert a.atual == 1 and a._frame(1).entrou == 1
        assert str(a.bt_proximo.cget("state")) == "disabled", "ultima etapa"
        a.anterior(); a.update()
        assert a.atual == 0
        assert a._frame(0).entrou == 2, "ao_entrar de novo ao voltar"
    finally:
        a.destroy()
    return "avanca e volta, chamando ao_entrar a cada visita"


def t_ao_sair_pode_bloquear(_):
    a = nova(Livre, Segunda)
    try:
        a._frame(0).bloquear = True
        a.proximo(); a.update()
        assert a.atual == 0, "a etapa recusou sair e a navegacao parou"
        a._frame(0).bloquear = False
        a.proximo(); a.update()
        assert a.atual == 1
    finally:
        a.destroy()
    return "ao_sair falso impede a navegacao (alteracoes nao salvas)"


def t_etapa_trancada_nao_abre(_):
    a = nova(Livre, Trancada)
    try:
        a.proximo(); a.update()
        assert a.atual == 0, "sem listas, a etapa seguinte esta trancada"
        assert "nao esta liberada" in a.lb_estado.cget("text")
        # a etapa anterior volta a aparecer
        assert a._frame(0).winfo_ismapped()
        a.sessao.listas = [{"nome": "zerado", "appids": {1}}]
        a.proximo(); a.update()
        assert a.atual == 1, "satisfeita a pre-condicao, abre"
    finally:
        a.destroy()
    return "pre-condicao tranca e destranca pelo ESTADO, nao pelo caminho"


def t_pre_condicao_olha_o_estado_nao_o_historico(_):
    """Quem ja mapeou antes nao precisa refazer o caminho nesta sessao."""
    a = A.App(passos=[Livre, Trancada])
    try:
        a.sessao.listas = [{"nome": "zerado", "appids": {1}}]
        a.ir(1)          # direto pra segunda, sem passar pela primeira
        a.update()
        assert a.atual == 1
    finally:
        a.destroy()
    return "da pra pular direto pra uma etapa ja satisfeita"


def t_barra_marca_atual_e_trancada(_):
    a = nova(Livre, Trancada)
    try:
        estilos = [w.cget("style") for w in a.barra.winfo_children()]
        assert estilos[0] == "EtapaAtual.TLabel", estilos
        assert estilos[1] == "EtapaTrancada.TLabel", estilos
        a.sessao.listas = [{"nome": "z", "appids": {1}}]
        a.desenhar_barra(); a.update()
        estilos = [w.cget("style") for w in a.barra.winfo_children()]
        assert estilos[1] == "Etapa.TLabel", estilos
    finally:
        a.destroy()
    return "a barra lateral mostra atual, liberada e trancada"


def t_ponte_com_thread(_):
    a = nova(Livre)
    try:
        visto = []
        a.em_thread(lambda: a.na_janela(lambda: visto.append("rodou")))
        for _ in range(60):
            a.update(); time.sleep(0.02)
            if visto:
                break
        assert visto == ["rodou"], "o recado da thread chegou na janela"
    finally:
        a.destroy()
    return "o que uma thread manda desenhar roda na thread da janela"


def t_erro_em_recado_nao_derruba_a_bomba(_):
    a = nova(Livre)
    try:
        a.na_janela(lambda: (_ for _ in ()).throw(RuntimeError("quebrei")))
        depois = []
        a.na_janela(lambda: depois.append(1))
        for _ in range(60):
            a.update(); time.sleep(0.02)
            if depois:
                break
        assert depois == [1], "a fila continuou viva apos o erro"
    finally:
        a.destroy()
    return "recado que explode nao mata a fila da janela"


def t_relatorio_vira_mensagem(_):
    recados = []
    rel = A.RelatorioTela(recados.append, verboso=False)
    rel.info("oi"); rel.aviso("cuidado"); rel.detalhe("escondido")
    rel.item(2, 10, 440, "zerado", "capas/", "")
    tipos = [r[0] for r in recados]
    assert tipos == ["linha", "linha", "item"], recados
    assert recados[1][2] == "aviso"
    assert recados[2][1][2] == 440
    rel.verboso = True
    rel.detalhe("agora aparece")
    assert recados[-1][2] == "fraco"
    return "o Relatorio da casca traduz o motor em recados pra tela"


def main():
    testes = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    falhas = 0
    for t in testes:
        try:
            print(f"  ok   {t(None)}")
        except Exception as e:
            falhas += 1
            print(f"  FALHA {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
