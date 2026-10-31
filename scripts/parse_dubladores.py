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

def why_empty(wt):
    if not wt: return "página sem conteúdo"
    if re.match(r"(?i)\s*#(redirect|redirecionamento)", wt): return "redirecionamento"
    secs = [text(h).lower() for h in re.findall(r"(?m)^==\s*([^=].*?)\s*==\s*$", wt)]
    if any(x.startswith(("ficha de dublador", "ficha por dublador", "ficha de vozes", "ficha por voz")) for x in secs) \
            and not any("trabalho" in x for x in secs):
        return "ficha de personagem ou seiyuu (vai para parse_fichas)"
    if "filmografia" in secs: return "filmografia em tabela (seiyuu/ator; vai para parse_fichas)"
    if not any("dublag" in x and "dire" not in x for x in secs): return "sem seção Trabalhos em Dublagem"
    if re.search(r"(?m)^\{\|", wt) and not re.search(r"(?m)^\*", wt): return "trabalhos em tabela, não em lista"
    return "itens fora do formato *[[Obra]] (ano) - Personagem"

if __name__ == "__main__":
    from collections import Counter
    from parse_obras import load
    raw, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    fails, n_pages, n_ok, n_rows = Counter(), 0, 0, 0
    with out.open("w", newline="") as fh, (out.parent / "dubladores_falhas.csv").open("w", newline="") as ff:
        w = csv.DictWriter(fh, fieldnames=["dublador", "ator_original", "midia", "obra", "ano", "personagem"])
        w.writeheader()
        wf = csv.writer(ff); wf.writerow(["dublador", "motivo"])
        for d in load(raw, "dublador"):
            n_pages += 1
            wt = d.get("wikitext") or ""
            r = parse(d["title"], wt)
            if not r:
                why = why_empty(wt); fails[why] += 1; wf.writerow([d["title"], why]); continue
            n_ok += 1; n_rows += len(r); w.writerows(r)
    print(f"dubladores: {n_pages} | com trabalhos: {n_ok} ({n_ok / max(n_pages, 1):.1%}) | linhas: {n_rows}")
    for why, n in fails.most_common(): print(f"  {n:6d}  {why}")
