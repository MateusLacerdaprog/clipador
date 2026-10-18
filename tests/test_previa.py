"""Fluxo previa -> gravar narracao -> assistir: o que quebrava e foi corrigido.

- a previa (proxy.mp4) sabe se esta em dia com a montagem (proxy_atual) e o player nao recarrega a cada redesenho;
- o render nao apaga edicoes feitas enquanto ele roda;
- analisar momentos nao invalida a aprovacao;
- a gravacao do navegador (webm/opus) vira narracao.wav.
"""
import os
import re

import pytest
from fastapi.testclient import TestClient

from clipador.core import projeto, render
from clipador.web.app import app
from conftest import ffmpeg, js_da_interface, sonda

JS = js_da_interface()


def _cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


@pytest.mark.lento
def test_previa_sabe_se_esta_em_dia_com_a_montagem(projeto_base):
    n = projeto_base["nome"]
    cli = _cli()
    assert cli.get(f"/api/projetos/{n}").json()["proxy_atual"] is False
    render.render(projeto.carregar(n), "proxy")
    e = cli.get(f"/api/projetos/{n}").json()
    assert e["tem_proxy"] and e["proxy_atual"] and isinstance(e["proxy_versao"], int)
    s = sonda(os.path.join(projeto.pasta(n), "proxy.mp4"))
    assert (s["w"], s["h"]) == (540, 960) and s["audio"] and abs(s["dur"] - 6.0) < 0.15
    # narracao e roteiro nao mudam a imagem da previa
    cli.put(f"/api/projetos/{n}", json={"roteiro": "outro roteiro"})
    assert cli.get(f"/api/projetos/{n}").json()["proxy_atual"] is True
    # mudar a montagem deixa a previa desatualizada
    p = projeto.carregar(n)
    cli.put(f"/api/projetos/{n}", json={"segmentos": p["segmentos"][:1]})
    assert cli.get(f"/api/projetos/{n}").json()["proxy_atual"] is False


@pytest.mark.lento
def test_render_nao_apaga_edicao_feita_durante_ele(projeto_base):
    n = projeto_base["nome"]
    velho = projeto.carregar(n)                      # copia que o render recebe ao comecar
    no_disco = projeto.carregar(n)
    no_disco["roteiro"] = "editado enquanto o render rodava"
    projeto.salvar(no_disco)
    render.render(velho, "rascunho")
    depois = projeto.carregar(n)
    assert depois["roteiro"] == "editado enquanto o render rodava"
    assert depois["aprovacao"]["rascunho_hash"] == projeto.hash_conteudo(velho)


def test_analisar_momentos_nao_invalida_aprovacao(projeto_base):
    p = projeto.carregar(projeto_base["nome"])
    h = projeto.hash_conteudo(p)
    p["fontes"][0]["destaques"] = {"duracao": 5, "lista": [{"ini": 1, "fim": 6}]}
    assert projeto.hash_conteudo(p) == h and projeto.hash_previa(p) == projeto.hash_previa(projeto_base)


def test_gravacao_do_navegador_webm_opus_vira_narracao(projeto_base, tmp_path):
    webm = str(tmp_path / "narracao.webm")
    ffmpeg("-f", "lavfi", "-i", "sine=f=300:d=2.5", "-c:a", "libopus", "-b:a", "96k", webm)
    with open(webm, "rb") as f:
        r = _cli().post(f"/api/projetos/{projeto_base['nome']}/narracao", files={"arquivo": ("narracao.webm", f, "audio/webm")})
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["narracao"] == "narracao.wav" and abs(e["narracao_dur"] - 2.5) < 0.1


def test_player_da_previa_nao_recarrega_a_cada_redesenho():
    corpo = JS[JS.index("function renderNarracao"):JS.index("const urlProxy")]
    assert 'arq("proxy.mp4")' not in corpo, "arq() poe Date.now() na URL: o player recarregava e voltava ao zero"
    assert "dataset.versao !== chave" in corpo
    assert re.search(r"sincronizarNarracao", JS) and "audioSync.pause(); $(\"#com-narracao\").checked = false" in JS
