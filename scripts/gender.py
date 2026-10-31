"""Gênero de pessoas: primeiro pela ficha da Dublapédia, depois pelo primeiro nome (Censo 2010).

Ficha: categorias Atores/Atrizes, campo `sexo`, artigo da frase de abertura ("'''X''' é uma dubladora")
e forma da ocupação no infobox ("Dubladora", "Ator"). Sinais contraditórios -> sem gênero.

Nome: dataset "Gênero dos Nomes" do Brasil.io (https://brasil.io/dataset/genero-nomes/), feito a partir
do Censo 2010 do IBGE, licença CC BY-SA 4.0. Só classifica quando a razão do gênero dominante é >= LIMIAR.
"""
import csv, gzip, re, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOMES = ROOT / "data" / "external" / "nomes.csv.gz"
NOMES_URL = "https://data.brasil.io/dataset/genero-nomes/nomes.csv.gz"
LIMIAR = 0.9

FEM = r"dubladora|atriz|locutora|cantora|diretora|apresentadora|tradutora|radialista feminina|seiyuu feminina"
MASC = r"dublador|ator|locutor|cantor|diretor|apresentador|tradutor"
INTRO = re.compile(r"'''[^'\n]+'''[^.\n]{0,160}?\b(?:é|foi|era)\s+(um|uma)\s+(\w+)", re.I)

def from_page(d):
    """'F', 'M' ou '' a partir da própria ficha."""
    wt, cats = d.get("wikitext") or "", set(d.get("categories", []))
    votes = []
    if "Atrizes" in cats: votes.append("F")
    if "Atores" in cats: votes.append("M")
    m = re.search(r"\|\s*sexo\s*=\s*([A-Za-zç]+)", wt)
    if m and m.group(1).lower().startswith("fem"): votes.append("F")
    if m and m.group(1).lower().startswith("mas"): votes.append("M")
    m = INTRO.search(wt[:3000])
    if m and re.match(rf"(?i)({FEM}|{MASC})", m.group(2)):
        votes.append("F" if m.group(1).lower() == "uma" else "M")
    m = re.search(r"\|\s*ocupação\s*=([^|\n]*)", wt)
    if m:
        oc = m.group(1).lower()
        f, ms = bool(re.search(FEM, oc)), bool(re.search(rf"\b({MASC})\b", oc))
        if f != ms: votes.append("F" if f else "M")
    return votes[0] if votes and len(set(votes)) == 1 else ""

def first_name(nome):
    """'Úrsula Bezerra' -> 'URSULA'; ignora prefixos como 'Dr.', 'MC'."""
    s = unicodedata.normalize("NFKD", nome or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    toks = [t for t in re.split(r"[^A-Z]+", s) if t and t not in {"DR", "DRA", "MC", "DJ", "SR", "SRA", "PE", "PADRE", "TIA", "TIO"}]
    return toks[0] if toks else ""

class NameGender:
    """first_name -> (classificação, razão) a partir do Brasil.io; nomes alternativos herdam do grupo."""
    def __init__(self, path=NOMES, limiar=LIMIAR):
        self.limiar, self.table = limiar, {}
        if not Path(path).exists():
            return
        with gzip.open(path, "rt", newline="") as fh:
            for r in csv.DictReader(fh):
                ratio = float(r["ratio"] or 0)
                self.table[r["first_name"]] = (r["classification"], ratio)
                for alt in (r["alternative_names"] or "").split("|"):
                    if alt: self.table.setdefault(alt, (r["classification"], ratio))

    def __bool__(self):
        return bool(self.table)

    def guess(self, nome):
        """'F', 'M' ou '' (nome ausente ou razão abaixo do limiar). "Júnior", "Filho", "Neto" no fim -> M."""
        if re.search(r"(?i)\b(j[uú]nior|filho|neto|sobrinho)$", (nome or "").strip()): return "M"
        c, ratio = self.table.get(first_name(nome), ("", 0.0))
        return c if c in ("F", "M") and ratio >= self.limiar else ""
