"""Rotas de video-fonte: adicionar, sugerir cortes, momentos (destaques), transcricao da fonte, pedido."""
import copy
import os
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...core import destaques, midia, pedido, projeto, render, tarefas
from ...core.ia import assistente, config as ia_config
from ..comum import _carregar, _estado, _f, _fonte_ou_404, _nome_livre, _sinais, _validar_segmentos, VIDEO_EXT

router = APIRouter()


# ---------------------------------------------------------------------- fontes
def _registrar_fonte(nome, caminho, progresso):
    progresso(0.05, "lendo o video")
    inf = midia.info(caminho)
    progresso(0.15, "procurando tarjas pretas")
    crop = midia.detectar_tarjas(caminho, min(5.0, inf["dur"] / 4), min(60.0, inf["dur"]))
    progresso(0.3, "detectando cenas")
    cs = destaques.cenas(caminho, inf)
    fid = projeto.novo_id()
    cache = os.path.join(projeto.pasta(nome), "cache", fid)
    for i, c in enumerate(cs):
        progresso(0.4 + 0.6 * i / max(len(cs), 1), f"miniaturas {i + 1}/{len(cs)}")
        arq = os.path.join(cache, f"c{i:03d}.jpg")
        if midia.miniatura(caminho, (c["ini"] + c["fim"]) / 2, arq):
            c["miniatura"] = os.path.relpath(arq, projeto.pasta(nome)).replace("\\", "/")
    def incluir(p):
        p["fontes"].append({"id": fid, "caminho": os.path.abspath(caminho), "nome": os.path.basename(caminho),
                            "info": inf, "crop": crop, "cenas": cs})
        if p.get("layout") == "comparacao":       # comparacao: o 1o video vira o A (em cima), o 2o o B (embaixo)
            for k in ("fonte_a", "fonte_b"):
                if not p["comparacao"].get(k):
                    p["comparacao"][k] = fid
                    break
    projeto.alterar(nome, incluir)
    return {"fonte": fid}


class Caminho(BaseModel):
    caminho: str


class Url(BaseModel):
    url: str


@router.post("/api/projetos/{nome}/fontes/caminho")
def fonte_caminho(nome: str, dados: Caminho):
    _carregar(nome)
    c = dados.caminho.strip().strip('"')
    if not os.path.isfile(c) or not c.lower().endswith(VIDEO_EXT):
        raise HTTPException(400, "arquivo de video nao encontrado")
    return tarefas.iniciar("fonte", _registrar_fonte, nome, c)


@router.post("/api/projetos/{nome}/fontes/upload")
async def fonte_upload(nome: str, arquivo: UploadFile = File(...)):
    _carregar(nome)
    base = os.path.basename((arquivo.filename or "video.mp4").replace("\\", "/"))
    if not base.lower().endswith(VIDEO_EXT):
        raise HTTPException(400, "formato de video nao suportado")
    pasta = os.path.join(projeto.pasta(nome), "fontes")
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, _nome_livre(pasta, base))
    with open(destino, "wb") as f:
        shutil.copyfileobj(arquivo.file, f, 4 << 20)
    return tarefas.iniciar("fonte", _registrar_fonte, nome, destino)


def _baixar(nome, url, progresso):
    import yt_dlp

    pasta = os.path.join(projeto.pasta(nome), "fontes")
    os.makedirs(pasta, exist_ok=True)

    def gancho(d):
        if d.get("status") == "downloading" and d.get("total_bytes"):
            progresso(0.5 * d["downloaded_bytes"] / d["total_bytes"], "baixando")

    opts = {"format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b",
            "merge_output_format": "mp4", "outtmpl": os.path.join(pasta, "%(title).80B [%(id)s].%(ext)s"),
            "quiet": True, "no_warnings": True, "progress_hooks": [gancho], "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
        caminho = y.prepare_filename(info)
    if not os.path.isfile(caminho):
        caminho = os.path.splitext(caminho)[0] + ".mp4"
    return _registrar_fonte(nome, caminho, lambda f, m=None: progresso(0.5 + f / 2, m))


@router.post("/api/projetos/{nome}/fontes/url")
def fonte_url(nome: str, dados: Url):
    _carregar(nome)
    if not dados.url.startswith(("http://", "https://")):
        raise HTTPException(400, "link invalido")
    return tarefas.iniciar("fonte", _baixar, nome, dados.url.strip())


@router.delete("/api/projetos/{nome}/fontes/{fid}")
def fonte_remover(nome: str, fid: str):
    p = _carregar(nome)
    if any(s["fonte"] == fid or s.get("fonte_b") == fid for s in p["segmentos"]):
        raise HTTPException(400, "essa fonte esta em uso em algum trecho")
    p["fontes"] = [f for f in p["fontes"] if f["id"] != fid]
    for k in ("fonte_a", "fonte_b"):                 # a comparacao deixa de apontar para o video removido
        if p["comparacao"].get(k) == fid:
            p["comparacao"][k] = None
    projeto.salvar(p)
    return _estado(p)


class MontarComparacao(BaseModel):
    duracao: float = 20.0          # so quando a timeline esta vazia: um trecho com essa duracao


@router.post("/api/projetos/{nome}/comparacao/montar")
def comparacao_montar(nome: str, dados: MontarComparacao):
    """Monta a tela dividida: todo trecho passa a mostrar o video A em cima e o B embaixo, no mesmo instante
    (cabendo no B). Timeline vazia: cria um trecho do comeco. A interface guarda o antes (Desfazer)."""
    p = _carregar(nome)
    if p.get("tipo") == "longo":
        raise HTTPException(400, "a comparação A × B (tela dividida) só existe no vídeo curto")
    C = p["comparacao"]
    if not (C.get("fonte_a") and C.get("fonte_b")):
        raise HTTPException(400, "escolha o vídeo de cima (A) e o de baixo (B)")
    fa, fb = _fonte_ou_404(p, C["fonte_a"]), _fonte_ou_404(p, C["fonte_b"])
    da, db = fa["info"]["dur"], fb["info"]["dur"]
    segs = copy.deepcopy(p["segmentos"]) or [{"fonte": fa["id"], "ini": 0.0, "foco_x": 0.5, "zoom": 1.0,
                                             "fim": round(min(da, db, _f(dados.duracao, "duracao", 1, 600)), 3)}]
    for s in segs:
        if s["fonte"] != fa["id"]:                    # trecho de outro video: mesmo tempo, agora no A
            s["fonte"] = fa["id"]
            s["fim"] = round(min(s["fim"], da), 3)
            s["ini"] = round(min(s["ini"], max(s["fim"] - 0.5, 0)), 3)
        dur = min(s["fim"] - s["ini"], db)
        s["fim"] = round(s["ini"] + dur, 3)
        if s.get("fonte_b") != fb["id"] or s.get("ini_b") is None:
            s["ini_b"] = round(max(0.0, min(s["ini"], db - dur)), 3)
        s["fonte_b"] = fb["id"]
        s["ini_b"] = round(min(s["ini_b"], max(db - dur, 0.0)), 3)
    p["layout"] = "comparacao"
    p["segmentos"] = _validar_segmentos(p, segs)
    projeto.salvar(p)
    return _estado(p)


@router.get("/api/projetos/{nome}/fontes/{fid}/video")
def fonte_video(nome: str, fid: str):
    p = _carregar(nome)
    try:
        c = projeto.fonte(p, fid)["caminho"]
    except KeyError:
        raise HTTPException(404, "fonte nao existe")
    if not os.path.isfile(c):
        raise HTTPException(404, "o arquivo de video foi movido ou apagado")
    return FileResponse(c)


class Sugestao(BaseModel):
    alvo: float = 20.0
    max_cena: float = 4.0


@router.post("/api/projetos/{nome}/fontes/{fid}/sugerir")
def sugerir(nome: str, fid: str, dados: Sugestao):
    p = _carregar(nome)
    try:
        f = projeto.fonte(p, fid)
    except KeyError:
        raise HTTPException(404, "fonte nao existe")
    segs = destaques.sugerir_sequencia(f.get("cenas") or [], _f(dados.alvo, "alvo", 3, 600),
                                       _f(dados.max_cena, "max_cena", 0.5, 30))
    p["segmentos"] = [{"id": projeto.novo_id(), "fonte": fid, "foco_x": 0.5, "zoom": 1.0, **s} for s in segs]
    projeto.salvar(p)
    return _estado(p)


# ---------------------------------------------------------------- destaques (momentos)
ASPECTO_LAYOUT = {"tela_cheia": 9 / 16, "empilhado": 1080 / 864, "dividido": 1080 / 960, "comparacao": 1080 / 960}


def _cortes(f):
    return [c["ini"] for c in f.get("cenas") or [] if c["ini"] > 0]


def _segmentos_do_momento(nome, p, f, m, s=None, dividir=True):
    """Trechos de um momento: divididos nos cortes de cena, cada um com foco automatico no movimento."""
    s = s if s is not None else _sinais(nome, f)
    aspecto = ASPECTO_LAYOUT.get(render.layout_efetivo(p))
    partes = destaques.dividir_em_cortes(m["ini"], m["fim"], _cortes(f)) if dividir else [(m["ini"], m["fim"])]
    return [{"id": projeto.novo_id(), "fonte": f["id"], "ini": a, "fim": b, "zoom": 1.0,
             "foco_x": destaques.foco_auto(s, a, b, f, aspecto) if aspecto else 0.5} for a, b in partes]


class PedidoDestaques(BaseModel):
    duracao: float = 20.0
    quantidade: int = 5


def _analisar_destaques(nome, fid, duracao, quantidade, progresso):
    p = projeto.carregar(nome)
    f = _fonte_ou_404(p, fid)
    s = _sinais(nome, f, progresso)
    progresso(0.9, "escolhendo os melhores momentos")
    lista = destaques.momentos(s, _cortes(f), f["info"]["dur"], duracao, quantidade)
    # grava so os momentos (sob a trava): o usuario pode ter editado durante a analise
    projeto.alterar(nome, lambda q: projeto.fonte(q, fid).update(destaques={"duracao": duracao, "lista": lista}))
    return {"quantidade": len(lista)}


@router.post("/api/projetos/{nome}/fontes/{fid}/destaques")
def destaques_analisar(nome: str, fid: str, dados: PedidoDestaques):
    p = _carregar(nome)
    f = _fonte_ou_404(p, fid)
    dur = _f(dados.duracao, "duracao", 5, min(600, max(5, f["info"]["dur"])))
    qtd = int(_f(dados.quantidade, "quantidade", 1, 20))
    return tarefas.iniciar("destaques", _analisar_destaques, nome, fid, dur, qtd)


class AplicarMomento(BaseModel):
    indice: int
    dividir: bool = True


@router.post("/api/projetos/{nome}/fontes/{fid}/destaques/aplicar")
def destaques_aplicar(nome: str, fid: str, dados: AplicarMomento):
    p = _carregar(nome)
    f = _fonte_ou_404(p, fid)
    lista = (f.get("destaques") or {}).get("lista") or []
    if not 0 <= dados.indice < len(lista):
        raise HTTPException(400, "momento inexistente: analise os destaques de novo")
    p["segmentos"] = _segmentos_do_momento(nome, p, f, lista[dados.indice], dividir=dados.dividir)
    projeto.salvar(p)
    return _estado(p)


class FocoAuto(BaseModel):
    indices: list[int] | None = None     # None = todos os trechos


@router.post("/api/projetos/{nome}/foco_auto")
def foco_automatico(nome: str, dados: FocoAuto):
    """Reenquadra os trechos para seguir a acao (centro do movimento). Nao mexe no zoom."""
    p = _carregar(nome)
    aspecto = ASPECTO_LAYOUT.get(render.layout_efetivo(p))
    if not aspecto:
        raise HTTPException(400, "o video longo (16:9) mostra o quadro inteiro: nao ha foco para ajustar")
    alvo = range(len(p["segmentos"])) if dados.indices is None else dados.indices
    cache = {}
    for i in alvo:
        if not 0 <= i < len(p["segmentos"]):
            raise HTTPException(400, f"trecho {i + 1} nao existe")
        sg = p["segmentos"][i]
        f = _fonte_ou_404(p, sg["fonte"])
        if f["id"] not in cache:
            cache[f["id"]] = _sinais(nome, f)
        sg["foco_x"] = destaques.foco_auto(cache[f["id"]], sg["ini"], sg["fim"], f, aspecto)
    projeto.salvar(p)
    return _estado(p)


class Lote(BaseModel):
    indices: list[int]


def _nome_projeto_livre(base, sufixo="clipe"):
    existentes = set(projeto.listar())
    for k in range(1, 1000):
        n = projeto.slug(f"{base}-{sufixo}-{k}")
        if n not in existentes:
            return n
    raise HTTPException(409, "nomes de projeto esgotados")


@router.post("/api/projetos/{nome}/fontes/{fid}/destaques/lote")
def destaques_lote(nome: str, fid: str, dados: Lote):
    """Cria um projeto novo por momento escolhido, com o mesmo formato/estilo/legenda/audio deste projeto.
    Narracao, legendas e aprovacao NAO sao copiadas (cada clipe tem a sua)."""
    p = _carregar(nome)
    f = _fonte_ou_404(p, fid)
    lista = (f.get("destaques") or {}).get("lista") or []
    if not dados.indices or len(dados.indices) > 20 or any(not 0 <= i < len(lista) for i in dados.indices):
        raise HTTPException(400, "escolha de 1 a 20 momentos da lista")
    s = _sinais(nome, f)
    criados = []
    for i in dados.indices:
        novo = projeto.criar(_nome_projeto_livre(p["nome"]))
        for k in ("tipo", "formato", "formato_cfg", "layout", "legenda", "referencia", "marca"):
            novo[k] = copy.deepcopy(p[k])
        novo["audio"] = copy.deepcopy(p["audio"])
        novo["audio"]["efeitos"] = []                 # efeitos sao presos a instantes do outro clipe
        novo["gancho"] = {"texto": "", "ate": p["gancho"].get("ate", 3.0)}
        fonte_nova = {k: copy.deepcopy(v) for k, v in f.items() if k != "destaques"}
        origem_cache = os.path.join(projeto.pasta(nome), "cache", fid)
        if os.path.isdir(origem_cache):              # miniaturas das cenas + sinais
            shutil.copytree(origem_cache, os.path.join(projeto.pasta(novo["nome"]), "cache", fid), dirs_exist_ok=True)
        novo["fontes"] = [fonte_nova]
        novo["segmentos"] = _segmentos_do_momento(novo["nome"], novo, fonte_nova, lista[i], s)
        m = lista[i]
        novo["roteiro"] = (f"Clipe gerado do momento {destaques._mmss(m['ini'])}–{destaques._mmss(m['fim'])} "
                           f"de {f['nome']} (nota {m['nota']}: {'; '.join(m['motivos'])}).")
        projeto.salvar(novo)
        criados.append(novo["nome"])
    return {"criados": criados}


# ------------------------------------------------- transcricao da fonte + clipar por pedido
def _transcrever_fonte(nome, fid, progresso):
    p = projeto.carregar(nome)
    pal = pedido.transcrever_fonte(projeto.pasta(nome), _fonte_ou_404(p, fid), progresso=progresso)
    return {"palavras": len(pal)}


@router.post("/api/projetos/{nome}/fontes/{fid}/transcrever")
def fonte_transcrever(nome: str, fid: str):
    f = _fonte_ou_404(_carregar(nome), fid)
    if not f["info"].get("audio"):
        raise HTTPException(400, "este vídeo não tem áudio para transcrever")
    return tarefas.iniciar("transcricao", _transcrever_fonte, nome, fid)


@router.get("/api/projetos/{nome}/fontes/{fid}/transcricao")
def fonte_transcricao(nome: str, fid: str):
    f = _fonte_ou_404(_carregar(nome), fid)
    return {"palavras": pedido.ler_transcricao(projeto.pasta(nome), f)}


class PedidoClipe(BaseModel):
    texto: str
    duracao: float = 20.0
    quantidade: int = 5
    modo: str = "local"          # local (busca na fala) | ia (provedor ativo, so texto)


def _validar_pedido(p, fid, dados):
    f = _fonte_ou_404(p, fid)
    if not 2 <= len(dados.texto.strip()) <= 500:
        raise HTTPException(400, "descreva o momento (2 a 500 caracteres)")
    if dados.modo not in ("local", "ia"):
        raise HTTPException(400, "modo inválido")
    dur = _f(dados.duracao, "duracao", 5, min(600, max(5, f["info"]["dur"])))
    return f, dur, int(_f(dados.quantidade, "quantidade", 1, 20))


def _guardar_lista(nome, fid, lista, duracao, **extra):
    p = projeto.carregar(nome)
    projeto.fonte(p, fid)["destaques"] = {"duracao": duracao, "lista": lista, **extra}
    projeto.salvar(p)
    return p


def _pedido_ia_req(nome, f, texto, dur, qtd):
    pal = pedido.ler_transcricao(projeto.pasta(nome), f) or []
    medidos = destaques.momentos(_sinais(nome, f), _cortes(f), f["info"]["dur"], dur, 10)
    return {"sistema": assistente.SISTEMA, "prompt": pedido.prompt_ia(texto, f, pal, medidos, dur, qtd),
            "schema": pedido.SCHEMA_IA}


def _pedido_ia(nome, fid, texto, dur, qtd, progresso):
    p = projeto.carregar(nome)
    f = _fonte_ou_404(p, fid)
    progresso(0.05, "preparando o texto (transcrição + momentos medidos)")
    r = assistente.enviar(p, "pedido", _pedido_ia_req(nome, f, texto, dur, qtd), progresso)
    lista = pedido.validar_ia(r["dados"], f["info"]["dur"], dur)
    obs = str((r["dados"] or {}).get("observacao") or "")[:500]
    _guardar_lista(nome, fid, lista, dur, pedido=texto, origem=r["origem"], observacao=obs)
    return {"quantidade": len(lista), "observacao": obs}


@router.post("/api/projetos/{nome}/fontes/{fid}/pedido")
def fonte_pedido(nome: str, fid: str, dados: PedidoClipe):
    p = _carregar(nome)
    f, dur, qtd = _validar_pedido(p, fid, dados)
    if dados.modo == "ia":
        return tarefas.iniciar("ia", _pedido_ia, nome, fid, dados.texto.strip(), dur, qtd, pesada=False)
    pal = pedido.ler_transcricao(projeto.pasta(nome), f)
    if pal is None:
        raise HTTPException(400, "transcreva a fala do vídeo primeiro (botão “Transcrever fala”)")
    try:
        lista = pedido.buscar(pal, dados.texto, f["info"]["dur"], dur, qtd, _cortes(f))
    except ValueError as e:
        raise HTTPException(400, str(e))
    p = _guardar_lista(nome, fid, lista, dur, pedido=dados.texto.strip(), origem="busca na fala (local)")
    return {**_estado(p), "encontrados": len(lista)}


@router.post("/api/projetos/{nome}/fontes/{fid}/pedido/previa")
def fonte_pedido_previa(nome: str, fid: str, dados: PedidoClipe):
    """Texto exato que iria para a IA (nada e enviado aqui)."""
    p = _carregar(nome)
    f, dur, qtd = _validar_pedido(p, fid, dados)
    req = _pedido_ia_req(nome, f, dados.texto.strip(), dur, qtd)
    return {"provedor": ia_config.carregar()["provedor_ativo"], "prompt": req["prompt"],
            "caracteres": len(req["sistema"]) + len(req["prompt"]), "envia_midia": False}


@router.get("/api/projetos/{nome}/transcricao_timeline")
def transcricao_timeline(nome: str):
    """Palavras faladas dentro de cada trecho da timeline (tempos DA FONTE), para editar pelo texto."""
    p = _carregar(nome)
    cache, out = {}, []
    for i, s in enumerate(p["segmentos"]):
        if s["fonte"] not in cache:
            try:
                cache[s["fonte"]] = pedido.ler_transcricao(projeto.pasta(nome), projeto.fonte(p, s["fonte"]))
            except KeyError:
                cache[s["fonte"]] = None
        pal = cache[s["fonte"]]
        out.append({"i": i, "fonte": s["fonte"], "ini": s["ini"], "fim": s["fim"], "transcrita": pal is not None,
                    "palavras": [w for w in pal or [] if s["ini"] <= w["start"] < s["fim"]]})
    return {"trechos": out}


@router.get("/api/projetos/{nome}/ritmo")
def ritmo(nome: str, minimo: float = 0.9):
    """Pausas longas na fala dos trechos (assistente de ritmo). So SUGERE: pausa depois de pergunta ou com acao na
    tela fica marcada como 'talvez manter' (expectativa/reacao). O corte deixa 0,15 s de respiro de cada lado."""
    import numpy as np
    p = _carregar(nome)
    minimo = _f(minimo, "minimo", 0.4, 5)
    trechos = transcricao_timeline(nome)["trechos"]
    sugestoes, sinais_cache, acc = [], {}, 0.0
    for t in trechos:
        pal = t["palavras"]
        for a, b in zip(pal, pal[1:]):
            gap = b["start"] - a["end"]
            if gap < minimo:
                continue
            ini, fim = round(a["end"] + 0.15, 3), round(b["start"] - 0.15, 3)
            if fim - ini < 0.3:
                continue
            motivo_manter = None
            if a["w"].rstrip().endswith("?"):
                motivo_manter = "vem depois de uma pergunta (expectativa)"
            else:
                try:
                    f = projeto.fonte(p, t["fonte"])
                    if f["id"] not in sinais_cache:
                        sinais_cache[f["id"]] = _sinais(nome, f)
                    sn = sinais_cache[f["id"]]
                    i0, i1 = int(ini / destaques.PASSO), max(int(fim / destaques.PASSO), int(ini / destaques.PASSO) + 1)
                    z = destaques._z(sn["movimento"]) + destaques._z(sn["impactos"])
                    if i1 <= len(z) and float(np.max(z[i0:i1])) > 1.5:
                        motivo_manter = "tem ação na tela durante a pausa (reação)"
                except (KeyError, OSError, ValueError):
                    pass
            sugestoes.append({"trecho": t["i"], "ini": ini, "fim": fim, "pausa_s": round(gap, 2),
                              "na_montagem_s": round(acc + a["end"] - t["ini"], 2), "depois_de": a["w"], "antes_de": b["w"],
                              "talvez_manter": motivo_manter})
        acc += t["fim"] - t["ini"]
    transcrito = any(t["transcrita"] for t in trechos)
    return {"sugestoes": sugestoes, "transcrito": transcrito,
            "economia_s": round(sum(s["fim"] - s["ini"] for s in sugestoes if not s["talvez_manter"]), 2)}
