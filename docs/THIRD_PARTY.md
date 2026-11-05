# Terceiros

A Vitrine é MIT, **sem fins lucrativos**. É um hobby feito para quem tem
o mesmo hobby: organizar a própria biblioteca e gostar de olhar para ela.
Não vende nada, não coleta nada e não tem relação com a Valve.

Esta página registra o que vem de fora, o que não vem, e o que
deliberadamente ficou de fora.

## Dependência de código

| O que | Licença | Para que |
|-------|---------|----------|
| [Pillow](https://python-pillow.org/) | MIT-CMU | toda a composição de imagem |
| [PyInstaller](https://pyinstaller.org/) | GPL-2.0 com exceção | gerar o `.exe`; a exceção permite distribuir o executável sob a licença que você quiser |
| [Bootstrap Icons](https://icons.getbootstrap.com/) | MIT | o conjunto padrão de badges (`assets/glifos/`, licença junto) |

Nada mais. Sem framework de HTTP, sem SDK da Steam: as chamadas de rede
usam `urllib` da biblioteca padrão.

## Arte: tudo gerado por código

As molduras, a fita de 100%, o canto de Family e os adesivos de FREE/DEMO
são desenhados em tempo de build por `tools/build_frame.py` e
`tools/build_stickers.py`, com primitivas do Pillow. Não há arquivo de
arte importado de outro projeto. Os PNG em `assets/molduras/` e
`assets/adesivos/` são saída desses scripts e podem ser regenerados a
qualquer momento.

O ícone de Family é um grupo de três figuras desenhado com elipses e
fatias de círculo — não é um ícone baixado.

## Onde fica cada coisa

A divisão é uma só: **`assets/` é o que o repositório carrega e o
programa lê.** Tudo que o programa *gera* ou que é seu fica fora, mesmo
quando tem uma pasta de mesmo nome dentro de `assets/`.

```
assets/badges/      conjunto padrão de status (Bootstrap Icons, MIT)
assets/molduras/    caixa, fita, scrim, canto de Family, geometria.json
assets/adesivos/    FREE e DEMO
assets/icone/       o ícone da janela e do executável
assets/glifos/      os SVG do Bootstrap e a licença deles
```

Ao lado do programa, uma pasta de **mesmo nome** guarda a sua versão e
vence: `badges/` vence `assets/badges/`, `molduras/` vence
`assets/molduras/`. A busca é arquivo a arquivo, então dá para trocar
uma peça só. Essas pastas estão no `.gitignore`:

- **`badges/*.png`** — os ícones de status que eu uso. São do
  [Magnific](https://www.flaticon.com/authors/magnific), no Flaticon. A
  licença gratuita deles **exige atribuição e não permite
  redistribuição**, então ficam só na minha máquina. Veja *Ícones*.
- **`molduras/`, `adesivos/`** — o que a etapa Aparência desenha na sua
  máquina, junto com `molduras/logo.png` (a logo da Steam, marca da
  Valve) e `molduras/icone_ribbon.png`.
- **`capas/`, `originais/`, `preview/`** — arte de capa dos jogos, que
  pertence às publicadoras. Uso pessoal, nunca commit.
- **`sgdb_key.txt`**, **`config.json`**, **`userdata.json`** — suas
  chaves e os seus dados.

## Ícones

Os ícones de status — zerado, platinado, pausado, abandonado, suficiente,
online, family — são do **[Magnific](https://www.flaticon.com/authors/magnific)**,
publicados no Flaticon.

A atribuição exigida pela licença gratuita:

> Icons created by Magnific - Flaticon

A mesma licença **não permite redistribuir os arquivos**, então eles não
estão neste repositório.

Por isso existe um **conjunto padrão** em `assets/badges/`, montado a
partir do [Bootstrap Icons](https://icons.getbootstrap.com/) — MIT,
redistribuição permitida — por `tools/build_badges.py`. É o que faz um
clone limpo funcionar de primeira.

O estilo é adesivo: aro escuro grosso, cor chapada, brilho no alto e o
glifo branco contornado. O aro é o que separa o badge da arte da capa,
que costuma ser cheia. As constantes ficam no topo do gerador — contorno,
espessura, tamanho do glifo, brilho — e mexer nelas muda o conjunto
inteiro de uma vez.

Quem quiser trocar põe os próprios em `badges/`, que sempre vence:

```
badges/           os seus (tem prioridade; fora do repositório)
assets/badges/    o conjunto MIT que vem junto
```

Os SVG originais ficam em `assets/glifos/`, junto com a licença do
Bootstrap Icons, e ao lado deles os PNG já rasterizados — assim o
gerador não precisa de nenhuma biblioteca de SVG.

## Ícone da aplicação

`assets/icone/vitrine.png` e `.ico`, e eles acompanham o repositório.

Para trocar por outro: `python tools/build_icone.py arte.png`. A imagem
sai quadrada, com o fundo das bordas removido por alagamento — o branco
de dentro do desenho fica — e nos sete tamanhos que o Windows pede. Se o
original não for quadrado, a diferença é dividida nos dois eixos, metade
para cada, porque esticar só um lado deforma círculo.

Os dois formatos existem porque fazem coisas diferentes: `.ico` guarda
vários tamanhos e é o único que a barra de tarefas do Windows aceita;
`.png` é o que o tkinter põe na janela. O `.ico` é montado à mão, e não
pelo Pillow, porque o Pillow grava todos os tamanhos como PNG — inclusive
o 16×16 — e a convenção do formato é o contrário: só o de 256 comprimido,
os menores como DIB. Um `.ico` todo em PNG abre num visualizador e parece
certo, mas parte do Windows não desenha o ícone.

`tools/build_icone.py` sem argumento desenha um ícone de reserva, do
zero, com o mesmo Bootstrap Icons dos badges. Não acompanha o
repositório e só serve para quem fizer um fork e quiser o próprio sem
desenhar nada.

## Agradecimentos

À **Valve**, pela arte que torna isto possível: a logo da Steam que
aparece no topo de cada caixa, e o próprio mecanismo de arte
personalizada na biblioteca, que é o que permite a ferramenta existir. A
logo é marca registrada deles e fica apenas na máquina de quem usa, nunca
no repositório.

Ao **Magnific**, pelos ícones que eu uso no dia a dia, e ao projeto
**Bootstrap Icons**, pelo conjunto padrão que vem no repositório.

Aos projetos da comunidade que vieram antes — `steam_case` e a coleção
"2.5D Steam Box Cover Project" na SteamGridDB — pela ideia de emoldurar a
capa como uma caixa física.

À **SteamGridDB** e a quem envia arte para lá, que é de onde saem as
capas dos jogos que a Steam deixou sem uma.

## Serviços consultados

| Serviço | Uso | Chave |
|---------|-----|-------|
| `api.steampowered.com` / `IStoreBrowseService` | descobrir a capa oficial e detectar capa fabricada do header | não |
| CDN de arte da Steam | baixar a capa oficial | não |
| [SteamGridDB](https://www.steamgriddb.com/) API v2 | arte alternativa quando a oficial é ruim ou não existe | sim, sua |
| `store.steampowered.com/dynamicstore/userdata/` | saber o que é seu, para refinar a detecção de Family Share | opcional; você salva a página logado, a Vitrine só lê o arquivo |

A Vitrine não faz login, não usa credenciais da sua conta Steam e não
envia nada sobre a sua biblioteca para fora. As Coleções são lidas de um
arquivo local, e o `userdata.json` da detecção de Family Share é um
arquivo que **você** salva do navegador: a ferramenta não toca nos seus
cookies nem abre sessão nenhuma.

## Inspiração, sem código reaproveitado

O conceito de emoldurar a capa como uma caixa física de jogo, e o método
de descobrir Family Share por subtração (biblioteca conhecida menos o que
é seu, com os pacotes expandidos), apareceram em outros projetos da
comunidade, entre eles
[steam_case](https://github.com/) e a coleção
["2.5D Steam Box Cover Project"](https://www.steamgriddb.com/collection/12973/grids)
na SteamGridDB. Técnica e ideia não são protegidas por direito autoral;
arquivos são. O `steam_case` é GPL-3, e por isso **nada dele** — nem
código, nem PSD, nem PNG — entrou aqui. A geometria, os biséis, a fita e
as cores foram reimplementados do zero a partir da observação de como uma
caixa de jogo real é construída. A detecção de Family Share aqui foi
escrita do zero a partir dos formatos públicos da Valve (key-value binária
e VDF texto), e vai além: além da subtração, lê o cache que o próprio
cliente mantém da biblioteca de cada membro da família, e cruza os dois
sinais. Tem seus próprios testes em `testes/test_family.py`.

## Marcas

Steam, Valve e Steam Family são marcas da Valve Corporation. A Vitrine é
uma ferramenta não oficial, sem nenhuma relação com a Valve.
