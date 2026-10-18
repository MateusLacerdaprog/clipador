"""Legendas: transcricao palavra a palavra (faster-whisper), cartoes por pausa natural e arquivo ASS.

Tambem desenha no mesmo ASS o gancho (titulo do 1o segundo) e os rotulos do layout comparacao,
para todo texto sair com a mesma fonte e sem problemas de escape de caminho no Windows.
"""
import re
from math import gcd

# Destaque #FFDE00 -> ASS usa BGR
AMARELO = "00DEFF"
BRANCO = "FFFFFF"

ESTILOS = {
    # cartao de ate 5 palavras, palavra falada em amarelo (padrao original do projeto)
    "karaoke": {"max_palavras": 5, "max_chars": 34, "quebra_linha": 18, "tamanho": 88,
                "contorno": 7, "sombra": 2, "caixa": False},
    # 1-2 palavras grandes no meio da tela (padrao dos Shorts de detalhe que viralizaram)
    "palavra": {"max_palavras": 3, "max_chars": 16, "quebra_linha": 99, "tamanho": 108,
                "contorno": 9, "sombra": 3, "caixa": False},
    # frase curta em caixa branca (padrao IGN)
    "caixa": {"max_palavras": 6, "max_chars": 30, "quebra_linha": 99, "tamanho": 58,
              "contorno": 14, "sombra": 0, "caixa": True},
}
PAUSA_QUEBRA = 0.35   # silencio (s) que fecha o cartao
CAUDA = 0.12          # tempo apos a ultima palavra (sempre cortado antes do proximo cartao)
POS_X = 500           # centro da area segura (esq 60 / dir 150 de 1080)

# posicao vertical padrao da legenda e do gancho por layout (zona segura: topo >= 288, base <= 1520)
POSICOES = {
    "empilhado": {"legenda": 1330, "gancho": 300, "ranking": 1190},     # lista na faixa livre abaixo do video
    "tela_cheia": {"legenda": 1180, "gancho": 330, "ranking": 560},
    "comparacao": {"legenda": 1440, "gancho": 300, "ranking": 560},
    "horizontal": {"legenda": 960, "gancho": 50, "ranking": 140},   # 1920x1080 (videos longos)
    "dividido": {"legenda": 940, "gancho": 300, "ranking": 330},    # react em tela dividida: legenda na divisoria
}


# ------------------------------------------------------------------ transcricao
def _audio_16k(caminho):
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly

    dados, sr = sf.read(caminho)
    if dados.ndim > 1:
        dados = dados.mean(axis=1)
    if sr != 16000:
        g = gcd(16000, int(sr))
        dados = resample_poly(dados, 16000 // g, int(sr) // g)
    return dados.astype(np.float32)


def transcrever(audio, modelo="small", dicas="", idioma="pt"):
    from faster_whisper import WhisperModel

    wm = WhisperModel(modelo, device="cpu", compute_type="int8")
    segs, _ = wm.transcribe(_audio_16k(audio), language=idioma, word_timestamps=True,
                            initial_prompt=(dicas or "")[:600] or None, vad_filter=True)
    palavras = []
    for s in segs:
        for w in (s.words or []):
            if w.word.strip():
                palavras.append({"w": w.word.strip(), "start": float(w.start), "end": float(w.end)})
    return palavras


def limpar(p):
    p = p.strip().replace("“", "").replace('"', "").replace("”", "")
    return re.sub(r"^[.,;:!?…]+|[.,;:!?…]+$", "", p)


# ---------------------------------------------------------------------- cartoes
def _dividir(trecho, max_pal, max_chars):
    """Divide um trecho em cartoes de tamanho parecido, sem cartao orfao."""
    n = len(trecho)
    k = max(1, -(-n // max_pal))
    while True:
        base, resto = divmod(n, k)
        partes, i = [], 0
        for j in range(k):
            t = base + (1 if j < resto else 0)
            partes.append(trecho[i:i + t])
            i += t
        longo = any(len(" ".join(limpar(x["w"]) for x in p)) > max_chars for p in partes)
        if not longo or k >= n:
            return partes
        k += 1


# palavras que nao devem fechar um cartao (ficam penduradas: "acabou de", "insanas da")
LIGACAO = {"a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos", "e", "em", "no",
           "na", "nos", "nas", "que", "com", "por", "pra", "para", "pelo", "pela", "ao", "aos", "se", "sem", "the",
           "of", "to", "and", "in", "on", "at", "for", "with", "is"}


def _sem_ligacao_no_fim(partes, max_pal, max_chars):
    """Empurra artigo/preposicao do fim de um cartao para o comeco do proximo (se couber)."""
    for i in range(len(partes) - 1):
        while (len(partes[i]) > 1 and limpar(partes[i][-1]["w"]).lower() in LIGACAO
               and len(partes[i + 1]) < max_pal
               and len(" ".join(limpar(x["w"]) for x in [partes[i][-1]] + partes[i + 1])) <= max_chars):
            partes[i + 1].insert(0, partes[i].pop())
    return partes


def construir_cartoes(palavras, estilo="karaoke"):
    E = ESTILOS[estilo]
    trechos, atual = [], []

    def fecha():
        if atual:
            trechos.append(list(atual))
            atual.clear()

    # 1) quebra nos pontos naturais da fala: pontuacao final, virgula e pausas
    for p in palavras:
        if atual and (p["start"] - atual[-1]["end"]) > PAUSA_QUEBRA:
            fecha()
        atual.append(p)
        if re.search(r"[.!?…]$", p["w"]) or p.get("q") == ".":
            fecha()
        elif (re.search(r"[,;:]$", p["w"]) or p.get("q") == ",") and len(atual) >= 2:
            fecha()
    fecha()

    # 2) trecho de 1 palavra gruda no anterior se couber e nao houver pausa entre eles
    fundidos = []
    for t in trechos:
        if (fundidos and len(t) == 1 and len(fundidos[-1]) < E["max_palavras"]
                and (t[0]["start"] - fundidos[-1][-1]["end"]) <= PAUSA_QUEBRA):
            fundidos[-1].extend(t)
        else:
            fundidos.append(t)

    def palavra(x):
        # a legenda sai sem pontuacao, mas guardamos onde havia ("q") para poder reagrupar depois
        q = "." if re.search(r"[.!?…]$", x["w"]) else ("," if re.search(r"[,;:]$", x["w"]) else x.get("q"))
        d = {"w": limpar(x["w"]), "start": round(x["start"], 3), "end": round(x["end"], 3)}
        if q:
            d["q"] = q
        return d

    cartoes = []
    for t in fundidos:
        partes = _sem_ligacao_no_fim(_dividir(t, E["max_palavras"], E["max_chars"]), E["max_palavras"], E["max_chars"])
        for c in partes:
            cartoes.append({"palavras": [palavra(x) for x in c]})
    return cartoes


def reagrupar(cartoes, estilo):
    """Refaz os cartoes para outro estilo mantendo as palavras (e correcoes) ja existentes."""
    palavras = [p for c in cartoes for p in c["palavras"]]
    return construir_cartoes(palavras, estilo) if palavras else []


def aplicar_texto(cartao, texto):
    """Troca o texto de um cartao. Mesmo numero de palavras: mantem os tempos; senao redistribui."""
    novas = texto.split()
    ps = cartao["palavras"]
    if not novas or not ps:
        return cartao
    if len(novas) != len(ps):
        ini, fim = ps[0]["start"], ps[-1]["end"]
        d = (fim - ini) / len(novas)
        ps = [{"start": round(ini + i * d, 3), "end": round(ini + (i + 1) * d, 3)} for i in range(len(novas))]
    for p, n in zip(ps, novas):
        p.pop("q", None)
        m = re.fullmatch(r"\*(.+)\*([.,;:!?…]*)", n)        # *palavra* (pontuacao pode vir depois)
        if m:
            n = m.group(1) + m.group(2)
            p["e"] = True
        else:
            p.pop("e", None)
        if re.search(r"[.!?…]$", n):
            p["q"] = "."
        elif re.search(r"[,;:]$", n):
            p["q"] = ","
        p["w"] = limpar(n) or n
    cartao["palavras"] = ps
    return cartao


# -------------------------------------------------------------------------- ASS
def fmt(t):
    cs = int(round(max(t, 0) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(t):
    return t.replace("\\", "").replace("{", "").replace("}", "")


def _quebra_equilibrada(textos, a_partir):
    total = len(" ".join(textos))
    if total <= a_partir or len(textos) < 2:
        return None
    return min(range(1, len(textos)),
               key=lambda i: abs(len(" ".join(textos[:i])) - len(" ".join(textos[i:]))))


def _quebra_titulo(texto, max_linha=18):
    """Quebra em linhas de tamanho parecido (sem deixar palavra orfa na ultima linha)."""
    pal = texto.split()
    n = max(1, -(-len(texto) // max_linha))
    alvo = len(texto) / n
    linhas, atual = [], ""
    for p in pal:
        if atual and len(linhas) < n - 1 and len(atual) + 1 + len(p) / 2 > alvo:
            linhas.append(atual)
            atual = p
        else:
            atual = f"{atual} {p}".strip()
    if atual:
        linhas.append(atual)
    return "\\N".join(linhas)


# cores do ranking por posicao (1o ouro, 2o verde, 3o azul, depois branco) em BGR
CORES_RANKING = {1: "00C8FF", 2: "5BD304", 3: "F5A742"}


# Presets por plataforma: RECOMENDACOES de legibilidade e de area livre da interface de cada app
# (nao sao regras oficiais e as interfaces mudam). Tudo pode ser ajustado pelo usuario.
# legenda_y por layout = centro vertical da legenda em 1080x1920.
PLATAFORMAS = {
    "shorts": {"nome": "YouTube Shorts", "estilo": "karaoke", "maiusculas": False, "tamanho": 88, "contorno": 7,
               "sombra": 2, "cor": "#FFFFFF", "destaque": "#FFDE00", "animacao": "nenhuma",
               "legenda_y": {"empilhado": 1330, "tela_cheia": 1180, "comparacao": 1440},
               "nota": "Rodapé com nome do canal e título ocupa ~400 px; botões à direita (~150 px)."},
    "tiktok": {"nome": "TikTok", "estilo": "palavra", "maiusculas": True, "tamanho": 100, "contorno": 8,
               "sombra": 3, "cor": "#FFFFFF", "destaque": "#25F4EE", "animacao": "pop",
               "legenda_y": {"empilhado": 1250, "tela_cheia": 1050, "comparacao": 1380},
               "nota": "Legenda, descrição e música ocupam a base (~480 px); deixe o texto mais alto que no Shorts."},
    "reels": {"nome": "Instagram Reels", "estilo": "palavra", "maiusculas": False, "tamanho": 96, "contorno": 7,
              "sombra": 3, "cor": "#FFFFFF", "destaque": "#FF4FA3", "animacao": "pop",
              "legenda_y": {"empilhado": 1280, "tela_cheia": 1100, "comparacao": 1400},
              "nota": "Perfil, legenda e áudio cobrem a base (~420 px); botões à direita."},
}
FONTES = ("Arial Black", "Impact", "Bahnschrift", "Segoe UI Black", "Arial")
ANIMACOES = ("nenhuma", "pop")


def _bgr(hexcor, padrao):
    h = (hexcor or "").lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        return padrao
    return (h[4:6] + h[2:4] + h[0:2]).upper()


def _visual_legenda(E, visual, k):
    """Fonte, tamanho, contorno, sombra, cores (BGR) e animacao: o escolhido pelo usuario, senao o do estilo."""
    v = visual or {}
    return {"fonte": v.get("fonte") if v.get("fonte") in FONTES else "Arial Black",
            "tam": int(int(v.get("tamanho") or E["tamanho"]) * k),
            "contorno": int(v["contorno"]) if v.get("contorno") is not None else E["contorno"],
            "sombra": int(v["sombra"]) if v.get("sombra") is not None else E["sombra"],
            "cor": _bgr(v.get("cor"), BRANCO), "destaque": _bgr(v.get("destaque"), AMARELO),
            "pop": v.get("animacao") == "pop"}


def _estilo_leg(E, vis, mlr):
    """Linha "Style: Leg": caixa (fundo na cor do texto, letra preta) ou texto com contorno e sombra."""
    f, t, c = vis["fonte"], vis["tam"], vis["cor"]
    if E["caixa"]:
        return (f"Style: Leg,{f},{t},&H00000000,&H00000000,&H00{c},&H00{c},"
                f"-1,0,0,0,100,100,0,0,3,{vis['contorno']},0,5,{mlr},0,1")
    return (f"Style: Leg,{f},{t},&H00{c},&H00{c},&H00000000,&H64000000,"
            f"-1,0,0,0,100,100,0,0,1,{vis['contorno']},{vis['sombra']},5,{mlr},0,1")


def _cabecalho_ass(W, H, k, estilo_leg):
    return (
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"{estilo_leg}\n"
        f"Style: Gancho,Arial Black,{int(72 * k)},&H00FFFFFF,&H00FFFFFF,&H002020E0,&H00000000,"
        "-1,0,0,0,100,100,0,0,3,16,0,8,60,60,0,1\n"
        "Style: Rotulo,Arial Black,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,"
        "-1,0,0,0,100,100,0,0,1,6,3,7,40,40,0,1\n"
        f"Style: Ranking,Arial Black,{int(54 * k)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,"
        "-1,0,0,0,100,100,0,0,1,5,2,7,40,40,0,1\n"
        "Style: Capitulo,Arial Black,46,&H00FFFFFF,&H00FFFFFF,&H00141414,&H00000000,"
        "-1,0,0,0,100,100,0,0,3,14,0,1,60,60,0,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _eventos_gancho(gancho, total, horiz, W, pos):
    """Titulo grande no topo durante os primeiros segundos (ate=0 -> fixo o video todo)."""
    if not (gancho and gancho.get("texto", "").strip()):
        return []
    ate = float(gancho.get("ate") or 0) or total
    txt = _quebra_titulo(_esc(gancho["texto"].strip().upper()), 30 if horiz else 18)
    return [f"Dialogue: 2,{fmt(0)},{fmt(ate)},Gancho,,0,0,0,,{{\\an8\\pos({W // 2},{pos['gancho']})}}{txt}"]


def _eventos_ranking(ranking, total, k, pos):
    """Numeros 1..N fixos; o texto de cada posicao aparece quando o trecho dela comeca."""
    if not ranking:
        return []
    ev = []
    n = max(r[1] for r in ranking)
    topo, passo = pos.get("ranking", 360), min(int(66 * k) + 6, max(int(300 / max(n, 1)), 40))
    textos = {pos_: (ini, txt) for ini, pos_, txt in ranking}
    for r in range(1, n + 1):
        cor = CORES_RANKING.get(r, BRANCO)
        yy = topo + (r - 1) * passo
        ev.append(f"Dialogue: 3,{fmt(0)},{fmt(total)},Ranking,,0,0,0,,{{\\an7\\pos(50,{yy})\\c&H{cor}&}}{r}.")
        ini, txt = textos.get(r, (None, ""))
        if ini is not None:
            ev.append(f"Dialogue: 3,{fmt(ini)},{fmt(total)},Ranking,,0,0,0,,"
                      f"{{\\an7\\pos({50 + int(60 * k)},{yy})}}{_esc(txt or '???')[:28]}")
    return ev


def _eventos_capitulos(capitulos, total, H):
    """Cartela de capitulo (canto inferior esquerdo, 3 s) nos videos longos."""
    return [f"Dialogue: 2,{fmt(ini + 0.2)},{fmt(min(ini + 3.2, total))},Capitulo,,0,0,0,,"
            f"{{\\an1\\pos(60,{H - 150})\\fad(200,300)}}{_esc(titulo)[:60]}" for ini, titulo in capitulos or []]


def _eventos_rotulos(rotulos):
    """Rotulos da comparacao: colados na linha divisoria (A acima, B abaixo), longe do gancho e da legenda."""
    ev = []
    for ini, fim, ta, tb in rotulos or []:
        if ta:
            ev.append(f"Dialogue: 1,{fmt(ini)},{fmt(fim)},Rotulo,,0,0,0,,{{\\an1\\pos(40,935)}}{_esc(ta.upper())}")
        if tb:
            ev.append(f"Dialogue: 1,{fmt(ini)},{fmt(fim)},Rotulo,,0,0,0,,{{\\an7\\pos(40,985)}}{_esc(tb.upper())}")
    return ev


def _texto_do_cartao(textos, ps, j, quebra, E, vis):
    """Cartao com a palavra j sendo falada: ela (e as destacadas) na cor de destaque; no estilo caixa as
    destacadas ficam sublinhadas."""
    partes = []
    for n, t in enumerate(textos):
        sep = "" if n == 0 else ("\\N" if n == quebra else " ")
        if E["caixa"]:
            partes.append(f"{sep}{{\\u1}}{t}{{\\u0}}" if ps[n].get("e") else f"{sep}{t}")
        else:
            cor = vis["destaque"] if (n == j or ps[n].get("e")) else vis["cor"]
            partes.append(f"{sep}{{\\c&H{cor}&}}{t}")
    return "".join(partes)


def _eventos_cartao(ps, prox, total, E, vis, x, y, maiusculas):
    """Um evento por palavra do cartao. Termina CAUDA s apos a ultima palavra, antes do proximo cartao (`prox`)
    e nunca depois do fim do video."""
    ini = ps[0]["start"]
    fim = ps[-1]["end"] + CAUDA
    if prox is not None:
        fim = min(fim, prox - 0.01)
    fim = min(fim, total)
    if fim <= ini:
        return []
    textos = [_esc(p["w"].upper() if maiusculas else p["w"]) for p in ps]
    quebra = _quebra_equilibrada(textos, E["quebra_linha"])
    ev = []
    for j, p in enumerate(ps):
        t0 = ini if j == 0 else p["start"]
        t1 = min(fim, ps[j + 1]["start"]) if j + 1 < len(ps) else fim
        if t1 <= t0:
            continue
        # "pop": o cartao entra crescendo de 80% a 100% em 120 ms
        anim = "\\fscx80\\fscy80\\t(0,120,\\fscx100\\fscy100)" if vis["pop"] and j == 0 else ""
        ev.append(f"Dialogue: 0,{fmt(t0)},{fmt(t1)},Leg,,0,0,0,,{{\\an5\\pos({x},{y}){anim}}}"
                  + _texto_do_cartao(textos, ps, j, quebra, E, vis))
    return ev


def _eventos_legenda(cartoes, total, E, vis, x, y, maiusculas):
    """Legenda: um evento por palavra falada, sem sobreposicao entre cartoes."""
    validos = [c for c in cartoes if c.get("palavras")]
    ev = []
    for i, c in enumerate(validos):
        prox = validos[i + 1]["palavras"][0]["start"] if i + 1 < len(validos) else None
        ev += _eventos_cartao(c["palavras"], prox, total, E, vis, x, y, maiusculas)
    return ev


def gerar_ass(caminho, cartoes, estilo="karaoke", layout="empilhado", pos_y=None, maiusculas=False,
              gancho=None, rotulos=None, dur_total=None, ranking=None, capitulos=None, visual=None):
    """Escreve o .ass e devolve o numero de eventos.

    rotulos   : [(ini, fim, texto_a, texto_b)] do layout comparacao
    ranking   : [(ini_trecho, posicao, texto)] -> lista 1..N fixa que se revela trecho a trecho
    capitulos : [(ini, titulo)] -> cartela de capitulo por 3 s (videos longos)
    """
    E = ESTILOS[estilo]
    horiz = layout == "horizontal"
    W, H = (1920, 1080) if horiz else (1080, 1920)
    k = 0.7 if horiz else 1.0                       # fontes menores no 16:9
    pos = POSICOES.get(layout, POSICOES["empilhado"])
    y = int(pos_y or pos["legenda"])
    if ranking and layout == "empilhado" and not pos_y:
        y = 1060          # com ranking embaixo, a legenda sobe para a parte de baixo do video
    x = W // 2 if horiz else POS_X
    vis = _visual_legenda(E, visual, k)
    cab = _cabecalho_ass(W, H, k, _estilo_leg(E, vis, "100,100" if horiz else "60,150"))
    total = dur_total or 3600
    ev = (_eventos_gancho(gancho, total, horiz, W, pos) + _eventos_ranking(ranking, total, k, pos)
          + _eventos_capitulos(capitulos, total, H) + _eventos_rotulos(rotulos)
          + _eventos_legenda(cartoes, total, E, vis, x, y, maiusculas))
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(cab + "\n".join(ev) + "\n")
    return len(ev)


# ------------------------------------------------------------------ destaque automatico
SIGLAS_COMUNS = {"OK", "EU", "UM", "AI"}


def destacar_automatico(cartoes, max_por_cartao=1):
    """Marca no maximo 1 palavra importante por cartao (numeros > siglas > nomes proprios no meio da frase).
    Nao mexe em cartao que o usuario ja destacou. Devolve quantas palavras marcou."""
    marcadas = 0
    for c in cartoes:
        ps = c.get("palavras") or []
        if any(p.get("e") for p in ps):
            continue
        candidatos = []
        for i, p in enumerate(ps):
            w = limpar(p["w"])
            if re.search(r"\d", w):
                candidatos.append((0, i))
            elif len(w) >= 2 and w.isupper() and w.isalpha() and w not in SIGLAS_COMUNS:
                candidatos.append((1, i))
            elif i > 0 and w[:1].isupper() and not re.search(r"[.!?…]$", ps[i - 1]["w"]) and ps[i - 1].get("q") != ".":
                candidatos.append((2, i))
        for _, i in sorted(candidatos)[:max_por_cartao]:
            ps[i]["e"] = True
            marcadas += 1
    return marcadas


def srt_para_vtt(srt):
    """WebVTT a partir do SRT (mesmos blocos; so muda o cabecalho e o separador dos milissegundos)."""
    return "WEBVTT\n\n" + re.sub(r"(\d\d:\d\d:\d\d),(\d\d\d)", r"\1.\2", srt)


# ------------------------------------------------------------------ SRT e tempo por palavra
def limitar(cartoes, fim):
    """A legenda nunca passa do fim do video: palavra que comeca no fim (ou depois) sai; a que atravessa termina
    no fim. Cartao que fica vazio some. Sem duracao minima artificial (regra 2)."""
    if fim is None:
        return cartoes
    out = []
    for c in cartoes:
        ps = [{**w, "end": round(min(w["end"], fim), 3)} for w in c.get("palavras") or [] if w["start"] < fim - 0.04]
        if ps:
            out.append({**c, "palavras": ps})
    return out


def deslocar(cartoes, desl):
    """Aplica o deslocamento da narracao (some o que fica antes de 0)."""
    if not desl:
        return cartoes
    out = []
    for c in cartoes:
        ps = [{**w, "start": w["start"] + desl, "end": w["end"] + desl} for w in c["palavras"] if w["end"] + desl > 0]
        if ps:
            out.append({**c, "palavras": ps})
    return out


def _srt_t(t):
    ms = int(round(max(t, 0) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def gerar_srt(cartoes, maiusculas=False, dur_total=None):
    """SRT: um bloco por cartao, sem sobreposicao (mesma regra de tempo do .ass)."""
    validos = [c for c in cartoes if c.get("palavras")]
    linhas, n = [], 0
    for i, c in enumerate(validos):
        ps = c["palavras"]
        ini, fim = ps[0]["start"], ps[-1]["end"] + CAUDA
        if i + 1 < len(validos):
            fim = min(fim, validos[i + 1]["palavras"][0]["start"] - 0.01)
        if dur_total:
            fim = min(fim, dur_total)
        if fim <= ini:
            continue
        n += 1
        txt = " ".join(p["w"] for p in ps)
        linhas += [str(n), f"{_srt_t(ini)} --> {_srt_t(fim)}", txt.upper() if maiusculas else txt, ""]
    return "\n".join(linhas)


def editar_tempos(cartoes, i, palavras, dur_max=None):
    """Troca as palavras/tempos do cartao i validando ordem e vizinhos (sem sobrepor outro cartao)."""
    if not 0 <= i < len(cartoes):
        raise ValueError("cartão inexistente")
    if not palavras:
        raise ValueError("o cartão precisa de pelo menos uma palavra")
    limite_ini = cartoes[i - 1]["palavras"][-1]["end"] if i > 0 and cartoes[i - 1]["palavras"] else 0.0
    limite_fim = cartoes[i + 1]["palavras"][0]["start"] if i + 1 < len(cartoes) and cartoes[i + 1]["palavras"] else dur_max
    novas, ant = [], limite_ini
    for w in palavras:
        txt = str(w.get("w", "")).strip()
        try:
            s, e = round(float(w["start"]), 3), round(float(w["end"]), 3)
        except (KeyError, TypeError, ValueError):
            raise ValueError("tempo inválido")
        if not txt or " " in txt:
            raise ValueError("cada palavra precisa de texto (sem espaços)")
        if e - s < 0.04:
            raise ValueError(f"'{txt}': o fim precisa ser depois do início")
        if s < ant - 1e-6:
            raise ValueError(f"'{txt}' começa antes da palavra anterior terminar")
        if limite_fim is not None and e > limite_fim + 1e-6:
            raise ValueError(f"'{txt}' invade o próximo cartão ({limite_fim:.2f} s)")
        d = {"w": limpar(txt) or txt, "start": s, "end": e}
        q = next((p.get("q") for p in cartoes[i]["palavras"] if limpar(p["w"]) == d["w"] and p.get("q")), None)
        if any(p.get("e") and limpar(p["w"]) == d["w"] for p in cartoes[i]["palavras"]):
            d["e"] = True                                   # ajustar o tempo nao tira o destaque
        if q:
            d["q"] = q
        novas.append(d)
        ant = e
    cartoes[i] = {**cartoes[i], "palavras": novas}
    return cartoes
