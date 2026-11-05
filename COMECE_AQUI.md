# Começando do zero

Este guia leva da pasta vazia até a biblioteca emoldurada. Leva uns 20
minutos na primeira vez, e quase tudo é espera.

O `README.md` explica cada detalhe. Aqui está só o caminho.

---

## O que a Vitrine faz

Ela troca a capa de cada jogo da sua biblioteca Steam por uma versão
emoldurada como caixa física, com um selo dizendo em que pé está aquele
jogo: zerado, platinado, pausado, abandonado.

**De onde vem esse status?** Das **Coleções que você já usa no Steam**.
A Vitrine não inventa categoria nova nem pede que você mantenha lista
nenhuma à mão: ela lê o que já existe.

---

## 1. Antes de tudo: você precisa de coleções

Este é o passo que as pessoas pulam, e sem ele nada funciona.

Abra a biblioteca do Steam e crie uma coleção para cada status que você
quiser marcar — algo como "Zerados", "Platinados", "Pausados". Arraste os
jogos para dentro.

Duas regras:

- **Coleção manual, não dinâmica.** As dinâmicas (as que o Steam monta
  sozinho por filtro) não servem: o Steam não grava a lista de jogos
  delas em disco, e a Vitrine avisa quando encontra uma.
- **Não precisa de todas.** Comece com uma ou duas. Jogo que não está em
  coleção nenhuma recebe só a moldura, sem selo.

Se você já organiza a biblioteca por coleções, esse passo já está feito.

---

## 2. Instalar o Python

Baixe em [python.org](https://www.python.org/downloads/) e, no
instalador, marque **as duas caixas**:

- `Add Python to PATH`
- `tcl/tk and IDLE` — é o que desenha a janela

Depois, abra o Prompt de Comando na pasta do projeto e rode:

```
pip install pillow
```

É a única dependência.

---

## 3. Feche o Steam

Importante e fácil de esquecer: **o Steam reescreve as capas ao sair.**
Se ele estiver aberto, o resultado some e parece que nada funcionou.

Feche de verdade — clicar no X costuma mandar para a bandeja. Saia pelo
menu, ou pelo ícone ao lado do relógio.

---

## 4. Abrir

Dois cliques em **`Vitrine.bat`**.

A aplicação conduz por sete etapas, na ordem. Cada uma explica o que está
em jogo, então não precisa decorar nada:

| | etapa | o que fazer |
|-|-------|-------------|
| 1 | **Começar** | confira a lista: Steam achado, coleções lidas, moldura pronta |
| 2 | **Aparência** | escolha caixa de jogo ou selo solto, e gere as molduras |
| 3 | **Coleções** | ligue cada coleção ao status que ela representa |
| 4 | **Family Share** | só importa se você usa biblioteca compartilhada |
| 5 | **Capas** | opcional: conserte as capas feias |
| 6 | **Simular** | gera tudo numa pasta, sem tocar no Steam |
| 7 | **Aplicar** | escreve na biblioteca |

A etapa **Aplicar** fica trancada até você simular. É de propósito.

---

## 5. O primeiro teste, pequeno

Antes de aplicar nos seus 2.000 jogos, teste em três.

Na etapa **Simular**, clique em **Abrir preview** e olhe as capas
geradas. Os arquivos se chamam `<appid>p.png`. Escolha três appids e,
no Prompt de Comando dentro da pasta:

```
python vitrine.py --only 440,630,8930
```

Trocando pelos seus três. Abra o Steam e veja como ficaram. Não gostou?

```
python vitrine.py --restore
```

Volta tudo ao que era. As capas originais ficam guardadas em
`originais/` antes de qualquer troca.

---

## 6. Aplicar de verdade

Gostou dos três? Feche o Steam de novo, volte na etapa **Aplicar** e
clique no botão. Ele pede confirmação.

A primeira execução é a demorada: ela baixa a capa original de cada jogo
e guarda em `originais/`, com uma pausa de 0,3 s entre downloads para não
martelar o servidor da Valve. Com 2.000 jogos são uns 15 minutos. Deixe
rodando. Da segunda vez em diante é rápido, porque as originais já estão
no disco.

Terminou, abra o Steam. Se algo ficou errado, **Desfazer tudo** na mesma
etapa.

---

## Duas coisas opcionais

**Trocar os selos.** O projeto já vem com um conjunto em
`assets/badges/`. Para usar outros, salve os seus em `badges/` com os
mesmos nomes — `zerado.png`, `platinado.png`, `pausado.png`,
`abandonado.png`, `suficiente.png`, `online.png`, `family.png`. Essa
pasta sempre vence a padrão, arquivo por arquivo, então dá para trocar só
um.

**Consertar capas feias.** Alguns jogos não têm capa vertical própria, e
o Steam fabrica uma colando o banner horizontal no meio e borrando o
resto. A etapa **Capas** acha essas e oferece alternativas da
[SteamGridDB](https://www.steamgriddb.com/). Para isso você precisa de
uma chave gratuita, que se pega em Preferences → API no site e se cola na
própria tela.

---

## Se algo der errado

| sintoma | o que é |
|---------|---------|
| "nenhuma coleção mapeada" | volte na etapa 3, ou crie coleções no Steam (passo 1) |
| "badge faltando" | aquele status não tem PNG nem em `badges/` nem em `assets/badges/` |
| as capas não mudaram | o Steam estava aberto. Feche, rode de novo, abra |
| "dinâmica — sem lista de jogos" | aquela coleção é por filtro e não serve; crie uma manual |
| a janela não abre | falta o tkinter: reinstale o Python marcando `tcl/tk and IDLE` |

Nada do que a Vitrine faz é irreversível. As capas originais ficam em
`originais/`, e **Desfazer tudo** devolve todas.
