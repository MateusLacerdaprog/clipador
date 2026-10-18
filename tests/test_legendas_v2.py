"""Legendas: destaque de palavras, VTT, legenda do audio do video (relogio da montagem) e previa sem legenda gravada."""
import os
import re
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from clipador.core import legendas, midia, projeto, render
from clipador.web.app import app
from conftest import ffmpeg


def _cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _esperar(cli, t):
    for _ in range(800):
        e = cli.get(f"/api/tarefas/{t['id']}").json()
        if e["estado"] in ("ok", "erro"):
            return e
        time.sleep(0.25)
    raise AssertionError("tarefa nao terminou")


def _cartao(*itens):
    return {"palavras": [{"w": w, "start": s, "end": s + 0.4} for s, w in itens]}


def test_asteriscos_marcam_destaque_e_ass_pinta_a_palavra(tmp_path):
    c = _cartao((0, "o"), (0.5, "Jason"), (1.0, "chegou"))
    legendas.aplicar_texto(c, "o *Jason* chegou!")
    assert [p.get("e") for p in c["palavras"]] == [None, True, None] and c["palavras"][1]["w"] == "Jason"
    legendas.aplicar_texto(c, "o Jason chegou")                     # tirar os asteriscos tira o destaque
    assert not any(p.get("e") for p in c["palavras"])
    legendas.aplicar_texto(c, "o *Jason* chegou")
    # ajustar o tempo da palavra nao tira o destaque
    legendas.editar_tempos([c], 0, [{"w": "o", "start": 0, "end": 0.4}, {"w": "Jason", "start": 0.5, "end": 0.95},
                                    {"w": "chegou", "start": 1.0, "end": 1.4}])
    assert c["palavras"][1].get("e") is True
    ass = tmp_path / "l.ass"
    legendas.gerar_ass(str(ass), [c], estilo="karaoke", visual={"destaque": "#00FF00", "cor": "#FFFFFF"})
    linhas = [l for l in ass.read_text(encoding="utf-8").splitlines() if l.startswith("Dialogue: 0")]
    # em TODO evento do cartao (inclusive quando outra palavra e a falada) "Jason" esta na cor de destaque (BGR 00FF00)
    assert len(linhas) == 3 and all(re.search(r"\\c&H00FF00&\}Jason", l) for l in linhas)
    caixa = tmp_path / "c.ass"
    legendas.gerar_ass(str(caixa), [c], estilo="caixa")
    assert "{\\u1}Jason{\\u0}" in caixa.read_text(encoding="utf-8")


def test_destaque_automatico_prioriza_numero_sigla_nome_e_respeita_o_usuario():
    cs = [_cartao((0, "GTA"), (0.5, "custa"), (1, "70"), (1.5, "dólares")),
          _cartao((3, "o"), (3.5, "GTA"), (4, "chegou")),
          _cartao((6, "falei"), (6.5, "com"), (7, "Lucia")),
          _cartao((9, "nada"), (9.5, "aqui")),
          _cartao((12, "já"), (12.5, "tinha"), (13, "Jason"))]
    cs[4]["palavras"][0]["e"] = True                              # destaque feito pelo usuario
    n = legendas.destacar_automatico(cs)
    marcadas = [[p["w"] for p in c["palavras"] if p.get("e")] for c in cs]
    assert marcadas == [["70"], ["GTA"], ["Lucia"], [], ["já"]] and n == 3


def test_vtt():
    srt = "1\n00:00:01,250 --> 00:00:02,000\nolá\n"
    assert legendas.srt_para_vtt(srt) == "WEBVTT\n\n1\n00:00:01.250 --> 00:00:02.000\nolá\n"


def test_previa_sai_sem_a_legenda_gravada(projeto_base):
    n = projeto_base["nome"]
    d = projeto.pasta(n)
    legendas_cart = [_cartao((0.2, "teste"), (0.8, "legenda"))]
    import json
    json.dump(legendas_cart, open(os.path.join(d, "legenda_cartoes.json"), "w", encoding="utf-8"))
    p = projeto.carregar(n)
    p["legenda_origem"] = "video"
    p["gancho"] = {"texto": "GANCHO", "ate": 2}
    projeto.salvar(p)
    cmd, _, _ = render.montar_comando(projeto.carregar(n), "proxy")
    assert "ass=" not in cmd[cmd.index("-filter_complex") + 1]        # a previa e limpa: base da previa ao vivo
    render.preparar_ass(projeto.carregar(n))
    assert ",Leg," in open(os.path.join(d, "legenda.ass"), encoding="utf-8").read()   # o video final continua com legenda


@pytest.mark.lento
@pytest.mark.skipif(os.name != "nt", reason="voz do Windows")
def test_legenda_do_audio_do_video_cai_no_relogio_da_montagem(projeto_base, tmp_path):
    wav = str(tmp_path / "fala.wav")
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$v = $s.GetInstalledVoices() | ? { $_.VoiceInfo.Culture.Name -eq 'pt-BR' } | select -First 1; "
          "if (-not $v) { exit 3 }; $s.SelectVoice($v.VoiceInfo.Name); "
          f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('O Jason roubou o carro em Vice City.'); $s.Dispose()")
    if subprocess.run(["powershell", "-NoProfile", "-Command", ps]).returncode != 0:
        pytest.skip("sem voz pt-BR no Windows")
    video = str(tmp_path / "fala.mp4")                              # fala comeca em 4 s da fonte
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=12", "-i", wav, "-filter_complex",
           "[1:a]adelay=4000|4000,apad[a]", "-map", "0:v", "-map", "[a]", "-t", "12", "-c:v", "libx264",
           "-preset", "ultrafast", "-c:a", "aac", video)
    n = projeto_base["nome"]
    p = projeto.carregar(n)
    p["fontes"] = [{"id": "fv", "caminho": video, "nome": "fala.mp4", "info": midia.info(video), "crop": None, "cenas": []}]
    p["segmentos"] = [{"id": "a", "fonte": "fv", "ini": 0.0, "fim": 1.0, "foco_x": 0.5, "zoom": 1.0},     # 1 s sem fala
                      {"id": "b", "fonte": "fv", "ini": 3.0, "fim": 9.0, "foco_x": 0.5, "zoom": 1.0}]     # fala: 4 s -> 2 s
    projeto.salvar(p)
    cli = _cli()
    assert cli.post(f"/api/projetos/{n}/legendas/transcrever", json={"origem": "xx"}).status_code == 400
    e = _esperar(cli, cli.post(f"/api/projetos/{n}/legendas/transcrever", json={"origem": "video", "modelo": "small"}).json())
    assert e["estado"] == "ok", e
    assert projeto.carregar(n)["legenda_origem"] == "video"
    cart = cli.get(f"/api/projetos/{n}/legendas").json()
    pal = [w for c in cart for w in c["palavras"]]
    jason = [w for w in pal if w["w"].lower().startswith("jason")]
    # na fonte a fala comeca em 4 s; o trecho b comeca em 3 s da fonte e em 1 s da montagem -> fala em ~2 s
    assert jason and 1.8 < jason[0]["start"] < 4.5, pal
    assert all(0 <= w["start"] < 7.0 for w in pal)
    srt = cli.get(f"/api/projetos/{n}/legendas.srt")
    vtt = cli.get(f"/api/projetos/{n}/legendas.vtt")
    assert srt.status_code == 200 and vtt.status_code == 200 and vtt.text.startswith("WEBVTT")
    primeiro = re.search(r"(\d\d):(\d\d):(\d\d)\.(\d\d\d) -->", vtt.text)
    assert 1.5 < int(primeiro.group(3)) + int(primeiro.group(4)) / 1000 < 4.5
