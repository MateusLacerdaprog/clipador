"""Pacote de publicacao por rede (YouTube, TikTok, Instagram Reels): campos, limites, verificacao e PUBLICACAO.md.

O app entrega arquivo + texto validado; quem publica e o usuario (sem login nas redes, sem promessa de alcance).
Declaracoes (feito para criancas, conteudo alterado/sintetico) sao do usuario: o app nunca escolhe por ele, so
cobra que seja escolhido. Limites das plataformas mudam: revisar de tempos em tempos (data em LIMITES_REVISADOS).
"""
import json
import os
import re
import unicodedata

from . import formatos, midia, projeto

LIMITES_REVISADOS = "2026-10"
LIMITES = {
    "youtube": {"titulo": 100, "titulo_ideal": 70, "chave_ate": 40, "descricao": 5000, "tags_total": 500,
                "hashtags_ignoradas_acima": 60},
    "tiktok": {"legenda": 4000, "hashtags_ideal": 5},
    "instagram": {"legenda": 2200, "hashtags": 5, "previa": 125},
}
CATEGORIAS = {"20": "Jogos", "24": "Entretenimento", "23": "Comédia", "22": "Pessoas e blogs", "27": "Educação",
              "28": "Ciência e tecnologia", "25": "Notícias e política", "1": "Filmes e animação"}
PRIVACIDADES = ("private", "unlisted", "public")
# hashtags genericas: nao categorizam nada (skill hashtag-strategy); #shorts e opcional e fica de fora da lista
GENERICAS = {"#fyp", "#foryou", "#foryoupage", "#fy", "#viral", "#explore", "#explorepage", "#trending", "#parati"}
CTA_GENERICO = re.compile(r"\b(se inscrev\w*|inscreva-?se|deixa (o|seu) like|curte e compartilha|ativ\w* o sininho)\b", re.I)

PADRAO = {
    "titulo": "", "descricao": "", "hashtags": [],          # base = YouTube (campos antigos, mantidos)
    "palavra_chave": "",
    "youtube": {"tags": [], "categoria": "20", "privacidade": "private", "feito_para_criancas": None,
                "conteudo_alterado": None},
    "tiktok": {"legenda": "", "hashtags": []},
    "instagram": {"legenda": "", "hashtags": []},
    "credito": "", "ponte": "",
    "capa": {"tempo": None, "arquivo": None, "video": None},
}


def completar(pub):
    """Publicacao no formato atual (projetos antigos so tinham titulo/descricao/hashtags)."""
    pub = pub if isinstance(pub, dict) else {}
    out = json.loads(json.dumps(PADRAO))
    for k, v in pub.items():
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k].update({kk: vv for kk, vv in v.items() if kk in out[k]})
        elif k in out:
            out[k] = v
    return out


def _hashtags(v, maximo=30):
    lista = v.split() if isinstance(v, str) else (v or [])
    out = []
    for t in lista:
        t = re.sub(r"[^\w]", "", str(t).lstrip("#"), flags=re.UNICODE)[:40]
        if t and ("#" + t).lower() not in [x.lower() for x in out]:
            out.append("#" + t)
    return out[:maximo]


def _tags(v):
    lista = v.split(",") if isinstance(v, str) else (v or [])
    out = []
    for t in lista:
        t = str(t).strip().lstrip("#")[:100]
        if t and t.lower() not in [x.lower() for x in out]:
            out.append(t)
    return out[:60]


def _decl(v):
    return v if v in (True, False) else None


def validar(dados, atual):
    """Mescla o que veio da interface no que ja existe, limpando e limitando cada campo. Nunca preenche declaracao."""
    pub = completar(atual)
    d = dados or {}
    for k, lim in (("titulo", 150), ("descricao", 5000), ("palavra_chave", 80), ("credito", 300), ("ponte", 300)):
        if k in d:
            pub[k] = str(d[k] or "").strip()[:lim] if k != "descricao" else str(d[k] or "")[:lim]
    if "hashtags" in d:
        pub["hashtags"] = _hashtags(d["hashtags"])
    yt = d.get("youtube") or {}
    if "tags" in yt:
        pub["youtube"]["tags"] = _tags(yt["tags"])
    if "categoria" in yt:
        if str(yt["categoria"]) not in CATEGORIAS:
            raise ValueError("categoria do YouTube desconhecida")
        pub["youtube"]["categoria"] = str(yt["categoria"])
    if "privacidade" in yt:
        if yt["privacidade"] not in PRIVACIDADES:
            raise ValueError("privacidade deve ser private, unlisted ou public")
        pub["youtube"]["privacidade"] = yt["privacidade"]
    for k in ("feito_para_criancas", "conteudo_alterado"):
        if k in yt:
            pub["youtube"][k] = _decl(yt[k])
    for rede, lim in (("tiktok", LIMITES["tiktok"]["legenda"]), ("instagram", LIMITES["instagram"]["legenda"])):
        r = d.get(rede) or {}
        if "legenda" in r:
            pub[rede]["legenda"] = str(r["legenda"] or "")[:lim]
        if "hashtags" in r:
            pub[rede]["hashtags"] = _hashtags(r["hashtags"])
    return pub


# ------------------------------------------------------------------ menção tripla da palavra-chave
def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " " + re.sub(r"[^a-z0-9]+", " ", s).strip() + " "


def _contem(texto, chave):
    c = _norm(chave).strip()
    return bool(c) and f" {c} " in _norm(texto)


def _cartoes(p):
    c = os.path.join(projeto.pasta(p["nome"]), "legenda_cartoes.json")
    if not os.path.isfile(c):
        return []
    with open(c, encoding="utf-8") as f:
        return [x for x in json.load(f) if x.get("palavras")]


def _texto_cartoes(cart):
    return " ".join(w.get("word", "") for c in cart for w in c["palavras"])


def mencoes(p):
    """Onde a palavra-chave aparece: falada (legenda transcrita), na tela (gancho/legenda/rotulos) e no texto do post.
    falada = None quando nao da para saber (legenda escrita a mao ou sem legenda)."""
    pub = completar(p.get("publicacao"))
    chave = pub["palavra_chave"]
    cart = _cartoes(p)
    texto_leg = _texto_cartoes(cart)
    na_tela = " ".join([p.get("gancho", {}).get("texto", ""), texto_leg,
                        (p.get("comparacao") or {}).get("rotulo_a", ""), (p.get("comparacao") or {}).get("rotulo_b", "")]
                       + [s.get("rotulo_a", "") + " " + s.get("rotulo_b", "") for s in p.get("segmentos", [])])
    falada = None
    if cart and p.get("legenda_origem") in ("narracao", "video"):
        falada = _contem(texto_leg, chave)
    post = {"youtube": _contem(pub["titulo"] + " " + pub["descricao"], chave),
            "tiktok": _contem(pub["tiktok"]["legenda"], chave),
            "instagram": _contem(pub["instagram"]["legenda"], chave)}
    return {"chave": chave, "falada": falada, "na_tela": _contem(na_tela, chave), "post": post}


# ------------------------------------------------------------------ verificação
def _item(nivel, titulo, detalhe="", como=""):
    return {"nivel": nivel, "titulo": titulo, "detalhe": detalhe, "como_resolver": como}


def _verif_hashtags(rede, tags, itens, maximo=None, ideal=None):
    nome = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}[rede]
    if maximo is not None and len(tags) > maximo:
        itens.append(_item("erro", f"{nome}: {len(tags)} hashtags (limite {maximo})", " ".join(tags),
                           f"Deixe só as {maximo} mais específicas do assunto."))
    elif ideal is not None and len(tags) > ideal:
        itens.append(_item("aviso", f"{nome}: {len(tags)} hashtags", f"o recomendado é 3 a {ideal}",
                           "Mais hashtags não dão mais alcance: hoje elas só categorizam o vídeo."))
    gen = [t for t in tags if t.lower() in GENERICAS]
    if gen:
        itens.append(_item("aviso", f"{nome}: hashtags genéricas", " ".join(gen),
                           "Troque por hashtags do assunto (ex.: #gta6, #rockstargames); as genéricas não categorizam nada."))


def verificar(p):
    """Itens no formato do verificador ({nivel, titulo, detalhe, como_resolver}); nivel: erro | aviso | dica | ok.
    Mede o que as regras das redes pedem. Nao e previsao de views."""
    pub = completar(p.get("publicacao"))
    L, yt, itens = LIMITES, pub["youtube"], []
    curto = p.get("tipo") != "longo"
    # YouTube
    tit = pub["titulo"].strip()
    if not tit:
        itens.append(_item("erro", "Sem título", "", "Escreva o título (a palavra-chave nos primeiros 40 caracteres)."))
    elif len(tit) > L["youtube"]["titulo"]:
        itens.append(_item("erro", f"Título com {len(tit)} caracteres", f"o YouTube aceita até {L['youtube']['titulo']}", "Encurte o título."))
    elif len(tit) > L["youtube"]["titulo_ideal"]:
        itens.append(_item("aviso", f"Título com {len(tit)} caracteres", f"acima de {L['youtube']['titulo_ideal']} ele é cortado na tela do celular",
                           "Deixe o essencial no começo ou encurte."))
    if len(pub["descricao"]) > L["youtube"]["descricao"]:
        itens.append(_item("erro", "Descrição longa demais", f"{len(pub['descricao'])} caracteres (máx. {L['youtube']['descricao']})", "Encurte a descrição."))
    tags_total = sum(len(t) for t in yt["tags"]) + max(len(yt["tags"]) - 1, 0)
    if tags_total > L["youtube"]["tags_total"]:
        itens.append(_item("erro", "Tags do YouTube passam de 500 caracteres", f"{tags_total} caracteres", "Tire as tags menos ligadas ao vídeo."))
    if len(pub["hashtags"]) > L["youtube"]["hashtags_ignoradas_acima"]:
        itens.append(_item("erro", "Mais de 60 hashtags no YouTube", "o YouTube ignora todas", "Deixe 3 a 5."))
    else:
        _verif_hashtags("youtube", pub["hashtags"], itens, ideal=5)
    if yt["feito_para_criancas"] is None:
        itens.append(_item("erro", "Declare se o vídeo é “feito para crianças”", "é uma declaração legal (COPPA) que só você pode fazer",
                           "Marque Sim ou Não no YouTube. O app nunca escolhe por você."))
    if yt["conteudo_alterado"] is None:
        itens.append(_item("aviso", "Declare se há conteúdo alterado ou sintético realista", "ex.: voz clonada, cena gerada por IA que parece real",
                           "Marque Sim ou Não. Edição comum (cortes, legenda, zoom) não conta."))
    # TikTok / Instagram
    if not pub["tiktok"]["legenda"].strip():
        itens.append(_item("dica", "TikTok sem legenda própria", "", "Use “Adaptar do YouTube” e ajuste o tom (cada rede tem o seu)."))
    _verif_hashtags("tiktok", pub["tiktok"]["hashtags"], itens, ideal=L["tiktok"]["hashtags_ideal"])
    ig = pub["instagram"]
    if not ig["legenda"].strip():
        itens.append(_item("dica", "Instagram sem legenda própria", "", "Use “Adaptar do YouTube” e ajuste a primeira linha."))
    _verif_hashtags("instagram", ig["hashtags"], itens, maximo=L["instagram"]["hashtags"])
    # palavra-chave
    m = mencoes(p)
    if not m["chave"]:
        itens.append(_item("aviso", "Sem palavra-chave", "as redes viraram busca: o vídeo é achado pelo que é dito, escrito e legendado",
                           "Escolha como o público procuraria o assunto (ex.: “gta 6 trailer”)."))
    else:
        faltam = []
        if m["falada"] is False:
            faltam.append("falada")
        if not m["na_tela"]:
            faltam.append("na tela")
        if not m["post"]["youtube"]:
            faltam.append("título/descrição")
        if faltam:
            itens.append(_item("aviso", f"Palavra-chave “{m['chave']}” não aparece: {', '.join(faltam)}",
                               "o ideal é a menção tripla: dita, escrita na tela e no texto do post",
                               "Diga a palavra na narração, coloque no gancho ou na legenda e no título."))
        elif m["falada"] is None:
            itens.append(_item("dica", "Não dá para saber se a palavra-chave é falada", "a legenda foi escrita à mão ou não existe",
                               "Confira se você fala a palavra-chave no começo do vídeo."))
        if tit and not _contem(tit[:L["youtube"]["chave_ate"]], m["chave"]):
            itens.append(_item("aviso", "Palavra-chave fora do começo do título", f"o YouTube pesa mais os primeiros ~{L['youtube']['chave_ate']} caracteres",
                               "Leve a palavra-chave para o início do título."))
        if ig["legenda"].strip() and not _contem(ig["legenda"][:L["instagram"]["previa"]], m["chave"]):
            itens.append(_item("dica", "Instagram: palavra-chave fora da primeira linha", "a busca do Instagram lê a legenda", "Coloque-a na primeira frase."))
    # CTA, crédito, ponte, capa
    textos = " ".join([pub["descricao"], pub["tiktok"]["legenda"], ig["legenda"]])
    if CTA_GENERICO.search(textos):
        itens.append(_item("dica", "Chamada genérica (“se inscreva”, “deixa o like”)", "", "Troque por uma pergunta ligada ao vídeo; gera comentário de verdade."))
    if not pub["credito"].strip():
        itens.append(_item("dica", "Sem crédito da fonte", "", "Se usa material de terceiros (trailer, gameplay de outro canal), credite a fonte."))
    if curto and not pub["ponte"].strip():
        itens.append(_item("dica", "Sem ponte para o vídeo longo", "Shorts que levam a um vídeo longo ajudam o canal a crescer",
                           "Indique o vídeo longo relacionado (no YouTube: “Vídeo relacionado”)."))
    if not (pub["capa"].get("arquivo") and os.path.isfile(os.path.join(projeto.pasta(p["nome"]), pub["capa"]["arquivo"]))):
        itens.append(_item("dica", "Capa não escolhida", "a capa aparece no perfil e na grade (no Instagram não muda depois)",
                           "Escolha o instante do quadro mais forte e gere a capa."))
    ordem = {"erro": 0, "aviso": 1, "dica": 2, "ok": 3}
    itens.sort(key=lambda i: ordem[i["nivel"]])
    if not [i for i in itens if i["nivel"] in ("erro", "aviso")]:
        itens.insert(0, _item("ok", "Publicação pronta para copiar", "nada obrigatório faltando"))
    return itens


# ------------------------------------------------------------------ adaptar e exportar
def adaptar(p):
    """Ponto de partida para TikTok e Instagram a partir do título/descrição do YouTube (o usuário ajusta o tom).
    Instagram: no máximo 5 hashtags; a palavra-chave vai para a primeira linha."""
    pub = completar(p.get("publicacao"))
    tit, desc = pub["titulo"].strip(), pub["descricao"].strip()
    primeira = desc.split("\n")[0].strip() if desc else ""
    corpo = tit + (("\n\n" + primeira) if primeira and primeira != tit else "")
    extra = ("\n\n" + pub["credito"].strip()) if pub["credito"].strip() else ""
    base = [t for t in pub["hashtags"] if t.lower() not in GENERICAS]
    return {"tiktok": {"legenda": corpo + extra, "hashtags": base[:5]},
            "instagram": {"legenda": corpo + extra, "hashtags": base[:LIMITES["instagram"]["hashtags"]]}}


def _sim_nao(v):
    return "Sim" if v is True else "Não" if v is False else "⚠ NÃO DECLARADO"


VARIANTES = ("_1x1.mp4", "_sem_audio.mp4")      # versoes derivadas de um RASCUNHO/FINAL (nao sao "o" video)


def _mais_recente(p, prefixo):
    d = projeto.pasta(p["nome"])
    if not os.path.isdir(d):
        return None
    achados = sorted((f for f in os.listdir(d) if f.startswith(prefixo) and f.endswith(".mp4") and ".tmp." not in f
                      and not f.endswith(VARIANTES)), key=lambda f: os.path.getmtime(os.path.join(d, f)))
    return achados[-1] if achados else None


def _saida_final(p):
    return _mais_recente(p, "FINAL_")


def markdown(p):
    pub = completar(p.get("publicacao"))
    yt, longo = pub["youtube"], p.get("tipo") == "longo"
    final = _saida_final(p)
    desc = pub["descricao"].rstrip()
    if longo and (p.get("formato_cfg") or {}).get("capitulos"):
        caps = formatos.capitulos(p)["texto"]
        if caps and caps not in desc:
            desc = (desc + "\n\n" + caps).strip()
    if pub["credito"].strip() and pub["credito"].strip() not in desc:
        desc = (desc + "\n\n" + pub["credito"].strip()).strip()
    if pub["ponte"].strip() and pub["ponte"].strip() not in desc:
        desc = (desc + "\n\n" + pub["ponte"].strip()).strip()
    capa = pub["capa"]
    txt_capa = "—"
    if capa.get("arquivo"):
        txt_capa = capa["arquivo"] + (f" (quadro em {capa['tempo']:.1f} s)" if capa.get("tempo") is not None else "")
    linhas = [f"# Publicação — {p['nome']}", "",
              f"- **Vídeo:** {final or 'ainda sem FINAL (gere e aprove o RASCUNHO antes)'}",
              f"- **Palavra-chave:** {pub['palavra_chave'] or '—'}",
              f"- **Capa:** {txt_capa}",
              "", f"## YouTube ({'vídeo' if longo else 'Shorts'})", "", f"**Título:** {pub['titulo']}", "",
              "**Descrição:**", "", desc + (("\n\n" + " ".join(pub["hashtags"])) if pub["hashtags"] else ""), "",
              f"**Tags:** {', '.join(yt['tags']) or '—'}",
              f"**Categoria:** {CATEGORIAS.get(yt['categoria'], yt['categoria'])} · **Privacidade:** {yt['privacidade']} · "
              f"**Feito para crianças:** {_sim_nao(yt['feito_para_criancas'])} · "
              f"**Conteúdo alterado/sintético:** {_sim_nao(yt['conteudo_alterado'])}", ""]
    for rede, nome in (("tiktok", "TikTok"), ("instagram", "Instagram Reels")):
        r = pub[rede]
        linhas += [f"## {nome}", "", (r["legenda"].rstrip() or "—") + (("\n\n" + " ".join(r["hashtags"])) if r["hashtags"] else ""), ""]
    itens = [i for i in verificar(p) if i["nivel"] != "ok"]
    linhas += ["## Verificação", ""] + ([f"- {'❌' if i['nivel'] == 'erro' else '⚠️' if i['nivel'] == 'aviso' else '💡'} "
                                           f"{i['titulo']}" + (f" — {i['como_resolver']}" if i["como_resolver"] else "") for i in itens]
                                          or ["- ✅ nada obrigatório faltando"])
    linhas += ["", f"_Limites das redes revisados em {LIMITES_REVISADOS}. Sem previsão de views._", ""]
    return "\n".join(linhas)


def exportar(p):
    """Grava PUBLICACAO.md na pasta do projeto (ao lado do FINAL). Devolve o nome do arquivo."""
    c = os.path.join(projeto.pasta(p["nome"]), "PUBLICACAO.md")
    tmp = c + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(markdown(p))
    os.replace(tmp, c)
    return "PUBLICACAO.md"


def video_para_capa(p):
    """Melhor vídeo pronto para tirar a capa: FINAL > RASCUNHO > prévia (proxy.mp4)."""
    d = projeto.pasta(p["nome"])
    pronto = _saida_final(p) or _mais_recente(p, "RASCUNHO_")
    if pronto:
        return os.path.join(d, pronto)
    prox = os.path.join(d, "proxy.mp4")
    return prox if os.path.isfile(prox) else None


def gerar_capa(p, tempo):
    """Extrai o quadro do instante `tempo` (s) do melhor vídeo pronto para capa.png. Devolve a publicacao atualizada."""
    video = video_para_capa(p)
    if not video:
        raise ValueError("gere a prévia, o RASCUNHO ou o FINAL antes de escolher a capa")
    dur = midia.duracao(video)
    tempo = float(tempo)
    if not 0 <= tempo <= max(dur - 0.05, 0):
        raise ValueError(f"o instante deve estar entre 0 e {dur:.1f} s")
    destino = os.path.join(projeto.pasta(p["nome"]), "capa.png")
    r = midia.rodar(["ffmpeg", "-y", "-v", "error", "-ss", f"{tempo:.3f}", "-i", video, "-frames:v", "1", destino])
    if r.returncode != 0 or not os.path.isfile(destino):
        raise RuntimeError("não consegui extrair o quadro do vídeo")
    pub = completar(p.get("publicacao"))
    pub["capa"] = {"tempo": round(tempo, 2), "arquivo": "capa.png", "video": os.path.basename(video)}
    return pub
