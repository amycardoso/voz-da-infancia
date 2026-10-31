"""Baixa wikitext + HTML renderizado + categorias de páginas da Dublapédia via API MediaWiki."""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

UA = "VozDaInfancia/0.1 (pesquisa academica; baixo volume)"
API = "https://dublagem.fandom.com/api.php"
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

def api(**p):
    p.update(format="json", formatversion="2")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(p), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        time.sleep(1.0)
        return json.load(r)

for title in sys.argv[2:]:
    d = api(action="parse", page=title, prop="wikitext|text|categories", redirects=1)
    if "error" in d:
        print("ERRO", title, d["error"]["info"]); continue
    p = d["parse"]
    name = p["title"].replace("/", "_")
    (OUT / f"{name}.json").write_text(json.dumps({
        "title": p["title"], "wikitext": p["wikitext"], "html": p["text"],
        "categories": [c["category"] for c in p["categories"]],
    }, ensure_ascii=False))
    print("ok", p["title"], len(p["text"]))
