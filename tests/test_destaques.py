"""Destaques de jogo: momentos com nota explicavel, foco automatico e clipes em lote.

Video sintetico de 30 s: fundo parado e som baixo, com UM trecho de "acao" (18-24 s) em que um bloco branco se
mexe do lado DIREITO da tela e ha estalos de ruido 4x por segundo. O certo e conhecido: o melhor momento cai em
18-24 s e o foco vai para a direita.
"""
import os
import time

import pytest
from fastapi.testclient import TestClient

from clipador.core import destaques, midia, projeto
from clipador.web.app import app
from conftest import ffmpeg

ACAO = (18.0, 24.0)


@pytest.fixture(scope="module")
def video_acao(tmp_path_factory):
    v = str(tmp_path_factory.mktemp("acao") / "jogo.mp4")
    ffmpeg("-f", "lavfi", "-i", "color=c=0x404040:s=1280x720:r=30:d=30",
           "-f", "lavfi", "-i",
           "aevalsrc='0.02*sin(2*PI*220*t)+if(between(t,18,24)*lt(mod(t,0.25),0.06),0.8*(random(0)*2-1),0)'"
           ":s=44100:d=30",
           "-f", "lavfi", "-i", "color=c=white:s=120x120:r=30:d=30",
           # overlay recalcula x/y a cada quadro (drawbox nao: o bloco ficaria parado)
           "-filter_complex", "[0:v][2:v]overlay=x=1050:y='mod(t*900,600)':enable='between(t,18,24)'[v]",
           "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", v)
    return v


@pytest.fixture(scope="module")
def sinais_acao(video_acao):
    return destaques.sinais(video_acao, midia.info(video_acao))


def _sobreposicao(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def test_sinais_medem_audio_impactos_e_movimento_no_lugar_certo(sinais_acao):
    s, p = sinais_acao, destaques.PASSO
    dentro, fora = slice(int(19 / p), int(23 / p)), slice(int(5 / p), int(15 / p))
    assert s["volume"][dentro].mean() > s["volume"][fora].mean() + 5     # estalos em 24% do tempo: ~ +8 dB
    assert s["impactos"][dentro].sum() >= 12 and s["impactos"][fora].sum() == 0
    assert s["movimento"][dentro].mean() > 10 * (s["movimento"][fora].mean() + 1e-4)
    perfil = s["perfil"][dentro].sum(axis=0)
    assert perfil[: destaques.COLS // 2].sum() < 0.05 * perfil.sum()      # movimento so do lado direito


def test_melhor_momento_e_a_acao_com_motivos(sinais_acao, video_acao):
    dur = midia.info(video_acao)["dur"]
    ms = destaques.momentos(sinais_acao, [], dur, duracao=6, quantidade=3)
    m = ms[0]
    assert _sobreposicao((m["ini"], m["fim"]), ACAO) >= 4.5, m
    assert m["nota"] > ms[1]["nota"]
    texto = " ".join(m["motivos"])
    assert "impactos sonoros" in texto and "ação na tela" in texto and "acima da média" in texto
    for a, b in zip(ms, ms[1:]):                                          # sem sobreposicao entre momentos
        assert _sobreposicao((a["ini"], a["fim"]), (b["ini"], b["fim"])) == 0
    # trecho parado recebe alerta em vez de elogio
    assert any("parada" in al or "sem cortes" in al for al in ms[-1]["alertas"])


def test_momento_comeca_no_corte_de_cena_proximo(sinais_acao, video_acao):
    dur = midia.info(video_acao)["dur"]
    m = destaques.momentos(sinais_acao, [17.4], dur, duracao=6, quantidade=1)[0]
    assert m["ini"] == 17.4 and abs((m["fim"] - m["ini"]) - 6) < 0.01


def test_evitar_trecho_e_video_sem_audio(sinais_acao, video_acao):
    dur = midia.info(video_acao)["dur"]
    ms = destaques.momentos(sinais_acao, [], dur, duracao=6, quantidade=2, evitar=[(16, 26)])
    assert all(_sobreposicao((m["ini"], m["fim"]), (16, 26)) == 0 for m in ms)
    mudo = {**sinais_acao, "volume": sinais_acao["volume"] * 0 - 90, "impactos": sinais_acao["impactos"] * 0}
    m = destaques.momentos(mudo, [], dur, duracao=6, quantidade=1)[0]
    assert _sobreposicao((m["ini"], m["fim"]), ACAO) >= 4.5                # so o movimento ja acha a acao


def test_foco_automatico_segue_a_acao(sinais_acao):
    fonte = {"info": {"w": 1280, "h": 720}, "crop": None}
    assert destaques.foco_auto(sinais_acao, 18.5, 23.5, fonte, 9 / 16) > 0.85   # bloco em x=1050..1170
    assert destaques.foco_auto(sinais_acao, 3, 10, fonte, 9 / 16) == 0.5        # sem movimento: centro
    # com tarja lateral recortada a conta usa so a area util
    f2 = {"info": {"w": 1280, "h": 720}, "crop": "1200:720:0:0"}
    assert destaques.foco_auto(sinais_acao, 18.5, 23.5, f2, 9 / 16) > 0.85


def test_dividir_em_cortes():
    assert destaques.dividir_em_cortes(10, 20, [9, 12, 12.3, 15, 19.8]) == [(10, 12.3), (12.3, 15), (15, 20)]
    assert destaques.dividir_em_cortes(0, 5, []) == [(0, 5)]


def test_cache_dos_sinais(video_acao, tmp_path):
    inf = midia.info(video_acao)
    c = str(tmp_path / "s.npz")
    a = destaques.sinais(video_acao, inf, c)
    t = time.time()
    b = destaques.sinais(video_acao, inf, c)
    assert time.time() - t < 0.5 and (a["movimento"] == b["movimento"]).all()


# ------------------------------------------------------------------ API
@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _esperar(cli, t):
    for _ in range(240):
        e = cli.get(f"/api/tarefas/{t['id']}").json()
        if e["estado"] in ("ok", "erro"):
            return e
        time.sleep(0.25)
    raise AssertionError("tarefa nao terminou")


@pytest.fixture()
def proj_acao(video_acao, request):
    nome = "d-" + request.node.name.lower()[:40]
    for n in [x for x in projeto.listar() if x.startswith(nome)]:
        import shutil
        shutil.rmtree(projeto.pasta(n))
    p = projeto.criar(nome)
    p["layout"] = "tela_cheia"
    p["legenda"]["estilo"] = "palavra"
    p["fontes"].append({"id": "f1", "caminho": video_acao, "nome": "jogo.mp4", "info": midia.info(video_acao),
                        "crop": None, "cenas": [{"ini": 0.0, "fim": 18.0, "nota": 50},
                                                {"ini": 18.0, "fim": 21.0, "nota": 60},
                                                {"ini": 21.0, "fim": 30.0, "nota": 50}]})
    projeto.salvar(p)
    return nome


def test_api_analisar_aplicar_foco_e_lote(cli, proj_acao):
    n = proj_acao
    t = cli.post(f"/api/projetos/{n}/fontes/f1/destaques", json={"duracao": 6, "quantidade": 3}).json()
    assert _esperar(cli, t)["estado"] == "ok"
    p = cli.get(f"/api/projetos/{n}").json()
    lista = p["fontes"][0]["destaques"]["lista"]
    assert len(lista) == 3 and _sobreposicao((lista[0]["ini"], lista[0]["fim"]), ACAO) >= 4.5
    assert os.path.isfile(os.path.join(projeto.pasta(n), "cache", "f1", "sinais.npz"))

    p = cli.post(f"/api/projetos/{n}/fontes/f1/destaques/aplicar", json={"indice": 0}).json()
    segs = p["segmentos"]
    assert len(segs) == 2 and segs[0]["fim"] == 21.0 == segs[1]["ini"]          # dividido no corte de 21 s
    assert all(s["foco_x"] > 0.85 for s in segs)                                  # seguiu a acao

    # foco automatico em trechos ja existentes
    cli.put(f"/api/projetos/{n}", json={"segmentos": [{**s, "foco_x": 0.0} for s in segs]})
    p = cli.post(f"/api/projetos/{n}/foco_auto", json={}).json()
    assert all(s["foco_x"] > 0.85 for s in p["segmentos"])

    r = cli.post(f"/api/projetos/{n}/fontes/f1/destaques/lote", json={"indices": [0, 1]}).json()
    assert len(r["criados"]) == 2
    novo = projeto.carregar(r["criados"][0])
    assert novo["legenda"]["estilo"] == "palavra" and novo["layout"] == "tela_cheia"
    assert novo["narracao"] is None and novo["aprovacao"]["aprovado_hash"] is None
    assert _sobreposicao((novo["segmentos"][0]["ini"], novo["segmentos"][-1]["fim"]), ACAO) >= 4.5
    assert "destaques" not in novo["fontes"][0] and "nota" in novo["roteiro"]


def test_api_valida_entradas(cli, proj_acao):
    n = proj_acao
    assert cli.post(f"/api/projetos/{n}/fontes/f1/destaques", json={"quantidade": 0}).status_code == 400
    assert cli.post(f"/api/projetos/{n}/fontes/f1/destaques", json={"duracao": 1}).status_code == 400
    assert cli.post(f"/api/projetos/{n}/fontes/zz/destaques", json={}).status_code == 404
    assert cli.post(f"/api/projetos/{n}/fontes/f1/destaques/aplicar", json={"indice": 0}).status_code == 400
    assert cli.post(f"/api/projetos/{n}/fontes/f1/destaques/lote", json={"indices": []}).status_code == 400
    assert cli.post(f"/api/projetos/{n}/foco_auto", json={"indices": [5]}).status_code == 400
    cli.put(f"/api/projetos/{n}", json={"tipo": "longo"})
    p = projeto.carregar(n)
    p["tipo"] = "longo"
    projeto.salvar(p)
    assert cli.post(f"/api/projetos/{n}/foco_auto", json={}).status_code == 400
