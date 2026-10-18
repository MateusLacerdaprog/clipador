"""Rotas do React (camera do criador sobre o jogo)."""
import os
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile

from ...core import projeto, react, tarefas
from ..comum import _carregar, _estado

router = APIRouter()


# -------------------------------------------------------------------- react
@router.post("/api/projetos/{nome}/react/gravacao")
async def react_gravacao(nome: str, arquivo: UploadFile = File(...), usar_audio: bool = True):
    """Recebe a gravacao da camera (webm do navegador ou um video enviado). O microfone vira a narracao."""
    p = _carregar(nome)
    d = react.pasta(p)
    os.makedirs(d, exist_ok=True)
    ext = os.path.splitext(arquivo.filename or "")[1].lower()
    if ext not in (".webm", ".mp4", ".mov", ".mkv", ".m4v", ".avi"):
        ext = ".webm"
    bruto = os.path.join(d, f"gravacao_bruta{ext}")
    with open(bruto, "wb") as f:
        shutil.copyfileobj(arquivo.file, f, 4 << 20)
    try:
        analise = react.importar_camera(p, bruto, usar_audio)
    except ValueError as e:
        raise HTTPException(400, str(e))
    projeto.salvar(p)
    return {**_estado(p), "analise": analise}


@router.delete("/api/projetos/{nome}/react")
def react_remover(nome: str):
    p = _carregar(nome)
    react.remover_camera(p)
    projeto.salvar(p)
    return _estado(p)


@router.post("/api/projetos/{nome}/react/recorte")
def react_recorte(nome: str):
    p = _carregar(nome)
    if not react.caminho_camera(p) or not os.path.isfile(react.caminho_camera(p)):
        raise HTTPException(400, "grave ou envie a câmera primeiro")
    if not react.ia_disponivel()["ok"]:
        raise HTTPException(400, react.ia_disponivel()["motivo"])

    def job(progresso):
        r = react.gerar_matte(projeto.carregar(nome), progresso, getattr(progresso, "cancelar", None))
        projeto.alterar(nome, lambda q: q["react"]["recorte_ia"].update(ativo=True, pronto=True, gerado_com=r["params"]))
        return r

    return tarefas.iniciar("recorte", job)
