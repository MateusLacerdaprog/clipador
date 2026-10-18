"""Checklist de retencao (medido na montagem, sem render) e "fechar o loop".
Nada aqui preve views: compara a montagem com as recomendacoes de Shorts (gancho, troca de imagem, legenda, loop)."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from clipador.core import formatos, projeto, timeline, verificador
from clipador.web.app import app


def _cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _titulos(p, nivel=None):
    return [i["titulo"] for i in verificador.verificar_projeto(p) if nivel is None or i["nivel"] == nivel]


def test_fechar_o_loop_repete_o_comeco_no_fim_e_fica_fora_do_ranking(projeto_base):
    p = projeto_base
    p["segmentos"][0]["rotulo"] = "Top 2"
    assert not timeline.tem_loop(p)
    i = timeline.fechar_loop(p)
    a, z = p["segmentos"][0], p["segmentos"][i]
    assert i == 2 and z["loop"] is True and z["ini"] == a["ini"] and z["fim"] == pytest.approx(a["ini"] + 0.9)
    assert z["foco_x"] == a["foco_x"] and "rotulo" not in z and z["id"] != a["id"]
    assert timeline.tem_loop(p)
    with pytest.raises(timeline.ErroTimeline):
        timeline.fechar_loop(p)                                   # nao repete duas vezes
    assert [pos for _, pos, _ in formatos.ranking(p)] == [2, 1]  # o loop nao vira posicao do ranking


def test_api_fechar_loop_e_o_desfazer_preservam_a_marca(projeto_base):
    n, cli = projeto_base["nome"], _cli()
    r = cli.post(f"/api/projetos/{n}/timeline", json={"op": "fechar_loop"}).json()
    assert r["selecionado"] == 2 and r["segmentos"][-1]["loop"] is True and r["duracao"] == pytest.approx(6.9)
    assert cli.post(f"/api/projetos/{n}/timeline", json={"op": "fechar_loop"}).status_code == 400
    # o desfazer da interface manda os trechos de volta pelo PUT: a marca de loop sobrevive
    segs = r["segmentos"]
    assert cli.put(f"/api/projetos/{n}", json={"segmentos": segs}).json()["segmentos"][-1]["loop"] is True
    assert "O final não volta ao começo" not in _titulos(projeto.carregar(n))


def test_retencao_cobra_gancho_legenda_e_loop(projeto_base):
    p = projeto_base
    p["gancho"]["texto"] = ""
    t = _titulos(p)
    assert "Nada escrito na tela nos primeiros segundos" in t and "Sem legenda" in t and "O final não volta ao começo" in t
    assert "Projeto sem problemas encontrados" not in t
    p["gancho"]["texto"] = "VOCÊ VIU ISSO?"
    cart = [{"palavras": [{"word": "olha", "start": 0.2, "end": 0.6}]}]
    json.dump(cart, open(os.path.join(projeto.pasta(p["nome"]), "legenda_cartoes.json"), "w", encoding="utf-8"))
    p["legenda_origem"] = "manual"
    timeline.fechar_loop(p)
    itens = verificador.verificar_projeto(p)
    assert itens[0]["nivel"] == "ok"                              # so dicas sobrando: o projeto esta ok
    assert not [i for i in itens if i["nivel"] in ("erro", "aviso")]


def test_planos_longos_curtos_e_zoom_contando_como_movimento(projeto_base):
    p = projeto_base
    p["segmentos"][0]["fim"] = 7.0                                # 6 s parado
    assert "Planos parados por mais de 4 s" in _titulos(p, "aviso")
    p["segmentos"][0]["zoom_fx"] = {"preset": "lento", "intensidade": 1.2}
    assert "Planos parados por mais de 4 s" not in _titulos(p, "aviso")
    p["segmentos"][0].pop("zoom_fx")
    p["fontes"][0]["cenas"] = [{"ini": 0.0, "fim": 4.0}, {"ini": 4.0, "fim": 12.0}]   # corte no meio = troca de imagem
    assert "Planos parados por mais de 4 s" not in _titulos(p, "aviso")
    p["segmentos"][1]["fim"] = 6.6                                # 0,6 s: pisca
    assert "Planos com menos de 1 s" in _titulos(p, "aviso")


def test_formato_comparacao_pede_plano_minimo_maior(projeto_base):
    p = projeto_base
    p["formato"], p["layout"] = "comparacao", "comparacao"
    p["segmentos"][1]["fim"] = 7.8                                # 1,8 s: pouco para comparar A x B
    assert formatos.guia(p)["min_cena"] == 2.2
    assert "Planos com menos de 2.2 s" in _titulos(p, "aviso")


def test_aviso_de_corte_de_cena_colado_na_borda_do_trecho(projeto_base):
    p = projeto_base
    p["fontes"][0]["cenas"] = [{"ini": 0.0, "fim": 1.2}, {"ini": 1.2, "fim": 12.0}]   # trecho 1 comeca em 1,0 s
    itens = [i for i in verificador.verificar_projeto(p) if i["titulo"] == "Trecho com pedaço de outra cena na borda"]
    assert itens and "1 (0.20 s)" in itens[0]["detalhe"]
    p["fontes"][0]["cenas"] = [{"ini": 0.0, "fim": 2.5}, {"ini": 2.5, "fim": 12.0}]   # corte no meio: normal
    assert "Trecho com pedaço de outra cena na borda" not in _titulos(p)


def test_duracao_na_zona_do_meio_vira_dica(projeto_base):
    p = projeto_base
    p["segmentos"] = [dict(p["segmentos"][0], id=f"s{k}", ini=0.0, fim=3.5) for k in range(11)]   # 38,5 s
    assert any(t.startswith("Duração de 38") for t in _titulos(p, "dica"))
