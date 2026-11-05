"""
O estado que todas as etapas compartilham.

Hoje cada tela redescobre tudo por conta propria: acha o Steam, le o
config, le as colecoes. Sao tres leituras do mesmo disco e tres chances de
divergirem - mapear numa tela e simular na outra usava o mapeamento velho.

Aqui isso acontece uma vez. Quem altera o estado chama recarregar(), e
quem depende dele e avisado.

Sem tkinter de proposito: da pra testar a maquina de estados inteira sem
abrir janela.
"""
import core


class Sessao:
    def __init__(self, base_dir=None):
        self.base_dir = base_dir or core.BASE_DIR
        self.steam = None
        self.grid = None
        self.user = None
        self.config = {}
        self.listas = []
        self.sgdb_key = None
        self.ultima_simulacao = None
        self.erro_steam = None
        self.erro_listas = None
        self.avisos = []
        self._ouvintes = []

    # ---- quem quer saber quando algo muda -------------------------------

    def ao_mudar(self, fn):
        """Registra um interessado. Devolve uma funcao que cancela."""
        self._ouvintes.append(fn)
        return lambda: self._ouvintes.remove(fn) if fn in self._ouvintes else None

    def _avisar(self):
        for fn in list(self._ouvintes):
            try:
                fn(self)
            except Exception:
                pass          # um ouvinte quebrado nao derruba os outros

    # ---- leitura ---------------------------------------------------------

    @property
    def caminho_config(self):
        return self.base_dir / "config.json"

    @property
    def badges_dir(self):
        return self.base_dir / "badges"

    def carregar(self, avisar=True):
        """
        Descobre o Steam, le o config e as colecoes. Nunca levanta: guarda
        o problema em erro_steam / erro_listas, porque a casca precisa
        desenhar a lista de verificacao mesmo quando algo falta.
        """
        self.erro_steam = self.erro_listas = None
        self.avisos = []
        try:
            self.steam = core.find_steam_path()
            self.config = core.carregar_config(self.caminho_config)
            user = self.config.get("user")
            self.grid = core.find_grid_dir(self.steam, user)
            self.user = user or self.grid.parent.parent.name
        except core.ErroCore as e:
            self.erro_steam = str(e)
            self.steam = self.grid = self.user = None
        except Exception as e:
            self.erro_steam = f"{type(e).__name__}: {e}"
            self.steam = self.grid = self.user = None

        self.listas = []
        if self.steam is not None:
            try:
                self.listas = core.listas_das_colecoes(
                    self.steam, self.user, self.badges_dir, self.config)
            except core.ErroCore as e:
                self.erro_listas = str(e)
            except Exception as e:
                self.erro_listas = f"{type(e).__name__}: {e}"

        try:
            import galeria
            self.sgdb_key = galeria.ler_chave()
        except Exception:
            self.sgdb_key = None

        if avisar:
            self._avisar()
        return self

    def recarregar(self):
        """Depois de salvar o mapa ou adotar uma capa."""
        return self.carregar(avisar=True)

    # ---- o que as pre-condicoes perguntam --------------------------------

    @property
    def tem_steam(self):
        return self.steam is not None

    @property
    def tem_listas(self):
        return bool(self.listas)

    @property
    def moldura(self):
        return bool(self.config.get("moldura"))

    @property
    def moldura_pronta(self):
        if not self.moldura:
            return True
        try:
            return core.geometria_moldura() is not None
        except Exception:
            return False

    @property
    def tem_chave(self):
        return bool(self.sgdb_key)

    @property
    def simulou(self):
        return self.ultima_simulacao is not None

    def appids_com_badge(self):
        return {a for l in self.listas for a in l["appids"]}

    def appids_todos(self):
        """
        O universo do modo --todos: tudo que aparece em qualquer colecao,
        mais o que ja tem capa no grid.
        """
        universo = set(self.appids_com_badge())
        if self.steam is None:
            return sorted(universo)
        try:
            colecoes, _ = core.ler_colecoes(self.steam, self.user)
            for c in colecoes:
                if not c["dinamica"]:
                    universo.update(c["appids"])
        except Exception:
            pass
        if self.grid is not None:
            for padrao in ("*p.png", "*p.jpg"):
                try:
                    for f in self.grid.glob(padrao):
                        if f.stem[:-1].isdigit():
                            universo.add(int(f.stem[:-1]))
                except OSError:
                    pass
        return sorted(universo)

    def ja_aplicados(self):
        try:
            return set(core.load_state().get("aplicados", []))
        except Exception:
            return set()

    # ---- a lista de verificacao da primeira etapa ------------------------

    def conferir(self):
        """
        [(estado, texto, detalhe)] com estado True/False/None.
        None = merece atencao mas nao impede.
        """
        itens = []
        if self.tem_steam:
            itens.append((True, "Steam encontrado", str(self.steam)))
        else:
            itens.append((False, "Steam não encontrado",
                          (self.erro_steam or "").splitlines()[0]
                          if self.erro_steam else ""))
            return itens

        if self.tem_listas:
            itens.append((True, f"{len(self.listas)} status mapeados",
                          f"{len(self.appids_com_badge())} jogos com badge"))
        else:
            itens.append((False, "nenhuma coleção mapeada",
                          (self.erro_listas or "").splitlines()[0]
                          if self.erro_listas
                          else "faça isso na etapa Coleções"))

        if self.moldura:
            if self.moldura_pronta:
                itens.append((True, "moldura pronta", ""))
            else:
                itens.append((False, "moldura ligada mas molduras/ está vazia",
                              "gere na etapa Aparência"))
        else:
            itens.append((None, "moldura desligada",
                          "as capas recebem só o badge, sem a caixa"))

        itens.append((True, "chave da SteamGridDB configurada", "")
                     if self.tem_chave else
                     (None, "sem chave da SteamGridDB",
                      "a busca de artes fica desligada"))

        n = len(self.ja_aplicados())
        if n:
            itens.append((True, f"{n} capas aplicadas por nos antes",
                          "da pra desfazer"))
        return itens
