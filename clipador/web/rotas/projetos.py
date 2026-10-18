"""Rotas de projeto: listar, criar, abrir, editar, formatos, arquivos, excluir/lixeira."""
import os
import shutil
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...core import audio, formatos, kits, layouts, legendas, projeto, publicacao, react, referencias
from ..comum import (
    _carregar, _estado, _f, _gravar_cartoes, _ler_cartoes, _validar_comparacao, _validar_legenda, _validar_react,
    _validar_segmentos)

router = APIRouter()


# -------------------------------------------------------------------- projetos
class NovoProjeto(BaseModel):
    nome: str
    tipo: str = "curto"
    formato: str | None = None
    kit: str | None = None


@router.get("/api/projetos")
def listar():
    out = []
    for n in projeto.listar():
        try:
            p = projeto.carregar(n)
            out.append({"nome": n, "tipo": p.get("tipo", "curto"), "formato": p.get("formato")})
        except (OSError, ValueError):
            out.append({"nome": n, "tipo": "curto", "formato": None, "erro": "projeto.json ilegivel"})
    return out


@router.post("/api/projetos")
def criar(dados: NovoProjeto):
    if not dados.nome.strip() or len(dados.nome) > 80 or projeto.slug(dados.nome) == LIXEIRA:
        raise HTTPException(400, "nome invalido")
    try:
        formatos.obter(dados.tipo, dados.formato)
        kit = kits.carregar(dados.kit) if dados.kit else None
    except ValueError as e:
        raise HTTPException(400, str(e))
    except OSError:
        raise HTTPException(400, "kit do canal não existe")
    try:
        p = projeto.criar(dados.nome)
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    formatos.aplicar(p, dados.tipo, dados.formato)
    if kit:
        kits.aplicar(p, kit)
    projeto.salvar(p)
    return _estado(p)


@router.get("/api/formatos")
def formatos_catalogo():
    return formatos.catalogo()


@router.get("/api/projetos/{nome}")
def obter(nome: str):
    return _estado(_carregar(nome))


@router.get("/api/projetos/{nome}/guia")
def guia_formato(nome: str):
    p = _carregar(nome)
    return formatos.guia({**p, "duracao_atual": projeto.duracao_timeline(p)})


class Duplicar(BaseModel):
    nome: str | None = None


@router.post("/api/projetos/{nome}/duplicar")
def duplicar(nome: str, dados: Duplicar):
    """Copia para testar outra versao (ex.: outro gancho). Sem nome: <nome>-b, -c..."""
    _carregar(nome)
    if dados.nome is not None and (not dados.nome.strip() or len(dados.nome) > 80 or projeto.slug(dados.nome) == LIXEIRA):
        raise HTTPException(400, "nome invalido")
    try:
        return _estado(projeto.duplicar(nome, dados.nome))
    except FileExistsError as e:
        raise HTTPException(409, str(e))


class Formato(BaseModel):
    formato: str | None = None


@router.post("/api/projetos/{nome}/formato")
def reaplicar_formato(nome: str, dados: Formato):
    """Troca o formato do projeto (aplica o preset; trechos e narracao ficam)."""
    p = _carregar(nome)
    try:
        formatos.aplicar(p, p.get("tipo", "curto"), dados.formato)
    except ValueError as e:
        raise HTTPException(400, str(e))
    projeto.salvar(p)
    return _estado(p)


@router.get("/api/projetos/{nome}/capitulos")
def capitulos(nome: str):
    return formatos.capitulos(_carregar(nome))


@router.put("/api/projetos/{nome}")
def atualizar(nome: str, dados: dict):
    # sob a trava: uma tarefa que termina no meio (marca do render) nao e apagada por esta copia
    with projeto.trava(nome):
        return _atualizar(nome, dados)


def _atualizar(nome, dados):
    p = _carregar(nome)
    estilo_antes = p["legenda"]["estilo"]
    if "layout" in dados:
        if dados["layout"] not in layouts.LAYOUTS:
            raise HTTPException(400, "layout invalido")
        p["layout"] = dados["layout"]
    if "formato_cfg" in dados:
        cfg = dados["formato_cfg"] or {}
        p["formato_cfg"] = {**p["formato_cfg"], "ranking": bool(cfg.get("ranking", p["formato_cfg"]["ranking"])),
                            "capitulos": bool(cfg.get("capitulos", p["formato_cfg"]["capitulos"]))}
    if "legenda" in dados:
        p["legenda"] = _validar_legenda({**p["legenda"], **(dados["legenda"] or {})})
    if "gancho" in dados:
        g = dados["gancho"] or {}
        p["gancho"] = {"texto": str(g.get("texto", ""))[:80], "ate": _f(g.get("ate", 3) or 0, "ate", 0, 3600)}
    if "roteiro" in dados:
        p["roteiro"] = str(dados["roteiro"] or "")[:20000]
    if "publicacao" in dados:
        try:
            p["publicacao"] = publicacao.validar(dados["publicacao"], p["publicacao"])
        except ValueError as e:
            raise HTTPException(400, str(e))
    if "marca" in dados:
        try:
            p["marca"] = kits.validar_marca({**p["marca"], **(dados["marca"] or {})})
        except ValueError as e:
            raise HTTPException(400, str(e))
    if "react" in dados:
        p["react"] = _validar_react(p["react"], dados["react"], p.get("tipo", "curto"))
        p["react"]["recorte_ia"]["pronto"] = os.path.isfile(react.caminho_matte(p))
        if p["react"]["recorte_ia"]["ativo"] and not p["react"]["recorte_ia"]["pronto"]:
            p["react"]["recorte_ia"]["ativo"] = False
    if "referencia" in dados:
        r = dados["referencia"]
        if r and not os.path.isfile(referencias.caminho(r)):
            raise HTTPException(400, "perfil de referência não existe")
        p["referencia"] = r or None
    if "comparacao" in dados:
        p["comparacao"] = _validar_comparacao(p, dados["comparacao"])
    if "segmentos" in dados:
        p["segmentos"] = _validar_segmentos(p, dados["segmentos"] or [])
    if "audio" in dados:
        novo = audio.migrar(p["audio"])
        for k in ("original", "musica", "narracao", "mix"):
            novo[k].update((dados["audio"] or {}).get(k) or {})
        if "efeitos" in (dados["audio"] or {}):
            novo["efeitos"] = [{**audio.EFEITO_PADRAO, **e} for e in dados["audio"]["efeitos"] or []]
        try:
            novo = audio.validar(novo)
            for tipo, n in [("musicas", novo["musica"]["arquivo"])] + [("efeitos", e["arquivo"])
                                                                        for e in novo["efeitos"]]:
                if n:
                    projeto.caminho_biblioteca(tipo, n)
        except ValueError as e:
            raise HTTPException(400, str(e))
        p["audio"] = novo
    if "fontes" in dados:  # so o recorte das tarjas e editavel aqui
        crops = {f.get("id"): (f.get("crop") or None) for f in dados["fontes"] or []}
        for f in p["fontes"]:
            if f["id"] in crops:
                c = crops[f["id"]]
                if c and not projeto.CROP_RE.match(str(c)):
                    raise HTTPException(400, "recorte invalido: use largura:altura:x:y (so numeros)")
                if c:
                    w, h, x, y = (int(v) for v in c.split(":"))
                    if w < 16 or h < 16 or x + w > f["info"]["w"] or y + h > f["info"]["h"]:
                        raise HTTPException(400, "recorte maior que o video")
                f["crop"] = c
    projeto.salvar(p)
    if p["legenda"]["estilo"] != estilo_antes:  # muda o tamanho dos cartoes conforme o estilo
        cart = _ler_cartoes(nome)
        if cart:
            _gravar_cartoes(nome, legendas.reagrupar(cart, p["legenda"]["estilo"]))
    return _estado(p)


# -------------------------------------------------------------------- arquivos
@router.get("/api/projetos/{nome}/arquivo")
def arquivo(nome: str, caminho: str):
    d = os.path.realpath(projeto.pasta(nome))
    alvo = os.path.realpath(os.path.join(d, caminho))
    if not alvo.startswith(d + os.sep) or not os.path.isfile(alvo):
        raise HTTPException(404, "arquivo nao encontrado")
    return FileResponse(alvo, headers={"Cache-Control": "no-store"})


# ---- projeto inteiro: vai para projetos/_lixeira (da para restaurar; nada some de vez)
LIXEIRA = "_lixeira"


def _pasta_lixeira():
    return os.path.join(projeto.RAIZ, LIXEIRA)


@router.delete("/api/projetos/{nome}")
def projeto_excluir(nome: str):
    _carregar(nome)
    os.makedirs(_pasta_lixeira(), exist_ok=True)
    item = f"{projeto.slug(nome)}--{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.move(projeto.pasta(nome), os.path.join(_pasta_lixeira(), item))
    return {"lixeira": item}


@router.post("/api/lixeira/{item}/restaurar")
def projeto_restaurar(item: str):
    if os.path.basename(item) != item or "--" not in item:
        raise HTTPException(400, "item inválido")
    origem = os.path.join(_pasta_lixeira(), item)
    if not os.path.isfile(os.path.join(origem, "projeto.json")):
        raise HTTPException(404, "não está na lixeira")
    nome = item.rsplit("--", 1)[0]
    if os.path.exists(projeto.pasta(nome)):
        raise HTTPException(409, f"já existe um projeto '{nome}'")
    shutil.move(origem, projeto.pasta(nome))
    return _estado(_carregar(nome))


@router.post("/api/projetos/{nome}/aprovar")
def aprovar(nome: str):
    p = _carregar(nome)
    h = projeto.hash_conteudo(p)
    if p["aprovacao"].get("rascunho_hash") != h:
        raise HTTPException(400, "gere um rascunho com a versao atual antes de aprovar")
    p["aprovacao"]["aprovado_hash"] = h
    projeto.salvar(p)
    return _estado(p)
