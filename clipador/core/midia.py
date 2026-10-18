"""Leitura de midia com ffprobe/ffmpeg: informacoes, tarjas, cortes de cena, miniaturas, energia do audio."""
import json
import os
import re
import subprocess

import numpy as np

SEM_JANELA = 0x08000000 if os.name == "nt" else 0  # nao abre console no Windows


def rodar(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace", creationflags=SEM_JANELA, **kw)


def info(caminho):
    r = rodar(["ffprobe", "-v", "error", "-show_entries",
               "format=duration:stream=codec_type,width,height,r_frame_rate", "-of", "json", caminho])
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe falhou: {r.stderr.strip()[:300]}")
    d = json.loads(r.stdout)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        raise RuntimeError("arquivo sem trilha de video")
    num, den = (v.get("r_frame_rate") or "30/1").split("/")
    return {
        "dur": float(d.get("format", {}).get("duration") or 0),
        "w": int(v["width"]), "h": int(v["height"]),
        "fps": round(float(num) / float(den or 1), 3),
        "audio": any(s.get("codec_type") == "audio" for s in d.get("streams", [])),
    }


def detectar_tarjas(caminho, ini=0.0, dur=60.0):
    """Devolve 'w:h:x:y' das tarjas pretas embutidas (o recorte mais frequente) ou None."""
    r = rodar(["ffmpeg", "-hide_banner", "-ss", str(ini), "-t", str(dur), "-i", caminho,
               "-vf", "cropdetect=limit=24:round=2:reset=0", "-an", "-f", "null", "-"])
    achados = re.findall(r"crop=(\d+:\d+:\d+:\d+)", r.stderr)
    if not achados:
        return None
    crop = max(set(achados), key=achados.count)
    w, h, _, _ = (int(x) for x in crop.split(":"))
    i = info(caminho)
    return None if (w, h) == (i["w"], i["h"]) else crop


def cortes_de_cena(caminho, limiar=0.3):
    """Instantes (s) em que a cena muda. Analisa em baixa resolucao para ser rapido."""
    r = rodar(["ffmpeg", "-hide_banner", "-i", caminho, "-an",
               "-vf", f"scale=320:-2,select='gt(scene,{limiar})',showinfo", "-f", "null", "-"])
    return [round(float(t), 3) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def energia_audio(caminho, passo=0.5):
    """RMS (dBFS) do audio a cada `passo` segundos. Lista vazia se nao houver audio."""
    sr = 8000
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", caminho, "-vn", "-ac", "1", "-ar", str(sr),
                        "-f", "s16le", "-"], capture_output=True, creationflags=SEM_JANELA)
    if r.returncode != 0 or not r.stdout:
        return []
    a = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768
    n = int(sr * passo)
    blocos = len(a) // n
    if blocos == 0:
        return []
    rms = np.sqrt((a[:blocos * n].reshape(blocos, n) ** 2).mean(axis=1) + 1e-12)
    return (20 * np.log10(rms)).round(1).tolist()


def analisar_audio(caminho):
    """Pico, nivel medio e clipping de um arquivo de audio (para avisar ANTES de usar a gravacao)."""
    sr = 16000
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", caminho, "-vn", "-ac", "1", "-ar", str(sr),
                        "-f", "f32le", "-"], capture_output=True, creationflags=SEM_JANELA)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError("nao consegui ler o audio (arquivo corrompido ou formato nao suportado)")
    a = np.frombuffer(r.stdout, dtype=np.float32)
    pico = float(np.abs(a).max()) + 1e-9
    rms = float(np.sqrt((a ** 2).mean()) + 1e-12)
    clip = float((np.abs(a) >= 0.985).mean() * 100)
    out = {"dur": round(len(a) / sr, 2), "pico_db": round(float(20 * np.log10(pico)), 1),
           "rms_db": round(float(20 * np.log10(rms)), 1), "clip_pct": round(clip, 3), "avisos": []}
    if clip >= 0.05:
        out["avisos"].append(f"clipping em {clip:.2f}% do audio: o som estourou. Grave mais longe do microfone "
                             "ou com menos ganho.")
    if out["rms_db"] < -35:
        out["avisos"].append("volume muito baixo: aproxime o microfone ou aumente o ganho.")
    return out


def miniatura(caminho, t, saida, largura=240):
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    r = rodar(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(t, 0):.3f}", "-i", caminho, "-frames:v", "1",
               "-vf", f"scale={largura}:-2", "-q:v", "4", saida])
    return r.returncode == 0


def para_wav(origem, destino, sr=48000):
    """Converte qualquer audio (ex.: webm do navegador) para WAV PCM 24-bit mono, sem processar."""
    r = rodar(["ffmpeg", "-y", "-v", "error", "-i", origem, "-vn", "-ac", "1", "-ar", str(sr),
               "-c:a", "pcm_s24le", destino])
    if r.returncode != 0:
        raise RuntimeError(f"conversao falhou: {r.stderr.strip()[:300]}")
    return destino


def duracao(caminho):
    r = rodar(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", caminho])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0
