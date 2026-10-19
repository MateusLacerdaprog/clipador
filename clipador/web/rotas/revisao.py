"""Rotas de revisao/exportacao: previa, quadros, RASCUNHO, aprovar, FINAL, versoes 1:1 e 4:5, saidas."""
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import editonny_fala, projeto, publicacao, render, tarefas
from ..comum import _carregar, _estado

router = APIRouter()


# ------------------------------------------------------------------ versao 1:1
class Exportar1x1(BaseModel):
    arquivo: str


@router.post("/api/projetos/{nome}/exportar_1x1")
def exportar_1x1(nome: str, dados: Exportar1x1):
    p = _carregar(nome)
    if render.layout_efetivo(p) not in render.FAIXA_1X1:
        raise HTTPException(400, "este layout (comparação A×B ou React em tela dividida) não cabe em 1:1")
    return tarefas.iniciar("render", lambda progresso: {"saida": os.path.basename(
        render.exportar_1x1(p, dados.arquivo, progresso))})


@router.post("/api/projetos/{nome}/exportar_4x5")
def exportar_4x5(nome: str, dados: Exportar1x1):
    """Versao 4:5 (1080x1350) para o feed do Instagram, recortada do RASCUNHO/FINAL pronto."""
    p = _carregar(nome)
    if render.layout_efetivo(p) not in render.FAIXA_1X1:
        raise HTTPException(400, "este layout (comparação A×B ou React em tela dividida) não cabe em 4:5")
    return tarefas.iniciar("render", lambda progresso: {"saida": os.path.basename(
        render.exportar_4x5(p, dados.arquivo, progresso))})


@router.post("/api/projetos/{nome}/exportar_sem_audio")
def exportar_sem_audio(nome: str, dados: Exportar1x1):
    """Copia sem audio de um RASCUNHO/FINAL (para usar a musica da propria rede). Rapido: a imagem nao e recodificada."""
    p = _carregar(nome)
    try:
        return {"saida": os.path.basename(render.exportar_sem_audio(p, dados.arquivo)), "estado": _estado(p)}
    except render.ErroRender as e:
        raise HTTPException(400, str(e))


# --------------------------------------------------------------- render/revisao
class Quadros(BaseModel):
    tempos: list[float]


@router.post("/api/projetos/{nome}/proxy")
def proxy(nome: str):
    _carregar(nome)
    return tarefas.iniciar("proxy", lambda progresso: render.render(projeto.carregar(nome), "proxy", progresso))


@router.post("/api/projetos/{nome}/quadros")
def quadros(nome: str, dados: Quadros):
    _carregar(nome)
    if not dados.tempos or len(dados.tempos) > 24:
        raise HTTPException(400, "informe de 1 a 24 instantes")
    return tarefas.iniciar("quadros",
                           lambda progresso: render.quadros(projeto.carregar(nome), dados.tempos, progresso))


@router.post("/api/projetos/{nome}/render/{modo}")
def renderizar(nome: str, modo: str):
    if modo not in ("rascunho", "final"):
        raise HTTPException(400, "modo invalido")
    p = _carregar(nome)
    if modo == "final" and p["aprovacao"].get("aprovado_hash") != projeto.hash_conteudo(p):
        raise HTTPException(400, "aprove o rascunho atual antes de gerar o FINAL")

    if modo == "rascunho" and p.get("editor") == "editonny":     # pessoa falando: o editonny edita e legenda
        return tarefas.iniciar("rascunho", lambda progresso: editonny_fala.editar(nome, progresso))

    def job(progresso):
        saida = render.render(projeto.carregar(nome), modo, progresso)
        r = {"arquivo": os.path.basename(saida), "verificado": True}
        if modo == "final":                          # texto por rede ao lado do FINAL (falhar aqui nao perde o video)
            try:
                r["publicacao"] = publicacao.exportar(projeto.carregar(nome))
            except OSError:
                pass
        return r

    return tarefas.iniciar(modo, job)


@router.delete("/api/projetos/{nome}/saidas/{arquivo}")
def saida_excluir(nome: str, arquivo: str):
    """Apaga um RASCUNHO/FINAL (ou a versao 1:1) gerado. So arquivos de saida da pasta do projeto."""
    p = _carregar(nome)
    d = projeto.pasta(nome)
    if (os.path.basename(arquivo) != arquivo or not arquivo.startswith(("RASCUNHO_", "FINAL_"))
            or not arquivo.endswith(".mp4") or ".tmp." in arquivo):
        raise HTTPException(400, "só dá para excluir vídeos gerados (RASCUNHO_… ou FINAL_…)")
    c = os.path.join(d, arquivo)
    if not os.path.isfile(c):
        raise HTTPException(404, "esse vídeo já não existe")
    os.remove(c)
    if arquivo.startswith("RASCUNHO_") and not any(f.startswith("RASCUNHO_") and f.endswith(".mp4") for f in os.listdir(d)):
        p["aprovacao"]["rascunho_hash"] = None        # sem rascunho na pasta: gere outro antes de aprovar
        projeto.salvar(p)
    return _estado(p)


@router.delete("/api/projetos/{nome}/quadros")
def quadros_excluir(nome: str):
    _carregar(nome)
    q = os.path.join(projeto.pasta(nome), "quadros")
    n = 0
    if os.path.isdir(q):
        for f in os.listdir(q):
            if f.lower().endswith(".png"):
                os.remove(os.path.join(q, f))
                n += 1
    return {"apagados": n}
