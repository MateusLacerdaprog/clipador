"""Centro de comando: interpretar (sem executar), executar so acoes do catalogo, efeito real no projeto, verificador."""
import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from clipador.core import comandos, midia, projeto, verificador
from clipador.web.app import app
from conftest import ffmpeg


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _esperar(cli, t):
    for _ in range(800):
        e = cli.get(f"/api/tarefas/{t['id']}").json()
        if e["estado"] in ("ok", "erro"):
            return e
        time.sleep(0.25)
    raise AssertionError("tarefa nao terminou")


@pytest.mark.parametrize("texto,acoes", [
    ("Gere legendas para este vídeo", ["legendas.gerar"]),
    ("Encontre os momentos mais interessantes", ["momentos.achar"]),
    ("Aplique um zoom suave neste trecho", ["zoom.aplicar"]),
    ("Crie uma versão vertical para Shorts", ["shorts.criar"]),
    ("Coloque o recorte do criador sobre o gameplay", ["react.recorte"]),
    ("Revise as legendas e destaque as palavras importantes", ["legendas.destacar"]),
    ("Prepare uma versão para revisão antes da exportação", ["revisao.preparar"]),
    ("tira o zoom de todos os trechos", ["zoom.remover"]),
    ("gere a prévia e depois gere legendas do áudio do vídeo", ["previa.gerar", "legendas.gerar"]),
    ("faz um bolo de chocolate", []),
])
def test_regras_entendem_os_pedidos_do_dia_a_dia(texto, acoes):
    assert [a["acao"] for a in comandos.interpretar(texto)] == acoes


def test_validacao_barra_acao_ou_parametro_fora_do_catalogo():
    for acao, params in (("rm -rf", {}), ("zoom.aplicar", {"preset": "explodir"}), ("zoom.aplicar", {"codigo": "x"}),
                         ("momentos.achar", {"duracao": "abc"})):
        with pytest.raises(ValueError):
            comandos.validar(acao, params)
    assert comandos.validar("momentos.achar", {"duracao": 9999})["duracao"] == 600


def test_interpretar_nao_executa_nada_e_ia_sem_provedor_explica(cli, projeto_base):
    n = projeto_base["nome"]
    antes = projeto.carregar(n)["segmentos"]
    r = cli.post(f"/api/projetos/{n}/comando/interpretar", json={"texto": "tira o zoom de todos os trechos"}).json()
    assert r["plano"][0]["acao"] == "zoom.remover" and projeto.carregar(n)["segmentos"] == antes
    r = cli.post(f"/api/projetos/{n}/comando/interpretar", json={"texto": "faz um bolo"}).json()
    assert r["plano"] == [] and r["exemplos"]
    t = cli.post(f"/api/projetos/{n}/comando/interpretar", json={"texto": "faz um bolo", "usar_ia": True}).json()["tarefa"]
    e = _esperar(cli, t)
    assert e["estado"] == "erro" and "provedor" in e["erro"]


def test_executar_muda_o_projeto_de_verdade(cli, projeto_base):
    n = projeto_base["nome"]
    ex = lambda acao, params=None, ctx=None: cli.post(f"/api/projetos/{n}/comando/executar",
                                                      json={"acao": acao, "params": params or {}, "contexto": ctx or {}})
    assert ex("zoom.aplicar", {"preset": "impacto", "alvo": "selecionado"}).status_code == 400   # nenhum trecho escolhido
    r = ex("zoom.aplicar", {"preset": "impacto", "alvo": "selecionado"}, {"trecho": 1})
    assert r.status_code == 200 and r.json()["aba"] == "cortes"
    segs = projeto.carregar(n)["segmentos"]
    assert "zoom_fx" not in segs[0] and segs[1]["zoom_fx"]["preset"] == "impacto"
    ex("zoom.aplicar", {"preset": "destaque", "alvo": "todos"})
    assert all(s["zoom_fx"]["preset"] == "destaque" for s in projeto.carregar(n)["segmentos"])
    ex("zoom.remover", {"alvo": "todos"})
    assert not any(s.get("zoom_fx") for s in projeto.carregar(n)["segmentos"])
    # legendas: destacar marca palavras no arquivo de cartoes
    d = projeto.pasta(n)
    json.dump([{"palavras": [{"w": "custa", "start": 0.1, "end": 0.4}, {"w": "70", "start": 0.4, "end": 0.8}]}],
              open(os.path.join(d, "legenda_cartoes.json"), "w", encoding="utf-8"))
    assert "1 palavra" in ex("legendas.destacar").json()["mensagem"]
    assert json.load(open(os.path.join(d, "legenda_cartoes.json"), encoding="utf-8"))[0]["palavras"][1]["e"] is True
    # protecoes
    assert ex("exportar.final").status_code == 400                     # sem aprovacao nao exporta
    assert ex("react.recorte").status_code == 400                      # sem camera
    assert "vertical" in ex("shorts.criar").json()["detail"]           # projeto curto ja e vertical
    assert ex("nao.existe").status_code == 400
    # tarefa longa: momentos -> lista guardada na fonte
    r = ex("momentos.achar", {"duracao": 5, "quantidade": 2}).json()
    assert _esperar(cli, r["tarefa"])["estado"] == "ok" and projeto.carregar(n)["fontes"][0]["destaques"]["lista"]


@pytest.mark.lento
def test_revisao_gera_rascunho_e_confere_o_arquivo(cli, projeto_base):
    n = projeto_base["nome"]
    r = cli.post(f"/api/projetos/{n}/comando/executar", json={"acao": "revisao.preparar"}).json()
    e = _esperar(cli, r["tarefa"])
    assert e["estado"] == "ok", e
    res = e["resultado"]
    assert res["arquivo"].startswith("RASCUNHO_") and os.path.isfile(os.path.join(projeto.pasta(n), res["arquivo"]))
    assert not any(i["nivel"] == "erro" for i in res["itens"]), res["itens"]
    v = cli.get(f"/api/projetos/{n}/verificar").json()
    assert v["conferiu_arquivo"] is True


def test_verificador_acha_problemas_reais(projeto_base, tmp_path):
    n = projeto_base["nome"]
    p = projeto.carregar(n)
    json.dump([{"palavras": [{"w": "fim", "start": 30.0, "end": 30.5}]}],
              open(os.path.join(projeto.pasta(n), "legenda_cartoes.json"), "w", encoding="utf-8"))
    p["legenda_origem"] = "video"
    projeto.salvar(p)
    # o render corta a legenda no fim do video: e aviso (o video sai certo), nao erro
    titulos = [i["titulo"] for i in verificador.verificar_projeto(projeto.carregar(n)) if i["nivel"] == "aviso"]
    assert "Legenda passa do fim do vídeo" in titulos
    # legenda de narracao sem narracao no projeto: nao aparece no video -> erro
    p["legenda_origem"] = "narracao"
    projeto.salvar(p)
    erros = [i["titulo"] for i in verificador.verificar_projeto(projeto.carregar(n)) if i["nivel"] == "erro"]
    assert "As legendas não aparecem no vídeo" in erros
    p["legenda_origem"] = "video"
    projeto.salvar(p)
    # arquivo com 1 s preto e 4 s de silencio no meio
    v = str(tmp_path / "ruim.mp4")
    ffmpeg("-f", "lavfi", "-i", "color=c=0x808080:s=1080x1920:r=30:d=2", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30:d=1.5",
           "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=3",
           "-f", "lavfi", "-i", "aevalsrc='if(lt(t,1)+gt(t,5.5),0.3*sin(2*PI*440*t),0)':s=48000:d=6.5",
           "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-map", "3:a",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", v)
    itens = {i["titulo"]: i for i in verificador.verificar_arquivo(v)}
    assert "Trechos pretos" in itens and "2.0" in itens["Trechos pretos"]["detalhe"]
    assert "Silêncio de 3 s ou mais" in itens
    assert midia.info(v)["audio"]


def test_comandos_fechar_loop_e_conferir_publicacao(cli, projeto_base):
    acoes = lambda f: [a["acao"] for a in comandos.interpretar(f)]
    assert acoes("feche o loop") == ["timeline.loop"] and acoes("faz o final voltar pro começo") == ["timeline.loop"]
    assert acoes("verifique a publicação") == ["publicacao.verificar"]
    assert acoes("revise as hashtags") == ["publicacao.verificar"]            # nao gera RASCUNHO
    assert acoes("verifique o projeto") == ["verificar"]                     # verifiQue, nao so verifiCar
    n = projeto_base["nome"]
    r = cli.post(f"/api/projetos/{n}/comando/executar", json={"acao": "timeline.loop"}).json()
    assert r["estado"]["segmentos"][-1]["loop"] is True and r["aba"] == "cortes"
    r = cli.post(f"/api/projetos/{n}/comando/executar", json={"acao": "timeline.loop"}).json()
    assert "já repete" in r["mensagem"] and len(r["estado"]["segmentos"]) == 3   # segunda vez nao duplica
    r = cli.post(f"/api/projetos/{n}/comando/executar", json={"acao": "publicacao.verificar"}).json()
    assert "Sem título" in [i["titulo"] for i in r["itens"]]


def test_versao_vertical_pode_ser_criada_mais_de_uma_vez(cli, projeto_base):
    n = projeto_base["nome"]
    cli.put(f"/api/projetos/{n}", json={"tipo": "longo"})
    p = projeto.carregar(n)
    p["tipo"] = "longo"
    projeto.salvar(p)
    nomes = [cli.post(f"/api/projetos/{n}/comando/executar", json={"acao": "shorts.criar"}).json() for _ in range(2)]
    criados = [projeto.slug(f"{n}-shorts-{k}") for k in (1, 2)]
    try:
        assert all(os.path.isfile(os.path.join(projeto.pasta(c), "projeto.json")) for c in criados), nomes
    finally:
        import shutil
        for c in criados:
            shutil.rmtree(projeto.pasta(c), ignore_errors=True)
