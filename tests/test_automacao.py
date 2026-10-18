"""Montagem automatica (python -m clipador montar|finalizar): do pedido ao RASCUNHO pela mesma API da tela."""
import os
import shutil
import subprocess
import sys

import pytest

from clipador import automacao
from clipador.core import projeto
from conftest import sonda

pytestmark = pytest.mark.lento


@pytest.fixture()
def nome(request):
    n = "auto-" + request.node.name[5:30].replace("_", "-")
    shutil.rmtree(projeto.pasta(n), ignore_errors=True)
    yield n
    shutil.rmtree(projeto.pasta(n), ignore_errors=True)


def test_montar_com_trechos_ate_o_rascunho_sem_narracao(midia, nome):
    log = []
    r = automacao.Clipador(log=log.append).montar(nome, midia["video"], formato="gameplay", trechos=[(1, 4), (6, 8.5)])
    p = projeto.carregar(nome)
    assert [(s["ini"], s["fim"]) for s in p["segmentos"]] == [(1, 4), (6, 8.5)]
    assert os.path.isfile(r["rascunho"]) and abs(sonda(r["rascunho"])["dur"] - 5.5) < 0.2
    assert os.path.isfile(os.path.join(projeto.pasta(nome), "proxy.mp4"))       # base para gravar a narracao
    assert p["narracao"] is None and not (p["gancho"].get("texto") or "")         # nada escrito pelo agente
    assert not any(f.startswith("FINAL_") for f in os.listdir(projeto.pasta(nome)))
    assert any("prévia" in linha for linha in log)


def test_montar_sem_trechos_usa_o_melhor_momento(midia, nome):
    r = automacao.Clipador(log=lambda *_: None).montar(nome, midia["video"], duracao=6)
    p = projeto.carregar(nome)
    total = projeto.duracao_timeline(p)
    assert p["segmentos"] and 3 <= total <= 8 and os.path.isfile(r["rascunho"])


@pytest.mark.skipif(os.name != "nt", reason="voz do Windows")
def test_finalizar_poe_as_legendas_da_narracao_e_refaz_o_rascunho(midia, nome, tmp_path):
    wav = str(tmp_path / "fala.wav")                            # fala de verdade: voz pt-BR do Windows
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$v = $s.GetInstalledVoices() | ? { $_.VoiceInfo.Culture.Name -eq 'pt-BR' } | select -First 1; "
          "if (-not $v) { exit 3 }; $s.SelectVoice($v.VoiceInfo.Name); "
          f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('Olha o Jason chegando de carro na praia.'); $s.Dispose()")
    if subprocess.run(["powershell", "-NoProfile", "-Command", ps]).returncode != 0:
        pytest.skip("sem voz pt-BR no Windows")
    c = automacao.Clipador(log=lambda *_: None)
    c.montar(nome, midia["video"], trechos=[(1, 9)])
    with pytest.raises(automacao.ErroAutomacao, match="aba 5"):
        c.finalizar(nome)                                       # sem narracao: diz onde gravar
    r = c.finalizar(nome, narracao=wav, modelo="small")
    p = projeto.carregar(nome)
    assert p["narracao"] and p["legenda_origem"] == "narracao" and os.path.isfile(r["rascunho"])
    assert not any(f.startswith("FINAL_") for f in os.listdir(projeto.pasta(nome)))   # FINAL so com aprovacao


def test_erros_claros_e_linha_de_comando(midia, nome, tmp_path):
    c = automacao.Clipador(log=lambda *_: None)
    with pytest.raises(automacao.ErroAutomacao, match="não encontrado"):
        c.montar(nome + "-x", str(tmp_path / "nao_existe.mp4"))
    shutil.rmtree(projeto.pasta(nome + "-x"), ignore_errors=True)
    assert automacao._trechos("14-20, 31.5-36") == [(14.0, 20.0), (31.5, 36.0)]
    for ruim in ("20-14", "abc", "5"):
        with pytest.raises(Exception, match="trecho inválido"):
            automacao._trechos(ruim)
    r = subprocess.run([sys.executable, "-m", "clipador", "montar", nome, "--fonte", midia["video"], "--trechos", "1-3.5"],
                       capture_output=True, text=True, encoding="utf-8", env=os.environ,
                       cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "RASCUNHO pronto para revisão" in r.stdout and "O FINAL só depois de aprovar" in r.stdout


def test_referencia_por_videos_locais_e_montar_seguindo_ela(midia, nome, tmp_path):
    from clipador.core import referencias
    from conftest import ffmpeg
    d = referencias.pasta_videos("estilo-teste")
    shutil.rmtree(d, ignore_errors=True)
    with pytest.raises(automacao.ErroAutomacao, match="coloque os vídeos"):
        automacao.referencia("estilo-teste", com_fala=False, log=lambda *_: None)     # pasta vazia: diz onde pôr
    for k in range(2):                                # 2 Shorts de 12 s com 3 planos de 4 s (cores bem diferentes)
        partes = []
        for j, cor in enumerate(("red", "blue", "green")):
            parte = str(tmp_path / f"p{k}{j}.mp4")
            ffmpeg("-f", "lavfi", "-i", f"color=c={cor}:s=1080x1920:r=30:d=4", "-c:v", "libx264", "-preset", "ultrafast",
                   "-pix_fmt", "yuv420p", parte)
            partes.append(parte)
        lista = tmp_path / f"l{k}.txt"
        lista.write_text("".join(f"file '{p}'\n" for p in partes), encoding="utf-8")
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", os.path.join(d, f"ref{k}.mp4"))
    try:
        perfil = automacao.referencia("estilo-teste", com_fala=False, log=lambda *_: None)
        v = perfil["observado"]["por_video"]
        assert len(v) == 2 and all(x["vertical"] and abs(x["plano_medio_s"] - 4) < 0.6 for x in v)
        assert perfil["derivado"]["curto"]["duracao_alvo"] == 12 and referencias.carregar("estilo-teste")
        r = automacao.Clipador(log=lambda *_: None).montar(nome, midia["video"], referencia="estilo-teste")
        p = projeto.carregar(nome)
        assert p["referencia"] == "estilo-teste" and p["formato_cfg"]["duracao_alvo"] == 12
        assert 6 <= projeto.duracao_timeline(p) <= 12.5 and os.path.isfile(r["rascunho"])   # momento com a duração dela
        with pytest.raises(automacao.ErroAutomacao):
            automacao.Clipador(log=lambda *_: None).montar(nome + "-y", midia["video"], referencia="nao-existe")
        assert not os.path.exists(projeto.pasta(nome + "-y"))          # referência errada não cria projeto
    finally:
        shutil.rmtree(d, ignore_errors=True)
        referencias.apagar("estilo-teste")
