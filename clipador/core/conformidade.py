"""Verificações preventivas de conformidade (matriz em docs/cpv/04-politicas-monetizacao.md).

Cada item diz a regra oficial que o motiva (F1…F11 do documento). Nada aqui garante aprovação no YPP nem prova
fair use: aponta riscos para revisão humana. Itens no formato do verificador (nivel, titulo, detalhe, como_resolver)
com o campo extra "regra".
"""
import json
import os
import re
import unicodedata

from . import projeto, recursos

# termos procurados no título, no texto do início e nas legendas dos primeiros 7 s (sem acento, minúsculo)
TERMOS = {
    "enganoso": (r"\b(vazad\w*|leak\w*|exclusiv\w*)\b", "aviso", "F5",
                 "Termo que promete algo verificável", "Registre a fonte que comprova (ou troque o termo): metadado enganoso é spam."),
    "afirmacao": (r"\b(confirmad\w*|oficial\w*|official)\b", "dica", "F5",
                  "Afirmação que pede fonte", "Tenha a fonte oficial registrada no roteiro/descrição."),
    "violencia": (r"\b(sangue\w*|gore|decapit\w*|esquartej\w*|brutal\w*|blood\w*|gory)\b", "aviso", "F7",
                  "Violência explícita no texto", "No título, na miniatura ou nos primeiros 7 s pode zerar os anúncios."),
    "palavrao": (r"\b(porra|caralh\w*|merda|puta\w*|fuck\w*|shit\w*|bitch\w*)\b", "aviso", "F7",
                 "Palavrão no texto", "Palavrão no título ou no início limita ou zera anúncios."),
    "incentivo": (r"\b(sorteio|giveaway|sub ?4 ?sub|inscreva-se e ganhe|ganhe um|concorra)\b", "aviso", "F5/F6",
                  "Recompensa por engajamento", "Oferecer prêmio por like/inscrição é proibido; pedir engajamento sem prêmio é permitido."),
    "drogas_armas": (r"\b(cocaina|maconha|crack|metanfetamina|fuzil|municao|vape|cigarro eletronico)\b", "dica", "F7",
                     "Tema que restringe anúncios", "Contexto educativo/documental pode manter anúncios; promoção não."),
}
LIMITE_TERCEIROS_S = 60.0      # Short com mais de 1 min e reivindicação de direitos não monetiza (F3)


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return s


def _item(nivel, titulo, detalhe, como, regra):
    return {"nivel": nivel, "titulo": titulo, "detalhe": detalhe, "como_resolver": como, "regra": regra}


def _textos_do_inicio(p):
    """Título da publicação, texto do gancho e legendas que começam nos primeiros 7 s."""
    out = [("título", (p.get("publicacao") or {}).get("titulo", "")), ("gancho", (p.get("gancho") or {}).get("texto", ""))]
    c = os.path.join(projeto.pasta(p["nome"]), "legenda_cartoes.json")
    if os.path.isfile(c):
        with open(c, encoding="utf-8") as f:
            cart = [x for x in json.load(f) if x.get("palavras")]
        out.append(("legenda 0–7 s", " ".join(w.get("word", "") for x in cart for w in x["palavras"] if w.get("start", 99) < 7)))
    return out


def termos_de_risco(p):
    itens = []
    textos = _textos_do_inicio(p)
    for chave, (padrao, nivel, regra, titulo, como) in TERMOS.items():
        achados = sorted({(onde, m.group(0)) for onde, t in textos for m in re.finditer(padrao, _norm(t))})
        if achados:
            itens.append(_item(nivel, titulo, "; ".join(f"{onde}: “{w}”" for onde, w in achados), como, regra))
    return itens


def direitos(p):
    itens = []
    total = projeto.duracao_timeline(p)
    por_origem = recursos.tempo_por_origem(p)
    terceiros = por_origem.get("terceiros", 0.0)
    sem_info = por_origem.get("nao_informado", 0.0)
    tem_fala_propria = bool(p.get("narracao")) or (p.get("react") or {}).get("ativo")
    if terceiros:
        if not tem_fala_propria:
            itens.append(_item("aviso", "Material de terceiros sem comentário seu",
                               f"{terceiros:.0f} s de {total:.0f} s vêm de vídeo de terceiros e o projeto não tem narração",
                               "Conteúdo reutilizado só é aceito com diferença significativa (comentário, crítica, explicação). "
                               "Grave a narração ou troque o material.", "F1"))
        else:
            itens.append(_item("dica", "Material de terceiros com narração",
                               f"{terceiros:.0f} s de {total:.0f} s", "Confira que a narração comenta o trecho (não só acompanha).", "F1/F8"))
    if p.get("tipo") != "longo" and total > LIMITE_TERCEIROS_S and (terceiros or sem_info):
        itens.append(_item("aviso", "Short com mais de 1 min usando material sem licença registrada",
                           f"{total:.0f} s; {terceiros + sem_info:.0f} s de terceiros ou sem origem",
                           "Short acima de 1 min com reivindicação de direitos não monetiza: encurte para ≤ 60 s ou use material próprio/licenciado.", "F3"))
    if sem_info:
        itens.append(_item("dica", "Origem do vídeo não registrada", f"{sem_info:.0f} s sem origem/licença",
                           "Aba 1 · Fonte → Direitos deste vídeo (próprio, licenciado, domínio público ou terceiros).", "F1/F8"))
    musica = ((p.get("audio") or {}).get("musica") or {}).get("arquivo")
    if musica:
        d = recursos.biblioteca_ler(projeto.BIBLIOTECAS["musicas"]).get(os.path.basename(musica))
        if recursos.precisa_atencao(d):
            itens.append(_item("aviso", "Música sem licença registrada", musica,
                               "Registre a origem na biblioteca (ex.: YouTube Audio Library) ou troque por música livre.", "F8"))
        if p.get("tipo") != "longo":
            itens.append(_item("dica", "Música de parceiros reduz a parte do Short no fundo de receita",
                               "1 faixa = metade; 2 faixas = um terço (regra oficial dos Shorts)",
                               "Use música só quando ela agrega; sem música, 100% da parte vai para o fundo.", "F3"))
    return itens


def _tem_final(nome):
    d = projeto.pasta(nome)
    return os.path.isdir(d) and any(f.startswith("FINAL_") and f.endswith(".mp4") for f in os.listdir(d))


def duplicados(p):
    """Outro projeto JÁ EXPORTADO (tem FINAL) com o mesmo conteúdo: publicar os dois é repost em massa (F5)."""
    if not p.get("segmentos"):
        return []
    meu = projeto.hash_conteudo(p)
    iguais = []
    for outro in projeto.listar():
        if outro == p["nome"] or not _tem_final(outro):
            continue
        try:
            if projeto.hash_conteudo(projeto.carregar(outro)) == meu:
                iguais.append(outro)
        except (OSError, ValueError, KeyError):
            continue
    if not iguais:
        return []
    return [_item("aviso", "Outro projeto tem exatamente o mesmo conteúdo", ", ".join(iguais[:5]),
                  "Publicar cópias com mudanças mínimas é spam (repost/produção em massa). Mude o gancho, o ângulo ou o roteiro.", "F5")]


def verificar(p):
    return termos_de_risco(p) + direitos(p) + duplicados(p)
