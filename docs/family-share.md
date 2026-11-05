# Family Share: por que não dá para detectar sozinho

Três hipóteses foram medidas e descartadas. O resultado é um "não dá"
bem documentado — vale ler antes de tentar de novo.

Quem quiser refazer as medições: as sondas estão em `tools/`
(`sonda_family.py` e companhia). Elas só leem, não alteram nada.

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
