"""Canais (docs/cpv/05): perfil editorial que liga ideias, roteiros e projetos.

`monetizacao`: "normal" ou "sem_receita" (ex.: canal 4, GTA 6, até haver licença escrita da Take-Two).
`limite_dia`: teto de Shorts exportados por dia (V5/F5: qualidade > volume; produção em massa é spam).
"""
from . import estudio

STATUS = ("rascunho", "ativo", "pausado", "encerrado")
MONETIZACAO = ("normal", "sem_receita")
PADRAO = {"nome": "", "idioma": "pt-BR", "nicho": "", "subnicho": "", "publico": "", "proposta": "",
          "formatos": [], "pilares": [], "frequencia_semana": 3, "limite_dia": 1, "kit": None, "referencia": None,
          "status": "rascunho", "monetizacao": "normal", "notas": ""}


def validar(dados, atual=None):
    c = dict(atual or PADRAO)
    d = dados or {}
    for k in ("nome", "idioma", "nicho", "subnicho", "publico", "proposta", "notas"):
        if k in d:
            c[k] = str(d[k] or "").strip()[:500 if k in ("proposta", "notas", "publico") else 80]
    for k in ("formatos", "pilares"):
        if k in d:
            lista = d[k] if isinstance(d[k], list) else str(d[k]).split(",")
            c[k] = [str(x).strip()[:80] for x in lista if str(x).strip()][:12]
    for k, lo, hi in (("frequencia_semana", 0, 21), ("limite_dia", 1, 5)):
        if k in d:
            try:
                v = int(d[k])
            except (TypeError, ValueError):
                raise ValueError(f"{k} precisa ser um número inteiro")
            if not lo <= v <= hi:
                raise ValueError(f"{k} precisa estar entre {lo} e {hi}")
            c[k] = v
    for k, opcoes in (("status", STATUS), ("monetizacao", MONETIZACAO)):
        if k in d:
            if d[k] not in opcoes:
                raise ValueError(f"{k} deve ser um de: {', '.join(opcoes)}")
            c[k] = d[k]
    for k in ("kit", "referencia"):
        if k in d:
            c[k] = (str(d[k]).strip()[:80] or None) if d[k] else None
    if not c["nome"]:
        raise ValueError("o canal precisa de um nome")
    return c


def criar(dados):
    c = validar(dados)
    c["id"] = estudio.slug(c["nome"], "canal")
    if estudio.existe("canais", c["id"]):
        raise FileExistsError(f"canal '{c['id']}' já existe")
    c["criado_em"] = estudio.agora()
    return estudio.gravar("canais", c)


def editar(id_, dados):
    atual = estudio.ler("canais", id_)
    novo = validar(dados, atual)
    novo["id"], novo["criado_em"] = atual["id"], atual.get("criado_em")
    return estudio.gravar("canais", novo)


def listar():
    return estudio.listar("canais")


def obter(id_):
    return estudio.ler("canais", id_)


# Os quatro canais da estratégia (docs/cpv/05), como RASCUNHO para o usuário revisar.
SEMENTES = [
    {"nome": "Mapa Esquisito", "nicho": "geografia", "subnicho": "fronteiras, escala e lugares estranhos",
     "publico": "Brasil/Portugal, 14–44", "proposta": "Cada vídeo traz um mapa próprio (dados livres) e uma fonte citada.",
     "formatos": ["explicador", "escala", "serie"], "pilares": ["fronteiras estranhas", "escala", "lugares improváveis", "por que o mapa é assim"]},
    {"nome": "História Esquisita", "nicho": "história", "subnicho": "episódios curiosos do Brasil e do mundo",
     "publico": "Brasil/Portugal, 18–54", "proposta": "Fontes primárias e um ângulo com posição, não resumo de enciclopédia.",
     "formatos": ["serie", "explicador"], "pilares": ["eventos bizarros", "mitos desmontados", "personagens esquecidos", "o mapa do episódio"]},
    {"nome": "Como o Espaço Funciona", "nicho": "ciência", "subnicho": "espaço e fenômenos do dia a dia",
     "publico": "Brasil/Portugal, 13–44 (decidir COPPA corretamente)", "proposta": "Imagem real (acervo público) + explicação em escada + demonstração.",
     "formatos": ["pergunta", "escala", "demonstracao"], "pilares": ["escala do universo", "como funciona no espaço", "fenômenos na Terra", "o que a NASA viu"]},
    {"nome": "GTA 6 Comparado", "nicho": "games", "subnicho": "GTA 6: comparações e detalhes",
     "publico": "Brasil, 14–34", "proposta": "Comparações A×B e análise narrada; só uso de fã até a licença da Take-Two.",
     "formatos": ["explicador", "momento"], "pilares": ["comparações", "detalhes", "gameplay próprio"],
     "monetizacao": "sem_receita", "notas": "Aguardando licença da Take-Two (docs/cpv/rascunho-email-take-two.md). Sem monetização até resposta escrita."},
]


def semear():
    """Cria os canais da estratégia que ainda não existem (não altera os que já existem)."""
    criados = []
    for s in SEMENTES:
        if not estudio.existe("canais", estudio.slug(s["nome"])):
            criados.append(criar(s))
    return criados
