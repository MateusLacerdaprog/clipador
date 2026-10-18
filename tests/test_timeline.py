"""Operacoes da timeline (dividir, duplicar, mover, aparar com ima, remover) e render apos editar."""
import pytest
from fastapi.testclient import TestClient

from clipador.core import projeto, render
from clipador.core import timeline as tl
from clipador.web.app import app
from conftest import sonda


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def test_dividir_preserva_duracao_e_rotulo_na_primeira_parte(projeto_base):
    p = projeto_base
    p["segmentos"][0]["rotulo"] = "Intro"
    total = projeto.duracao_timeline(p)
    sel = tl.dividir_no_tempo(p, 1.25)          # trecho 1 = 1.0..4.0 da fonte
    a, b = p["segmentos"][0], p["segmentos"][1]
    assert sel == 1 and (a["ini"], a["fim"], b["ini"], b["fim"]) == (1.0, 2.25, 2.25, 4.0)
    assert a["rotulo"] == "Intro" and "rotulo" not in b and a["id"] != b["id"]
    assert abs(projeto.duracao_timeline(p) - total) < 1e-6


def test_dividir_no_segundo_trecho_e_limites(projeto_base):
    p = projeto_base
    tl.dividir_no_tempo(p, 4.5)                  # 1.5 s dentro do trecho 2 (6..9)
    assert [(s["ini"], s["fim"]) for s in p["segmentos"]][1:] == [(6.0, 7.5), (7.5, 9.0)]
    with pytest.raises(tl.ErroTimeline):
        tl.dividir(p, 0, 0.05)                   # parte pequena demais


def test_duplicar_mover_remover(projeto_base):
    p = projeto_base
    tl.duplicar(p, 0)
    assert len(p["segmentos"]) == 3 and p["segmentos"][0]["ini"] == p["segmentos"][1]["ini"]
    assert p["segmentos"][0]["id"] != p["segmentos"][1]["id"]
    ultimo = p["segmentos"][2]["id"]
    tl.mover(p, 2, 0)
    assert p["segmentos"][0]["id"] == ultimo
    tl.remover(p, 0)
    assert ultimo not in [s["id"] for s in p["segmentos"]]


def test_aparar_limita_a_fonte_e_gruda_no_corte(projeto_base):
    p = projeto_base
    p["fontes"][0]["cenas"] = [{"ini": 0.0, "fim": 5.0}, {"ini": 5.0, "fim": 12.0}]
    tl.aparar(p, 0, fim=4.9, ima=0.2)           # gruda no corte de 5.0
    assert p["segmentos"][0]["fim"] == 5.0
    tl.aparar(p, 0, ini=-3)                     # nao passa do comeco da fonte
    assert p["segmentos"][0]["ini"] == 0.0
    tl.aparar(p, 1, fim=99)
    assert p["segmentos"][1]["fim"] == pytest.approx(p["fontes"][0]["info"]["dur"])
    with pytest.raises(tl.ErroTimeline):
        tl.aparar(p, 0, ini=4.95)


@pytest.mark.lento
def test_api_timeline_e_render_apos_editar(cli, projeto_base):
    nome = projeto_base["nome"]
    r = cli.post(f"/api/projetos/{nome}/timeline", json={"op": "dividir_no_tempo", "t": 2.0})
    assert r.status_code == 200 and len(r.json()["segmentos"]) == 3 and r.json()["selecionado"] == 1
    assert cli.post(f"/api/projetos/{nome}/timeline", json={"op": "duplicar", "i": 1}).status_code == 200
    assert cli.post(f"/api/projetos/{nome}/timeline", json={"op": "mover", "i": 3, "para": 0}).status_code == 200
    assert cli.post(f"/api/projetos/{nome}/timeline", json={"op": "remover", "i": 99}).status_code == 400
    assert cli.post(f"/api/projetos/{nome}/timeline", json={"op": "explodir", "i": 0}).status_code == 400
    p = projeto.carregar(nome)
    total = projeto.duracao_timeline(p)
    saida = render.render(p, "rascunho")
    assert abs(sonda(saida)["dur"] - total) < 0.15      # o video montado bate com a timeline editada
