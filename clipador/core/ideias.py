"""Banco de ideias + pontuação CPV (docs/cpv/03 §4.2).

Pontuação = Σ peso × nota/5 (0–100), SÓ depois dos portões eliminatórios. É instrumento de priorização, não
probabilidade de viralizar. Pesos fixados no documento antes de avaliar qualquer ideia; recalibrar só com dados
do próprio canal (Fase 10). Toda mudança fica no histórico da ideia.
"""
from . import canais, estudio

PESOS = {  # critério: (peso, nota 5, nota 0) — âncoras do documento 03
    "gancho": (15, "afirmação/pergunta concreta em < 2 s, com prova visual imediata", "precisa de contexto antes de interessar"),
    "originalidade": (15, "ângulo/fonte que ninguém usou no quadrado da grade", "repete vídeo existente"),
    "interesse": (15, "demanda observável alta e viva no quadrado", "nenhum sinal de demanda"),
    "atencao": (10, "escada de revelações até o fim", "tudo dito no começo"),
    "narrativa": (10, "conflito/curiosidade com resolução clara", "lista de fatos soltos"),
    "viabilidade": (10, "material próprio/livre disponível; < 2 h de produção", "depende de material indisponível"),
    "seguranca": (10, "nenhum item de risco na matriz 04", "risco médio em 2+ itens"),
    "nicho": (5, "centro do pilar editorial", "fora do canal"),
    "compartilhamento": (5, "'tenho que mandar isso para alguém'", "nada a comentar"),
    "economico": (5, "leva a vídeo longo/parceria/produto legítimo", "só views de baixo valor"),
}
PORTOES = {
    "direitos_viaveis": "Há material próprio, licenciado ou de domínio público suficiente",
    "politica_ok": "Nenhum risco alto na matriz de políticas (docs/cpv/04)",
    "fato_verificavel": "O fato central tem fonte confiável",
    "sem_persona_sensivel": "Não usa voz/persona sintética de especialista em saúde, direito, finanças ou política",
}
STATUS = ("nova", "pontuada", "aprovada", "descartada", "em_roteiro", "produzida")
FORMATOS = ("explicador", "serie", "pergunta", "demonstracao", "escala", "processo", "momento", "humor")


def _hist(ideia, acao, detalhe=""):
    ideia.setdefault("historico", []).append({"em": estudio.agora(), "acao": acao, "detalhe": str(detalhe)[:300]})


def _fonte(f):
    url = str((f or {}).get("url") or "").strip()
    if not url.startswith(("https://", "http://")):
        raise ValueError("cada fonte precisa de um link http(s)")
    return {"url": url[:500], "titulo": str(f.get("titulo") or "").strip()[:200],
            "acessado_em": str(f.get("acessado_em") or estudio.agora()[:10])[:10], "nota": str(f.get("nota") or "").strip()[:300]}


def pontuar(ideia):
    """(nota 0–100 ou None, motivo). None = reprovada em portão ou critérios faltando."""
    port = ideia.get("portoes") or {}
    reprovados = [k for k in PORTOES if port.get(k) is False]
    if reprovados:
        return None, "reprovada nos portões: " + ", ".join(reprovados)
    pendentes = [k for k in PORTOES if port.get(k) is not True]
    if pendentes:
        return None, "portões ainda não avaliados: " + ", ".join(pendentes)
    notas = ideia.get("notas") or {}
    faltando = [k for k in PESOS if k not in notas]
    if faltando:
        return None, "faltam notas: " + ", ".join(faltando)
    return round(sum(PESOS[k][0] * notas[k] / 5 for k in PESOS), 1), "ok"


def criar(dados):
    d = dados or {}
    canal = str(d.get("canal") or "")
    canais.obter(canal)                                    # canal tem de existir
    titulo = str(d.get("titulo") or "").strip()[:150]
    if not titulo:
        raise ValueError("a ideia precisa de um título provisório")
    formato = d.get("formato") or "explicador"
    if formato not in FORMATOS:
        raise ValueError(f"formato deve ser um de: {', '.join(FORMATOS)}")
    ideia = {"id": estudio.novo_id("ideia"), "canal": canal, "titulo": titulo, "formato": formato,
             "quadrado": str(d.get("quadrado") or "").strip()[:150], "justificativa": str(d.get("justificativa") or "").strip()[:1000],
             "fontes": [_fonte(f) for f in d.get("fontes") or []], "notas": {}, "portoes": {}, "nota": None,
             "status": "nova", "criada_em": estudio.agora()}
    _hist(ideia, "criada", titulo)
    return estudio.gravar("ideias", ideia)


def avaliar(id_, notas=None, portoes=None, quem="usuário"):
    """Grava notas 0–5 e/ou portões (True/False) e recalcula a pontuação."""
    ideia = estudio.ler("ideias", id_)
    for k, v in (notas or {}).items():
        if k not in PESOS:
            raise ValueError(f"critério desconhecido: {k}")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 5:
            raise ValueError(f"nota de '{k}' precisa ser de 0 a 5")
        ideia["notas"][k] = v
    for k, v in (portoes or {}).items():
        if k not in PORTOES or not isinstance(v, bool):
            raise ValueError(f"portão inválido: {k}")
        ideia["portoes"][k] = v
    ideia["nota"], motivo = pontuar(ideia)
    if ideia["status"] in ("nova", "pontuada"):
        ideia["status"] = "pontuada" if ideia["nota"] is not None else "nova"
    _hist(ideia, "avaliada", f"por {quem}: {ideia['nota'] if ideia['nota'] is not None else motivo}")
    return estudio.gravar("ideias", ideia)


def adicionar_fonte(id_, fonte):
    ideia = estudio.ler("ideias", id_)
    ideia["fontes"].append(_fonte(fonte))
    _hist(ideia, "fonte", fonte.get("url"))
    return estudio.gravar("ideias", ideia)


def mudar_status(id_, status, motivo=""):
    ideia = estudio.ler("ideias", id_)
    if status not in STATUS:
        raise ValueError(f"status deve ser um de: {', '.join(STATUS)}")
    if status == "aprovada":
        if ideia["nota"] is None:
            raise ValueError("só aprova ideia pontuada (portões aprovados e as 10 notas)")
        if not ideia["fontes"]:
            raise ValueError("só aprova ideia com pelo menos uma fonte registrada")
    ideia["status"] = status
    _hist(ideia, f"status: {status}", motivo)
    return estudio.gravar("ideias", ideia)


def listar(canal=None, status=None):
    out = [i for i in estudio.listar("ideias") if (not canal or i["canal"] == canal) and (not status or i["status"] == status)]
    return sorted(out, key=lambda i: -(i["nota"] or -1))


def obter(id_):
    return estudio.ler("ideias", id_)
