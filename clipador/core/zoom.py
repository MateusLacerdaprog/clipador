"""Zoom por trecho: previsivel, suave e com funcao narrativa (destacar um momento, nao enfeitar tudo).

Modelo (seg["zoom_fx"]): intensidade (1.05-2.0), inicio e duracao (s, dentro do trecho; duracao 0 = ate o fim),
curva (suave | rapida | linear), volta (sai do zoom depois de `segura` s) e o PONTO de destaque (foco_x, foco_y,
0-1 no quadro final). O zoom acontece em volta desse ponto, que fica parado na tela: a janela nunca sai do quadro
(sem bordas pretas) e nao ha deslocamentos estranhos.

Render: filtro `perspective` com cantos fracionarios (subpixel) avaliados por quadro. Medido num ponto de teste:
tremor medio 0,25 px/quadro (o metodo antigo, scale+crop com tamanhos pares, tremia 1,1 px) e erro < 1,1 px em
relacao a trajetoria ideal.

Presets: 4 embutidos (PRESETS, fixos) + os do usuario em kits/zoom/presets.json (biblioteca de estilos). O trecho
guarda os VALORES do preset, entao excluir um preset do usuario nao muda nenhum video (vira "personalizado").
"""
import copy
import json
import os

CURVAS = ("suave", "rapida", "linear")
PRESETS = {
    "destaque": {"nome": "Destaque suave", "intensidade": 1.25, "inicio": 0.0, "duracao": 0.7, "curva": "suave",
                 "volta": False, "segura": 0.0, "dica": "aproxima devagar e fica: para mostrar um detalhe"},
    "impacto": {"nome": "Impacto (soco)", "intensidade": 1.45, "inicio": 0.0, "duracao": 0.15, "curva": "rapida",
                "volta": False, "segura": 0.0, "dica": "aproxima de uma vez: tiro, batida, susto"},
    "reacao": {"nome": "Reação (entra e sai)", "intensidade": 1.3, "inicio": 0.0, "duracao": 0.35, "curva": "suave",
               "volta": True, "segura": 0.8, "dica": "aproxima, segura e volta: risada, fala marcante"},
    "lento": {"nome": "Lento cinematográfico", "intensidade": 1.12, "inicio": 0.0, "duracao": 0.0, "curva": "linear",
              "volta": False, "segura": 0.0, "dica": "aproxima bem devagar o trecho todo: cena calma, paisagem"},
}
CAMPOS = ("preset", "intensidade", "inicio", "duracao", "curva", "volta", "segura", "foco_x", "foco_y")
VALORES = ("intensidade", "inicio", "duracao", "curva", "volta", "segura")
RESERVADOS = ("nenhum", "personalizado")


# ------------------------------------------------------------------ presets do usuario (biblioteca de estilos)
def caminho_usuario():
    """kits/zoom/presets.json, ao lado de projetos/ (compartilhado entre projetos, como os kits). Fica numa
    subpasta para nunca ser confundido com um kit (kits/<id>.json)."""
    from . import projeto
    return os.path.join(os.path.dirname(projeto.RAIZ), "kits", "zoom", "presets.json")


def do_usuario():
    try:
        with open(caminho_usuario(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def todos():
    """Embutidos + do usuario (os do usuario marcados com usuario=True)."""
    return {**PRESETS, **{k: {**v, "usuario": True} for k, v in do_usuario().items() if k not in PRESETS}}


def _gravar_usuario(d):
    c = caminho_usuario()
    os.makedirs(os.path.dirname(c), exist_ok=True)
    with open(c + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(c + ".tmp", c)


def salvar_preset(nome, valores, dica=""):
    """Cria/atualiza um preset do usuario. Os 4 embutidos nao podem ser trocados."""
    from . import projeto
    nome = str(nome or "").strip()[:40]
    if not nome:
        raise ValueError("dê um nome ao preset de zoom")
    pid = projeto.slug(nome)
    if pid in PRESETS or pid in RESERVADOS or pid == "projeto":
        raise ValueError("esse nome é de um preset embutido: escolha outro")
    fx = validar({**{k: valores.get(k) for k in VALORES if k in valores}, "preset": "personalizado"})
    d = do_usuario()
    if pid not in d and len(d) >= 50:
        raise ValueError("limite de 50 presets de zoom")
    d[pid] = {"nome": nome, **{k: fx[k] for k in VALORES}, "dica": str(dica or "").strip()[:120]}
    _gravar_usuario(d)
    return pid


def remover_preset(pid):
    d = do_usuario()
    if pid not in d:
        raise FileNotFoundError("preset de zoom não existe (os embutidos não podem ser excluídos)")
    del d[pid]
    _gravar_usuario(d)


def _num(v, nome, lo, hi):
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"zoom: valor inválido em '{nome}'")
    if not lo <= v <= hi:
        raise ValueError(f"zoom: '{nome}' precisa ficar entre {lo} e {hi}")
    return round(v, 3)


def validar(fx):
    """Normaliza e valida o efeito vindo da interface/IA. None ou preset 'nenhum' = sem zoom."""
    if not fx or fx.get("preset") == "nenhum":
        return None
    preset = fx.get("preset") or "personalizado"
    catalogo = todos()
    if preset not in catalogo and preset != "personalizado":
        # preset do usuario que foi excluido: os valores guardados no trecho/kit continuam valendo
        if not all(k in fx for k in ("intensidade", "duracao", "curva")):
            raise ValueError("zoom: preset desconhecido")
        preset = "personalizado"
    base = catalogo.get(preset, PRESETS["destaque"])
    v = {k: fx.get(k, base.get(k)) for k in VALORES}
    if v["curva"] not in CURVAS:
        raise ValueError("zoom: curva inválida (suave, rapida ou linear)")
    return {"preset": preset, "intensidade": _num(v["intensidade"], "intensidade", 1.05, 2.0),
            "inicio": _num(v["inicio"], "inicio", 0, 3600), "duracao": _num(v["duracao"], "duracao", 0, 3600),
            "curva": v["curva"], "volta": bool(v["volta"]), "segura": _num(v["segura"] or 0, "segura", 0, 3600),
            "foco_x": _num(fx.get("foco_x", 0.5), "foco_x", 0, 1), "foco_y": _num(fx.get("foco_y", 0.5), "foco_y", 0, 1)}


def efeito(seg, dur):
    """Efeito pronto para o render (tempos dentro de `dur`), ou None. Projetos antigos (`zoom` numerico > 1)
    viram o preset 'lento' do trecho inteiro, em direcao ao centro (o mesmo resultado de antes, sem tremer)."""
    fx = seg.get("zoom_fx")
    if not fx:
        z = float(seg.get("zoom", 1.0) or 1.0)
        if z <= 1.001:
            return None
        fx = {**PRESETS["lento"], "preset": "lento", "intensidade": min(z, 2.0), "foco_x": 0.5, "foco_y": 0.5}
    fx = copy.deepcopy(fx)
    fx["inicio"] = min(max(float(fx["inicio"]), 0.0), max(dur - 0.05, 0.0))
    resto = max(dur - fx["inicio"], 0.05)
    d = float(fx["duracao"]) or resto
    if fx.get("volta"):
        d = min(d, resto / 2)
        fx["segura"] = min(float(fx.get("segura") or 0), max(resto - 2 * d, 0))
    fx["duracao"] = max(min(d, resto), 0.04)
    return fx


def _curva(u, curva):
    """Expressao FFmpeg da curva aplicada a u (0-1)."""
    if curva == "suave":
        return f"({u}*{u}*(3-2*{u}))"                 # smoothstep: comeca e termina devagar
    if curva == "rapida":
        return f"(1-pow(1-{u},3))"                    # sai rapido e assenta (ease-out)
    return u


def expr_z(fx, t="(in/30)"):
    """Fator de zoom em funcao do tempo `t` (s, dentro do trecho), como expressao do FFmpeg."""
    a, d, ganho = fx["inicio"], fx["duracao"], fx["intensidade"] - 1
    entra = _curva(f"clip(({t}-{a:.4f})/{d:.4f},0,1)", fx["curva"])
    if not fx.get("volta"):
        return f"(1+{ganho:.4f}*{entra})"
    b = a + d + float(fx.get("segura") or 0)
    sai = _curva(f"clip(({t}-{b:.4f})/{d:.4f},0,1)", fx["curva"])
    return f"(1+{ganho:.4f}*({entra}-{sai}))"


def z_em(fx, t):
    """Mesmo calculo em Python (testes e graficos)."""
    def c(u):
        u = min(max(u, 0.0), 1.0)
        return u * u * (3 - 2 * u) if fx["curva"] == "suave" else 1 - (1 - u) ** 3 if fx["curva"] == "rapida" else u
    a, d = fx["inicio"], fx["duracao"]
    z = c((t - a) / d)
    if fx.get("volta"):
        z -= c((t - (a + d + float(fx.get("segura") or 0))) / d)
    return 1 + (fx["intensidade"] - 1) * z


def filtro(fx):
    """Cadeia do FFmpeg (entrada ja no tamanho final, 30 fps, relogio zerado no inicio do trecho).
    Janela de zoom = W/z x H/z com o ponto (fx, fy) parado: x0 = fx*W*(1-1/z)."""
    z = expr_z(fx)
    fxv, fyv = fx["foco_x"], fx["foco_y"]
    x0, y0 = f"({fxv:.4f}*W*(1-1/{z}))", f"({fyv:.4f}*H*(1-1/{z}))"
    x1, y1 = f"({x0}+W/{z})", f"({y0}+H/{z})"
    return (f"format=yuv444p,perspective=x0='{x0}':y0='{y0}':x1='{x1}':y1='{y0}':x2='{x0}':y2='{y1}':"
            f"x3='{x1}':y3='{y1}':interpolation=cubic:sense=source:eval=frame")
