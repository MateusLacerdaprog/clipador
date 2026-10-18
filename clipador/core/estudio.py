"""Pasta de dados do estúdio (canais, ideias, roteiros, métricas, experimentos): estudio/<tipo>/<id>.json.

Dados do usuário (estratégia dos canais): fora do Git, como projetos/. Gravação atômica; id = slug.
Testes usam CLIPADOR_ESTUDIO para não tocar nos dados reais.
"""
import datetime as dt
import json
import os
import re
import threading
import unicodedata
import uuid

from . import projeto

RAIZ = os.environ.get("CLIPADOR_ESTUDIO") or os.path.join(os.path.dirname(projeto.RAIZ), "estudio")
TIPOS = ("canais", "ideias", "roteiros", "metricas", "experimentos", "custos")
_TRAVA = threading.RLock()


def agora():
    return dt.datetime.now().isoformat(timespec="seconds")


def slug(texto, padrao="item"):
    s = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or padrao


def novo_id(prefixo):
    return f"{prefixo}-{uuid.uuid4().hex[:8]}"


def _pasta(tipo):
    if tipo not in TIPOS:
        raise ValueError(f"tipo desconhecido: {tipo}")
    return os.path.join(RAIZ, tipo)


def _arquivo(tipo, id_):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", str(id_ or "")):
        raise ValueError("id inválido")
    return os.path.join(_pasta(tipo), f"{id_}.json")


def existe(tipo, id_):
    try:
        return os.path.isfile(_arquivo(tipo, id_))
    except ValueError:
        return False


def ler(tipo, id_):
    c = _arquivo(tipo, id_)
    if not os.path.isfile(c):
        raise FileNotFoundError(f"{tipo[:-1] if tipo.endswith('s') else tipo} '{id_}' não existe")
    with open(c, encoding="utf-8") as f:
        return json.load(f)


def gravar(tipo, obj):
    c = _arquivo(tipo, obj["id"])
    os.makedirs(os.path.dirname(c), exist_ok=True)
    tmp = f"{c}.{os.getpid()}.{threading.get_ident()}.tmp"
    with _TRAVA:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, c)
    return obj


def listar(tipo):
    d = _pasta(tipo)
    if not os.path.isdir(d):
        return []
    out = []
    for n in sorted(os.listdir(d)):
        if n.endswith(".json"):
            with open(os.path.join(d, n), encoding="utf-8") as f:
                out.append(json.load(f))
    return out


def apagar(tipo, id_):
    c = _arquivo(tipo, id_)
    if os.path.isfile(c):
        os.remove(c)
