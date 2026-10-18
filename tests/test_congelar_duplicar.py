"""Quadro congelado (timeline + render real), duplicar projeto (teste A/B de gancho), versao sem audio e revisar mudo."""
import os
import subprocess

import pytest
from fastapi.testclient import TestClient

from clipador.core import formatos, projeto, render, timeline
from clipador.web.app import app
from conftest import ESTATICO, ffmpeg, sonda, volume_medio


def _cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _quadro(video, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-vf", "scale=64:114",
                        "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True)
    return r.stdout


def _diferenca(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / max(len(a), 1)


def test_congelar_divide_o_trecho_e_insere_o_quadro_parado(projeto_base):
    p = projeto_base                                              # trechos: 1-4 s e 6-9 s da fonte
    i = timeline.congelar(p, 1.5)
    segs = p["segmentos"]
    assert i == 1 and [round(s["fim"] - s["ini"], 2) for s in segs] == [1.5, 1.0, 1.5, 3.0]
    assert segs[1]["congelado"] is True and segs[1]["ini"] == 2.5 and segs[0]["fim"] == 2.5
    with pytest.raises(timeline.ErroTimeline):
        timeline.congelar(p, 1.7)                                 # ja e um quadro congelado
    timeline.dividir(p, 1, 0.4)                                   # dividir o congelado: as duas partes no MESMO quadro
    assert p["segmentos"][1]["ini"] == p["segmentos"][2]["ini"] == 2.5
    assert round(p["segmentos"][1]["fim"] - 2.5, 2) == 0.4 and round(p["segmentos"][2]["fim"] - 2.5, 2) == 0.6
    assert len(formatos.ranking(p)) == 3                          # congelado nao vira posicao do ranking
    assert timeline.congelar(p, 0.0) == 0 and p["segmentos"][0]["ini"] == 1.0   # no comeco: entra antes


@pytest.mark.lento
def test_render_do_quadro_congelado_fica_parado_e_sem_som_do_jogo(projeto_base):
    p = projeto_base
    timeline.congelar(p, 1.5, 1.0)                                # 1,5-2,5 s da montagem: parado
    projeto.salvar(p)
    saida = render.render(projeto.carregar(p["nome"]), "proxy")
    s = sonda(saida)
    assert abs(s["dur"] - 7.0) < 0.15
    assert _diferenca(_quadro(saida, 1.6), _quadro(saida, 2.4)) < 2          # mesma imagem
    assert _diferenca(_quadro(saida, 3.0), _quadro(saida, 3.8)) > 2          # o resto continua andando
    assert volume_medio(saida, 1.6, 0.8) < -60 < volume_medio(saida, 3.0, 0.8)


@pytest.mark.lento
@pytest.mark.parametrize("layout", ["empilhado", "comparacao"])
def test_quadro_congelado_nos_outros_layouts(projeto_base, layout):
    p = projeto_base
    p["layout"] = layout
    if layout == "comparacao":
        p["comparacao"].update(fonte_a="f1", fonte_b="f1")
        for s in p["segmentos"]:
            s.update(fonte_b="f1", ini_b=s["ini"])
    timeline.congelar(p, 4.0, 0.8)
    projeto.salvar(p)
    saida = render.render(projeto.carregar(p["nome"]), "proxy")
    assert abs(sonda(saida)["dur"] - 6.8) < 0.15


def test_api_congelar_e_validacao_do_trecho_parado(projeto_base):
    n, cli = projeto_base["nome"], _cli()
    r = cli.post(f"/api/projetos/{n}/timeline", json={"op": "congelar", "t": 5.9, "dentro": 2.0}).json()
    assert r["segmentos"][-1]["congelado"] is True and r["duracao"] == pytest.approx(8.0)
    segs = r["segmentos"]
    segs[-1].update(ini=11.5, fim=13.0)                           # parado no fim da fonte (12 s): pode passar dela
    assert cli.put(f"/api/projetos/{n}", json={"segmentos": segs}).json()["segmentos"][-1]["fim"] == 13.0
    segs[0].update(fim=13.0)                                      # trecho normal nao pode
    assert cli.put(f"/api/projetos/{n}", json={"segmentos": segs}).status_code == 400
    assert cli.post(f"/api/projetos/{n}/timeline", json={"op": "congelar", "t": 1, "dentro": 30}).status_code == 400


def test_duplicar_projeto_para_testar_outro_gancho(projeto_base):
    n, cli = projeto_base["nome"], _cli()
    d = projeto.pasta(n)
    for arq in ("narracao.wav", "RASCUNHO_x.mp4", "FINAL_x.mp4"):
        open(os.path.join(d, arq), "w").write("x")
    open(os.path.join(d, "legenda_cartoes.json"), "w").write("[]")
    os.makedirs(os.path.join(d, "quadros"), exist_ok=True)
    os.makedirs(os.path.join(d, "cache", "f1"), exist_ok=True)
    open(os.path.join(d, "cache", "f1", "c000.jpg"), "w").write("x")
    p = projeto.carregar(n)
    p.update(narracao="narracao.wav", aprovacao={"rascunho_hash": "a", "aprovado_hash": "a"})
    p["gancho"]["texto"] = "GANCHO A"
    projeto.salvar(p)
    try:
        e = cli.post(f"/api/projetos/{n}/duplicar", json={}).json()
        assert e["nome"] == f"{n}-b" and e["gancho"]["texto"] == "GANCHO A" and e["narracao"] == "narracao.wav"
        assert e["aprovacao"] == {"rascunho_hash": None, "aprovado_hash": None}
        assert e["fontes"][0]["caminho"] == p["fontes"][0]["caminho"]          # o video-fonte nao e copiado
        copia = set(os.listdir(projeto.pasta(e["nome"])))
        assert {"narracao.wav", "legenda_cartoes.json", "cache"} <= copia
        assert not copia & {"RASCUNHO_x.mp4", "FINAL_x.mp4", "quadros"}
        assert os.path.isfile(os.path.join(projeto.pasta(e["nome"]), "cache", "f1", "c000.jpg"))
        assert cli.post(f"/api/projetos/{e['nome']}/duplicar", json={}).json()["nome"] == f"{n}-c"   # a partir da -b
        assert cli.post(f"/api/projetos/{n}/duplicar", json={"nome": f"{n}-b"}).status_code == 409
        assert projeto.carregar(n)["aprovacao"]["aprovado_hash"] == "a"            # o original nao muda
    finally:
        import shutil
        for sufixo in ("-b", "-c"):
            shutil.rmtree(projeto.pasta(n + sufixo), ignore_errors=True)


@pytest.mark.lento
def test_versao_sem_audio_de_um_video_pronto(projeto_base):
    n, cli = projeto_base["nome"], _cli()
    d = projeto.pasta(n)
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=2", "-f", "lavfi", "-i", "sine=f=440:d=2",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
           os.path.join(d, "RASCUNHO_teste.mp4"))
    r = cli.post(f"/api/projetos/{n}/exportar_sem_audio", json={"arquivo": "RASCUNHO_teste.mp4"}).json()
    assert r["saida"] == "RASCUNHO_teste_sem_audio.mp4" and r["saida"] in r["estado"]["saidas"]
    s = sonda(os.path.join(d, r["saida"]))
    assert not s["audio"] and abs(s["dur"] - 2.0) < 0.1 and (s["w"], s["h"]) == (1080, 1920)
    for ruim in ("RASCUNHO_teste_sem_audio.mp4", "../projeto.json", "proxy.mp4", "RASCUNHO_nao_existe.mp4"):
        assert cli.post(f"/api/projetos/{n}/exportar_sem_audio", json={"arquivo": ruim}).status_code == 400, ruim
    um = render.exportar_1x1(projeto.carregar(n), r["saida"])                 # a 1:1 da sem audio continua sem audio
    assert not sonda(um)["audio"]


def test_interface_tem_os_controles_novos():
    html = open(os.path.join(ESTATICO, "index.html"), encoding="utf-8").read()
    for id_ in ("tlv-congelar", "tlv-loop", "duplicar-projeto", "exportar-sem-audio", "revisar-mudo", "dica-mudo"):
        assert f'id="{id_}"' in html, id_
