"""Operacoes de edicao da timeline (nao destrutivas: so mexem na lista de trechos do projeto).

Tempos: `ini`/`fim` de um trecho sao segundos DA FONTE; `t` da timeline e o tempo no video montado.
"""
import copy

from . import projeto

MIN_TRECHO = 0.2


class ErroTimeline(ValueError):
    pass


def _idx(p, i):
    if not 0 <= i < len(p["segmentos"]):
        raise ErroTimeline("trecho inexistente")
    return i


def localizar(p, t):
    """(indice, segundos dentro do trecho) para um instante da timeline."""
    acc = 0.0
    for i, s in enumerate(p["segmentos"]):
        d = s["fim"] - s["ini"]
        if t < acc + d or i == len(p["segmentos"]) - 1:
            return i, min(max(t - acc, 0.0), d)
        acc += d
    raise ErroTimeline("timeline vazia")


def dividir(p, i, dentro):
    """Divide o trecho i a `dentro` segundos do seu inicio."""
    s = p["segmentos"][_idx(p, i)]
    corte = s["ini"] + dentro
    if corte - s["ini"] < MIN_TRECHO or s["fim"] - corte < MIN_TRECHO:
        raise ErroTimeline(f"cada parte precisa de pelo menos {MIN_TRECHO} s")
    if s.get("congelado"):                     # quadro parado: as duas partes mostram o MESMO quadro
        b = copy.deepcopy(s)
        b["id"], b["fim"] = projeto.novo_id(), round(s["ini"] + (s["fim"] - corte), 3)
        s["fim"] = round(corte, 3)
        p["segmentos"].insert(i + 1, b)
        return i + 1
    b = copy.deepcopy(s)
    b["id"], b["ini"] = projeto.novo_id(), round(corte, 3)
    b.pop("rotulo", None)                      # o rotulo (capitulo/ranking) fica com a 1a parte
    if "ini_b" in s:                           # comparacao: a fonte B anda junto
        b["ini_b"] = round(s["ini_b"] + dentro, 3)
    s["fim"] = round(corte, 3)
    p["segmentos"].insert(i + 1, b)
    return i + 1


def dividir_no_tempo(p, t):
    i, dentro = localizar(p, t)
    return dividir(p, i, dentro)


def duplicar(p, i):
    c = copy.deepcopy(p["segmentos"][_idx(p, i)])
    c["id"] = projeto.novo_id()
    p["segmentos"].insert(i + 1, c)
    return i + 1


def mover(p, de, para):
    _idx(p, de)
    para = max(0, min(para, len(p["segmentos"]) - 1))
    p["segmentos"].insert(para, p["segmentos"].pop(de))
    return para


def remover(p, i):
    p["segmentos"].pop(_idx(p, i))
    return min(i, len(p["segmentos"]) - 1)


CONGELADO_PADRAO = 1.0


def congelar(p, t, duracao=CONGELADO_PADRAO):
    """Quadro congelado no instante `t` da timeline: divide o trecho ali e insere o quadro parado por `duracao` s
    (pausa dramatica, "repara nisso", meme). O som do jogo fica mudo nele; narracao e musica seguem."""
    i, dentro = localizar(p, t)
    s = p["segmentos"][i]
    if s.get("congelado"):
        raise ErroTimeline("este trecho já é um quadro congelado")
    duracao = round(float(duracao), 3)
    if not MIN_TRECHO <= duracao <= 10:
        raise ErroTimeline("o quadro congelado precisa ter entre 0,2 e 10 s")
    quadro = round(s["ini"] + dentro, 3)
    c = {k: copy.deepcopy(v) for k, v in s.items() if k not in ("rotulo", "loop", "zoom_fx", "audio")}
    c.update(id=projeto.novo_id(), ini=quadro, fim=round(quadro + duracao, 3), congelado=True)
    if "ini_b" in s:                           # comparacao: o video B congela no mesmo instante
        c["ini_b"] = round(s["ini_b"] + dentro, 3)
    if dentro < MIN_TRECHO:                    # no comeco do trecho: entra antes dele
        p["segmentos"].insert(i, c)
        return i
    if s["fim"] - s["ini"] - dentro < MIN_TRECHO:   # no fim: entra depois
        p["segmentos"].insert(i + 1, c)
        return i + 1
    dividir(p, i, dentro)
    p["segmentos"].insert(i + 1, c)
    return i + 1


LOOP_PADRAO = 0.9


def tem_loop(p):
    """O fim ja volta ao comeco? (trecho marcado por fechar_loop ou o mesmo plano do inicio)."""
    segs = p["segmentos"]
    if len(segs) < 2:
        return False
    a, z = segs[0], segs[-1]
    return bool(z.get("loop")) or (z["fonte"] == a["fonte"] and abs(z["ini"] - a["ini"]) < 0.05)


def fechar_loop(p, duracao=LOOP_PADRAO):
    """Final que emenda no comeco: repete os primeiros `duracao` s do 1o trecho no fim, para o replay automatico
    parecer continuo (replays contam como visualizacao). Igual ao 1o trecho em tudo (zoom, foco, som)."""
    if not p["segmentos"]:
        raise ErroTimeline("monte a timeline antes de fechar o loop")
    if tem_loop(p):
        raise ErroTimeline("o final já repete o começo")
    s = p["segmentos"][0]
    d = min(float(duracao), s["fim"] - s["ini"])
    if d < MIN_TRECHO:
        raise ErroTimeline(f"o 1º trecho precisa de pelo menos {MIN_TRECHO} s")
    c = copy.deepcopy(s)
    c.update(id=projeto.novo_id(), fim=round(s["ini"] + d, 3), loop=True)
    c.pop("rotulo", None)                      # nao vira capitulo nem posicao do ranking
    p["segmentos"].append(c)
    return len(p["segmentos"]) - 1


def cortar_intervalo(p, i, ini, fim):
    """Tira [ini, fim] (segundos DA FONTE) de dentro do trecho i: editar pela transcricao (apagar palavras).
    Sobras menores que MIN_TRECHO somem junto; se nada sobrar, o trecho e removido."""
    s = p["segmentos"][_idx(p, i)]
    ini, fim = max(float(ini), s["ini"]), min(float(fim), s["fim"])
    if fim - ini < 0.05:
        raise ErroTimeline("o intervalo nao esta dentro do trecho")
    partes = []
    if ini - s["ini"] >= MIN_TRECHO:
        a = copy.deepcopy(s)
        a["fim"] = round(ini, 3)
        partes.append(a)
    if s["fim"] - fim >= MIN_TRECHO:
        b = copy.deepcopy(s)
        if partes:
            b["id"] = projeto.novo_id()
            b.pop("rotulo", None)
        if "ini_b" in s:
            b["ini_b"] = round(s["ini_b"] + (fim - s["ini"]), 3)
        b["ini"] = round(fim, 3)
        partes.append(b)
    p["segmentos"][i:i + 1] = partes
    if not p["segmentos"]:
        return -1
    return min(i, len(p["segmentos"]) - 1)


def aparar(p, i, ini=None, fim=None, ima=0.0):
    """Novo inicio/fim (segundos da fonte), limitado a fonte; com `ima` > 0 gruda no corte de cena mais proximo."""
    s = p["segmentos"][_idx(p, i)]
    f = projeto.fonte(p, s["fonte"])
    dur = f["info"]["dur"]
    cortes = [c["ini"] for c in f.get("cenas") or []] + [c["fim"] for c in f.get("cenas") or []]

    def grudar(x):
        if ima > 0 and cortes:
            perto = min(cortes, key=lambda c: abs(c - x))
            if abs(perto - x) <= ima:
                return perto
        return x

    novo_ini = s["ini"] if ini is None else min(max(grudar(float(ini)), 0.0), dur)
    novo_fim = s["fim"] if fim is None else min(max(grudar(float(fim)), 0.0), dur)
    if novo_fim - novo_ini < MIN_TRECHO:
        raise ErroTimeline(f"o trecho precisa de pelo menos {MIN_TRECHO} s")
    s["ini"], s["fim"] = round(novo_ini, 3), round(novo_fim, 3)
    return i


OPS = {"dividir": dividir, "dividir_no_tempo": dividir_no_tempo, "duplicar": duplicar, "mover": mover,
       "remover": remover, "aparar": aparar}
