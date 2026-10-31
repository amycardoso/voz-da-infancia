import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from clean import entries, name_key, normalize_name, split_cell, studio_for  # noqa: E402

def names(wt):
    return [(x["nome"], x["qualificador"], x["desconhecido"]) for x in split_cell(wt)]

# ---------------------------------------------------------------- células compostas

def test_celula_simples_com_link():
    assert split_cell("[[Wendel Bezerra]]") == [
        {"nome": "Wendel Bezerra", "link": "Wendel Bezerra", "qualificador": "", "desconhecido": False}]

def test_link_com_rotulo_guarda_o_alvo():
    (x,) = split_cell("[[Leonardo Rabelo|Léo Rabelo]]")
    assert (x["nome"], x["link"]) == ("Léo Rabelo", "Leonardo Rabelo")

def test_hr_e_qualificador_em_small():
    wt = "[[Garcia Júnior]]<hr>[[Sandro Christopher]]<br><small>(canções)</small>"
    assert names(wt) == [("Garcia Júnior", "", False), ("Sandro Christopher", "canções", False)]

def test_ponto_e_virgula_e_parenteses():
    assert names("Fulano ; Beltrano (canções)") == [("Fulano", "", False), ("Beltrano", "canções", False)]

def test_qualificador_criança():
    assert names("[[João Vitor Mafra]] (criança)") == [("João Vitor Mafra", "criança", False)]

def test_predefinicao_pequena_vira_qualificador():
    assert names("[[Úrsula Bezerra]] {{Pequena2|(1ª voz)}}") == [("Úrsula Bezerra", "1ª voz", False)]

def test_barra_separa_dubladores():
    assert names("[[A Um]] / [[B Dois]]") == [("A Um", "", False), ("B Dois", "", False)]

def test_dois_links_com_e():
    assert names("[[Gilmara Sanchez]] e [[Rosangela Mello]]") == [
        ("Gilmara Sanchez", "", False), ("Rosangela Mello", "", False)]

def test_e_dentro_do_nome_nao_divide():
    assert names("[[Maria e Silva]]") == [("Maria e Silva", "", False)]

def test_desconhecido_fica_marcado():
    assert names("?") == [("", "", True)]
    assert names("N/A") == [("", "", True)]
    assert names("? (canções)") == [("", "canções", True)]
    for v in ("Por Confirmar", "Por identificar", "A identificar", "Ainda não identificado", "Sem Diálogos", "N/D"):
        assert names(v) == [("", "", True)], v

def test_ponto_e_virgula_dentro_de_parenteses_nao_divide():
    assert names("[[Fulana Tal]] (criança; 1ª temp.)") == [("Fulana Tal", "criança; 1ª temp.", False)]

def test_pedaco_so_de_episodio_vira_qualificador():
    assert names("[[Fulano]] ; 1x06") == [("Fulano", "1x06", False)]
    assert names("[[Fulano]]<br>2ª-4ª Temp") == [("Fulano", "2ª-4ª Temp", False)]

def test_mantido_no_original_e_desconhecido():
    for v in ("Mantido no original", "Mantido no Original", "¿?", "Sem dialógos"):
        assert names(v)[0][2], v

def test_dublador_desconhecido_numerado_e_uma_pessoa():
    assert names("[[Dublador Desconhecido nº 9]]") == [("Dublador Desconhecido nº 9", "", False)]

def test_ref_e_imagem_somem():
    assert names("[[Arquivo:x.png|80px]][[Ana Lúcia Menezes]]<ref>fonte</ref>") == [("Ana Lúcia Menezes", "", False)]

# ---------------------------------------------------------------- nomes

def test_normaliza_espacos_aspas_e_marcacao():
    assert normalize_name("  Leonardo  ''Léo''   Rabelo ") == "Leonardo Léo Rabelo"
    assert normalize_name("Leonardo “Léo” Rabelo") == 'Leonardo "Léo" Rabelo'
    assert normalize_name("[[Isaac Bardavid]]") == "Isaac Bardavid"
    assert normalize_name("Isaac_Bardavid ;") == "Isaac Bardavid"

def test_chave_ignora_acento_e_caixa():
    assert name_key("Úrsula Bezerra") == name_key("ursula  bezerra") == "ursula bezerra"
    assert name_key("Élida L'Astorina") == name_key("Elida L’Astorina")

# ---------------------------------------------------------------- estúdio por versão

def test_estudio_por_temporada():
    wt = ("|estúdio_de_dublagem=[[Clone]] <small>(1ª-3ª Temporadas)</small><br>"
          "[[Dubbing & Mix]] <small>(4ª Temporada em diante)</small>\n|ano=2000")
    st = entries(wt, "estúdio_de_dublagem")
    assert studio_for("2ª Temporada", st, [])[0::2] == ("Clone", "casado")
    assert studio_for("5ª Temporada", st, [])[0::2] == ("Dubbing & Mix", "casado")
    assert studio_for("Elenco", st, [])[2] == "ambiguo"

def test_estudio_por_etapa_e_diretores():
    wt = ("|estúdio_de_dublagem_1=[[Point.360]]\n|direção_de_dublagem_1=[[Mabel Cezar]]<br>[[Rayani Immediato]]\n"
          "|estúdio_de_dublagem_2=[[IDF]]<br><small>(2ª Temporada)</small>\n|direção_de_dublagem_2=[[Léo Caldas]]\n}}")
    st, di = entries(wt, "estúdio_de_dublagem"), entries(wt, "direção_de_dublagem")
    assert studio_for("Elenco — 2ª Temporada", st, di) == ("IDF", "Léo Caldas", "casado")

def test_estudio_pelo_nome_na_coluna():
    st = entries("|estúdio_de_dublagem=[[Álamo]]<hr>[[VTI]]\n", "estúdio_de_dublagem")
    assert studio_for("Elenco — VTI", st, [])[0::2] == ("VTI", "casado")
