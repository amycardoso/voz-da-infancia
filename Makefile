RAW ?= data/raw
OUT ?= data/processed
PY  ?= python3

.PHONY: all collect parse stats

all: collect parse

# Baixa (ou retoma) o wikitext das obras e fichas pela API MediaWiki.
collect:
	$(PY) -u scripts/collect.py $(RAW)

parse:
	$(PY) scripts/parse_obras.py $(RAW) $(OUT)/obras_elenco.csv
	$(PY) scripts/parse_dubladores.py $(RAW) $(OUT)/dubladores_trabalhos.csv
	$(PY) scripts/parse_fichas.py $(RAW) $(OUT)/fichas_filmografia.csv

stats:
	$(PY) scripts/stats.py $(RAW) $(OUT)
