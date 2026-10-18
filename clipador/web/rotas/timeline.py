"""Rota de edicao da timeline (dividir, duplicar, mover, aparar, remover, cortar intervalo, congelar, fechar o loop)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import projeto
from ...core import timeline as tl
from ..comum import _carregar, _estado, _f

router = APIRouter()


# -------------------------------------------------------------------- timeline
class OpTimeline(BaseModel):
    op: str
    i: int | None = None
    para: int | None = None
    t: float | None = None
    dentro: float | None = None
    ini: float | None = None
    fim: float | None = None
    ima: float = 0.0


@router.post("/api/projetos/{nome}/timeline")
def timeline_op(nome: str, dados: OpTimeline):
    p = _carregar(nome)
    try:
        if dados.op == "dividir":
            sel = tl.dividir(p, dados.i, _f(dados.dentro, "dentro", 0))
        elif dados.op == "dividir_no_tempo":
            sel = tl.dividir_no_tempo(p, _f(dados.t, "t", 0))
        elif dados.op == "duplicar":
            sel = tl.duplicar(p, dados.i)
        elif dados.op == "mover":
            sel = tl.mover(p, dados.i, int(dados.para if dados.para is not None else dados.i))
        elif dados.op == "remover":
            sel = tl.remover(p, dados.i)
        elif dados.op == "aparar":
            sel = tl.aparar(p, dados.i, dados.ini, dados.fim, _f(dados.ima, "ima", 0, 2))
        elif dados.op == "cortar_intervalo":
            sel = tl.cortar_intervalo(p, dados.i, _f(dados.ini, "ini", 0), _f(dados.fim, "fim", 0))
        elif dados.op == "congelar":
            sel = tl.congelar(p, _f(dados.t, "t", 0), _f(dados.dentro if dados.dentro is not None else tl.CONGELADO_PADRAO,
                                                         "duracao", 0.2, 10))
        elif dados.op == "fechar_loop":
            sel = tl.fechar_loop(p, _f(dados.dentro if dados.dentro is not None else tl.LOOP_PADRAO, "duracao", 0.2, 3))
        else:
            raise HTTPException(400, "operação desconhecida")
    except (tl.ErroTimeline, TypeError, KeyError) as e:
        raise HTTPException(400, str(e) or "operação inválida")
    projeto.salvar(p)
    return {**_estado(p), "selecionado": sel}
