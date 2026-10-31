"""Extrai dublador|ator_original|midia|obra|ano|personagem da seção 'Trabalhos em Dublagem' (wikitext)."""
import csv, json, re, sys
from pathlib import Path

LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
ITEM = re.compile(r"^\*+\s*(?P<obra>.+?)\s*\((?P<ano>[^)]*\d{4}[^)]*)\)\s*[-–—:]\s*(?P<per>.+)$")

def text(s):
    s = re.sub(r"<ref[^>]*?/>|<ref.*?</ref>", "", s)
    for _ in range(2): s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"<[^>]+>|'''?", "", LINK.sub(r"\1", s))
    return re.sub(r"\s+", " ", s).strip()

def parse(title, wt):
    """Cabeçalhos com [[link]] são o ator original; os demais (Filmes, Animes...) são a mídia.
    A ordem varia por página (ator > mídia ou mídia > ator), por isso guarda uma pilha por nível."""
    rows, stack, on = [], {}, False
    for line in wt.splitlines():
        h = re.match(r"^(=+)\s*(.*?)\s*\1\s*$", line)
        if h:
            lvl, raw = len(h.group(1)), h.group(2)
            if lvl == 2:
                name = text(raw).lower(); on = "dublag" in name and "dire" not in name; stack = {}
            else:
                stack = {k: v for k, v in stack.items() if k < lvl}
                stack[lvl] = (text(raw), "[[" in raw)
            continue
        m = ITEM.match(line.strip())
        if on and m:
            heads = [stack[k] for k in sorted(stack)]
            ator = next((n for n, is_actor in reversed(heads) if is_actor), "")
            midia = " / ".join(n for n, is_actor in heads if not is_actor)
            per = text(m["per"])
            tail = re.match(r"^(.*\S)\s*\(([^()]+)\)$", per)  # "Keith Pérez (Jay Hernandez)" em seções "Outros"
            if not ator and tail and not re.search(r"(?i)\b(ep|eps|temp|voz|vozes|cap|dlc|redub|\d)", tail.group(2)):
                per, ator = tail.group(1), tail.group(2)
            rows.append(dict(dublador=title, ator_original=ator, midia=midia,
                             obra=text(m["obra"]), ano=text(m["ano"]), personagem=per))
    return rows

if __name__ == "__main__":
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    allrows = []
    for f in sorted(src.glob("*.json")):
        d = json.loads(f.read_text())
        r = parse(d["title"], d["wikitext"])
        print("%-35s linhas=%4d atores=%3d" % (d["title"], len(r), len({x["ator_original"] for x in r})))
        allrows += r
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["dublador", "ator_original", "midia", "obra", "ano", "personagem"])
        w.writeheader(); w.writerows(allrows)
    print("TOTAL", len(allrows), "| páginas com trabalhos", sum(1 for _ in src.glob("*.json")))
