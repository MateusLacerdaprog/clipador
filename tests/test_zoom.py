"""Zoom por trecho: curvas, limites, compatibilidade com o zoom antigo, render real (posicao medida), empilhado,
sugestao so nos picos de acao."""
import os
import subprocess

import numpy as np
import pytest
from fastapi.testclient import TestClient

from clipador.core import midia, projeto, render, zoom
from clipador.web.app import app
from conftest import ffmpeg


def test_curvas_e_limites():
    fx = zoom.efeito({"zoom_fx": zoom.validar({"preset": "impacto", "inicio": 1.0})}, 4.0)
    assert zoom.z_em(fx, 0.9) == 1.0 and abs(zoom.z_em(fx, 1.0 + fx["duracao"]) - 1.45) < 1e-9
    assert zoom.z_em(fx, 1.05) > 1.0 + 0.45 * 0.5          # "rapida": passa da metade antes da metade do tempo
    r = zoom.efeito({"zoom_fx": zoom.validar({"preset": "reacao", "inicio": 0.5})}, 3.0)
    meio = r["inicio"] + r["duracao"] + r["segura"] / 2
    assert abs(zoom.z_em(r, meio) - 1.3) < 1e-9 and zoom.z_em(r, 2.99) == pytest.approx(1.0, abs=1e-6)  # entra e volta
    # 'reacao' num trecho curto: entrada + saida cabem no trecho (sem ficar preso no zoom)
    c = zoom.efeito({"zoom_fx": zoom.validar({"preset": "reacao"})}, 0.6)
    assert 2 * c["duracao"] + c["segura"] <= 0.6 + 1e-9
    # 'lento' = trecho todo; inicio fora do trecho e puxado para dentro
    lento = zoom.efeito({"zoom_fx": zoom.validar({"preset": "lento"})}, 5.0)
    assert lento["duracao"] == 5.0 and zoom.efeito({"zoom_fx": zoom.validar({"preset": "destaque", "inicio": 99})}, 2)["inicio"] < 2


def test_validacao_e_zoom_antigo_continua_funcionando():
    assert zoom.validar(None) is None and zoom.validar({"preset": "nenhum"}) is None
    for ruim in ({"preset": "xx"}, {"preset": "impacto", "intensidade": 5}, {"preset": "personalizado", "curva": "doida"},
                 {"preset": "destaque", "foco_x": 2}):
        with pytest.raises(ValueError):
            zoom.validar(ruim)
    fx = zoom.efeito({"zoom": 1.2}, 4.0)                    # projeto antigo: "zoom final 1.2"
    assert fx["preset"] == "lento" and fx["intensidade"] == 1.2 and fx["duracao"] == 4.0
    assert zoom.efeito({"zoom": 1.0}, 4.0) is None


@pytest.fixture(scope="module")
def ponto(tmp_path_factory):
    """1920x1080 cinza com um ponto branco em (1010, 440): no recorte 9:16 central ele cai fora do centro."""
    v = str(tmp_path_factory.mktemp("zoom") / "ponto.mp4")
    ffmpeg("-f", "lavfi", "-i", "color=c=0x606060:s=1920x1080:r=30:d=4", "-vf",
           "drawbox=x=1004:y=434:w=12:h=12:color=white:t=fill", "-c:v", "libx264", "-preset", "ultrafast",
           "-crf", "10", "-pix_fmt", "yuv420p", v)
    return v


def _centro_do_ponto(png):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", png, "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    q = np.frombuffer(raw, np.uint8).reshape(1920, 1080).astype(float)
    m = np.clip(q - 140, 0, None)
    ys, xs = np.indices(m.shape)
    return (xs * m).sum() / m.sum(), (ys * m).sum() / m.sum(), q


@pytest.mark.lento
def test_render_real_zoom_em_volta_do_ponto_escolhido(projeto_base, ponto):
    n = projeto_base["nome"]
    p = projeto.carregar(n)
    p["fontes"] = [{"id": "z", "caminho": ponto, "nome": "ponto.mp4", "info": midia.info(ponto), "crop": None, "cenas": []}]
    p["layout"] = "tela_cheia"
    p["segmentos"] = [{"id": "a", "fonte": "z", "ini": 0.0, "fim": 4.0, "foco_x": 0.5, "zoom": 1.0,
                       "zoom_fx": zoom.validar({"preset": "impacto", "inicio": 1.0, "foco_x": 0.5, "foco_y": 0.45})}]
    projeto.salvar(p)
    q = render.quadros(projeto.carregar(n), [0.5, 2.5])
    (x0, y0, _), (x1, y1, img) = (_centro_do_ponto(os.path.join(projeto.pasta(n), f)) for f in q)
    # sem zoom: regiao 608x1080 (x 656..1264) ampliada 1080/608 -> ponto em ~(629, 782)
    assert abs(x0 - (1010 - 656) * 1080 / 608) < 3 and abs(y0 - 440 * 1920 / 1080) < 3, (x0, y0)
    # no auge (1.45x) em volta do ponto (540, 864): pos = ancora + (pos - ancora) * 1.45
    ex, ey = 540 + (x0 - 540) * 1.45, 864 + (y0 - 864) * 1.45
    assert abs(x1 - ex) < 3 and abs(y1 - ey) < 3, ((x1, y1), (ex, ey))
    assert min(img[0, 0], img[0, -1], img[-1, 0], img[-1, -1]) > 60      # sem borda preta nos cantos


@pytest.mark.lento
def test_empilhado_aplica_o_zoom_so_no_bloco(projeto_base, ponto):
    n = projeto_base["nome"]
    p = projeto.carregar(n)
    p["fontes"] = [{"id": "z", "caminho": ponto, "nome": "ponto.mp4", "info": midia.info(ponto), "crop": None, "cenas": []}]
    p["layout"] = "empilhado"
    p["segmentos"] = [{"id": "a", "fonte": "z", "ini": 0.0, "fim": 3.0, "foco_x": 0.5, "zoom": 1.0,
                       "zoom_fx": zoom.validar({"preset": "impacto", "inicio": 0.5})}]
    projeto.salvar(p)
    cmd, _, _ = render.montar_comando(projeto.carregar(n), "rascunho")
    grafo = cmd[cmd.index("-filter_complex") + 1]
    bloco = grafo.split("crop=1080:864")[1].split(";")[0]
    assert "perspective" in bloco and grafo.count("perspective") == 1      # so no bloco nitido, nao no fundo
    assert render.render(projeto.carregar(n), "rascunho")                  # e o FFmpeg aceita o grafo


def test_api_valida_e_sugere_zoom_so_no_pico(projeto_base, tmp_path):
    v = str(tmp_path / "acao.mp4")                                         # acao (bloco mexendo + estalos) em 18-24 s
    ffmpeg("-f", "lavfi", "-i", "color=c=0x404040:s=1280x720:r=30:d=30", "-f", "lavfi", "-i",
           "aevalsrc='0.02*sin(2*PI*220*t)+if(between(t,18,24)*lt(mod(t,0.25),0.06),0.8*(random(0)*2-1),0)':s=44100:d=30",
           "-f", "lavfi", "-i", "color=c=white:s=120x120:r=30:d=30",
           "-filter_complex", "[0:v][2:v]overlay=x=1050:y='mod(t*900,600)':enable='between(t,18,24)'[v]",
           "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
           "-shortest", v)
    n = projeto_base["nome"]
    p = projeto.carregar(n)
    p["fontes"] = [{"id": "f", "caminho": v, "nome": "acao.mp4", "info": midia.info(v), "crop": None, "cenas": []}]
    p["layout"] = "tela_cheia"
    p["segmentos"] = [{"id": "q", "fonte": "f", "ini": 3.0, "fim": 9.0, "foco_x": 0.5, "zoom": 1.0},
                      {"id": "a", "fonte": "f", "ini": 16.0, "fim": 22.0, "foco_x": 0.5, "zoom": 1.0}]
    projeto.salvar(p)
    cli = TestClient(app, base_url="http://127.0.0.1:8765")
    seg_ruim = [{**p["segmentos"][0], "zoom_fx": {"preset": "impacto", "intensidade": 9}}]
    assert cli.put(f"/api/projetos/{n}", json={"segmentos": seg_ruim}).status_code == 400
    r = cli.post(f"/api/projetos/{n}/zoom/sugerir").json()
    assert [s["trecho"] for s in r["sugeridos"]] == [2]                     # so o trecho com acao
    fx = r["segmentos"][1]["zoom_fx"]
    assert fx["preset"] == "impacto" and 1.8 <= fx["inicio"] <= 5.9          # dentro da acao (18-22 s = 2-6 s no trecho)
    assert "zoom_fx" not in r["segmentos"][0]
