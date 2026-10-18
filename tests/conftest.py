"""Fixtures com midia REAL gerada pelo FFmpeg (nada de mocks): video com tarjas, audio, narracao.

Os projetos de teste ficam numa pasta temporaria (CLIPADOR_PROJETOS), nunca em projetos/ do usuario.
"""
import os
import re
import subprocess
import sys
import tempfile

import pytest

_TMP = tempfile.mkdtemp(prefix="clipador_testes_")
os.environ["CLIPADOR_PROJETOS"] = os.path.join(_TMP, "projetos")
os.environ["CLIPADOR_ESTUDIO"] = os.path.join(_TMP, "estudio")       # canais/ideias/roteiros de teste
os.environ["CLIPADOR_COFRE"] = "Clipador-IA-TESTES"      # nunca mexe nas chaves reais do usuario
for _v in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
    os.environ.pop(_v, None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ESTATICO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "clipador", "web", "static")


def pytest_configure(config):
    # ciclo rapido: python -m pytest tests -q -m "not lento"  (a suite inteira continua obrigatoria antes de concluir)
    config.addinivalue_line("markers", "lento: renderiza video/audio com o FFmpeg ou transcreve (fora do ciclo rapido)")


def scripts_da_interface():
    """Caminhos dos js/*.js na ordem em que o index.html carrega (scripts classicos, escopo global compartilhado)."""
    with open(os.path.join(ESTATICO, "index.html"), encoding="utf-8") as f:
        html = f.read()
    return [os.path.join(ESTATICO, *s.split("/")) for s in re.findall(r'<script src="/static/([^"]+)"></script>', html)]


def js_da_interface():
    """Todo o JavaScript da interface, concatenado na ordem de carga."""
    partes = []
    for c in scripts_da_interface():
        with open(c, encoding="utf-8") as f:
            partes.append(f.read())
    return "\n".join(partes)


def ffmpeg(*args):
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.fixture(scope="session")
def midia():
    d = os.path.join(_TMP, "midia")
    os.makedirs(d, exist_ok=True)
    video = os.path.join(d, "fonte_1080p_tarjas.mp4")
    # 12 s, 1920x1080 com tarjas pretas de 60 px (como o trailer), tom de 440 Hz como "som do jogo"
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=1920x960:r=30:d=12", "-f", "lavfi", "-i", "sine=f=440:d=12",
           "-vf", "pad=1920:1080:0:60:black", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", video)
    mudo = os.path.join(d, "fonte_sem_audio.mp4")
    ffmpeg("-f", "lavfi", "-i", "testsrc=s=1280x720:r=30:d=6", "-c:v", "libx264", "-preset", "ultrafast",
           "-pix_fmt", "yuv420p", mudo)
    # "voz": tom de 1 kHz ligado/desligado (falas de 1 s com pausas de 1 s), 8 s
    voz = os.path.join(d, "voz.wav")
    # nivel de fala real (pico ~ -6 dBFS); o "sine" do FFmpeg sai em 1/8 de amplitude
    ffmpeg("-f", "lavfi", "-i", "sine=f=1000:d=8", "-af", "volume='if(lt(mod(t,2),1),4,0)':eval=frame", voz)
    musica = os.path.join(d, "musica.mp3")
    ffmpeg("-f", "lavfi", "-i", "sine=f=220:d=5", "-af", "volume=0.6", "-c:a", "libmp3lame", musica)
    efeito = os.path.join(d, "efeito.wav")
    ffmpeg("-f", "lavfi", "-i", "sine=f=2000:d=0.5", efeito)
    estourada = os.path.join(d, "voz_estourada.wav")
    ffmpeg("-f", "lavfi", "-i", "sine=f=300:d=2", "-af", "volume=8,alimiter=limit=1:level=false", estourada)
    return {"video": video, "mudo": mudo, "voz": voz, "musica": musica, "efeito": efeito,
            "estourada": estourada, "dir": d}


@pytest.fixture()
def projeto_base(midia, request):
    """Projeto novo com a fonte de 12 s registrada e 2 trechos (total 6 s)."""
    from clipador.core import midia as M
    from clipador.core import projeto

    nome = "t-" + request.node.name.lower().replace("[", "-").replace("]", "")[:40]
    d = projeto.pasta(nome)
    if os.path.isdir(d):
        import shutil
        shutil.rmtree(d)
    p = projeto.criar(nome)
    inf = M.info(midia["video"])
    p["fontes"].append({"id": "f1", "caminho": midia["video"], "nome": "fonte.mp4", "info": inf,
                        "crop": M.detectar_tarjas(midia["video"], 0, 6), "cenas": []})
    p["segmentos"] = [{"id": "s1", "fonte": "f1", "ini": 1.0, "fim": 4.0, "foco_x": 0.5, "zoom": 1.0},
                      {"id": "s2", "fonte": "f1", "ini": 6.0, "fim": 9.0, "foco_x": 0.3, "zoom": 1.15}]
    projeto.salvar(p)
    return projeto.carregar(nome)


def sonda(arquivo):
    """Duracao, dimensoes e streams de um arquivo gerado."""
    import json
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                        "-of", "json", arquivo], capture_output=True, text=True)
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), {})
    return {"dur": float(d["format"]["duration"]), "w": v.get("width"), "h": v.get("height"),
            "audio": any(s["codec_type"] == "audio" for s in d["streams"])}


def volume_medio(arquivo, ini, dur):
    """Volume medio (dBFS) de um trecho do audio."""
    import re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(ini), "-t", str(dur), "-i", arquivo,
                        "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"mean_volume: (-?[\d.]+|-inf)", r.stderr)
    return float(m.group(1)) if m else float("-inf")
