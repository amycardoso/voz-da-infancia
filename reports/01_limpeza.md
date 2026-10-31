# 01 · Limpeza do elenco

Gerado por `make clean-data` (`scripts/clean.py`) a partir do cache da coleta de 31/10/2026.
Entrada: as tabelas de elenco das obras (`obras_elenco.csv`). Saída: `data/processed/elenco_limpo.csv`, uma linha por par personagem → dublador.

## Antes e depois

"Antes" é o `obras_elenco.csv` do parser já corrigido. Esse parser passou a ler todas as colunas de dublador de uma tabela (uma por dublagem ou estúdio), e isso recuperou 41,5 mil linhas de redublagens: a primeira versão tinha 375.497 linhas.

| | Antes | Depois |
|---|---:|---:|
| Linhas | 416.991 | 420.758 |
| Linhas com dublador desconhecido ("?", "N/A", "Por Confirmar"…) | 11,4% (texto solto) | 11,5% (`dublador_desconhecido=True`, linha mantida) |
| Dubladores únicos | 17.938 nomes escritos de formas diferentes | **6.774 ids** |
| Dubladores únicos ligados a uma ficha | 3.521 (nome idêntico ao título) | 3.661 |
| Linhas com dublador ligado a uma ficha | 91,3% | **98,2%** |
| Atores originais únicos | 115.945 nomes | 109.628 ids |
| Linhas com ator original ligado a uma ficha | 27,9% | 30,5% |
| Linhas com gênero do ator original | — | 19,9% (65,4% entre os que têm ficha) |
| Linhas com gênero do dublador | — | 0,9% |
| Células compostas | 3,2% das linhas, com " ; ", " / " ou parênteses | separadas; 5,2% das linhas têm `qualificador` |
| Ano | texto ("1994-2004 ; 1998-2004") | `ano` numérico (o primeiro ano) em 98,6% das linhas |
| Mídia | 8 valores, vazia em 7,5% | 14 valores; "outro" em 5,0% |
| Estúdio e diretor | concatenados quando há mais de uma dublagem | por versão; ver abaixo |
| Franquia | — | 10.074 grupos; 4.850 obras estão num grupo com mais de uma obra |

Estúdio por versão (`estudio_status`):

| status | linhas | o que quer dizer |
|---|---:|---|
| `unico` | 73,3% | o infobox tem um estúdio só |
| `casado` | 10,4% | vários estúdios; a versão foi ligada a um deles pelo nome do estúdio no título da seção ou da coluna, pelo ordinal (1ª/2ª dublagem, redublagem), pela temporada ("1ª-3ª Temporadas", "4ª em diante") ou pelo ano |
| `ambiguo` | 12,0% | vários estúdios e nada no wikitext que ligue a versão a um deles; `estudio` e `diretor` ficam concatenados com " ; " |
| `vazio` | 4,2% | o infobox não informa estúdio |

Entre as linhas de obras com mais de um estúdio, 46,4% foram ligadas à versão certa.

## Como cada coluna foi limpa

- **Células compostas**: o wikitext bruto da célula é cortado em `<br>`, `<hr>`, ";" e " / " fora de links, e em "[[A]] e [[B]]" / "[[A]], [[B]]". O texto entre parênteses, em `<small>` ou em `{{Pequena…}}` vira `qualificador` ("canções", "criança", "1ª voz", "eps. 1-18"). Um pedaço que é só qualificador vai para o nome anterior. Quando a célula do ator original também vem composta, os pedaços são pareados lado a lado se as contagens batem; senão, cada dublador fica com todos os atores. O qualificador do ator vem com o prefixo "original: ".
- **Nomes**: NFC; aspas tipográficas, espaços e `_` padronizados; marcação wiki residual removida. A chave de comparação ignora acentos, caixa e pontuação.
- **Id canônico** (`p:<ficha>` ou `n:<nome>`), nesta ordem:
  1. o alvo do link da célula (`[[Sandra Mara Azevedo|Sandra Mara]]` → a ficha, não o rótulo);
  2. os redirecionamentos para fichas, baixados pela API com `prop=redirects` (726, como "Aldo Perrota" → "Aldo Perrotta");
  3. um nome igual a uma ficha ou a um redirecionamento, comparando pela chave.

  O que sobra recebe `n:` + a chave do nome.
- **Gênero**: categorias Atores/Atrizes (Dubladores/Dubladoras, se existissem) ou o campo `sexo` do infobox. As fichas de dublador da Dublapédia não têm categoria por gênero e quase nunca preenchem `sexo`, por isso o gênero do dublador fica vazio em 99% das linhas.
- **Mídia**: pelas categorias, numa ordem de prioridade: game, novela, anime, filme animado, curta, filme, série animada, documentário, reality, série, websérie, especial, programa de TV, comercial; o que não se encaixa vira "outro".
- **Franquia**: união de obras ligadas por `antecessor`/`sucessor` no infobox, pela mesma categoria de franquia ("Franquia Star Wars", "Universo Cinematográfico Marvel") ou pela mesma raiz de título ("Toy Story 2" → "toy story"; corta em ":" e " - "). O rótulo é a categoria de franquia mais comum do grupo ou o título mais curto. Serve para separar treino e teste sem vazamento entre continuações.

## 3 casos difíceis

1. **Rótulo ≠ ficha.** Em *.hack//SIGN*, Morgana está como `[[Sandra Mara Azevedo|Sandra Mara]] <small>(eps. 1-18)</small>`. Pelo texto, "Sandra Mara" não casaria com nenhuma ficha. Pelo alvo do link, vira `p:Sandra Mara Azevedo` com o qualificador "eps. 1-18". Esse caminho, somado aos redirecionamentos, levou a ligação com fichas de 91,3% para 98,2% das linhas.
2. **Personagem e dublador compostos ao mesmo tempo.** Em *007 Contra a Chantagem Atômica*, o personagem é "Emilio Largo / No. 2" e a célula do dublador é `[[Alfredo Martins]]<br>[[Carlos Marques]]<br><small>(1 loop)</small>`. O dublador é separado em Alfredo Martins e Carlos Marques (qualificador "1 loop"), mas o personagem não. Não dá para saber, só pela célula, quem dubla qual papel, então as duas linhas ficam com o personagem composto.
3. **Estúdio por temporada sem temporada no elenco.** *31 Minutos* tem Álamo (1ª-2ª temps.) e UniDub (3ª-4ª temps.) no infobox, mas as tabelas são "Elenco" e "Personagens da Parada Top" e não dizem a temporada. Essas linhas ficam como `ambiguo`, com "Álamo ; UniDub".

## O que ainda não ficou bom

- **Estúdio ambíguo em 12% das linhas.** São obras com vários estúdios em que nenhuma seção ou coluna indica a versão. Daria para cruzar com as fichas de dublador, que trazem o ano de cada trabalho.
- **Gênero do dublador**: ~~praticamente vazio~~ resolvido depois em `scripts/gender.py`. A ficha resolve 98,0% das linhas e o primeiro nome (Censo 2010) mais 1,3%; o nome concorda com a ficha em 98,8% das fichas que têm os dois sinais.
- **Atores originais**: só 30% estão ligados a uma ficha. Os 109 mil ids `n:` ainda contêm variações de grafia e de romanização ("Alicia Witt" e "Alicia Wit", "Wil Wheaton" e "Will Wheaton", "Hiroomi Sugino" e "Hiromi Sugino") e não tratam homônimos. O gênero do ator original só existe para quem tem ficha.
- **Personagens**: não foram separados nem normalizados entre obras (caso 2).
- **Qualificadores**: misturam tipos diferentes (ordem de voz, episódios, canções, idade do personagem, "?" de incerteza) e ainda não foram classificados.
- **Franquias**: a raiz de título pode juntar obras homônimas sem relação. Para validação isso é conservador. O rótulo às vezes sai estranho: "Jason X" nomeia o grupo que junta Sexta-Feira 13 e A Hora do Pesadelo, ligados pelo crossover Freddy vs. Jason, e franquias sem ligação de infobox e com títulos diferentes ficam separadas.
- **Dublador desconhecido**: 11,5% das linhas. São mantidas e marcadas. Contam como desconhecidos "?", "N/A", "N/D" e os marcadores de vaga da wiki ("Por Confirmar", "Por identificar", "Por adicionar", "Sem Diálogos"…). "Dublador Desconhecido nº 9" e similares ficam como pessoas: são vozes recorrentes não identificadas, com ficha própria. Do lado do ator original, "Locução", "Narrador" e "Vários" não contam como pessoa.
