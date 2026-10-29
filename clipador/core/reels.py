"""Medicao de Reels/Shorts de referencia: o que as empresas que viralizaram fazem na edicao.

Fluxo (python -m clipador reels NOME --top conta:ID ... [--controle conta:ID ...]):
  1. baixa cada video pelo ID com o yt-dlp numa pasta temporaria (nenhum link assinado passa por fora);
  2. UMA leitura do FFmpeg por video tira cortes de cena, loudness (EBU R128), silencio e o audio 16 kHz;
  3. o Whisper (um modelo, varias threads) transcreve so os videos com som;
  4. folhas de quadros agrupadas (3 videos por imagem) para olhar tipografia e gancho;
  5. apaga os videos. Fica so numero + os 3 primeiros segundos de fala (o texto inteiro e descartado).
O grupo "controle" (um Reel na mediana de cada conta) separa o que e causa de viralizacao do estilo da marca.
"""
import datetime as dt
import json
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor

from . import midia, referencias

PASTA = os.path.join(referencias.PASTA, "reels")
LIMIAR_CENA = 0.3
SILENCIO_DB = -40
QUADROS_S = (0.05, 0.5, 1.5, 3.0)   # + meio e fim do video


def pasta(nome):
    return os.path.join(PASTA, referencias._slug(nome))


def item(texto, grupo):
    """'conta:ID' ou 'conta:https://...' -> {'conta', 'id', 'url', 'grupo'}."""
    conta, sep, alvo = texto.partition(":")
    if not sep or not conta or not alvo:
        raise ValueError(f"use conta:ID (ex.: loja:ABCteste123), recebi “{texto}”")
    url = alvo if alvo.startswith("http") else f"https://www.instagram.com/reel/{alvo}/"
    vid = re.search(r"/(?:reel|reels|p|shorts)/([\w-]+)", url)
    if not re.fullmatch(r"[\w.-]{1,40}", conta) or not vid:
        raise ValueError(f"conta ou ID inválido em “{texto}”")
    return {"conta": conta, "id": vid.group(1), "url": url, "grupo": grupo}


# ------------------------------------------------------------------ download
def baixar(itens, destino, cookies_navegador=None):
    """Baixa cada item para destino/<conta>_<id>.mp4. Devolve {chave: caminho | 'erro: ...'}."""
    import yt_dlp
    out = {}
    for it in itens:
        chave = f"{it['conta']}_{it['id']}"
        opts = {"quiet": True, "no_warnings": True, "noprogress": True, "format": "best[ext=mp4]/best",
                "outtmpl": os.path.join(destino, chave + ".%(ext)s"), "noplaylist": True}
        if cookies_navegador:                      # so com autorizacao explicita do usuario
            opts["cookiesfrombrowser"] = (cookies_navegador,)
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                info = y.extract_info(it["url"], download=True)
                out[chave] = y.prepare_filename(info)
        except Exception as e:                     # um Reel fora do ar nao derruba os outros
            out[chave] = f"erro: {str(e).splitlines()[0][:200]}"
    return out


# ------------------------------------------------------------------ medicao (1 leitura)
def comando_medicao(video, wav, com_audio):
    """Uma leitura do arquivo: nota de cena de cada quadro (320 px; o limiar e aplicado depois, entao um video
    sem corte nao deixa a saida vazia), ebur128 + silencedetect e o wav 16 kHz para o Whisper."""
    vid = "[0:v]scale=320:-2,select='gte(scene,0)',metadata=print:key=lavfi.scene_score[v]"
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", video]
    if not com_audio:
        return cmd + ["-filter_complex", vid, "-map", "[v]", "-f", "null", "-"]
    aud = f"[0:a]asplit=2[a1][a2];[a1]ebur128=peak=true,silencedetect=noise={SILENCIO_DB}dB:d=0.3[a]"
    return cmd + ["-filter_complex", vid + ";" + aud, "-map", "[v]", "-map", "[a]", "-f", "null", "-",
                  "-map", "[a2]", "-ac", "1", "-ar", "16000", wav]


def ler_saida(stderr, dur, limiar=LIMIAR_CENA):
    """Extrai cortes (nota de cena > limiar), loudness e fracao de silencio do stderr do comando de medicao."""
    notas = re.findall(r"pts_time:([\d.]+)[^\n]*\n[^\n]*lavfi\.scene_score=([\d.]+)", stderr)
    cortes = [round(float(t), 2) for t, n in notas if float(n) > limiar and 0.05 < float(t) < dur - 0.05]
    resumo = stderr[stderr.rfind("Summary:"):] if "Summary:" in stderr else ""
    def num(chave):
        m = re.search(chave + r":\s+(-?[\d.]+)", resumo)
        return float(m.group(1)) if m else None
    inicios = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", stderr)]
    duracoes = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", stderr)]
    silencio = sum(duracoes) + sum(max(dur - s, 0) for s in inicios[len(duracoes):])  # silencio ate o fim
    return {"cortes": cortes, "lufs": num("I"), "lra": num("LRA"), "true_peak": num("Peak"),
            "silencio": round(min(silencio / dur, 1.0), 3) if dur else None}


def planos(cortes, dur):
    lim = [0.0] + cortes + [dur]
    p = sorted(b - a for a, b in zip(lim, lim[1:]))
    return {"cortes": len(cortes), "plano_medio": round(dur / (len(cortes) + 1), 2),
            "plano_mediana": round(statistics.median(p), 2), "plano_max": round(p[-1], 2),
            "primeiro_corte": cortes[0] if cortes else None,
            "cortes_10s": sum(1 for t in cortes if t < 10)}


def medir(video):
    inf = midia.info(video)
    wav = os.path.splitext(video)[0] + ".wav"
    r = subprocess.run(comando_medicao(video, wav, inf["audio"]), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=midia.SEM_JANELA)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {r.stderr.strip()[-300:]}")
    s = ler_saida(r.stderr, inf["dur"])
    m = {"dur": round(inf["dur"], 2), "res": f"{inf['w']}x{inf['h']}", "fps": inf["fps"],
         "tempos_corte": s["cortes"], **planos(s["cortes"], inf["dur"]),
         "lufs": s["lufs"], "lra": s["lra"], "true_peak": s["true_peak"], "silencio": s["silencio"]}
    return m, (wav if inf["audio"] and os.path.exists(wav) else None)


# ------------------------------------------------------------------ fala
def resumo_fala(palavras):
    """Numeros da fala + o que foi dito nos 3 primeiros segundos (o resto do texto e descartado)."""
    if not palavras:
        return {"palavras": 0}
    ini, fim = palavras[0]["start"], palavras[-1]["end"]
    pausas = [b["start"] - a["end"] for a, b in zip(palavras, palavras[1:])]
    return {"palavras": len(palavras), "primeira_palavra": round(ini, 2),
            "ppm": round(len(palavras) / (fim - ini) * 60, 1) if fim > ini else None,
            "pausas_0_35": sum(1 for p in pausas if p >= 0.35),
            "texto_3s": " ".join(w["w"] for w in palavras if w["start"] < 3.0)}


def transcrever_todos(wavs, modelo="small", paralelo=2):
    """Um modelo do Whisper e `paralelo` threads (o CTranslate2 roda fora do GIL)."""
    if not wavs:
        return {}
    from faster_whisper import WhisperModel
    from . import legendas
    wm = WhisperModel(modelo, device="cpu", compute_type="int8", num_workers=paralelo,
                      cpu_threads=max(1, (os.cpu_count() or 2) // paralelo))

    def um(par):
        chave, wav = par
        segs, _ = wm.transcribe(legendas._audio_16k(wav), language="pt", word_timestamps=True, vad_filter=True)
        pal = [{"w": w.word.strip(), "start": float(w.start), "end": float(w.end)}
               for s in segs for w in (s.words or []) if w.word.strip()]
        return chave, resumo_fala(pal)
    with ThreadPoolExecutor(paralelo) as ex:
        return dict(ex.map(um, wavs.items()))


# ------------------------------------------------------------------ folhas de quadros
def folha(video, dur, saida):
    """6 quadros lado a lado (270x480 cada): 0,05 / 0,5 / 1,5 / 3 s, meio e fim. Sem drawtext (trava sem fontconfig)."""
    ts = [min(t, dur * 0.9) for t in QUADROS_S] + [dur * 0.5, max(dur - 1.2, 0)]   # sempre 6 (folhas empilhaveis)
    ins, flt = [], []
    for i, t in enumerate(ts):
        ins += ["-ss", f"{t:.2f}", "-i", video]
        flt.append(f"[{i}:v]scale=270:480,setsar=1[v{i}]")
    flt.append("".join(f"[v{i}]" for i in range(len(ts))) + f"hstack=inputs={len(ts)}")
    midia.rodar(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(flt), "-frames:v", "1", saida])
    return saida if os.path.exists(saida) else None


def agrupar_folhas(folhas, pasta_saida, por_imagem=3):
    """Empilha as folhas de 3 em 3 (menos imagens para olhar)."""
    grupos = []
    for k in range(0, len(folhas), por_imagem):
        lote = folhas[k:k + por_imagem]
        saida = os.path.join(pasta_saida, f"grupo_{k // por_imagem:02d}.png")
        ins = sum((["-i", f] for f in lote), [])
        filtro = ["-filter_complex", f"vstack=inputs={len(lote)}"] if len(lote) > 1 else []
        r = midia.rodar(["ffmpeg", "-y", "-v", "error", *ins, *filtro, "-frames:v", "1", saida])
        if r.returncode == 0:
            grupos.append({"imagem": os.path.basename(saida), "videos": [os.path.basename(f)[:-4] for f in lote]})
    return grupos


# ------------------------------------------------------------------ resumo
def resumo(medidas):
    """Medianas por grupo (top x controle): a diferenca e o que pode explicar a viralizacao."""
    out = {}
    for g in ("top", "controle"):
        vs = [m for m in medidas.values() if m.get("grupo") == g and "erro" not in m]
        if not vs:
            continue
        med = lambda xs: round(statistics.median(xs), 2) if xs else None
        fal = [m["fala"] for m in vs if m.get("fala", {}).get("palavras")]
        out[g] = {"n": len(vs),
                  **{c: med([m[c] for m in vs if m.get(c) is not None])
                     for c in ("dur", "plano_mediana", "plano_max", "primeiro_corte", "cortes_10s", "lufs", "silencio")},
                  "com_fala": len(fal), "ppm": med([f["ppm"] for f in fal if f.get("ppm")]),
                  "fala_no_quadro_0": sum(1 for f in fal if f.get("primeira_palavra", 9) <= 0.3)}
    return out


def medir_lote(nome, itens, modelo="small", paralelo=2, cookies_navegador=None, manter_videos=False,
               log=print):
    """Baixa, mede, transcreve e gera folhas. Grava referencias/reels/<nome>/medidas.json."""
    if not itens:
        raise ValueError("passe pelo menos um Reel (--top conta:ID)")
    destino = pasta(nome)
    os.makedirs(os.path.join(destino, "folhas"), exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="clipador-reels-")
    try:
        log(f"baixando {len(itens)} vídeo(s)…")
        arquivos = baixar(itens, tmp, cookies_navegador)
        medidas, wavs, folhas = {}, {}, []
        for it in itens:
            chave = f"{it['conta']}_{it['id']}"
            arq = arquivos.get(chave, "erro: não baixou")
            base = {"conta": it["conta"], "id": it["id"], "grupo": it["grupo"]}
            if arq.startswith("erro"):
                medidas[chave] = {**base, "erro": arq}
                log(f"  {chave}: {arq}")
                continue
            try:
                m, wav = medir(arq)
            except RuntimeError as e:                    # um arquivo ruim nao derruba o lote
                medidas[chave] = {**base, "erro": str(e)[:300]}
                log(f"  {chave}: {e}")
                continue
            medidas[chave] = {**base, **m}
            if wav and (m["silencio"] or 0) < 0.9:       # sem som util nao vale transcrever
                wavs[chave] = wav
            f = folha(arq, m["dur"], os.path.join(destino, "folhas", chave + ".png"))
            if f:
                folhas.append(f)
            log(f"  {chave}: {m['dur']} s, {m['cortes']} cortes, {m['lufs']} LUFS")
        log(f"transcrevendo {len(wavs)} vídeo(s) com fala ({paralelo} em paralelo)…")
        for chave, fala in transcrever_todos(wavs, modelo, paralelo).items():
            medidas[chave]["fala"] = fala
        for m in medidas.values():
            if "erro" not in m:
                m.setdefault("fala", {"palavras": 0})
        grupos = agrupar_folhas(folhas, os.path.join(destino, "folhas"))
    finally:
        if manter_videos:
            log(f"vídeos mantidos em {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    dados = {"nome": nome, "data": dt.date.today().isoformat(), "limiar_cena": LIMIAR_CENA,
             "resumo": resumo(medidas), "folhas": grupos, "videos": medidas}
    with open(os.path.join(destino, "medidas.json"), "w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=1)
    return dados
