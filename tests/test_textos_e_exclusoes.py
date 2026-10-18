"""Aba 6 · Textos e funcoes de excluir: titulo do inicio so por escolha, legendas que nao apareciam (projeto sem
narracao) passam a aparecer, legenda escrita a mao (adicionar/editar/excluir/excluir todas, com Desfazer),
excluir RASCUNHO/FINAL e quadros, excluir projeto para a lixeira e restaurar.

API real (TestClient) + render real do FFmpeg; projetos na pasta temporaria do conftest.
"""
import json
import os

import pytest
from fastapi.testclient import TestClient

from clipador.core import projeto, render
from clipador.web.app import app


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _pal(*itens):
    return [{"w": w, "start": t, "end": t + 0.3} for t, w in itens]


def _falas_do_ass(n):
    render.preparar_ass(projeto.carregar(n))
    ass = open(os.path.join(projeto.pasta(n), "legenda.ass"), encoding="utf-8-sig").read()
    return [l for l in ass.splitlines() if l.startswith("Dialogue:") and ",Leg," in l]


def _palavras(cart):
    return [w["w"] for c in cart for w in c["palavras"]]


def test_formato_so_sugere_o_titulo_e_tirar_o_titulo_funciona(cli):
    p = cli.post("/api/projetos", json={"nome": "t-txt-curio", "tipo": "curto", "formato": "curiosidades"}).json()
    assert p["gancho"]["texto"] == ""                                       # antes: "VOCÊ SABIA DISSO?" sozinho
    assert cli.get("/api/projetos/t-txt-curio/guia").json()["sugestao_gancho"] == "VOCÊ SABIA DISSO?"
    cli.put("/api/projetos/t-txt-curio", json={"gancho": {"texto": "MEU TÍTULO", "ate": 2}})
    cli.post("/api/projetos/t-txt-curio/formato", json={"formato": "guias"})    # trocar o formato nao mexe no titulo
    assert cli.get("/api/projetos/t-txt-curio").json()["gancho"]["texto"] == "MEU TÍTULO"
    assert cli.put("/api/projetos/t-txt-curio", json={"gancho": {"texto": "", "ate": 2}}).json()["gancho"]["texto"] == ""
    cli.post("/api/projetos/t-txt-curio/formato", json={"formato": "curiosidades"})
    assert cli.get("/api/projetos/t-txt-curio").json()["gancho"]["texto"] == ""   # tirado continua tirado


def test_legendas_que_nao_apareciam_passam_a_aparecer_e_desfazer(cli, projeto_base):
    n = projeto_base["nome"]                                                 # sem narracao, video de 6 s
    cli.put(f"/api/projetos/{n}", json={"audio": {"narracao": {"deslocamento": 1.0}}})
    cart = [{"palavras": _pal((0.5, "olha"), (1.0, "isso"))}, {"palavras": _pal((2.0, "agora"))}]
    json.dump(cart, open(os.path.join(projeto.pasta(n), "legenda_cartoes.json"), "w", encoding="utf-8"))
    est = cli.get(f"/api/projetos/{n}").json()
    assert est["legendas_invisiveis"] is True and _falas_do_ass(n) == []     # o bug: legenda feita e nada no video
    r = cli.post(f"/api/projetos/{n}/legendas/manual").json()
    assert r["legenda_origem"] == "manual" and r["legendas_invisiveis"] is False and r["desloc_legenda"] == 0
    assert r["cartoes"][0]["palavras"][0]["start"] == 1.5                    # + deslocamento: mesmo ponto do video
    falas = _falas_do_ass(n)
    assert any("olha" in l for l in falas) and any("agora" in l for l in falas)
    v = cli.post(f"/api/projetos/{n}/legendas/restaurar").json()            # Desfazer: volta tudo, origem junto
    assert v["legenda_origem"] == "narracao" and v["cartoes"][0]["palavras"][0]["start"] == 0.5


def test_escrever_editar_e_excluir_legendas_a_mao(cli, projeto_base):
    n = projeto_base["nome"]                                                 # timeline de 6 s, sem legenda
    r = cli.post(f"/api/projetos/{n}/legendas/cartao", json={"texto": "Olha o *Jason* aqui!", "ini": 1.0, "fim": 3.0}).json()
    assert r["legenda_origem"] == "manual" and r["indice"] == 0
    ps = r["cartoes"][0]["palavras"]
    assert [w["w"] for w in ps] == ["Olha", "o", "Jason", "aqui"] and ps[2]["e"] and (ps[0]["start"], ps[-1]["end"]) == (1.0, 3.0)
    # outra antes: termina antes da proxima (nao invade); no mesmo instante: recusa
    r = cli.post(f"/api/projetos/{n}/legendas/cartao", json={"texto": "primeiro", "ini": 0.2, "fim": 2.0}).json()
    assert r["indice"] == 0 and r["cartoes"][0]["palavras"][-1]["end"] == pytest.approx(0.99)
    assert cli.post(f"/api/projetos/{n}/legendas/cartao", json={"texto": "x", "ini": 2.0, "fim": 2.5}).status_code == 400
    assert cli.post(f"/api/projetos/{n}/legendas/cartao", json={"texto": "x", "ini": 7.0, "fim": 8.0}).status_code == 400
    assert cli.post(f"/api/projetos/{n}/legendas/cartao", json={"texto": " ", "ini": 4.0, "fim": 5.0}).status_code == 400
    r = cli.post(f"/api/projetos/{n}/legendas/cartao", json={"texto": "no fim", "ini": 5.0, "fim": 9.0}).json()
    assert r["cartoes"][-1]["palavras"][-1]["end"] == 6.0                    # nunca passa do fim do video
    falas = _falas_do_ass(n)                                                 # aparecem no video (sem narracao)
    assert all(any(w in l for l in falas) for w in ("primeiro", "Jason", "fim"))

    # editar o texto de um cartao; texto vazio exclui
    r = cli.put(f"/api/projetos/{n}/legendas/cartao/1/texto", json={"texto": "mudei tudo"}).json()
    assert _palavras(r["cartoes"][1:2]) == ["mudei", "tudo"]
    r = cli.put(f"/api/projetos/{n}/legendas/cartao/0/texto", json={"texto": ""}).json()
    assert len(r["cartoes"]) == 2
    v = cli.post(f"/api/projetos/{n}/legendas/restaurar").json()            # Desfazer a exclusao
    assert len(v["cartoes"]) == 3
    # excluir um, salvar correcoes com um vazio, excluir todas
    assert len(cli.delete(f"/api/projetos/{n}/legendas/cartao/2").json()["cartoes"]) == 2
    assert cli.delete(f"/api/projetos/{n}/legendas/cartao/9").status_code == 404
    assert _palavras(cli.put(f"/api/projetos/{n}/legendas", json={"textos": ["", "ficou"]}).json()) == ["ficou"]
    r = cli.delete(f"/api/projetos/{n}/legendas").json()
    assert r["cartoes"] == [] and r["n_cartoes"] == 0 and _falas_do_ass(n) == []
    assert _palavras(cli.post(f"/api/projetos/{n}/legendas/restaurar").json()["cartoes"]) == ["ficou"]


@pytest.mark.lento
def test_excluir_rascunho_e_quadros(cli, projeto_base):
    n = projeto_base["nome"]
    rasc = render.render(projeto.carregar(n), "rascunho")
    nome = os.path.basename(rasc)
    p = projeto.carregar(n)
    p["aprovacao"]["rascunho_hash"] = projeto.hash_conteudo(p)
    projeto.salvar(p)
    q = render.quadros(projeto.carregar(n), [1.0, 2.0])
    est = cli.get(f"/api/projetos/{n}").json()
    assert nome in est["saidas"] and est["rascunho_atual"]
    for ruim in ("projeto.json", "..%2Fx.mp4", "outro.mp4", "RASCUNHO_x.mov"):
        assert cli.delete(f"/api/projetos/{n}/saidas/{ruim}").status_code in (400, 404), ruim
    est = cli.delete(f"/api/projetos/{n}/saidas/{nome}").json()
    assert nome not in est["saidas"] and not est["rascunho_atual"] and not os.path.exists(rasc)
    assert os.path.isfile(os.path.join(projeto.pasta(n), "projeto.json"))   # o projeto continua
    assert cli.delete(f"/api/projetos/{n}/saidas/{nome}").status_code == 404
    assert cli.delete(f"/api/projetos/{n}/quadros").json()["apagados"] == len(q) == 2
    assert not any(f.endswith(".png") for f in os.listdir(os.path.join(projeto.pasta(n), "quadros")))


def test_excluir_projeto_vai_para_a_lixeira_e_restaura(cli):
    cli.post("/api/projetos", json={"nome": "t-lixo", "tipo": "curto"})
    cli.put("/api/projetos/t-lixo", json={"roteiro": "guardado"})
    item = cli.delete("/api/projetos/t-lixo").json()["lixeira"]
    assert "t-lixo" not in [p["nome"] for p in cli.get("/api/projetos").json()]
    assert cli.get("/api/projetos/t-lixo").status_code == 404
    assert cli.post("/api/projetos", json={"nome": "_lixeira"}).status_code == 400
    assert cli.post("/api/lixeira/..%2F..%2Fx/restaurar").status_code in (400, 404)
    p = cli.post(f"/api/lixeira/{item}/restaurar").json()
    assert p["nome"] == "t-lixo" and p["roteiro"] == "guardado"
    item2 = cli.delete("/api/projetos/t-lixo").json()["lixeira"]
    cli.post("/api/projetos", json={"nome": "t-lixo"})                       # outro com o mesmo nome
    assert cli.post(f"/api/lixeira/{item2}/restaurar").status_code == 409    # nao sobrescreve
