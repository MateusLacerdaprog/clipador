"""Perfis de referencia editorial: aprende TECNICA de edicao de canais publicos, sem copiar conteudo.

O que e coletado (so dados publicos, sem baixar video):
  - metadados das abas /shorts e /videos (titulo, duracao, views) via yt-dlp;
  - detalhes de uma amostra (data, capitulos, legenda automatica) -> so metricas agregadas.
O texto das legendas e lido para contar palavras/ritmo e DESCARTADO: nada de roteiro, fala ou video fica salvo.
Metricas visuais (ritmo de cortes, layout, estilo de legenda) entram como "observacao visual" quando alguem
analisa os quadros (ex.: pela folha de quadros no navegador), com data e amostra registradas.
"""
import datetime as dt
import json
import os
import re
import statistics
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import projeto

PASTA = os.path.join(os.path.dirname(projeto.RAIZ), "referencias")
ASPECTOS = {
    "duracao": "Duração dos vídeos curtos e longos",
    "publicacao": "Frequência de publicação",
    "titulos": "Padrão dos títulos (tamanho, maiúsculas, emoji, perguntas)",
    "fala": "Ritmo de fala (palavras por minuto, densidade nos 3 primeiros segundos)",
    "capitulos": "Uso de capítulos nos vídeos longos",
    "visual": "Ritmo de cortes, layout e legenda (observação visual)",
}
STOP = set("a o e de da do das dos em no na nos nas um uma que pra para com por se ao à é the of to and in on is "
           "eu você voce isso esse essa mais muito como foi vai tem ter já ja não nao sim seu sua meu minha".split())
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def _slug(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "perfil"


def caminho(pid):
    return os.path.join(PASTA, f"{_slug(pid)}.json")


def listar():
    if not os.path.isdir(PASTA):
        return []
    out = []
    for f in sorted(os.listdir(PASTA)):
        if f.endswith(".json"):
            try:
                p = carregar(f[:-5])
                out.append({"id": p["id"], "nome": p["nome"], "data": p["fonte"]["data"],
                            "amostra": p["fonte"]["amostra"]})
            except (OSError, ValueError, KeyError):
                continue
    return out


def carregar(pid):
    with open(caminho(pid), encoding="utf-8") as f:
        return json.load(f)


def salvar(perfil):
    os.makedirs(PASTA, exist_ok=True)
    tmp = caminho(perfil["id"]) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(perfil, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho(perfil["id"]))


def apagar(pid):
    c = caminho(pid)
    if os.path.isfile(c):
        os.remove(c)


# ------------------------------------------------------------------ coleta
def _ydl(flat=True):
    import yt_dlp
    return yt_dlp.YoutubeDL({"extract_flat": flat, "quiet": True, "no_warnings": True, "skip_download": True,
                             "playlistend": 60})


def _aba(url_canal, aba):
    url = url_canal.rstrip("/") + "/" + aba
    try:
        with _ydl() as y:
            info = y.extract_info(url, download=False)
    except Exception:
        return []
    return [{"id": e.get("id"), "titulo": e.get("title") or "", "dur": e.get("duration"),
             "views": e.get("view_count") or 0} for e in info.get("entries") or [] if e.get("id")]


def _palavras_legenda(info):
    """Le a legenda automatica (json3) e devolve so as contagens. O texto nao e guardado."""
    caps = info.get("automatic_captions") or {}
    lang = next((l for l in ("pt", "pt-BR", "pt-orig", "en", "en-orig") if l in caps), None)
    if not lang:
        return None
    fmt = next((c for c in caps[lang] if c.get("ext") == "json3"), None)
    if not fmt:
        return None
    try:
        with urllib.request.urlopen(fmt["url"], timeout=20) as r:
            dados = json.load(r)
    except Exception:
        return None
    tempos = []
    for ev in dados.get("events", []):
        t0 = ev.get("tStartMs", 0)
        for s in ev.get("segs") or []:
            txt = (s.get("utf8") or "").strip()
            if txt and txt != "\n":
                tempos += [(t0 + s.get("tOffsetMs", 0)) / 1000] * len(txt.split())
    if len(tempos) < 5:
        return None
    dur_fala = max(tempos[-1] - tempos[0], 1.0)
    return {"palavras": len(tempos), "ppm": round(len(tempos) / dur_fala * 60, 1),
            "palavras_3s": sum(1 for t in tempos if t < 3.0), "primeira_fala_s": round(tempos[0], 2)}


def _detalhe(vid, com_fala):
    try:
        with _ydl(flat=False) as y:
            d = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    except Exception:
        return None
    return {"id": vid, "data": d.get("upload_date"), "dur": d.get("duration"), "views": d.get("view_count"),
            "capitulos": len(d.get("chapters") or []),
            "fala": _palavras_legenda(d) if com_fala else None}


def _q(vals, q):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    return vals[min(int(q * (len(vals) - 1) + 0.5), len(vals) - 1)]


def _resumo_dur(itens):
    d = [i["dur"] for i in itens if i.get("dur")]
    if not d:
        return None
    vs = [i["views"] for i in itens if i.get("views")]   # a listagem as vezes vem sem views: ignora zeros
    return {"n": len(itens), "com_duracao": len(d), "dur_mediana_s": statistics.median(d), "dur_p25_s": _q(d, .25),
            "dur_p75_s": _q(d, .75), "views_mediana": int(statistics.median(vs)) if vs else None,
            "views_max": max(vs) if vs else None}


def _titulos(itens):
    ts = [i["titulo"] for i in itens if i.get("titulo")]
    if not ts:
        return None
    pal = [w for t in ts for w in re.findall(r"[\wÀ-ÿ]+", t.lower()) if w not in STOP and len(w) > 2]
    freq = sorted({w: pal.count(w) for w in set(pal)}.items(), key=lambda kv: -kv[1])[:10]

    def caps(t):
        ws = [w for w in re.findall(r"[A-Za-zÀ-ÿ]{3,}", t)]
        return sum(w.isupper() for w in ws) / max(len(ws), 1)

    pct = lambda f: round(100 * sum(1 for t in ts if f(t)) / len(ts))  # noqa: E731
    return {"n": len(ts), "caracteres_mediana": statistics.median(len(t) for t in ts),
            "pct_maioria_maiusculas": pct(lambda t: caps(t) > 0.6), "pct_emoji": pct(lambda t: _EMOJI.search(t)),
            "pct_pergunta": pct(lambda t: "?" in t), "pct_exclamacao": pct(lambda t: "!" in t),
            "pct_numeros": pct(lambda t: re.search(r"\d", t)), "pct_hashtag": pct(lambda t: "#" in t),
            "palavras_frequentes": [w for w, _ in freq]}


def gerar(nome, canais, aspectos=None, progresso=lambda f, m=None: None, visual=None):
    """Gera (ou atualiza) um perfil a partir de 1+ URLs de canal do YouTube."""
    aspectos = [a for a in (aspectos or list(ASPECTOS)) if a in ASPECTOS]
    curtos, longos = [], []
    for k, url in enumerate(canais):
        progresso(0.05 + 0.3 * k / max(len(canais), 1), f"lendo {url}")
        curtos += _aba(url, "shorts")
        longos += [v for v in _aba(url, "videos") if (v.get("dur") or 0) >= 180]
    if not curtos and not longos:
        raise RuntimeError("não encontrei vídeos públicos nesses links (confira a URL do canal)")
    amostra = sorted(curtos, key=lambda v: -v["views"])[:8] + sorted(longos, key=lambda v: -v["views"])[:6]
    recentes = curtos[:6] + longos[:6]               # as abas vem da mais nova para a mais antiga
    ids = list(dict.fromkeys(v["id"] for v in amostra + recentes))
    progresso(0.4, f"detalhando {len(ids)} vídeos")
    com_fala = "fala" in aspectos
    with ThreadPoolExecutor(6) as ex:
        det = {d["id"]: d for d in ex.map(lambda i: _detalhe(i, com_fala), ids) if d}

    # a aba /shorts nao traz duracao nem sempre views: completa com os detalhes da amostra
    for v in curtos + longos:
        if v["id"] in det:
            v["dur"] = v.get("dur") or det[v["id"]].get("dur")
            v["views"] = v.get("views") or det[v["id"]].get("views") or 0
    obs = {}
    if "duracao" in aspectos:
        obs["curtos"] = _resumo_dur(curtos)
        obs["longos"] = _resumo_dur(longos)
    if "publicacao" in aspectos:
        datas = sorted({dt.datetime.strptime(d["data"], "%Y%m%d") for d in det.values() if d.get("data")})
        gaps = [(b - a).days for a, b in zip(datas, datas[1:])]
        obs["publicacao"] = {"datas_analisadas": len(datas),
                             "dias_entre_posts_mediana": statistics.median(gaps) if gaps else None,
                             "mais_recente": datas[-1].strftime("%Y-%m-%d") if datas else None}
    if "titulos" in aspectos:
        obs["titulos_curtos"] = _titulos(curtos)
        obs["titulos_longos"] = _titulos(longos)
    if "fala" in aspectos:
        fc = [det[v["id"]]["fala"] for v in curtos if v["id"] in det and det[v["id"]].get("fala")]
        fl = [det[v["id"]]["fala"] for v in longos if v["id"] in det and det[v["id"]].get("fala")]
        obs["fala"] = {
            "curtos_medidos": len(fc), "longos_medidos": len(fl),
            "ppm_curtos_mediana": statistics.median(f["ppm"] for f in fc) if fc else None,
            "ppm_longos_mediana": statistics.median(f["ppm"] for f in fl) if fl else None,
            "palavras_3s_curtos_mediana": statistics.median(f["palavras_3s"] for f in fc) if fc else None,
            "primeira_fala_s_curtos_mediana": statistics.median(f["primeira_fala_s"] for f in fc) if fc else None}
    if "capitulos" in aspectos:
        caps = [det[v["id"]]["capitulos"] for v in longos if v["id"] in det]
        obs["capitulos"] = {"longos_analisados": len(caps),
                            "pct_com_capitulos": round(100 * sum(c > 0 for c in caps) / len(caps)) if caps else None,
                            "capitulos_mediana": statistics.median([c for c in caps if c]) if any(caps) else None}
    if "visual" in aspectos:
        obs["visual"] = visual  # None = ainda nao observado

    perfil = {"id": _slug(nome), "nome": nome, "aspectos": aspectos,
              "fonte": {"canais": canais, "data": dt.date.today().isoformat(),
                        "amostra": {"curtos": len(curtos), "longos": len(longos), "detalhados": len(det)}},
              "observado": obs, "derivado": derivar(obs),
              "limitacoes": ["Amostra das abas públicas (até 60 por aba) e detalhes de até ~26 vídeos.",
                             "Views variam com o tempo; os números são do dia da coleta.",
                             "Legendas automáticas erram palavras; servem só para medir ritmo.",
                             "O perfil descreve técnica de edição. Não copie roteiros, falas, vinhetas ou a identidade do criador."]}
    progresso(1.0, "perfil gerado")
    return perfil


PASTA_VIDEOS = os.path.join(PASTA, "videos")      # referencias/videos/<perfil>/*.mp4: o usuario solta os videos aqui
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".m4v")


def pasta_videos(nome):
    return os.path.join(PASTA_VIDEOS, _slug(nome))


def _fala_local(caminho, modelo):
    """Ritmo de fala de um video local (Whisper no PC). Como em _palavras_legenda: so contagens, o texto e descartado."""
    from . import legendas
    tempos = [w["start"] for w in legendas.transcrever(caminho, modelo)]
    if len(tempos) < 5:
        return None
    return {"palavras": len(tempos), "ppm": round(len(tempos) / max(tempos[-1] - tempos[0], 1.0) * 60, 1),
            "palavras_3s": sum(1 for t in tempos if t < 3.0), "primeira_fala_s": round(tempos[0], 2)}


def analisar_videos(nome, progresso=lambda f, m=None: None, com_fala=True, modelo="small"):
    """Perfil a partir dos videos de referencia que o usuario colocou em referencias/videos/<nome>/: duracao,
    ritmo de cortes (deteccao de cena do FFmpeg) e ritmo de fala. Mede tecnica de edicao; nada do video e copiado."""
    from . import midia
    d = pasta_videos(nome)
    arquivos = sorted(f for f in os.listdir(d) if f.lower().endswith(VIDEO_EXT)) if os.path.isdir(d) else []
    if not arquivos:
        raise RuntimeError(f"coloque os vídeos de referência em {d}")
    curtos, longos, por_video = [], [], []
    for k, arq in enumerate(arquivos):
        progresso(0.05 + 0.9 * k / len(arquivos), f"analisando {arq}")
        c = os.path.join(d, arq)
        inf = midia.info(c)
        cortes = [t for t in midia.cortes_de_cena(c, 0.3) if 0.3 < t < inf["dur"] - 0.3]
        curto = inf["h"] > inf["w"] or inf["dur"] <= 180
        v = {"arquivo": arq, "dur": round(inf["dur"], 1), "views": 0, "vertical": inf["h"] > inf["w"],
             "cortes_por_min": round(len(cortes) / max(inf["dur"], 1) * 60, 1),
             "plano_medio_s": round(inf["dur"] / (len(cortes) + 1), 2),
             "fala": _fala_local(c, modelo) if com_fala and inf["audio"] else None}
        (curtos if curto else longos).append(v)
        por_video.append({k2: v[k2] for k2 in ("arquivo", "dur", "vertical", "cortes_por_min", "plano_medio_s", "fala")})
    med = lambda vs: round(statistics.median(vs), 1) if vs else None
    fc = [v["fala"] for v in curtos if v["fala"]]
    fl = [v["fala"] for v in longos if v["fala"]]
    obs = {"curtos": _resumo_dur(curtos), "longos": _resumo_dur(longos),
           "fala": {"curtos_medidos": len(fc), "longos_medidos": len(fl),
                    "ppm_curtos_mediana": med([f["ppm"] for f in fc]), "ppm_longos_mediana": med([f["ppm"] for f in fl]),
                    "palavras_3s_curtos_mediana": med([f["palavras_3s"] for f in fc]),
                    "primeira_fala_s_curtos_mediana": med([f["primeira_fala_s"] for f in fc])},
           "visual": {"cortes_por_min_curtos": med([v["cortes_por_min"] for v in curtos]),
                      "cortes_por_min_longos": med([v["cortes_por_min"] for v in longos]),
                      "medido": "detecção de corte de cena do FFmpeg nos vídeos locais"},
           "por_video": por_video}
    progresso(1.0, "perfil gerado")
    return {"id": _slug(nome), "nome": nome, "aspectos": ["duracao", "fala", "visual"],
            "fonte": {"videos": arquivos, "pasta": d, "data": dt.date.today().isoformat(),
                      "amostra": {"curtos": len(curtos), "longos": len(longos)}},
            "observado": obs, "derivado": derivar(obs),
            "limitacoes": ["Mede duração, ritmo de cortes e de fala; layout e estilo de legenda você escolhe olhando os vídeos.",
                           "A detecção de corte erra em transições suaves e em flashes.",
                           "O perfil descreve técnica de edição. Não copie roteiros, falas, vinhetas ou a identidade do criador."]}


def derivar(obs):
    """Transforma o que foi observado em parametros que o Clipador sabe aplicar."""
    d = {"curto": {}, "longo": {}, "titulo": {}}
    if (obs.get("curtos") or {}).get("dur_mediana_s"):
        d["curto"]["duracao_alvo"] = round(obs["curtos"]["dur_mediana_s"])
    if (obs.get("longos") or {}).get("dur_mediana_s"):
        d["longo"]["duracao_alvo"] = round(obs["longos"]["dur_mediana_s"])
    f = obs.get("fala") or {}
    if f.get("ppm_curtos_mediana"):
        d["curto"]["palavras_por_minuto"] = f["ppm_curtos_mediana"]
    if f.get("palavras_3s_curtos_mediana") is not None:
        d["curto"]["palavras_nos_3s"] = f["palavras_3s_curtos_mediana"]
    if f.get("ppm_longos_mediana"):
        d["longo"]["palavras_por_minuto"] = f["ppm_longos_mediana"]
    c = obs.get("capitulos") or {}
    if c.get("pct_com_capitulos") is not None:
        d["longo"]["capitulos"] = c["pct_com_capitulos"] >= 50
    for k, alvo in (("titulos_curtos", "curto"), ("titulos_longos", "longo")):
        t = obs.get(k)
        if t:
            d["titulo"][alvo] = {"max_caracteres": int(t["caracteres_mediana"] * 1.15),
                                 "maiusculas": t["pct_maioria_maiusculas"] >= 50,
                                 "emoji": t["pct_emoji"] >= 40}
    v = obs.get("visual") or {}
    if v.get("cortes_por_min_curtos"):
        d["curto"]["max_cena"] = round(60 / v["cortes_por_min_curtos"], 1)
    if v.get("cortes_por_min_longos"):
        d["longo"]["max_cena"] = round(60 / v["cortes_por_min_longos"], 1)
    for k in ("layout_curtos", "legenda_curtos"):
        if v.get(k):
            d["curto"][k.split("_")[0]] = v[k]
    return d


# ------------------------------------------------------------------ comparacao
def metricas_projeto(p):
    """Metricas do projeto comparaveis com um perfil."""
    d = projeto.pasta(p["nome"])
    total = projeto.duracao_timeline(p)
    cortes = max(len(p["segmentos"]) - 1, 0)
    for s in p["segmentos"]:   # cortes de cena dentro de cada trecho tambem contam
        try:
            f = projeto.fonte(p, s["fonte"])
        except KeyError:
            continue
        cortes += sum(1 for c in f.get("cenas") or [] if s["ini"] + 0.2 < c["ini"] < s["fim"] - 0.2)
    m = {"duracao_s": round(total, 1), "cortes_por_min": round(cortes / total * 60, 1) if total else None,
         "cena_media_s": round(total / (cortes + 1), 1) if total else None}
    cart_path = os.path.join(d, "legenda_cartoes.json")
    if p.get("narracao") and os.path.isfile(cart_path):
        with open(cart_path, encoding="utf-8") as f:
            cart = [c for c in json.load(f) if not c.get("provisorio")]
        ws = [w for c in cart for w in c["palavras"]]
        if len(ws) >= 5:
            span = max(ws[-1]["end"] - ws[0]["start"], 1)
            m["palavras_por_minuto"] = round(len(ws) / span * 60, 1)
            m["palavras_nos_3s"] = sum(1 for w in ws if w["start"] < 3)
            m["primeira_fala_s"] = round(ws[0]["start"], 2)
    tit = (p.get("publicacao") or {}).get("titulo")
    if tit:
        letras = re.findall(r"[A-Za-zÀ-ÿ]{3,}", tit)
        m["titulo_caracteres"] = len(tit)
        m["titulo_maiusculas"] = sum(w.isupper() for w in letras) / max(len(letras), 1) > 0.6
    return m


def comparar(p, perfil):
    """Lista de comparacoes: observado no perfil x seu projeto x sugestao (explicavel, nada automatico)."""
    tipo = p.get("tipo", "curto")
    m = metricas_projeto(p)
    obs, der = perfil["observado"], perfil["derivado"].get(tipo, {})
    out = []

    def item(aspecto, ref, seu, ok, sugestao):
        out.append({"aspecto": aspecto, "referencia": ref, "seu_projeto": seu,
                    "situacao": "ok" if ok else "atencao", "sugestao": None if ok else sugestao})

    res = obs.get("curtos" if tipo == "curto" else "longos")
    if res and res.get("dur_p25_s"):
        lo, hi = res["dur_p25_s"], res["dur_p75_s"]
        ok = lo * 0.85 <= m["duracao_s"] <= hi * 1.15
        item("Duração", f"{_fmt(lo)}–{_fmt(hi)} (mediana {_fmt(res['dur_mediana_s'])})", _fmt(m["duracao_s"]), ok,
             f"Ajuste a timeline para perto de {_fmt(res['dur_mediana_s'])}.")
    v = obs.get("visual") or {}
    cpm = v.get("cortes_por_min_curtos" if tipo == "curto" else "cortes_por_min_longos")
    if cpm and m.get("cortes_por_min") is not None:
        ok = cpm * 0.7 <= m["cortes_por_min"] <= cpm * 1.4
        item("Ritmo de cortes", f"{cpm} cortes/min (cena de ~{round(60 / cpm, 1)} s)",
             f"{m['cortes_por_min']} cortes/min", ok,
             "Mais cortes: divida cenas longas." if m["cortes_por_min"] < cpm else "Menos cortes: deixe as cenas respirarem.")
    ppm = der.get("palavras_por_minuto")
    if ppm and m.get("palavras_por_minuto"):
        ok = ppm * 0.8 <= m["palavras_por_minuto"] <= ppm * 1.2
        item("Ritmo de fala", f"{ppm} palavras/min", f"{m['palavras_por_minuto']} palavras/min", ok,
             "Fale um pouco mais rápido ou corte pausas." if m["palavras_por_minuto"] < ppm else "Fale um pouco mais devagar.")
    p3 = der.get("palavras_nos_3s")
    if tipo == "curto" and p3 is not None and "palavras_nos_3s" in m:
        ok = m["palavras_nos_3s"] >= p3 * 0.7
        item("Fala nos 3 primeiros segundos", f"{p3} palavras", f"{m['palavras_nos_3s']} palavras", ok,
             "Comece falando já no primeiro segundo; deixe o contexto para depois.")
    if tipo == "longo" and der.get("capitulos") is not None:
        n = sum(1 for s in p["segmentos"] if s.get("rotulo"))
        item("Capítulos", "usa capítulos" if der["capitulos"] else "quase não usa", f"{n} rótulos", (n >= 3) or not der["capitulos"],
             "Escreva rótulos nos trechos que abrem cada parte (pelo menos 3).")
    t = perfil["derivado"].get("titulo", {}).get(tipo)
    if t and "titulo_caracteres" in m:
        ok = m["titulo_caracteres"] <= t["max_caracteres"] and (m["titulo_maiusculas"] == t["maiusculas"])
        item("Título", f"até ~{t['max_caracteres']} caracteres, {'MAIÚSCULAS' if t['maiusculas'] else 'normal'}",
             f"{m['titulo_caracteres']} caracteres, {'MAIÚSCULAS' if m['titulo_maiusculas'] else 'normal'}", ok,
             "Encurte o título ou ajuste as maiúsculas para o padrão da referência.")
    if not (p.get("gancho") or {}).get("texto") and tipo == "curto":
        item("Gancho na tela", "texto de abertura nos primeiros segundos (padrão dos Shorts analisados)", "sem gancho", False,
             "Escreva um gancho na aba Estilo.")
    return {"metricas": m, "itens": out}


def aplicar(p, perfil):
    """Aplica os parametros derivados (duracao-alvo, capitulos, legenda/layout se observados). Retorna o que mudou."""
    tipo = p.get("tipo", "curto")
    der = perfil["derivado"].get(tipo, {})
    mudou = []
    if der.get("duracao_alvo"):
        p.setdefault("formato_cfg", {})["duracao_alvo"] = der["duracao_alvo"]
        mudou.append(f"duração-alvo {_fmt(der['duracao_alvo'])}")
    if tipo == "longo" and der.get("capitulos") is not None:
        p["formato_cfg"]["capitulos"] = bool(der["capitulos"])
        mudou.append("capítulos " + ("ligados" if der["capitulos"] else "desligados"))
    if tipo == "curto" and der.get("legenda") in ("karaoke", "palavra", "caixa"):
        p["legenda"]["estilo"] = der["legenda"]
        mudou.append(f"legenda {der['legenda']}")
    if tipo == "curto" and der.get("layout") in ("tela_cheia", "empilhado", "comparacao"):
        p["layout"] = der["layout"]
        mudou.append(f"layout {der['layout']}")
    p["referencia"] = perfil["id"]
    return mudou


def _fmt(s):
    s = float(s)
    return f"{s:.0f} s" if s < 120 else f"{int(s // 60)} min {int(s % 60):02d} s"
