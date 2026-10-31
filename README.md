# Voz da Infância

A rede da dublagem brasileira: quem dubla quem, em quais obras, e um modelo que prevê o dublador de um personagem.

## Fonte

Os dados vêm da [Dublapédia](https://dublagem.fandom.com) (dublagem.fandom.com), lida só pela API MediaWiki (`api.php`): nada de páginas HTML, User-Agent `VozDaInfancia/0.1`, até ~1 requisição por segundo e `maxlag=5`. O conteúdo da Dublapédia é licenciado sob [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/); créditos aos editores da Dublapédia. Qualquer dado derivado publicado a partir daqui mantém a atribuição e a mesma licença.

## Como rodar

A coleta, os parsers e a limpeza só usam a biblioteca padrão do Python 3. Os testes e os notebooks usam a `.venv` (`make venv`, a partir de `requirements.txt`).

```bash
make collect      # baixa (ou retoma) o wikitext e os redirecionamentos para data/raw/
make parse        # gera os CSVs em data/processed/
make clean-data   # gera data/processed/elenco_limpo.csv
make stats        # resume a coleta e os CSVs
make test         # pytest
make notebooks    # reexecuta os notebooks (salvos com os gráficos)
```

`make` sozinho roda `collect`, `parse` e `clean-data`. A coleta pode ser interrompida e rodada de novo: as listas já salvas e os títulos já baixados são pulados.

## Scripts

- `collect.py [data/raw]`: lista os títulos de cada categoria e infobox (`data/raw/lists/`), baixa a revisão atual (wikitext + categorias) em lotes de 50 (`data/raw/pages/part-NNNN.jsonl`) e salva os redirecionamentos que apontam para cada ficha de pessoa (`data/raw/redirects.json`). Cada página leva os tipos de que faz parte em `kinds`.
  - obras: categorias Filmes, Desenhos animados, Séries, Anime, Jogos Eletrônicos, Novelas e Redublagem, mais as páginas com `Infobox de produção` (com ou sem etapas);
  - dubladores: `Infobox de dublador` e a categoria Dubladores;
  - atores originais: `Infobox de ator` e as categorias Atores e Atrizes;
  - estúdios: `Infobox de estúdio`; diretores: categoria Diretores de Dublagem.
- `wikitable.py`: lê tabelas MediaWiki (`{| … |}`) direto do wikitext, com rowspan e colspan.
- `parse_obras.py <raw> <saida.csv>`: tabelas de elenco das obras → `obra|versao|ano|midia|estudio|diretor|personagem|ator_original|dublador`. `versao` é o título da seção (Elenco, uma redublagem, uma temporada…), mais o rótulo da coluna quando a tabela tem uma coluna de dublador por dublagem ("Elenco — Herbert Richers"). As páginas que falham vão para `obras_falhas.csv` com o motivo.
- `parse_dubladores.py <raw> <saida.csv>`: seção "Trabalhos em Dublagem" das fichas de dublador → `dublador|ator_original|midia|obra|ano|personagem`. Falhas em `dubladores_falhas.csv`.
- `parse_fichas.py <raw> <saida.csv>`: tabelas de filmografia das fichas de ator original, seiyuu e personagem → `pagina|tipo|obra|ano|personagem|ator_original|dublador|estudio`. É uma terceira visão da mesma rede, já organizada como ator original → dublador.
- `clean.py [raw] [processed]`: limpa o elenco das obras → `elenco_limpo.csv`. Separa células compostas (coluna `qualificador`), marca `dublador_desconhecido`, dá um id canônico por pessoa (`p:<ficha>` ou `n:<nome>`), liga estúdio e diretor à versão (`estudio_status`) e cria `ano` numérico, `midia` padronizada, `franquia` e o gênero do ator original e do dublador. Detalhes e números em [reports/01_limpeza.md](reports/01_limpeza.md).
- `stats.py`: as estatísticas abaixo.
- `explore.py`: agregados e estilo dos gráficos de [notebooks/01_exploracao.ipynb](notebooks/01_exploracao.ipynb), a exploração da base limpa (mídia e década, dubladores e atores mais frequentes, cauda longa, estúdios e diretores, gênero e lacunas).

## Estatísticas da coleta

Coleta completa em 31/10/2026, cerca de 45 minutos e nenhum erro da API.

| | |
|---|---|
| Páginas baixadas | 24.732: 14.300 obras, 5.283 atores originais, 4.895 fichas de dublador, 655 diretores e 324 estúdios (uma página pode ter mais de um tipo) |
| Tamanho | 136 MB de wikitext; `data/raw/` ocupa 153 MB e `data/processed/` 92 MB |
| `obras_elenco.csv` | 416.991 linhas (375.497 antes de ler todas as colunas de dublador); 13.670 obras |
| `elenco_limpo.csv` | 420.758 linhas; 6.774 dubladores (98,2% das linhas ligadas a uma ficha); 109.628 atores originais |
| `dubladores_trabalhos.csv` | 220.207 linhas; 3.787 dubladores; 47 mil atores originais; 36 mil obras |
| `fichas_filmografia.csv` | 134.740 linhas; 5.997 fichas; 11.130 dubladores; 6.730 atores originais |

Taxa de parse:

- Obras: 13.670 de 14.300 páginas têm elenco (95,6%).
- Fichas de dublador: 3.787 de 4.895 têm "Trabalhos em Dublagem" (77,4%). Das 1.108 que ficam de fora, 885 são de personagens ou seiyuus, que o `parse_fichas.py` aproveita.

Falhas mais comuns (obras):

| Páginas | Motivo |
|---|---|
| 350 | Produção nacional: a tabela só tem vozes originais, não é dublagem |
| 138 | Tabelas sem colunas Personagem/Dublador (só transmissão ou home vídeo, ou cabeçalho fora do padrão) |
| 60 | Seção Elenco sem tabela (lista ou vazia) |
| 44 | Página sem nenhuma tabela |
| 25 | Elenco montado por predefinição |

As limitações que ficaram depois da limpeza estão em [reports/01_limpeza.md](reports/01_limpeza.md#o-que-ainda-não-ficou-bom).

## Licença

- Código: [MIT](LICENSE).
- Dados derivados: CC BY-SA 3.0, com atribuição à Dublapédia. Não são versionados (`data/` e `raw/` estão no `.gitignore`).
