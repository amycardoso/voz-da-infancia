"""Extrai a tabela obra|ano|midia|estudio|diretor|versao|personagem|ator_original|dublador do HTML renderizado."""
import csv, json, re, sys
from html.parser import HTMLParser
from pathlib import Path

class Tables(HTMLParser):
    """Coleta tabelas (célula = texto, rowspan, colspan, is_header) e o último heading antes de cada uma."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.stack, self.heading, self.in_h, self.skip = [], [], "", None, 0
    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag in ("h2", "h3", "h4"): self.in_h, self.htext = tag, ""
        if tag in ("sup", "style", "script"): self.skip += 1
        if tag == "table": self.stack.append({"heading": self.heading, "rows": [], "cell": None})
        if not self.stack: return
        t = self.stack[-1]
        if tag == "tr": t["rows"].append([])
        elif tag in ("td", "th") and t["rows"] is not None:
            if not t["rows"]: t["rows"].append([])
            t["cell"] = {"text": "", "h": tag == "th",
                         "rs": int(re.sub(r"\D", "", a.get("rowspan", "1")) or 1),
                         "cs": int(re.sub(r"\D", "", a.get("colspan", "1")) or 1)}
            t["rows"][-1].append(t["cell"])
        elif tag in ("hr", "br") and t["cell"] is not None: t["cell"]["text"] += " ; " if tag == "hr" else " "
    def handle_endtag(self, tag):
        if tag in ("sup", "style", "script"): self.skip = max(0, self.skip - 1)
        if tag == self.in_h:
            self.heading, self.in_h = re.sub(r"\s+", " ", self.htext.replace("[editar]", "")).strip(), None
        if self.stack and tag in ("td", "th"): self.stack[-1]["cell"] = None
        if tag == "table" and self.stack: self.tables.append(self.stack.pop())
    def handle_data(self, d):
        if self.skip: return
        if self.in_h: self.htext += d
        if self.stack and self.stack[-1]["cell"] is not None: self.stack[-1]["cell"]["text"] += d

def grid(rows):
    """Expande rowspan/colspan numa grade retangular."""
    out, pend = [], {}
    for r in rows:
        line, ci, it = [], 0, iter(r)
        while True:
            if ci in pend:
                cell, left = pend[ci]
                line.append(cell)
                if left <= 1: del pend[ci]
                else: pend[ci] = (cell, left - 1)
                ci += 1; continue
            c = next(it, None)
            if c is None: break
            for _ in range(c["cs"]):
                line.append(c)
                if c["rs"] > 1: pend[ci] = (c, c["rs"] - 1)
                ci += 1
        while ci in pend:  # células pendentes no fim da linha
            cell, left = pend[ci]; line.append(cell)
            if left <= 1: del pend[ci]
            else: pend[ci] = (cell, left - 1)
            ci += 1
        out.append(line)
    return out

clean = lambda s: re.sub(r"\s*;\s*$", "", re.sub(r"\s+", " ", s)).strip(" ;")

def cast_rows(table):
    g = grid(table["rows"])
    if g and not any(c["h"] for c in g[0]) and any("personage" in c["text"].lower() for c in g[0]):
        for c in g[0]: c["h"] = True  # cabeçalho escrito como '''negrito''' em <td>
    is_hdr = lambda r: r and all(c["h"] for c in r)
    divider = lambda r: len({id(c) for c in r}) == 1  # linha "Personagens Principais" ocupando a largura toda
    lead = 0
    while lead < len(g) and (not g[lead] or is_hdr(g[lead])): lead += 1
    hdr = [r for r in g[:lead] if r and not divider(r)]
    body = [r for r in g[lead:] if r and not is_hdr(r) and not divider(r)]
    if not hdr or not body: return None
    ncol = max(len(r) for r in g)
    names = [" ".join(dict.fromkeys(clean(r[i]["text"]) for r in hdr if i < len(r))).lower() for i in range(ncol)]
    find = lambda *keys: next((i for i, n in enumerate(names) if any(k in n for k in keys)), None)
    ip = find("personage", "papel")
    idub = find("dublador", "dublagem", "voz brasileira", "dubladora", "versão brasileira")
    iorig = find("diálogo") if find("diálogo") is not None else find("origina", "seiy", "ator", "atriz", "intérprete", "elenco")
    if ip is None or idub is None or idub == ip: return None
    if iorig in (ip, idub): iorig = None
    res = []
    for r in body:
        get = lambda i: clean(r[i]["text"]) if i is not None and i < len(r) else ""
        p, d = get(ip), get(idub)
        if p and d: res.append((p, get(iorig), d))
    return res

def infobox(wt, *keys):
    """Valor do campo; em "Infobox de produção com etapas" junta campo_1, campo_2... com ' ; '."""
    for k in keys:
        vals = []
        for m in re.finditer(r"\|+\s*" + k + r"(?:_\d+)?\s*=(.*)$", wt, re.M):
            v = m.group(1)
            for _ in range(3): v = re.sub(r"\{\{[^{}]*\}\}", " ", v)
            v = re.sub(r"\{\{.*", "", v)
            v = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", v)
            v = re.sub(r"<hr[^>]*>|<br\s*/?>", " ; ", v)
            v = clean(re.sub(r"<[^>]+>|''+", " ", v).split("|")[0])
            if v: vals.append(v)
        if vals: return " ; ".join(vals)
    return ""

MEDIA = [("Jogos_Eletrônicos", "game"), ("Novelas", "novela"), ("Anime", "anime"), ("Séries_de_anime", "anime"),
         ("Filmes_Animados", "filme animado"), ("Filmes", "filme"), ("Séries_Animadas", "série animada"),
         ("Desenhos_animados", "série animada"), ("Séries", "série")]

def media(cats):
    return next((m for c, m in MEDIA if c in cats), "")

if __name__ == "__main__":
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    stats, rows = [], []
    for f in sorted(src.glob("*.json")):
        d = json.loads(f.read_text())
        p = Tables(); p.feed(d["html"])
        wt = d["wikitext"]
        meta = dict(obra=d["title"], ano=infobox(wt, "ano", "lançamento", "data_de_lançamento", "exibição"),
                    midia=media(d["categories"]),
                    estudio=infobox(wt, "estúdio_de_dublagem", "estúdio"),
                    diretor=infobox(wt, "direção_de_dublagem", "diretor_de_dublagem"))
        n_tab, n = 0, 0
        for t in p.tables:
            cr = cast_rows(t)
            if cr:
                n_tab += 1
                for per, orig, dub in cr:
                    rows.append({**meta, "versao": t["heading"], "personagem": per, "ator_original": orig, "dublador": dub}); n += 1
        stats.append((d["title"], meta["midia"], len(p.tables), n_tab, n))
    rows = list({tuple(r.values()): r for r in rows}.values())  # rowspan em colunas ignoradas duplica linhas
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["obra"]); w.writeheader(); w.writerows(rows)
    for s in stats: print("%-40s %-15s tabelas=%3d elenco=%3d linhas=%4d" % s)
    print("TOTAL linhas", len(rows), "| páginas com elenco", sum(1 for s in stats if s[4]), "/", len(stats))
