"""Formatos de video (curto/longo x guias/noticias/gameplay/curiosidades/compilados).

Cada formato e um PRESET editavel: aplica layout, legenda, gancho, audio e duracao-alvo, e traz um guia
(estrutura em blocos, roteiro-modelo, checklist). "evidencias" sao dados OBSERVADOS na pesquisa de
16/10/2026 (docs/FORMATOS_VIRAIS.md); o resto e recomendacao, nao garantia de alcance.
"""
import copy

TIPOS = ("curto", "longo")
CATEGORIAS = ("guias", "noticias", "gameplay", "curiosidades", "compilados")

_CURTO = {
    "guias": {
        "nome": "Guia / Dica", "icone": "🧭",
        "descricao": "Um truque por vídeo: resultado no gancho, passo a passo mostrando o botão, prova no fim.",
        "evidencias": ["'Secret GTA Online Motorcycle Trick' — 10,8 mi em 24 s",
                       "'Best Way To Make Money As A Beginner' — 4,6 mi com 10,6 mil inscritos (11 s)",
                       "Mediana dos Shorts de guia: 24,5 s"],
        "preset": {"layout": "tela_cheia", "legenda": {"estilo": "palavra", "maiusculas": True},
                   "gancho": {"texto": "O TRUQUE QUE NINGUÉM TE CONTOU", "ate": 2.5},
                   "audio": {"original": {"db": 0, "db_com_narracao": -18}}},
        "duracao_alvo": 25, "max_cena": 4, "ranking": False,
        "estrutura": [("Gancho: o resultado", 0.10, "Mostre o resultado final logo de cara (dinheiro, carro, vitória)."),
                      ("Passo a passo", 0.70, "Cada passo numa cena; escreva o botão na tela (ex.: 'APERTE X')."),
                      ("Prova", 0.20, "Mostre funcionando. Termine sem despedida para emendar no começo.")],
        "roteiro": "Esse truque [RESULTADO] em [TEMPO].\nPrimeiro, [PASSO 1].\nDepois, [PASSO 2].\nE pronto: [PROVA].",
        "checklist": ["Um truque só", "Botões/comandos escritos na tela", "Prova visual no fim", "Série numerada (Parte 1, 2…)"],
    },
    "noticias": {
        "nome": "Notícia", "icone": "📰",
        "descricao": "Um fato por vídeo, rápido. Selo fixo (OFICIAL / RUMOR) e fonte na tela.",
        "evidencias": ["'GTA 6 New Leak Just Dropped' — 7,8 mi com 2,6 mil inscritos, em 8 s",
                       "Mediana dos Shorts de notícia: 29 s; os de out/2026 têm 7–30 s",
                       "Longos de análise saíram 1–3 dias depois do anúncio"],
        "preset": {"layout": "empilhado", "legenda": {"estilo": "caixa", "maiusculas": False},
                   "gancho": {"texto": "OFICIAL: ", "ate": 0},
                   "audio": {"original": {"db": -6, "db_com_narracao": -22}}},
        "duracao_alvo": 20, "max_cena": 3, "ranking": False,
        "estrutura": [("Manchete", 0.15, "O fato em uma frase. Diga se é OFICIAL ou RUMOR."),
                      ("Detalhe que importa", 0.65, "O que muda para o jogador; mostre a imagem que comprova."),
                      ("Fonte + pergunta", 0.20, "Cite a fonte e faça uma pergunta para os comentários.")],
        "roteiro": "[OFICIAL/RUMOR]: [FATO EM UMA FRASE].\nIsso significa que [IMPACTO NO JOGO].\nFonte: [QUEM DISSE]. Você acredita?",
        "checklist": ["Publicar rápido (mesmo dia)", "Selo OFICIAL ou RUMOR", "Fonte citada",
                      "Nunca usar imagem falsa como se fosse real"],
    },
    "gameplay": {
        "nome": "Gameplay", "icone": "🎮",
        "descricao": "Um momento só, sem introdução: jogada épica, contraste ou vitrine gráfica.",
        "evidencias": ["Shorts de gameplay: 26,6× mais views que inscritos (mediana, a maior das 5 categorias)",
                       "'GTA 5 FPS Comparison' — 8,9 mi com 6,3 mil inscritos (16 s)",
                       "Mediana: 16,5 s"],
        "preset": {"layout": "tela_cheia", "legenda": {"estilo": "palavra", "maiusculas": False},
                   "gancho": {"texto": "", "ate": 2.0},
                   "audio": {"original": {"db": 0, "db_com_narracao": -14}}},
        "duracao_alvo": 15, "max_cena": 6, "ranking": False,
        "estrutura": [("Ação imediata", 0.25, "Comece no meio da ação, sem intro."),
                      ("O momento", 0.60, "A jogada, o bug, o contraste ou o visual impressionante."),
                      ("Reação / loop", 0.15, "Corte seco que emenda no começo.")],
        "roteiro": "(opcional) Uma frase curta de contexto ou de reação.",
        "checklist": ["10–20 s", "Sem introdução", "Som do jogo alto", "Para comparação use o layout A × B"],
    },
    "curiosidades": {
        "nome": "Curiosidade / Segredo", "icone": "🔍",
        "descricao": "'Você sabia…?' + prova visual + zoom no detalhe. Funciona como série.",
        "evidencias": ["'Secret Facts in GTA 5' — 14,4 mi (37 s), uma palavra por vez na tela",
                       "'VOCÊ SABIA disso no GTA?' — 3,6 mi (14 s)",
                       "Detalhe de GTA 6 — 1,4 mi com 1,3 mil inscritos (18 s)"],
        "preset": {"layout": "tela_cheia", "legenda": {"estilo": "palavra", "maiusculas": True},
                   "gancho": {"texto": "VOCÊ SABIA DISSO?", "ate": 2.5},
                   "audio": {"original": {"db": -4, "db_com_narracao": -20}}},
        "duracao_alvo": 30, "max_cena": 5, "ranking": False, "zoom": 1.15,
        "estrutura": [("Pergunta", 0.12, "'Você sabia que…?' com a imagem mais intrigante."),
                      ("Prova", 0.68, "Mostre o detalhe com zoom; um fato por cena."),
                      ("Virada", 0.20, "O detalhe mais surpreendente por último; sem despedida.")],
        "roteiro": "Você sabia que em [JOGO] [CURIOSIDADE]?\nRepara: [PROVA].\nE o mais estranho: [VIRADA].",
        "checklist": ["Um assunto só", "Zoom no detalhe", "Série numerada (Parte 1, 2…)", "Fato verificável"],
    },
    "compilados": {
        "nome": "Compilado / Ranking", "icone": "🏆",
        "descricao": "Ranking de momentos com a lista 1–5 se revelando a cada clipe; o nº 1 por último.",
        "evidencias": ["'Ranking Best GTA V Moments' — 27,8 mi com 15 mil inscritos (55 s), lista 1–5 progressiva",
                       "Compilados: 20,1× mais views que inscritos (mediana)",
                       "Mediana: 21 s; rankings ficam em 40–55 s"],
        "preset": {"layout": "empilhado", "legenda": {"estilo": "karaoke", "maiusculas": False},
                   "gancho": {"texto": "RANKING: OS MELHORES MOMENTOS", "ate": 0},
                   "audio": {"original": {"db": 0, "db_com_narracao": -16}}},
        "duracao_alvo": 45, "max_cena": 8, "ranking": True,
        "estrutura": [("5º ao 2º lugar", 0.80, "Um clipe por posição (3–8 s), do pior para o melhor."),
                      ("1º lugar", 0.20, "O melhor por último: é o que segura até o fim.")],
        "roteiro": "(opcional) Narração curta por posição ou só o som do jogo.",
        "checklist": ["Escreva o rótulo de cada trecho (aparece no ranking)", "O melhor momento por último",
                      "Use clipes seus ou com permissão (compilado de terceiros = risco de direitos autorais)"],
    },
    # so existe no curto: tela dividida com DOIS videos (A em cima, B embaixo), sem camera (nao e React)
    "comparacao": {
        "nome": "Comparação A × B", "icone": "⚖️",
        "descricao": "Tela dividida: um vídeo em cima e outro embaixo, na mesma cena (gráficos, física, antes × depois).",
        "evidencias": ["'GTA 5 FPS Comparison' — 8,9 mi com 6,3 mil inscritos (16 s)",
                       "'GTA 6 Trailer vs GTA 5 Comparison' — formato de exemplo enviado: cada jogo ocupa meia tela, mesma cena"],
        "preset": {"layout": "comparacao", "legenda": {"estilo": "palavra", "maiusculas": True},
                   "gancho": {"texto": "GTA 5 × GTA 6", "ate": 2.5},
                   "audio": {"original": {"db": -2, "db_com_narracao": -18}}},
        # plano minimo: pares A x B com menos de ~2,2 s nao dao tempo de comparar (lote 3 de producao, out/2026)
        "duracao_alvo": 20, "max_cena": 4, "min_cena": 2.2, "ranking": False,
        "estrutura": [("Cena mais impactante", 0.20, "Abra com a diferença mais gritante entre A e B."),
                      ("Cena a cena", 0.65, "Mesma cena nos dois jogos, alinhadas no tempo; 2–4 s cada."),
                      ("Final", 0.15, "O contraste mais forte por último; termine sem despedida.")],
        "roteiro": "(opcional) Diga o que mudou em cada cena: '[DETALHE] em [JOGO A]… e agora em [JOGO B]'.",
        "checklist": ["Vídeo A (em cima) e vídeo B (embaixo) escolhidos na aba 1 · Fonte",
                      "Mesma cena alinhada nos dois (ajuste 'B começa em')", "Rótulos A e B (ex.: GTA 5 / GTA 6)",
                      "Use vídeos que você tem direito de usar"],
    },
}
SO_CURTO = ("comparacao",)

_LONGO = {
    "guias": {"nome": "Guia completo", "icone": "🧭", "duracao_alvo": 720,
              "checklist": ["Prometa um resultado concreto nos primeiros 30 s", "Uma etapa por capítulo",
                            "Feche com resumo e indicação do próximo vídeo"],
              "descricao": "Intro dizendo o que a pessoa vai conseguir, capítulos por etapa e resumo.",
              "evidencias": ["Top guias: mediana de 11,6 min, sempre com capítulos por etapa",
                             "'GTA Online FOR DUMMIES' — 9,2 mi, 16 min, capítulos por negócio"],
              "estrutura": [("Intro: o que você vai conseguir", 0.05, "20–40 s; prometa um resultado concreto."),
                            ("Etapas (1 capítulo cada)", 0.85, "Cada etapa é um capítulo com nome claro."),
                            ("Resumo + próximo passo", 0.10, "Recapitule e indique o próximo vídeo.")]},
    "noticias": {"nome": "Análise de notícia", "icone": "📰", "duracao_alvo": 900,
                 "checklist": ["Publique em até 1–3 dias do anúncio", "Separe o que é oficial do que é rumor",
                               "Cite as fontes na tela e na descrição"],
                 "descricao": "Análise aprofundada com capítulos temáticos, publicada logo depois do anúncio.",
                 "evidencias": ["Top análises de GTA 6: 13–41 min, 3,5–4,6 mi, publicadas 1–3 dias após o trailer",
                                "SaninPlay (out/2026, observado): GTA 6 em 12–35 min, sempre 12 capítulos; mediana 61 mil "
                                "views nos longos, melhor recente 237 mil (16,9 mil/dia)",
                                "Títulos com número e MAIÚSCULAS ('155 DETALHES ABSURDOS', '+617 Detalhes') e capítulo de patrocínio"],
                 "estrutura": [("Gancho: a revelação mais forte", 0.04, "Comece pelo fato mais surpreendente, sem vinheta longa."),
                               ("Resumo do que saiu", 0.08, "O anúncio em 1 minuto: o que é oficial."),
                               ("Tópicos (1 capítulo cada, ~10)", 0.76, "Um capítulo por tema, com a imagem como prova; "
                                "deixe um tópico forte para o meio (retenção)."),
                               ("Patrocínio/aviso (opcional)", 0.02, "Se houver, em capítulo próprio, depois do 2º tópico."),
                               ("Opinião + pergunta", 0.10, "Sua conclusão e uma pergunta para os comentários.")]},
    "gameplay": {"nome": "Gameplay / Série", "icone": "🎮", "duracao_alvo": 1800,
                 "checklist": ["Série numerada (#1, #2…) com o objetivo no título", "Marque os momentos-chave como capítulos",
                               "Termine com o gancho do próximo episódio"],
                 "descricao": "Episódio de série numerada com um objetivo no título.",
                 "evidencias": ["Séries numeradas de 49–73 min com 48–55 mi de views ('GTA 5 GAMEPLAY #142')",
                                "Jazzghost (out/2026, observado): histórias/roleplay de Minecraft de 40–80 min, "
                                "4,6–6,4 mi em semanas (200–330 mil/dia), títulos que contam a premissa",
                                "MrBeast Gaming (observado): desafios em etapas que sobem de nível ('$100 → $1k → $100k')",
                                "SSundee (observado): série com mods, 20–30 min, mediana 653 mil views"],
                 "estrutura": [("Premissa + objetivo", 0.05, "Diga o desafio ou a história em 1 frase (o título conta a premissa)."),
                               ("Etapas que sobem de nível", 0.70, "Cada etapa mais difícil ou mais cara que a anterior; "
                                "um capítulo por etapa; complicação no meio."),
                               ("Clímax", 0.15, "A etapa final/maior consequência: o momento que o título prometeu."),
                               ("Resultado + gancho do próximo", 0.10, "Mostre se conseguiu e o que vem no próximo.")]},
    "curiosidades": {"nome": "Lista de segredos", "icone": "🔍", "duracao_alvo": 1200,
                     "checklist": ["Um capítulo por segredo", "Mostre um pedaço do melhor item no começo e entregue no fim",
                                   "Só fatos verificáveis"],
                     "descricao": "Lista de curiosidades/easter eggs, um capítulo por item.",
                     "evidencias": ["'All NEW Easter Eggs And Secrets' — 16,4 mi, 106 min, 1 capítulo por segredo",
                                    "'29 Secrets and Easter Eggs' — 10,2 mi em 6 min (IGN)"],
                     "estrutura": [("Gancho: o segredo mais forte (prévia)", 0.05, "Mostre um pedaço do melhor item."),
                                   ("Itens (1 capítulo cada)", 0.90, "Pergunta → prova → explicação."),
                                   ("O melhor por último", 0.05, "Entregue o item prometido no gancho.")]},
    "compilados": {"nome": "Compilado / Top", "icone": "🏆", "duracao_alvo": 660,
                   "checklist": ["Abra com 3–5 s do melhor momento", "Blocos por tipo de momento",
                                 "Use clipes seus ou com permissão (compilado de terceiros = risco de direitos autorais)"],
                   "descricao": "Top N ou melhores momentos, capítulos por tipo de momento.",
                   "evidencias": ["'Awesome GTA 5 Stunts & Fails' — 107,9 mi, 16 min, capítulos por tipo",
                                  "Duração mediana dos compilados longos: 11,2 min"],
                   "estrutura": [("Abertura com o melhor trecho", 0.05, "3–5 s do melhor momento."),
                                 ("Blocos por tipo de momento", 0.90, "Cada bloco é um capítulo."),
                                 ("Final mais forte", 0.05, "Guarde um ótimo momento para o fim.")]},
}

LIVRE = {"nome": "Livre", "icone": "✏️", "descricao": "Sem preset: você define tudo.", "evidencias": [],
         "estrutura": [], "roteiro": "", "checklist": [], "duracao_alvo": None, "ranking": False}


def _longo(cat):
    base = copy.deepcopy(_CURTO[cat])
    base.update(copy.deepcopy(_LONGO[cat]))
    base["preset"] = {"layout": "horizontal", "legenda": {"estilo": "karaoke", "maiusculas": False},
                      "gancho": {"texto": "", "ate": 0},
                      "audio": copy.deepcopy(_CURTO[cat]["preset"]["audio"])}
    base["ranking"] = False
    base["capitulos"] = True
    base["max_cena"] = 12
    base["roteiro"] = "\n".join(f"[{nome.upper()}]\n" for nome, _, _ in base["estrutura"])
    base["checklist"] = ["Capítulos: pelo menos 3, cada um com 10 s ou mais (regra do YouTube)",
                         "Rótulo em cada trecho que abre um capítulo"] + _LONGO[cat]["checklist"]
    return base


def catalogo():
    """Lista para a interface: {tipo: [{id, nome, icone, descricao, evidencias, ...}]}."""
    out = {}
    for tipo in TIPOS:
        itens = []
        for cat in CATEGORIAS + (SO_CURTO if tipo == "curto" else ()):
            f = obter(tipo, cat)
            itens.append({"id": cat, **{k: f[k] for k in ("nome", "icone", "descricao", "evidencias", "duracao_alvo")}})
        itens.append({"id": "livre", **{k: LIVRE[k] for k in ("nome", "icone", "descricao", "evidencias", "duracao_alvo")}})
        out[tipo] = itens
    return out


def obter(tipo, cat):
    if tipo not in TIPOS:
        raise ValueError("tipo invalido (curto ou longo)")
    if not cat or cat == "livre":
        return copy.deepcopy(LIVRE)
    if cat in SO_CURTO and tipo == "longo":
        raise ValueError("a comparação A × B (tela dividida) só existe no vídeo curto")
    if cat not in CATEGORIAS + SO_CURTO:
        raise ValueError("formato invalido")
    return _longo(cat) if tipo == "longo" else copy.deepcopy(_CURTO[cat])


def guia(p):
    """Guia do formato atual do projeto (estrutura com tempos em segundos)."""
    f = obter(p.get("tipo", "curto"), p.get("formato"))
    alvo = f.get("duracao_alvo") or max(p.get("duracao_atual", 0), 1)
    t, blocos = 0.0, []
    for nome, frac, dica in f["estrutura"]:
        blocos.append({"nome": nome, "ini": round(t, 1), "fim": round(t + frac * alvo, 1), "dica": dica})
        t += frac * alvo
    return {"tipo": p.get("tipo", "curto"), "formato": p.get("formato") or "livre", "nome": f["nome"],
            "icone": f["icone"], "descricao": f["descricao"], "evidencias": f["evidencias"],
            "duracao_alvo": f.get("duracao_alvo"), "max_cena": f.get("max_cena"), "min_cena": f.get("min_cena"),
            "estrutura": blocos,
            "roteiro": f.get("roteiro", ""), "checklist": f.get("checklist", []),
            "sugestao_gancho": ((f.get("preset") or {}).get("gancho") or {}).get("texto", "")}


def aplicar(p, tipo, cat):
    """Aplica o preset ao projeto (layout, legenda, gancho vazio, audio, opcoes). Nao apaga trechos."""
    from . import audio as A

    f = obter(tipo, cat)
    p["tipo"], p["formato"] = tipo, (None if cat in (None, "", "livre") else cat)
    pr = f.get("preset") or {}
    if tipo == "longo":
        p["layout"] = "horizontal"
    elif pr.get("layout"):
        p["layout"] = pr["layout"]
    elif p.get("layout") == "horizontal":
        p["layout"] = "tela_cheia"
    if pr.get("legenda"):
        p["legenda"] = {**p["legenda"], **pr["legenda"]}
    # o texto do gancho do formato e so SUGESTAO (guia -> "sugestao_gancho"): nada aparece no video sem o
    # usuario escolher (antes o "VOCE SABIA DISSO?" entrava sozinho e era dificil de achar para tirar)
    if pr.get("gancho") is not None and not (p.get("gancho") or {}).get("texto"):
        p["gancho"] = {"texto": "", "ate": pr["gancho"].get("ate", 3.0)}
    if pr.get("audio"):
        a = A.migrar(p.get("audio"))
        for k, v in pr["audio"].items():
            a[k].update(v)
        p["audio"] = A.validar(a)
    p["formato_cfg"] = {"ranking": bool(f.get("ranking")), "capitulos": bool(f.get("capitulos", tipo == "longo")),
                        "duracao_alvo": f.get("duracao_alvo")}
    if f.get("zoom"):
        for s in p.get("segmentos", []):
            if s.get("zoom", 1.0) == 1.0:
                s["zoom"] = f["zoom"]
    if not (p.get("roteiro") or "").strip():
        p["roteiro"] = f.get("roteiro", "")
    return p


# ------------------------------------------------------------------ capitulos
def capitulos(p):
    """Capitulos (inicio, titulo) a partir dos rotulos dos trechos + avisos das regras do YouTube."""
    caps, t = [], 0.0
    for s in p.get("segmentos", []):
        rot = (s.get("rotulo") or "").strip()
        if rot:
            caps.append([round(t, 2), rot])
        t += s["fim"] - s["ini"]
    total = t
    if caps and caps[0][0] > 0:
        caps.insert(0, [0.0, "Introdução"])
    avisos = []
    if len(caps) < 3:
        avisos.append("O YouTube só mostra capítulos com 3 ou mais. Escreva um rótulo nos trechos que abrem cada capítulo.")
    for (a, n), (b, _) in zip(caps, caps[1:] + [[total, ""]]):
        if b - a < 10:
            avisos.append(f"O capítulo '{n}' tem {b - a:.0f} s; o YouTube exige pelo menos 10 s.")
    texto = "\n".join(f"{_hms(a)} {n}" for a, n in caps)
    return {"capitulos": caps, "texto": texto, "avisos": avisos}


def _hms(s):
    s = int(s)
    h, m, ss = s // 3600, s // 60 % 60, s % 60
    return f"{h}:{m:02d}:{ss:02d}" if h else f"{m:02d}:{ss:02d}"


def ranking(p):
    """[(ini_trecho, posicao, texto)]: o 1o trecho e a ultima posicao (N) e o ultimo trecho e o nº 1.
    O trecho de loop (repeticao do comeco no fim) e o quadro congelado nao contam como posicao."""
    segs, t, out = p.get("segmentos", []), 0.0, []
    conta = lambda s: not (s.get("loop") or s.get("congelado"))
    pos = sum(1 for s in segs if conta(s))
    for s in segs:
        if conta(s):
            out.append((round(t, 2), pos, (s.get("rotulo") or "").strip()))
            pos -= 1
        t += s["fim"] - s["ini"]
    return out
