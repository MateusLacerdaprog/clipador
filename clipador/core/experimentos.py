"""Experimentos controlados (Fase 10): hipótese, variantes A/B ligadas a vídeos publicados, métrica primária e
leitura honesta. Regras: amostra mínima por variante; comparação por MEDIANA (views de Shorts são assimétricas);
intervalo de confiança da diferença por bootstrap; "inconclusivo" sempre que a amostra for pequena ou o intervalo
cruzar zero; resultado é ASSOCIAÇÃO (publicações diferem em tema, dia, público-semente), nunca prova de causa.
O aprendizado gera nova hipótese; nunca "copiar o vídeo que foi melhor".
"""
import random
import statistics

from . import estudio, metricas

METRICAS = ("views", "views_engajadas", "escolheram_assistir_pct", "duracao_media_s", "pct_assistido",
            "likes", "comentarios", "compartilhamentos", "inscritos", "receita_usd")
VARIAVEIS = ("gancho", "duracao", "formato", "edicao", "narracao", "tema", "outra")
AMOSTRA_MINIMA = 10


def criar(dados):
    d = dados or {}
    hip = str(d.get("hipotese") or "").strip()
    if len(hip) < 10:
        raise ValueError("escreva a hipótese (o que você espera que mude e por quê)")
    if d.get("variavel") not in VARIAVEIS:
        raise ValueError(f"variável deve ser uma de: {', '.join(VARIAVEIS)}")
    if d.get("metrica", "views") not in METRICAS:
        raise ValueError(f"métrica deve ser uma de: {', '.join(METRICAS)}")
    e = {"id": estudio.novo_id("exp"), "canal": d.get("canal"), "hipotese": hip[:500], "variavel": d["variavel"],
         "metrica": d.get("metrica", "views"), "janela_dias": int(d.get("janela_dias") or 7),
         "amostra_minima": max(3, int(d.get("amostra_minima") or AMOSTRA_MINIMA)),
         "variantes": {"A": [], "B": []}, "descricao_variantes": d.get("descricao_variantes") or {"A": "", "B": ""},
         "criado_em": estudio.agora(), "status": "aberto"}
    return estudio.gravar("experimentos", e)


def ligar(id_, variante, video_id):
    e = estudio.ler("experimentos", id_)
    if variante not in e["variantes"]:
        raise ValueError("variante deve ser A ou B")
    if any(video_id in v for v in e["variantes"].values()):
        raise ValueError("este vídeo já está no experimento")
    e["variantes"][variante].append(video_id)
    return estudio.gravar("experimentos", e)


def _valores(e, variante):
    out = []
    for vid in e["variantes"][variante]:
        linha = metricas.ultimo(vid)
        v = (linha or {}).get("metricas", {}).get(e["metrica"])
        if v is not None:
            out.append(v)
    return out


def _ic_diferenca_medianas(a, b, reamostras=2000, semente=7):
    rng = random.Random(semente)
    difs = sorted(statistics.median(rng.choices(b, k=len(b))) - statistics.median(rng.choices(a, k=len(a)))
                  for _ in range(reamostras))
    return difs[int(0.025 * reamostras)], difs[int(0.975 * reamostras) - 1]


def analisar(id_):
    e = estudio.ler("experimentos", id_)
    a, b = _valores(e, "A"), _valores(e, "B")
    r = {"experimento": id_, "metrica": e["metrica"], "n": {"A": len(a), "B": len(b)},
         "mediana": {"A": statistics.median(a) if a else None, "B": statistics.median(b) if b else None}}
    if min(len(a), len(b)) < e["amostra_minima"]:
        r.update(veredito="inconclusivo", motivo=f"amostra pequena: precisa de {e['amostra_minima']} vídeos com dado em cada variante")
        return r
    lo, hi = _ic_diferenca_medianas(a, b)
    r["ic95_diferenca_B_menos_A"] = (round(lo, 3), round(hi, 3))
    if lo <= 0 <= hi:
        r.update(veredito="inconclusivo", motivo="o intervalo da diferença inclui zero")
    else:
        r.update(veredito="B acima de A" if lo > 0 else "B abaixo de A",
                 motivo="associação observada; vídeos diferem em tema, data e público-semente — não prova causa")
    r["proximo_passo"] = "transforme o resultado em nova hipótese e teste de novo (não copie o vídeo vencedor)"
    return r


def listar(canal=None):
    return [e for e in estudio.listar("experimentos") if not canal or e.get("canal") == canal]
