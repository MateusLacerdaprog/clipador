"""Rotas de legendas e textos: transcrever, editar, tempos, plataformas, SRT/VTT, edicao manual."""
import os
import shutil

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core import audio, legendas, pedido, projeto, render, tarefas
from ..comum import (
    _carregar, _cartoes_anterior, _cartoes_path, _estado, _f, _fonte_ou_404, _gravar_cartoes, _ler_cartoes,
    _validar_legenda)

router = APIRouter()


# -------------------------------------------------------------------- legendas
class Transcricao(BaseModel):
    modelo: str = "small"
    origem: str = "narracao"        # narracao | video (fala que ja esta no audio dos trechos)


def _palavras_do_video(nome, p, modelo, progresso):
    """Transcreve cada video-fonte usado (cache por fonte) e leva as palavras para o relogio da montagem."""
    usadas = list(dict.fromkeys(s["fonte"] for s in p["segmentos"]))
    por_fonte = {}
    for k, fid in enumerate(usadas):
        f = _fonte_ou_404(p, fid)
        if not f["info"].get("audio"):
            continue
        sub = lambda fr, m=None, k=k: progresso(0.05 + 0.85 * (k + fr) / len(usadas), m)
        por_fonte[fid] = pedido.transcrever_fonte(projeto.pasta(nome), f, modelo=modelo, progresso=sub)
    palavras, acc = [], 0.0
    for s in p["segmentos"]:
        for w in por_fonte.get(s["fonte"], []):
            if s["ini"] <= w["start"] < s["fim"]:
                palavras.append({"w": w["w"], "start": round(acc + w["start"] - s["ini"], 3),
                                 "end": round(acc + min(w["end"], s["fim"]) - s["ini"], 3)})
        acc += s["fim"] - s["ini"]
    return palavras


def _transcrever(nome, modelo, origem, progresso):
    p = projeto.carregar(nome)
    if origem == "video":
        if not p["segmentos"]:
            raise RuntimeError("monte a timeline (aba Cortes) antes de legendar o áudio do vídeo")
        palavras = _palavras_do_video(nome, p, modelo, progresso)
        if not palavras:
            raise RuntimeError("não encontrei fala no áudio dos trechos da montagem")
    else:
        if not p.get("narracao"):
            raise RuntimeError("grave ou envie a narração antes de transcrever (ou escolha “Áudio do vídeo”)")
        progresso(0.1, f"transcrevendo com whisper '{modelo}' (a 1a vez baixa o modelo)")
        palavras = legendas.transcrever(os.path.join(projeto.pasta(nome), p["narracao"]), modelo, p.get("roteiro", ""))
        if not palavras:
            raise RuntimeError("nenhuma fala detectada (volume muito baixo?)")
    # narracao: tempos no relogio da narracao (o deslocamento da trilha entra no .ass); video: relogio da montagem
    cart = legendas.construir_cartoes(palavras, p["legenda"]["estilo"])
    # nunca maior que o video: o que a narracao fala depois do fim da montagem nao vira legenda
    fim = projeto.duracao_timeline(p)
    if origem == "narracao":
        fim -= audio.migrar(p["audio"])["narracao"]["deslocamento"]
    total = sum(len(c["palavras"]) for c in cart)
    cart = legendas.limitar(cart, fim) if p["segmentos"] else cart
    fora = total - sum(len(c["palavras"]) for c in cart)

    def gravar(atual):                               # sob a trava: nao apaga o que o usuario editou enquanto transcrevia
        _guardar_anterior(nome, atual)               # guarda a versao de antes (botao Desfazer da interface)
        _gravar_cartoes(nome, cart)
        atual["legenda_origem"] = origem
        atual["legenda_base"] = projeto.base_legenda(atual, origem)
    projeto.alterar(nome, gravar)
    return {"cartoes": len(cart), "origem": origem, "fora_do_video": fora}


@router.post("/api/projetos/{nome}/legendas/transcrever")
def transcrever(nome: str, dados: Transcricao):
    _carregar(nome)
    if dados.modelo not in ("tiny", "base", "small", "medium"):
        raise HTTPException(400, "modelo invalido")
    if dados.origem not in ("narracao", "video"):
        raise HTTPException(400, "origem invalida: narracao ou video")
    return tarefas.iniciar("transcricao", _transcrever, nome, dados.modelo, dados.origem)


def _guardar_anterior(nome, p):
    """Antes de qualquer mudanca grande nas legendas: guarda os cartoes (e de onde eles vem) para o Desfazer.
    O chamador salva o projeto."""
    atual = _cartoes_path(nome)
    if os.path.isfile(atual):
        shutil.copyfile(atual, _cartoes_anterior(nome))
    else:
        with open(_cartoes_anterior(nome), "w", encoding="utf-8") as f:
            f.write("[]")
    p["legenda_origem_anterior"] = p.get("legenda_origem") or "narracao"


@router.post("/api/projetos/{nome}/legendas/restaurar")
def legendas_restaurar(nome: str):
    """Desfaz a ultima mudanca (transcrever, excluir, adicionar, mostrar no video): volta os cartoes de antes.
    Troca com os atuais, entao clicar de novo refaz."""
    p = _carregar(nome)
    ant, atual = _cartoes_anterior(nome), _cartoes_path(nome)
    if not os.path.isfile(ant):
        raise HTTPException(400, "não há legenda anterior para voltar")
    tmp = atual + ".troca"
    os.replace(ant, tmp)
    if os.path.isfile(atual):
        os.replace(atual, ant)
    os.replace(tmp, atual)
    if p.get("legenda_origem_anterior"):             # os tempos dos cartoes dependem da origem: troca junto
        p["legenda_origem"], p["legenda_origem_anterior"] = p["legenda_origem_anterior"], p.get("legenda_origem") or "narracao"
        p["legenda_base"] = projeto.base_legenda(p) if p["legenda_origem"] == "manual" else p.get("legenda_base")
        projeto.salvar(p)
    return {**_estado(p), "cartoes": _ler_cartoes(nome)}


# ---- edicao manual (aba 6 · Textos e na propria previa): tempos que a interface manda sao do VIDEO
def _desloc_cartoes(p):
    """Tempo no video = tempo do cartao + este valor (so a legenda da narracao tem deslocamento)."""
    return 0.0 if projeto.relogio_da_montagem(p) else float(audio.migrar(p["audio"])["narracao"]["deslocamento"])


def _visivel(p):
    return projeto.relogio_da_montagem(p) or bool(p.get("narracao") and audio.migrar(p["audio"])["narracao"]["ativo"])


def _para_manual(p, cart):
    """Passa os cartoes para o relogio do video (+ deslocamento) e a origem para 'manual' (sempre aparecem)."""
    desl = _desloc_cartoes(p)
    out = []
    for c in cart:
        ps = [{**w, "start": round(max(w["start"] + desl, 0.0), 3), "end": round(w["end"] + desl, 3)}
              for w in c.get("palavras") or [] if w["end"] + desl > 0.04]
        if ps:
            out.append({**c, "palavras": ps})
    p["legenda_origem"], p["legenda_base"] = "manual", "manual"
    return out


@router.post("/api/projetos/{nome}/legendas/manual")
def legendas_mostrar_no_video(nome: str):
    """Legendas de uma narracao que nao esta no projeto: passam a usar o tempo do video e aparecem no render."""
    p = _carregar(nome)
    cart = _ler_cartoes(nome)
    if not cart:
        raise HTTPException(400, "não há legendas")
    _guardar_anterior(nome, p)
    _gravar_cartoes(nome, _para_manual(p, cart))
    projeto.salvar(p)
    return {**_estado(p), "cartoes": _ler_cartoes(nome)}


class NovaLegenda(BaseModel):
    texto: str
    ini: float
    fim: float


def _texto_legenda(t):
    t = " ".join(str(t or "").split())
    if not t or len(t) > 200 or len(t.split()) > 15:
        raise HTTPException(400, "texto da legenda: de 1 a 15 palavras (até 200 caracteres)")
    return t


@router.post("/api/projetos/{nome}/legendas/cartao")
def legendas_adicionar(nome: str, dados: NovaLegenda):
    """Legenda escrita a mao no instante escolhido (tempos do video). Nunca invade outro cartao nem passa do fim."""
    p = _carregar(nome)
    texto = _texto_legenda(dados.texto)
    total = projeto.duracao_timeline(p)
    if total <= 0:
        raise HTTPException(400, "monte a timeline (aba 2 · Cortes) antes de escrever legendas")
    ini = _f(dados.ini, "ini", 0, total)
    fim = min(_f(dados.fim, "fim", 0, 36000), total)  # passou do fim do video: termina no fim
    cart = _ler_cartoes(nome)
    _guardar_anterior(nome, p)
    if not _visivel(p):                              # projeto sem narracao: tudo passa para o tempo do video
        cart = _para_manual(p, cart)
    desl = _desloc_cartoes(p)
    a, b = round(ini - desl, 3), round(fim - desl, 3)
    k = sum(1 for c in cart if c["palavras"] and c["palavras"][0]["start"] <= a)
    if k > 0 and cart[k - 1]["palavras"][-1]["end"] > a + 0.01:
        raise HTTPException(400, "já tem legenda nesse instante: clique nela para editar, ou escolha outro momento")
    if k < len(cart):
        b = min(b, cart[k]["palavras"][0]["start"] - 0.01)
    if b - a < 0.2:
        raise HTTPException(400, "não cabe uma legenda aqui (pelo menos 0,2 s antes da próxima)")
    novo = legendas.aplicar_texto({"palavras": [{"w": "x", "start": a, "end": b}]}, texto)
    novo["manual"] = True
    cart.insert(k, novo)
    _gravar_cartoes(nome, cart)
    projeto.salvar(p)
    return {**_estado(p), "cartoes": cart, "indice": k}


class TextoCartao(BaseModel):
    texto: str


@router.put("/api/projetos/{nome}/legendas/cartao/{i}/texto")
def legendas_texto_cartao(nome: str, i: int, dados: TextoCartao):
    """Troca o texto de UM cartao (edicao na propria previa). Texto vazio exclui o cartao."""
    cart = _ler_cartoes(nome)
    if not 0 <= i < len(cart):
        raise HTTPException(404, "cartão inexistente (recarregue a página)")
    if not dados.texto.strip():
        return legendas_excluir_cartao(nome, i)
    legendas.aplicar_texto(cart[i], _texto_legenda(dados.texto))
    _gravar_cartoes(nome, cart)
    return {**_estado(_carregar(nome)), "cartoes": cart}


@router.delete("/api/projetos/{nome}/legendas/cartao/{i}")
def legendas_excluir_cartao(nome: str, i: int):
    p = _carregar(nome)
    cart = _ler_cartoes(nome)
    if not 0 <= i < len(cart):
        raise HTTPException(404, "cartão inexistente (recarregue a página)")
    _guardar_anterior(nome, p)
    del cart[i]
    _gravar_cartoes(nome, cart)
    projeto.salvar(p)
    return {**_estado(p), "cartoes": cart}


@router.delete("/api/projetos/{nome}/legendas")
def legendas_excluir_todas(nome: str):
    p = _carregar(nome)
    _guardar_anterior(nome, p)
    _gravar_cartoes(nome, [])
    projeto.salvar(p)
    return {**_estado(p), "cartoes": []}


@router.post("/api/projetos/{nome}/legendas/destacar")
def legendas_destacar(nome: str):
    """Marca 1 palavra importante por cartao (numeros, siglas, nomes). O usuario corrige com *palavra* no editor."""
    _carregar(nome)
    cart = _ler_cartoes(nome)
    if not cart:
        raise HTTPException(400, "transcreva primeiro")
    n = legendas.destacar_automatico(cart)
    _gravar_cartoes(nome, cart)
    return {"marcadas": n, "cartoes": cart}


@router.get("/api/projetos/{nome}/legendas")
def legendas_obter(nome: str):
    _carregar(nome)
    return _ler_cartoes(nome)


class Textos(BaseModel):
    textos: list[str]


@router.put("/api/projetos/{nome}/legendas")
def legendas_editar(nome: str, dados: Textos):
    _carregar(nome)
    cart = _ler_cartoes(nome)
    if len(dados.textos) != len(cart):
        raise HTTPException(400, "numero de cartoes diferente (recarregue a pagina)")
    if any(not t.strip() for t in dados.textos):     # cartao apagado no texto = cartao excluido (com Desfazer)
        p = _carregar(nome)
        _guardar_anterior(nome, p)
        projeto.salvar(p)
    novos = []
    for c, t in zip(cart, dados.textos):
        if t.strip():
            novos.append(legendas.aplicar_texto(c, t[:200]))
    _gravar_cartoes(nome, novos)
    return novos


@router.get("/api/legendas/plataformas")
def plataformas():
    return {"plataformas": legendas.PLATAFORMAS, "fontes": legendas.FONTES, "animacoes": legendas.ANIMACOES,
            "posicoes": legendas.POSICOES, "estilos": legendas.ESTILOS, "pos_x": legendas.POS_X}


@router.post("/api/projetos/{nome}/legendas/plataforma/{pid}")
def aplicar_plataforma(nome: str, pid: str):
    """Aplica o preset de legenda da plataforma (estilo, posicao na zona segura, tamanho, cores, animacao)."""
    p = _carregar(nome)
    pr = legendas.PLATAFORMAS.get(pid)
    if not pr:
        raise HTTPException(404, "plataforma desconhecida")
    antes = p["legenda"]["estilo"]
    layout = render.layout_efetivo(p)
    p["legenda"] = _validar_legenda({
        "estilo": pr["estilo"], "maiusculas": pr["maiusculas"], "plataforma": pid, "fonte": "Arial Black",
        "tamanho": pr["tamanho"], "contorno": pr["contorno"], "sombra": pr["sombra"], "cor": pr["cor"],
        "destaque": pr["destaque"], "animacao": pr["animacao"],
        "pos_y": None if layout == "horizontal" else pr["legenda_y"].get(layout)})
    projeto.salvar(p)
    if pr["estilo"] != antes:
        cart = _ler_cartoes(nome)
        if cart:
            _gravar_cartoes(nome, legendas.reagrupar(cart, pr["estilo"]))
    return _estado(p)


class TemposCartao(BaseModel):
    palavras: list[dict]


@router.put("/api/projetos/{nome}/legendas/cartao/{i}")
def legendas_tempo(nome: str, i: int, dados: TemposCartao):
    p = _carregar(nome)
    cart = _ler_cartoes(nome)
    try:
        legendas.editar_tempos(cart, i, dados.palavras[:20], dur_max=None)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _gravar_cartoes(nome, cart)
    return cart


@router.get("/api/projetos/{nome}/legendas.srt")
def legendas_srt(nome: str):
    from fastapi.responses import Response
    p = _carregar(nome)
    txt = render.legenda_srt(p)
    if not txt.strip():
        raise HTTPException(404, "não há legenda para exportar (transcreva a narração primeiro)")
    return Response(txt, media_type="application/x-subrip; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{projeto.slug(nome)}.srt"'})


@router.get("/api/projetos/{nome}/legendas.vtt")
def legendas_vtt(nome: str):
    from fastapi.responses import Response
    p = _carregar(nome)
    txt = render.legenda_srt(p)
    if not txt.strip():
        raise HTTPException(404, "não há legenda para exportar (transcreva primeiro)")
    return Response(legendas.srt_para_vtt(txt), media_type="text/vtt; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{projeto.slug(nome)}.vtt"'})
