"""React: camera do criador sobre o video do jogo (nao destrutivo).

Gravacao  : o navegador grava camera+microfone (webm) sobre a previa da montagem. O servidor guarda
            react/camera.mp4 (so video, 30 fps) e extrai o microfone como a trilha de NARRACAO (ducking, volume,
            legenda e tratamento de voz continuam funcionando).
Modos     : janela (camera pequena sobre o video), dividido (video em cima, camera embaixo — so curtos),
            fundo_virtual (pessoa sem fundo sobre o video: chroma key ou recorte por IA local).
Recorte   : chroma key (FFmpeg chromakey + despill) — confiavel com fundo verde/azul liso e bem iluminado;
            sem tela verde: MediaPipe (modelo de segmentacao de pessoa) gera react/matte.mp4 neste PC.
            Nenhum dos dois e perfeito em qualquer camera/luz: o modo janela sempre funciona como alternativa.
"""
import os
import re
import subprocess

import numpy as np

from . import midia, projeto

PASTA = "react"
MODOS = ("janela", "dividido", "fundo_virtual")
FORMAS = ("retangulo", "circulo", "vertical")
MODELO = os.path.join(os.path.dirname(projeto.RAIZ), "modelos", "selfie_segmenter.tflite")
MODELO_URL = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"
PADRAO = {
    "ativo": False, "arquivo": None, "info": None, "modo": "janela",
    "janela": {"x": 0.95, "y": 0.92, "w": 0.34, "forma": "retangulo", "borda": True},   # x,y = fracao do espaco livre
    "espelhar": True, "deslocamento": 0.0,
    "chroma": {"ativo": False, "cor": "#00FF00", "similaridade": 0.18, "mistura": 0.08, "despill": True},
    # recorte por IA: limiar = onde termina a pessoa; borda = largura da transicao; estabilidade = mistura com o quadro anterior
    "recorte_ia": {"ativo": False, "pronto": False, "limiar": 0.5, "borda": 0.4, "estabilidade": 0.4, "gerado_com": None},
    "recorte": {"x": 0.5, "y": 1.0, "w": 0.95},        # fundo virtual: posicao (fracao do espaco livre) e largura
}


def completar(r):
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in PADRAO.items()}
    for k, v in (r or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        elif k in out:
            out[k] = v
    return out


def pasta(p):
    return os.path.join(projeto.pasta(p["nome"]), PASTA)


def caminho_camera(p):
    r = p.get("react") or {}
    return os.path.join(pasta(p), r["arquivo"]) if r.get("arquivo") else None


def caminho_matte(p):
    return os.path.join(pasta(p), "matte.mp4")


def ia_disponivel():
    try:
        import mediapipe  # noqa: F401
    except ImportError:
        return {"ok": False, "motivo": "o MediaPipe não está instalado (pip install mediapipe)"}
    return {"ok": True, "modelo_baixado": os.path.isfile(MODELO)}


def baixar_modelo():
    import urllib.request
    os.makedirs(os.path.dirname(MODELO), exist_ok=True)
    tmp = MODELO + ".tmp"
    urllib.request.urlretrieve(MODELO_URL, tmp)
    os.replace(tmp, MODELO)


# ------------------------------------------------------------------ camera enviada pelo navegador
def importar_camera(p, origem, usar_audio=True):
    """Converte a gravacao para react/camera.mp4 (CFR 30 fps, <=1280 px) e extrai o microfone como narracao."""
    os.makedirs(pasta(p), exist_ok=True)
    destino = os.path.join(pasta(p), "camera.mp4")
    tmp = os.path.join(pasta(p), "camera.tmp.mp4")
    r = midia.rodar(["ffmpeg", "-y", "-v", "error", "-i", origem, "-an", "-vf", "fps=30,scale='min(1280,iw)':-2",
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", tmp])
    if r.returncode != 0 or not os.path.isfile(tmp):
        raise ValueError("não consegui ler o vídeo da câmera (arquivo corrompido ou sem imagem)")
    os.replace(tmp, destino)
    inf = midia.info(destino)
    analise = None
    if usar_audio:
        try:
            wav = os.path.join(projeto.pasta(p["nome"]), "narracao.wav")
            midia.para_wav(origem, wav)
            analise = midia.analisar_audio(wav)
            p["narracao"] = "narracao.wav"
        except RuntimeError:
            analise = None          # gravacao sem microfone: segue so com a imagem
    p["react"] = completar(p.get("react"))
    p["react"].update(arquivo="camera.mp4", ativo=True, info={"dur": inf["dur"], "w": inf["w"], "h": inf["h"]})
    if os.path.isfile(caminho_matte(p)):
        os.remove(caminho_matte(p))          # matte antigo nao serve para outra gravacao
    p["react"]["recorte_ia"] = {"ativo": False, "pronto": False}
    return analise


def estado_extra(p):
    """Informacoes derivadas para a interface (arquivos presentes, versoes para recarregar o player, matte velho)."""
    cam, mt = caminho_camera(p), caminho_matte(p)
    ia = completar(p.get("react"))["recorte_ia"]
    atuais = {k: ia[k] for k in ("limiar", "borda", "estabilidade")}
    tem_cam, tem_mt = bool(cam and os.path.isfile(cam)), os.path.isfile(mt)
    return {"recorte_ia": ia_disponivel(), "matte_pronto": tem_mt, "camera_ok": tem_cam,
            "camera_versao": int(os.path.getmtime(cam)) if tem_cam else None,
            "matte_versao": int(os.path.getmtime(mt)) if tem_mt else None,
            "matte_desatualizado": tem_mt and ia.get("gerado_com") not in (None, atuais)}


def remover_camera(p):
    """Desliga o react no projeto. Os arquivos ficam na pasta (nada e apagado sem pedir)."""
    p["react"] = completar(p.get("react"))
    p["react"].update(ativo=False, arquivo=None, info=None)
    p["react"]["recorte_ia"] = {"ativo": False, "pronto": False}


# ------------------------------------------------------------------ recorte de pessoa (MediaPipe, local)
def _caixa(x, r):
    import cv2
    return cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1), borderType=cv2.BORDER_REFLECT)


def refinar_mascara(conf, guia, limiar=0.5, borda=0.4):
    """Filtro guiado (He et al., 2010): a mascara que o modelo calcula em 256 px passa a seguir as bordas reais da
    imagem (cabelo, ombro, maos). Depois uma rampa de largura `borda` em torno do `limiar` vira o alfa (0-1)."""
    h, w = conf.shape
    r = max(4, int(round(max(h, w) / 64)))               # cobre o borrao da ampliacao de 256 px (~20 px em 1280x720)
    mI, mp = _caixa(guia, r), _caixa(conf, r)
    a = (_caixa(guia * conf, r) - mI * mp) / (_caixa(guia * guia, r) - mI * mI + 1e-3)
    q = _caixa(a, r) * guia + _caixa(mp - a * mI, r)
    larg = 0.04 + 0.36 * float(borda)
    return np.clip((q - (float(limiar) - larg / 2)) / larg, 0, 1)


def gerar_matte(p, progresso=lambda f, m=None: None, cancelar=None):
    """Gera react/matte.mp4 (cinza: branco = pessoa). Roda inteiro neste PC; nada e enviado a lugar nenhum."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision

    cam = caminho_camera(p)
    if not cam or not os.path.isfile(cam):
        raise RuntimeError("o projeto não tem gravação de câmera")
    if not os.path.isfile(MODELO):
        progresso(0.02, "baixando o modelo de segmentação (250 KB)")
        try:
            baixar_modelo()
        except Exception:  # noqa: BLE001
            raise RuntimeError("não consegui baixar o modelo de segmentação (sem internet?). "
                               "Use chroma key ou o modo janela.") from None
    seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
        base_options=mpt.BaseOptions(model_asset_path=MODELO), output_confidence_masks=True, output_category_mask=False))
    cap = cv2.VideoCapture(cam)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = max(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 1)
    tmp = os.path.join(pasta(p), "matte.tmp.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", "30",
                            "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", tmp],
                           stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=midia.SEM_JANELA)
    ia = completar(p.get("react"))["recorte_ia"]
    lim, bor, est = float(ia["limiar"]), float(ia["borda"]), float(ia["estabilidade"])
    ant, n = None, 0
    try:
        while True:
            if cancelar is not None and cancelar.is_set():
                raise RuntimeError("tarefa cancelada")
            ok, quadro = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(quadro, cv2.COLOR_BGR2RGB)
            m = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
            conf = np.squeeze(m.confidence_masks[0].numpy_view()).astype(np.float32)
            conf = cv2.resize(conf, (w, h), interpolation=cv2.INTER_LINEAR)
            conf = conf if ant is None else (1 - est) * conf + est * ant      # menos tremida entre quadros
            ant = conf
            guia = cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
            alfa = refinar_mascara(conf, guia, lim, bor)                       # borda segue a imagem real
            enc.stdin.write((alfa * 255).astype(np.uint8).tobytes())
            n += 1
            if n % 15 == 0:
                progresso(min(0.05 + 0.93 * n / total, 0.98), f"recortando pessoa {n}/{total}")
        enc.stdin.close()
        if enc.wait() != 0 or n == 0:
            raise RuntimeError("falha ao gravar o recorte: " + enc.stderr.read().decode(errors="replace")[-300:])
    except BaseException:
        try:
            enc.kill()
        except Exception:  # noqa: BLE001
            pass
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    finally:
        cap.release()
    os.replace(tmp, caminho_matte(p))
    return {"quadros": n, "params": {"limiar": lim, "borda": bor, "estabilidade": est}}


# ------------------------------------------------------------------ grafo de filtros
def _par(x):
    return max(int(round(x / 2.0)) * 2, 2)


def _cor(hexcor):
    h = (hexcor or "#00FF00").lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        h = "00FF00"
    return "0x" + h.upper()


def _recorte(forma, cw, ch):
    """(filtro crop, largura/altura relativas) para a forma da janela."""
    if forma == "circulo":
        return "crop=min(iw\\,ih):min(iw\\,ih)", 1.0
    if forma == "vertical":
        return "crop='min(iw\\,ih*9/16)':ih", 9 / 16
    return "", (ch / cw if cw else 9 / 16)


def aplicar(p, base, camera_idx, matte_idx, saida, W, H):
    """Retorna (filtros, dividido). `base` = rotulo do video montado; `saida` = rotulo de saida."""
    R = completar(p.get("react"))
    modo = R["modo"]
    inf = R.get("info") or {"w": 1280, "h": 720}
    esp = "hflip," if R["espelhar"] else ""
    ch = R["chroma"]
    usa_alpha = ch["ativo"] or matte_idx is not None
    f = []

    if modo == "dividido":
        top = H // 2
        reg = f"crop='min(iw\\,ih*{W}/{top})':'min(ih\\,iw*{top}/{W})'"
        f.append(f"[{camera_idx}:v]fps=30,setpts=PTS-STARTPTS,{esp}{reg},scale={W}:{top}:flags=lanczos,format=yuv420p,setsar=1[cam]")
        d = float(R["deslocamento"])
        if d > 0:      # camera atrasada: ate la, quadro preto embaixo
            f[-1] = (f"[{camera_idx}:v]fps=30,setpts=PTS-STARTPTS,{esp}{reg},scale={W}:{top}:flags=lanczos,format=yuv420p,setsar=1,"
                     f"tpad=start_duration={d:.3f}:color=black[cam]")
        f.append(f"[{base}][cam]vstack=inputs=2:shortest=0[{saida}]")
        return f, True

    J = R["janela"]
    C = R["recorte"] if modo == "fundo_virtual" else J       # fundo virtual tem posicao/tamanho proprios
    forma = J["forma"] if modo == "janela" else "retangulo"
    wpx = _par(W * C["w"])
    corte, rel = _recorte(forma, inf["w"], inf["h"])
    hpx = _par(wpx * rel) if forma != "retangulo" else _par(wpx * inf["h"] / inf["w"])
    if forma == "vertical":
        hpx = _par(wpx * 16 / 9)
    d = float(R["deslocamento"])
    atraso = f"tpad=start_duration={d:.3f}:start_mode=clone," if d > 0 else ""     # atrasa o CONTEUDO da camera
    cadeia = f"[{camera_idx}:v]fps=30,setpts=PTS-STARTPTS,{atraso}{esp}"
    cadeia += (corte + ",") if corte else ""
    if usa_alpha:
        cadeia += "format=yuva420p,"
        if ch["ativo"]:
            cadeia += f"chromakey=color={_cor(ch['cor'])}:similarity={ch['similaridade']}:blend={ch['mistura']},"
            if ch.get("despill", True):
                k = _cor(ch["cor"])
                tipo = "blue" if int(k[6:8], 16) > int(k[4:6], 16) else "green"   # fundo azul tira reflexo azul
                cadeia += f"despill=type={tipo}:mix=0.5,format=yuva420p,"
    cadeia += f"scale={wpx}:{hpx}:flags=lanczos,format=yuva420p" if usa_alpha else f"scale={wpx}:{hpx}:flags=lanczos,format=yuv420p"
    if matte_idx is not None:
        mt = f"[{matte_idx}:v]fps=30,setpts=PTS-STARTPTS,{atraso}{esp}" + ((corte + ",") if corte else "") + f"scale={wpx}:{hpx},format=gray[mt]"
        f.append(cadeia + "[cam0]")
        f.append(mt)
        f.append("[cam0][mt]alphamerge[cam1]")
        cadeia = "[cam1]"
    else:
        cadeia += "[cam1]"
        f.append(cadeia)
        cadeia = "[cam1]"
    ultimo = cadeia
    if forma == "circulo":
        f.append(f"{ultimo}format=yuva420p,geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':"
                 f"a='alpha(X,Y)*lte(hypot(X-W/2,Y-H/2),W/2)'[cam2]")
        ultimo = "[cam2]"
    elif J["borda"] and not usa_alpha and modo == "janela":
        f.append(f"{ultimo}drawbox=x=0:y=0:w=iw:h=ih:color=white@1:t=4[cam2]")
        ultimo = "[cam2]"
    px = int(round(C["x"] * (W - wpx)))
    py = int(round(C["y"] * (H - hpx)))
    quando = f":enable='gte(t,{d:.3f})'" if d > 0 else ""      # antes de a camera comecar nao mostra nada
    f.append(f"[{base}]{ultimo}overlay={max(px, 0)}:{max(py, 0)}:format=auto:eof_action=pass:shortest=0{quando}[{saida}]")
    return f, False

