"""Resumo da coleta e dos CSVs processados. Uso: python3 scripts/stats.py [data/raw] [data/processed]"""
import csv, json, sys
from collections import Counter
from pathlib import Path

raw = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw")
out = Path(sys.argv[2] if len(sys.argv) > 2 else "data/processed")
size = lambda p: sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6

kinds, wt_bytes, n = Counter(), 0, 0
for f in sorted((raw / "pages").glob("part-*.jsonl")):
    for line in f.open():
        d = json.loads(line); n += 1
        kinds.update(d.get("kinds", []))
        wt_bytes += len((d.get("wikitext") or "").encode())
print(f"páginas baixadas: {n} ({', '.join(f'{k} {v}' for k, v in kinds.most_common())})")
print(f"wikitext: {wt_bytes / 1e6:.1f} MB | data/raw em disco: {size(raw):.1f} MB")

unk = lambda v: v.strip() in ("?", "-", "—", "N/A", "Desconhecido", "Desconhecida", "")
rows = list(csv.DictReader((out / "obras_elenco.csv").open()))
print(f"obras_elenco.csv: {len(rows)} linhas | obras {len({r['obra'] for r in rows})} | "
      f"dubladores {len({r['dublador'] for r in rows if not unk(r['dublador'])})} | atores originais {len({r['ator_original'] for r in rows if r['ator_original']})} | "
      f"com ator original {sum(1 for r in rows if r['ator_original']) / max(len(rows), 1):.1%}")
dub = list(csv.DictReader((out / "dubladores_trabalhos.csv").open()))
print(f"dubladores_trabalhos.csv: {len(dub)} linhas | dubladores {len({r['dublador'] for r in dub})} | "
      f"atores originais {len({r['ator_original'] for r in dub if r['ator_original']})} | obras {len({r['obra'] for r in dub})}")
fic = list(csv.DictReader((out / "fichas_filmografia.csv").open()))
print(f"fichas_filmografia.csv: {len(fic)} linhas | páginas {len({r['pagina'] for r in fic})} | "
      f"dubladores {len({r['dublador'] for r in fic})} | atores originais {len({r['ator_original'] for r in fic if r['ator_original']})}")
print(f"obras_elenco.csv: dublador desconhecido ('?', N/A...) em {sum(unk(r['dublador']) for r in rows) / max(len(rows), 1):.1%} das linhas")
print(f"data/processed em disco: {size(out):.1f} MB")
