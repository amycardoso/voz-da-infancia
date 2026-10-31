"""Prever o dublador brasileiro de um papel (notebooks/03_modelo.ipynb).

Um papel = uma linha de elenco_limpo.csv com dublador e ator original conhecidos. Dado o papel
(ator original, obra, ano, mídia, estúdio, diretor, gênero do ator), ordenar os dubladores candidatos.

Sem vazamento:
- toda feature histórica (contagens ator→dublador, diretor→dublador, estúdio→dublador, popularidade)
  vem de um `History` construído só com o treino;
- para as consultas de treino do ranker, as contagens descontam o próprio grupo da consulta (a obra na
  validação temporal, a franquia na validação por franquia), imitando o que o teste vai ver;
- recência e atividade recente olham só para anos anteriores ao do papel.
"""
import bisect, json, math, random, re
from collections import Counter, defaultdict
from pathlib import Path

from explore import ROOT, load as load_clean

GRUPO = {"filme": "live-action", "série": "live-action", "novela": "live-action",
         "série animada": "animação", "filme animado": "animação", "curta": "animação",
         "anime": "anime", "game": "game"}
ADICIONAL = re.compile(r"(?i)adiciona|outras vozes|participa|epis[oó]dic|secund|recorrent|apoio|figura|convidad|extra")
MIN_PAPEIS = 5
INF = float("inf")

# ================================================================ dados

def _paginas(raw=ROOT / "data" / "raw"):
    """({título: 'RJ'|'SP'} por categorias de cidade, {título: tipos da página})."""
    cid, kinds = {}, {}
    for f in sorted((raw / "pages").glob("part-*.jsonl")):
        for line in f.open():
            d = json.loads(line)
            kinds[d["title"]] = set(d.get("kinds", []))
            c = set(d.get("categories", []))
            rj = bool({"Dubladores do Rio de Janeiro", "Dublagens do Rio de Janeiro"} & c)
            sp = bool({"Dubladores de São Paulo", "Dublagens de São Paulo"} & c)
            if rj != sp: cid[d["title"]] = "RJ" if rj else "SP"
    return cid, kinds

def load_papeis(path=None):
    """Papéis com dublador e ator original conhecidos, com os campos que o modelo usa."""
    rows = load_clean(path) if path else load_clean()
    cid, kinds = _paginas()
    so_ator = lambda i: i.startswith("p:") and not kinds.get(i[2:], set()) & {"dublador", "diretor"}
    out = []
    for r in rows:
        if r["dublador_desconhecido"] or not r["ator_original_id"] or not r["dublador_id"]: continue
        if so_ator(r["dublador_id"]): continue  # voz original numa coluna de dublador (ficha só de ator)
        dirs = [d for d in r["diretor"].split(" ; ") if d] if r["estudio_status"] in ("unico", "casado") else []
        out.append({
            "obra": r["obra"], "franquia": r["franquia"], "versao": r["versao"], "personagem": r["personagem"],
            "ano": r["ano"], "midia": r["midia"], "grupo": GRUPO.get(r["midia"], "outro"),
            "ator": r["ator_original_id"], "ator_nome": r["ator_original"], "ator_genero": r["ator_original_genero"],
            "dub": r["dublador_id"], "dub_nome": r["dublador"], "dub_genero": r["dublador_genero"],
            "dub_cidade": cid.get(r["dublador"], ""), "obra_cidade": cid.get(r["obra"], ""),
            "dirs": dirs, "est": r["estudio"] if r["estudio_status"] in ("unico", "casado") and r["estudio"] else "",
            "adicional": bool(ADICIONAL.search(r["versao"])),
        })
    return out

# ================================================================ histórico (só treino)

class History:
    """Contagens tiradas de um conjunto de papéis. `minus` (outro History) é subtraído nas consultas."""
    def __init__(self, rows):
        self.ator_dub, self.ator = Counter(), Counter()
        self.dir_dub, self.dir = Counter(), Counter()
        self.est_dub, self.est = Counter(), Counter()
        self.pop, self.grp_dub, self.dec_dub, self.prin = Counter(), Counter(), Counter(), Counter()
        self.anos = defaultdict(list)
        self.est_anos, self.dir_anos = defaultdict(list), defaultdict(list)
        self.est_dubs, self.dir_dubs = defaultdict(set), defaultdict(set)
        self.dub_info = {}
        for r in rows:
            a, d = r["ator"], r["dub"]
            self.ator_dub[(a, d)] += 1; self.ator[a] += 1
            for x in r["dirs"]: self.dir_dub[(x, d)] += 1; self.dir[x] += 1
            if r["est"]: self.est_dub[(r["est"], d)] += 1; self.est[r["est"]] += 1
            self.pop[d] += 1; self.grp_dub[(r["grupo"], d)] += 1; self.prin[d] += not r["adicional"]
            if r["ano"]:
                self.dec_dub[(r["ano"] // 10, d)] += 1; self.anos[d].append(r["ano"])
                if r["est"]: self.est_anos[(r["est"], d)].append(r["ano"]); self.est_dubs[r["est"]].add(d)
                for x in r["dirs"]: self.dir_anos[(x, d)].append(r["ano"]); self.dir_dubs[x].add(d)
            self.dub_info.setdefault(d, (r["dub_nome"], r["dub_genero"], r["dub_cidade"]))
        for idx in (self.anos, self.est_anos, self.dir_anos):
            for v in idx.values(): v.sort()
        self.ano_max = max((v[-1] for v in self.anos.values()), default=0)
        # índices para os candidatos
        self.by_ator, self.by_dir, self.by_est = defaultdict(list), defaultdict(list), defaultdict(list)
        for (a, d), n in self.ator_dub.items(): self.by_ator[a].append((n, d))
        for (x, d), n in self.dir_dub.items(): self.by_dir[x].append((n, d))
        for (e, d), n in self.est_dub.items(): self.by_est[e].append((n, d))
        for idx in (self.by_ator, self.by_dir, self.by_est):
            for k in idx: idx[k].sort(key=lambda t: (-t[0], t[1]))

def cnt(h, minus, attr, key):
    v = getattr(h, attr)[key]
    return v - getattr(minus, attr)[key] if minus is not None else v

JANELA = 6  # anos antes do papel que contam como "recente"

def janela(h, minus, attr, key, y):
    """Papéis do par em [y' - JANELA, y'), y' = min(y, fim do histórico + 1): só o passado do papel,
    e no teste temporal, os últimos anos que o histórico tem."""
    if not y: return 0
    y = min(y, h.ano_max + 1)
    def c(hh):
        v = getattr(hh, attr).get(key)
        return bisect.bisect_left(v, y) - bisect.bisect_left(v, y - JANELA) if v else 0
    return c(h) - (c(minus) if minus is not None else 0)

def recentes(h, minus, kind, k, y, cls):
    """Os k dubladores com mais papéis recentes (janela antes de y) num estúdio ou diretor."""
    dubs = (h.est_dubs if kind == "est" else h.dir_dubs).get(k, ())
    attr = "est_anos" if kind == "est" else "dir_anos"
    sc = [(janela(h, minus, attr, (k, d), y), d) for d in dubs if d in cls.pos]
    return [(n, d) for n, d in sorted(sc, key=lambda t: (-t[0], t[1])) if n > 0]

class Classes:
    """Dubladores candidatos: >= MIN_PAPEIS papéis no histórico; ordem de popularidade fixa."""
    def __init__(self, h, min_papeis=MIN_PAPEIS):
        self.order = [d for d, n in sorted(h.pop.items(), key=lambda t: (-t[1], t[0])) if n >= min_papeis]
        self.pos = {d: i for i, d in enumerate(self.order)}
        self.by_grupo = defaultdict(list)
        for (g, d), n in sorted(h.grp_dub.items(), key=lambda t: (-t[1], t[0][1])):
            if d in self.pos: self.by_grupo[g].append(d)

# ================================================================ candidatos e features

def candidatos(r, h, cls, minus=None, k_ator=10, k_dir=20, k_est=20, k_rec=40, k_grp=10, k_pop=10):
    """Top-K do ator, dos diretores e do estúdio (no histórico todo e nos anos recentes antes do papel),
    mais os populares da mídia e os gerais."""
    out = []
    def add(lst, k, ok=lambda d: True):
        out.extend([d for _, d in lst if d in cls.pos and ok(d)][:k])
    add(h.by_ator.get(r["ator"], []), k_ator, lambda d: cnt(h, minus, "ator_dub", (r["ator"], d)) > 0)
    for x in r["dirs"]:
        add(h.by_dir.get(x, []), k_dir); add(recentes(h, minus, "dir", x, r["ano"], cls), k_rec)
    if r["est"]:
        add(h.by_est.get(r["est"], []), k_est); add(recentes(h, minus, "est", r["est"], r["ano"], cls), k_rec)
    out += cls.by_grupo.get(r["grupo"], [])[:k_grp]
    out += cls.order[:k_pop]
    return list(dict.fromkeys(out))

FEATURES = ["ator_n", "ator_share", "ator_rank", "ator_total", "ator_visto",
            "dir_n", "dir_share", "dir_recente", "est_n", "est_share", "est_recente",
            "pop_log", "grp_share", "dec_share", "dub_share_principal", "papel_adicional",
            "anos_desde_ultimo", "papeis_5anos", "carreira_anos",
            "genero_igual", "genero_conhecido", "cidade_igual", "cidade_conhecida"]

def features(r, d, h, minus=None, ator_rank=None):
    """Vetor de features do par (papel r, candidato d). Recência só olha anos < r['ano']."""
    a, y = r["ator"], r["ano"]
    ator_n = cnt(h, minus, "ator_dub", (a, d)); ator_tot = cnt(h, minus, "ator", a)
    dir_n = sum(cnt(h, minus, "dir_dub", (x, d)) for x in r["dirs"]); dir_tot = sum(cnt(h, minus, "dir", x) for x in r["dirs"])
    est_n = cnt(h, minus, "est_dub", (r["est"], d)) if r["est"] else 0
    est_tot = cnt(h, minus, "est", r["est"]) if r["est"] else 0
    pop = cnt(h, minus, "pop", d)
    grp = cnt(h, minus, "grp_dub", (r["grupo"], d))
    dec = cnt(h, minus, "dec_dub", (r["ano"] // 10, d)) if r["ano"] else 0
    anos = h.anos.get(d, [])
    if y and anos:
        i = bisect.bisect_left(anos, y)  # só anos anteriores ao papel
        ultimo = anos[i - 1] if i else None
        desde = y - ultimo if ultimo else 99
        recentes = i - bisect.bisect_left(anos, y - 5)
        carreira = y - anos[0] if anos[0] < y else 0
    else:
        desde, recentes, carreira = 99, 0, 0
    _, dg, dc = h.dub_info.get(d, ("", "", ""))
    ag, oc = r["ator_genero"], r["obra_cidade"]
    return [ator_n, ator_n / ator_tot if ator_tot else 0.0, ator_rank if ator_rank is not None else 99,
            math.log1p(ator_tot), float(ator_tot > 0),
            dir_n, dir_n / dir_tot if dir_tot else 0.0, sum(janela(h, minus, "dir_anos", (x, d), y) for x in r["dirs"]),
            est_n, est_n / est_tot if est_tot else 0.0, janela(h, minus, "est_anos", (r["est"], d), y) if r["est"] else 0,
            math.log1p(max(pop, 0)), grp / pop if pop > 0 else 0.0, dec / pop if pop > 0 else 0.0,
            cnt(h, minus, "prin", d) / pop if pop > 0 else 0.0, float(r["adicional"]),
            desde, recentes, carreira,
            float(bool(ag and dg and ag == dg)), float(bool(ag and dg)),
            float(bool(oc and dc and oc == dc)), float(bool(oc and dc))]

def query_matrix(r, h, cls, minus=None):
    cands = candidatos(r, h, cls, minus)
    alist = [d for _, d in h.by_ator.get(r["ator"], []) if cnt(h, minus, "ator_dub", (r["ator"], d)) > 0]
    arank = {d: i + 1 for i, d in enumerate(alist)}
    X = [features(r, d, h, minus, arank.get(d)) for d in cands]
    return cands, X

# ================================================================ rankings e métricas

def rank_full(ordered, true, cls):
    """Posição (1 = primeiro) do verdadeiro numa lista ordenada completada pela popularidade."""
    if true not in cls.pos: return INF
    try: return ordered.index(true) + 1
    except ValueError: pass
    seen = set(ordered)
    before = sum(1 for d in ordered if cls.pos.get(d, INF) < cls.pos[true])
    return len(seen) + cls.pos[true] + 1 - before

def rank_popularidade(r, h, cls):
    return rank_full([], r["dub"], cls)

def rank_ator(r, h, cls):
    return rank_full([d for _, d in h.by_ator.get(r["ator"], []) if d in cls.pos], r["dub"], cls)

def rank_diretor(r, h, cls):
    tot = Counter()
    for x in r["dirs"]:
        for n, d in h.by_dir.get(x, []):
            if d in cls.pos: tot[d] += n
    return rank_full([d for d, _ in sorted(tot.items(), key=lambda t: (-t[1], t[0]))], r["dub"], cls)

def metricas(ranks):
    n = len(ranks)
    if not n: return {"n": 0, "top-1": 0.0, "top-5": 0.0, "MRR": 0.0}
    return {"n": n, "top-1": 100 * sum(k == 1 for k in ranks) / n, "top-5": 100 * sum(k <= 5 for k in ranks) / n,
            "MRR": sum(1 / k for k in ranks) / n}

# ================================================================ treino e avaliação

def _grupo_hist(rows, key):
    """Histórias por grupo (obra ou franquia), para descontar o próprio grupo das consultas de treino."""
    by = defaultdict(list)
    for r in rows: by[r[key]].append(r)
    cache = {}
    def get(g):
        if g not in cache: cache[g] = History(by[g])
        return cache[g]
    return get

def treinar_ranker(train, h, cls, loo_key, n_queries=20000, seed=0):
    from sklearn.ensemble import HistGradientBoostingClassifier
    rng = random.Random(seed)
    sample = rng.sample(train, min(n_queries, len(train)))
    minus_of = _grupo_hist(train, loo_key)
    X, y = [], []
    for r in sample:
        minus = minus_of(r[loo_key])
        if r["dub"] not in cls.pos: continue
        cands, Xq = query_matrix(r, h, cls, minus)
        if r["dub"] not in cands: continue
        X += Xq; y += [int(d == r["dub"]) for d in cands]
    model = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
                                           l2_regularization=1.0, random_state=seed)
    model.fit(X, y)
    return model, len(X)

def avaliar(test, h, cls, model, n_queries=8000, seed=1):
    """Ranks do verdadeiro para cada modelo numa amostra do teste, com os metadados para os recortes."""
    rng = random.Random(seed)
    sample = rng.sample(test, min(n_queries, len(test)))
    out = []
    for r in sample:
        cands, Xq = query_matrix(r, h, cls)
        scores = model.predict_proba(Xq)[:, 1] if Xq else []
        ordered = [d for _, d in sorted(zip(scores, cands), key=lambda t: (-t[0], cls.pos.get(t[1], INF)))]
        out.append({"r": r, "top3": ordered[:3], "em_candidatos": r["dub"] in cands,
                    "ranks": {"popularidade": rank_popularidade(r, h, cls), "ator": rank_ator(r, h, cls),
                              "diretor": rank_diretor(r, h, cls), "ranker": rank_full(ordered, r["dub"], cls)},
                    "ator_visto": h.ator[r["ator"]] > 0, "classe": r["dub"] in cls.pos})
    return out

def split_temporal(papeis, corte=2017):
    com_ano = [r for r in papeis if r["ano"]]
    return [r for r in com_ano if r["ano"] <= corte], [r for r in com_ano if r["ano"] > corte]

def folds_franquia(papeis, k=5, seed=0):
    """GroupKFold pela franquia (grupos embaralhados com semente fixa)."""
    grupos = sorted({r["franquia"] for r in papeis})
    random.Random(seed).shuffle(grupos)
    fold = {g: i % k for i, g in enumerate(grupos)}
    for i in range(k):
        yield [r for r in papeis if fold[r["franquia"]] != i], [r for r in papeis if fold[r["franquia"]] == i]

def rodar(train, test, loo_key, n_train=20000, n_test=8000, seed=0):
    h = History(train)
    cls = Classes(h)
    model, n_pairs = treinar_ranker(train, h, cls, loo_key, n_train, seed)
    res = avaliar(test, h, cls, model, n_test, seed + 1)
    cobertura = 100 * sum(r["dub"] in cls.pos for r in test) / max(len(test), 1)
    return {"res": res, "model": model, "h": h, "cls": cls, "n_pairs": n_pairs, "cobertura": cobertura,
            "n_classes": len(cls.order), "n_train": len(train), "n_test": len(test)}

MODELOS = ["popularidade", "ator", "diretor", "ranker"]

def tabela(res, filtro=lambda x: True):
    sub = [x for x in res if filtro(x)]
    return {m: metricas([x["ranks"][m] for x in sub]) for m in MODELOS}

def recortes(res):
    """Métricas por mídia, ator visto x não visto e elenco principal x vozes adicionais."""
    out = {}
    for g in ("live-action", "animação", "anime", "game"):
        out[f"mídia: {g}"] = tabela(res, lambda x, g=g: x["r"]["grupo"] == g)
    out["ator visto no treino"] = tabela(res, lambda x: x["ator_visto"])
    out["ator novo"] = tabela(res, lambda x: not x["ator_visto"])
    out["elenco principal"] = tabela(res, lambda x: not x["r"]["adicional"])
    out["vozes adicionais"] = tabela(res, lambda x: x["r"]["adicional"])
    return out

def importancia(run, test, n_queries=1500, seed=3):
    """Importância por permutação (queda de AUC nos pares papel × candidato de uma amostra do teste)."""
    from sklearn.inspection import permutation_importance
    rng = random.Random(seed)
    X, y = [], []
    for r in rng.sample(test, min(n_queries, len(test))):
        cands, Xq = query_matrix(r, run["h"], run["cls"])
        X += Xq; y += [int(d == r["dub"]) for d in cands]
    pi = permutation_importance(run["model"], X, y, scoring="roc_auc", n_repeats=3, random_state=seed)
    return sorted(zip(FEATURES, pi.importances_mean), key=lambda t: -t[1])

# ================================================================ execução completa

def exemplos(res, h, n=5):
    """Acertos e erros do ranker em papéis de atores famosos (ficha + muitos papéis no histórico)."""
    fam = sorted([x for x in res if x["r"]["ator"].startswith("p:") and h.ator[x["r"]["ator"]] >= 20],
                 key=lambda x: (-h.ator[x["r"]["ator"]], x["r"]["obra"], x["r"]["personagem"]))
    nome = lambda d: h.dub_info.get(d, (d.split(":", 1)[-1],))[0]
    def pick(cond):
        out, seen = [], set()
        for x in fam:
            if cond(x) and x["r"]["ator"] not in seen and x["r"]["dub_nome"] != x["r"]["ator_nome"]:  # sem "voz original mantida"
                seen.add(x["r"]["ator"])
                out.append({"obra": x["r"]["obra"], "ano": x["r"]["ano"], "personagem": x["r"]["personagem"],
                            "ator_original": x["r"]["ator_nome"], "dublador_real": x["r"]["dub_nome"],
                            "top3_ranker": [nome(d) for d in x["top3"]], "rank": x["ranks"]["ranker"]})
            if len(out) == n: break
        return out
    return pick(lambda x: x["ranks"]["ranker"] == 1), pick(lambda x: x["ranks"]["ranker"] > 5)

def _leve(res):
    keep = ("obra", "ano", "grupo", "adicional", "ator", "ator_nome", "dub_nome", "personagem")
    return [{**{k: x[k] for k in ("ranks", "em_candidatos", "ator_visto", "classe")},
             "r": {k: x["r"][k] for k in keep}} for x in res]

def main(out=ROOT / "data" / "processed" / "modelo_resultados.pkl", n_train=20000, n_test=8000, k=5,
         n_train_fold=12000, n_test_fold=2000):
    import pickle, time
    t0 = time.time()
    papeis = load_papeis()
    resultado = {"n_papeis": len(papeis)}
    tr, te = split_temporal(papeis)
    run = rodar(tr, te, "obra", n_train, n_test)
    hits, misses = exemplos(run["res"], run["h"])
    resultado["temporal"] = {"res": _leve(run["res"]), "cobertura": run["cobertura"], "n_classes": run["n_classes"],
                             "n_train": run["n_train"], "n_test": run["n_test"], "n_pairs": run["n_pairs"],
                             "importancia": importancia(run, te), "acertos": hits, "erros": misses}
    print(f"temporal ok ({time.time() - t0:.0f}s)", flush=True)
    folds = []
    for i, (tr, te) in enumerate(folds_franquia(papeis, k)):
        run = rodar(tr, te, "franquia", n_train_fold, n_test_fold, seed=10 + i)
        folds.append({"res": _leve(run["res"]), "cobertura": run["cobertura"], "n_classes": run["n_classes"],
                      "n_train": run["n_train"], "n_test": run["n_test"], "importancia": importancia(run, te, 600)})
        print(f"franquia {i + 1}/{k} ok ({time.time() - t0:.0f}s)", flush=True)
    resultado["franquia"] = folds
    with open(out, "wb") as fh: pickle.dump(resultado, fh)
    print(f"salvo em {out} ({time.time() - t0:.0f}s)")

# ================================================================ leitura dos resultados (notebook)

def carregar(path=ROOT / "data" / "processed" / "modelo_resultados.pkl"):
    import pickle
    with open(path, "rb") as fh: return pickle.load(fh)

def _res(resultado, validacao):
    if validacao == "temporal": return resultado["temporal"]["res"]
    return [x for f in resultado["franquia"] for x in f["res"]]

def metricas_validacoes(resultado):
    """[(validação, modelo, métricas)] nas duas validações (franquia = todas as dobras juntas)."""
    out = []
    for v in ("temporal", "franquia"):
        for mod, met in tabela(_res(resultado, v)).items(): out.append((v, mod, met))
    return out

def recortes_validacoes(resultado, metrica="top-5"):
    """{validação: {recorte: {modelo: valor}}} com o n de cada recorte."""
    out = {}
    for v in ("temporal", "franquia"):
        out[v] = {k: {**{mod: t[mod][metrica] for mod in MODELOS}, "n": t["ranker"]["n"]}
                  for k, t in recortes(_res(resultado, v)).items()}
    return out

def info_validacoes(resultado):
    t, f = resultado["temporal"], resultado["franquia"]
    rec = lambda res: 100 * sum(x["em_candidatos"] for x in res) / len(res)
    return [("temporal (treino ≤ 2017, teste ≥ 2018)", t["n_train"], t["n_test"], len(t["res"]), t["n_classes"], t["cobertura"], rec(t["res"])),
            (f"franquia ({len(f)} dobras)", sum(x["n_train"] for x in f) // len(f), sum(x["n_test"] for x in f) // len(f),
             sum(len(x["res"]) for x in f), sum(x["n_classes"] for x in f) // len(f), sum(x["cobertura"] for x in f) / len(f),
             rec(_res(resultado, "franquia")))]

def importancia_media(resultado):
    """Importância por permutação: temporal e a média das dobras de franquia."""
    acc = Counter()
    for f in resultado["franquia"]:
        for k, v in f["importancia"]: acc[k] += v / len(resultado["franquia"])
    return dict(resultado["temporal"]["importancia"]), dict(acc)

if __name__ == "__main__":
    main()
