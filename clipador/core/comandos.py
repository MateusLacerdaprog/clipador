"""Command Center: catalogo de ACOES (como ferramentas MCP) + interpretacao de comandos em portugues.

Separacao: interpretar (texto -> lista de acoes com parametros) NAO executa nada. A execucao fica na API
(app.py, _executar_acao), que so conhece as acoes deste catalogo e valida cada parametro. A IA (opcional) tambem
so pode escolher acoes daqui: nunca roda codigo.
"""
import re
import unicodedata

# acao -> descricao (mostrada no plano e enviada a IA), parametros aceitos, se demora, se sobrescreve algo
ACOES = {
    "legendas.gerar": {"desc": "Transcrever a fala e gerar as legendas", "params": {"origem": ["auto", "narracao", "video"]},
                       "demorada": True, "sobrescreve": "as correções feitas nos cartões de legenda"},
    "legendas.destacar": {"desc": "Destacar as palavras importantes das legendas (números, siglas, nomes)", "params": {}},
    "momentos.achar": {"desc": "Encontrar os momentos mais interessantes do vídeo-fonte",
                       "params": {"duracao": "número de segundos (5-600)", "quantidade": "1-20"}, "demorada": True},
    "momentos.usar": {"desc": "Montar a timeline com o melhor momento encontrado", "params": {"indice": "0 = o melhor"},
                      "sobrescreve": "a timeline atual (dá para desfazer)"},
    "zoom.aplicar": {"desc": "Aplicar zoom num trecho", "params": {"preset": ["destaque", "impacto", "reacao", "lento"],
                                                                   "alvo": ["selecionado", "todos"]}},
    "zoom.remover": {"desc": "Tirar o zoom", "params": {"alvo": ["selecionado", "todos"]}},
    "zoom.picos": {"desc": "Zoom de impacto só nos trechos com pico de ação", "params": {}},
    "foco.auto": {"desc": "Reenquadrar cada trecho para onde está a ação", "params": {}},
    "timeline.loop": {"desc": "Fechar o loop: repetir o começo no fim para o replay emendar sem corte", "params": {}},
    "publicacao.verificar": {"desc": "Conferir o texto de publicação de cada rede (limites, palavra-chave, declarações)",
                             "params": {}},
    "shorts.criar": {"desc": "Criar uma versão vertical (Shorts/TikTok/Reels) num projeto novo", "params": {}},
    "legendas.plataforma": {"desc": "Aplicar o visual de legenda de uma plataforma", "params": {"plataforma": ["shorts", "tiktok", "reels"]}},
    "react.recorte": {"desc": "Colocar o criador recortado sobre o gameplay (fundo virtual)", "params": {}},
    "previa.gerar": {"desc": "Gerar/atualizar a prévia da montagem", "params": {}, "demorada": True},
    "revisao.preparar": {"desc": "Verificar o projeto e gerar um RASCUNHO para revisão", "params": {}, "demorada": True},
    "verificar": {"desc": "Verificar o projeto antes de exportar (sem renderizar)", "params": {}},
    "exportar.final": {"desc": "Gerar o vídeo FINAL (só depois de você aprovar o rascunho)", "params": {}, "demorada": True},
    "ir": {"desc": "Abrir uma etapa do app", "params": {"aba": ["fonte", "cortes", "estilo", "audio", "narracao", "legendas",
                                                                "revisar", "assistente", "react"]}},
}

EXEMPLOS = ["Gere legendas para este vídeo", "Encontre os momentos mais interessantes", "Aplique um zoom suave neste trecho",
            "Crie uma versão vertical para Shorts", "Coloque o recorte do criador sobre o gameplay",
            "Revise as legendas e destaque as palavras importantes", "Prepare uma versão para revisão antes da exportação"]


def norm(t):
    t = unicodedata.normalize("NFKD", str(t).lower())
    return " " + re.sub(r"[^a-z0-9 ]+", " ", "".join(c for c in t if not unicodedata.combining(c))) + " "


def _tem(t, *padroes):
    return any(re.search(p, t) for p in padroes)


def _interpretar_um(t):
    """Uma frase -> lista de acoes (ordem natural). Regras simples e previsiveis; o que nao casar fica para a IA."""
    acoes = []
    num = lambda pad: (int(m.group(1)) if (m := re.search(pad, t)) else None)
    legenda = _tem(t, r" legend")
    if legenda and _tem(t, r" destac", r" importante", r" enfat"):
        acoes.append(("legendas.destacar", {}))
    elif legenda and _tem(t, r" (ger|cri|fa[cz]|transcrev|coloc|bot|adicion)", r" quero legenda"):
        origem = "video" if _tem(t, r" (do|no) (video|jogo|trailer|gameplay)", r" audio (do video|original)") else \
                 "narracao" if _tem(t, r" narrac", r" minha voz") else "auto"
        acoes.append(("legendas.gerar", {"origem": origem}))
    if legenda and _tem(t, r" (estilo|visual|preset|formato) (do |de |para )?(shorts|tiktok|reels)"):
        pl = "tiktok" if " tiktok " in t else "reels" if " reels " in t else "shorts"
        acoes.append(("legendas.plataforma", {"plataforma": pl}))
    if _tem(t, r" zoom"):
        alvo = "todos" if _tem(t, r" todos", r" tudo", r" cada trecho", r" todas") else "selecionado"
        if _tem(t, r" (tir|remov|desliga|apag)", r" sem zoom"):
            acoes.append(("zoom.remover", {"alvo": alvo}))
        elif _tem(t, r" pico", r" momentos? fortes?", r" automat", r" onde (tem|houver) acao"):
            acoes.append(("zoom.picos", {}))
        else:
            preset = "impacto" if _tem(t, r" impacto", r" soco", r" forte", r" rapido", r" punch") else \
                     "reacao" if _tem(t, r" reac", r" entra e sai", r" volta") else \
                     "lento" if _tem(t, r" lento", r" cinemat", r" devagarinho") else "destaque"
            acoes.append(("zoom.aplicar", {"preset": preset, "alvo": alvo}))
    if _tem(t, r" momento", r" melhores partes", r" partes? (mais )?(interessante|legal|boa)", r" destaques? do video",
            r" highlights?") and not legenda and _tem(t, r" (encontr|ach|procur|busc|mostr|quais|ve |analis|descobr)"):
        acoes.append(("momentos.achar", {"duracao": num(r" (\d{1,3}) ?s(eg|egundos)? ") or 25,
                                         "quantidade": num(r" (\d{1,2}) (momentos|clipes|cortes|trechos) ") or 5}))
    if _tem(t, r" (monte|montar|usa|use|coloc).{0,30}(melhor momento|primeiro momento)"):
        acoes.append(("momentos.usar", {"indice": 0}))
    if _tem(t, r" (vertical|shorts?|tiktok|reels)") and _tem(t, r" (cri|fa[cz]|ger|vers|transform|corte)") and not legenda:
        acoes.append(("shorts.criar", {}))
    if _tem(t, r" (recorte|criador|camera|webcam|meu rosto|reac(t|ao)? )") and _tem(t, r" (sobre|cima|sobrepo|frente|coloc|poe|por)"):
        acoes.append(("react.recorte", {}))
    if _tem(t, r" (foco|enquadr)") and _tem(t, r" automat", r" acao", r" segu"):
        acoes.append(("foco.auto", {}))
    if _tem(t, r" previa") and _tem(t, r" (ger|cri|atualiz|refa)"):
        acoes.append(("previa.gerar", {}))
    if _tem(t, r" loop", r" emend\w* (no|com o) (comeco|inicio)", r" volt\w* (pro|para o|ao) (comeco|inicio)"):
        acoes.append(("timeline.loop", {}))
    publicar = _tem(t, r" publica", r" post(ar|agem)? ", r" hashtags?", r" titulo e descricao") and \
        _tem(t, r" (verific|verifiq|confer|checa|revis|ve se|esta (tudo )?certo)")
    if publicar:
        acoes.append(("publicacao.verificar", {}))
    revisar_legenda = legenda and any(a == "legendas.destacar" for a, _ in acoes)   # "revise as legendas" != rascunho
    if publicar:
        pass                                                        # "revise a publicacao" != rascunho
    elif not revisar_legenda and _tem(t, r" revis", r" rascunho", r" conferir", r" antes da export", r" antes de export"):
        acoes.append(("revisao.preparar", {}))
    elif _tem(t, r" verific", r" verifiq", r" checa", r" tem algum problema", r" esta tudo certo"):   # verifiCar/verifiQue
        acoes.append(("verificar", {}))
    elif _tem(t, r" export(e|ar|a)? (o )?(video )?final", r" ger(e|ar|a) (o )?final", r" renderiz(e|ar) (o )?final"):
        acoes.append(("exportar.final", {}))
    m = re.search(r" (abr[ae]|v[ao]|ir) (para |pra )?(a )?(aba |etapa )?(fonte|cortes|estilo|audio|narracao|legendas|revisar|assistente|react) ", t)
    if m and not acoes:
        acoes.append(("ir", {"aba": m.group(5)}))
    return acoes


def interpretar(texto):
    """Texto -> [{acao, params, desc, demorada, sobrescreve}]. Varias acoes: separe com 'depois', 'em seguida' ou ';'."""
    if not texto or len(texto) > 500:
        return []
    partes = re.split(r";|\bdepois\b|\bem seguida\b|\be entao\b", norm(texto))
    vistos, plano = set(), []
    for parte in partes:
        for acao, params in _interpretar_um(" " + parte.strip() + " "):
            chave = (acao, tuple(sorted(params.items())))
            if chave not in vistos:
                vistos.add(chave)
                plano.append(descrever(acao, params))
    return plano


def validar(acao, params):
    """So acoes do catalogo, so parametros conhecidos e dentro do permitido (protege contra a IA e contra o navegador)."""
    if acao not in ACOES:
        raise ValueError(f"ação desconhecida: {acao}")
    esperado, out = ACOES[acao]["params"], {}
    for k, v in (params or {}).items():
        if k not in esperado:
            raise ValueError(f"parâmetro desconhecido em {acao}: {k}")
        regra = esperado[k]
        if isinstance(regra, list):
            if v not in regra:
                raise ValueError(f"{acao}: '{k}' precisa ser um de {', '.join(regra)}")
            out[k] = v
        else:
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                raise ValueError(f"{acao}: '{k}' precisa ser um número")
    if acao == "momentos.achar":
        out["duracao"] = min(max(out.get("duracao", 25), 5), 600)
        out["quantidade"] = min(max(out.get("quantidade", 5), 1), 20)
    if acao == "momentos.usar":
        out["indice"] = min(max(out.get("indice", 0), 0), 19)
    return out


def descrever(acao, params):
    a = ACOES[acao]
    return {"acao": acao, "params": validar(acao, params), "desc": a["desc"], "demorada": bool(a.get("demorada")),
            "sobrescreve": a.get("sobrescreve")}


def schema_ia():
    """Formato que a IA deve devolver (so acoes do catalogo)."""
    return {"type": "object", "properties": {
        "acoes": {"type": "array", "items": {"type": "object", "properties": {
            "acao": {"type": "string", "enum": list(ACOES)}, "params": {"type": "object"}, "porque": {"type": "string"}},
            "required": ["acao", "params", "porque"]}},
        "resposta": {"type": "string"}}, "required": ["acoes", "resposta"]}


def prompt_ia(texto, resumo):
    linhas = ["Você controla o editor de vídeo Clipador. Escolha SOMENTE ações desta lista (nome: descrição; parâmetros):"]
    for nome, a in ACOES.items():
        linhas.append(f"- {nome}: {a['desc']}; parâmetros: {a['params'] or 'nenhum'}")
    linhas += ["Se o pedido não couber em nenhuma ação, devolva a lista vazia e explique em 'resposta' o que dá para fazer.",
               "Nunca invente ações nem parâmetros. Não execute nada: só escolha.",
               f"Estado do projeto: {resumo}", f"Pedido do usuário: {texto.strip()[:500]}"]
    return "\n".join(linhas)
