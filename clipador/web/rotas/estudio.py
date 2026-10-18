"""Rotas do estúdio (docs/cpv): canais, banco de ideias com pontuação CPV e roteiros com aprovação."""
import os

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ...core import canais, ideias, roteiros, tarefas

router = APIRouter()


def _chamar(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/api/cpv/criterios")
def cpv_criterios():
    return {"pesos": {k: {"peso": p, "nota5": a, "nota0": b} for k, (p, a, b) in ideias.PESOS.items()},
            "portoes": ideias.PORTOES, "formatos": ideias.FORMATOS, "estruturas": roteiros.ESTRUTURAS}


# ---------------------------------------------------------------------- canais
@router.get("/api/canais")
def canais_listar():
    return canais.listar()


@router.post("/api/canais")
def canais_criar(dados: dict):
    return _chamar(canais.criar, dados)


@router.post("/api/canais/semear")
def canais_semear():
    """Cria (como rascunho) os canais da estratégia docs/cpv/05 que ainda não existem."""
    return {"criados": [c["id"] for c in canais.semear()], "canais": canais.listar()}


@router.get("/api/canais/{cid}")
def canais_obter(cid: str):
    return _chamar(canais.obter, cid)


@router.put("/api/canais/{cid}")
def canais_editar(cid: str, dados: dict):
    return _chamar(canais.editar, cid, dados)


# ---------------------------------------------------------------------- ideias
@router.get("/api/ideias")
def ideias_listar(canal: str | None = None, status: str | None = None):
    return ideias.listar(canal, status)


@router.post("/api/ideias")
def ideias_criar(dados: dict):
    return _chamar(ideias.criar, dados)


@router.get("/api/ideias/{iid}")
def ideias_obter(iid: str):
    return _chamar(ideias.obter, iid)


class Avaliacao(BaseModel):
    notas: dict | None = None
    portoes: dict | None = None


@router.post("/api/ideias/{iid}/avaliar")
def ideias_avaliar(iid: str, dados: Avaliacao):
    return _chamar(ideias.avaliar, iid, dados.notas, dados.portoes)


@router.post("/api/ideias/{iid}/fontes")
def ideias_fonte(iid: str, dados: dict):
    return _chamar(ideias.adicionar_fonte, iid, dados)


class Status(BaseModel):
    status: str
    motivo: str = ""


@router.post("/api/ideias/{iid}/status")
def ideias_status(iid: str, dados: Status):
    return _chamar(ideias.mudar_status, iid, dados.status, dados.motivo)


# --------------------------------------------------------------------- roteiros
def _com_checagem(r):
    return {**r, "texto": roteiros.texto(r), "metricas": roteiros.metricas(r), "checagem": roteiros.checar(r)}


@router.get("/api/roteiros")
def roteiros_listar(canal: str | None = None):
    return roteiros.listar(canal)


class NovoRoteiro(BaseModel):
    ideia: str


@router.post("/api/roteiros")
def roteiros_criar(dados: NovoRoteiro):
    return _com_checagem(_chamar(roteiros.criar, dados.ideia))


@router.get("/api/roteiros/{rid}")
def roteiros_obter(rid: str):
    return _com_checagem(_chamar(roteiros.obter, rid))


class EdicaoRoteiro(BaseModel):
    blocos: dict | None = None
    ganchos_alternativos: list[str] | None = None
    afirmacoes: list[dict] | None = None
    ppm: int | None = None


@router.put("/api/roteiros/{rid}")
def roteiros_editar(rid: str, dados: EdicaoRoteiro):
    return _com_checagem(_chamar(roteiros.editar, rid, dados.blocos, dados.ganchos_alternativos, dados.afirmacoes, dados.ppm))


@router.post("/api/roteiros/{rid}/aprovar")
def roteiros_aprovar(rid: str):
    """Aprovação é do usuário (botão na tela ou pedido explícito na conversa)."""
    return _com_checagem(_chamar(roteiros.aprovar, rid))


@router.post("/api/roteiros/{rid}/ia")
def roteiros_ia(rid: str):
    """Rascunho pela IA ativa (consentimento e limites do assistente). Fica em sugestao_ia; nada é aplicado."""
    _chamar(roteiros.obter, rid)
    return tarefas.iniciar("ia", lambda progresso: {"roteiro": roteiros.sugerir_com_ia(rid, progresso=progresso)["id"]}, pesada=False)


@router.post("/api/roteiros/{rid}/ia/aplicar")
def roteiros_ia_aplicar(rid: str):
    return _com_checagem(_chamar(roteiros.aplicar_sugestao, rid))


@router.get("/api/projetos/{nome}/esteira")
def esteira_estado(nome: str):
    from ...core import esteira, projeto
    p = _chamar(projeto.carregar, nome)
    return {**esteira.estado(p), "log": esteira.log(nome)[-50:]}


class Publicado(BaseModel):
    url: str


@router.post("/api/projetos/{nome}/esteira/publicado")
def esteira_publicado(nome: str, dados: Publicado):
    """O USUÁRIO publicou e informa o link; o Clipador não publica."""
    from ...core import esteira
    return _chamar(esteira.marcar_publicado, nome, dados.url)


@router.post("/api/metricas/importar")
async def metricas_importar(arquivo: UploadFile = File(...), canal: str | None = None):
    from ...core import metricas
    texto = (await arquivo.read()).decode("utf-8-sig", errors="replace")
    linhas, desconhecidas = _chamar(metricas.ler_csv, texto)
    snap = metricas.gravar_retrato(linhas, desconhecidas, os.path.basename(arquivo.filename or ""), canal)
    return {"id": snap["id"], "videos": len(linhas), "colunas_nao_reconhecidas": desconhecidas}


@router.get("/api/metricas/{video_id}")
def metricas_video(video_id: str):
    from ...core import metricas
    return [{"importado_em": q, **l} for q, l in metricas.serie(video_id)]


@router.post("/api/experimentos")
def experimentos_criar(dados: dict):
    from ...core import experimentos
    return _chamar(experimentos.criar, dados)


class Ligacao(BaseModel):
    variante: str
    video_id: str


@router.post("/api/experimentos/{eid}/ligar")
def experimentos_ligar(eid: str, dados: Ligacao):
    from ...core import experimentos
    return _chamar(experimentos.ligar, eid, dados.variante, dados.video_id)


@router.get("/api/experimentos/{eid}/analise")
def experimentos_analise(eid: str):
    from ...core import experimentos
    return _chamar(experimentos.analisar, eid)


@router.post("/api/custos")
def custos_lancar(dados: dict):
    from ...core import financeiro
    return _chamar(financeiro.lancar, dados)


@router.get("/api/projetos/{nome}/financeiro")
def financeiro_projeto(nome: str, valor_hora_usd: float | None = None):
    from ...core import financeiro
    return _chamar(financeiro.por_projeto, nome, valor_hora_usd)


class RoteiroProjeto(BaseModel):
    nome: str
    tipo: str = "curto"
    formato: str | None = None


@router.post("/api/roteiros/{rid}/projeto")
def roteiros_projeto(rid: str, dados: RoteiroProjeto):
    from ..comum import _estado
    if not dados.nome.strip() or len(dados.nome) > 80:
        raise HTTPException(400, "nome invalido")
    return _estado(_chamar(roteiros.para_projeto, rid, dados.nome, dados.tipo, dados.formato))
