"""Agregados para a análise exploratória (notebooks/01_exploracao.ipynb) e o estilo dos gráficos.

Tudo aqui devolve contagens, percentuais ou top-N: nenhuma linha bruta sai deste módulo.
"""
import csv, json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELENCO = ROOT / "data" / "processed" / "elenco_limpo.csv"

# paleta de referência (skill dataviz): série única em azul, 2ª categoria em laranja, cinza para "sem dado"
BLUE, ORANGE, GRAY = "#2a78d6", "#eb6834", "#b8b7b0"
INK, INK2, SURFACE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e6e5e0"

def load(path=ELENCO):
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["dublador_desconhecido"] = r["dublador_desconhecido"] == "True"
        r["dublador_ficha"] = r["dublador_ficha"] == "True"
        r["ator_original_ficha"] = r["ator_original_ficha"] == "True"
        r["ano"] = int(r["ano"]) if r["ano"] else None
    return rows

def known(rows):
    return [r for r in rows if not r["dublador_desconhecido"]]

def pct(a, b):
    return 100 * a / b if b else 0.0

# ---------------------------------------------------------------- tamanho e cobertura

def resumo(rows):
    k = known(rows)
    return {
        "linhas (personagem → dublador)": len(rows),
        "obras": len({r["obra"] for r in rows}),
        "franquias": len({r["franquia"] for r in rows}),
        "dubladores (ids)": len({r["dublador_id"] for r in k}),
        "atores originais (ids)": len({r["ator_original_id"] for r in rows if r["ator_original_id"]}),
        "estúdios": len({r["estudio"] for r in rows if r["estudio_status"] in ("unico", "casado") and r["estudio"]}),
        "anos": f'{min(r["ano"] for r in rows if r["ano"])}–{max(r["ano"] for r in rows if r["ano"])}',
    }

def por_midia(rows):
    """[(mídia, obras, linhas)] do maior para o menor número de obras."""
    obras, linhas = defaultdict(set), Counter()
    for r in rows:
        obras[r["midia"]].add(r["obra"]); linhas[r["midia"]] += 1
    return sorted(((m, len(o), linhas[m]) for m, o in obras.items()), key=lambda x: -x[1])

def por_decada(rows, desde=1930, ate=2026):
    """{década: obras}, pelo primeiro ano da obra (sem lançamentos anunciados depois de `ate`)."""
    ano = {}
    for r in rows:
        if r["ano"]: ano.setdefault(r["obra"], r["ano"])
    c = Counter(a // 10 * 10 for a in ano.values() if desde <= a <= ate)
    return dict(sorted(c.items()))

def midia_por_decada(rows, midias, desde=1950):
    """{mídia: {década: obras}} para as mídias pedidas."""
    first = {}
    for r in rows:
        if r["ano"] and r["midia"] in midias: first.setdefault((r["midia"], r["obra"]), r["ano"])
    out = {m: Counter() for m in midias}
    for (m, _), a in first.items():
        if a >= desde: out[m][a // 10 * 10] += 1
    return out

# ---------------------------------------------------------------- pessoas

def top_dubladores(rows, n=20):
    """[(dublador, papéis, obras)] pelos papéis (personagem distinto por obra e versão)."""
    papeis, obras, nome = Counter(), defaultdict(set), {}
    for r in known(rows):
        papeis[r["dublador_id"]] += 1; obras[r["dublador_id"]].add(r["obra"]); nome[r["dublador_id"]] = r["dublador"]
    return [(nome[i], c, len(obras[i])) for i, c in papeis.most_common(n)]

def top_atores(rows, n=20):
    """[(ator original, obras, dubladores distintos)] pelo número de obras."""
    obras, dubs, nome = defaultdict(set), defaultdict(set), {}
    for r in known(rows):
        i = r["ator_original_id"]
        if not i or r["midia"] in ("documentário", "reality"): continue
        obras[i].add(r["obra"]); dubs[i].add(r["dublador_id"]); nome[i] = r["ator_original"]
    top = sorted(obras, key=lambda i: -len(obras[i]))[:n]
    return [(nome[i], len(obras[i]), len(dubs[i])) for i in top]

def papeis_por_dublador(rows):
    """Lista ordenada (desc) de papéis por dublador — a cauda longa."""
    return sorted(Counter(r["dublador_id"] for r in known(rows)).values(), reverse=True)

def concentracao(contagens, fracoes=(0.01, 0.1, 0.5)):
    """{fração dos dubladores do topo: % dos papéis que eles fazem}."""
    tot = sum(contagens)
    return {f: pct(sum(contagens[:max(1, int(len(contagens) * f))]), tot) for f in fracoes}

# ---------------------------------------------------------------- estúdios e diretores

def _vaga(nome):
    from clean import UNKNOWN
    return not nome or bool(UNKNOWN.match(nome))

def cidades(nomes, raw=ROOT / "data" / "raw"):
    """{cidade: quantos dos nomes têm a categoria 'Dubladores do Rio de Janeiro' / 'de São Paulo'}."""
    want, found = set(nomes), {}
    for f in sorted((raw / "pages").glob("part-*.jsonl")):
        for line in f.open():
            d = json.loads(line)
            if d["title"] in want: found[d["title"]] = set(d.get("categories", []))
    return {"Rio de Janeiro": sum("Dubladores do Rio de Janeiro" in c for c in found.values()),
            "São Paulo": sum("Dubladores de São Paulo" in c for c in found.values())}

def top_estudios(rows, n=15):
    """[(estúdio, obras)] só com estúdio ligado à versão (unico/casado)."""
    obras = defaultdict(set)
    for r in rows:
        if r["estudio_status"] in ("unico", "casado") and r["estudio"]:
            for e in r["estudio"].split(" ; "):
                if not _vaga(e): obras[e].add(r["obra"])
    return sorted(((e, len(o)) for e, o in obras.items()), key=lambda x: -x[1])[:n]

def top_diretores(rows, n=15):
    obras = defaultdict(set)
    for r in rows:
        if r["estudio_status"] in ("unico", "casado") and r["diretor"]:
            for d in r["diretor"].split(" ; "):
                if not _vaga(d): obras[d].add(r["obra"])
    return sorted(((d, len(o)) for d, o in obras.items()), key=lambda x: -x[1])[:n]

def status_estudio(rows):
    c = Counter(r["estudio_status"] for r in rows)
    return {k: pct(c[k], len(rows)) for k in ("unico", "casado", "ambiguo", "vazio")}

# ---------------------------------------------------------------- gênero

def genero(rows):
    """% de linhas com gênero do ator original (F/M/sem) e do dublador, por pessoa distinta também."""
    com_ator = [r for r in rows if r["ator_original_id"]]
    lin = Counter(r["ator_original_genero"] or "sem" for r in com_ator)
    pessoas = {r["ator_original_id"]: r["ator_original_genero"] or "sem" for r in com_ator}
    pes = Counter(pessoas.values())
    k = known(rows)
    dub = Counter(r["dublador_genero"] or "sem" for r in k)
    return {
        "ator original — linhas": {g: pct(lin[g], len(com_ator)) for g in ("F", "M", "sem")},
        "ator original — pessoas": {g: pct(pes[g], len(pessoas)) for g in ("F", "M", "sem")},
        "dublador — linhas": {g: pct(dub[g], len(k)) for g in ("F", "M", "sem")},
    }

# ---------------------------------------------------------------- lacunas

def lacunas(rows):
    """% das linhas afetadas por cada lacuna conhecida."""
    n = len(rows)
    return {
        "dublador desconhecido (?, N/A)": pct(sum(r["dublador_desconhecido"] for r in rows), n),
        "dublador sem ficha": pct(sum(not r["dublador_desconhecido"] and not r["dublador_ficha"] for r in rows), n),
        "sem ator original": pct(sum(not r["ator_original_id"] for r in rows), n),
        "ator original sem ficha": pct(sum(bool(r["ator_original_id"]) and not r["ator_original_ficha"] for r in rows), n),
        "ator original sem gênero": pct(sum(bool(r["ator_original_id"]) and not r["ator_original_genero"] for r in rows), n),
        "dublador sem gênero": pct(sum(not r["dublador_desconhecido"] and not r["dublador_genero"] for r in rows), n),
        "estúdio ambíguo (várias dublagens)": pct(sum(r["estudio_status"] == "ambiguo" for r in rows), n),
        "estúdio não informado": pct(sum(r["estudio_status"] == "vazio" for r in rows), n),
        "sem ano": pct(sum(not r["ano"] for r in rows), n),
        "mídia 'outro'": pct(sum(r["midia"] == "outro" for r in rows), n),
    }

# ---------------------------------------------------------------- estilo

def style():
    import matplotlib as mpl
    mpl.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "figure.dpi": 110, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.titlepad": 12, "axes.labelcolor": INK2,
        "axes.edgecolor": GRID, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "xtick.color": INK2, "ytick.color": INK, "text.color": INK,
        "legend.frameon": False, "axes.axisbelow": True,
    })

def barh(ax, labels, values, title, xlabel, color=BLUE):
    """Barras horizontais finas, maior em cima, grade só no eixo do valor."""
    y = range(len(labels))[::-1]
    ax.barh(list(y), values, height=0.62, color=color)
    ax.set_yticks(list(y), labels)
    ax.set_title(title); ax.set_xlabel(xlabel)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    return ax
