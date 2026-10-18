"""Similaridade entre roteiros do mesmo canal (risco "conteúdo inautêntico/repetitivo", F1/F5).

É um ALERTA de repetição dentro do próprio canal — não prova originalidade jurídica nem compara com a internet.
Duas medidas: trechos de 3 palavras em comum (Jaccard) e abertura igual (primeiras palavras do gancho).
"""
import re
import unicodedata

from . import estudio

LIMIAR_AVISO = 0.35          # fração de trechos de 3 palavras em comum que já indica roteiro "intercambiável"
STOP = set("a o e de da do das dos em no na nos nas um uma uns umas que para pra com por se ao aos as os "
           "e é foi ser era isso esse essa este esta mas ou como mais muito ja nao sim the of to and in is".split())


def _palavras(texto):
    s = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return [w for w in re.findall(r"[a-z0-9]+", s)]


def _trechos(texto):
    ws = [w for w in _palavras(texto) if w not in STOP]
    return {tuple(ws[i:i + 3]) for i in range(len(ws) - 2)}


def similaridade(a, b):
    ta, tb = _trechos(a), _trechos(b)
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 3)


def mesma_abertura(a, b, n=5):
    pa, pb = _palavras(a)[:n], _palavras(b)[:n]
    return len(pa) == n and pa == pb


def comparar_no_canal(roteiro, texto_de):
    """[(id, similaridade, abertura_igual)] dos outros roteiros do mesmo canal, do mais parecido ao menos."""
    meu = texto_de(roteiro)
    out = []
    for r in estudio.listar("roteiros"):
        if r["id"] == roteiro["id"] or r.get("canal") != roteiro.get("canal"):
            continue
        outro = texto_de(r)
        out.append((r["id"], similaridade(meu, outro),
                    mesma_abertura(roteiro.get("blocos", {}).get("gancho", ""), r.get("blocos", {}).get("gancho", ""))))
    return sorted(out, key=lambda x: -x[1])
