"""Extrai obra|versao|ano|midia|estudio|diretor|personagem|ator_original|dublador das tabelas de elenco (wikitext)."""
import csv, json, re, sys
from collections import Counter
from pathlib import Path

import wikitable

REF = re.compile(r"<ref[^>]*?/>|<ref.*?</ref>|<!--.*?-->", re.S)
FILE = re.compile(r"\[\[(?:Arquivo|Ficheiro|File|Imagem|Image):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", re.I)
LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
EXT = re.compile(r"\[(?:https?:)?//[^\s\]]+\s*([^\]]*)\]")
KEEP = re.compile(r"\{\{\s*(?:nowrap|tooltip|small|nobr|lang|pequen[oa]\d*)\s*\|([^{}|]*)[^{}]*\}\}", re.I)

def wtext(s):
    """Wikitext de uma célula -> texto: tira refs, imagens e predefinições; links viram o rótulo."""
    s = REF.sub("", s)
    s = re.sub(r"<sup.*?</sup>", "", s, flags=re.S | re.I)
    s = FILE.sub("", s)
    s = re.sub(r"<hr[^>]*>|\n-{4,}", " ; ", s, flags=re.I)
    s = re.sub(r"<br\s*/?>|\n", " ", s, flags=re.I)
    for _ in range(3):
        s = KEEP.sub(r"\1", s)
        s = re.sub(r"\{\{[^{}]*\}\}", " ", s)
    s = LINK.sub(r"\1", EXT.sub(r"\1", s))
    s = re.sub(r"<[^>]+>|'{2,}|__\w+__", "", s)
    return s.replace("&nbsp;", " ").replace("&amp;", "&")

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

clean = lambda s: re.sub(r"\s*;\s*$", "", re.sub(r"\s+", " ", s)).strip(" ;|")

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
    ip = find("personage", "persongem", "papel")
    idub = find("dublador", "dublagem", "voz brasileira", "dubladora", "versão brasileira")
    iorig = find("diálogo") if find("diálogo") is not None else find("origina", "seiy", "ator", "atriz", "intérprete", "elenco")
    real = False
    if ip is None and idub is not None:
        ip = find("pessoa", "participante", "apresenta", "jurado", "convidado", "elenco")
        real = ip is not None  # reality/documentário: a pessoa é o próprio original
        if ip is None and names and not names[0].strip() and idub != 0: ip = 0  # 1ª coluna sem título
    if ip is None or idub is None or idub == ip: return None
    if real: iorig = ip
    elif iorig in (ip, idub): iorig = None
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
            v = re.sub(r"\{\{.*", "", v).replace("}}", "")
            v = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", v)
            v = re.sub(r"<hr[^>]*>|<br\s*/?>", " ; ", v)
            v = clean(re.sub(r"<[^>]+>|''+", " ", v).split("|")[0])
            if v: vals.append(v)
        if vals: return " ; ".join(vals)
    return ""

MEDIA = [("Jogos Eletrônicos", "game"), ("Novelas", "novela"), ("Anime", "anime"), ("Séries de anime", "anime"),
         ("Filmes Animados", "filme animado"), ("Filmes", "filme"), ("Séries Animadas", "série animada"),
         ("Desenhos animados", "série animada"), ("Séries", "série")]

def media(cats):
    return next((m for c, m in MEDIA if c in cats), "")

def load(raw, kind):
    """Páginas do cache (data/raw/pages/*.jsonl) de um tipo: obra, dublador, ator, estudio, diretor."""
    for f in sorted((Path(raw) / "pages").glob("part-*.jsonl")):
        for line in f.open():
            try: d = json.loads(line)
            except json.JSONDecodeError: continue
            if kind in d.get("kinds", []): yield d

def parse_page(d):
    """(linhas, motivo da falha ou "")."""
    wt = d.get("wikitext") or ""
    if d.get("missing") or not wt: return [], "página sem conteúdo"
    if re.match(r"(?i)\s*#(redirect|redirecionamento)", wt): return [], "redirecionamento"
    meta = dict(obra=d["title"], ano=infobox(wt, "ano", "lançamento", "data_de_lançamento", "exibição"),
                midia=media(d.get("categories", [])),
                estudio=infobox(wt, "estúdio_de_dublagem", "estúdio"),
                diretor=infobox(wt, "direção_de_dublagem", "diretor_de_dublagem"))
    tabs = wikitable.tables(wt)
    if not tabs:
        if re.search(r"(?i)\{\{\s*(elenco|dublagem|personagem)", wt): return [], "elenco em predefinição, sem tabela"
        if re.search(r"(?im)^=+\s*elenco", wt): return [], "seção Elenco sem tabela (lista ou vazia)"
        return [], "sem tabela"
    rows, n_cast = [], 0
    for t in tabs:
        for r in t["rows"]:
            for c in r: c["text"] = wtext(c["text"])
        cr = cast_rows(t)
        if cr is None: continue
        n_cast += 1
        for per, orig, dub in cr:
            rows.append({"obra": meta["obra"], "versao": clean(wtext(t["heading"])), "ano": meta["ano"],
                         "midia": meta["midia"], "estudio": meta["estudio"], "diretor": meta["diretor"],
                         "personagem": per, "ator_original": orig, "dublador": dub})
    if rows: return rows, ""
    if n_cast: return [], "tabela de elenco sem linhas preenchidas"
    heads = [" ".join(c["text"] for c in t["rows"][0]).lower() for t in tabs if t["rows"]]
    if any("personage" in h and "origina" in h for h in heads):
        return [], "produção nacional: só a coluna de vozes originais"
    return [], "tabelas sem colunas Personagem/Dublador"

FIELDS = ["obra", "versao", "ano", "midia", "estudio", "diretor", "personagem", "ator_original", "dublador"]

if __name__ == "__main__":
    raw, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    fails, n_pages, n_ok, seen = Counter(), 0, 0, set()
    with out.open("w", newline="") as fh, (out.parent / "obras_falhas.csv").open("w", newline="") as ff:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader()
        wf = csv.writer(ff); wf.writerow(["obra", "motivo"])
        for d in load(raw, "obra"):
            n_pages += 1
            rows, why = parse_page(d)
            if why: fails[why] += 1; wf.writerow([d["title"], why]); continue
            n_ok += 1
            for r in rows:
                k = tuple(r.values())
                if k in seen: continue  # rowspan em colunas ignoradas duplica linhas
                seen.add(k); w.writerow(r)
    print(f"obras: {n_pages} | com elenco: {n_ok} ({n_ok / max(n_pages, 1):.1%}) | linhas: {len(seen)}")
    for why, n in fails.most_common(): print(f"  {n:6d}  {why}")
