import csv, gzip, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gender import NameGender, first_name, from_page  # noqa: E402

def page(wt, cats=()):
    return {"wikitext": wt, "categories": list(cats)}

def test_frase_de_abertura_e_ocupacao():
    assert from_page(page("{{Infobox de dublador|ocupação=Dubladora}}\n'''Fulana''' é uma dubladora brasileira.")) == "F"
    assert from_page(page("'''Fulano de Tal''' é um ator e dublador brasileiro.")) == "M"

def test_categoria_e_campo_sexo():
    assert from_page(page("", ["Atrizes"])) == "F"
    assert from_page(page("|sexo=Masculino\n")) == "M"

def test_sinais_contraditorios_ficam_vazios():
    assert from_page(page("|sexo=Feminino\n'''X''' é um dublador.")) == ""
    assert from_page(page("'''X''' é uma das vozes mais conhecidas.")) == ""

def test_primeiro_nome():
    assert first_name("Úrsula Bezerra") == "URSULA"
    assert first_name("Dr. Fulano") == "FULANO"

def test_limiar_de_confianca(tmp_path):
    f = tmp_path / "nomes.csv.gz"
    with gzip.open(f, "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["alternative_names", "classification", "first_name", "frequency_female", "frequency_male",
                    "frequency_total", "frequency_group", "group_name", "ratio"])
        w.writerow(["URSSULA", "F", "URSULA", "100", "", "100", "100", "URSULA", "1.0"])
        w.writerow(["", "M", "ARIEL", "40", "60", "100", "100", "ARIEL", "0.6"])
    ng = NameGender(f, limiar=0.9)
    assert ng.guess("Úrsula Bezerra") == "F"
    assert ng.guess("Urssula X") == "F"          # grafia alternativa herda do grupo
    assert ng.guess("Ariel Silva") == ""         # razão 0,6 < 0,9: fica desconhecido
    assert ng.guess("Fulano Inexistente") == ""
    assert ng.guess("Malta Júnior") == "M"       # sufixo masculino
