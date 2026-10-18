"""Rotas dos provedores de IA e do assistente (so texto, com consentimento)."""
import os
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import referencias, tarefas
from ...core.ia import assistente, config as ia_config, uso
from ...core.ia.provedores import criar as criar_provedor, ErroIA, PRECOS_CLAUDE
from ..comum import _carregar, _f, HOSTS_LOCAIS

router = APIRouter()


# ------------------------------------------------------------------ IA
def _estado_ia():
    cfg = ia_config.carregar()
    prov = []
    for pid, meta in ia_config.PROVEDORES.items():
        chave, origem = ia_config.obter_chave(pid)
        prov.append({"id": pid, "nome": meta["nome"], "painel": meta["painel"], "precisa_chave": meta["precisa_chave"],
                     "credencial": bool(chave) or not meta["precisa_chave"], "origem": origem,
                     "mascara": ia_config.mascarar(chave), "modelo": cfg["provedores"][pid]["modelo"],
                     "consentimento": cfg["provedores"][pid]["consentimento"],
                     "custo_conhecido": pid == "claude" and cfg["provedores"][pid]["modelo"] in PRECOS_CLAUDE})
    return {"provedor_ativo": cfg["provedor_ativo"], "provedores": prov, "limites": cfg["limites"],
            "historico": cfg["historico"], "uso": uso.resumo(), "tarefas": assistente.TAREFAS}


@router.get("/api/ia")
def ia_estado():
    return _estado_ia()


class Credencial(BaseModel):
    provedor: str
    chave: str


@router.post("/api/ia/credencial")
def ia_credencial(dados: Credencial):
    try:
        ia_config.salvar_chave(dados.provedor, dados.chave)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:  # noqa: BLE001 - nunca devolve detalhes que possam conter a chave
        raise HTTPException(500, "não consegui gravar no cofre do Windows")
    return _estado_ia()


@router.delete("/api/ia/credencial/{provedor}")
def ia_credencial_apagar(provedor: str):
    if provedor not in ia_config.PROVEDORES:
        raise HTTPException(404, "provedor desconhecido")
    ia_config.apagar_chave(provedor)
    return _estado_ia()


@router.put("/api/ia/config")
def ia_config_salvar(dados: dict):
    cfg = ia_config.carregar()
    if "provedor_ativo" in dados:
        if dados["provedor_ativo"] not in (None, *ia_config.PROVEDORES):
            raise HTTPException(400, "provedor inválido")
        cfg["provedor_ativo"] = dados["provedor_ativo"]
    for pid, v in (dados.get("provedores") or {}).items():
        if pid not in ia_config.PROVEDORES:
            raise HTTPException(400, "provedor inválido")
        if "modelo" in v:
            cfg["provedores"][pid]["modelo"] = str(v["modelo"] or "")[:120]
        if "consentimento" in v:
            cfg["provedores"][pid]["consentimento"] = bool(v["consentimento"])
    if "limites" in dados:
        L = dados["limites"] or {}
        cfg["limites"] = {"chamadas_por_dia": int(_f(L.get("chamadas_por_dia", 40), "chamadas_por_dia", 1, 10000)),
                          "max_tokens_saida": int(_f(L.get("max_tokens_saida", 8000), "max_tokens_saida", 500, 64000)),
                          "orcamento_mensal_usd": _f(L.get("orcamento_mensal_usd", 5) or 0, "orcamento", 0, 10000)}
    if "historico" in dados:
        H = dados["historico"] or {}
        cfg["historico"] = {"ativo": bool(H.get("ativo", True)), "guardar_conteudo": bool(H.get("guardar_conteudo", False))}
    if "ollama_url" in dados:
        u = str(dados["ollama_url"] or "")
        if (urlparse(u).hostname or "") not in HOSTS_LOCAIS:
            raise HTTPException(400, "o Ollama precisa estar neste PC (127.0.0.1 ou localhost)")
        cfg["ollama_url"] = u
    ia_config.salvar(cfg)
    return _estado_ia()


class ProvedorReq(BaseModel):
    provedor: str


@router.post("/api/ia/testar")
def ia_testar(dados: ProvedorReq):
    """Testa a credencial listando os modelos (não gasta tokens)."""
    if dados.provedor not in ia_config.PROVEDORES:
        raise HTTPException(404, "provedor desconhecido")
    try:
        modelos = criar_provedor(dados.provedor).listar_modelos()
    except ErroIA as e:
        return {"ok": False, "tipo": e.tipo, "erro": str(e)}
    return {"ok": True, "modelos": modelos[:200]}


@router.get("/api/ia/historico")
def ia_historico():
    return list(reversed(uso.registros()))[:200]


@router.delete("/api/ia/historico")
def ia_historico_apagar():
    uso.apagar()
    return {"ok": True}


class PedidoIA(BaseModel):
    extra: str = ""
    perfil: str | None = None


@router.post("/api/projetos/{nome}/ia/previa/{tarefa}")
def ia_previa(nome: str, tarefa: str, dados: PedidoIA):
    """Mostra exatamente o texto que seria enviado, sem enviar nada."""
    p = _carregar(nome)
    try:
        m = assistente.montar(p, tarefa, dados.extra, dados.perfil)
    except ErroIA as e:
        raise HTTPException(400, str(e))
    cfg = ia_config.carregar()
    return {"provedor": cfg["provedor_ativo"], "sistema": m["sistema"], "prompt": m["prompt"],
            "caracteres": len(m["sistema"]) + len(m["prompt"]), "envia_midia": False}


@router.post("/api/projetos/{nome}/ia/{tarefa}")
def ia_executar(nome: str, tarefa: str, dados: PedidoIA):
    p = _carregar(nome)
    if tarefa not in assistente.TAREFAS:
        raise HTTPException(404, "tarefa desconhecida")
    if dados.perfil and not os.path.isfile(referencias.caminho(dados.perfil)):
        raise HTTPException(400, "perfil de referência não existe")
    return tarefas.iniciar("ia", lambda progresso: assistente.executar(p, tarefa, dados.extra, dados.perfil, progresso),
                           pesada=False)


@router.get("/api/projetos/{nome}/ia/sugestoes")
def ia_sugestoes(nome: str):
    _carregar(nome)
    return assistente.sugestoes(nome)
