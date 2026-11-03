# Vitrine

Transforma a biblioteca Steam numa estante de caixas de jogo: cada capa
ganha uma moldura de case física e um badge no canto dizendo em que pé
está aquele jogo — zerado, platinado, pausado, abandonado, só online.

O status vem das **Coleções do Steam** que você já mantém. Não há lista
para editar à mão: você organiza no cliente da Steam como sempre fez e
roda a ferramenta.

```
Coleção do Steam  ->  status  ->  camada na capa
07-platinado          platinado   case dourada + fita "100%"
03-zerados            zerado      badge no canto inferior direito
10-Free               free        adesivo roseta verde "FREE"

detectado sozinho  ->  family   ->  canto verde no alto à esquerda
```

## Por onde começar

Dois cliques em **`Vitrine.bat`**. A aplicação conduz por sete etapas, e
cada uma explica o que está em jogo no momento em que importa:

| | etapa | o que faz |
|-|-------|-----------|
| 1 | **Começar** | o que vai acontecer, onde achou o Steam, o que já está pronto |
| 2 | **Aparência** | caixa de jogo ou badge solto; gera as molduras |
| 3 | **Coleções** | liga cada coleção a um status |
| 4 | **Family Share** | por que não dá para detectar, e como resolver |
| 5 | **Capas** | troca as capas ruins |
| 6 | **Simular** | gera tudo em `preview/`, sem tocar no Steam |
| 7 | **Aplicar** | escreve na biblioteca; só libera depois de simular |

Feche o Steam antes de aplicar — ele reescreve as capas ao sair.

Uma etapa libera quando a condição dela está satisfeita, não quando você
passou por ela: quem já mapeou e só quer rodar de novo vai direto.

Quem prefere terminal tem a CLI completa em `vitrine.py`, com os mesmos
modos e mais os de diagnóstico.

## Como funciona

A Steam deixa você substituir a arte de cada jogo gravando um PNG em
`userdata/<id>/config/grid/<appid>p.png`. A Vitrine pega a capa original,
monta a composição e grava ali. A original vai para `originais/`, então dá
para desfazer tudo depois.

As Coleções ficam num JSON em
`userdata/<id>/config/cloudstorage/cloud-storage-namespace-*.json`. A
ferramenta lê esse arquivo direto do disco — nada de API, nada de login.

> **Feche o Steam antes de aplicar.** O cliente só grava as Coleções em
> disco ao sair ou sincronizar, e sobrescreve o grid ao fechar.

## Instalação

Precisa de Python 3.9+ e Pillow:

```
pip install pillow
```

No Windows, dois cliques em **`Vitrine.bat`** abrem a aplicação. Se
preferir um executável único, rode `build_exe.bat` uma vez: ele gera
`Vitrine.exe` e o Python deixa de ser necessário.

A janela precisa do tkinter, que vem com o Python do python.org quando
"tcl/tk and IDLE" está marcado na instalação. No Linux: `apt install
python3-tk`.

### Os badges

Ponha um PNG por status na pasta `badges/`, com fundo transparente e
quadrado (256×256 serve bem). Os nomes têm de bater com os status do
`config.json`:

```
badges/platinado.png    badges/abandonado.png
badges/zerado.png       badges/pausado.png
badges/suficiente.png   badges/online.png
badges/boardgame.png    badges/shovelware.png
```

**O repositório já vem com um conjunto pronto** em `badges_padrao/`,
montado a partir do [Bootstrap Icons](https://icons.getbootstrap.com/)
(MIT). Clonou, funciona.

Para usar outros, ponha os seus em `badges/` com os nomes acima: essa
pasta **sempre vence** a padrão, arquivo por arquivo. Dá para trocar só
um ícone e deixar os outros seis como estão.

Os que eu uso são do [Magnific](https://www.flaticon.com/authors/magnific),
no Flaticon, cuja licença exige atribuição e não permite redistribuir os
arquivos — por isso eles não estão aqui, e por isso o conjunto padrão
existe.

Para regerar a padrão depois de mexer nas cores ou no estilo:

```
python tools/build_badges.py
```

As constantes ficam no topo do gerador: a cor de cada status, a espessura
do aro escuro, quanto do disco o glifo ocupa e a intensidade do brilho.

### As molduras

As molduras são geradas por código, não são arte baixada:

```
python tools/build_frame.py      # molduras/case.png, case_ouro.png, ...
python tools/build_stickers.py   # adesivos/free.png, demo.png
```

Rode de novo sempre que mexer nas cores ou nas medidas dentro desses
scripts. `tools/build_stickers.py` lê os adesivos declarados no
`config.json`, então mudar a cor de `FREE` lá e rodar o script é o
caminho.

## A etapa Coleções

A etapa **Coleções** liga cada coleção a um status, sem editar JSON à
mão.

Ela lista todas as suas coleções com a contagem de jogos e os três
encaixes em colunas: o seletor de **status**, a caixa de **family** e o
seletor de **adesivo**. À direita fica a legenda, dizendo o que cada
status quer dizer e como a disputa é resolvida.
Embaixo ficam os avisos: badge faltando, coleção que você mapeou e
renomeou no Steam, coleção dinâmica que não serve de fonte.

Nada vai para o disco até você clicar em **Salvar**. Ao salvar, o
`config.json` anterior é preservado em `config.json.bak`, e a escrita é
atômica — se faltar energia no meio, o arquivo antigo continua inteiro em
vez de virar um pedaço de JSON.

A tela edita **só** `colecoes` e `hierarquia`. Tudo o mais que estiver no
`config.json` — `camadas`, cores, posições, `moldura`, ajustes seus,
inclusive chaves que esta versão não conhece — passa intacto.

Coleção que você apagou ou renomeou no Steam some do `config.json` ao
salvar — não fica mapeamento morto no arquivo. Com duas travas, porque
apagar o mapa inteiro por uma leitura ruim seria bem pior que conviver
com duas linhas mortas: se **nenhuma** coleção for lida (Steam aberto
segurando o arquivo, caminho errado), ou se **mais da metade** do que
está mapeado não aparecer — o sintoma de ter lido a conta errada, quando
há duas no mesmo computador — a tela não apaga nada e diz por quê.

A janela precisa do tkinter, que vem junto com o Python do python.org
(marque "tcl/tk and IDLE" na instalação). No Linux: `apt install
python3-tk`.

## A etapa Capas

A etapa **Capas** cuida das capas ruins.

**Varrer biblioteca** passa por todos os jogos e separa os problemáticos,
dizendo por que cada um entrou na lista:

| motivo | o que é |
|--------|---------|
| `sem capa` | não existe arte vertical em lugar nenhum |
| `fabricada pela Steam` | a Steam colou o banner horizontal no meio e borrou o resto |
| `sem pagina na loja` | saiu da loja e perdeu a página, então a API não responde |
| `capa fraca` | a nitidez ficou baixa — pode ser header colado, mas também pode ser arte minimalista legítima |

Clicando num jogo, a direita mostra **como a capa está hoje** ao lado do
nome — sem ver a atual junto das alternativas, escolher é chute — e
abaixo as opções da SteamGridDB com miniatura, dimensões, pontuação da
comunidade e autor. **Usar esta** (ou
duplo clique) baixa e grava em `capas/<appid>.png`, que é a fonte de maior
prioridade — dali em diante aquele jogo usa essa capa em toda execução, e
sai da lista.

**Usar arquivo meu...** faz o mesmo com uma imagem sua. Em ambos os casos
a imagem é validada antes de gravar: algo que não seja vertical na
proporção de capa é recusado na hora, em vez de dar erro lá na frente ao
montar a moldura.

**Abrir no site** leva à página do jogo na SteamGridDB, para os casos em
que você quer garimpar com calma.

A varredura roda fora da thread da janela e pode ser cancelada no meio com
**Parar** — são milhares de jogos. A busca de artes também, então a tela
não congela enquanto baixa miniaturas.

### A chave, sem sair da tela

O campo no topo guarda a chave da SteamGridDB. **Pegar a minha** abre a
página onde ela é gerada; cole no campo e clique em **Salvar chave**. Ela
vai para `sgdb_key.txt` — arquivo, e não linha de comando, para não ficar
no histórico do terminal — e é conferida contra a SteamGridDB na hora, em
vez de você descobrir que está morta só quando nenhuma arte aparecer.

O campo vem mascarado; a caixa **mostrar** revela quando precisar conferir.

Sem chave a galeria ainda funciona: varre, lista os problemas, mostra a
capa atual e aceita arquivos seus. Só a busca de artes fica desligada, e a
tela diz isso onde as alternativas apareceriam.

## As etapas Simular e Aplicar

As etapas **Simular** e **Aplicar** fecham o fluxo.

Antes de qualquer coisa a lista de verificação mostra o que precisa estar
pronto: Steam encontrado, coleções mapeadas, molduras geradas, quantas
capas já foram aplicadas antes — e **se o Steam está aberto**. Esse último
importa: o cliente reescreve o grid ao fechar, então aplicar com ele
rodando costuma dar a impressão de que nada funcionou. Se algo essencial
faltar, os botões ficam desabilitados e a lista diz o que resolver.

**Simular** gera tudo em `preview/` sem tocar no Steam, com barra de
progresso e o log ao vivo, jogo a jogo. **Abrir preview** abre a pasta no
explorador. A etapa **Aplicar** só libera depois de uma simulação — é o
que impede aplicar 2.800 capas e só então descobrir que o mapeamento
estava trocado. Ela pede confirmação e avisa de novo se o Steam estiver
aberto. **Parar** interrompe no próximo
jogo — são milhares, e desistir no meio tem que ser possível.

**Desfazer tudo** repõe as capas originais.

### Por que a tela e a CLI nunca divergem

As duas chamam o mesmo `rodar.executar()`. O laço que monta e grava as
capas foi extraído de `vitrine.py` para `rodar.py` justamente para não
existirem duas cópias — duas cópias divergiriam no primeiro conserto.

Nada em `rodar.py` imprime ou pergunta por conta própria: ele recebe um
`Relatorio` (a CLI escreve no terminal, a tela escreve no log colorido),
uma função `confirmar` para as perguntas de sim/não, e uma `parar`
consultada a cada jogo. É para isso que o `core` foi separado na fase 1.

## O mapa de coleções

A tela acima é a forma recomendada de montar isto. Se preferir editar o
arquivo, comece copiando o exemplo:

```
copy config.exemplo.json config.json      # Windows
cp   config.exemplo.json config.json      # Linux/macOS
```

Para ver os nomes exatos das suas coleções:

```
python vitrine.py --listar-colecoes
```

O mapa liga cada coleção aos encaixes que ela representa:

```json
{
  "moldura": true,
  "hierarquia": ["platinado", "family", "zerado", "suficiente",
                 "abandonado", "pausado", "online", "free", "demo"],
  "colecoes": {
    "07-platinado":          "platinado",
    "03-zerados":            "zerado",
    "04-Zerados (Family)":   ["zerado", "family"],
    "FAMILY":                "family",
    "10-Free":               "free"
  }
}
```

Uma coleção pode dar mais de um encaixe, desde que sejam **encaixes
diferentes**: `["zerado", "family"]` vale, e `["zerado", "online"]` não —
os dois são status, e um jogo tem só um. Nesse caso a hierarquia desempata
e o perdedor é descartado.

Coleção que não aparece no mapa é ignorada de propósito: os anos, os
gêneros, as listas de quem jogou junto.

Coleções **dinâmicas** (as que a Steam monta por filtro) não têm lista de
jogos gravada em disco, então não funcionam como fonte. Só as manuais.

## O vocabulário

É fechado de propósito. Cada status precisa de arte desenhada e de um
lugar definido na capa, então não dá para inventar um pela tela.

São **três encaixes independentes**, que convivem na mesma capa:

| encaixe | valores | onde aparece |
|---------|---------|--------------|
| **status** | um dos seis abaixo, ou nada | badge no canto inferior direito — menos `platinado`, que troca a moldura pela dourada e ganha a fita de 100% |
| **family** | sim ou não | canto verde no alto à esquerda |
| **adesivo** | `free`, `demo`, ou nada | selo roseta colado sobre a arte |

Os seis status, em ordem de precedência:

| status | quer dizer |
|--------|------------|
| `platinado` | terminei e peguei todas as conquistas |
| `zerado` | terminei o jogo |
| `suficiente` | não tem um fim, mas joguei o bastante — *done* |
| `abandonado` | não gostei ou enjoei; não sei se volto |
| `pausado` | joguei um pouco e parei; uma hora volto — *shelved* |
| `online` | não tem fim porque é um jogo online |

### A ordem é fixa, e isso é intencional

Ela já foi editável, e era engano: `family` nunca disputou com um status,
e `free` nunca disputou com `zerado` — são encaixes diferentes da capa.
O que havia de disputa real era só dentro dos status, e essa ordem
descreve quanto do jogo foi consumido, de "acabei tudo" a "não acaba
nunca". Entre os adesivos, `free` vence `demo`.

Um jogo em duas coleções de status fica com o que estiver mais acima.
`family` e adesivo não entram nessa conta.

### O que saiu

`boardgame` e `shovelware` foram removidos. Um `config.json` que ainda os
tenha é limpo ao salvar, com aviso antes.

## Family Share

O canto verde marca os jogos que estão na sua biblioteca por empréstimo.
Conseguir essa lista é mais difícil do que parece, e vale saber por quê.

### A lista não existe no seu computador

Procuramos. O `localconfig.vdf` guarda o seu `FamilyGroup` — id do grupo,
nome, membros — e **nenhum jogo**. O nó `shared-familygroup` da barra
lateral guarda só a ordem em que ele aparece. O cliente pede os appids ao
servidor e os mantém em memória.

As listas que a Steam serve na web também não resolvem, e isto foi
**medido, não suposto**: `store.steampowered.com/dynamicstore/userdata/` e
a página de jogos do perfil dizem o que você **pode jogar**, e com o Steam
Families o emprestado entra nas duas. Dos 30 jogos que o `appmanifest`
prova serem emprestados, 28 aparecem em `rgOwnedApps`, 28 em
`rgOwnedPackages` e 24 de 24 na página do perfil. Subtrair qualquer uma
delas apaga exatamente o alvo: 6% de acerto.

### O jeito certo: deixe o Steam montar a lista

O cliente sabe quais são. Então peça a ele:

1. abra a biblioteca e clique em **STEAM FAMILY** na barra lateral;
2. selecione tudo (clique no primeiro, `Shift` + clique no último, ou
   `Ctrl+A`);
3. clique com o botão direito → **Adicionar a** → nova coleção, chamada
   por exemplo `FAMILY`;
4. **feche o Steam** (ele só grava as coleções ao sair);
5. mapeie no `config.json`:

```json
"colecoes": { "FAMILY": "family" }
```

Pronto. A Vitrine passa a ler a lista completa do disco, como lê qualquer
outra coleção. Refaça quando a biblioteca da família mudar.

### Quando não há coleção

Sem uma coleção mapeada, a Vitrine deduz, e avisa que está deduzindo. Dois
sinais, nesta ordem de confiança:

- **o `appmanifest`** — um jogo emprestado **e instalado** carrega
  `SharedDepots` com o dono de cada depot. Exato, sem dedução. Só cobre
  os instalados.
- **o cache dos membros** — o cliente guarda em
  `WebStorage > FriendsOwnedGames_storage_<accountid>` a biblioteca de
  cada membro da família. Incompleto: medido em 23% de acerto.

```
python vitrine.py --comparar-family   # mede cada método contra o appmanifest
python vitrine.py --conferir-family   # mede o método atual
python vitrine.py --listar-family     # mostra o que ele achou
```

O `--comparar-family` é a ferramenta honesta aqui: ele usa os seus jogos
instalados como gabarito, porque é o único pedaço onde existe resposta
certa em disco, e mostra o acerto de cada variante lado a lado.

`--sem-family` desliga; `"family_auto": false` desliga de vez;
`"family_fonte": "deteccao"` ignora a coleção e força a dedução.

## Uso

Sempre simule antes:

```
python vitrine.py --dry-run
```

Isso escreve em `preview/` e não toca no Steam. Gostou, aplique:

```
python vitrine.py
```

Para uniformizar a biblioteca inteira — todos com moldura, badge só em
quem está numa coleção mapeada:

```
python vitrine.py --todos --dry-run
python vitrine.py --todos
```

## De onde vem a capa

Na ordem:

1. `capas/<appid>.png` — se você pôs uma à mão, ela ganha de todas
2. `originais/` — a capa que já salvamos antes
3. a arte custom que você já tinha no grid
4. o cache local do cliente Steam
5. a API da loja da Steam
6. SteamGridDB, se houver chave

### Capas que a Steam fabricou

Jogo sem arte vertical própria recebe da Steam uma capa montada do banner
horizontal: o header no meio e o resto borrado. A API da loja entrega
esses casos com nome de arquivo terminando em `portrait.png`, então a
detecção é exata, não um chute por nitidez.

```
python vitrine.py --todos --so-auto --dry-run   # ver quais são
python vitrine.py --todos --so-auto             # trocar pela SteamGridDB
```

Jogos que saíram da loja e perderam a página não aparecem na API. Para
esses, `--forcar-auto <appids>` trata como fabricada mesmo assim.

### SteamGridDB

Opcional, só para buscar arte melhor. Pegue a chave em
`steamgriddb.com` → Preferences → API e salve sozinha numa linha em
`sgdb_key.txt` (está no `.gitignore`), ou exporte `SGDB_KEY`. Evite
`--sgdb-key` na linha de comando: fica no histórico do terminal.

```
python vitrine.py --auditar                # mede e lista as capas fracas
python vitrine.py --melhorar --only 630    # troca as que você aprovou
python vitrine.py --testar-sgdb 630        # o que a SteamGridDB tem
```

O `--auditar` usa uma métrica de nitidez que **confunde capa fabricada
com capa minimalista legítima**. Trate a lista como sugestão: confira
antes de trocar. A troca escolhe por pontuação da comunidade, não por
nitidez; `--variante N` pula as N primeiras se a melhor não agradar, e
`--exigir-ganho` só troca se a nova for mais nítida.

## Desfazendo

```
python vitrine.py --restore
```

Repõe as originais de `originais/` e remove o que gravamos. A arte custom
que você já tinha antes da Vitrine fica guardada em `originais/custom/` e
é devolvida de lá — não se perde.

Para tirar do grid capas verticais que **não** são nossas (sobras de
outras ferramentas), e deixar a Steam voltar à arte oficial:

```
python vitrine.py --limpar-sobras --dry-run
python vitrine.py --limpar-sobras
```

## Estrutura

```
Vitrine.bat         abre a aplicacao
build_exe.bat       gera Vitrine.exe

app.py              a casca: janela, etapas, navegacao, threads
tema.py             cores e estilos, num lugar so
sessao.py           o estado que todas as etapas compartilham
passos/             uma etapa por arquivo, na ordem do fluxo

core.py             o motor: Steam, Colecoes, composicao, SteamGridDB
mapa.py             a regra da etapa Colecoes
galeria.py          a regra da etapa Capas
rodar.py            o laco que monta e grava, usado pela tela E pela CLI
vitrine.py          a CLI completa, com os modos de diagnostico

tools/              geradores das molduras e dos adesivos, e as sondas
testes/             as provas: nenhuma usa rede, quase nenhuma abre janela

config.exemplo.json ponto de partida para o config.json
badges/             seus PNG de status, se quiser trocar (fora do repo)
badges_padrao/      o conjunto MIT que vem junto, usado quando badges/ nao tem
molduras/           molduras geradas por codigo
adesivos/           adesivos gerados por codigo
capas/              suas capas manuais, por appid
originais/          backup das capas que substituimos
estado.json         o que gravamos, para saber o que desfazer

DESENVOLVIMENTO.md  as decisoes, as hipoteses que morreram e por que
PLANO.md            o desenho da unificacao
THIRD_PARTY.md      dependencias, o que nao vai no repo, e por que
```

A regra que se repete: **a lógica num módulo sem interface, a tela só
desenhando**. É o que permite as provas rodarem sem abrir janela, e foi o
que deixou a unificação mexer só na camada de cima.

`core.py` não imprime nada por conta própria e não encerra o processo:
reporta por um objeto `Relatorio` e levanta `ErroCore`. A CLI instala um
`Relatorio` que escreve no terminal; a aplicação instala um que escreve
no log colorido.

## Limitações

- Coleções dinâmicas não servem de fonte (não ficam em disco).
- A lista do Steam Family não existe em disco e nenhuma lista web da
  Steam separa seu de emprestado. Sem uma coleção montada a partir da aba
  STEAM FAMILY, a detecção é incompleta — e diz isso.
- O Steam sobrescreve o grid ao fechar: feche antes de aplicar.
- Jogos fora da loja, sem página, não têm arte para buscar.
- A métrica de nitidez do `--auditar` erra em capas minimalistas.
- `build_exe.bat` só roda no Windows: PyInstaller não faz cross-compile.

## Aviso e créditos

Ferramenta **sem fins lucrativos**, feita por hobby para quem tem o mesmo
hobby: organizar a própria biblioteca e gostar de olhar para ela. Não
vende nada, não coleta nada, e não tem nenhuma relação com a Valve.

**Obrigado à Valve** pela arte que torna isto possível — a logo da Steam
no topo de cada caixa — e pelo próprio mecanismo de arte personalizada na
biblioteca, que é o que permite a ferramenta existir. Steam e Steam
Family são marcas da Valve Corporation, e a logo fica apenas na sua
máquina, nunca no repositório.

**Obrigado ao [Magnific](https://www.flaticon.com/authors/magnific)**
pelos ícones de status:

> Icons created by Magnific - Flaticon

**Obrigado à [SteamGridDB](https://www.steamgriddb.com/)** e a quem envia
arte para lá, que é de onde saem as capas dos jogos que a Steam deixou
sem uma. E aos projetos da comunidade que vieram antes, pela ideia de
emoldurar a capa como uma caixa física.

A arte de capa pertence às publicadoras: ela fica na sua máquina, em
`capas/`, `originais/` e `preview/`, e nada disso vai para o repositório.

## Licença

MIT — veja `LICENSE`. Dependências e referências em `THIRD_PARTY.md`.

Em `tools/` há também as sondas usadas na investigação do Family Share
(`sonda_family.py` e companhia). Elas só leem, não alteram nada, e estão
ali para quem quiser reproduzir as medições descritas no
`DESENVOLVIMENTO.md`.

Se for mexer no código, leia antes o [`DESENVOLVIMENTO.md`](DESENVOLVIMENTO.md):
ele registra o que já foi tentado e falhou, e economiza repetir as mesmas
três hipóteses mortas sobre Family Share.
