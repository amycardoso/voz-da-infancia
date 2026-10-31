# Voz da Infância

**Quem dubla quem no Brasil, e dá para prever a voz brasileira de um personagem?**

A rede da dublagem brasileira montada a partir de 420 mil papéis catalogados na [Dublapédia](https://dublagem.fandom.com): 13,7 mil obras, 6,2 mil dubladores, 110 mil atores originais. A coleta, a limpeza, quatro perguntas sobre a rede e um modelo que tenta prever o dublador estão em três notebooks:

1. [Exploração](notebooks/01_exploracao.ipynb): tamanho e cobertura da base, dubladores e atores mais frequentes, estúdios, lacunas.
2. [Quatro perguntas](notebooks/02_perguntas.ipynb): concentração, mapa da escalação, fidelidade de voz e gênero.
3. [O modelo](notebooks/03_modelo.ipynb): prever o dublador de um papel, com validação temporal e por franquia.

## Quatro achados

**1. A escalação se divide entre Rio e São Paulo.** No grafo de quem trabalha com quem (dubladores e diretores com duas ou mais obras em comum), as comunidades encontradas pelo algoritmo de Louvain seguem a cidade. As quatro maiores são duas paulistas e duas cariocas, e 97% das pessoas com cidade conhecida caem numa comunidade da sua cidade. Diretores têm elenco fixo: na mediana, 63% dos papéis de um diretor vão para dubladores com quem ele já fez 5 ou mais obras.

![Comunidades por cidade](reports/figs/02_comunidades_cidade.png)

**2. Poucos fazem quase tudo.** Os 10% de dubladores mais ativos fazem 83% dos papéis (Gini 0,87). A concentração caiu nas obras recentes: a fatia dos 50 mais ativos foi de 32% (anos 80) para 18% (anos 2020).

![Curva de Lorenz](reports/figs/01_lorenz.png)

**3. A "voz fixa" é exceção.** Entre atores de live-action com 3 ou mais obras, na mediana só 33% das obras têm o mesmo dublador, e só 2% passam de 80%. Os clássicos existem (Adam Sandler e Alexandre Moreno em 78% das obras, Tom Hanks e Marco Ribeiro em 71%), mas são poucos. Quando uma obra é redublada, o dublador muda em 92% dos personagens.

![Fidelidade de voz](reports/figs/03_fidelidade.png)

**4. Mais mulheres na dublagem, e o caso do anime.** Dubladoras fazem 34% dos papéis, e a fatia cresce em todas as mídias: no live-action, de 23% (obras dos anos 70) para 41% (anos 2020). No anime, seiyuus mulheres que fazem meninos no Japão ganham um dublador homem no Brasil em 13% dos papéis: a voz japonesa de Goku é Masako Nozawa; a brasileira, Wendel Bezerra.

![Dubladoras por década](reports/figs/04_genero_decada.png)

## O modelo: a voz da sua infância é menos previsível do que parece

Dado um papel (ator original, obra, ano, mídia, estúdio, diretor e gênero do ator), o modelo ordena os dubladores candidatos. O ranker é um gradient boosting sobre pares papel × candidato, comparado com três baselines. A avaliação é feita sem vazamento: **temporal** (treino com obras até 2017, teste de 2018 em diante) e **por franquia** (GroupKFold, para nenhuma continuação ficar de um lado e a original do outro).

| validação | modelo | top-1 | top-5 | top-20 |
|---|---|---:|---:|---:|
| temporal | popularidade | 0,5% | 1,7% | 5,6% |
| temporal | dublador mais frequente do ator | 4,3% | 8,8% | 13,8% |
| temporal | **ranker** | **4,5%** | **9,7%** | **19,8%** |
| franquia | dublador mais frequente do ator | 5,6% | 12,4% | 20,7% |
| franquia | **ranker** | **6,7%** | **14,3%** | **28,9%** |

Acertar o nome exato é difícil. O personagem não está nos dados, cerca de 16% dos papéis são vozes adicionais, e atores de voz como Dan Castellaneta ou Frank Welker fazem dezenas de personagens, cada um com uma voz brasileira diferente. O modelo ajuda onde o histórico do ator não diz nada. Para atores que nunca apareceram no treino, o dublador certo entra no top-20 em 13,3% dos papéis, contra 3,4% do baseline. Como **sugestão de elenco**, uma lista curta para um diretor conferir, é mais útil do que como adivinho. Detalhes em [reports/03_modelo.md](reports/03_modelo.md).

![Sugestão de elenco](reports/figs/08_sugestao_elenco.png)

## Como reproduzir

Coleta, parsers e limpeza só usam a biblioteca padrão do Python 3. Testes, notebooks e modelo usam a `.venv`.

```bash
make venv         # cria a .venv a partir de requirements.txt
make collect      # baixa (ou retoma) o wikitext pela API MediaWiki para data/raw/ (~45 min, ~150 MB)
make parse        # tabelas de elenco e filmografias -> data/processed/*.csv
make clean-data   # limpeza, ids de pessoa, gênero -> data/processed/elenco_limpo.csv
make model        # treina e avalia o modelo (~20 min)
make notebooks    # reexecuta os três notebooks
make test         # pytest
```

A coleta usa só a API (`api.php`), com User-Agent próprio, cerca de 1 requisição por segundo e `maxlag`. Ela pode ser interrompida e retomada.

## Estrutura

```
scripts/
  collect.py           coleta pela API MediaWiki (retomável)
  wikitable.py         lê tabelas {| … |} do wikitext, com rowspan/colspan
  parse_obras.py       elenco das obras -> obras_elenco.csv
  parse_dubladores.py  "Trabalhos em Dublagem" das fichas -> dubladores_trabalhos.csv
  parse_fichas.py      filmografias de atores, seiyuus e personagens -> fichas_filmografia.csv
  clean.py             células compostas, ids de pessoa, estúdio por versão, franquias
  gender.py            gênero pela ficha e pelo primeiro nome (Censo 2010)
  explore.py           agregados do notebook 01
  questions.py         as quatro perguntas do notebook 02
  model.py             baselines, ranker e avaliação do notebook 03
  stats.py             resumo da coleta
notebooks/             01_exploracao, 02_perguntas, 03_modelo (com os gráficos salvos)
reports/               01_limpeza, 02_perguntas, 03_modelo e as figuras em reports/figs/
tests/                 separador de células, nomes, gênero e testes de vazamento do modelo
```

Os dados (`data/`) não são versionados.

## Limitações

- **A Dublapédia é uma wiki**: a cobertura mede o que os editores catalogaram. Obras antigas e vozes adicionais estão sub-representadas, e "papel" depende de quanto cada página detalha o elenco.
- **Gênero do ator original**: só existe para quem tem ficha (27% dos papéis). Ele também serve de proxy do gênero do personagem, o que falha justamente no anime. O gênero do dublador cobre 99,6% dos papéis (98,4% pela ficha, 1,2% pelo primeiro nome).
- **Atores sem ficha**: 70% dos papéis. Eles ainda aparecem com grafias diferentes da mesma pessoa ("Wil" e "Will Wheaton").
- **Estúdio e diretor**: ficam ambíguos em 12% dos papéis, em obras com várias dublagens que não dizem qual estúdio fez qual versão.
- **Cidade**: vem só das categorias das fichas, e um quarto das pessoas da rede fica sem ela.
- **Modelo**: o ranker é treinado e avaliado em amostras (20 mil e 8 mil papéis no temporal). O dublador real só está na lista de candidatos em 38% dos papéis temporais.

Mais detalhes em [reports/01_limpeza.md](reports/01_limpeza.md), [reports/02_perguntas.md](reports/02_perguntas.md) e [reports/03_modelo.md](reports/03_modelo.md).

## Créditos e licenças

- **Fonte**: [Dublapédia](https://dublagem.fandom.com), dublagem.fandom.com, lida pela API MediaWiki. Conteúdo sob [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/); créditos aos editores da Dublapédia.
- **Gênero por nome**: [Gênero dos Nomes](https://brasil.io/dataset/genero-nomes/), do Brasil.io (libertado por Álvaro Justen a partir do Censo 2010 do IBGE), sob [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- **Código**: [MIT](LICENSE).
- **Dados derivados** (`data/processed/`): CC BY-SA 3.0, com atribuição à Dublapédia. Não são versionados; para obtê-los, rode o pipeline acima.
- **Inspiração**: os ensaios visuais de dados do [The Pudding](https://pudding.cool).
