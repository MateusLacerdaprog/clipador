"""Kit do canal: estilo salvo (legenda, layout, marca d'agua, referencia, mixagem, zoom padrao) aplicado a
projetos, e a marca d'agua (logo) desenhada no render.

Biblioteca de estilos: o kit pode ser criado em branco, duplicado, renomeado e editado sem projeto aberto.
Kits em kits/<id>.json, logos em kits/logos/ e presets de zoom do usuario em kits/zoom/presets.json (core/zoom.py),
ao lado de projetos/ e compartilhados entre projetos.
"""
import copy
import json
import os

from . import projeto, zoom

PASTA = os.path.join(os.path.dirname(projeto.RAIZ), "kits")
PASTA_LOGOS = os.path.join(PASTA, "logos")
LOGO_EXT = (".png", ".webp", ".jpg", ".jpeg")
POSICOES = ("sup_esq", "sup_dir", "inf_esq", "inf_dir")
MARCA_PADRAO = {"arquivo": None, "pos": "sup_dir", "tamanho": 0.14, "opacidade": 0.85}


def caminho_logo(nome):
    base = os.path.basename(str(nome or "").replace("\\", "/"))
    if not base or base in (".", "..") or not base.lower().endswith(LOGO_EXT):
        raise ValueError("logo inválido: use PNG (com fundo transparente), WEBP ou JPG")
    return os.path.join(PASTA_LOGOS, base)


def logos():
    if not os.path.isdir(PASTA_LOGOS):
        return []
    return sorted(f for f in os.listdir(PASTA_LOGOS) if f.lower().endswith(LOGO_EXT))


def validar_marca(m):
    m = {**MARCA_PADRAO, **(m or {})}
    if m["arquivo"]:
        if not os.path.isfile(caminho_logo(m["arquivo"])):
            raise ValueError("o logo escolhido não está em kits/logos")
        m["arquivo"] = os.path.basename(m["arquivo"])
    else:
        m["arquivo"] = None
    if m["pos"] not in POSICOES:
        raise ValueError("posição do logo inválida")
    try:
        m["tamanho"] = float(m["tamanho"])
        m["opacidade"] = float(m["opacidade"])
    except (TypeError, ValueError):
        raise ValueError("tamanho/opacidade do logo inválidos")
    if not (0.04 <= m["tamanho"] <= 0.4 and 0.1 <= m["opacidade"] <= 1):
        raise ValueError("logo: tamanho de 4% a 40% da largura e opacidade de 10% a 100%")
    return {k: m[k] for k in MARCA_PADRAO}


def filtro_marca(marca, entrada_logo, rotulo_in, rotulo_out, W, H):
    """Logo sobre o video. Curto: cantos dentro da area segura (topo >= 288 px, base <= 1520, direita livre dos
    botoes so no topo/rodape). Longo: margem de 40 px."""
    larg = int(W * marca["tamanho"]) // 2 * 2
    if H > W:   # 1080x1920
        x = {"esq": 60, "dir": f"{W - 60}-w"}
        y = {"sup": 290, "inf": f"1520-h"}
    else:
        x = {"esq": 40, "dir": f"{W - 40}-w"}
        y = {"sup": 40, "inf": f"{H - 40}-h"}
    v, h = marca["pos"].split("_")[0], marca["pos"].split("_")[1]
    return (f"[{entrada_logo}:v]scale={larg}:-1,format=rgba,colorchannelmixer=aa={marca['opacidade']:.2f}[logo];"
            f"[{rotulo_in}][logo]overlay=x={x[h]}:y={y[v]}:format=auto:eof_action=repeat[{rotulo_out}]")


# ------------------------------------------------------------------ kits
CAMPOS = ("layout", "legenda", "marca", "referencia")


def _id(nome):
    return projeto.slug(nome)


def _caminho(kid):
    return os.path.join(PASTA, _id(kid) + ".json")


def existe(kid):
    return os.path.isfile(_caminho(kid))


def _gravar(k):
    os.makedirs(PASTA, exist_ok=True)
    c = _caminho(k["id"])
    with open(c + ".tmp", "w", encoding="utf-8") as f:
        json.dump(k, f, ensure_ascii=False, indent=1)
    os.replace(c + ".tmp", c)
    return k


def _id_livre(nome):
    """Id novo que nao sobrescreve outro kit: meu-canal, meu-canal-2..."""
    base, n = _id(nome), 2
    kid = base
    while existe(kid):
        kid, n = f"{base}-{n}", n + 1
    return kid


def listar():
    if not os.path.isdir(PASTA):
        return []
    out = []
    for f in sorted(os.listdir(PASTA)):
        if f.endswith(".json"):
            try:
                out.append(carregar(f[:-5]))
            except (OSError, ValueError):
                continue
    return out


def carregar(kid):
    with open(_caminho(kid), encoding="utf-8") as f:
        k = json.load(f)
    if not isinstance(k, dict) or not k.get("id") or not k.get("nome"):
        raise ValueError("arquivo em kits/ não é um kit")
    k.setdefault("zoom_padrao", None)         # kits antigos (antes da biblioteca de estilos)
    return k


def salvar_de_projeto(nome, p):
    """Guarda o estilo do projeto. Com o nome de um kit que ja existe, atualiza esse kit (o zoom padrao fica)."""
    kid = _id(nome)
    anterior = carregar(kid) if existe(kid) else {}
    k = {"id": kid, "nome": nome.strip()[:60], **{c: copy.deepcopy(p.get(c)) for c in CAMPOS},
         "gancho_ate": p["gancho"].get("ate", 3.0), "mix": copy.deepcopy((p.get("audio") or {}).get("mix")),
         "zoom_padrao": anterior.get("zoom_padrao")}
    return _gravar(k)


def novo(nome):
    """Kit em branco (estilo padrao de um projeto novo), para montar sem precisar de projeto."""
    P = projeto.PADRAO
    k = {"id": _id_livre(nome), "nome": nome.strip()[:60], "layout": P["layout"], "legenda": copy.deepcopy(P["legenda"]),
         "marca": copy.deepcopy(MARCA_PADRAO), "referencia": None, "gancho_ate": P["gancho"]["ate"], "mix": None,
         "zoom_padrao": None}
    return _gravar(k)


def duplicar(kid, nome=None):
    k = copy.deepcopy(carregar(kid))
    nome = (nome or "").strip()[:60] or f"{k['nome']} (cópia)"[:60]
    k["id"], k["nome"] = _id_livre(nome), nome
    return _gravar(k)


def atualizar(kid, mudancas):
    """Aplica mudancas JA VALIDADAS (app.py) e grava. Trocar o nome troca o arquivo (id = nome sem acento);
    se ja houver outro kit com esse nome, recusa (FileExistsError) em vez de sobrescrever."""
    k = carregar(kid)
    antigo = k["id"]
    for c in ("layout", "legenda", "marca", "gancho_ate", "zoom_padrao", "referencia"):
        if c in mudancas:
            k[c] = copy.deepcopy(mudancas[c])
    if "nome" in mudancas:
        k["nome"] = mudancas["nome"].strip()[:60]
        novo_id = _id(k["nome"])
        if novo_id != antigo:
            if existe(novo_id):
                raise FileExistsError(f"já existe um kit chamado “{k['nome']}”")
            k["id"] = novo_id
    _gravar(k)
    if k["id"] != antigo:
        os.remove(_caminho(antigo))
    return k


def aplicar_zoom(p, k):
    """Zoom padrao do kit nos trechos SEM zoom (sem zoom_fx e sem o zoom antigo). Devolve os indices mudados."""
    fx = zoom.validar(k.get("zoom_padrao"))
    if not fx:
        return []
    mudou = []
    for i, s in enumerate(p["segmentos"]):
        if s.get("zoom_fx") or float(s.get("zoom", 1.0) or 1.0) > 1.001:
            continue
        s["zoom_fx"], s["zoom"] = copy.deepcopy(fx), 1.0
        mudou.append(i)
    return mudou


def aplicar(p, k):
    """Copia o estilo do kit para o projeto. Video longo mantem o layout horizontal."""
    for c in CAMPOS:
        if k.get(c) is not None and not (c == "layout" and p.get("tipo") == "longo"):
            p[c] = copy.deepcopy(k[c])
    if k.get("gancho_ate") is not None:
        p["gancho"]["ate"] = k["gancho_ate"]
    if k.get("mix") and p.get("audio"):
        p["audio"]["mix"] = copy.deepcopy(k["mix"])
    return p


def remover(kid):
    c = _caminho(kid)
    if not os.path.isfile(c):
        raise FileNotFoundError("kit não existe")
    os.remove(c)
