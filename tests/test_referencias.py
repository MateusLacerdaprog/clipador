"""Perfis de referencia: comparacao e aplicacao (com perfil construido aqui). Perfis reais medem canais de
terceiros e ficam so na maquina (referencias/*.json fora do Git)."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from clipador.core import referencias
from clipador.web.app import app

PERFIL = {"id": "ref-teste", "nome": "Ref Teste", "aspectos": list(referencias.ASPECTOS),
          "fonte": {"canais": ["https://www.youtube.com/@x"], "data": "2026-10-16", "amostra": {"curtos": 10, "longos": 5, "detalhados": 5}},
          "observado": {"curtos": {"n": 10, "dur_mediana_s": 25, "dur_p25_s": 23, "dur_p75_s": 29},
                        "visual": {"cortes_por_min_curtos": 51, "layout_curtos": "tela_cheia", "legenda_curtos": "palavra"},
                        "fala": {"ppm_curtos_mediana": 234, "palavras_3s_curtos_mediana": 10}},
          "limitacoes": []}


@pytest.fixture()
def perfil():
    p = dict(PERFIL)
    p["derivado"] = referencias.derivar(p["observado"])
    referencias.salvar(p)
    yield p
    referencias.apagar(p["id"])


def test_derivados(perfil):
    d = perfil["derivado"]["curto"]
    assert d["duracao_alvo"] == 25 and d["max_cena"] == 1.2 and d["layout"] == "tela_cheia" and d["legenda"] == "palavra"


def test_comparar_aponta_diferencas_explicaveis(projeto_base, perfil):
    c = referencias.comparar(projeto_base, perfil)
    itens = {i["aspecto"]: i for i in c["itens"]}
    assert itens["Duração"]["situacao"] == "atencao" and "25 s" in itens["Duração"]["sugestao"]   # 6 s vs ~25 s
    assert "Ritmo de cortes" in itens and itens["Gancho na tela"]["situacao"] == "atencao"
    assert c["metricas"]["duracao_s"] == 6.0


def test_aplicar_pela_api_e_reabrir(projeto_base, perfil):
    cli = TestClient(app, base_url="http://127.0.0.1:8765")
    r = cli.post(f"/api/projetos/{projeto_base['nome']}/referencia/{perfil['id']}/aplicar").json()
    assert r["layout"] == "tela_cheia" and r["legenda"]["estilo"] == "palavra" and r["referencia"] == perfil["id"]
    assert r["formato_cfg"]["duracao_alvo"] == 25 and r["mudancas"]
    assert cli.get(f"/api/projetos/{projeto_base['nome']}").json()["referencia"] == perfil["id"]


def test_perfil_nao_guarda_texto_de_fala(perfil):
    txt = json.dumps(perfil, ensure_ascii=False)
    assert "roteiro" not in txt and "transcri" not in txt


def test_gerar_so_aceita_youtube():
    cli = TestClient(app, base_url="http://127.0.0.1:8765")
    r = cli.post("/api/referencias", json={"nome": "x", "canais": ["https://evil.example/canal"]})
    assert r.status_code == 400


def test_perfil_real_local_tem_dados_observados():
    pasta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "referencias")
    reais = sorted(f for f in os.listdir(pasta) if f.endswith(".json")) if os.path.isdir(pasta) else []
    if not reais:
        pytest.skip("nenhum perfil real nesta máquina (são de terceiros: ficam fora do Git)")
    caminho = os.path.join(pasta, reais[0])
    p = json.load(open(caminho, encoding="utf-8"))
    assert p["fonte"]["amostra"]["curtos"] > 50 and p["observado"]["visual"]["cortes_por_min_curtos"] > 0
