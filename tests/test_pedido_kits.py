"""Clipar por pedido, editar pela transcricao, kit do canal (logo) e versao 1:1.

A transcricao REAL usa fala sintetizada pela voz pt-BR do Windows (SAPI) + Whisper local; se a voz nao existir,
esse teste e pulado. Os demais testes de busca usam palavras com tempo escritas a mao (o que se testa e a busca).
"""
import json
import os
import subprocess
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from clipador.core import kits, midia, pedido, projeto, render
from clipador.core import timeline as tl
from clipador.web.app import app
from conftest import ffmpeg, sonda


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _esperar(cli, t):
    for _ in range(600):
        e = cli.get(f"/api/tarefas/{t['id']}").json()
        if e["estado"] in ("ok", "erro"):
            return e
        time.sleep(0.25)
    raise AssertionError("tarefa nao terminou")


def _pal(*itens):
    return [{"w": w, "start": t, "end": t + 0.3} for t, w in itens]


FALA = _pal((3, "olha"), (10, "o"), (10.4, "Jason"), (11, "chegando"), (25, "nada"), (40, "Jason"),
            (40.6, "roubou"), (41.2, "o"), (41.5, "carro"), (55, "fim"))


# ------------------------------------------------------------------ busca
def test_termos_sem_acento_e_sem_palavras_vazias():
    assert pedido.termos("Mostra o momento das Explosões no carro do Jason!") == ["explosoes", "carro", "jason"]
    assert pedido._casa("explosao", "explosoes") and not pedido._casa("explicacao", "explosoes")


def test_busca_prioriza_trecho_com_mais_termos_e_nao_sobrepoe():
    ms = pedido.buscar(FALA, "Jason com o carro", 60, duracao=8, quantidade=3, cortes=[37.5, 39.0])
    assert len(ms) == 2
    a, b = ms
    assert a["ini"] <= 40 < a["fim"] and a["ini"] <= 41.5 < a["fim"] and a["nota"] > b["nota"]
    assert a["ini"] == 37.5                                   # abre no corte de cena antes da fala
    assert b["ini"] <= 10.4 < b["fim"] and "carro" in b["alertas"][0]
    assert "Jason" in a["motivos"][0] and a["fim"] <= b["ini"] or b["fim"] <= a["ini"]
    assert pedido.buscar(FALA, "helicóptero", 60) == []
    with pytest.raises(ValueError):
        pedido.buscar(FALA, "o de", 60)


def test_resposta_da_ia_e_validada_e_prompt_nao_envia_video():
    dados = {"momentos": [{"ini": 5, "fim": 20, "porque": "fala do Jason"}, {"ini": 10, "fim": 15, "porque": "sobrepõe"},
                          {"ini": 50, "fim": 999, "porque": "passa do fim"}, {"ini": "x", "fim": 3, "porque": "lixo"},
                          {"ini": 30, "fim": 31, "porque": "curto demais"}], "observacao": "ok"}
    v = pedido.validar_ia(dados, 60, 15)
    assert [(m["ini"], m["fim"]) for m in v] == [(5, 20), (50, 60)] and v[0]["motivos"][0].startswith("IA:")
    fonte = {"nome": "jogo.mp4", "info": {"dur": 60}}
    pr = pedido.prompt_ia("o Jason no carro", fonte, FALA, [], 15, 3)
    assert "NÃO vê a imagem" in pr and "[0:40] Jason roubou o carro" in pr and "o Jason no carro" in pr


# ------------------------------------------------------------------ API pedido + editar pela transcricao
def _escrever_transcricao(nome, fonte, palavras):
    c = pedido.caminho_cache(projeto.pasta(nome), fonte["id"])
    os.makedirs(os.path.dirname(c), exist_ok=True)
    with open(c, "w", encoding="utf-8") as f:
        json.dump({"assinatura": pedido._assinatura(fonte["caminho"]), "palavras": palavras}, f)


def test_api_pedido_local_previa_ia_e_sem_provedor(cli, projeto_base):
    n = projeto_base["nome"]
    corpo = {"texto": "Jason", "duracao": 5, "quantidade": 2}
    assert cli.post(f"/api/projetos/{n}/fontes/f1/pedido", json=corpo).status_code == 400   # sem transcricao
    _escrever_transcricao(n, projeto_base["fontes"][0], _pal((2, "o"), (2.3, "Jason"), (7, "voltou")))
    r = cli.post(f"/api/projetos/{n}/fontes/f1/pedido", json=corpo).json()
    D = r["fontes"][0]["destaques"]
    assert r["encontrados"] == 1 and D["pedido"] == "Jason" and D["lista"][0]["ini"] <= 2.3 < D["lista"][0]["fim"]
    assert cli.post(f"/api/projetos/{n}/fontes/f1/destaques/aplicar", json={"indice": 0}).status_code == 200
    # previa mostra o texto e nao envia nada; sem provedor ativo a tarefa falha com mensagem clara
    pv = cli.post(f"/api/projetos/{n}/fontes/f1/pedido/previa", json={**corpo, "modo": "ia"}).json()
    assert pv["envia_midia"] is False and "Jason" in pv["prompt"]
    t = cli.post(f"/api/projetos/{n}/fontes/f1/pedido", json={**corpo, "modo": "ia"}).json()
    e = _esperar(cli, t)
    assert e["estado"] == "erro" and "provedor" in e["erro"]
    assert cli.post(f"/api/projetos/{n}/fontes/f1/pedido", json={**corpo, "modo": "xx"}).status_code == 400
    # transcricao velha (video mudou) e ignorada
    c = pedido.caminho_cache(projeto.pasta(n), "f1")
    d = json.load(open(c, encoding="utf-8"))
    d["assinatura"][1] += 1
    json.dump(d, open(c, "w", encoding="utf-8"))
    assert cli.get(f"/api/projetos/{n}/fontes/f1/transcricao").json()["palavras"] is None


def test_cortar_intervalo_unidade():
    p = {"segmentos": [{"id": "a", "fonte": "f", "ini": 0.0, "fim": 10.0, "rotulo": "Top 1", "ini_b": 100.0}]}
    sel = tl.cortar_intervalo(p, 0, 3.0, 4.5)
    a, b = p["segmentos"]
    assert (a["ini"], a["fim"], b["ini"], b["fim"]) == (0.0, 3.0, 4.5, 10.0) and sel == 0
    assert a["rotulo"] == "Top 1" and "rotulo" not in b and b["ini_b"] == 104.5 and a["id"] != b["id"]
    tl.cortar_intervalo(p, 1, 4.4, 4.6)                       # sobra < 0,2 s no comeco some junto
    assert p["segmentos"][1]["ini"] == 4.6
    tl.cortar_intervalo(p, 0, 0, 3)                           # trecho inteiro: removido
    assert len(p["segmentos"]) == 1
    with pytest.raises(tl.ErroTimeline):
        tl.cortar_intervalo(p, 0, 20, 30)


def test_api_editar_pela_transcricao(cli, projeto_base):
    n = projeto_base["nome"]                                  # trechos 1-4 s e 6-9 s da fonte
    _escrever_transcricao(n, projeto_base["fontes"][0],
                          _pal((1.2, "bom"), (2.0, "tipo"), (2.4, "assim"), (3.0, "olha"), (6.5, "agora")))
    tr = cli.get(f"/api/projetos/{n}/transcricao_timeline").json()["trechos"]
    assert [w["w"] for w in tr[0]["palavras"]] == ["bom", "tipo", "assim", "olha"] and tr[1]["palavras"][0]["w"] == "agora"
    total = cli.get(f"/api/projetos/{n}").json()["duracao"]
    r = cli.post(f"/api/projetos/{n}/timeline", json={"op": "cortar_intervalo", "i": 0, "ini": 2.0, "fim": 2.7}).json()
    assert len(r["segmentos"]) == 3 and abs(r["duracao"] - (total - 0.7)) < 0.01
    assert [w["w"] for t in cli.get(f"/api/projetos/{n}/transcricao_timeline").json()["trechos"]
            for w in t["palavras"]] == ["bom", "olha", "agora"]


@pytest.mark.lento
@pytest.mark.skipif(os.name != "nt", reason="voz do Windows")
def test_transcricao_real_com_whisper(cli, projeto_base, tmp_path):
    wav = str(tmp_path / "fala.wav")
    frase = "Agora o Jason pegou o carro e fugiu da polícia em Vice City."
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$v = $s.GetInstalledVoices() | ? { $_.VoiceInfo.Culture.Name -eq 'pt-BR' } | select -First 1; "
          "if (-not $v) { exit 3 }; $s.SelectVoice($v.VoiceInfo.Name); "
          f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('{frase}'); $s.Dispose()")
    if subprocess.run(["powershell", "-NoProfile", "-Command", ps]).returncode != 0:
        pytest.skip("sem voz pt-BR no Windows")
    video = str(tmp_path / "com_fala.mp4")                    # 3 s de silencio + fala
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=10", "-i", wav, "-filter_complex",
           "[1:a]adelay=3000|3000,apad[a]", "-map", "0:v", "-map", "[a]", "-t", "10", "-c:v", "libx264",
           "-preset", "ultrafast", "-c:a", "aac", video)
    n = projeto_base["nome"]
    p = projeto.carregar(n)
    p["fontes"].append({"id": "fz", "caminho": video, "nome": "com_fala.mp4", "info": midia.info(video),
                        "crop": None, "cenas": []})
    projeto.salvar(p)
    e = _esperar(cli, cli.post(f"/api/projetos/{n}/fontes/fz/transcrever").json())
    assert e["estado"] == "ok", e
    pal = cli.get(f"/api/projetos/{n}/fontes/fz/transcricao").json()["palavras"]
    j = [w for w in pal if pedido.norm(w["w"]).startswith("jason")]
    assert j and 3.0 < j[0]["start"] < 6.5, pal               # tempo real da palavra (fala comeca em 3 s)
    r = cli.post(f"/api/projetos/{n}/fontes/fz/pedido", json={"texto": "Jason e a polícia", "duracao": 5}).json()
    assert r["encontrados"] == 1 and "polic" in r["fontes"][-1]["destaques"]["lista"][0]["motivos"][1]


# ------------------------------------------------------------------ kit + logo + 1:1
@pytest.fixture()
def logo_png(tmp_path):
    c = str(tmp_path / "logo canal.png")
    ffmpeg("-f", "lavfi", "-i", "color=c=red:s=200x100", "-frames:v", "1", c)
    return c


@pytest.mark.lento
def test_kit_logo_e_render_com_marca(cli, projeto_base, logo_png):
    n = projeto_base["nome"]
    with open(logo_png, "rb") as f:
        r = cli.post("/api/kits/logos", files={"arquivo": ("logo canal.png", f, "image/png")}).json()
    logo = r["logo"]
    assert logo in r["logos"]
    assert cli.post("/api/kits/logos", files={"arquivo": ("x.png", b"nao e imagem", "image/png")}).status_code == 400
    assert cli.post("/api/kits/logos", files={"arquivo": ("x.exe", b"MZ", "application/x")}).status_code == 400
    assert cli.put(f"/api/projetos/{n}", json={"marca": {"arquivo": "nao_existe.png"}}).status_code == 400
    assert cli.put(f"/api/projetos/{n}", json={"marca": {"pos": "meio"}}).status_code == 400
    assert cli.put(f"/api/projetos/{n}", json={"marca": {"arquivo": logo, "pos": "sup_dir"},
                                               "legenda": {"estilo": "palavra"}}).status_code == 200

    # o logo aparece no canto superior direito (dentro da area segura) e nao no esquerdo
    p = projeto.carregar(n)
    q = os.path.join(projeto.pasta(n), render.quadros(p, [1.0])[0])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", q, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    img = np.frombuffer(raw, np.uint8).reshape(1920, 1080, 3).astype(int)
    dentro = img[300:350, 900:1000].mean(axis=(0, 1))       # logo: x 870-1020, y 290-365
    assert dentro[0] > 150 and dentro[1] < 110 and dentro[2] < 110, dentro
    fora = img[300:350, 80:180].mean(axis=(0, 1))
    assert not (fora[0] > 150 and fora[1] < 110)

    # salvar kit, criar projeto novo com ele (curto e longo), aplicar e remover
    k = cli.post("/api/kits", json={"nome": "Meu Canal", "projeto": n}).json()
    assert k["id"] == "meu-canal" and k["marca"]["arquivo"] == logo
    novo = cli.post("/api/projetos", json={"nome": f"{n}-k", "tipo": "curto", "kit": "meu-canal"}).json()
    assert novo["marca"]["arquivo"] == logo and novo["legenda"]["estilo"] == "palavra" and novo["layout"] == p["layout"]
    longo = cli.post("/api/projetos", json={"nome": f"{n}-kl", "tipo": "longo", "kit": "meu-canal"}).json()
    assert longo["marca"]["arquivo"] == logo and longo["layout"] != "tela_cheia" or longo["tipo"] == "longo"
    assert cli.post("/api/projetos", json={"nome": f"{n}-kx", "kit": "nao-existe"}).status_code == 400
    os.remove(kits.caminho_logo(logo))                        # logo apagado: kit aplica o resto e avisa
    r = cli.post(f"/api/projetos/{n}-k/kit", json={"kit": "meu-canal"}).json()
    assert r["marca"]["arquivo"] is None and r["aviso"]
    assert cli.delete("/api/kits/meu-canal").status_code == 200
    assert cli.delete("/api/kits/meu-canal").status_code == 404


@pytest.mark.lento
def test_exportar_1x1(cli, projeto_base):
    n = projeto_base["nome"]
    p = projeto.carregar(n)
    rasc = render.render(p, "rascunho")
    e = _esperar(cli, cli.post(f"/api/projetos/{n}/exportar_1x1", json={"arquivo": os.path.basename(rasc)}).json())
    assert e["estado"] == "ok", e["erro"]
    s = sonda(os.path.join(projeto.pasta(n), e["resultado"]["saida"]))
    assert (s["w"], s["h"]) == (1080, 1080) and s["audio"] and abs(s["dur"] - sonda(rasc)["dur"]) < 0.1
    assert e["resultado"]["saida"] in cli.get(f"/api/projetos/{n}").json()["saidas"]
    de_novo = cli.post(f"/api/projetos/{n}/exportar_1x1", json={"arquivo": e["resultado"]["saida"]}).json()
    assert "1:1" in _esperar(cli, de_novo)["erro"]
    ruim = cli.post(f"/api/projetos/{n}/exportar_1x1", json={"arquivo": "../../x.mp4"}).json()
    assert _esperar(cli, ruim)["estado"] == "erro"
    # empilhado: faixa (gancho..legenda) maior que 1080 -> faixa inteira com laterais desfocadas
    assert render.faixa_1x1(projeto.carregar(n), "empilhado") == (270, 1440)
    cli.put(f"/api/projetos/{n}", json={"layout": "empilhado"})
    rasc2 = render.render(projeto.carregar(n), "rascunho")
    q = render.exportar_1x1(projeto.carregar(n), os.path.basename(rasc2))
    assert (sonda(q)["w"], sonda(q)["h"]) == (1080, 1080)
    cli.put(f"/api/projetos/{n}", json={"layout": "comparacao"})
    assert cli.post(f"/api/projetos/{n}/exportar_1x1", json={"arquivo": os.path.basename(rasc)}).status_code == 400
