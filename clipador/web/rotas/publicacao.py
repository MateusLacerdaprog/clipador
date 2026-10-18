"""Rotas do pacote de publicacao: verificar por rede, adaptar o texto do YouTube, capa e PUBLICACAO.md.
Os campos em si sao salvos pelo PUT do projeto (chave "publicacao", validada em core/publicacao.validar)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import projeto, publicacao
from ..comum import _carregar, _estado

router = APIRouter()


@router.get("/api/projetos/{nome}/publicacao/verificar")
def publicacao_verificar(nome: str):
    p = _carregar(nome)
    return {"itens": publicacao.verificar(p), "mencoes": publicacao.mencoes(p), "limites": publicacao.LIMITES,
            "categorias": publicacao.CATEGORIAS}


@router.get("/api/projetos/{nome}/publicacao/adaptar")
def publicacao_adaptar(nome: str):
    """Sugestao de legenda para TikTok/Instagram a partir do YouTube. Nao grava: a interface preenche e o usuario salva."""
    return publicacao.adaptar(_carregar(nome))


@router.post("/api/projetos/{nome}/publicacao/exportar")
def publicacao_exportar(nome: str):
    p = _carregar(nome)
    return {"arquivo": publicacao.exportar(p), "texto": publicacao.markdown(p)}


class Capa(BaseModel):
    tempo: float


@router.post("/api/projetos/{nome}/publicacao/capa")
def publicacao_capa(nome: str, dados: Capa):
    p = _carregar(nome)
    try:
        pub = publicacao.gerar_capa(p, dados.tempo)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    return _estado(projeto.alterar(nome, lambda q: q.update(publicacao={**q["publicacao"], "capa": pub["capa"]})))
