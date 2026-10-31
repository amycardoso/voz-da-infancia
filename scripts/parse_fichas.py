"""Extrai as tabelas de filmografia das fichas de ator original, seiyuu e personagem:
pagina|tipo|obra|ano|personagem|ator_original|dublador|estudio.

Fichas de ator/seiyuu: "Ano | Título | Personagem | Dublagem | Estúdio" (o ator é a própria página).
Fichas de personagem: "Ano | Título | Ator Original | Dublador | Estúdio" (o personagem é a página).
Uso: python3 scripts/parse_fichas.py <data/raw> <saida.csv>
"""
import csv, sys
from collections import Counter
from pathlib import Path

import wikitable
from parse_obras import clean, grid, load, wtext

FIELDS = ["pagina", "tipo", "obra", "ano", "personagem", "ator_original", "dublador", "estudio"]

def film_rows(title, table):
    g = grid(table["rows"])
    lead = 0
    while lead < len(g) and g[lead] and all(c["h"] for c in g[lead]): lead += 1
    if not lead: return None
    ncol = max(len(r) for r in g)
    names = [" ".join(dict.fromkeys(clean(r[i]["text"]) for r in g[:lead] if i < len(r))).lower() for i in range(ncol)]
    find = lambda *keys: next((i for i, n in enumerate(names) if any(k in n for k in keys)), None)
    if find("projeto") is not None: return None  # "Ficha de vozes": contagem por dublador, não obra a obra
    iobra, idub = find("título", "titulo", "obra", "produção"), find("dublag", "dublador", "dubladora")
    if iobra is None or idub is None: return None
    iano, iest, iper = find("ano"), find("estúdio", "estudio"), find("personage")
    iorig = find("origina", "ator", "atriz", "seiy", "intérprete")
    tipo = "personagem" if iorig is not None and iorig != idub else "ator"
    res = []
    for r in g[lead:]:
        if not r or all(c["h"] for c in r) or len({id(c) for c in r}) == 1: continue
        get = lambda i: clean(r[i]["text"]) if i is not None and i < len(r) else ""
        obra, dub = get(iobra), get(idub)
        if not obra or not dub: continue
        res.append({"pagina": title, "tipo": tipo, "obra": obra, "ano": get(iano),
                    "personagem": get(iper) if tipo == "ator" else title,
                    "ator_original": title if tipo == "ator" else get(iorig),
                    "dublador": dub, "estudio": get(iest)})
    return res

if __name__ == "__main__":
    raw, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    seen_pages, n_ok, fails, seen = set(), 0, Counter(), set()
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader()
        for kind in ("ator", "dublador"):
            for d in load(raw, kind):
                if d["title"] in seen_pages: continue
                seen_pages.add(d["title"])
                rows = []
                for t in wikitable.tables(d.get("wikitext") or ""):
                    for r in t["rows"]:
                        for c in r: c["text"] = wtext(c["text"])
                    rows += film_rows(d["title"], t) or []
                if kind == "dublador" and not rows: continue  # dublador brasileiro: vai para parse_dubladores
                if not rows: fails["sem tabela de filmografia"] += 1; continue
                n_ok += 1
                for r in rows:
                    k = tuple(r.values())
                    if k not in seen: seen.add(k); w.writerow(r)
    print(f"fichas com filmografia: {n_ok} | linhas: {len(seen)} | atores sem tabela: {fails['sem tabela de filmografia']}")
