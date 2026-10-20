"""Aba Aprovacao: fila de rascunhos de todos os projetos, aprovar (e gerar o FINAL) ou pedir ajuste."""
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import aprovacao, editonny_fala, projeto, publicacao, render, tarefas
from ..comum import _carregar

router = APIRouter()


@router.get("/api/aprovacao")
def fila():
    return {"itens": aprovacao.fila()}


@router.post("/api/aprovacao/{nome}/aprovar")
def aprovar(nome: str):
    """Aprova o rascunho atual (clique do usuario) e gera o FINAL em segundo plano."""
    p = _carregar(nome)
    h = projeto.hash_conteudo(p)
    if p["aprovacao"].get("rascunho_hash") != h:
        raise HTTPException(400, "este rascunho está desatualizado: gere um novo antes de aprovar")
    projeto.alterar(nome, lambda atual: atual["aprovacao"].update(aprovado_hash=h))

    def job(progresso):
        saida = render.render(projeto.carregar(nome), "final", progresso)
        r = {"arquivo": os.path.basename(saida)}
        try:
            r["publicacao"] = publicacao.exportar(projeto.carregar(nome))
        except OSError:
            pass
        return r
    return tarefas.iniciar("final", job)


class Ajuste(BaseModel):
    nota: str = ""


@router.post("/api/aprovacao/{nome}/ajuste")
def ajuste(nome: str, dados: Ajuste):
    _carregar(nome)
    return aprovacao.item(aprovacao.pedir_ajuste(nome, dados.nota)) or {"nome": nome, "nota": dados.nota}


class Editor(BaseModel):
    editor: str


@router.put("/api/projetos/{nome}/editor")
def editor(nome: str, dados: Editor):
    from ..comum import _estado
    _carregar(nome)
    try:
        return _estado(editonny_fala.definir_editor(nome, dados.editor))
    except ValueError as e:
        raise HTTPException(400, str(e))


class Motion(BaseModel):
    ativo: bool


@router.put("/api/projetos/{nome}/motion")
def motion_ativo(nome: str, dados: Motion):
    """Liga/desliga o motion automatico da skill effectcraft na edicao do editonny."""
    from ..comum import _estado
    _carregar(nome)
    return _estado(projeto.alterar(nome, lambda p: p.update(motion=dados.ativo)))
