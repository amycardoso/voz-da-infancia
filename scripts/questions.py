"""Perguntas sobre a rede da dublagem (notebooks/02_perguntas.ipynb).

Cada função devolve agregados (contagens, percentuais, curvas, top-N); nenhuma linha bruta sai daqui.
"""
import json, re
from collections import Counter, defaultdict
from pathlib import Path

from explore import ROOT, known, load, pct  # noqa: F401  (load é reexportado para o notebook)

GRUPO = {"filme": "live-action", "série": "live-action", "novela": "live-action",
         "série animada": "animação", "filme animado": "animação", "curta": "animação",
         "anime": "anime", "game": "game"}
DECADAS = (1980, 1990, 2000, 2010, 2020)

# ================================================================ 1. concentração

def lorenz(counts):
    """(x, y) da curva de Lorenz: fração acumulada de dubladores (do menos ao mais ativo) x de papéis."""
    c = sorted(counts)
    tot, acc, xs, ys = sum(c), 0, [0.0], [0.0]
    for i, v in enumerate(c, 1):
        acc += v; xs.append(i / len(c)); ys.append(acc / tot)
    return xs, ys

def gini(counts):
    c = sorted(counts)
    n, tot = len(c), sum(c)
    if not n or not tot: return 0.0
    return sum((2 * i - n - 1) * v for i, v in enumerate(c, 1)) / (n * tot)

def shares(counts):
    """% dos papéis feitos pelo top 1%, top 10% e pelos 50 dubladores mais ativos."""
    c, tot = sorted(counts, reverse=True), sum(counts)
    top = lambda k: pct(sum(c[:max(1, k)]), tot)
    return {"top 1%": top(len(c) // 100), "top 10%": top(len(c) // 10), "top 50": top(50)}

def roles(rows):
    return list(Counter(r["dublador_id"] for r in known(rows)).values())

def concentracao(rows):
    """Tabela geral, por década do lançamento e por grupo de mídia: dubladores, papéis, Gini, top 10%."""
    out = [("todos", roles(rows))]
    out += [(f"{d}s", roles([r for r in rows if r["ano"] and d <= r["ano"] < d + 10])) for d in DECADAS]
    out += [(g, roles([r for r in rows if GRUPO.get(r["midia"]) == g])) for g in ("live-action", "animação", "anime", "game")]
    return [{"recorte": k, "dubladores": len(c), "papéis": sum(c), "gini": gini(c), **shares(c)} for k, c in out]

# ================================================================ 2. mapa da escalação

def _vaga(nome):
    from clean import UNKNOWN
    return not nome or bool(UNKNOWN.match(nome))

def cidades(raw=ROOT / "data" / "raw"):
    """{ficha: 'RJ' | 'SP' | 'RJ+SP'} pelas categorias de cidade das fichas."""
    out = {}
    for f in sorted((raw / "pages").glob("part-*.jsonl")):
        for line in f.open():
            d = json.loads(line)
            cats = set(d.get("categories", []))
            rj = bool({"Dubladores do Rio de Janeiro", "Diretores de Dublagem do Rio de Janeiro"} & cats)
            sp = bool({"Dubladores de São Paulo", "Diretores de Dublagem de São Paulo"} & cats)
            if rj or sp: out[d["title"]] = "RJ+SP" if rj and sp else "RJ" if rj else "SP"
    return out

def grafo_escalacao(rows, min_peso=2):
    """Grafo bipartido dublador–diretor; peso = obras em que trabalharam juntos.
    Só usa linhas com diretor ligado à versão (estudio_status unico/casado)."""
    import networkx as nx
    peso = Counter()
    for r in known(rows):
        if r["estudio_status"] not in ("unico", "casado") or not r["diretor"]: continue
        for d in {x for x in r["diretor"].split(" ; ") if not _vaga(x)}:
            peso[(r["dublador"], d, r["obra"])] = 1
    w = Counter((dub, d) for dub, d, _ in peso)
    g = nx.Graph()
    for (dub, d), k in sorted(w.items()):  # ordem fixa: o Louvain depende da ordem de inserção
        if k >= min_peso:
            g.add_node("dub:" + dub, tipo="dublador", nome=dub)
            g.add_node("dir:" + d, tipo="diretor", nome=d)
            g.add_edge("dub:" + dub, "dir:" + d, weight=k)
    return g

def comunidades(g, seed=42):
    """Louvain (networkx) -> lista de conjuntos de nós, da maior para a menor."""
    import networkx as nx
    com = nx.community.louvain_communities(g, weight="weight", seed=seed)
    return sorted(com, key=len, reverse=True)

def comunidades_por_cidade(g, com, cid, top=10):
    """Para as maiores comunidades: tamanho e % de pessoas com categoria RJ, SP, ambas ou sem."""
    res = []
    for i, c in enumerate(com[:top]):
        k = Counter(cid.get(g.nodes[n]["nome"], "sem") for n in c)
        com_cidade = k["RJ"] + k["SP"] + k["RJ+SP"]
        maior = max(("RJ", "SP"), key=lambda x: k[x])
        res.append({"comunidade": i + 1, "pessoas": len(c), "diretores": sum(g.nodes[n]["tipo"] == "diretor" for n in c),
                    "RJ": k["RJ"], "SP": k["SP"], "RJ+SP": k["RJ+SP"], "sem": k["sem"],
                    "cidade dominante": maior, "pureza": pct(k[maior], com_cidade)})
    return res

def pureza_geral(g, com, cid):
    """% das pessoas com uma só cidade que estão numa comunidade cuja maioria é da mesma cidade."""
    ok = tot = 0
    for c in com:
        k = Counter(cid.get(g.nodes[n]["nome"]) for n in c)
        maior = "RJ" if k["RJ"] >= k["SP"] else "SP"
        tot += k["RJ"] + k["SP"]; ok += k[maior]
    return pct(ok, tot)

def diretores_fieis(rows, min_obras=30, min_repet=5, top=15):
    """% dos papéis de cada diretor dados a dubladores com quem ele trabalhou em >= min_repet obras."""
    obras_par, papeis_dir, obras_dir = defaultdict(set), defaultdict(list), defaultdict(set)
    for r in known(rows):
        if r["estudio_status"] not in ("unico", "casado") or not r["diretor"]: continue
        for d in {x for x in r["diretor"].split(" ; ") if not _vaga(x)}:
            obras_par[(d, r["dublador_id"])].add(r["obra"]); papeis_dir[d].append(r["dublador_id"]); obras_dir[d].add(r["obra"])
    res = []
    for d, papeis in papeis_dir.items():
        if len(obras_dir[d]) < min_obras: continue
        fixos = {dub for dub in set(papeis) if len(obras_par[(d, dub)]) >= min_repet}
        res.append((d, len(obras_dir[d]), len(fixos), pct(sum(p in fixos for p in papeis), len(papeis))))
    return sorted(res, key=lambda x: -x[3])[:top], len(res), sorted(x[3] for x in res)

def subgrafo_desenho(g, com, n_com=6, por_com=25):
    """Os nós de maior grau ponderado das maiores comunidades, para desenhar."""
    keep = []
    for c in com[:n_com]:
        keep += sorted(c, key=lambda n: -g.degree(n, weight="weight"))[:por_com]
    return g.subgraph(keep).copy()

# ================================================================ 3. fidelidade de voz

def fidelidade(rows, min_obras=3):
    """Por grupo de mídia: para cada ator com >= min_obras obras no grupo, % das obras em que aparece
    o seu dublador mais frequente. Devolve {grupo: lista de fidelidades}."""
    obras = defaultdict(lambda: defaultdict(set))  # (grupo, ator) -> obra -> dubladores
    for r in known(rows):
        g = GRUPO.get(r["midia"])
        if g and r["ator_original_id"]: obras[(g, r["ator_original_id"])][r["obra"]].add(r["dublador_id"])
    out = defaultdict(list)
    for (g, _), por_obra in obras.items():
        if len(por_obra) < min_obras: continue
        top, _ = Counter(d for ds in por_obra.values() for d in ds).most_common(1)[0]
        out[g].append(pct(sum(top in ds for ds in por_obra.values()), len(por_obra)))
    return dict(out)

def fidelidade_top(rows, grupo="live-action", n=12):
    """Os atores com mais obras no grupo: (ator, obras, dublador mais frequente, % das obras com ele)."""
    obras = defaultdict(lambda: defaultdict(set)); nome = {}
    for r in known(rows):
        if GRUPO.get(r["midia"]) == grupo and r["ator_original_id"].startswith("p:"):
            obras[r["ator_original_id"]][r["obra"]].add(r["dublador"]); nome[r["ator_original_id"]] = r["ator_original"]
    res = []
    for a in sorted(obras, key=lambda a: -len(obras[a]))[:n]:
        top, _ = Counter(d for ds in obras[a].values() for d in ds).most_common(1)[0]
        res.append((nome[a], len(obras[a]), top, pct(sum(top in ds for ds in obras[a].values()), len(obras[a]))))
    return res

def resumo_fidelidade(fid):
    med = lambda v: sorted(v)[len(v) // 2] if v else 0
    return [{"grupo": g, "atores": len(v), "mediana": med(v), "≥ 80%": pct(sum(x >= 80 for x in v), len(v)),
             "100%": pct(sum(x == 100 for x in v), len(v))} for g, v in fid.items()]

TEMPORADA = re.compile(r"(?i)temporada|\btemp\b|parte|season|\bt\d")

def redublagens(rows):
    """Mesmo personagem e ator original em duas versões da mesma obra: % em que o dublador muda.
    Separa versões de temporada (recast) de dublagens diferentes (redublagem, outro estúdio)."""
    vs = defaultdict(lambda: defaultdict(set))
    for r in known(rows):
        if r["ator_original_id"]:
            vs[(r["obra"], r["personagem"], r["ator_original_id"])][r["versao"]].add(r["dublador_id"])
    res = {"temporadas": [0, 0], "dublagens diferentes": [0, 0]}
    for por_versao in vs.values():
        if len(por_versao) < 2: continue
        tipo = "temporadas" if all(TEMPORADA.search(v) for v in por_versao) else "dublagens diferentes"
        mudou = len({frozenset(d) for d in por_versao.values()}) > 1
        res[tipo][0] += 1; res[tipo][1] += mudou
    return {k: {"personagens": n, "% com dublador diferente": pct(m, n)} for k, (n, m) in res.items()}

# ================================================================ 4. gênero

ADICIONAL = re.compile(r"(?i)adiciona|outras vozes|participa|epis[oó]dic|secund|recorrent|apoio|figura|convidad|extra")

def pct_dubladoras(rows, chave):
    """{valor da chave: (% de papéis feitos por dubladoras, papéis com gênero)}."""
    tot, fem = Counter(), Counter()
    for r in known(rows):
        if r["dublador_genero"] in ("F", "M"):
            k = chave(r)
            if k is None: continue
            tot[k] += 1; fem[k] += r["dublador_genero"] == "F"
    return {k: (pct(fem[k], tot[k]), tot[k]) for k in tot}

def por_midia_decada(rows):
    """{grupo: {década: % dubladoras}} (só células com >= 300 papéis)."""
    d = pct_dubladoras(rows, lambda r: (GRUPO.get(r["midia"]), r["ano"] // 10 * 10) if r["ano"] and GRUPO.get(r["midia"]) and 1970 <= r["ano"] < 2030 else None)
    out = defaultdict(dict)
    for (g, dec), (p, n) in d.items():
        if n >= 300: out[g][dec] = p
    return {g: dict(sorted(v.items())) for g, v in out.items()}

def genero_cruzado(rows):
    """Por grupo de mídia: % dos papéis de atores originais homens dublados por mulheres, e o inverso."""
    out = {}
    for g in ("live-action", "animação", "anime", "game"):
        sub = [r for r in known(rows) if GRUPO.get(r["midia"]) == g and r["dublador_genero"] in ("F", "M")]
        h = [r for r in sub if r["ator_original_genero"] == "M"]
        m = [r for r in sub if r["ator_original_genero"] == "F"]
        out[g] = {"atores homens": len(h), "% dublados por mulheres": pct(sum(r["dublador_genero"] == "F" for r in h), len(h)),
                  "atrizes": len(m), "% dubladas por homens": pct(sum(r["dublador_genero"] == "M" for r in m), len(m))}
    return out

def top_cruzados(rows, n=8):
    """Dubladoras com mais papéis de atores originais homens no anime (o caso Naruto)."""
    c = Counter(r["dublador"] for r in known(rows)
                if r["midia"] == "anime" and r["ator_original_genero"] == "M" and r["dublador_genero"] == "F")
    return c.most_common(n)

def seiyuu(rows, nome):
    """Para uma seiyuu: papéis no anime por gênero do dublador brasileiro, e os dubladores mais frequentes."""
    sub = [r for r in known(rows) if r["midia"] == "anime" and r["ator_original"] == nome]
    return Counter(r["dublador_genero"] or "?" for r in sub), Counter(r["dublador"] for r in sub).most_common(5)

def principal_vs_adicional(rows):
    """% dubladoras no elenco principal x nas vozes adicionais, pelo nome da seção (versao)."""
    return pct_dubladoras(rows, lambda r: "vozes adicionais / participações" if ADICIONAL.search(r["versao"]) else "elenco principal")
