RAW ?= data/raw
OUT ?= data/processed
PY  ?= python3

.PHONY: all collect parse clean-data stats test notebooks venv

all: collect parse clean-data

# Baixa (ou retoma) o wikitext das obras e fichas pela API MediaWiki.
collect:
	$(PY) -u scripts/collect.py $(RAW)

parse:
	$(PY) scripts/parse_obras.py $(RAW) $(OUT)/obras_elenco.csv
	$(PY) scripts/parse_dubladores.py $(RAW) $(OUT)/dubladores_trabalhos.csv
	$(PY) scripts/parse_fichas.py $(RAW) $(OUT)/fichas_filmografia.csv

stats:
	$(PY) scripts/stats.py $(RAW) $(OUT)

# Separa células compostas, normaliza nomes e liga estúdio/diretor à versão -> $(OUT)/elenco_limpo.csv
clean-data:
	$(PY) scripts/clean.py $(RAW) $(OUT)

venv:
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt

test:
	.venv/bin/pytest -q tests

notebooks:
	.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb
