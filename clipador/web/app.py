"""Servidor local do Clipador (FastAPI). Abra http://127.0.0.1:8765 no navegador.

Seguranca: so atende 127.0.0.1/localhost (bloqueia DNS rebinding) e recusa comandos vindos de
outros sites (CSRF). Toda entrada que vira parametro do FFmpeg e validada aqui e em core/audio.py.

As rotas ficam em web/rotas/<area>.py (APIRouter) e as utilidades comuns em web/comum.py.
"""
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .comum import ESTATICO, HOSTS_LOCAIS
from .rotas import (audio, comandos, estudio, fontes, ia, kits, legendas, projetos, publicacao, react, referencias,
                    revisao, timeline, zoom)

app = FastAPI(title="Clipador")
app.mount("/static", StaticFiles(directory=ESTATICO), name="static")


# ------------------------------------------------------------------- seguranca
@app.middleware("http")
async def protecao_local(request: Request, call_next):
    host = (urlparse(f"http://{request.headers.get('host', '')}").hostname or "").lower()
    if host not in HOSTS_LOCAIS:
        return JSONResponse({"detail": "acesso permitido apenas pelo proprio computador"}, status_code=403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origem = request.headers.get("origin")
        if origem and (urlparse(origem).hostname or "").lower() not in HOSTS_LOCAIS:
            return JSONResponse({"detail": "comando recusado: veio de outro site"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "comando recusado: veio de outro site"}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def sempre_revalidar(request: Request, call_next):
    """HTML, JS e CSS sao revalidados a cada carga (ETag: se nao mudou, nao baixa de novo). Sem isso o navegador
    reaproveitava um app.js velho com um index.html novo e a tela quebrava ate um Ctrl+F5."""
    resp = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


# --------------------------------------------------------------------- paginas
@app.get("/")
def inicio():
    return FileResponse(os.path.join(ESTATICO, "index.html"), headers={"Cache-Control": "no-store"})


# ordem importa: o FastAPI casa a primeira rota que servir (a das areas antigas e a do app.py monolitico original)
for _m in (projetos, fontes, zoom, kits, revisao, react, timeline, audio, legendas, ia, referencias, comandos, publicacao, estudio):
    app.include_router(_m.router)
