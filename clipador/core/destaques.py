"""Sugestao de cenas e de MOMENTOS (clipes prontos) de um video de jogo, tudo local e explicavel.

cenas()      : divide a fonte em cenas e da uma nota (0-100) para cada uma (feito ao adicionar a fonte).
sinais()     : mede a cada 0,5 s o volume, os impactos sonoros (tiros, explosoes, batidas), o movimento na tela e
               ONDE ele acontece (perfil horizontal, usado no foco automatico). Fica em cache na pasta do projeto.
momentos()   : janelas de N segundos com a melhor combinacao de sinais, sem sobreposicao, cada uma com a nota e os
               MOTIVOS medidos (a nota e relativa ao proprio video: compara trechos entre si, nao preve views).
foco_auto()  : posicao horizontal do recorte vertical que segue a acao (centro do movimento).
"""
import os

import numpy as np

from . import midia

PASSO = 0.5            # resolucao dos sinais (s)
FPS_MOV = 4            # quadros/s analisados para movimento
COLS = 64              # largura do quadro reduzido (perfil horizontal do movimento)
VERSAO_SINAIS = 1


def cenas(caminho, info, limiar=0.3, passo=0.5):
    dur = info["dur"]
    cortes = [t for t in midia.cortes_de_cena(caminho, limiar) if 0.3 < t < dur - 0.3]
    limites = [0.0] + cortes + [dur]
    energia = np.array(midia.energia_audio(caminho, passo)) if info.get("audio") else np.array([])
    ref = float(np.median(energia)) if energia.size else 0.0

    saida = []
    for ini, fim in zip(limites[:-1], limites[1:]):
        d = fim - ini
        if d < 0.4:
            continue
        nota = 50.0
        # cenas de 1.5 a 6 s funcionam melhor em Shorts (ritmo de troca de plano)
        if 1.5 <= d <= 6:
            nota += 15
        elif d > 10:
            nota -= 15
        if energia.size:
            a, b = int(ini / passo), max(int(fim / passo), int(ini / passo) + 1)
            trecho = energia[a:b]
            if trecho.size:
                nota += float(np.clip((trecho.mean() - ref) * 2.5, -20, 25))
        # logos e cartelas costumam ficar no comeco/fim
        if ini < 1.5 or fim > dur - 3:
            nota -= 15
        saida.append({"ini": round(ini, 3), "fim": round(fim, 3), "nota": int(np.clip(nota, 0, 100))})
    return saida


def sugerir_sequencia(lista_cenas, alvo_s=20.0, max_cena_s=4.0):
    """Escolhe as melhores cenas, em ordem cronologica, ate somar ~alvo_s (cenas longas sao aparadas)."""
    escolhidas, total = [], 0.0
    for c in sorted(lista_cenas, key=lambda c: -c["nota"]):
        if total >= alvo_s:
            break
        d = min(c["fim"] - c["ini"], max_cena_s)
        meio = (c["ini"] + c["fim"]) / 2
        ini = max(c["ini"], meio - d / 2)
        escolhidas.append({"ini": round(ini, 3), "fim": round(ini + d, 3)})
        total += d
    return sorted(escolhidas, key=lambda s: s["ini"])


# ------------------------------------------------------------------ sinais
def _audio_sinais(caminho, n):
    """(volume dB, impactos) por bloco de PASSO s. Impacto = subida >= 9 dB em 50 ms sobre o nivel recente."""
    sr = 8000
    r = midia.subprocess.run(["ffmpeg", "-v", "error", "-i", caminho, "-vn", "-ac", "1", "-ar", str(sr),
                              "-f", "s16le", "-"], capture_output=True, creationflags=midia.SEM_JANELA)
    vol, imp = np.full(n, -90.0), np.zeros(n)
    if r.returncode != 0 or not r.stdout:
        return vol, imp
    a = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768
    j = sr // 20                                          # janelas de 50 ms
    k = len(a) // j
    if k < 2:
        return vol, imp
    db = 20 * np.log10(np.sqrt((a[:k * j].reshape(k, j) ** 2).mean(axis=1)) + 1e-6)
    # nivel recente = minimo dos 4 blocos anteriores (200 ms); subida forte e acima do ruido = impacto
    ant = np.full(k, np.inf)
    for d in range(1, 5):
        ant[d:] = np.minimum(ant[d:], db[:-d])
    onset = (db - ant >= 9) & (db > np.median(db) - 3)
    por = int(PASSO * 20)
    m = min(n, k // por)
    vol[:m] = db[:m * por].reshape(m, por).mean(axis=1)
    imp[:m] = onset[:m * por].reshape(m, por).sum(axis=1)
    return vol, imp


def _video_sinais(caminho, n):
    """(movimento medio 0-1, perfil horizontal do movimento [n x COLS]) por bloco de PASSO s."""
    h = COLS * 9 // 16
    r = midia.subprocess.run(["ffmpeg", "-v", "error", "-i", caminho, "-an", "-vf",
                              f"fps={FPS_MOV},scale={COLS}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"],
                             capture_output=True, creationflags=midia.SEM_JANELA)
    mov, perfil = np.zeros(n), np.zeros((n, COLS), dtype=np.float32)
    q = len(r.stdout) // (COLS * h)
    if r.returncode != 0 or q < 2:
        return mov, perfil
    fr = np.frombuffer(r.stdout[:q * COLS * h], dtype=np.uint8).reshape(q, h, COLS).astype(np.float32) / 255
    dif = np.abs(np.diff(fr, axis=0))                     # quadro i+1 menos i
    por = int(PASSO * FPS_MOV)
    m = min(n, len(dif) // por)
    if m:
        blocos = dif[:m * por].reshape(m, por, h, COLS)
        mov[:m] = blocos.mean(axis=(1, 2, 3))
        perfil[:m] = blocos.mean(axis=(1, 2))
    return mov, perfil


def sinais(caminho, info, cache=None, progresso=lambda f, m=None: None):
    """Sinais por bloco de 0,5 s. `cache`: arquivo .npz reaproveitado enquanto o video nao mudar."""
    st = os.stat(caminho)
    assinatura = np.array([VERSAO_SINAIS, st.st_size, int(st.st_mtime)], dtype=np.int64)
    if cache and os.path.isfile(cache):
        try:
            z = np.load(cache)
            if np.array_equal(z["assinatura"], assinatura):
                return {k: z[k] for k in ("volume", "impactos", "movimento", "perfil")}
        except (OSError, KeyError, ValueError):
            pass
    n = max(1, int(info["dur"] / PASSO))
    progresso(0.1, "medindo o audio (volume e impactos)")
    vol, imp = _audio_sinais(caminho, n) if info.get("audio") else (np.full(n, -90.0), np.zeros(n))
    progresso(0.4, "medindo o movimento na tela")
    mov, perfil = _video_sinais(caminho, n)
    out = {"volume": vol, "impactos": imp, "movimento": mov, "perfil": perfil}
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        tmp = cache + ".tmp.npz"
        np.savez_compressed(tmp, assinatura=assinatura, **out)
        os.replace(tmp, cache)
    return out


# ---------------------------------------------------------------- momentos
def _z(x):
    x = np.asarray(x, dtype=np.float64)
    s = x.std()
    return (x - x.mean()) / s if s > 1e-9 else np.zeros_like(x)


def _mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def momentos(s, cortes, dur, duracao=20.0, quantidade=5, evitar=None):
    """Melhores janelas de `duracao` s, sem sobreposicao. `cortes`: instantes de troca de cena.
    `evitar`: [(ini, fim)] a excluir (ex.: logo/creditos marcados pelo usuario)."""
    n = len(s["volume"])
    w = max(2, int(round(duracao / PASSO)))
    if n < w:
        w = n
    tem_audio = float(np.max(s["volume"])) > -80
    zv, zi, zm = _z(s["volume"]), _z(s["impactos"]), _z(s["movimento"])
    ref_db = float(np.median(s["volume"]))
    cortes = np.asarray(sorted(cortes), dtype=np.float64)
    g = min(w, int(3 / PASSO))                            # gancho = 3 primeiros segundos

    cands = []
    for a in range(0, n - w + 1, 2):                     # testa a cada 1 s
        b = a + w
        ini, fim = a * PASSO, b * PASSO
        if evitar and any(ini < e1 and fim > e0 for e0, e1 in evitar):
            continue
        f = {
            "volume": float(zv[a:b].mean()), "pico": float(zv[a:b].max()),
            "impactos": float(zi[a:b].mean()), "movimento": float(zm[a:b].mean()),
            "gancho": float((zv[a:a + g] + zm[a:a + g] + zi[a:a + g]).mean() / 3),
            "cortes_min": float(((cortes > ini) & (cortes < fim)).sum() / (fim - ini) * 60),
        }
        ritmo = 0.3 if 15 <= f["cortes_min"] <= 70 else (-0.2 if f["cortes_min"] < 4 else 0.0)
        pts = (0.25 * f["volume"] + 0.10 * f["pico"] + 0.20 * f["impactos"] + 0.25 * f["movimento"]
               + 0.20 * f["gancho"] + ritmo)
        if not tem_audio:
            pts = 0.6 * f["movimento"] + 0.25 * f["gancho"] + ritmo
        if ini < 2 or fim > dur - 4:                     # logos, cartelas e creditos
            pts -= 0.4
        cands.append((pts, a, b, f))

    escolhidos = []
    for pts, a, b, f in sorted(cands, key=lambda c: -c[0]):
        if len(escolhidos) >= quantidade:
            break
        if any(a < e[2] and b > e[1] for e in escolhidos):
            continue
        escolhidos.append((pts, a, b, f))

    saida = []
    for pts, a, b, f in escolhidos:
        ini, fim = a * PASSO, b * PASSO
        # comeca no corte de cena mais proximo (ate 1,5 s) para nao abrir no meio de um plano
        perto = cortes[(cortes >= ini - 1.5) & (cortes <= ini + 1.5)]
        if perto.size:
            desl = float(perto[np.argmin(np.abs(perto - ini))]) - ini
            if 0 <= ini + desl and fim + desl <= dur:
                ini, fim = ini + desl, fim + desl
        db = float(s["volume"][a:b].mean()) - ref_db
        pico_t = (a + int(np.argmax(zv[a:b] + zm[a:b] + zi[a:b]))) * PASSO
        motivos, alertas = [], []
        if tem_audio and db >= 2:
            motivos.append(f"áudio {db:+.0f} dB acima da média do vídeo")
        if f["impactos"] >= 0.4:
            motivos.append(f"muitos impactos sonoros (tiros, explosões, batidas): {int(s['impactos'][a:b].sum())}")
        if f["movimento"] >= 0.4:
            motivos.append("muita ação na tela")
        elif f["movimento"] <= -0.5:
            alertas.append("imagem quase parada (menu, diálogo ou cena lenta)")
        if 15 <= f["cortes_min"] <= 70:
            motivos.append(f"ritmo de cortes bom ({f['cortes_min']:.0f}/min)")
        elif f["cortes_min"] < 4:
            alertas.append("plano longo, sem cortes: considere dividir e acelerar")
        if f["gancho"] >= 0.4:
            motivos.append("começo forte (gancho nos 3 primeiros segundos)")
        elif f["gancho"] <= 0:
            alertas.append(f"começo fraco: o ponto mais forte está em {_mmss(pico_t)}")
        if not motivos:
            motivos.append("melhor trecho disponível, sem destaque forte")
        saida.append({"ini": round(ini, 2), "fim": round(min(fim, dur), 2),
                      "nota": int(np.clip(50 + 25 * pts, 0, 100)), "pico": round(pico_t, 2),
                      "motivos": motivos, "alertas": alertas,
                      "medidas": {k: round(v, 2) for k, v in f.items()}})
    return sorted(saida, key=lambda m: -m["nota"])


def dividir_em_cortes(ini, fim, cortes, minimo=0.6):
    """Divide [ini, fim] nos cortes de cena internos (trechos < `minimo` s sao unidos ao anterior)."""
    pts = [ini] + [c for c in sorted(cortes) if ini + minimo <= c <= fim - minimo] + [fim]
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        if out and b - a < minimo:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return [(round(a, 3), round(b, 3)) for a, b in out]


# ------------------------------------------------------------------- foco
def foco_auto(s, ini, fim, fonte, aspecto):
    """foco_x (0-1) que centraliza o recorte de `aspecto` (w/h) no centro de massa do movimento do trecho.
    Sem movimento suficiente devolve 0.5 (centro)."""
    a, b = int(ini / PASSO), max(int(fim / PASSO), int(ini / PASSO) + 1)
    p = s["perfil"][a:b].sum(axis=0) if len(s["perfil"]) else np.zeros(COLS)
    W, H = fonte["info"]["w"], fonte["info"]["h"]
    x0, larg = 0, W
    if fonte.get("crop"):
        cw, ch, cx, _ = (int(v) for v in fonte["crop"].split(":"))
        x0, larg, H = cx, cw, ch
    # colunas do perfil que caem dentro da area util (o perfil cobre o quadro inteiro)
    c0, c1 = int(x0 / W * COLS), max(int((x0 + larg) / W * COLS), int(x0 / W * COLS) + 1)
    p = p[c0:c1]
    if p.size == 0 or p.sum() < 1e-6 or p.max() < 1.5 * p.mean():
        return 0.5                                        # movimento espalhado: centro
    p = np.clip(p - np.median(p), 0, None)                # ignora o movimento de fundo (camera andando)
    if p.sum() < 1e-9:
        return 0.5
    centro = float((np.arange(p.size) + 0.5) @ p / p.sum()) / p.size * larg
    rw = min(larg, H * aspecto)
    if larg - rw < 2:
        return 0.5
    return round(float(np.clip((centro - rw / 2) / (larg - rw), 0, 1)), 3)
