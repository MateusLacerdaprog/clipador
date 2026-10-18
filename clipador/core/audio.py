"""Audio multipista: modelo das 4 trilhas, migracao de projetos antigos e grafo de mixagem FFmpeg.

Trilhas (tudo nao destrutivo: os arquivos de origem nunca sao alterados)
  original : som dos trechos do video. Volume da trilha (com/sem narracao) + volume ou mudo POR TRECHO
             (campo "audio" de cada segmento: {"modo": "padrao"|"volume"|"mudo", "db": float}).
  musica   : 1 arquivo da biblioteca musicas/, com inicio/fim no video, ponto de entrada no arquivo,
             fade-in/out e repeticao.
  narracao : narracao.wav do projeto (gravada ou importada), com deslocamento, fades e tratamento de voz.
  efeitos  : lista de sons curtos da biblioteca efeitos/, cada um num instante do video.
  mix      : ducking (trilha e jogo abaixam quando a voz fala) e normalizacao final -14 LUFS.
"""
import copy
import uuid

# Ordem recomendada: HPF > denoise > EQ > de-esser > compressor > limiter (regra 4 do CLAUDE.md)
CADEIA_VOZ = (
    "highpass=f=90,"
    "afftdn=nf=-28,"
    "equalizer=f=300:t=q:w=1.2:g=-2,"      # reduz caixa/abafado
    "equalizer=f=3000:t=q:w=1.0:g=4,"      # presenca/inteligibilidade
    "equalizer=f=6500:t=q:w=1.0:g=2,"      # brilho
    "deesser=i=0.2,"
    "acompressor=threshold=-20dB:ratio=3:attack=10:release=150:makeup=4,"
    "alimiter=limit=0.89"
)
LOUDNORM = "loudnorm=I=-14:TP=-1:LRA=9"
# (threshold, ratio) do sidechaincompress; "media" = comportamento original do projeto
DUCKING = {"leve": (0.05, 4), "media": (0.03, 8), "forte": (0.02, 14)}
FORMATO = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"

PADRAO = {
    "versao": 2,
    "original": {"ativo": True, "db": 0.0, "db_com_narracao": -20.0},
    "musica": {"ativo": True, "arquivo": None, "db": -16.0, "inicio_arquivo": 0.0, "inicio_video": 0.0,
               "fim_video": None, "fade_in": 0.3, "fade_out": 1.5, "loop": True},
    "narracao": {"ativo": True, "db": 0.0, "deslocamento": 0.0, "fade_in": 0.0, "fade_out": 0.0,
                 "tratamento": True},
    "efeitos": [],
    "mix": {"ducking": True, "ducking_forca": "media", "normalizar": True},
}
EFEITO_PADRAO = {"ativo": True, "arquivo": None, "em": 0.0, "db": -6.0, "inicio_arquivo": 0.0, "dur": None,
                 "fade_in": 0.0, "fade_out": 0.05}


# ------------------------------------------------------------------ modelo
def migrar(a):
    """Converte o formato antigo (chaves soltas jogo_db, musica_*, ...) para o v2 e completa padroes."""
    a = copy.deepcopy(a or {})
    if a.get("versao") != 2:
        v1 = a
        a = copy.deepcopy(PADRAO)
        o, m, n, x = a["original"], a["musica"], a["narracao"], a["mix"]
        if "jogo_sem_narracao_db" in v1:
            o["db"] = float(v1["jogo_sem_narracao_db"])
        if "jogo_db" in v1:
            o["db_com_narracao"] = float(v1["jogo_db"])
        if v1.get("jogo_mudo"):
            o["ativo"] = False
        if "narracao_db" in v1:
            n["db"] = float(v1["narracao_db"])
        if "ducking" in v1:
            x["ducking"] = bool(v1["ducking"])
        for antigo, novo in (("musica_arquivo", "arquivo"), ("musica_db", "db"), ("musica_inicio", "inicio_arquivo"),
                             ("musica_fade", "fade_out"), ("musica_loop", "loop")):
            if antigo in v1:
                m[novo] = v1[antigo]
        return validar(a)
    out = copy.deepcopy(PADRAO)
    for k in ("original", "musica", "narracao", "mix"):
        out[k].update(a.get(k) or {})
    out["efeitos"] = [{**EFEITO_PADRAO, **e} for e in a.get("efeitos") or []]
    return validar(out)


def _num(v, padrao, lo=None, hi=None, nulo=False):
    if v is None or v == "":
        return None if nulo else padrao
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"valor numerico invalido: {v!r}")
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def validar(a):
    """Normaliza tipos e limites (tudo que vai para o FFmpeg passa por aqui). Levanta ValueError."""
    o, m, n, x = a["original"], a["musica"], a["narracao"], a["mix"]
    o["ativo"] = bool(o["ativo"])
    o["db"] = _num(o["db"], 0.0, -60, 12)
    o["db_com_narracao"] = _num(o["db_com_narracao"], -20.0, -60, 12)
    m["ativo"], m["loop"] = bool(m["ativo"]), bool(m["loop"])
    m["db"] = _num(m["db"], -16.0, -60, 12)
    for k in ("inicio_arquivo", "inicio_video", "fade_in", "fade_out"):
        m[k] = _num(m[k], 0.0, 0, 36000)
    m["fim_video"] = _num(m["fim_video"], None, 0, 36000, nulo=True)
    n["ativo"], n["tratamento"] = bool(n["ativo"]), bool(n["tratamento"])
    n["db"] = _num(n["db"], 0.0, -30, 18)
    n["deslocamento"] = _num(n["deslocamento"], 0.0, -36000, 36000)
    n["fade_in"] = _num(n["fade_in"], 0.0, 0, 30)
    n["fade_out"] = _num(n["fade_out"], 0.0, 0, 30)
    x["ducking"], x["normalizar"] = bool(x["ducking"]), bool(x["normalizar"])
    if x["ducking_forca"] not in DUCKING:
        x["ducking_forca"] = "media"
    a["efeitos"] = [{**EFEITO_PADRAO, **e} for e in a.get("efeitos") or []]
    for e in a["efeitos"]:
        e.setdefault("id", uuid.uuid4().hex[:8])
        e["arquivo"] = str(e["arquivo"]) if e["arquivo"] else None
        e["ativo"] = bool(e["ativo"])
        e["em"] = _num(e["em"], 0.0, 0, 36000)
        e["db"] = _num(e["db"], -6.0, -60, 12)
        e["inicio_arquivo"] = _num(e["inicio_arquivo"], 0.0, 0, 36000)
        e["dur"] = _num(e["dur"], None, 0.05, 36000, nulo=True)
        e["fade_in"] = _num(e["fade_in"], 0.0, 0, 30)
        e["fade_out"] = _num(e["fade_out"], 0.0, 0, 30)
    return a


def nivel_trecho(seg, a, tem_voz):
    """Volume (dB) do som original de um trecho, ou None se estiver mudo."""
    o = a["original"]
    if not o["ativo"]:
        return None
    cfg = seg.get("audio") or {}
    modo = cfg.get("modo", "padrao")
    if modo == "mudo":
        return None
    if modo == "volume":
        return _num(cfg.get("db"), 0.0, -60, 12)
    return o["db_com_narracao"] if tem_voz else o["db"]


def _lin(db):
    return 10 ** (db / 20.0)


def _fades(dur, fade_in, fade_out):
    f = []
    fi = min(fade_in, dur / 2)
    fo = min(fade_out, dur / 2)
    if fi > 0:
        f.append(f"afade=t=in:st=0:d={fi:.3f}")
    if fo > 0:
        f.append(f"afade=t=out:st={max(dur - fo, 0):.3f}:d={fo:.3f}")
    return ("," + ",".join(f)) if f else ""


def _posicionar(inicio, total):
    """Atrasa a camada ate `inicio` e completa com silencio ate `total` (toda camada termina junto)."""
    atraso = f"adelay={int(round(inicio * 1000))}:all=1," if inicio > 0.0005 else ""
    return f"{atraso}apad=whole_dur={total:.3f},atrim=0:{total:.3f}"


# ------------------------------------------------------------------ grafo FFmpeg
def grafo_mix(jogo, a, total, voz=None, musica=None, efeitos=(), normalizar=None, saida="aout"):
    """Monta o filtergraph de audio.

    jogo   : rotulo do audio dos trechos ja concatenado e com volume por trecho aplicado (ou None)
    voz    : (indice_entrada, duracao_s) da narracao, ou None
    musica : (indice_entrada, duracao_arquivo_s) ou None (o -stream_loop/-ss ficam na entrada)
    efeitos: [(indice_entrada, efeito_dict, duracao_arquivo_s)]
    """
    f, cama = [], []
    if jogo:
        if a["original"]["ativo"]:
            f.append(f"[{jogo}]{_posicionar(0, total)}[jogo_v]")
            cama.append("[jogo_v]")
        else:
            f.append(f"[{jogo}]anullsink")

    if musica is not None and a["musica"]["ativo"]:
        m = a["musica"]
        idx, dur_arq = musica
        ini_v = min(m["inicio_video"], total)
        fim_v = total if m["fim_video"] is None else min(max(m["fim_video"], ini_v), total)
        dur = fim_v - ini_v
        if not m["loop"] and dur_arq:
            dur = min(dur, max(dur_arq - m["inicio_arquivo"], 0.0))
        if dur > 0.05:
            f.append(f"[{idx}:a]{FORMATO},atrim=0:{dur:.3f},asetpts=PTS-STARTPTS"
                     f"{_fades(dur, m['fade_in'], m['fade_out'])},volume={_lin(m['db']):.4f},"
                     f"{_posicionar(ini_v, total)}[mus_v]")
            cama.append("[mus_v]")
        else:
            f.append(f"[{idx}:a]anullsink")
    elif musica is not None:
        f.append(f"[{musica[0]}:a]anullsink")

    if not cama:
        f.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{total:.3f}[cama]")
    elif len(cama) == 1:
        f.append(f"{cama[0]}anull[cama]")
    else:
        f.append(f"{''.join(cama)}amix=inputs={len(cama)}:duration=longest:normalize=0[cama]")

    finais = []
    if voz is not None and a["narracao"]["ativo"]:
        n = a["narracao"]
        idx, dur_voz = voz
        desl = n["deslocamento"]
        corte = f"atrim=start={-desl:.3f}," if desl < 0 else ""
        dur_util = max((dur_voz or total) - max(-desl, 0), 0.05)
        trat = f"{CADEIA_VOZ}," if n["tratamento"] else ""
        ganho = f"volume={_lin(n['db']):.4f}," if n["db"] else ""
        f.append(f"[{idx}:a]{FORMATO},{corte}asetpts=PTS-STARTPTS,{trat}{ganho}"
                 f"anull{_fades(dur_util, n['fade_in'], n['fade_out'])},"
                 f"{_posicionar(max(desl, 0), total)},asplit=2[voz_mix][voz_sc]")
        if a["mix"]["ducking"]:
            thr, ratio = DUCKING[a["mix"]["ducking_forca"]]
            f.append(f"[cama][voz_sc]sidechaincompress=threshold={thr}:ratio={ratio}:attack=5:release=300[cama_d]")
            finais += ["[voz_mix]", "[cama_d]"]
        else:
            f.append("[voz_sc]anullsink")
            finais += ["[voz_mix]", "[cama]"]
    else:
        if voz is not None:
            f.append(f"[{voz[0]}:a]anullsink")
        finais.append("[cama]")

    # efeitos entram depois do ducking (nao sao abaixados pela voz)
    for k, (idx, e, dur_arq) in enumerate(efeitos):
        if not e["ativo"] or e["em"] >= total:
            f.append(f"[{idx}:a]anullsink")
            continue
        disponivel = max((dur_arq or 0) - e["inicio_arquivo"], 0.05)
        dur = min(e["dur"] or disponivel, disponivel, total - e["em"])
        f.append(f"[{idx}:a]{FORMATO},atrim=start={e['inicio_arquivo']:.3f}:duration={dur:.3f},asetpts=PTS-STARTPTS"
                 f"{_fades(dur, e['fade_in'], e['fade_out'])},volume={_lin(e['db']):.4f},"
                 f"{_posicionar(e['em'], total)}[fx{k}]")
        finais.append(f"[fx{k}]")

    norm = a["mix"]["normalizar"] if normalizar is None else normalizar
    fim = LOUDNORM if norm else "anull"
    if len(finais) == 1:
        f.append(f"{finais[0]}{fim}[{saida}]")
    else:
        f.append(f"{''.join(finais)}amix=inputs={len(finais)}:duration=longest:normalize=0,{fim}[{saida}]")
    return ";".join(f)
