"""Clipar por pedido ("o momento em que falam do Jason") e transcricao da FONTE.

transcrever_fonte() : Whisper local no audio do video (palavras com tempo), em cache na pasta do projeto.
buscar()            : busca LOCAL no que e falado (sem acento, prefixo das palavras) -> momentos com o trecho dito.
pedido_ia()         : monta o texto para a IA (transcricao + cenas + momentos medidos). A IA nunca ve o video:
                      so acha o que foi FALADO ou o que os sinais medidos indicam.
"""
import json
import os
import re
import unicodedata

from . import legendas, midia

STOP = set("""a o as os um uma uns umas de da do das dos em na no nas nos por para pra pro com sem que se e ou
mas como quando onde qual quais quem ele ela eles elas eu voce voces nos isso esse essa este esta aquilo ao aos
the and of to in on at for with is are was were it this that momento momentos parte trecho video clipe hora
mostra mostrar quero achar ache encontre onde tem""".split())
VERSAO = 1


def norm(t):
    t = unicodedata.normalize("NFKD", str(t).lower())
    return re.sub(r"[^a-z0-9 ]", "", "".join(c for c in t if not unicodedata.combining(c)))


def termos(texto):
    vistos = []
    for t in norm(texto).split():
        if len(t) >= 3 and t not in STOP and t not in vistos:
            vistos.append(t)
    return vistos


def _casa(palavra, termo):
    raiz = termo[:max(4, len(termo) - 3)] if len(termo) > 4 else termo   # "explosoes" casa "explosao"
    return palavra.startswith(raiz)


# ------------------------------------------------------------------ transcricao
def caminho_cache(pasta_projeto, fid):
    return os.path.join(pasta_projeto, "cache", fid, "transcricao.json")


def _assinatura(caminho):
    st = os.stat(caminho)
    return [VERSAO, st.st_size, int(st.st_mtime)]


def ler_transcricao(pasta_projeto, fonte):
    c = caminho_cache(pasta_projeto, fonte["id"])
    if not os.path.isfile(c) or not os.path.isfile(fonte["caminho"]):
        return None
    try:
        with open(c, encoding="utf-8") as f:
            d = json.load(f)
    except ValueError:
        return None
    return d["palavras"] if d.get("assinatura") == _assinatura(fonte["caminho"]) else None


def transcrever_fonte(pasta_projeto, fonte, modelo="small", progresso=lambda f, m=None: None):
    if not fonte["info"].get("audio"):
        raise ValueError("este vídeo não tem áudio para transcrever")
    pronto = ler_transcricao(pasta_projeto, fonte)
    if pronto is not None:
        return pronto
    c = caminho_cache(pasta_projeto, fonte["id"])
    os.makedirs(os.path.dirname(c), exist_ok=True)
    wav = os.path.join(os.path.dirname(c), "audio16k.wav")
    progresso(0.05, "extraindo o áudio")
    midia.para_wav(fonte["caminho"], wav, sr=16000)
    progresso(0.1, "transcrevendo (Whisper local; vídeos longos demoram)")
    from faster_whisper import WhisperModel

    wm = WhisperModel(modelo, device="cpu", compute_type="int8")
    # idioma detectado: trailers e gameplays costumam falar ingles
    segs, _ = wm.transcribe(legendas._audio_16k(wav), language=None, word_timestamps=True, vad_filter=True)
    palavras, dur = [], max(fonte["info"]["dur"], 1)
    for s in segs:
        progresso(0.1 + 0.85 * min(s.end / dur, 1), f"transcrevendo {int(s.end // 60)}:{int(s.end % 60):02d}")
        for w in s.words or []:
            if w.word.strip():
                palavras.append({"w": w.word.strip(), "start": round(float(w.start), 2), "end": round(float(w.end), 2)})
    os.remove(wav)
    with open(c + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"assinatura": _assinatura(fonte["caminho"]), "palavras": palavras}, f, ensure_ascii=False)
    os.replace(c + ".tmp", c)
    return palavras


def _mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def _citacao(palavras, t, n=7):
    i = min(range(len(palavras)), key=lambda k: abs(palavras[k]["start"] - t))
    trecho = " ".join(w["w"] for w in palavras[max(0, i - n): i + n + 1])
    return f"“…{trecho[:140]}…”"


# ------------------------------------------------------------------ busca local
def buscar(palavras, texto, dur, duracao=20.0, quantidade=5, cortes=()):
    ts = termos(texto)
    if not ts:
        raise ValueError("escreva o que procurar (ex.: nomes, lugares, armas, carros)")
    hits = [(w["start"], t) for w in palavras for t in ts if _casa(norm(w["w"]), t)]
    if not hits:
        return []
    duracao = min(duracao, dur)
    cortes = sorted(cortes)
    cands = []
    for h, _ in hits:
        ini = max(0.0, h - 2.0)                              # um pouco antes da fala, para dar contexto
        antes = [c for c in cortes if ini - 1.5 <= c <= ini]
        if antes:
            ini = antes[-1]
        ini = min(ini, dur - duracao)
        fim = ini + duracao
        dentro = [(t, k) for t, k in hits if ini <= t < fim]
        distintos = {k for _, k in dentro}
        cands.append((len(distintos) * 3 + min(len(dentro), 6), ini, fim, h, distintos, len(dentro)))
    saida = []
    for pts, ini, fim, h, distintos, n in sorted(cands, key=lambda c: (-c[0], c[1])):
        if len(saida) >= quantidade:
            break
        if any(ini < m["fim"] and fim > m["ini"] for m in saida):
            continue
        saida.append({"ini": round(ini, 2), "fim": round(fim, 2), "pico": round(h, 2),
                      "nota": int(min(100, 45 + 12 * len(distintos) + 3 * min(n, 6))),
                      "motivos": [f"fala em {_mmss(h)}: {_citacao(palavras, h)}",
                                  f"{len(distintos)} de {len(ts)} termos do pedido ({', '.join(sorted(distintos))})"],
                      "alertas": [] if len(distintos) == len(ts) else
                      [f"não achei: {', '.join(t for t in ts if t not in distintos)}"], "medidas": {}})
    return saida


# ------------------------------------------------------------------ IA
SCHEMA_IA = {"type": "object", "properties": {
    "momentos": {"type": "array", "items": {"type": "object", "properties": {
        "ini": {"type": "number"}, "fim": {"type": "number"}, "porque": {"type": "string"}},
        "required": ["ini", "fim", "porque"]}},
    "observacao": {"type": "string"}}, "required": ["momentos", "observacao"]}


def texto_transcricao(palavras, limite=14000):
    """Linhas "[m:ss] frase" (quebra em pausas >= 0,8 s), cortadas em `limite` caracteres."""
    linhas, atual, t0, fim_ant = [], [], None, None
    for w in palavras:
        if atual and (w["start"] - fim_ant >= 0.8 or len(atual) >= 25):
            linhas.append(f"[{_mmss(t0)}] {' '.join(atual)}")
            atual = []
        if not atual:
            t0 = w["start"]
        atual.append(w["w"])
        fim_ant = w["end"]
    if atual:
        linhas.append(f"[{_mmss(t0)}] {' '.join(atual)}")
    out = "\n".join(linhas)
    return out if len(out) <= limite else out[:limite] + "\n[...transcrição cortada por tamanho]"


def prompt_ia(texto, fonte, palavras, medidos, duracao, quantidade):
    linhas = [f"Vídeo-fonte: {fonte['nome']} ({fonte['info']['dur']:.0f} s). Você NÃO vê a imagem: use só a fala "
              "transcrita e os sinais medidos abaixo. Se o pedido depender só do que aparece na tela e não houver "
              "pista na fala ou nos sinais, diga isso na observação em vez de inventar.",
              f"Pedido do usuário: {texto.strip()[:500]}",
              f"Quero até {quantidade} trechos de ~{duracao:.0f} s (ini/fim em segundos do vídeo-fonte, sem sobreposição), "
              "do mais relevante para o menos, com o motivo em uma frase.",
              "Momentos com mais ação medidos no áudio/imagem: " + "; ".join(
                  f"{m['ini']:.0f}-{m['fim']:.0f} s ({', '.join(m['motivos'])})" for m in medidos[:10]) if medidos else
              "Momentos medidos: (não analisados)",
              "Transcrição:\n" + (texto_transcricao(palavras) if palavras else "(sem transcrição)")]
    return "\n".join(linhas)


def validar_ia(dados, dur, duracao):
    """Converte a resposta da IA em momentos, descartando tempos impossiveis (nao confia cegamente)."""
    out = []
    for m in (dados or {}).get("momentos") or []:
        try:
            ini, fim = float(m["ini"]), float(m["fim"])
        except (KeyError, TypeError, ValueError):
            continue
        ini, fim = max(0.0, ini), min(dur, fim)
        if fim - ini < 2 or fim - ini > max(duracao * 2, 60) or any(ini < o["fim"] and fim > o["ini"] for o in out):
            continue
        out.append({"ini": round(ini, 2), "fim": round(fim, 2), "pico": round(ini, 2), "nota": None,
                    "motivos": [f"IA: {str(m.get('porque') or '')[:200]}"], "alertas": [], "medidas": {}})
    return out
