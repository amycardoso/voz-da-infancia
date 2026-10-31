import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import model as m  # noqa: E402

def papel(obra, ano, ator, dub, franquia=None, est="Estúdio A", dirs=("Dir X",), adicional=False):
    return {"obra": obra, "franquia": franquia or obra, "versao": "Elenco", "personagem": "P", "ano": ano,
            "midia": "filme", "grupo": "live-action", "ator": ator, "ator_nome": ator, "ator_genero": "M",
            "dub": dub, "dub_nome": dub, "dub_genero": "M", "dub_cidade": "RJ", "obra_cidade": "RJ",
            "dirs": list(dirs), "est": est, "adicional": adicional}

PAPEIS = [papel("F1", 2010, "a", "d1"), papel("F2", 2012, "a", "d1"), papel("F3", 2015, "a", "d2"),
          papel("F4", 2016, "b", "d2"), papel("F5", 2019, "a", "d3"), papel("F6", 2021, "a", "d3")]

def feat(r, d, h, minus=None):
    return dict(zip(m.FEATURES, m.features(r, d, h, minus)))

def test_split_temporal_separa_por_ano():
    tr, te = m.split_temporal(PAPEIS, 2017)
    assert max(r["ano"] for r in tr) <= 2017 < min(r["ano"] for r in te)

def test_historico_do_teste_nao_ve_o_futuro():
    tr, te = m.split_temporal(PAPEIS, 2017)
    h = m.History(tr)
    f = feat(te[-1], "d3", h)  # d3 só aparece no teste
    assert f["ator_n"] == 0 and f["pop_log"] == 0 and f["papeis_5anos"] == 0
    assert h.ator["a"] == 3  # só os papéis até 2017

def test_recencia_so_olha_o_passado_do_papel():
    h = m.History(PAPEIS)
    f = feat(papel("Q", 2013, "a", "?"), "d2", h)
    assert f["papeis_5anos"] == 0 and f["anos_desde_ultimo"] == 99  # d2 só aparece em 2015 e 2016
    assert f["est_recente"] == 0 and f["dir_recente"] == 0

def test_janela_no_teste_temporal_usa_o_fim_do_historico():
    tr, _ = m.split_temporal(PAPEIS, 2017)
    h = m.History(tr)
    # papel de 2030: a janela vira [2012, 2018) e não [2024, 2030), que estaria vazia
    assert m.janela(h, None, "est_anos", ("Estúdio A", "d2"), 2030) == 2

def test_consulta_de_treino_desconta_o_proprio_grupo():
    tr = [papel("O1", 2010, "a", "d1", franquia="X"), papel("O2", 2011, "a", "d1", franquia="X"),
          papel("O3", 2012, "a", "d2", franquia="Y")]
    h = m.History(tr)
    minus = m.History([r for r in tr if r["franquia"] == "X"])
    f = feat(tr[0], "d1", h, minus)
    assert f["ator_n"] == 0  # os dois papéis de "a" com d1 são da própria franquia X
    assert feat(tr[0], "d2", h, minus)["ator_n"] == 1

def test_rank_completa_pela_popularidade():
    h = m.History(PAPEIS * 5)
    cls = m.Classes(h, min_papeis=5)
    assert m.rank_full(["d3"], "d3", cls) == 1
    assert m.rank_full([], cls.order[1], cls) == 2
    assert m.rank_full([], "nao-existe", cls) == m.INF
