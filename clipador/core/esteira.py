"""Esteira rastreável (docs/cpv/03, Fase 8.4): Pesquisa → Ideia → Roteiro → Verificação factual → Direitos →
Narração → Montagem → Legendas → Controle de qualidade → Aprovação → Exportação → Publicação autorizada → Análise.

Cada etapa é DEDUZIDA do estado real do projeto (arquivos, aprovações, registros) — não de um "feito" marcado à
mão. Assim rodar de novo retoma de onde parou e nenhuma etapa é dada como pronta sem estar. A única etapa
marcada é a publicação, e só por comando explícito do usuário (nada publica sozinho). Trava contra execução
duplicada e log por etapa em projetos/<n>/esteira.log.jsonl (só texto de status; nunca chaves ou conteúdo de IA).
"""
import datetime as dt
import json
import os
import re

from . import conformidade, estudio, projeto, recursos, roteiros, verificador

ETAPAS = ("ideia", "roteiro", "verificacao_factual", "revisao_direitos", "narracao", "montagem", "legendas",
          "qc", "aprovacao", "exportacao", "publicacao_autorizada", "analise")
NOMES = {"ideia": "Ideia aprovada", "roteiro": "Roteiro aprovado", "verificacao_factual": "Fatos com fonte",
         "revisao_direitos": "Direitos revisados", "narracao": "Narração", "montagem": "Montagem", "legendas": "Legendas",
         "qc": "Controle de qualidade", "aprovacao": "RASCUNHO aprovado", "exportacao": "FINAL exportado",
         "publicacao_autorizada": "Publicação autorizada", "analise": "Resultados importados"}
TRAVA_MAX_S = 30 * 60
URL_VIDEO = re.compile(r"^https://(www\.)?(youtube\.com/(shorts/|watch\?v=)|youtu\.be/)([A-Za-z0-9_-]{11})")


def _roteiro(p):
    try:
        return roteiros.obter(p["roteiro_id"]) if p.get("roteiro_id") else None
    except (FileNotFoundError, ValueError):
        return None


def _cartoes(p):
    c = os.path.join(projeto.pasta(p["nome"]), "legenda_cartoes.json")
    if not os.path.isfile(c):
        return []
    with open(c, encoding="utf-8") as f:
        return [x for x in json.load(f) if x.get("palavras")]


def estado(p):
    """[{etapa, nome, ok, detalhe}] na ordem; 'atual' = primeira não concluída."""
    r = _roteiro(p)
    d = projeto.pasta(p["nome"])
    itens_qc = verificador.verificar_projeto(p) if p.get("segmentos") else []
    conf = [i for i in conformidade.direitos(p) if i["nivel"] == "aviso"]
    pub = p.get("publicacao_registro") or {}
    checks = {
        "ideia": (bool(r) and r.get("ideia") is not None, "projeto criado de um roteiro (python -m clipador roteiro projeto)" if not r else "ok"),
        "roteiro": (bool(r) and r["status"] == "aprovado", "aprove o roteiro" if r else "sem roteiro ligado"),
        "verificacao_factual": (bool(r) and bool(r["afirmacoes"]) and all(a["fonte"] for a in r["afirmacoes"]),
                                "liste os fatos do roteiro com o link de cada um"),
        "revisao_direitos": (bool(p["fontes"]) and not conf
                             and all(recursos.completar(f.get("direitos"))["origem"] != "nao_informado" for f in p["fontes"]),
                             "registre a origem/licença de cada vídeo (aba 1) e resolva os avisos de direitos"),
        "narracao": (bool(p.get("narracao")) and os.path.isfile(os.path.join(d, p["narracao"])), "grave a narração (aba 5)"),
        "montagem": (bool(p.get("segmentos")), "monte a timeline (python -m clipador montar ou aba 2)"),
        "legendas": (bool(_cartoes(p)) and p.get("legenda_base") in (None, projeto.base_legenda(p)),
                     "gere/atualize as legendas (python -m clipador finalizar)"),
        "qc": (bool(itens_qc) and not [i for i in itens_qc if i["nivel"] == "erro"] and bool(verificador.rascunho_atual(p)),
               "gere o RASCUNHO e resolva os erros do Verificar"),
        "aprovacao": (p["aprovacao"].get("aprovado_hash") == projeto.hash_conteudo(p), "assista e aprove o RASCUNHO (aba 7)"),
        "exportacao": (os.path.isdir(d) and any(f.startswith("FINAL_") and f.endswith(".mp4") for f in os.listdir(d)),
                       "gere o FINAL (aba 7)"),
        "publicacao_autorizada": (bool(pub.get("url")), "publique você mesmo e registre o link (python -m clipador esteira NOME --publicado URL)"),
        "analise": (bool(pub.get("video_id")) and _tem_metricas(pub.get("video_id")), "importe o CSV do YouTube Studio (python -m clipador metricas importar)"),
    }
    out, atual = [], None
    for e in ETAPAS:
        ok, detalhe = checks[e]
        if not ok and atual is None:
            atual = e
        out.append({"etapa": e, "nome": NOMES[e], "ok": bool(ok), "detalhe": "ok" if ok else detalhe})
    return {"etapas": out, "atual": atual}


def _tem_metricas(video_id):
    if not video_id:
        return False
    from . import metricas
    return metricas.ultimo(video_id) is not None


# ------------------------------------------------------------------ trava e log
def _trava(nome):
    return os.path.join(projeto.pasta(nome), ".esteira.lock")


def adquirir(nome, dono):
    """Trava contra duas execuções da esteira no mesmo projeto (trava velha de > 30 min é ignorada)."""
    c = _trava(nome)
    if os.path.isfile(c):
        try:
            with open(c, encoding="utf-8") as f:
                t = json.load(f)
            idade = (dt.datetime.now() - dt.datetime.fromisoformat(t["em"])).total_seconds()
            if idade < TRAVA_MAX_S:
                raise RuntimeError(f"a esteira deste projeto já está rodando ({t.get('dono')}, desde {t['em']})")
        except (ValueError, KeyError):
            pass
    os.makedirs(os.path.dirname(c), exist_ok=True)
    with open(c, "w", encoding="utf-8") as f:
        json.dump({"dono": str(dono)[:80], "em": estudio.agora()}, f)


def liberar(nome):
    c = _trava(nome)
    if os.path.isfile(c):
        os.remove(c)


def registrar(nome, etapa, acao, resultado):
    with open(os.path.join(projeto.pasta(nome), "esteira.log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"em": estudio.agora(), "etapa": etapa, "acao": str(acao)[:200], "resultado": str(resultado)[:300]},
                           ensure_ascii=False) + "\n")


def log(nome):
    c = os.path.join(projeto.pasta(nome), "esteira.log.jsonl")
    if not os.path.isfile(c):
        return []
    with open(c, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def marcar_publicado(nome, url):
    """O USUÁRIO publicou e informa o link (o Clipador nunca publica sozinho). Exige FINAL exportado."""
    m = URL_VIDEO.match(str(url or "").strip())
    if not m:
        raise ValueError("link do YouTube inválido (use youtube.com/shorts/ID, youtube.com/watch?v=ID ou youtu.be/ID)")
    p = projeto.carregar(nome)
    st = {e["etapa"]: e["ok"] for e in estado(p)["etapas"]}
    if not st["exportacao"]:
        raise ValueError("gere o FINAL antes de registrar a publicação")
    reg = {"url": url.strip(), "video_id": m.group(4), "registrado_em": estudio.agora()}
    projeto.alterar(nome, lambda q: q.update(publicacao_registro=reg))
    registrar(nome, "publicacao_autorizada", "publicado pelo usuário", reg["url"])
    return reg
