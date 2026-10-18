"""Rotas do kit do canal, logos e biblioteca de estilos."""
import os

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...core import kits, layouts, midia, projeto, referencias, zoom
from ..comum import _carregar, _estado, _f, _nome_livre, _validar_legenda
from .zoom import layouts_sem_zoom

router = APIRouter()


# ------------------------------------------------------------------ kit do canal
@router.get("/api/kits")
def kits_listar():
    return {"kits": kits.listar(), "logos": kits.logos()}


class NovoKit(BaseModel):
    nome: str
    projeto: str | None = None     # sem projeto = kit em branco (biblioteca de estilos)


def _nome_kit(nome):
    nome = str(nome or "").strip()
    if not 1 <= len(nome) <= 60:
        raise HTTPException(400, "nome do kit inválido (1 a 60 caracteres)")
    return nome


def _carregar_kit(kid):
    try:
        return kits.carregar(kid)
    except (OSError, ValueError):
        raise HTTPException(404, "kit do canal não existe")


CAMPOS_KIT = ("nome", "layout", "legenda", "marca", "gancho_ate", "zoom_padrao", "referencia")


def _validar_kit(k, dados):
    """Edicao de um kit sem projeto: mesmas regras do PUT do projeto. Devolve so os campos mudados, validados."""
    desconhecidos = set(dados) - set(CAMPOS_KIT)
    if desconhecidos:
        raise HTTPException(400, f"campo desconhecido no kit: {', '.join(sorted(desconhecidos))}")
    out = {}
    if "nome" in dados:
        out["nome"] = _nome_kit(dados["nome"])
    if "layout" in dados:
        if dados["layout"] not in layouts.LAYOUTS or dados["layout"] == "horizontal":
            raise HTTPException(400, "layout invalido (o vídeo longo é sempre horizontal)")
        out["layout"] = dados["layout"]
    if "legenda" in dados:
        out["legenda"] = _validar_legenda({**projeto.PADRAO["legenda"], **(k.get("legenda") or {}), **(dados["legenda"] or {})})
    if "marca" in dados:
        try:
            out["marca"] = kits.validar_marca({**(k.get("marca") or {}), **(dados["marca"] or {})})
        except ValueError as e:
            raise HTTPException(400, str(e))
    if "gancho_ate" in dados:
        out["gancho_ate"] = _f(dados["gancho_ate"], "gancho_ate", 0, 3600)
    if "zoom_padrao" in dados:
        try:
            out["zoom_padrao"] = zoom.validar(dados["zoom_padrao"])
        except ValueError as e:
            raise HTTPException(400, str(e))
    if "referencia" in dados:
        r = dados["referencia"]
        if r and not os.path.isfile(referencias.caminho(r)):
            raise HTTPException(400, "perfil de referência não existe")
        out["referencia"] = r or None
    return out


@router.post("/api/kits")
def kits_salvar(dados: NovoKit):
    nome = _nome_kit(dados.nome)
    if dados.projeto is None:
        return kits.novo(nome)
    return kits.salvar_de_projeto(nome, _carregar(dados.projeto))


@router.get("/api/kits/{kid}")
def kits_obter(kid: str):
    return _carregar_kit(kid)


@router.put("/api/kits/{kid}")
def kits_editar(kid: str, dados: dict):
    """Abrir, mudar (nome/legenda/layout/logo/gancho/zoom padrao) e salvar um kit, sem projeto aberto."""
    k = _carregar_kit(kid)
    try:
        return kits.atualizar(k["id"], _validar_kit(k, dados))
    except FileExistsError as e:
        raise HTTPException(409, str(e))


class CopiaKit(BaseModel):
    nome: str | None = None


@router.post("/api/kits/{kid}/duplicar")
def kits_duplicar(kid: str, dados: CopiaKit):
    k = _carregar_kit(kid)
    return kits.duplicar(k["id"], _nome_kit(dados.nome) if dados.nome else None)


class UsarKit(BaseModel):
    kit: str


@router.post("/api/projetos/{nome}/kit")
def kits_aplicar(nome: str, dados: UsarKit):
    p = _carregar(nome)
    try:
        k = kits.carregar(dados.kit)
    except (OSError, ValueError):
        raise HTTPException(404, "kit do canal não existe")
    kits.aplicar(p, k)
    aviso = None
    try:
        p["marca"] = kits.validar_marca(p["marca"])
    except ValueError as e:                    # logo do kit apagado: aplica o resto sem logo
        p["marca"]["arquivo"], aviso = None, str(e)
    projeto.salvar(p)
    return {**_estado(p), "aviso": aviso}


@router.post("/api/projetos/{nome}/kit/zoom")
def kits_aplicar_zoom(nome: str, dados: UsarKit):
    """Zoom padrao do kit so nos trechos sem zoom (os que ja tem zoom ficam). A interface guarda o estado de antes
    (Desfazer / Ctrl+Z)."""
    p = _carregar(nome)
    k = _carregar_kit(dados.kit)
    if not k.get("zoom_padrao"):
        raise HTTPException(400, "este kit não tem zoom padrão (escolha um na Biblioteca de estilos)")
    if layouts_sem_zoom(p):
        raise HTTPException(400, "o layout atual (comparação / tela dividida) não usa zoom")
    try:
        mudou = kits.aplicar_zoom(p, k)
    except ValueError as e:
        raise HTTPException(400, f"zoom do kit inválido: {e}")
    if mudou:
        projeto.salvar(p)
    return {**_estado(p), "aplicados": [i + 1 for i in mudou]}


@router.delete("/api/kits/{kid}")
def kits_remover(kid: str):
    try:
        kits.remover(kid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return kits_listar()


@router.post("/api/kits/logos")
async def kits_logo_upload(arquivo: UploadFile = File(...)):
    base = os.path.basename((arquivo.filename or "").replace("\\", "/"))
    try:
        kits.caminho_logo(base)
    except ValueError as e:
        raise HTTPException(400, str(e))
    os.makedirs(kits.PASTA_LOGOS, exist_ok=True)
    destino = os.path.join(kits.PASTA_LOGOS, _nome_livre(kits.PASTA_LOGOS, base))
    dados = await arquivo.read((10 << 20) + 1)
    if len(dados) > (10 << 20):
        raise HTTPException(400, "logo grande demais (máx. 10 MB)")
    with open(destino, "wb") as f:
        f.write(dados)
    try:
        inf = midia.info(destino)              # confere que e mesmo uma imagem
        if inf["w"] < 16 or inf["h"] < 16:
            raise RuntimeError("imagem pequena demais")
    except RuntimeError:
        os.remove(destino)
        raise HTTPException(400, "o arquivo não é uma imagem válida")
    return {"logo": os.path.basename(destino), **kits_listar()}


@router.get("/api/kits/logos/{nome}")
def kits_logo(nome: str):
    try:
        c = kits.caminho_logo(nome)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not os.path.isfile(c):
        raise HTTPException(404, "logo não encontrado")
    return FileResponse(c)
