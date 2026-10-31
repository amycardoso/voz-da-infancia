"""Coleta o wikitext das obras e fichas da Dublapédia pela API MediaWiki, com cache retomável.

Uso: python3 scripts/collect.py [pasta_raw]   (padrão: data/raw)

1. Lista os títulos (ns 0) de cada categoria e de cada infobox -> <raw>/lists/<nome>.json
2. Baixa revisões em lotes de 50 (wikitext + categorias) -> <raw>/pages/part-NNNN.jsonl
   Rodar de novo pula as listas já salvas e os títulos já baixados.
"""
import json, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

UA = "VozDaInfancia/0.1 (pesquisa academica; baixo volume)"
API = "https://dublagem.fandom.com/api.php"
RAW = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw")
BATCH, PAUSE = 50, 1.0

# tipo -> fontes ("cat:" = categoria, "tpl:" = páginas que usam a predefinição)
SOURCES = {
    "obra": ["cat:Filmes", "cat:Desenhos animados", "cat:Séries", "cat:Anime", "cat:Jogos Eletrônicos",
             "cat:Novelas", "cat:Redublagem", "tpl:Infobox de produção", "tpl:Infobox de produção com etapas"],
    "dublador": ["tpl:Infobox de dublador", "cat:Dubladores"],
    "ator": ["tpl:Infobox de ator", "cat:Atores", "cat:Atrizes"],
    "estudio": ["tpl:Infobox de estúdio"],
    "diretor": ["cat:Diretores de Dublagem"],
}

_last = 0.0
def api(**p):
    """GET na API com no máximo ~1 req/s, maxlag e novas tentativas com espera crescente."""
    global _last
    p.update(format="json", formatversion="2", maxlag="5")
    url = API + "?" + urllib.parse.urlencode(p)
    for attempt in range(6):
        time.sleep(max(0.0, PAUSE - (time.time() - _last)))
        _last = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.load(r)
            if d.get("error", {}).get("code") == "maxlag":
                raise RuntimeError("maxlag")
            if "error" in d:
                raise RuntimeError(d["error"])
            return d
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as e:
            wait = 2 ** (attempt + 1)
            print(f"  erro ({e}); nova tentativa em {wait}s", flush=True)
            time.sleep(wait)
    raise SystemExit("API falhou 6 vezes seguidas: " + url)

def list_titles(src):
    kind, name = src.split(":", 1)
    if kind == "cat":
        q, key, cont_key = dict(list="categorymembers", cmtitle="Categoria:" + name, cmnamespace=0,
                                cmtype="page", cmlimit=500), "categorymembers", "cmcontinue"
    else:
        q, key, cont_key = dict(list="embeddedin", eititle="Predefinição:" + name, einamespace=0,
                                eilimit=500), "embeddedin", "eicontinue"
    titles, cont = [], {}
    while True:
        d = api(action="query", **q, **cont)
        titles += [x["title"] for x in d["query"][key]]
        if "continue" not in d: return titles
        cont = {cont_key: d["continue"][cont_key]}

def fetch_batch(titles):
    """Revisão atual + categorias de até 50 títulos; segue 'continue' juntando as partes."""
    pages, cont = {}, {}
    while True:
        d = api(action="query", titles="|".join(titles), prop="revisions|categories",
                rvprop="ids|timestamp|content", rvslots="main", cllimit="max", clshow="!hidden", **cont)
        for pg in d["query"].get("pages", []):
            cur = pages.setdefault(pg["title"], {"title": pg["title"], "pageid": pg.get("pageid"),
                                                 "missing": pg.get("missing", False), "categories": []})
            cur["categories"] += [c["title"].split(":", 1)[1] for c in pg.get("categories", [])]
            for rev in pg.get("revisions", []):
                cur.update(revid=rev["revid"], timestamp=rev["timestamp"],
                           wikitext=rev["slots"]["main"].get("content", ""))
        if "continue" not in d: return list(pages.values())
        cont = {k: v for k, v in d["continue"].items()}

def main():
    (RAW / "lists").mkdir(parents=True, exist_ok=True)
    (RAW / "pages").mkdir(parents=True, exist_ok=True)
    kinds = {}
    for kind, srcs in SOURCES.items():
        for src in srcs:
            f = RAW / "lists" / (src.replace(":", "_").replace(" ", "_") + ".json")
            if not f.exists():
                f.write_text(json.dumps(list_titles(src), ensure_ascii=False))
            titles = json.loads(f.read_text())
            print(f"{src}: {len(titles)}", flush=True)
            for t in titles: kinds.setdefault(t, set()).add(kind)
    (RAW / "kinds.json").write_text(json.dumps({t: sorted(k) for t, k in kinds.items()}, ensure_ascii=False))

    done = set()
    parts = sorted((RAW / "pages").glob("part-*.jsonl"))
    for f in parts:
        for line in f.open():
            try: done.add(json.loads(line)["title"])
            except json.JSONDecodeError: pass  # última linha cortada por interrupção: baixa de novo
    todo = sorted(t for t in kinds if t not in done)
    print(f"títulos: {len(kinds)} | já baixados: {len(done)} | faltam: {len(todo)}", flush=True)
    n = len(parts)
    for i in range(0, len(todo), BATCH):
        batch = fetch_batch(todo[i:i + BATCH])
        with (RAW / "pages" / f"part-{n:04d}.jsonl").open("w") as fh:
            for pg in batch:
                pg["kinds"] = sorted(kinds.get(pg["title"], []))
                fh.write(json.dumps(pg, ensure_ascii=False) + "\n")
        n += 1
        print(f"  {min(i + BATCH, len(todo))}/{len(todo)}", flush=True)

if __name__ == "__main__":
    main()
