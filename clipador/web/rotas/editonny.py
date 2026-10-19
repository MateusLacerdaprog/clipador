"""Rotas do editonny: catalogo de cenas, graficos sobre a montagem e narracao sem pausas (core/editonny.py)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import editonny, tarefas
from ..comum import _carregar, _estado

router = APIRouter()


def _ou_400(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except (ValueError, editonny.ErroEditonny) as e:
        raise HTTPException(400, str(e))
    except IndexError as e:
        raise HTTPException(404, str(e))


@router.get("/api/editonny")
def editonny_status():
    return editonny.status()


@router.get("/api/editonny/cenas")
def editonny_cenas(busca: str = ""):
    return {"cenas": _ou_400(editonny.catalogo, busca[:100])}


class Grafico(BaseModel):
    cena: str
    inicio: float
    duracao: float | None = None
    parametros: dict = {}
    textos: dict = {}
    estilo: str = "night"


@router.post("/api/projetos/{nome}/graficos")
def grafico_novo(nome: str, dados: Grafico):
    """Confere o pedido na hora (texto de exemplo, tempos) e renderiza em segundo plano (1-2 min)."""
    _carregar(nome)
    pedido = dict(cena_id=dados.cena, inicio=dados.inicio, duracao=dados.duracao, parametros=dados.parametros,
                  textos=dados.textos, estilo=dados.estilo)
    _ou_400(editonny.conferir_pedido, nome, **pedido)
    return tarefas.iniciar("grafico", lambda progresso: editonny.gerar_grafico(nome, progresso=progresso, **pedido))


class MoverGrafico(BaseModel):
    inicio: float


@router.put("/api/projetos/{nome}/graficos/{i}")
def grafico_mover(nome: str, i: int, dados: MoverGrafico):
    _carregar(nome)
    return _estado(_ou_400(editonny.mover_grafico, nome, i, dados.inicio))


@router.delete("/api/projetos/{nome}/graficos/{i}")
def grafico_remover(nome: str, i: int):
    _carregar(nome)
    return _estado(_ou_400(editonny.remover_grafico, nome, i))


class Apertar(BaseModel):
    aplicar: bool = False
    pausa_max: float = 0.15
    pausa_min: float = 0.25


@router.post("/api/projetos/{nome}/narracao/apertar")
def narracao_apertar(nome: str, dados: Apertar):
    """Plano (aplicar=false) ou aplicacao do aperto de pausas da narracao, em segundo plano."""
    p = _carregar(nome)
    if not p.get("narracao"):
        raise HTTPException(400, "o projeto ainda não tem narração")
    if not editonny.instalacao():
        raise HTTPException(400, "o editonny não está instalado")
    return tarefas.iniciar("narracao", lambda progresso: editonny.apertar_narracao(
        nome, dados.aplicar, dados.pausa_max, dados.pausa_min, progresso=progresso))


@router.post("/api/projetos/{nome}/narracao/apertar/desfazer")
def narracao_apertar_desfazer(nome: str):
    _carregar(nome)
    return _estado(_ou_400(editonny.desfazer_aperto, nome))
