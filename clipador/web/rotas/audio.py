"""Rotas de audio: narracao, bibliotecas de musica/efeitos, previa da mixagem."""
import os
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...core import midia, projeto, recursos, render, tarefas
from ..comum import _carregar, _estado, _nome_livre
from .fontes import Url

router = APIRouter()


# -------------------------------------------------------------------- narracao
@router.post("/api/projetos/{nome}/narracao")
async def narracao(nome: str, arquivo: UploadFile = File(...)):
    p = _carregar(nome)
    d = projeto.pasta(nome)
    ext = os.path.splitext(arquivo.filename or "")[1].lower()
    if ext not in projeto.AUDIO_EXT + (".mkv", ".mov"):
        ext = ".webm"
    bruto = os.path.join(d, f"narracao_bruta{ext}")
    with open(bruto, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)
    try:
        midia.para_wav(bruto, os.path.join(d, "narracao.wav"))
        analise = midia.analisar_audio(os.path.join(d, "narracao.wav"))
    except RuntimeError as e:
        raise HTTPException(400, f"nao consegui ler esse audio: {e}")
    p["narracao"] = "narracao.wav"
    projeto.salvar(p)
    return {**_estado(p), "analise": analise}


@router.get("/api/projetos/{nome}/narracao/analise")
def narracao_analise(nome: str):
    p = _carregar(nome)
    if not p.get("narracao"):
        raise HTTPException(404, "o projeto nao tem narracao")
    return midia.analisar_audio(os.path.join(projeto.pasta(nome), p["narracao"]))


@router.delete("/api/projetos/{nome}/narracao")
def narracao_remover(nome: str):
    p = _carregar(nome)
    p["narracao"] = None   # o arquivo fica na pasta do projeto (nada e apagado sem pedir)
    projeto.salvar(p)
    return _estado(p)


# ------------------------------------------------------------------ biblioteca
def _tipo(tipo):
    if tipo not in projeto.BIBLIOTECAS:
        raise HTTPException(404, "biblioteca desconhecida")
    os.makedirs(projeto.BIBLIOTECAS[tipo], exist_ok=True)
    return projeto.BIBLIOTECAS[tipo]


def _arq_biblio(tipo, nome):
    try:
        c = projeto.caminho_biblioteca(tipo, nome)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not os.path.isfile(c):
        raise HTTPException(404, "arquivo nao encontrado na biblioteca")
    return c


def _info_biblio(tipo, nome, direitos=None):
    c = projeto.caminho_biblioteca(tipo, nome)
    d = (direitos if direitos is not None else recursos.biblioteca_ler(projeto.BIBLIOTECAS[tipo])).get(nome)
    return {"nome": nome, "dur": round(midia.duracao(c), 2), "mb": round(os.path.getsize(c) / 1e6, 2),
            "direitos": recursos.completar(d)}


@router.get("/api/biblioteca/{tipo}")
def biblioteca_listar(tipo: str):
    pasta = _tipo(tipo)
    direitos = recursos.biblioteca_ler(pasta)
    return [_info_biblio(tipo, f, direitos) for f in sorted(os.listdir(pasta)) if f.lower().endswith(projeto.AUDIO_EXT)]


@router.put("/api/biblioteca/{tipo}/{nome}/direitos")
def biblioteca_direitos(tipo: str, nome: str, dados: dict):
    """Origem e licenca de uma musica/efeito da biblioteca (ex.: YouTube Audio Library, CC0, comprada)."""
    pasta = _tipo(tipo)
    _arq_biblio(tipo, nome)
    try:
        return {"nome": nome, "direitos": recursos.biblioteca_gravar(pasta, nome, dados)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/api/biblioteca/{tipo}/{nome}/arquivo")
def biblioteca_arquivo(tipo: str, nome: str):
    _tipo(tipo)
    return FileResponse(_arq_biblio(tipo, nome))


@router.get("/api/biblioteca/{tipo}/{nome}/analise")
def biblioteca_analise(tipo: str, nome: str):
    _tipo(tipo)
    try:
        return midia.analisar_audio(_arq_biblio(tipo, nome))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.post("/api/biblioteca/{tipo}/upload")
async def biblioteca_upload(tipo: str, arquivo: UploadFile = File(...)):
    pasta = _tipo(tipo)
    base = os.path.basename((arquivo.filename or "").replace("\\", "/"))
    if not base.lower().endswith(projeto.AUDIO_EXT):
        raise HTTPException(400, "formato de audio nao suportado")
    nome = _nome_livre(pasta, base)
    destino = os.path.join(pasta, nome)
    with open(destino, "wb") as f:
        shutil.copyfileobj(arquivo.file, f, 4 << 20)
    if midia.duracao(destino) <= 0:
        os.remove(destino)
        raise HTTPException(400, "o arquivo nao parece ser um audio valido")
    return _info_biblio(tipo, nome)


def _baixar_audio(tipo, url, progresso):
    import yt_dlp

    pasta = _tipo(tipo)

    def gancho(d):
        if d.get("status") == "downloading" and d.get("total_bytes"):
            progresso(d["downloaded_bytes"] / d["total_bytes"], "baixando audio")

    opts = {"format": "bestaudio/best", "outtmpl": os.path.join(pasta, "%(title).70B.%(ext)s"),
            "quiet": True, "no_warnings": True, "noplaylist": True, "progress_hooks": [gancho],
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
        nome = os.path.splitext(os.path.basename(y.prepare_filename(info)))[0] + ".mp3"
    return _info_biblio(tipo, nome)


@router.post("/api/biblioteca/{tipo}/url")
def biblioteca_url(tipo: str, dados: Url):
    _tipo(tipo)
    if not dados.url.startswith(("http://", "https://")):
        raise HTTPException(400, "link invalido")
    return tarefas.iniciar("biblioteca", _baixar_audio, tipo, dados.url.strip())


@router.delete("/api/biblioteca/{tipo}/{nome}")
def biblioteca_remover(tipo: str, nome: str):
    _tipo(tipo)
    c = _arq_biblio(tipo, nome)
    base = os.path.basename(c)
    for pn in projeto.listar():
        if (tipo, base) in projeto.arquivos_de_audio(projeto.carregar(pn)):
            raise HTTPException(400, f"o arquivo esta em uso no projeto '{pn}'")
    os.remove(c)  # so apaga o que o usuario mandou para a biblioteca, nunca videos/projetos
    return {"ok": True}


# ------------------------------------------------------------------- previa
class Previa(BaseModel):
    solo: str | None = None


@router.post("/api/projetos/{nome}/audio/previa")
def audio_previa(nome: str, dados: Previa | None = None):
    _carregar(nome)
    solo = dados.solo if dados else None
    if solo and solo not in render.TRILHAS:
        raise HTTPException(400, "trilha invalida")

    def job(progresso):
        render.render(projeto.carregar(nome), "audio", progresso, solo=solo)
        return {"arquivo": "previa_audio.m4a", "solo": solo}

    return tarefas.iniciar("audio", job)
