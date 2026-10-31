"""Limpa o elenco das obras e gera data/processed/elenco_limpo.csv.

- separa células compostas ("X ; Y (canções)", "X / Y") em várias linhas, com a coluna qualificador;
- marca dublador desconhecido ("?", "N/A"...) sem apagar a linha;
- normaliza nomes e dá um id canônico por pessoa, ligado à ficha quando há (link da célula, redirecionamentos, nome);
- liga estúdio e diretor à versão certa nas obras com várias dublagens, com uma flag de como foi feito;
- ano numérico, mídia padronizada, franquia (para validação) e gênero (scripts/gender.py: ficha, depois primeiro nome).

Uso: python3 scripts/clean.py [data/raw] [data/processed]
"""
import csv, json, re, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import wikitable
from gender import NameGender, from_page
from parse_obras import clean, load, parse_page, wtext

# ---------------------------------------------------------------- nomes

QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "´": "'", "`": "'"})
# marcadores de vaga; "Dublador Desconhecido nº 6" NÃO entra: é uma voz recorrente com ficha própria
UNKNOWN = re.compile(r"(?i)^(\?+|n/?[ad]|-+|—|–|desconhecid[oa]s?|(ainda )?não (identificad|creditad|confirmad|revelad|especificad)[oa]s?|"
                     r"sem dublagem|não dublad[oa]|(a|por) (confirmar|identificar|adicionar)|sem identificar|indefinid[oa]|"
                     r"ninguém|sem diálogos?|não aparece)$")
# no lado do ator original, papéis que não são uma pessoa
NOT_PERSON = re.compile(r"(?i)^(locução( e placas)?|locutora?|narra(dor|dora|ção)|vários|vozes adicionais)$")

def normalize_name(s):
    """Nome para exibição: sem marcação wiki residual, aspas e espaços padronizados."""
    s = unicodedata.normalize("NFC", s or "").translate(QUOTES)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s).replace("[[", "").replace("]]", "")
    s = re.sub(r"\{\{|\}\}|'{2,}|<[^>]*>|\(\s*\)", "", s).replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip(" ;,.:-–—|*\t")
    if s.count('"') == 2 and s.startswith('"') and s.endswith('"'): s = s[1:-1].strip()
    return s

def name_key(s):
    """Chave de comparação: sem acentos, minúsculas, só letras e dígitos."""
    s = unicodedata.normalize("NFKD", normalize_name(s).casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def title_case_link(t):
    """Alvo de link MediaWiki -> título de página (1ª letra maiúscula, sem âncora)."""
    t = normalize_name(t.split("#")[0])
    return t[:1].upper() + t[1:]

# ---------------------------------------------------------------- células compostas

LINK = re.compile(r"\[\[([^|\]]*)(?:\|([^\]]*))?\]\]")
PAREN = re.compile(r"\(([^()]*)\)")

def _segments(wt):
    """Corta a célula em pedaços por <br>, <hr>, quebra de linha, ';' e '/' fora de links."""
    s = re.sub(r"<ref[^>]*?/>|<ref.*?</ref>|<!--.*?-->", "", wt or "", flags=re.S)
    wrap = lambda m: " (" + m.group(1).strip().strip("()") + ") "  # "<small>(canções)</small>" -> " (canções) "
    s = re.sub(r"<small>(.*?)</small>", wrap, s, flags=re.S | re.I)
    s = re.sub(r"\{\{\s*(?:pequen[oa]\d*|small)\s*\|([^{}]*)\}\}", wrap, s, flags=re.I)
    s = re.sub(r"(?i)<hr[^>]*>|<br\s*/?>|\n", "\x00", s)
    parts = []
    for p in s.split("\x00"):
        for q in wikitable.split_top(p, ";"):
            parts += wikitable.split_top(q, " / ")
    return [p for p in parts if p.strip()]

def _split_links(seg):
    """'[[A]] e [[B]]' ou '[[A]], [[B]]' -> dois pedaços; o resto fica inteiro."""
    links = list(LINK.finditer(seg))
    if len(links) < 2: return [seg]
    between = [seg[a.end():b.start()] for a, b in zip(links, links[1:])]
    if all(re.fullmatch(r"\s*(?:,|e|&|\+)\s*", x) for x in between):
        return [m.group(0) + (seg[links[-1].end():] if m is links[-1] else "") for m in links]
    return [seg]

def split_cell(wt):
    """Wikitext de uma célula -> [{"nome", "link", "qualificador", "desconhecido"}].

    "X ; Y (canções)" -> X | Y (qualificador "canções"); "X (criança)" -> X (qualificador "criança").
    Um pedaço que é só qualificador ("<br><small>(canções)</small>") vai para o nome anterior."""
    out = []
    for seg in _segments(wt):
        for piece in _split_links(seg):
            m = LINK.search(piece)
            link = title_case_link(m.group(1)) if m and not re.match(r"(?i)\s*(arquivo|file|imagem|ficheiro):", m.group(1)) else ""
            text = re.sub(r"\s+", " ", wtext(piece)).strip()
            quals = [q.strip() for q in PAREN.findall(text) if q.strip()]
            nome = normalize_name(PAREN.sub(" ", text))
            if not nome and quals and out:
                out[-1]["qualificador"] = " ; ".join(filter(None, [out[-1]["qualificador"], *quals])); continue
            if not nome and not quals: continue
            unk = not nome or bool(UNKNOWN.match(nome))
            out.append({"nome": "" if unk else nome, "link": "" if unk else link,
                        "qualificador": " ; ".join(quals), "desconhecido": unk})
    return out

# ---------------------------------------------------------------- pessoas

class People:
    """Liga nomes a fichas: link da célula > redirecionamento > nome igual (sem acentos/caixa)."""
    def __init__(self, pages, redirects):
        self.fichas = {d["title"]: d for d in pages}
        self.redirects = redirects
        self.by_key = {}
        for t in self.fichas: self.by_key.setdefault(name_key(t), t)
        for r, t in redirects.items():
            if t in self.fichas: self.by_key.setdefault(name_key(r), t)
        self.gender = {t: from_page(d) for t, d in self.fichas.items()}
        self.names = NameGender()

    def dub_gender(self, ficha, nome):
        """(gênero, fonte) do dublador: a ficha primeiro; senão o primeiro nome (Censo 2010)."""
        g = self.gender.get(ficha, "")
        if g: return g, "ficha"
        g = self.names.guess(ficha or nome)
        return (g, "nome") if g else ("", "")

    def resolve(self, nome, link=""):
        """(id, ficha ou "")"""
        for cand in (link, self.redirects.get(link, "")):
            if cand in self.fichas: return "p:" + cand, cand
        t = self.by_key.get(name_key(nome)) if nome else None
        if t: return "p:" + t, t
        return ("n:" + name_key(nome), "") if nome else ("", "")

# ---------------------------------------------------------------- estúdio e diretor por versão

def field_values(wt, key):
    """{índice: wikitext} de key e key_N no infobox (índice 0 = campo sem número)."""
    out = {}
    for m in re.finditer(r"(?:^|\|)\s*" + key + r"(?:_(\d+))?\s*=(.*?)(?=\n\s*\||\n\s*\}\}|\Z)", wt, re.S | re.M):
        v = wikitable.split_top(m.group(2), "|")[0]
        v = re.sub(r"\}\}\s*$", "", v).strip()
        if v: out[int(m.group(1) or 0)] = v
    return out

def entries(wt, key):
    """[(nomes, qualificador)]: uma entrada por etapa (campo _N) ou por bloco separado por <hr>.
    Dentro de um bloco, cada linha com link abre uma entrada nova se for estúdio, ou se a entrada
    anterior já tem qualificador ("[[A]] (1ª temp.)<br>[[B]] (2ª temp.)"); senão soma nomes (vários diretores)."""
    vals = field_values(wt, key)
    blocks = list(vals.values()) if len(vals) > 1 else [b for v in vals.values() for b in re.split(r"(?i)<hr[^>]*>", v)]
    res = []
    for b in blocks:
        cur = None
        for line in re.split(r"(?i)<br\s*/?>|\n", b):
            names = [normalize_name(x.group(2) or x.group(1)) for x in LINK.finditer(line)
                     if not re.match(r"(?i)\s*(arquivo|file|imagem):", x.group(1))]
            txt = wtext(re.sub(r"\{\{\s*pequen[oa]\d*\s*\|([^{}]*)\}\}", r" (\1) ", line, flags=re.I))
            qual = " ".join(PAREN.findall(txt)).strip()
            plain = normalize_name(PAREN.sub(" ", txt))
            if not names and plain and cur is None: names = [plain]  # estúdio sem link
            if names:
                if cur is None or (len(blocks) == 1 and (key.startswith("estúdio") or cur[1])):
                    if cur: res.append(cur)
                    cur = [names, qual]
                else:
                    cur[0] += names; cur[1] = (cur[1] + " " + qual).strip()
            elif cur is not None and qual:
                cur[1] = (cur[1] + " " + qual).strip()
        if cur: res.append(cur)
    return [(n, q.lower()) for n, q in res if n]

def tokens(s):
    """Marcas que ligam uma versão a uma entrada do infobox: ordinais, anos e 'redublagem'."""
    s = s.lower()
    toks = set()
    for m in re.finditer(r"(\d+)\s*[ªºa°]?\s*(?:(?:e|a|-|,)\s*(\d+)\s*[ªºa°]?\s*)?(dublagem|versão|temporada|temp)\w*(\s+em diante)?", s):
        kind = "temp" if m.group(3).startswith("temp") else "dub"
        lo = int(m.group(1))
        hi = lo + 20 if m.group(4) else int(m.group(2) or m.group(1))
        toks |= {f"{kind}{i}" for i in range(lo, min(hi, lo + 20) + 1)}
    if "redublagem" in s: toks.add("dub2")
    if re.search(r"dublagem original|1ª dublagem", s): toks.add("dub1")
    toks |= set(re.findall(r"\b(19[3-9]\d|20[0-4]\d)\b", s))
    return toks

def match_entry(versao, ents):
    """Índice da entrada do infobox que corresponde à versão, ou None."""
    v = name_key(versao)
    hits = [i for i, (names, _) in enumerate(ents) if any(name_key(n) and name_key(n) in v for n in names)]
    if len(hits) == 1: return hits[0]
    vt = tokens(versao)
    if vt:
        scored = [(len(vt & tokens(q)), i) for i, (_, q) in enumerate(ents)]
        best = max(scored)[0] if scored else 0
        top = [i for s, i in scored if s == best]
        if best and len(top) == 1: return top[0]
    return None

def studio_for(versao, st, di):
    """(estudio, diretor, status) para uma versão; status: vazio | unico | casado | ambiguo."""
    join = lambda e: " ; ".join(dict.fromkeys(e[0]))
    if not st: return "", " ; ".join(join(e) for e in di), "vazio"
    if len(st) == 1: return join(st[0]), " ; ".join(join(e) for e in di), "unico"
    i = match_entry(versao, st)
    if i is None:
        return " ; ".join(join(e) for e in st), " ; ".join(join(e) for e in di), "ambiguo"
    if len(di) == len(st): d = join(di[i])
    elif len(di) == 1: d = join(di[0])
    else:
        j = match_entry(versao, di)
        d = join(di[j]) if j is not None else " ; ".join(join(e) for e in di)
    return join(st[i]), d, "casado"

# ---------------------------------------------------------------- ano, mídia, franquia

MEDIA = [("Jogos Eletrônicos", "game"), ("Novelas", "novela"), ("Anime", "anime"), ("Séries de anime", "anime"),
         ("Filmes de anime", "anime"), ("Filmes Animados", "filme animado"), ("Curtas animados", "curta"),
         ("Curtas da Disney", "curta"), ("Filmes", "filme"), ("Séries Animadas", "série animada"),
         ("Desenhos animados", "série animada"), ("Documentários", "documentário"), ("Reality Show", "reality"),
         ("Reality Shows dos Estados Unidos", "reality"), ("Minisséries", "série"), ("Séries", "série"),
         ("Webséries", "websérie"), ("Especiais", "especial"), ("Especiais de TV", "especial"),
         ("Programas de TV", "programa de TV"), ("Comerciais", "comercial")]

def media(cats):
    cats = set(cats)
    return next((m for c, m in MEDIA if c in cats), "outro")

def first_year(s):
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", s or "")
    return int(m.group(1)) if m else None

FRANCHISE_CAT = re.compile(r"^(Franquia|Universo|Saga|Trilogia) (?!s$).+")
ROMAN = r"(?:i{1,3}|iv|v|vi{0,3}|ix|x)"

def title_stem(t):
    """'Toy Story 2', 'Shrek Terceiro', 'Harry Potter e a Pedra Filosofal' -> raiz do título."""
    s = name_key(re.sub(r"\([^)]*\)", " ", t))
    s = re.split(r"\s+(?:-|–)\s+|:", t.lower())[0] if re.search(r":|\s[-–]\s", t) else s
    s = name_key(s)
    s = re.sub(rf"\s+(?:\d+|{ROMAN}|o retorno|o filme|the movie|parte \d+|o inicio|a origem)$", "", s)
    s = re.sub(r"^(o|a|os|as|the)\s+", "", s)
    return s

def franchises(obras):
    """União de obras ligadas por antecessor/sucessor, mesma categoria de franquia ou mesma raiz de título."""
    parent = {t: t for t in obras}
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        if a in parent and b in parent: parent[find(a)] = find(b)
    by_cat, by_stem = defaultdict(list), defaultdict(list)
    for t, d in obras.items():
        wt = d.get("wikitext") or ""
        for k in ("antecessor", "sucessor"):
            for v in field_values(wt, k).values():
                for m in LINK.finditer(v): union(t, title_case_link(m.group(1)))
        for c in d.get("categories", []):
            if FRANCHISE_CAT.match(c): by_cat[c].append(t)
        stem = title_stem(t)
        if len(stem) >= 4: by_stem[stem].append(t)
    for group in list(by_cat.values()) + list(by_stem.values()):
        for t in group[1:]: union(group[0], t)
    comps = defaultdict(list)
    for t in obras: comps[find(t)].append(t)
    label = {}
    for members in comps.values():
        cats = Counter(c for t in members for c in obras[t].get("categories", []) if FRANCHISE_CAT.match(c))
        name = cats.most_common(1)[0][0] if cats else min(members, key=lambda t: (len(t), t))
        for t in members: label[t] = name
    return label

# ---------------------------------------------------------------- principal

FIELDS = ["obra", "versao", "ano", "ano_texto", "midia", "franquia", "estudio", "diretor", "estudio_status",
          "personagem", "ator_original", "ator_original_id", "ator_original_ficha", "ator_original_genero",
          "dublador", "dublador_id", "dublador_ficha", "dublador_genero", "dublador_genero_fonte", "qualificador",
          "dublador_desconhecido"]

def pair(origs, dubs):
    """Cruza os pedaços das células: mesmo número -> lado a lado; senão, produto."""
    origs = origs or [{"nome": "", "link": "", "qualificador": "", "desconhecido": False}]
    if len(origs) == len(dubs) > 1: return list(zip(origs, dubs))
    if len(origs) > 1 and len(dubs) == 1: return [(o, dubs[0]) for o in origs]
    return [(origs[0] if len(origs) == 1 else {**origs[0], "nome": " ; ".join(o["nome"] for o in origs)}, d)
            for d in dubs]

def main(raw, out):
    raw, out = Path(raw), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    pages = {k: list(load(raw, k)) for k in ("obra", "dublador", "ator", "diretor")}
    redirects = json.loads((raw / "redirects.json").read_text()) if (raw / "redirects.json").exists() else {}
    people = People([d for k in ("dublador", "ator", "diretor") for d in pages[k]], redirects)
    obras = {d["title"]: d for d in pages["obra"]}
    fran = franchises(obras)
    seen, n_in = set(), 0
    with (out / "elenco_limpo.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader()
        for t, d in obras.items():
            rows, _ = parse_page(d)
            if not rows: continue
            wt = d.get("wikitext") or ""
            st = entries(wt, "estúdio_de_dublagem") or entries(wt, "estúdio")
            di = entries(wt, "direção_de_dublagem") or entries(wt, "diretor_de_dublagem")
            ano, midia = first_year(rows[0]["ano"]), media(d.get("categories", []))
            for r in rows:
                n_in += 1
                estudio, diretor, status = studio_for(r["versao"], st, di)
                dubs = split_cell(r["_dub_wt"]) or [{"nome": "", "link": "", "qualificador": "", "desconhecido": True}]
                origs = [o for o in split_cell(r["_orig_wt"]) if not o["desconhecido"] and not NOT_PERSON.match(o["nome"])]
                for o, x in pair(origs, dubs):
                    oid, ofi = people.resolve(o["nome"], o["link"])
                    did, dfi = people.resolve(x["nome"], x["link"])
                    dg, dgf = people.dub_gender(dfi, x["nome"]) if not x["desconhecido"] else ("", "")
                    row = {"obra": t, "versao": r["versao"], "ano": ano or "", "ano_texto": r["ano"], "midia": midia,
                           "franquia": fran[t], "estudio": estudio, "diretor": diretor, "estudio_status": status,
                           "personagem": normalize_name(r["personagem"]),
                           "ator_original": (ofi or o["nome"]), "ator_original_id": oid, "ator_original_ficha": bool(ofi),
                           "ator_original_genero": people.gender.get(ofi, ""),
                           "dublador": (dfi or x["nome"]), "dublador_id": did, "dublador_ficha": bool(dfi),
                           "dublador_genero": dg, "dublador_genero_fonte": dgf,
                           "qualificador": " ; ".join(filter(None, [x["qualificador"], o["qualificador"] and "original: " + o["qualificador"]])),
                           "dublador_desconhecido": x["desconhecido"]}
                    k = tuple(row.values())
                    if k not in seen: seen.add(k); w.writerow(row)
    print(f"linhas de entrada: {n_in} | linhas limpas: {len(seen)}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/raw", sys.argv[2] if len(sys.argv) > 2 else "data/processed")
