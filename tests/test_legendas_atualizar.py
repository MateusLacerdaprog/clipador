"""Atualizar legendas: a legenda nunca passa do fim do video (geracao, .ass, .srt), o app avisa quando a montagem
ou a narracao mudou depois da transcricao, e "Atualizar legendas" refaz tudo com Desfazer (versao anterior guardada).

Narracao REAL: fala sintetizada pela voz pt-BR do Windows + Whisper local (pulado se a voz nao existir). A parte
do audio do video usa a transcricao da fonte em cache escrita a mao (o que se testa e o fluxo, nao o Whisper).
"""
import json
import os
import re
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from clipador.core import legendas, pedido, projeto, render
from clipador.web.app import app
from conftest import ffmpeg


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _esperar(cli, t):
    for _ in range(1200):
        e = cli.get(f"/api/tarefas/{t['id']}").json()
        if e["estado"] in ("ok", "erro"):
            return e
        time.sleep(0.25)
    raise AssertionError("tarefa nao terminou")


def _pal(*itens):
    return [{"w": w, "start": t, "end": t + 0.3} for t, w in itens]


def test_limitar_corta_no_fim_sem_duracao_minima():
    cart = [{"palavras": _pal((1.0, "um"), (2.0, "dois"))}, {"palavras": _pal((5.8, "atravessa"), (6.0, "fora"))},
            {"palavras": _pal((7.0, "longe"))}]
    out = legendas.limitar(cart, 6.0)
    assert [w["w"] for c in out for w in c["palavras"]] == ["um", "dois", "atravessa"]
    assert out[-1]["palavras"][-1]["end"] == 6.0 and len(out) == 2           # cartao vazio some
    assert out[0] == cart[0] and legendas.limitar(cart, None) == cart        # o que cabe nao muda


def test_ass_e_srt_nunca_passam_do_fim_do_video(cli, projeto_base, midia):
    n = projeto_base["nome"]                                                 # timeline de 6 s
    d = projeto.pasta(n)
    import shutil
    shutil.copyfile(midia["voz"], os.path.join(d, "narracao.wav"))          # 8 s (mais longa que o video)
    p = projeto.carregar(n)
    p["narracao"] = "narracao.wav"
    projeto.salvar(p)
    cart = [{"palavras": _pal((1.0, "olha"), (2.0, "isso"))}, {"palavras": _pal((5.5, "quase"), (5.9, "no"))},
            {"palavras": _pal((7.0, "depois"), (7.5, "do"), (7.8, "fim"))}]
    with open(os.path.join(d, "legenda_cartoes.json"), "w", encoding="utf-8") as f:
        json.dump(cart, f)
    est = cli.get(f"/api/projetos/{n}").json()
    assert est["legendas_passam"] == pytest.approx(2.1, abs=0.01)           # 8,1 s - 6 s: a interface avisa

    srt = cli.get(f"/api/projetos/{n}/legendas.srt").text
    fins = [int(m[0]) * 3600 + int(m[1]) * 60 + int(m[2]) + int(m[3]) / 1000
            for m in re.findall(r"--> (\d\d):(\d\d):(\d\d),(\d\d\d)", srt)]
    assert fins and max(fins) <= 6.0 and "depois" not in srt.lower()
    render.preparar_ass(projeto.carregar(n))
    ass = open(os.path.join(d, "legenda.ass"), encoding="utf-8-sig").read()
    falas = [l for l in ass.splitlines() if l.startswith("Dialogue:") and ",Gancho," not in l]
    fim_ass = max(int(h) * 3600 + int(m) * 60 + float(s)
                  for h, m, s in (re.match(r"Dialogue: \d+,[^,]+,(\d+):(\d+):([\d.]+)", l).groups() for l in falas))
    assert fim_ass <= 6.0 and not any("DEPOIS" in l.upper() for l in falas)

    # com deslocamento de +1 s a narracao "anda" para frente: o limite acompanha
    cli.put(f"/api/projetos/{n}", json={"audio": {"narracao": {"deslocamento": 1.0}}})
    assert cli.get(f"/api/projetos/{n}").json()["legendas_passam"] == pytest.approx(3.1, abs=0.01)
    srt = cli.get(f"/api/projetos/{n}/legendas.srt").text
    assert "isso" in srt.split() and "quase" not in srt.split()             # 5,5+1 = 6,5 s: ja passou do fim


def _escrever_transcricao(nome, fonte, palavras):
    c = pedido.caminho_cache(projeto.pasta(nome), fonte["id"])
    os.makedirs(os.path.dirname(c), exist_ok=True)
    with open(c, "w", encoding="utf-8") as f:
        json.dump({"assinatura": pedido._assinatura(fonte["caminho"]), "palavras": palavras}, f)


def test_atualizar_legendas_quando_a_montagem_muda_e_desfazer(cli, projeto_base):
    n = projeto_base["nome"]                                                 # trechos 1-4 s e 6-9 s da fonte
    _escrever_transcricao(n, projeto_base["fontes"][0],
                          _pal((1.5, "primeiro"), (2.5, "trecho."), (6.5, "segundo"), (7.5, "trecho."), (10.5, "sobra.")))
    assert cli.post(f"/api/projetos/{n}/legendas/restaurar").status_code == 400      # nada para voltar ainda
    e = _esperar(cli, cli.post(f"/api/projetos/{n}/legendas/transcrever", json={"origem": "video"}).json())
    assert e["estado"] == "ok", e
    est = cli.get(f"/api/projetos/{n}").json()
    assert est["legendas_desatualizadas"] is False and est["legendas_passam"] == 0
    assert est["tem_legenda_anterior"]                    # ate a 1a transcricao tem Desfazer (volta para "sem legenda")
    v1 = [w["w"] for c in cli.get(f"/api/projetos/{n}/legendas").json() for w in c["palavras"]]
    assert v1 == ["primeiro", "trecho", "segundo", "trecho"]                   # "sobra" (fora dos trechos) nao entra

    # o usuario corta o 2o trecho: as legendas ficam velhas (e o proximo passo aponta para elas)
    segs = est["segmentos"][:1]
    est = cli.put(f"/api/projetos/{n}", json={"segmentos": segs}).json()
    assert est["legendas_desatualizadas"] is True and est["legendas_passam"] > 0

    # Atualizar legendas = transcrever de novo com a mesma origem: so o que esta no video, nada depois do fim
    e = _esperar(cli, cli.post(f"/api/projetos/{n}/legendas/transcrever", json={"origem": est["legenda_origem"]}).json())
    assert e["estado"] == "ok" and e["resultado"]["cartoes"] >= 1
    cart = cli.get(f"/api/projetos/{n}/legendas").json()
    assert [w["w"] for c in cart for w in c["palavras"]] == ["primeiro", "trecho"]
    assert max(w["end"] for c in cart for w in c["palavras"]) <= 3.0
    est = cli.get(f"/api/projetos/{n}").json()
    assert est["legendas_desatualizadas"] is False and est["legendas_passam"] == 0 and est["tem_legenda_anterior"]

    # Desfazer volta a versao anterior; clicar de novo refaz
    r = cli.post(f"/api/projetos/{n}/legendas/restaurar").json()
    assert [w["w"] for c in r["cartoes"] for w in c["palavras"]] == v1
    r = cli.post(f"/api/projetos/{n}/legendas/restaurar").json()
    assert [w["w"] for c in r["cartoes"] for w in c["palavras"]] == ["primeiro", "trecho"]


@pytest.mark.lento
@pytest.mark.skipif(os.name != "nt", reason="voz do Windows")
def test_narracao_real_mais_longa_que_o_video_nao_vira_legenda_depois_do_fim(cli, projeto_base, tmp_path):
    wav = str(tmp_path / "fala.wav")
    frase = "Olha o Jason chegando de carro. Agora ele vai para a praia. E depois vai para o aeroporto de Vice City."
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$v = $s.GetInstalledVoices() | ? { $_.VoiceInfo.Culture.Name -eq 'pt-BR' } | select -First 1; "
          "if (-not $v) { exit 3 }; $s.SelectVoice($v.VoiceInfo.Name); "
          f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('{frase}'); $s.Dispose()")
    if subprocess.run(["powershell", "-NoProfile", "-Command", ps]).returncode != 0:
        pytest.skip("sem voz pt-BR no Windows")
    n = projeto_base["nome"]                                                 # video de 6 s
    d = projeto.pasta(n)
    ffmpeg("-i", wav, "-af", "adelay=2000|2000", "-ar", "48000", os.path.join(d, "narracao.wav"))   # fala de 2 s em diante
    p = projeto.carregar(n)
    p["narracao"] = "narracao.wav"
    projeto.salvar(p)
    e = _esperar(cli, cli.post(f"/api/projetos/{n}/legendas/transcrever", json={"origem": "narracao", "modelo": "small"}).json())
    assert e["estado"] == "ok", e
    assert e["resultado"]["fora_do_video"] > 0                               # a fala continua depois dos 6 s
    pal = [w for c in cli.get(f"/api/projetos/{n}/legendas").json() for w in c["palavras"]]
    assert pal and all(w["start"] < 6.0 and w["end"] <= 6.0 for w in pal), pal
    assert any(w["w"].lower().startswith("jason") for w in pal)              # o comeco da fala esta la
    assert not any(w["w"].lower().startswith("aeroporto") for w in pal)
    est = cli.get(f"/api/projetos/{n}").json()
    assert est["legendas_passam"] == 0 and est["legendas_desatualizadas"] is False
    # gravar outra narracao deixa a legenda desatualizada
    ffmpeg("-i", wav, "-ar", "48000", os.path.join(d, "narracao.wav"))
    os.utime(os.path.join(d, "narracao.wav"), (time.time() + 5, time.time() + 5))
    assert cli.get(f"/api/projetos/{n}").json()["legendas_desatualizadas"] is True
