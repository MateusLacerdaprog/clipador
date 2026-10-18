"""Comparacao A x B (tela dividida com DOIS videos, sem camera): formato proprio, video A em cima e B embaixo,
"Montar comparacao", som de A/B/ambos, linha divisoria, rotulos padrao e validacao.

Tudo com video e audio REAIS do FFmpeg: A vermelho com tom de 440 Hz, B azul com tom de 2000 Hz; a cor de cada
metade e a frequencia do som sao medidas no resultado.
"""
import os
import re
import subprocess
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from clipador.core import formatos, projeto, render
from clipador.web.app import app
from conftest import ffmpeg, sonda


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


@pytest.fixture(scope="module")
def videos(tmp_path_factory):
    d = tmp_path_factory.mktemp("cmp")
    a, b = str(d / "gta5_vermelho.mp4"), str(d / "gta6_azul.mp4")
    ffmpeg("-f", "lavfi", "-i", "color=c=red:s=1280x720:r=30:d=8", "-f", "lavfi", "-i", "sine=f=440:d=8",
           "-af", "volume=4", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", a)
    ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=1920x1080:r=30:d=5", "-f", "lavfi", "-i", "sine=f=2000:d=5",
           "-af", "volume=4", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", b)
    return a, b


def _esperar(cli, t):
    for _ in range(600):
        e = cli.get(f"/api/tarefas/{t['id']}").json()
        if e["estado"] in ("ok", "erro"):
            return e
        time.sleep(0.25)
    raise AssertionError("tarefa nao terminou")


def _rgb(png):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", png, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(1920, 1080, 3).astype(int)


def _nivel(arquivo, freq):
    """Volume medio (dBFS) so na faixa de `freq` Hz."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", arquivo, "-af",
                        f"bandpass=f={freq}:w=150,volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"mean_volume: (-?[\d.]+|-inf)", r.stderr)
    return float(m.group(1)) if m else float("-inf")


def test_formato_comparacao_so_no_curto(cli):
    curto = [f["id"] for f in formatos.catalogo()["curto"]]
    assert "comparacao" in curto and "comparacao" not in [f["id"] for f in formatos.catalogo()["longo"]]
    assert cli.post("/api/projetos", json={"nome": "t-cmp-longo", "tipo": "longo", "formato": "comparacao"}).status_code == 400
    p = cli.post("/api/projetos", json={"nome": "t-cmp-formato", "tipo": "curto", "formato": "comparacao"}).json()
    assert p["layout"] == "comparacao" and p["comparacao"]["fonte_a"] is None
    assert p["gancho"]["texto"] == ""                                      # o formato so SUGERE o titulo
    assert cli.get("/api/projetos/t-cmp-formato/guia").json()["sugestao_gancho"] == "GTA 5 × GTA 6"


@pytest.mark.lento
def test_comparacao_real_a_em_cima_b_embaixo_som_e_validacao(cli, videos):
    n = "t-cmp-real"
    cli.post("/api/projetos", json={"nome": n, "tipo": "curto", "formato": "comparacao"})
    for v in videos:                                   # o 1o video vira o A, o 2o o B (sozinho)
        assert _esperar(cli, cli.post(f"/api/projetos/{n}/fontes/caminho", json={"caminho": v}).json())["estado"] == "ok"
    p = cli.get(f"/api/projetos/{n}").json()
    fa, fb = (f["id"] for f in p["fontes"])
    assert (p["comparacao"]["fonte_a"], p["comparacao"]["fonte_b"]) == (fa, fb)

    # validacao
    for ruim in ({"fonte_a": "nao-existe"}, {"audio": "xx"}):
        assert cli.put(f"/api/projetos/{n}", json={"comparacao": ruim}).status_code == 400
    assert cli.put(f"/api/projetos/{n}", json={"comparacao": {"rotulo_a": "GTA 5", "rotulo_b": "GTA 6" * 20}}).json()[
        "comparacao"]["rotulo_b"] == ("GTA 6" * 20)[:30]
    cli.put(f"/api/projetos/{n}", json={"comparacao": {"rotulo_b": "GTA 6"}})

    # timeline vazia: "Montar" cria um trecho que cabe nos DOIS videos (B tem 5 s)
    r = cli.post(f"/api/projetos/{n}/comparacao/montar", json={}).json()
    s = r["segmentos"][0]
    assert (s["fonte"], s["fonte_b"], s["ini"], s["ini_b"], s["fim"]) == (fa, fb, 0.0, 0.0, 5.0)
    # trecho novo (sem dizer o B) ja entra com o video B; B que passa do fim do video B e recusado
    segs = r["segmentos"] + [{"fonte": fa, "ini": 6.0, "fim": 7.5}]
    novo = cli.put(f"/api/projetos/{n}", json={"segmentos": segs}).json()["segmentos"][1]
    assert novo["fonte_b"] == fb and novo["ini_b"] == 3.5                  # 5 s - 1,5 s: cabe no B
    ruim = segs[:1] + [{**novo, "ini_b": 4.0}]
    assert cli.put(f"/api/projetos/{n}", json={"segmentos": ruim}).status_code == 400
    cli.put(f"/api/projetos/{n}", json={"segmentos": r["segmentos"]})

    # quadro real: metade de cima vermelha (A), de baixo azul (B), linha branca no meio, rotulos desenhados
    pr = projeto.carregar(n)
    img = _rgb(os.path.join(projeto.pasta(n), render.quadros(pr, [2.0])[0]))
    cima, baixo, linha = img[200:800, 100:980].mean(axis=(0, 1)), img[1100:1800, 100:980].mean(axis=(0, 1)), img[958:962, 300:700].mean(axis=(0, 1))
    assert cima[0] > 180 and cima[2] < 80, cima
    assert baixo[2] > 180 and baixo[0] < 80, baixo
    assert linha.min() > 200, linha
    ass = open(os.path.join(projeto.pasta(n), "legenda.ass"), encoding="utf-8-sig").read()
    assert "GTA 5" in ass and "GTA 6" in ass

    # sem linha e com A/B trocados: a cor de cada metade troca
    cli.put(f"/api/projetos/{n}", json={"comparacao": {"divisoria": False}})
    segs = [{**r["segmentos"][0], "fonte": fb, "fonte_b": fa}]
    cli.put(f"/api/projetos/{n}", json={"segmentos": segs})
    img = _rgb(os.path.join(projeto.pasta(n), render.quadros(projeto.carregar(n), [2.0])[0]))
    assert img[200:800, 100:980].mean(axis=(0, 1))[2] > 180 and img[1100:1800, 100:980].mean(axis=(0, 1))[0] > 180
    assert img[958:962, 300:700].mean() < 200                              # sem linha branca
    cli.put(f"/api/projetos/{n}", json={"segmentos": r["segmentos"]})

    # som: so A (440 Hz), so B (2000 Hz) ou os dois — medido no RASCUNHO
    niveis = {}
    for modo in ("a", "b", "ambos"):
        cli.put(f"/api/projetos/{n}", json={"comparacao": {"audio": modo}})
        saida = render.render(projeto.carregar(n), "rascunho")
        assert abs(sonda(saida)["dur"] - 5.0) < 0.1 and (sonda(saida)["w"], sonda(saida)["h"]) == (1080, 1920)
        niveis[modo] = (_nivel(saida, 440), _nivel(saida, 2000))
    a440, a2k = niveis["a"]
    b440, b2k = niveis["b"]
    m440, m2k = niveis["ambos"]
    assert a440 > a2k + 15 and b2k > b440 + 15, niveis                    # cada um so com o seu tom
    assert m440 > b440 + 15 and m2k > a2k + 15, niveis                    # ambos: os dois tons

    # remover um video da comparacao (fora de uso) limpa a referencia
    cli.put(f"/api/projetos/{n}", json={"segmentos": []})
    est = cli.delete(f"/api/projetos/{n}/fontes/{fb}").json()
    assert est["comparacao"]["fonte_b"] is None
    assert cli.post(f"/api/projetos/{n}/comparacao/montar", json={}).status_code == 400


@pytest.mark.lento
def test_b_mais_curto_que_o_trecho_congela_em_vez_de_quebrar(cli, videos, projeto_base):
    n = projeto_base["nome"]
    p = projeto.carregar(n)
    from clipador.core import midia
    p["fontes"].append({"id": "b", "caminho": videos[1], "nome": "b.mp4", "info": midia.info(videos[1]), "crop": None, "cenas": []})
    p["layout"] = "comparacao"
    p["segmentos"] = [{"id": "x", "fonte": "f1", "ini": 1.0, "fim": 4.0, "foco_x": 0.5, "zoom": 1.0, "fonte_b": "b", "ini_b": 4.0}]
    projeto.salvar(p)                                  # gravado direto (ex.: projeto antigo): B so tem 1 s ali
    saida = render.render(projeto.carregar(n), "rascunho")
    assert abs(sonda(saida)["dur"] - 3.0) < 0.1


def test_hash_de_projeto_que_nao_e_comparacao_nao_muda(projeto_base):
    p = projeto.carregar(projeto_base["nome"])
    h = projeto.hash_conteudo(p)
    p["comparacao"]["rotulo_a"] = "outro"
    assert projeto.hash_conteudo(p) == h
    p["layout"] = "comparacao"
    h2 = projeto.hash_conteudo(p)
    p["comparacao"]["rotulo_a"] = "mais um"
    assert projeto.hash_conteudo(p) != h2
