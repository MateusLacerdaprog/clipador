"""Presets de legenda por plataforma, visual personalizado, tempo por palavra e exportacao SRT."""
import json
import os
import re
import shutil

import pytest
from fastapi.testclient import TestClient

from clipador.core import legendas, projeto, render
from clipador.web.app import app


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _cartoes(n=3):
    out, t = [], 0.5
    for k in range(n):
        ps = []
        for w in ("palavra", "de", f"teste{k}"):
            ps.append({"w": w, "start": round(t, 2), "end": round(t + 0.3, 2)})
            t += 0.35
        out.append({"palavras": ps})
        t += 0.4
    return out


@pytest.fixture()
def com_legenda(projeto_base, midia):
    p = projeto_base
    d = projeto.pasta(p["nome"])
    shutil.copy(midia["voz"], os.path.join(d, "narracao.wav"))
    p["narracao"] = "narracao.wav"
    projeto.salvar(p)
    with open(os.path.join(d, "legenda_cartoes.json"), "w", encoding="utf-8") as f:
        json.dump(_cartoes(), f)
    return projeto.carregar(p["nome"])


@pytest.mark.parametrize("pid", ["shorts", "tiktok", "reels"])
def test_preset_plataforma_muda_estilo_posicao_e_cores(cli, com_legenda, pid):
    nome = com_legenda["nome"]
    p = cli.post(f"/api/projetos/{nome}/legendas/plataforma/{pid}").json()
    pr = legendas.PLATAFORMAS[pid]
    L = p["legenda"]
    assert L["plataforma"] == pid and L["estilo"] == pr["estilo"] and L["destaque"] == pr["destaque"]
    assert L["pos_y"] == pr["legenda_y"]["tela_cheia"]            # projeto_base usa tela cheia
    render.preparar_ass(projeto.carregar(nome))
    ass = open(os.path.join(projeto.pasta(nome), "legenda.ass"), encoding="utf-8").read()
    bgr = pr["destaque"][5:7] + pr["destaque"][3:5] + pr["destaque"][1:3]
    assert f"\\c&H{bgr.upper()}&" in ass and f",{pr['legenda_y']['tela_cheia']})" in ass
    assert ("\\t(0,120" in ass) == (pr["animacao"] == "pop")


def test_presets_diferem_entre_si():
    ys = {pid: p["legenda_y"]["tela_cheia"] for pid, p in legendas.PLATAFORMAS.items()}
    assert len(set(ys.values())) == 3 and ys["tiktok"] < ys["shorts"]   # TikTok tem mais interface embaixo


def test_visual_personalizado_validado(cli, com_legenda):
    nome = com_legenda["nome"]
    ok = cli.put(f"/api/projetos/{nome}", json={"legenda": {"estilo": "karaoke", "fonte": "Impact", "tamanho": 70,
                                                          "cor": "#00FF00", "destaque": "#FF0000"}})
    assert ok.status_code == 200
    render.preparar_ass(projeto.carregar(nome))
    ass = open(os.path.join(projeto.pasta(nome), "legenda.ass"), encoding="utf-8").read()
    assert "Style: Leg,Impact,70,&H0000FF00" in ass and "\\c&H0000FF&" in ass
    for ruim in ({"cor": "verde"}, {"fonte": "C:/x.ttf"}, {"tamanho": 999}, {"animacao": "explodir"}):
        assert cli.put(f"/api/projetos/{nome}", json={"legenda": {"estilo": "karaoke", **ruim}}).status_code == 400


def test_editar_tempo_por_palavra(cli, com_legenda):
    nome = com_legenda["nome"]
    cart = cli.get(f"/api/projetos/{nome}/legendas").json()
    ps = cart[1]["palavras"]
    novas = [{"w": ps[0]["w"], "start": ps[0]["start"] + 0.04, "end": ps[0]["end"] + 0.04}] + ps[1:]
    r = cli.put(f"/api/projetos/{nome}/legendas/cartao/1", json={"palavras": novas})
    assert r.status_code == 200 and r.json()[1]["palavras"][0]["start"] == round(ps[0]["start"] + 0.04, 3)
    # erros: fora de ordem, invadindo o proximo cartao, palavra vazia
    ruim1 = [{"w": "a", "start": 2.0, "end": 2.3}, {"w": "b", "start": 1.9, "end": 2.4}]
    ruim2 = [{"w": "a", "start": ps[0]["start"], "end": 99}]
    ruim3 = [{"w": "", "start": ps[0]["start"], "end": ps[0]["end"]}]
    for ruim in (ruim1, ruim2, ruim3):
        assert cli.put(f"/api/projetos/{nome}/legendas/cartao/1", json={"palavras": ruim}).status_code == 400
    assert cli.put(f"/api/projetos/{nome}/legendas/cartao/9", json={"palavras": novas}).status_code == 400


def test_exportar_srt_com_deslocamento_e_sem_sobreposicao(cli, com_legenda):
    nome = com_legenda["nome"]
    cli.put(f"/api/projetos/{nome}", json={"audio": {"narracao": {"deslocamento": 1.0}}})
    r = cli.get(f"/api/projetos/{nome}/legendas.srt")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    blocos = r.text.strip().split("\n\n")
    assert len(blocos) == 3 and blocos[0].splitlines()[0] == "1"
    tempos = [re.findall(r"(\d\d):(\d\d):(\d\d),(\d{3})", b.splitlines()[1]) for b in blocos]
    seg = lambda t: int(t[0]) * 3600 + int(t[1]) * 60 + int(t[2]) + int(t[3]) / 1000  # noqa: E731
    ini0 = seg(tempos[0][0])
    assert abs(ini0 - 1.5) < 0.01                       # 0.5 s + 1.0 s de deslocamento
    for a, b in zip(tempos, tempos[1:]):
        assert seg(a[1]) <= seg(b[0])                   # sem sobreposicao
    assert blocos[2].splitlines()[2] == "palavra de teste2"


def test_srt_sem_legenda_da_404(cli, projeto_base):
    assert cli.get(f"/api/projetos/{projeto_base['nome']}/legendas.srt").status_code == 404

