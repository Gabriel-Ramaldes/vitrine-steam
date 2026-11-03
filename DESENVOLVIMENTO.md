# Como esta ferramenta foi construída

Este documento não é um changelog. É o registro das decisões que custaram
caro, das hipóteses que morreram e do porquê o código tem a forma que tem.
Quem for mexer aqui depois — inclusive eu, daqui a seis meses — precisa
saber o que já foi tentado e falhou.

---

## O princípio que emergiu de tudo

> **Medir, não supor. Sinal exato vence heurística. Na dúvida, não marcar.**

Essas três frases não foram escolhidas no início. Elas são o resíduo de
errar três vezes seguidas do mesmo jeito.

---

## 1. De onde veio

A ideia original era pequena: pegar a capa de um jogo, colar um ícone de
"zerado" em cima, devolver para a biblioteca da Steam. Começou com
`steamgrid` do boppreh, que não funcionou com overlays por categoria, e
virou código próprio em Python.

A Steam permite substituir a arte de cada jogo gravando um PNG em
`userdata/<id>/config/grid/<appid>p.png`. Esse é o mecanismo inteiro. Todo
o resto é decidir **qual** PNG gravar.

## 2. As listas .txt morreram

A primeira versão lia appids de arquivos `.txt` mantidos à mão. Com uma
biblioteca de 2.800 jogos, manter as listas passou a custar mais do que o
problema que elas resolviam.

A descoberta que destravou: **as Coleções do Steam são JSON puro em
disco**, em `userdata/<id>/config/cloudstorage/cloud-storage-namespace-*.json`.
Um array de pares `[chave, registro]`, onde `registro["value"]` é um JSON
*em string*. Coleção apagada tem `value: null`; coleção dinâmica tem
`filterSpec` e nenhuma lista `added`.

Eu havia afirmado antes que isso vivia num LevelDB — estava desatualizado,
e a correção veio de olhar o arquivo em vez de confiar na memória. Foi o
primeiro aviso do princípio lá de cima.

As listas `.txt` saíram de vez na fase 1.

## 3. Uma badge por jogo, e os três encaixes

Um jogo pode cair em várias coleções mapeadas. A primeira solução foi uma
hierarquia simples: o primeiro que casar vence.

Isso evoluiu quando a moldura entrou. Hoje são **três encaixes
independentes** que convivem na mesma capa:

- **status** — um por jogo, no canto inferior (ou a moldura dourada, no
  caso do platinado);
- **family** — um canto, que soma a qualquer status;
- **adesivo** — `free` ou `demo`, colado sobre a arte.

A hierarquia só desempata dentro de um mesmo encaixe.

O vocabulário é **fechado**. `boardgame` e `shovelware` foram removidos
porque cada status precisa de arte desenhada e de um lugar definido na
capa; status solto que ninguém desenhou vira badge faltando.

## 4. A moldura: reimplementar em vez de adotar

O conceito de emoldurar a capa como uma caixa física de jogo veio do
projeto `steam_case` e da coleção "2.5D Steam Box Cover Project" na
SteamGridDB. O `steam_case` é **GPL-3**, e a decisão foi manter MIT e
reimplementar.

Técnica e ideia não são protegidas por direito autoral; arquivos são. Nada
do `steam_case` entrou — nem código, nem PSD, nem PNG. A geometria, os
biséis, a fita e as cores foram escritos do zero, e as molduras são
**geradas por código** (`tools/build_frame.py`), não arte importada.

Duas correções vieram de olho humano, não de teste:

- a ponta da fita de 100% estava espelhada para o lado errado — o `dobra`
  era aplicado na borda interna do lado direito. Consertado desenhando a
  ponta esquerda uma vez e espelhando;
- as junções dos blocos estavam duras demais. Os biséis eram tiras
  independentes de comprimento total que cortavam o header; viraram
  retângulos arredondados concêntricos, que se "meia-esquadriam" sozinhos.

## 5. Heurística falhou duas vezes; sinal exato resolveu

O problema: a Steam fabrica uma capa vertical para jogos que não têm uma,
colando o banner horizontal no meio e borrando o resto. São feias e
queríamos trocá-las.

**Tentativa 1 — medir nitidez.** Falhou. Capas emolduradas mediam 32–67 e
capas limpas 3,7–71: as faixas se sobrepõem. Pior, arte minimalista
legítima pontua baixo, então a métrica confunde "header colado" com
"design limpo".

**Tentativa 2 — heurística de pixels** para separar capa nossa de capa
alheia. Também falhou (o caso Just Cause 2, que tinha arte do steam_case
adotada pelo caminho de "arte custom existente" e ganhava moldura dupla).

**O que funcionou — sinais exatos:**

| sinal | o que prova |
|-------|-------------|
| nome do asset termina em `portrait.png` (API da loja) | a capa foi fabricada pela Steam |
| arquivo `.era-custom` no backup | a arte já era custom antes de nós |
| `escrito_por_nos` no `estado.json` | aquele PNG tem badge nosso queimado |
| `SharedDepots` no `appmanifest` | o jogo é emprestado |

A métrica de nitidez **continua no código**, mas só como sugestão no
`--auditar`, e o texto avisa que ela erra. Ela nunca decide sozinha.

## 6. O bug que teria apagado 1.510 capas

`--todos --so-auto` calculava os órfãos — jogos que saíram de todas as
listas e devem perder o badge — usando `em_alguma_lista = set(appids)`,
onde `appids` já tinha sido **estreitado** pelo `--so-auto`. Resultado: a
biblioteca inteira virava órfã.

Três correções, e as três continuam lá:

1. `universo_completo` capturado **antes** de qualquer estreitamento;
2. execução parcial (`--so-auto`, `--forcar-auto`) nunca limpa nada;
3. uma guarda que pede confirmação quando a remoção passa de 25 capas ou
   de 10% do que já foi aplicado, porque remoção em massa costuma indicar
   configuração trocada, não intenção.

---

## 7. Family Share: três hipóteses mortas e o que sobrou

Esta foi a investigação mais longa, e o resultado é um "não dá" bem
documentado. Vale ler antes de tentar de novo.

### O que não existe em disco

- `localconfig.vdf` guarda o `FamilyGroup` — id do grupo, nome, papel, e
  os membros — e **nenhum jogo**;
- o nó `STEAM FAMILY` da barra lateral existe como um *showcase* com
  `strCollectionId: "shared-familygroup"`, guardando ordem e estado de
  expansão. Diferente de `favorite` e `hidden`, que têm array `added`, ele
  **não tem lista de membros**;
- não há LevelDB nem IndexedDB do cliente com isso.

A conclusão: o cliente pede os appids ao servidor e os mantém em memória.

### As três fontes web, todas contaminadas

Medidas contra o mesmo gabarito — os 30 jogos que o `appmanifest` prova
serem emprestados:

| fonte | emprestados que ela lista como "seus" |
|-------|---------------------------------------|
| `rgOwnedApps` (dynamicstore) | 28 de 30 |
| `rgOwnedPackages` (dynamicstore) | 28 de 30 |
| página de jogos do perfil | 24 de 24 |

Nenhuma responde "o que é seu". Todas respondem **"o que você pode
jogar"**, e desde o Steam Families isso inclui o emprestado. Subtrair
qualquer uma delas apaga exatamente o alvo: **6% de acerto medido**.

Isso derruba a premissa em que o `steam_case` se apoia. Não é que o
projeto deles esteja errado — é que o Steam Families mudou o significado
do campo.

### O que sobrou

| sinal | recall medido | cobertura |
|-------|---------------|-----------|
| `SharedDepots` no `appmanifest` | exato | só instalados (30 de ~470) |
| cache `FriendsOwnedGames_storage_<id>` no `localconfig.vdf` | 23% | biblioteca dos membros, incompleta |
| subtração pela lista da loja | 6% | **prejudicial, saiu do padrão** |

O cache dos membros foi um achado real — o cliente guarda, por membro da
família, a lista de jogos de cada um, atualizada diariamente, indexada por
`FriendsOwnedGames_storage` → `m_rgStorageKeys`. Só que é incompleto.

### A saída

**Deixar o Steam materializar a lista.** O cliente sabe quais são os 470 e
sabe mostrá-los numa tela. Selecionar tudo na aba STEAM FAMILY e criar uma
coleção converte o conhecimento do servidor num arquivo local — exatamente
o formato que a ferramenta já lê.

Por isso a ordem de confiança hoje é: **coleção > appmanifest > dedução**.

### O erro de medição que quase passou

A primeira versão do `--conferir-family` reportou **30 de 30, 100%**. Era
circular: os `SharedDepots` eram injetados à força no resultado e depois
medidos contra si mesmos. A medida honesta roda a dedução com
`usar_exatos=False` e revelou os **6%** reais.

Há um teste que trava isso: ele monta um caso onde a resposta certa é 50%,
e quebra se alguém voltar a medir o resultado final.

---

## 8. As quatro fases

| fase | o que foi feito | por quê |
|------|-----------------|---------|
| 1 | `core.py` extraído do monolito; `Relatorio` e `ErroCore` | o motor não pode imprimir nem encerrar o processo se uma tela vai usá-lo |
| 2 | `mapa.py` + `vitrine_gui.py` | parar de editar `config.json` à mão |
| 3 | `galeria.py` + `vitrine_galeria.py` | capas ruins precisavam de olho humano e busca |
| 4 | `rodar.py` + `vitrine_rodar.py` | simular e aplicar com progresso |

O padrão se repete nas três telas: **a regra num módulo sem interface, a
tela só desenhando**. É o que permite 68 provas rodando sem abrir janela.

### A verificação que vale mais que teste

Toda vez que um refatoramento mexeu no caminho das capas, a prova foi
**byte a byte**: gerar as mesmas capas antes e depois e comparar com
`cmp`. Foi assim na extração do `core.py` (fase 1), na do `rodar.py`
(fase 4), e na comparação entre a tela e a CLI. Oito capas idênticas não
deixam dúvida.

Dois bugs foram pegos exatamente por isso — um `NameError` escondido
porque eu tinha mandado a saída para `/dev/null`, e uma função
`aplicar_family` duplicada porque usei uma âncora de corte que estava
*antes* do trecho, não depois.

---

## 9. O que ficou de fora, de propósito

- **Ler o token de autenticação do cliente** para chamar
  `IFamilyGroupsService`. Resolveria o Family Share de vez, e não foi
  feito: extrair credencial da máquina do usuário é outra categoria de
  coisa.
- **Distribuir os ícones de badge** no repositório. Vieram de fora, com
  licença desconhecida.
- **A logo da Steam** (`molduras/logo.png`) — marca registrada da Valve,
  fica só na máquina.
- **Arte de capa** em `capas/`, `originais/` e `preview/` — pertence às
  publicadoras. Uso pessoal, nunca commit.
