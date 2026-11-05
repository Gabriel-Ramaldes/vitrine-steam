"""
O modelo por tras da tela de mapeamento.

Separado da interface de proposito: aqui mora toda a regra - quais status
existem, o que cada colecao vira, qual a ordem da hierarquia, o que falta
pra funcionar - e nada de tkinter. Assim da pra testar sem abrir janela, e
a mesma logica serve se um dia a tela mudar de tecnologia.

A regra de ouro ao salvar: mexer SO em "colecoes" e "hierarquia". Todo o
resto do config.json e do usuario (camadas, cores, posicoes, ajustes) e
passa intacto, inclusive chaves que esta versao nao conhece.
"""
import json
from pathlib import Path

NADA = "(nada)"
IGNORAR = NADA          # nome antigo, mantido pra nao quebrar chamador velho

# O vocabulario e fechado de proposito. Nao da pra inventar status novo
# pela tela: cada um precisa de arte desenhada e de um lugar na capa, e
# "status solto que ninguém desenhou" so gera badge faltando.
#
# Tres encaixes independentes, que convivem numa mesma capa:

# 1. o status do jogo. Um so, ou nenhum. Esta e a unica dimensao em que
#    existe disputa - um jogo pode cair em duas colecoes de status, e ai
#    a ordem abaixo decide. E fixa: ela descreve o quanto do jogo foi
#    consumido, de "acabei tudo" a "não acaba nunca", e mexer nisso so
#    produziria resultado errado.
STATUS = ["platinado", "zerado", "suficiente", "abandonado", "pausado", "online"]

DESCRICAO = {
    "platinado": "terminei e peguei todas as conquistas",
    "zerado": "terminei o jogo",
    "suficiente": "não tem um fim, mas joguei o bastante - 'done'",
    "abandonado": "não gostei ou enjoei; não sei se volto",
    "pausado": "joguei um pouco e parei; uma hora volto - 'shelved'",
    "online": "não tem fim porque é um jogo online",
    "family": "está na sua biblioteca por empréstimo da família",
    "free": "o jogo é gratuito",
    "demo": "é uma demo ou playtest",
}

# 2. o modificador. Booleano: o jogo e ou nao e. Nao disputa com nada -
#    e um canto proprio, e soma a qualquer status ou a nenhum.
MODIFICADOR = "family"

# 3. o adesivo classificador, colado por cima da arte. Categoria a parte,
#    com a propria ordem: free vence demo, e nenhum dos dois tambem vale.
ADESIVOS = ["free", "demo"]

# A ordem de precedencia completa. Nao e editavel: encaixes diferentes nao
# disputam entre si, entao so a ordem DENTRO de STATUS e DENTRO de
# ADESIVOS tem efeito, e as duas sao fixas pelo significado.
HIERARQUIA = STATUS + [MODIFICADOR] + ADESIVOS

# o vocabulario inteiro, pra validar o que entra
TODOS = list(HIERARQUIA)

APOSENTADOS = ["boardgame", "shovelware"]


class Mapa:
    """
    Junta as Colecoes do Steam com o config.json e devolve a tabela que a
    tela desenha. Nenhuma alteracao toca o disco ate salvar().
    """

    def __init__(self, colecoes, config, badges_dir):
        self.colecoes = list(colecoes)
        self.config = json.loads(json.dumps(config)) if config else {}
        self.badges_dir = Path(badges_dir)
        mapa = self.config.get("colecoes") or {}
        # nome da colecao -> lista de status (o config aceita str ou lista)
        self.atual = {}
        for nome, destino in mapa.items():
            self.atual[nome] = [destino] if isinstance(destino, str) else list(destino)
        self.hierarquia = self._normaliza_hierarquia()
        self.sujo = False

    @staticmethod
    def _normaliza_hierarquia(_bruta=None):
        """
        A hierarquia e sempre a canonica.

        Era editavel e isso era engano: 'family' nunca disputou com um
        status, e 'free' nunca disputou com 'zerado' - sao encaixes
        diferentes da capa. O que sobrava de real era a ordem dentro dos
        status, e essa descreve o quanto do jogo foi consumido. Config
        antigo com outra ordem e ignorado em vez de respeitado.
        """
        return list(HIERARQUIA)

    # ---- leitura -------------------------------------------------------

    def status_disponiveis(self):
        """Compatibilidade: o vocabulario e fixo agora."""
        return list(TODOS)

    def tem_badge(self, status):
        for ext in (".png", ".webp", ".gif"):
            if (self.badges_dir / f"{status}{ext}").exists():
                return True
        return False

    def camada_de(self, status):
        cam = (self.config.get("camadas") or {}).get(status) or {}
        return cam.get("tipo", "badge")

    def _separa(self, nomes):
        """Uma lista de status do config vira os tres encaixes."""
        status = next((n for n in nomes if n in STATUS), None)
        adesivo = next((n for n in nomes if n in ADESIVOS), None)
        family = MODIFICADOR in nomes
        return status, family, adesivo

    def linhas(self):
        """Uma linha por Colecao, na ordem em que o Steam as devolve."""
        saida = []
        for c in self.colecoes:
            nome = c["nome"]
            status, family, adesivo = self._separa(self.atual.get(nome, []))
            saida.append({
                "nome": nome,
                "jogos": len(c.get("appids") or ()),
                "dinamica": bool(c.get("dinamica")),
                "status": status,
                "family": family,
                "adesivo": adesivo,
                "legado": [n for n in self.atual.get(nome, [])
                           if n not in TODOS],
            })
        return saida

    def legados(self):
        """
        Status que sairam da ferramenta mas ainda estao no config.
        Devolve {status: [colecoes]}, pra avisar antes de limpar.
        """
        fora = {}
        for nome, lista in self.atual.items():
            for n in lista:
                if n not in TODOS:
                    fora.setdefault(n, []).append(nome)
        return {k: sorted(v) for k, v in sorted(fora.items())}

    def orfas(self):
        """
        Colecoes que estao no config mas sumiram do Steam - renomeadas ou
        apagadas. O mapeamento delas e letra morta.
        """
        existentes = {c["nome"] for c in self.colecoes}
        return sorted(n for n in self.atual if n not in existentes)

    def pode_podar(self):
        """
        Se e seguro apagar as orfas ao salvar.

        A poda e desejavel: coleção que nao existe mais so suja o arquivo.
        Mas ela so e segura quando a leitura do Steam foi boa. Duas
        situacoes dizem que nao foi, e nas duas o certo e nao mexer:

          - nao veio colecao nenhuma (Steam aberto segurando o arquivo,
            caminho errado, conta sem colecoes);
          - sumiu mais da metade do que estava mapeado, o que acontece
            quando se le a conta errada - quem tem duas contas no mesmo
            computador tem uma delas com poucas colecoes.

        Perder o mapa inteiro por uma leitura ruim e bem pior do que
        conviver com duas linhas mortas no config.
        """
        if not self.colecoes:
            return False, ("nenhuma coleção foi lida: não vou apagar nada do "
                           "config até ler o Steam direito")
        orfas = self.orfas()
        if not orfas:
            return True, ""
        if len(orfas) > len(self.atual) / 2:
            return False, (f"{len(orfas)} de {len(self.atual)} coleções "
                           f"mapeadas não apareceram. Isso costuma ser leitura "
                           f"da conta errada, então não vou apagar nada. "
                           f"Confira \"user\" no config.json")
        return True, ""

    def avisos(self):
        fora = []
        usados = {s for lista in self.atual.values() for s in lista}
        for s in sorted(usados):
            if self.camada_de(s) in ("caixa", "adesivo"):
                continue          # esses nao usam PNG de badge
            if not self.tem_badge(s):
                fora.append(f"sem {self.badges_dir.name}/{s}.png - "
                            f"as coleções com status '{s}' ficam de fora")
        orfas = self.orfas()
        if orfas:
            pode, porque = self.pode_podar()
            lista = ", ".join(f'"{n}"' for n in orfas[:4])
            resto = f" e mais {len(orfas) - 4}" if len(orfas) > 4 else ""
            if pode:
                fora.append(f"{len(orfas)} coleção(oes) do config não existem "
                            f"mais no Steam ({lista}{resto}) - serão removidas "
                            f"ao salvar")
            else:
                fora.append(f"{len(orfas)} coleção(oes) do config não "
                            f"apareceram ({lista}{resto}). {porque}")
        for antigo, colecoes in self.legados().items():
            quais = ", ".join(f'"{n}"' for n in colecoes[:3])
            resto = f" e mais {len(colecoes) - 3}" if len(colecoes) > 3 else ""
            fora.append(f"'{antigo}' não existe mais na ferramenta - "
                        f"{quais}{resto} vai(vao) ficar sem status ao salvar")
        dinamicas = [c["nome"] for c in self.colecoes if c.get("dinamica")]
        if dinamicas:
            fora.append(f"{len(dinamicas)} coleção(oes) dinâmica(s) não podem "
                        f"ser usadas: o Steam não grava a lista de jogos delas")
        return fora

    # ---- escrita --------------------------------------------------------

    def definir(self, colecao, status=None, family=False, adesivo=None):
        """
        Os tres encaixes de uma colecao. Qualquer um pode ser vazio.
        Valor fora do vocabulario e recusado em silencio, em vez de
        entrar no config e virar badge faltando depois.
        """
        nomes = []
        if status in STATUS:
            nomes.append(status)
        if family:
            nomes.append(MODIFICADOR)
        if adesivo in ADESIVOS:
            nomes.append(adesivo)
        antes = self.atual.get(colecao, [])
        if nomes:
            self.atual[colecao] = nomes
        else:
            self.atual.pop(colecao, None)
        if antes != nomes:
            self.sujo = True

    def podadas(self):
        """Quantas orfas o proximo salvar vai remover. 0 se a trava pegou."""
        pode, _ = self.pode_podar()
        return len(self.orfas()) if pode else 0

    def para_config(self):
        """
        O config.json inteiro com o mapeamento novo. Tudo que nao for
        "colecoes" nem "hierarquia" sobrevive exatamente como estava.
        """
        saida = json.loads(json.dumps(self.config))
        novo = {}
        for c in self.colecoes:                      # ordem do Steam
            nome = c["nome"]
            if nome in self.atual:
                v = self.atual[nome]
                novo[nome] = v[0] if len(v) == 1 else list(v)
        for nome, v in self.atual.items():           # e as que sobraram
            if nome not in novo:
                novo[nome] = v[0] if len(v) == 1 else list(v)
        pode, _ = self.pode_podar()
        if pode:
            existentes = {c["nome"] for c in self.colecoes}
            novo = {k: v for k, v in novo.items() if k in existentes}
        # status aposentado sai do arquivo; colecao que so tinha ele some
        limpo = {}
        for k, v in novo.items():
            lista = [v] if isinstance(v, str) else list(v)
            lista = [n for n in lista if n in TODOS]
            if lista:
                limpo[k] = lista[0] if len(lista) == 1 else lista
        novo = limpo
        saida["colecoes"] = novo
        saida["hierarquia"] = list(self.hierarquia)
        return saida

    def salvar(self, caminho):
        """
        Grava, preservando o anterior em <nome>.bak. Escreve num temporario
        e so entao renomeia: se faltar energia no meio, o config antigo
        continua inteiro em vez de virar um arquivo pela metade.
        """
        caminho = Path(caminho)
        dados = json.dumps(self.para_config(), indent=2, ensure_ascii=False) + "\n"
        tmp = caminho.with_suffix(caminho.suffix + ".tmp")
        tmp.write_text(dados, encoding="utf-8")
        if caminho.exists():
            bak = caminho.with_suffix(caminho.suffix + ".bak")
            bak.write_bytes(caminho.read_bytes())
        tmp.replace(caminho)
        self.sujo = False
        return caminho
