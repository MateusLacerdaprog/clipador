"""Rotas dos perfis de referencia editorial."""
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import projeto, referencias, tarefas
from ..comum import _carregar, _estado

router = APIRouter()


# ------------------------------------------------------------------ referencias
@router.get("/api/referencias")
def ref_listar():
    return {"perfis": referencias.listar(), "aspectos": referencias.ASPECTOS}


@router.get("/api/referencias/{pid}")
def ref_obter(pid: str):
    try:
        return referencias.carregar(pid)
    except (OSError, ValueError):
        raise HTTPException(404, "perfil não encontrado")


class NovoPerfil(BaseModel):
    nome: str
    canais: list[str]
    aspectos: list[str] | None = None


@router.post("/api/referencias")
def ref_gerar(dados: NovoPerfil):
    canais = [c.strip() for c in dados.canais if c.strip()]
    if not dados.nome.strip() or not canais or len(canais) > 5:
        raise HTTPException(400, "informe um nome e de 1 a 5 links de canal")
    for c in canais:
        if (urlparse(c).hostname or "").lower() not in ("www.youtube.com", "youtube.com", "m.youtube.com"):
            raise HTTPException(400, "use links de canal do YouTube (youtube.com/@canal ou /channel/...)")

    def job(progresso):
        antigo = None
        try:
            antigo = referencias.carregar(dados.nome)
        except (OSError, ValueError):
            pass
        perfil = referencias.gerar(dados.nome.strip()[:60], canais, dados.aspectos, progresso,
                                   visual=(antigo or {}).get("observado", {}).get("visual"))
        referencias.salvar(perfil)
        return {"id": perfil["id"]}

    return tarefas.iniciar("referencia", job, pesada=False)


@router.delete("/api/referencias/{pid}")
def ref_apagar(pid: str):
    referencias.apagar(pid)
    return {"ok": True}


@router.get("/api/projetos/{nome}/referencia/{pid}")
def ref_comparar(nome: str, pid: str):
    p = _carregar(nome)
    try:
        return referencias.comparar(p, referencias.carregar(pid))
    except (OSError, ValueError):
        raise HTTPException(404, "perfil não encontrado")


@router.post("/api/projetos/{nome}/referencia/{pid}/aplicar")
def ref_aplicar(nome: str, pid: str):
    p = _carregar(nome)
    try:
        mudou = referencias.aplicar(p, referencias.carregar(pid))
    except (OSError, ValueError):
        raise HTTPException(404, "perfil não encontrado")
    projeto.salvar(p)
    return {**_estado(p), "mudancas": mudou}


@router.get("/api/tarefas/{tid}")
def tarefa(tid: str):
    t = tarefas.obter(tid)
    if not t:
        raise HTTPException(404, "tarefa nao existe")
    return t


@router.post("/api/tarefas/{tid}/cancelar")
def tarefa_cancelar(tid: str):
    if not tarefas.cancelar(tid):
        raise HTTPException(404, "tarefa nao existe")
    return {"ok": True}
