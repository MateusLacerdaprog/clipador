"""Formatos curto/longo: presets, video longo 16:9, ranking progressivo e capitulos do YouTube."""
import os
import re

import pytest
from fastapi.testclient import TestClient

from clipador.core import formatos, projeto, render
from clipador.web.app import app
from conftest import sonda


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def test_catalogo_tem_as_5_categorias_mais_livre_nos_dois_tipos(cli):
    cat = cli.get("/api/formatos").json()
    for tipo in ("curto", "longo"):
        ids = [f["id"] for f in cat[tipo]]
        extra = ["comparacao"] if tipo == "curto" else []          # tela dividida A x B so no curto
        assert ids == ["guias", "noticias", "gameplay", "curiosidades", "compilados", *extra, "livre"]
        assert all(f["descricao"] for f in cat[tipo])


@pytest.mark.parametrize("cat", formatos.CATEGORIAS)
def test_criar_projeto_curto_aplica_preset(cli, cat):
    r = cli.post("/api/projetos", json={"nome": f"fmt curto {cat}", "tipo": "curto", "formato": cat})
    assert r.status_code == 200, r.text
    p = r.json()
    f = formatos.obter("curto", cat)
    assert p["tipo"] == "curto" and p["formato"] == cat
    assert p["layout"] == f["preset"]["layout"] and p["legenda"]["estilo"] == f["preset"]["legenda"]["estilo"]
    assert p["formato_cfg"]["duracao_alvo"] == f["duracao_alvo"]
    assert p["formato_cfg"]["ranking"] == (cat == "compilados")
    g = cli.get(f"/api/projetos/{p['nome']}/guia").json()
    assert g["estrutura"] and g["checklist"] and abs(g["estrutura"][-1]["fim"] - f["duracao_alvo"]) < 1


def test_criar_projeto_longo_e_horizontal_com_capitulos(cli):
    p = cli.post("/api/projetos", json={"nome": "fmt longo guia", "tipo": "longo", "formato": "guias"}).json()
    assert p["layout"] == "horizontal" and p["formato_cfg"]["capitulos"] is True
    assert "[INTRO" in p["roteiro"]


def test_formato_invalido_rejeitado(cli):
    assert cli.post("/api/projetos", json={"nome": "x1", "tipo": "medio"}).status_code == 400
    assert cli.post("/api/projetos", json={"nome": "x2", "formato": "dancinha"}).status_code == 400


@pytest.mark.lento
def test_video_longo_sai_1920x1080(projeto_base):
    p = projeto_base
    formatos.aplicar(p, "longo", "gameplay")
    p["segmentos"][0]["rotulo"] = "Começo"
    saida = render.render(p, "rascunho")
    s = sonda(saida)
    assert (s["w"], s["h"]) == (1920, 1080) and abs(s["dur"] - 6.0) < 0.15
    q = render.quadros(p, [1.0])
    assert q   # quadro horizontal gerado
    ass = open(os.path.join(projeto.pasta(p["nome"]), "legenda.ass"), encoding="utf-8").read()
    assert "PlayResX: 1920" in ass and "Capitulo" in ass and "Começo" in ass


def test_ranking_revela_do_ultimo_para_o_primeiro(projeto_base):
    p = projeto_base
    formatos.aplicar(p, "curto", "compilados")
    p["segmentos"][0]["rotulo"] = "quase"
    p["segmentos"][1]["rotulo"] = "o melhor"
    render.preparar_ass(p)
    ass = open(os.path.join(projeto.pasta(p["nome"]), "legenda.ass"), encoding="utf-8").read()
    linhas = [l for l in ass.splitlines() if ",Ranking," in l]
    assert any(l.endswith("1.") for l in linhas) and any(l.endswith("2.") for l in linhas)
    quase = next(l for l in linhas if l.endswith("quase"))
    melhor = next(l for l in linhas if l.endswith("o melhor"))
    assert quase.split(",")[1] == "0:00:00.00"          # 1o trecho = 2o lugar, aparece no inicio
    assert melhor.split(",")[1] == "0:00:03.00"         # ultimo trecho = 1o lugar, aparece aos 3 s
    y = lambda l: int(re.search(r"\\pos\(\d+,(\d+)\)", l).group(1))  # noqa: E731
    assert y(melhor) < y(quase)                          # 1o lugar fica em cima na lista


def test_capitulos_e_regras_do_youtube():
    p = {"segmentos": [{"ini": 0, "fim": 30, "rotulo": "Intro"}, {"ini": 0, "fim": 25, "rotulo": "Parte 1"},
                       {"ini": 0, "fim": 5}, {"ini": 0, "fim": 40, "rotulo": "Parte 2"}]}
    c = formatos.capitulos(p)
    assert c["texto"].splitlines() == ["00:00 Intro", "00:30 Parte 1", "01:00 Parte 2"]
    assert not c["avisos"]
    c = formatos.capitulos({"segmentos": [{"ini": 0, "fim": 5, "rotulo": "A"}, {"ini": 0, "fim": 20, "rotulo": "B"}]})
    assert any("3 ou mais" in a for a in c["avisos"]) and any("10 s" in a for a in c["avisos"])
    c = formatos.capitulos({"segmentos": [{"ini": 0, "fim": 12}, {"ini": 0, "fim": 12, "rotulo": "X"}]})
    assert c["capitulos"][0] == [0.0, "Introdução"]


def test_trocar_formato_mantem_trechos(cli, projeto_base):
    nome = projeto_base["nome"]
    antes = projeto.carregar(nome)["segmentos"]
    p = cli.post(f"/api/projetos/{nome}/formato", json={"formato": "curiosidades"}).json()
    assert p["formato"] == "curiosidades" and len(p["segmentos"]) == len(antes)
    assert all(s["zoom"] >= 1.15 or s["zoom"] != 1.0 for s in p["segmentos"])
