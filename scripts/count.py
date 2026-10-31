"""Conta páginas (ns 0) que transcluem cada template e salva os títulos."""
import json, sys, time, urllib.parse, urllib.request
UA = "VozDaInfancia/0.1 (pesquisa academica; baixo volume)"
API = "https://dublagem.fandom.com/api.php"
def api(**p):
    p.update(format="json", formatversion="2")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(p), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        time.sleep(0.5); return json.load(r)
out = {}
for tpl in sys.argv[2:]:
    titles, cont = [], {}
    while True:
        d = api(action="query", list="embeddedin", eititle="Predefinição:" + tpl, einamespace=0, eilimit=500, **cont)
        titles += [x["title"] for x in d["query"]["embeddedin"]]
        if "continue" not in d: break
        cont = {"eicontinue": d["continue"]["eicontinue"]}
    out[tpl] = titles; print(tpl, len(titles))
json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False)
