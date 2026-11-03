# Plano: unificar em um app só

Hoje são três janelas separadas (`tela.bat`, `capas.bat`, `rodar.bat`) mais
a CLI. Cada uma funciona, mas o usuário precisa saber **qual abrir e em que
ordem** — conhecimento que só existe no README.

O objetivo é uma aplicação única que conduz por etapas, explicando cada
opção no momento em que ela importa.

---

## 1. A forma: assistente com etapas, não abas

Abas deixam o usuário escolher a ordem. Aqui a ordem **importa**: mapear
antes de simular, simular antes de aplicar. Então: etapas numeradas numa
barra lateral, com avançar/voltar, e a etapa seguinte só libera quando a
anterior está satisfeita.

Mas sem prender: quem já mapeou e só quer rodar de novo deve poder pular
direto. A regra proposta é **etapa liberada quando sua pré-condição está
atendida**, não "quando você passou por ela nesta sessão".

### As etapas

| # | etapa | pré-condição | o que explica |
|---|-------|--------------|---------------|
| 1 | **Começar** | — | o que a ferramenta faz, onde achou o Steam, o que vai mexer, e que dá para desfazer |
| 2 | **Aparência** | Steam achado | moldura ligada ou badge solto; gera `molduras/` se faltar |
| 3 | **Coleções** | Steam achado | a tela de mapeamento atual |
| 4 | **Family Share** | coleções lidas | explica por que não dá para detectar, e ensina a criar a coleção |
| 5 | **Capas** | coleções mapeadas | a galeria atual, com a chave da SteamGridDB |
| 6 | **Simular** | coleções mapeadas | gera em `preview/`, abre a pasta |
| 7 | **Aplicar** | simulação feita | avisa do Steam aberto, aplica, oferece desfazer |

A etapa 4 é nova e justifica-se: o Family Share é a parte mais confusa do
produto e hoje está explicada só no README. Ela vira uma etapa que mostra o
estado atual (quantos vêm da coleção, quantos o `appmanifest` confirma) e
oferece o passo a passo de criar a coleção `FAMILY`.

A etapa 2 também é nova, e resolve um ponto cego: hoje `"moldura": true`
só se descobre lendo o `config.json`.

---

## 2. A arquitetura

### O que muda no código das telas

As três telas são hoje subclasses de `tk.Tk` — cada uma dona da própria
janela e do próprio `mainloop`. Para conviverem numa janela só, cada uma
vira um **`ttk.Frame`**, e a casca (`app.py`) é dona do root.

```
app.py              a casca: janela, barra de etapas, navegação, estado
  passos/
    inicio.py       etapa 1
    aparencia.py    etapa 2
    colecoes.py     etapa 3  <- vitrine_gui.py vira isto
    family.py       etapa 4
    capas.py        etapa 5  <- vitrine_galeria.py vira isto
    base_rodar.py   o que Simular e Aplicar compartilham
    simular.py      etapa 6
    aplicar.py      etapa 7

A divisão de Rodar em duas aconteceu no passo 4, não no 2: o passo 2 era
explicitamente "sem mudar nada do conteúdo".
```

A lógica (`mapa.py`, `galeria.py`, `rodar.py`, `core.py`) **não muda**.
Essa é a vantagem de ter separado regra de interface desde a fase 2: a
unificação mexe só na camada de cima.

### O estado compartilhado

Hoje cada tela redescobre tudo: acha o Steam, lê o config, lê as coleções.
São três leituras do mesmo disco e três chances de divergirem.

Proposta: um objeto `Sessao` criado uma vez pela casca e passado a cada
etapa.

```python
class Sessao:
    steam, grid, user          # descobertos uma vez
    config                     # o config.json carregado
    listas                     # coleções já resolvidas em status
    sgdb_key                   # chave validada
    ultima_simulacao           # resumo do rodar.executar mais recente
    def recarregar(self): ...  # quando o config muda, avisa as etapas
```

Uma etapa que altera o estado (salvar o mapeamento, adotar uma capa) chama
`sessao.recarregar()`, e as etapas seguintes se redesenham. Sem isso,
mapear e ir direto para simular usaria o mapeamento velho.

### O que fazer com a extração do estilo

As três telas repetem o mesmo bloco de `ttk.Style` — mesmas cores, mesmos
nomes de estilo. Vai para `tema.py`, aplicado uma vez pela casca.

### O que fazer com o `Relatorio`

Hoje `vitrine_rodar.py` tem a `RelatorioTela`. Ela sobe para a casca e
serve qualquer etapa que precise mostrar progresso, junto com o par
`fila`/`_bombear` que já está duplicado em duas telas.

---

## 3. Os `.bat`

Hoje são cinco (`vitrine`, `tela`, `capas`, `rodar`, `build_exe`).
Viram **dois**:

- `Vitrine.bat` — abre o app;
- `build_exe.bat` — gera o executável, agora do `app.py`.

O `vitrine.bat` atual, com o menu de texto, some: ele existia porque não
havia interface. A CLI (`vitrine.py`) **continua**, para quem quer
automatizar ou rodar sem janela — só deixa de ter um menu `.bat` na frente.

---

## 4. Ordem de execução proposta

| passo | entrega | risco | estado |
|-------|---------|-------|--------|
| 1 | `tema.py` + `Sessao` + casca `app.py` com uma etapa de teste | baixo | **FEITO** |
| 2 | converter as três telas em `ttk.Frame` **sem mudar nada do conteúdo** | médio — é onde mais se quebra | **FEITO** |
| 3 | provar que nada regrediu: capas byte a byte iguais | — | **FEITO** — 7 capas idênticas à CLI |
| 4 | etapas novas (Começar, Aparência, Family Share) + divisão de Rodar | baixo | **FEITO** |
| 5 | navegação, pré-condições, "pode pular" | baixo | **FEITO** |
| 6 | `.bat` e documentação | baixo | a seguir |

O passo 3 não é opcional. A conversão de `tk.Tk` para `ttk.Frame` mexe em
ciclo de vida de widget, variáveis Tk e `after()` — é exatamente o tipo de
mudança que parece funcionar e quebra em um caso específico.

---

## 5. Depois da unificação: a lista de otimização

Anotado agora para não se perder, **não** para fazer junto.

### Código

- `core.py` tem 2.180 linhas e faz muita coisa: descoberta do Steam,
  coleções, rede, composição, estado. Candidato a virar pacote
  (`core/steam.py`, `core/arte.py`, `core/rede.py`).
- `vitrine.py` (CLI) ainda tem 577 linhas, boa parte de `print`. Com as
  etapas na interface, vários modos de diagnóstico (`--testar-sgdb`,
  `--diag-auto`, `--comparar-family`) podem virar uma tela só de
  diagnóstico.
- `fila`/`_bombear`/`_em_thread` duplicados em duas telas.

### Operação

- A primeira execução baixa a biblioteca inteira com pausa de 0,3 s entre
  downloads. Com 2.800 jogos isso é ~15 min só de espera. Dá para paralelizar
  com um punhado de conexões respeitando o mesmo teto de requisições.
- `carregar_assets` já busca em lote de 100; a varredura da galeria ainda
  chama `arte_automatica` jogo a jogo.
- `preview/` acumula entre simulações, sem limpeza.

### Processo

- Não há `pytest` nem CI: as provas são três scripts com `main()` próprio.
  Funciona, mas um `pytest` daria descoberta automática e relatório melhor.
- Não há verificação automática do "byte a byte" — hoje é feito à mão a
  cada refatoramento. Virava um script.

### Interface

- A lista da galeria não tem filtro nem busca; com centenas de problemas,
  rolar é o único jeito.
- O log da tela de rodar não tem como salvar em arquivo.
- Nenhuma tela lembra tamanho ou posição da janela.
- Sem atalhos de teclado.

---

## 6. O que fica fora do escopo

- Trocar tkinter por outra coisa. Ele vem com o Python, empacota no
  PyInstaller sem drama e já está funcionando nas três telas.
- Tornar o app multiplataforma de verdade. O código é razoavelmente
  portátil, mas só foi exercitado no Windows.
- Qualquer tentativa nova de deduzir Family Share pelas listas web.
  Veja `DESENVOLVIMENTO.md`, seção 7 — foi medido, não funciona.
