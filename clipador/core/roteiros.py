"""Roteiros por formato (docs/cpv/03 §4.3): esqueleto, ganchos alternativos, afirmações com fonte, versões e
aprovação. O texto final é do USUÁRIO (memória do projeto: o agente erra texto): a IA só sugere, e a sugestão
nunca entra no roteiro sem o usuário aplicar. Roteiro aprovado vira projeto (o texto vai para o teleprompter).
"""
import re

from . import conformidade, estudio, formatos, ideias, originalidade, projeto

ORDEM = ("gancho", "contexto", "desenvolvimento", "tensao", "recompensa", "fechamento", "cta")
OBRIGATORIOS = ("gancho", "desenvolvimento", "recompensa")
ESTRUTURAS = {  # formato: orientação por bloco (o que escrever em cada um)
    "explicador": {"gancho": "afirmação que contraria o senso comum ou pergunta concreta (0–2 s)",
                   "contexto": "por que parece verdade (1 frase)", "desenvolvimento": "a prova, em escada",
                   "tensao": "o detalhe que ainda falta", "recompensa": "o dado final que fecha a afirmação",
                   "fechamento": "volta ao começo (loop) ou ironia curta", "cta": "opcional, só no fim"},
    "serie": {"gancho": "nome da série + o caso do dia em 1 frase", "contexto": "quem/onde/quando, mínimo",
              "desenvolvimento": "3 fatos em escada, do curioso ao absurdo", "tensao": "o que deu errado",
              "recompensa": "o desfecho/ironia", "fechamento": "gancho para o próximo episódio", "cta": "opcional"},
    "pergunta": {"gancho": "a pergunta em voz alta + o objeto/cena na tela", "contexto": "por que a resposta não é óbvia",
                 "desenvolvimento": "tentativa/demonstração", "tensao": "o que surpreende", "recompensa": "a resposta literal ('…e é assim que…')",
                 "fechamento": "loop para a pergunta", "cta": "opcional"},
    "demonstracao": {"gancho": "o resultado curioso na tela", "contexto": "o que vamos testar", "desenvolvimento": "o passo a passo",
                     "tensao": "o momento em que pode dar errado", "recompensa": "o resultado e a explicação", "fechamento": "loop", "cta": "opcional"},
    "escala": {"gancho": "dois objetos do mesmo tipo, tamanhos absurdamente diferentes", "contexto": "a medida de cada um",
               "desenvolvimento": "consequências da diferença", "tensao": "a comparação mais inesperada",
               "recompensa": "a comparação final que fecha", "fechamento": "loop", "cta": "opcional"},
    "processo": {"gancho": "o resultado final escondido/insinuado", "contexto": "(sem fala: texto curto na tela)",
                 "desenvolvimento": "etapas de 2–4 s", "tensao": "a etapa decisiva", "recompensa": "a revelação", "fechamento": "loop", "cta": "opcional"},
    "momento": {"gancho": "a tensão em 1 frase", "contexto": "o mínimo para entender", "desenvolvimento": "o que acontece",
                "tensao": "a virada", "recompensa": "a reação/resultado", "fechamento": "desfecho", "cta": "opcional"},
    "humor": {"gancho": "o setup já em ação", "contexto": "(evitar)", "desenvolvimento": "escalada",
              "tensao": "o quase", "recompensa": "a punchline", "fechamento": "corte seco", "cta": "opcional"},
}
PPM_PADRAO = 160                  # narrados virais medidos: 144–224 palavras/min (docs/cpv/02); a voz real manda
MAX_CURTO_S = 180
MIN_GANCHOS_ALT = 2               # gancho principal + pelo menos 2 alternativas para comparar


def _hist(r, acao, detalhe=""):
    r.setdefault("historico", []).append({"em": estudio.agora(), "acao": acao, "detalhe": str(detalhe)[:300]})


def texto(r):
    """Texto corrido para narrar (ordem dos blocos; vazios ignorados)."""
    b = r.get("blocos") or {}
    return "\n".join(b[k].strip() for k in ORDEM if (b.get(k) or "").strip())


def _palavras(t):
    return re.findall(r"\w+", t or "")


def metricas(r):
    b = r.get("blocos") or {}
    total = len(_palavras(texto(r)))
    antes = sum(len(_palavras(b.get(k, ""))) for k in ORDEM[:ORDEM.index("recompensa")])
    ppm = r.get("ppm") or PPM_PADRAO
    return {"palavras": total, "duracao_s": round(total / ppm * 60, 1),
            "recompensa_em": round(antes / total, 2) if total else None}


def criar(ideia_id):
    ideia = ideias.obter(ideia_id)
    if ideia["status"] not in ("aprovada", "em_roteiro"):
        raise ValueError("só ideia APROVADA vira roteiro (pontuada, com fonte)")
    r = {"id": estudio.novo_id("roteiro"), "ideia": ideia_id, "canal": ideia["canal"], "formato": ideia["formato"],
         "titulo": ideia["titulo"], "blocos": {k: "" for k in ORDEM}, "guia": ESTRUTURAS[ideia["formato"]],
         "ganchos_alternativos": [], "afirmacoes": [], "fontes": ideia["fontes"], "ppm": PPM_PADRAO,
         "status": "rascunho", "versao": 1, "versoes": [], "sugestao_ia": None, "criado_em": estudio.agora()}
    _hist(r, "criado", f"da ideia {ideia_id}")
    if ideia["status"] == "aprovada":
        ideias.mudar_status(ideia_id, "em_roteiro", r["id"])
    return estudio.gravar("roteiros", r)


def editar(id_, blocos=None, ganchos_alternativos=None, afirmacoes=None, ppm=None, quem="usuário"):
    r = estudio.ler("roteiros", id_)
    r["versoes"].append({"versao": r["versao"], "blocos": dict(r["blocos"]), "ganchos_alternativos": list(r["ganchos_alternativos"]),
                         "afirmacoes": list(r["afirmacoes"]), "em": estudio.agora()})
    for k, v in (blocos or {}).items():
        if k not in ORDEM:
            raise ValueError(f"bloco desconhecido: {k}")
        r["blocos"][k] = str(v or "").strip()[:2000]
    if ganchos_alternativos is not None:
        r["ganchos_alternativos"] = [str(g).strip()[:300] for g in ganchos_alternativos if str(g).strip()][:5]
    if afirmacoes is not None:
        r["afirmacoes"] = [{"texto": str(a.get("texto") or "").strip()[:500], "fonte": str(a.get("fonte") or "").strip()[:500]}
                           for a in afirmacoes if str(a.get("texto") or "").strip()]
    if ppm is not None:
        if not 80 <= int(ppm) <= 260:
            raise ValueError("palavras por minuto entre 80 e 260")
        r["ppm"] = int(ppm)
    r["versao"] += 1
    if r["status"] == "aprovado":                       # mudou depois de aprovar: precisa aprovar de novo
        r["status"] = "rascunho"
        r.pop("aprovado_em", None)
    _hist(r, "editado", f"versão {r['versao']} por {quem}")
    return estudio.gravar("roteiros", r)


def checar(r):
    """Itens (nivel, titulo, detalhe) que impedem (erro) ou pedem atenção (aviso) antes de aprovar."""
    itens = []
    b, m = r.get("blocos") or {}, metricas(r)
    for k in OBRIGATORIOS:
        if not (b.get(k) or "").strip():
            itens.append({"nivel": "erro", "titulo": f"Bloco obrigatório vazio: {k}", "detalhe": r["guia"].get(k, "")})
    if len(r.get("ganchos_alternativos") or []) < MIN_GANCHOS_ALT:
        itens.append({"nivel": "erro", "titulo": f"Escreva pelo menos {MIN_GANCHOS_ALT} ganchos alternativos",
                      "detalhe": "compare clareza em 2 s, promessa verdadeira, especificidade e prova visual"})
    sem_fonte = [a["texto"][:60] for a in r.get("afirmacoes") or [] if not a["fonte"].startswith(("http://", "https://"))]
    if sem_fonte:
        itens.append({"nivel": "erro", "titulo": "Afirmação sem fonte", "detalhe": "; ".join(sem_fonte)})
    if not r.get("afirmacoes"):
        itens.append({"nivel": "aviso", "titulo": "Nenhuma afirmação com fonte registrada",
                      "detalhe": "liste os fatos do roteiro com o link que os comprova (revisão factual)"})
    if m["duracao_s"] > MAX_CURTO_S:
        itens.append({"nivel": "erro", "titulo": f"Roteiro longo demais para Short ({m['duracao_s']:.0f} s)", "detalhe": "máximo 180 s"})
    elif m["duracao_s"] > 60:
        itens.append({"nivel": "aviso", "titulo": f"Mais de 60 s ({m['duracao_s']:.0f} s)",
                      "detalhe": "acima de 1 min, qualquer material com reivindicação impede a monetização do Short (F3)"})
    if m["recompensa_em"] is not None and m["palavras"] and m["recompensa_em"] < 0.6:
        itens.append({"nivel": "aviso", "titulo": "Recompensa cedo demais",
                      "detalhe": f"começa em {m['recompensa_em']:.0%} do texto; o ideal é no fim (V2: não pagar cedo)"})
    for padrao, nivel, regra, titulo, como in conformidade.TERMOS.values():
        if re.search(padrao, conformidade._norm(b.get("gancho", "") + " " + r.get("titulo", ""))):
            itens.append({"nivel": nivel, "titulo": f"{titulo} no gancho/título", "detalhe": f"{como} (regra {regra})"})
    parecidos = [(i, s, ab) for i, s, ab in originalidade.comparar_no_canal(r, texto) if s >= originalidade.LIMIAR_AVISO or ab]
    for i, s, ab in parecidos[:3]:
        itens.append({"nivel": "aviso", "titulo": "Parecido com outro roteiro do canal",
                      "detalhe": f"{i}: {s:.0%} de trechos em comum" + ("; mesma abertura" if ab else "")
                      + " — canal 'intercambiável' perde monetização (F1)"})
    return itens


def aprovar(id_, quem="usuário"):
    r = estudio.ler("roteiros", id_)
    erros = [i for i in checar(r) if i["nivel"] == "erro"]
    if erros:
        raise ValueError("não dá para aprovar: " + "; ".join(i["titulo"] for i in erros))
    r["status"], r["aprovado_em"], r["aprovado_por"] = "aprovado", estudio.agora(), quem
    _hist(r, "aprovado", quem)
    return estudio.gravar("roteiros", r)


# ------------------------------------------------------------------ sugestão da IA (opcional)
SCHEMA_IA = {"type": "object", "properties": {
    "blocos": {"type": "object", "properties": {k: {"type": "string"} for k in ORDEM}},
    "ganchos_alternativos": {"type": "array", "items": {"type": "string"}},
    "afirmacoes": {"type": "array", "items": {"type": "object", "properties": {"texto": {"type": "string"}, "fonte": {"type": "string"}},
                                              "required": ["texto", "fonte"]}},
    "a_confirmar": {"type": "array", "items": {"type": "string"}}},
    "required": ["blocos", "ganchos_alternativos", "afirmacoes", "a_confirmar"]}


def pedido_ia(r):
    fontes = "\n".join(f"- {f['url']} — {f.get('titulo', '')} {f.get('nota', '')}" for f in r["fontes"]) or "(nenhuma)"
    guia = "\n".join(f"- {k}: {v}" for k, v in r["guia"].items())
    return {"sistema": ("Você rascunha roteiros de YouTube Shorts em português do Brasil. Use SOMENTE os fatos que estão nas "
                        "fontes listadas; cada afirmação precisa do link da fonte de onde saiu. O que não estiver nas fontes vai "
                        "para 'a_confirmar'. Não prometa views. Não copie títulos, bordões ou roteiros de outros criadores. "
                        "Gancho verdadeiro: a recompensa precisa existir no fim."),
            "prompt": (f"Ideia: {r['titulo']}\nFormato: {r['formato']}\nBlocos do formato:\n{guia}\n\nFontes:\n{fontes}\n\n"
                       f"Escreva os blocos (ritmo ~{r['ppm']} palavras/min, 30–60 s), 3 ganchos alternativos e a lista de afirmações "
                       "com a fonte de cada uma."),
            "schema": SCHEMA_IA}


def sugerir_com_ia(id_, enviar=None, progresso=lambda f, m=None: None):
    """Pede um RASCUNHO ao provedor de IA ativo (mesmo consentimento/limites/registro de custo do assistente).
    Guarda em r['sugestao_ia']; o roteiro só muda com aplicar_sugestao()."""
    from .ia import assistente
    r = estudio.ler("roteiros", id_)
    res = (enviar or assistente.enviar)({"nome": f"roteiro:{id_}"}, "roteiro_cpv", pedido_ia(r), progresso)
    fontes_ok = {f["url"] for f in r["fontes"]}
    dados = res.get("dados") or {}
    for a in dados.get("afirmacoes") or []:          # fonte que não está na ideia vira "a confirmar"
        if a.get("fonte") not in fontes_ok:
            dados.setdefault("a_confirmar", []).append(f"{a.get('texto', '')} (fonte não registrada: {a.get('fonte', '')})")
            a["fonte"] = ""
    r["sugestao_ia"] = {"origem": res.get("origem"), "em": estudio.agora(), "dados": dados, "custo_usd": res.get("custo_usd")}
    _hist(r, "sugestão da IA", res.get("origem"))
    return estudio.gravar("roteiros", r)


def aplicar_sugestao(id_, quem="usuário"):
    r = estudio.ler("roteiros", id_)
    s = (r.get("sugestao_ia") or {}).get("dados")
    if not s:
        raise ValueError("não há sugestão da IA para aplicar")
    r = editar(id_, blocos=s.get("blocos") or {}, ganchos_alternativos=s.get("ganchos_alternativos") or [],
               afirmacoes=[a for a in s.get("afirmacoes") or [] if a.get("fonte")], quem=f"{quem} (aplicou sugestão da IA)")
    r["origem_texto"] = "sugestão da IA revisada pelo usuário"
    return estudio.gravar("roteiros", r)


def para_projeto(id_, nome_projeto, tipo="curto", formato=None):
    """Cria o projeto do roteiro APROVADO: texto no teleprompter da narração, ligado ao canal e ao roteiro."""
    r = estudio.ler("roteiros", id_)
    if r["status"] != "aprovado":
        raise ValueError("aprove o roteiro antes de criar o projeto")
    p = projeto.criar(nome_projeto)
    formatos.aplicar(p, tipo, formato)                 # mesmo preset do "+ Novo" do app
    p.update(roteiro=texto(r), canal=r["canal"], roteiro_id=r["id"])
    projeto.salvar(p)
    r.setdefault("projetos", []).append(p["nome"])
    _hist(r, "projeto criado", p["nome"])
    estudio.gravar("roteiros", r)
    if ideias.obter(r["ideia"])["status"] != "produzida":
        ideias.mudar_status(r["ideia"], "produzida", p["nome"])
    return p


def listar(canal=None):
    return [r for r in estudio.listar("roteiros") if not canal or r["canal"] == canal]


def obter(id_):
    return estudio.ler("roteiros", id_)
