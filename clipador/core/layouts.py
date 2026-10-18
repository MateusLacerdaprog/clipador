"""Presets de enquadramento vertical 1080x1920. Cada funcao devolve a cadeia de filtros de UM segmento.

tela_cheia : recorte 9:16 do quadro (foco_x escolhe a area) com zoom lento opcional
empilhado  : bloco nitido 1080x864 em y=300 + fundo desfocado escurecido (padrao IGN/GameSpot)
comparacao : duas fontes, uma em cima e outra embaixo (A x B)
"""
from . import zoom as _zoom

LAYOUTS = ("tela_cheia", "empilhado", "comparacao", "horizontal")
TELA = {"curto": (1080, 1920), "longo": (1920, 1080)}
FPS = 30
BLOCO_H, BLOCO_Y = 864, 300


def _par(x):
    return int(round(x / 2.0)) * 2


def _dims(fonte):
    """Largura/altura uteis depois de tirar as tarjas pretas."""
    if fonte.get("crop"):
        w, h, _, _ = (int(v) for v in fonte["crop"].split(":"))
        return w, h
    return fonte["info"]["w"], fonte["info"]["h"]


def _corte_tarjas(fonte):
    return f"crop={fonte['crop']}," if fonte.get("crop") else ""


def _regiao(fonte, aspecto, foco_x):
    """Maior retangulo com `aspecto` (w/h) dentro da area util, posicionado horizontalmente por foco_x."""
    W, H = _dims(fonte)
    if W / H > aspecto:
        rh, rw = H, _par(H * aspecto)
    else:
        rw, rh = W, _par(W / aspecto)
    x = _par(min(max(foco_x, 0.0), 1.0) * (W - rw))
    y = _par((H - rh) / 2)
    return f"crop={rw}:{rh}:{x}:{y}"


def _v(entrada):
    """Imagem do trecho: numero da entrada do FFmpeg ([3:v]) ou rotulo ja preparado ([cg3], quadro congelado)."""
    return f"[{entrada}:v]" if isinstance(entrada, int) else f"[{entrada}]"


def _final(rotulo):
    return f"fps={FPS},format=yuv420p,setsar=1,setpts=PTS-STARTPTS[{rotulo}]"


def _com_zoom(seg, dur):
    """Trecho do zoom (core/zoom.py) a inserir depois da imagem ja no tamanho final, ou ''.
    (O relogio de cada trecho comeca em 0 porque a entrada usa -ss; o zoompan fica de fora: no FFmpeg 9 ele
    gera quadros a mais e desalinha a montagem.)"""
    fx = _zoom.efeito(seg, dur)
    return f"fps={FPS},setpts=PTS-STARTPTS,{_zoom.filtro(fx)}," if fx else ""


def tela_cheia(idx, seg, fonte, dur, rotulo):
    foco = float(seg.get("foco_x", 0.5))
    base = f"{_v(idx)}{_corte_tarjas(fonte)}{_regiao(fonte, 9 / 16, foco)},"
    return base + "scale=1080:1920:flags=lanczos," + _com_zoom(seg, dur) + _final(rotulo)


def empilhado(idx, seg, fonte, dur, rotulo):
    foco = float(seg.get("foco_x", 0.5))
    W, H = _dims(fonte)
    larg = _par(W * BLOCO_H / H)            # largura apos escalar para a altura do bloco
    x = _par(max(larg - 1080, 0) * min(max(foco, 0.0), 1.0))
    a, b, bg, fg = (f"{rotulo}_{s}" for s in ("a", "b", "bg", "fg"))
    return (
        f"{_v(idx)}{_corte_tarjas(fonte)}split=2[{a}][{b}];"
        f"[{a}]scale=108:192:force_original_aspect_ratio=increase,crop=108:192,boxblur=4:2,"
        f"scale=1080:1920,eq=brightness=-0.18,"
        f"drawbox=x=0:y={BLOCO_Y - 6}:w=1080:h={BLOCO_H + 12}:color=black@0.55:t=fill[{bg}];"
        f"[{b}]scale={max(larg, 1080)}:{BLOCO_H}:flags=lanczos,crop=1080:{BLOCO_H}:{x}:0"
        f"{',' + _com_zoom(seg, dur).rstrip(',') if _com_zoom(seg, dur) else ''}[{fg}];"     # zoom so no bloco nitido
        f"[{bg}][{fg}]overlay=0:{BLOCO_Y}," + _final(rotulo)
    )


def dividido_topo(idx, seg, fonte, dur, rotulo):
    """React em tela dividida: o jogo ocupa a metade de cima (1080x960); a camera entra embaixo no render."""
    foco = float(seg.get("foco_x", 0.5))
    return (f"{_v(idx)}{_corte_tarjas(fonte)}{_regiao(fonte, 1080 / 960, foco)},scale=1080:960:flags=lanczos,"
            + _final(rotulo))


def horizontal(idx, seg, fonte, dur, rotulo):
    """Video longo 1920x1080: fonte inteira e nitida (sem tarjas), fundo desfocado se a proporcao nao bater,
    zoom lento opcional."""
    W, H = _dims(fonte)
    a, b, bg, fg = (f"{rotulo}_{s}" for s in ("a", "b", "bg", "fg"))
    if abs(W / H - 16 / 9) < 0.02:
        base = f"{_v(idx)}{_corte_tarjas(fonte)}scale=1920:1080:flags=lanczos,setsar=1"
    else:
        base = (f"{_v(idx)}{_corte_tarjas(fonte)}split=2[{a}][{b}];"
                f"[{a}]scale=192:108:force_original_aspect_ratio=increase,crop=192:108,boxblur=4:2,"
                f"scale=1920:1080,eq=brightness=-0.2[{bg}];"
                f"[{b}]scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,setsar=1[{fg}];"
                f"[{bg}][{fg}]overlay=(W-w)/2:(H-h)/2")
    return base + "," + _com_zoom(seg, dur) + _final(rotulo)


def comparacao(idx_a, idx_b, seg, fonte_a, fonte_b, dur, rotulo, divisoria=True):
    """Tela dividida A x B: cada video preenche meia tela (1080x960, recorte pelo foco de cada um). Se um video
    acabar antes do trecho, o ultimo quadro fica parado (tpad) em vez de quebrar a montagem."""
    foco = float(seg.get("foco_x", 0.5))
    foco_b = float(seg.get("foco_x_b", foco))
    a, b = f"{rotulo}_ca", f"{rotulo}_cb"
    segura = f"tpad=stop_mode=clone:stop_duration={dur:.3f},trim=duration={dur:.3f},setpts=PTS-STARTPTS"
    linha = "drawbox=x=0:y=957:w=1080:h=6:color=white@0.9:t=fill," if divisoria else ""
    return (
        f"{_v(idx_a)}{_corte_tarjas(fonte_a)}{_regiao(fonte_a, 1080 / 960, foco)},"
        f"scale=1080:960:flags=lanczos,setsar=1,fps={FPS},setpts=PTS-STARTPTS,{segura}[{a}];"
        f"{_v(idx_b)}{_corte_tarjas(fonte_b)}{_regiao(fonte_b, 1080 / 960, foco_b)},"
        f"scale=1080:960:flags=lanczos,setsar=1,fps={FPS},setpts=PTS-STARTPTS,{segura}[{b}];"
        f"[{a}][{b}]vstack=inputs=2,{linha}"
        + _final(rotulo)
    )
