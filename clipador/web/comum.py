"""Utilidades compartilhadas pelas rotas: carregar projeto, estado para a interface, validacoes de entrada."""
import json
import os
import re

from fastapi import HTTPException

from ..core import audio, destaques, legendas, midia, projeto, react, zoom

ESTATICO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")
HOSTS_LOCAIS = {"127.0.0.1", "localhost", "::1"}
MODOS_AUDIO_TRECHO = ("padrao", "volume", "mudo")
MAX_CONGELADO = 10.0       # quadro congelado mais longo que isso vira tela parada demais


# ------------------------------------------------------------------ utilidades
def _carregar(nome):
    try:
        return projeto.carregar(nome)
    except FileNotFoundError:
        raise HTTPException(404, f"projeto '{nome}' nao existe")


def _cartoes_path(nome):
    return os.path.join(projeto.pasta(nome), "legenda_cartoes.json")


def _cartoes_anterior(nome):
    return os.path.join(projeto.pasta(nome), "legenda_cartoes.anterior.json")


def _ler_cartoes(nome):
    c = _cartoes_path(nome)
    if not os.path.isfile(c):
        return []
    with open(c, encoding="utf-8") as f:
        return json.load(f)


def _gravar_cartoes(nome, cartoes):
    tmp = _cartoes_path(nome) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cartoes, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _cartoes_path(nome))


def _nome_livre(pasta, base):
    """Nao sobrescreve arquivo existente: video.mp4 -> video (2).mp4."""
    raiz, ext = os.path.splitext(base)
    nome, k = base, 2
    while os.path.exists(os.path.join(pasta, nome)):
        nome, k = f"{raiz} ({k}){ext}", k + 1
    return nome


def _estado(p):
    """Projeto + informacoes derivadas que a interface precisa."""
    d = projeto.pasta(p["nome"])
    h = projeto.hash_conteudo(p)
    ap = p["aprovacao"]
    saidas = sorted((f for f in os.listdir(d) if f.startswith(("RASCUNHO_", "FINAL_")) and f.endswith(".mp4")
                     and ".tmp." not in f), key=lambda f: -os.path.getmtime(os.path.join(d, f)))
    faltando = [f"{t}/{n}" for t, n in projeto.arquivos_de_audio(p)
                if not os.path.isfile(projeto.caminho_biblioteca(t, n))]
    faltando += [f["caminho"] for f in p["fontes"] if not os.path.isfile(f["caminho"])]
    cart = _ler_cartoes(p["nome"])
    fim_video = projeto.duracao_timeline(p)
    # mesmos cartoes que o render usa: sem narracao (ou desligada) so os provisorios do roteiro entram no video
    narr = audio.migrar(p["audio"])["narracao"]
    usa_fala = projeto.relogio_da_montagem(p) or (p.get("narracao") and narr["ativo"])
    desl = 0.0 if projeto.relogio_da_montagem(p) else narr["deslocamento"]
    fim_leg = max([c["palavras"][-1]["end"] + (0.0 if c.get("provisorio") else desl) for c in cart
                   if c.get("palavras") and (usa_fala or c.get("provisorio"))] or [0.0])
    return {
        **p,
        "duracao": round(projeto.duracao_timeline(p), 2),
        "narracao_dur": round(midia.duracao(os.path.join(d, p["narracao"])), 2) if p.get("narracao") else 0,
        "tem_proxy": os.path.isfile(os.path.join(d, "proxy.mp4")),
        "proxy_versao": int(os.path.getmtime(os.path.join(d, "proxy.mp4"))) if os.path.isfile(os.path.join(d, "proxy.mp4")) else None,
        "proxy_atual": os.path.isfile(os.path.join(d, "proxy.mp4")) and p.get("proxy_hash") == projeto.hash_previa(p),
        "n_cartoes": len(cart),
        # a montagem (audio do video) ou a narracao mudou depois da transcricao: oferecer "Atualizar legendas"
        "legendas_desatualizadas": bool(cart) and bool(p.get("legenda_base"))
                                   and p["legenda_base"] != projeto.base_legenda(p),
        "legendas_passam": round(max(0.0, fim_leg - fim_video), 2) if cart and fim_video else 0,
        "tem_legenda_anterior": os.path.isfile(_cartoes_anterior(p["nome"])),
        # legenda de narracao num projeto sem narracao (ou com ela desligada) nao entra no video
        "legendas_invisiveis": bool([c for c in cart if c.get("palavras") and not c.get("provisorio")]) and not usa_fala,
        "desloc_legenda": desl,                    # video = cartao + desl (a interface converte os tempos)
        "saidas": saidas,
        "arquivos_faltando": faltando,
        "react_extra": react.estado_extra(p),
        "rascunho_atual": ap.get("rascunho_hash") == h,
        "aprovado_atual": ap.get("aprovado_hash") == h,
    }


def _f(v, campo, lo=None, hi=None):
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise HTTPException(400, f"valor invalido em '{campo}'")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise HTTPException(400, f"'{campo}' fora do limite ({lo} a {hi})")
    return v


def _validar_legenda(L):
    if L.get("estilo") not in legendas.ESTILOS:
        raise HTTPException(400, "estilo de legenda invalido")
    out = {"estilo": L["estilo"], "maiusculas": bool(L.get("maiusculas")),
           "pos_y": None if L.get("pos_y") in (None, "") else int(_f(L["pos_y"], "pos_y", 100, 1800))}
    if L.get("plataforma") not in (None, "", *legendas.PLATAFORMAS):
        raise HTTPException(400, "plataforma invalida")
    out["plataforma"] = L.get("plataforma") or None
    if L.get("fonte") not in (None, "", *legendas.FONTES):
        raise HTTPException(400, "fonte nao disponivel")
    out["fonte"] = L.get("fonte") or None
    for k, lo, hi in (("tamanho", 30, 200), ("contorno", 0, 20), ("sombra", 0, 10)):
        out[k] = None if L.get(k) in (None, "") else int(_f(L[k], k, lo, hi))
    for k in ("cor", "destaque"):
        v = L.get(k)
        if v and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(v)):
            raise HTTPException(400, f"cor invalida em '{k}' (use #RRGGBB)")
        out[k] = v or None
    if L.get("animacao") not in (None, "", *legendas.ANIMACOES):
        raise HTTPException(400, "animacao invalida")
    out["animacao"] = L.get("animacao") or None
    return out


def _validar_react(atual, novo, tipo):
    R = react.completar(atual)
    n = novo or {}
    if "modo" in n:
        if n["modo"] not in react.MODOS:
            raise HTTPException(400, "modo de react invalido")
        R["modo"] = n["modo"]
    if R["modo"] == "dividido" and tipo == "longo":
        raise HTTPException(400, "a tela dividida só existe para vídeos curtos (use o modo janela no vídeo longo)")
    for k in ("espelhar",):
        if k in n:
            R[k] = bool(n[k])
    if "deslocamento" in n:
        R["deslocamento"] = _f(n["deslocamento"], "deslocamento", -30, 30)
    if "janela" in n:
        J = n["janela"] or {}
        if J.get("forma", R["janela"]["forma"]) not in react.FORMAS:
            raise HTTPException(400, "forma da janela invalida")
        R["janela"] = {"x": _f(J.get("x", R["janela"]["x"]), "x", 0, 1), "y": _f(J.get("y", R["janela"]["y"]), "y", 0, 1),
                       "w": _f(J.get("w", R["janela"]["w"]), "w", 0.1, 1),
                       "forma": J.get("forma", R["janela"]["forma"]), "borda": bool(J.get("borda", R["janela"]["borda"]))}
    if "chroma" in n:
        C = n["chroma"] or {}
        cor = C.get("cor", R["chroma"]["cor"])
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(cor)):
            raise HTTPException(400, "cor do chroma invalida (use #RRGGBB)")
        R["chroma"] = {"ativo": bool(C.get("ativo", R["chroma"]["ativo"])), "cor": cor,
                       "similaridade": _f(C.get("similaridade", R["chroma"]["similaridade"]), "similaridade", 0.01, 0.6),
                       "mistura": _f(C.get("mistura", R["chroma"]["mistura"]), "mistura", 0, 0.5),
                       "despill": bool(C.get("despill", R["chroma"]["despill"]))}
    if "recorte_ia" in n:
        I, A = n["recorte_ia"] or {}, R["recorte_ia"]
        R["recorte_ia"] = {**A, "ativo": bool(I.get("ativo", A["ativo"])),
                           "limiar": _f(I.get("limiar", A["limiar"]), "limiar", 0.2, 0.8),
                           "borda": _f(I.get("borda", A["borda"]), "borda", 0, 1),
                           "estabilidade": _f(I.get("estabilidade", A["estabilidade"]), "estabilidade", 0, 0.8)}
    if "recorte" in n:
        C, A = n["recorte"] or {}, R["recorte"]
        R["recorte"] = {"x": _f(C.get("x", A["x"]), "x", 0, 1), "y": _f(C.get("y", A["y"]), "y", 0, 1),
                        "w": _f(C.get("w", A["w"]), "w", 0.15, 1)}
    if "ativo" in n:
        R["ativo"] = bool(n["ativo"]) and bool(R["arquivo"])
    if R["modo"] == "dividido":
        R["chroma"]["ativo"] = False            # tela dividida e opaca: recorte nao se aplica
        R["recorte_ia"]["ativo"] = False
    return R


AUDIO_COMPARACAO = ("a", "b", "ambos")


def _validar_comparacao(p, novo):
    """Video A (em cima) e B (embaixo) padrao, rotulos, som e linha divisoria do layout comparacao."""
    ids = {f["id"] for f in p["fontes"]}
    C = {**projeto.PADRAO["comparacao"], **(p.get("comparacao") or {}), **(novo or {})}
    for k in ("fonte_a", "fonte_b"):
        if C[k] in ("", None):
            C[k] = None
        elif C[k] not in ids:
            raise HTTPException(400, f"comparação: o vídeo {k[-1].upper()} não está nas fontes do projeto")
    if C["audio"] not in AUDIO_COMPARACAO:
        raise HTTPException(400, "comparação: som inválido (a, b ou ambos)")
    return {"fonte_a": C["fonte_a"], "fonte_b": C["fonte_b"], "rotulo_a": str(C["rotulo_a"] or "")[:30],
            "rotulo_b": str(C["rotulo_b"] or "")[:30], "audio": C["audio"], "divisoria": bool(C["divisoria"])}


def _validar_segmentos(p, segs):
    ids = {f["id"]: f for f in p["fontes"]}
    out = []
    for i, s in enumerate(segs):
        if s.get("fonte") not in ids:
            raise HTTPException(400, f"trecho {i + 1}: fonte inexistente")
        dur_f = ids[s["fonte"]]["info"]["dur"]
        congelado = s.get("congelado") is True       # quadro parado: `fim - ini` e so a duracao (pode passar da fonte)
        ini = _f(s.get("ini"), "ini", 0, dur_f)
        fim = _f(s.get("fim"), "fim", 0, ini + MAX_CONGELADO if congelado else dur_f + 0.05)
        if fim - ini < 0.1:
            raise HTTPException(400, f"trecho {i + 1}: o fim precisa ser depois do inicio")
        n = {"id": str(s.get("id") or projeto.novo_id())[:16], "fonte": s["fonte"], "ini": round(ini, 3),
             "fim": round(fim, 3), "foco_x": _f(s.get("foco_x", 0.5), "foco_x", 0, 1),
             "zoom": _f(s.get("zoom", 1.0), "zoom", 1, 3)}
        if s.get("fonte_b"):
            if s["fonte_b"] not in ids:
                raise HTTPException(400, f"trecho {i + 1}: fonte B inexistente")
            n["fonte_b"] = s["fonte_b"]
        if s.get("ini_b") is not None:
            n["ini_b"] = _f(s["ini_b"], "ini_b", 0)
        if p.get("layout") == "comparacao" and p.get("tipo", "curto") != "longo":
            C = p.get("comparacao") or {}
            if not n.get("fonte_b") and C.get("fonte_b") in ids:          # trecho novo ja entra com o video B
                n["fonte_b"] = C["fonte_b"]
            fb = ids[n.get("fonte_b") or s["fonte"]]
            dur_b = fb["info"]["dur"]
            if n.get("ini_b") is None:                                   # mesmo instante, cabendo no video B
                n["ini_b"] = round(max(0.0, min(ini, dur_b - (fim - ini))), 3)
            if n["ini_b"] + (fim - ini) > dur_b + 0.05:
                raise HTTPException(400, f"trecho {i + 1}: o vídeo B ({fb['nome']}) acaba em {dur_b:.1f} s; "
                                         f"comece o B mais cedo ou encurte o trecho")
        if s.get("foco_x_b") is not None:
            n["foco_x_b"] = _f(s["foco_x_b"], "foco_x_b", 0, 1)
        for k in ("rotulo_a", "rotulo_b"):
            if s.get(k):
                n[k] = str(s[k])[:30]
        if s.get("zoom_fx"):
            try:
                fx = zoom.validar(s["zoom_fx"])
            except ValueError as e:
                raise HTTPException(400, f"trecho {i + 1}: {e}")
            if fx:
                n["zoom_fx"] = fx
        if s.get("rotulo"):            # capitulo (longo) ou texto do ranking (compilado)
            n["rotulo"] = str(s["rotulo"])[:60]
        if s.get("loop") is True:      # repeticao do comeco no fim (timeline.fechar_loop): fora do ranking
            n["loop"] = True
        if congelado:
            n["congelado"] = True
        a = s.get("audio")
        if a:
            modo = a.get("modo", "padrao")
            if modo not in MODOS_AUDIO_TRECHO:
                raise HTTPException(400, f"trecho {i + 1}: modo de audio invalido")
            n["audio"] = {"modo": modo, "db": _f(a.get("db", 0), "db", -60, 12)}
        out.append(n)
    return out


def _fonte_ou_404(p, fid):
    try:
        f = projeto.fonte(p, fid)
    except KeyError:
        raise HTTPException(404, "fonte nao existe")
    if not os.path.isfile(f["caminho"]):
        raise HTTPException(400, "o arquivo de video foi movido ou apagado")
    return f


def _sinais(nome, f, progresso=lambda *a: None):
    cache = os.path.join(projeto.pasta(nome), "cache", f["id"], "sinais.npz")
    return destaques.sinais(f["caminho"], f["info"], cache, progresso)
