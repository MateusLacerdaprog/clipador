"""Centro de comando: interpretar (regras/IA) e executar acoes do catalogo; verificador; ritmo."""
import copy
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import comandos, destaques, legendas, projeto, publicacao, react, render, tarefas, verificador, zoom
from ...core import timeline as tl
from ...core.ia import assistente
from ..comum import _carregar, _estado, _fonte_ou_404, _ler_cartoes, _sinais, _validar_legenda
from .fontes import (
    _cortes, _nome_projeto_livre, _segmentos_do_momento, AplicarMomento, destaques_analisar, destaques_aplicar,
    foco_automatico, FocoAuto, PedidoDestaques)
from .legendas import aplicar_plataforma, legendas_destacar, transcrever, Transcricao
from .react import react_recorte
from .revisao import proxy, renderizar
from .zoom import zoom_sugerir

router = APIRouter()


# ====================================================================== COMMAND CENTER
# interpretar (texto -> plano de acoes) e executar (uma acao validada) ficam separados. A execucao so chama
# funcoes do proprio app; a IA, quando usada, so escolhe acoes do catalogo (core/comandos.py).
class Comando(BaseModel):
    texto: str
    usar_ia: bool = False
    contexto: dict | None = None


def _resumo_projeto(p, ctx):
    return (f"tipo {p.get('tipo', 'curto')}, layout {render.layout_efetivo(p)}, {len(p['segmentos'])} trechos "
            f"({projeto.duracao_timeline(p):.0f} s), {len(p['fontes'])} vídeo(s)-fonte, narração {'sim' if p.get('narracao') else 'não'}, "
            f"legendas {len(_ler_cartoes(p['nome']))} cartões, react {'ligado' if (p.get('react') or {}).get('ativo') else 'desligado'}, "
            f"trecho selecionado: {(ctx or {}).get('trecho')}")


def _interpretar_ia(nome, texto, ctx, progresso):
    p = projeto.carregar(nome)
    pedido_ia = {"sistema": "Você é o intérprete de comandos do Clipador. Responda só com o JSON pedido.",
                 "prompt": comandos.prompt_ia(texto, _resumo_projeto(p, ctx)), "schema": comandos.schema_ia()}
    r = assistente.enviar(p, "comando", pedido_ia, progresso)
    plano, recusadas = [], []
    for a in (r["dados"] or {}).get("acoes") or []:
        try:
            item = comandos.descrever(a.get("acao"), a.get("params") or {})
            item["porque"] = str(a.get("porque") or "")[:200]
            plano.append(item)
        except ValueError as e:
            recusadas.append(str(e))
    return {"plano": plano, "origem": r["origem"], "resposta": str((r["dados"] or {}).get("resposta") or "")[:500],
            "recusadas": recusadas}


@router.post("/api/projetos/{nome}/comando/interpretar")
def comando_interpretar(nome: str, dados: Comando):
    _carregar(nome)
    if not dados.texto.strip():
        raise HTTPException(400, "escreva o que quer fazer")
    plano = comandos.interpretar(dados.texto)
    if plano:
        return {"plano": plano, "origem": "regras (sem IA, na hora)"}
    if dados.usar_ia:
        return {"tarefa": tarefas.iniciar("ia", _interpretar_ia, nome, dados.texto, dados.contexto, pesada=False)}
    return {"plano": [], "origem": "regras", "exemplos": comandos.EXEMPLOS,
            "resposta": "Não reconheci esse pedido. Tente um dos exemplos, ou marque “usar IA” para a IA interpretar."}


class Acao(BaseModel):
    acao: str
    params: dict | None = None
    contexto: dict | None = None


def _trechos_alvo(p, params, ctx):
    if params.get("alvo") == "todos":
        return list(range(len(p["segmentos"])))
    i = (ctx or {}).get("trecho")
    if i is None and len(p["segmentos"]) == 1:
        i = 0
    if i is None or not 0 <= int(i) < len(p["segmentos"]):
        raise HTTPException(400, "selecione um trecho na timeline (ou diga “em todos os trechos”)")
    return [int(i)]


def _fonte_ctx(p, ctx):
    fid = (ctx or {}).get("fonte") or (p["fontes"][0]["id"] if p["fontes"] else None)
    if not fid:
        raise HTTPException(400, "adicione um vídeo na aba 1 · Fonte primeiro")
    return _fonte_ou_404(p, fid)


def _criar_shorts(nome, p):
    if p.get("tipo") != "longo":
        raise HTTPException(400, "este projeto já é vertical (9:16). Para tirar vários cortes, use “Encontre os momentos” "
                                 "e “Criar um projeto por momento”.")
    novo = projeto.criar(_nome_projeto_livre(p["nome"], "shorts"))
    novo["tipo"], novo["layout"], novo["referencia"], novo["marca"] = "curto", "empilhado", p.get("referencia"), copy.deepcopy(p.get("marca"))
    pr = legendas.PLATAFORMAS["shorts"]
    novo["legenda"] = _validar_legenda({"estilo": pr["estilo"], "maiusculas": pr["maiusculas"], "plataforma": "shorts",
                                        "fonte": "Arial Black", "tamanho": pr["tamanho"], "contorno": pr["contorno"],
                                        "sombra": pr["sombra"], "cor": pr["cor"], "destaque": pr["destaque"],
                                        "animacao": pr["animacao"], "pos_y": pr["legenda_y"].get("empilhado")})
    novo["audio"] = copy.deepcopy(p["audio"])
    novo["audio"]["efeitos"] = []
    novo["fontes"] = [{k: copy.deepcopy(v) for k, v in f.items() if k != "destaques"} for f in p["fontes"]]
    total = projeto.duracao_timeline(p)
    if total <= 60:
        novo["segmentos"] = copy.deepcopy(p["segmentos"])
        origem = "a montagem inteira (já cabe em 60 s)"
    else:
        f = novo["fontes"][0]
        s = _sinais(nome, f)
        m = destaques.momentos(s, _cortes(f), f["info"]["dur"], 30, 1)
        if not m:
            raise HTTPException(400, "não achei um trecho bom para o Short")
        novo["segmentos"] = _segmentos_do_momento(novo["nome"], novo, f, m[0], s)
        origem = f"o melhor momento ({m[0]['ini']:.0f}–{m[0]['fim']:.0f} s): {'; '.join(m[0]['motivos'])}"
    novo["roteiro"] = f"Versão vertical de “{p['nome']}”, feita a partir de {origem}."
    projeto.salvar(novo)
    return {"mensagem": f"Projeto novo “{novo['nome']}” (vertical, empilhado, legenda Shorts) a partir de {origem}.",
            "criados": [novo["nome"]]}


def _revisao(nome, progresso):
    p = projeto.carregar(nome)
    itens = verificador.verificar_projeto(p)
    if any(i["nivel"] == "erro" for i in itens):
        return {"itens": itens, "arquivo": None, "mensagem": "Corrija os erros antes de gerar o rascunho."}
    progresso(0.05, "gerando o RASCUNHO")
    saida = render.render(p, "rascunho", progresso)
    progresso(0.97, "conferindo o arquivo gerado")
    return {"itens": [i for i in itens if i["nivel"] != "ok"] + verificador.verificar_arquivo(saida, p),
            "arquivo": os.path.basename(saida), "mensagem": "RASCUNHO pronto e conferido. Assista inteiro antes de aprovar."}


def _executar_acao(nome, acao, params, ctx):
    p = _carregar(nome)
    if acao == "legendas.gerar":
        origem = params.get("origem", "auto")
        if origem == "auto":
            origem = "narracao" if p.get("narracao") else "video"
        return {"tarefa": transcrever(nome, Transcricao(modelo="small", origem=origem)), "aba": "legendas",
                "mensagem": f"Transcrevendo {'a narração' if origem == 'narracao' else 'o áudio do vídeo'}…"}
    if acao == "legendas.destacar":
        r = legendas_destacar(nome)
        return {"mensagem": f"{r['marcadas']} palavra(s) destacada(s). Ajuste com *palavra* no texto do cartão.", "aba": "legendas"}
    if acao == "legendas.plataforma":
        aplicar_plataforma(nome, params["plataforma"])
        return {"mensagem": f"Visual de legenda {legendas.PLATAFORMAS[params['plataforma']]['nome']} aplicado.", "aba": "legendas"}
    if acao == "momentos.achar":
        f = _fonte_ctx(p, ctx)
        return {"tarefa": destaques_analisar(nome, f["id"], PedidoDestaques(duracao=min(params["duracao"], max(5, f["info"]["dur"])),
                                                                            quantidade=params["quantidade"])),
                "aba": "cortes", "modo_cortes": "momentos", "mensagem": "Procurando os momentos (áudio, impactos, movimento)…"}
    if acao == "momentos.usar":
        f = _fonte_ctx(p, ctx)
        if not (f.get("destaques") or {}).get("lista"):
            raise HTTPException(400, "primeiro encontre os momentos (“Encontre os momentos mais interessantes”)")
        destaques_aplicar(nome, f["id"], AplicarMomento(indice=params["indice"]))
        return {"mensagem": "Timeline montada com o momento escolhido (Ctrl+Z desfaz).", "aba": "cortes"}
    if acao in ("zoom.aplicar", "zoom.remover"):
        alvo = _trechos_alvo(p, params, ctx)
        for i in alvo:
            s = p["segmentos"][i]
            if acao == "zoom.remover":
                s.pop("zoom_fx", None)
                s["zoom"] = 1.0
            else:
                antigo = s.get("zoom_fx") or {}
                s["zoom_fx"] = zoom.validar({"preset": params["preset"], "foco_x": antigo.get("foco_x", 0.5),
                                             "foco_y": antigo.get("foco_y", 0.5)})
        projeto.salvar(p)
        nome_preset = zoom.PRESETS.get(params.get("preset"), {}).get("nome", "")
        quais = "todos os trechos" if len(alvo) > 1 else f"trecho {alvo[0] + 1}"
        return {"mensagem": (f"Zoom “{nome_preset}” no {quais}." if acao == "zoom.aplicar" else f"Zoom removido: {quais}.")
                + " Confira com “▶ Prévia exata” (Ctrl+Z desfaz).", "aba": "cortes"}
    if acao == "zoom.picos":
        r = zoom_sugerir(nome)
        return {"mensagem": (f"Zoom de impacto em {len(r['sugeridos'])} trecho(s) com pico de ação." if r["sugeridos"]
                             else "Nenhum trecho tem pico de ação forte: nada mudou."), "aba": "cortes"}
    if acao == "foco.auto":
        foco_automatico(nome, FocoAuto())
        return {"mensagem": "Cada trecho foi reenquadrado para onde está a ação.", "aba": "cortes"}
    if acao == "shorts.criar":
        return _criar_shorts(nome, p)
    if acao == "react.recorte":
        R = react.completar(p.get("react"))
        if not R["arquivo"] or not react.estado_extra(p)["camera_ok"]:
            raise HTTPException(400, "grave ou envie a câmera do criador na aba React primeiro")
        R.update(modo="fundo_virtual", ativo=True)
        ex = react.estado_extra(p)
        if ex["matte_pronto"]:
            R["recorte_ia"]["ativo"] = True
            p["react"] = R
            projeto.salvar(p)
            return {"mensagem": "Criador recortado (IA) sobre o gameplay. Ajuste posição e tamanho na prévia.", "aba": "react"}
        p["react"] = R
        projeto.salvar(p)
        if R["chroma"]["ativo"]:
            return {"mensagem": "Criador sobre o gameplay usando o chroma key.", "aba": "react"}
        return {"tarefa": react_recorte(nome), "aba": "react",
                "mensagem": "Fundo virtual ligado; gerando o recorte por IA (sem tela verde) neste PC…"}
    if acao == "previa.gerar":
        return {"tarefa": proxy(nome), "aba": "narracao", "mensagem": "Gerando a prévia da montagem…"}
    if acao == "timeline.loop":
        try:
            tl.fechar_loop(p)
        except tl.ErroTimeline as e:
            return {"mensagem": str(e), "aba": "cortes"}
        projeto.salvar(p)
        return {"mensagem": "Loop fechado: o fim repete 0,9 s do começo (Ctrl+Z desfaz).", "aba": "cortes"}
    if acao == "publicacao.verificar":
        return {"itens": publicacao.verificar(p), "aba": "revisar", "mensagem": "Publicação conferida."}
    if acao == "verificar":
        return {"itens": verificador.verificar_projeto(p), "aba": "revisar", "mensagem": "Verificação feita."}
    if acao == "revisao.preparar":
        return {"tarefa": tarefas.iniciar("rascunho", _revisao, nome), "aba": "revisar",
                "mensagem": "Verificando o projeto e gerando o RASCUNHO…"}
    if acao == "exportar.final":
        return {"tarefa": renderizar(nome, "final"), "aba": "revisar", "mensagem": "Gerando o FINAL (rascunho aprovado)…"}
    if acao == "ir":
        return {"aba": params["aba"], "mensagem": ""}
    raise HTTPException(400, "ação sem executor")


@router.post("/api/projetos/{nome}/comando/executar")
def comando_executar(nome: str, dados: Acao):
    try:
        params = comandos.validar(dados.acao, dados.params or {})
    except ValueError as e:
        raise HTTPException(400, str(e))
    r = _executar_acao(nome, dados.acao, params, dados.contexto or {})
    p = projeto.carregar(nome)
    return {**r, "acao": dados.acao, "estado": _estado(p)}


@router.get("/api/comandos")
def comandos_catalogo():
    return {"acoes": {k: {"desc": v["desc"], "params": v["params"]} for k, v in comandos.ACOES.items()},
            "exemplos": comandos.EXEMPLOS}


@router.get("/api/projetos/{nome}/verificar")
def verificar(nome: str):
    p = _carregar(nome)
    itens = verificador.verificar_projeto(p)
    rasc = verificador.rascunho_atual(p)
    if rasc:
        itens = [i for i in itens if i["nivel"] != "ok"] + verificador.verificar_arquivo(rasc, p)
    return {"itens": itens, "conferiu_arquivo": bool(rasc)}
