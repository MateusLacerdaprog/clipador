"""Rotas de zoom por trecho: presets, previa exata do trecho, zoom nos picos."""
import copy
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import destaques, projeto, render, tarefas, zoom
from ..comum import _carregar, _estado, _fonte_ou_404, _sinais

router = APIRouter()


# ------------------------------------------------------------------ zoom
@router.get("/api/zoom/presets")
def zoom_presets():
    return {"presets": zoom.todos(), "curvas": zoom.CURVAS, "embutidos": list(zoom.PRESETS)}


@router.post("/api/zoom/presets")
def zoom_preset_salvar(dados: dict):
    """Preset de zoom do usuario (biblioteca de estilos). Valores validados por zoom.validar."""
    desconhecidos = set(dados) - {"nome", "dica", *zoom.VALORES}
    if desconhecidos:
        raise HTTPException(400, f"campo desconhecido no preset de zoom: {', '.join(sorted(desconhecidos))}")
    try:
        pid = zoom.salvar_preset(dados.get("nome"), dados, dados.get("dica", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": pid, **zoom_presets()}


@router.delete("/api/zoom/presets/{pid}")
def zoom_preset_remover(pid: str):
    try:
        zoom.remover_preset(pid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return zoom_presets()


class PrevTrecho(BaseModel):
    i: int


@router.post("/api/projetos/{nome}/previa_trecho")
def previa_trecho(nome: str, dados: PrevTrecho):
    """Renderiza SO um trecho em baixa resolucao (layout + zoom exatos do video final) para conferir na hora."""
    p = _carregar(nome)
    if not 0 <= dados.i < len(p["segmentos"]):
        raise HTTPException(400, "trecho inexistente")

    def job(progresso):
        q = copy.deepcopy(projeto.carregar(nome))
        q["segmentos"] = [q["segmentos"][dados.i]]
        saida = os.path.join(projeto.pasta(nome), "cache", "previa_trecho.mp4")
        os.makedirs(os.path.dirname(saida), exist_ok=True)
        cmd, total, saida = render.montar_comando(q, "proxy", saida=saida)
        render.executar(cmd, total, projeto.pasta(nome), progresso, getattr(progresso, "cancelar", None))
        return {"arquivo": "cache/previa_trecho.mp4", "v": int(os.path.getmtime(saida))}

    return tarefas.iniciar("previa", job, pesada=False)


@router.post("/api/projetos/{nome}/zoom/sugerir")
def zoom_sugerir(nome: str):
    """Zoom com funcao narrativa: so nos trechos que tem um pico forte de acao (audio + impactos + movimento),
    no instante do pico. Trechos que ja tem zoom ou sem pico claro ficam como estao."""
    import numpy as np
    p = _carregar(nome)
    segs, sugeridos, cache = copy.deepcopy(p["segmentos"]), [], {}
    for i, s in enumerate(segs):
        if s.get("zoom_fx") or layouts_sem_zoom(p):
            continue
        f = _fonte_ou_404(p, s["fonte"])
        if f["id"] not in cache:
            cache[f["id"]] = _sinais(nome, f)
        sn = cache[f["id"]]
        a, b = int(s["ini"] / destaques.PASSO), max(int(s["fim"] / destaques.PASSO), int(s["ini"] / destaques.PASSO) + 1)
        z = destaques._z(sn["volume"]) + destaques._z(sn["movimento"]) + destaques._z(sn["impactos"])
        if b <= a or a >= len(z):
            continue
        k = a + int(np.argmax(z[a:b]))
        if z[k] < 2.5:                                   # sem pico claro: nao enfeita
            continue
        t = max(0.0, k * destaques.PASSO - s["ini"] - 0.1)
        s["zoom_fx"] = zoom.validar({"preset": "impacto", "inicio": min(t, max(s["fim"] - s["ini"] - 0.3, 0)),
                                     "foco_x": 0.5, "foco_y": 0.45})
        sugeridos.append({"trecho": i + 1, "em_s": round(t, 2), "forca": round(float(z[k]), 1)})
    if sugeridos:
        p["segmentos"] = segs
        projeto.salvar(p)
    return {**_estado(p), "sugeridos": sugeridos}


def layouts_sem_zoom(p):
    return render.layout_efetivo(p) in ("comparacao", "dividido")
