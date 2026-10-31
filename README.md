# Voz da Infância

A rede da dublagem brasileira: quem dubla quem, em quais obras, e um modelo que prevê o dublador de um personagem.

## Fonte

Os dados vêm da [Dublapédia](https://dublagem.fandom.com) (dublagem.fandom.com), lida pela API MediaWiki (`api.php`) em baixo volume. O conteúdo da Dublapédia é licenciado sob [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/); créditos aos editores da Dublapédia. Qualquer dado derivado publicado a partir daqui mantém a atribuição e a mesma licença.

## Scripts

Os scripts em `scripts/` vêm do teste de viabilidade e recebem os caminhos pela linha de comando:

- `count.py <saida.json> <template>...` — conta as páginas que transcluem cada template e salva os títulos.
- `fetch.py <pasta_raw> <título>...` — baixa wikitext, HTML renderizado e categorias das páginas.
- `parse_obras.py <pasta_raw> <saida.csv>` — extrai a tabela de elenco das obras (personagem, ator original, dublador, estúdio, diretor) do HTML renderizado.
- `parse_dubladores.py <pasta_raw> <saida.csv>` — extrai a seção "Trabalhos em Dublagem" das páginas de dubladores.

## Licença

- Código: [MIT](LICENSE).
- Dados derivados: CC BY-SA 3.0, com atribuição à Dublapédia. Não são versionados (`data/` e `raw/` estão no `.gitignore`).
