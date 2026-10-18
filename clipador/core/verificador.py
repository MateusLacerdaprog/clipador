"""Verificador pre-exportacao: acha problemas ANTES de exportar, com o que fazer para corrigir.

verificar_projeto(p) : rapido, sem render (arquivos, trechos, legenda x video, camera, recorte, duracao-alvo,
                       retencao medida: gancho, planos, legenda, loop, corte de cena na borda).
verificar_arquivo(c) : um passe do FFmpeg no video gerado (resolucao, duracao, audio, trechos pretos, imagem
                       congelada, silencio longo, volume final).
Cada item: {"nivel": "erro"|"aviso"|"dica"|"ok", "titulo", "detalhe", "como_resolver"}. Retencao e medida contra
as recomendacoes de Shorts (gancho em 3 s, troca de imagem a cada 2-4 s, legenda, loop); nunca e previsao de views.
"""
import json
import os
import re
import subprocess

from . import audio, formatos, midia, projeto, react, timeline

MIN_CENA_PADRAO = 1.0      # plano mais curto que isso "pisca" (formatos podem pedir mais: comparacao 2,2 s)
MAX_CENA_PADRAO = 4.0      # curto sem formato: trocar a imagem a cada 2-4 s
BORDA_CORTE = 0.5          # corte de cena a menos disso da borda do trecho = pedaco de outra cena piscando


def _planos(p):
    """[(n_trecho, duracao)] dos planos de verdade: cada trecho dividido nos cortes de cena da fonte.
    Zoom animado conta como troca de imagem (o trecho inteiro vira um plano "com movimento")."""
    fontes = {f["id"]: f for f in p["fontes"]}
    out = []
    for i, s in enumerate(p["segmentos"]):
        if s.get("loop"):
            continue
        cortes = [] if p.get("layout") == "comparacao" or s.get("congelado") else sorted(
            c["ini"] for c in (fontes.get(s["fonte"]) or {}).get("cenas") or [] if s["ini"] < c["ini"] < s["fim"])
        marcos = [s["ini"]] + cortes + [s["fim"]]
        for a, b in zip(marcos, marcos[1:]):      # quadro congelado e uma troca de imagem por si so
            out.append((i + 1, round(b - a, 2), bool(s.get("zoom_fx") or s.get("congelado"))))
    return out


def verificar_retencao(p, cart, total):
    """Itens de retencao medidos na montagem (sem render)."""
    itens, curto = [], p.get("tipo") != "longo"
    try:
        g = formatos.guia(p)
    except Exception:  # noqa: BLE001
        g = {}
    fontes = {f["id"]: f for f in p["fontes"]}
    # corte de cena colado na borda do trecho: 1-15 quadros de outra cena aparecem e somem (parece erro)
    pisca = []
    for i, s in enumerate(p["segmentos"]):
        if p.get("layout") == "comparacao":
            break
        if s.get("congelado"):
            continue
        for c in (fontes.get(s["fonte"]) or {}).get("cenas") or []:
            if s["ini"] < c["ini"] < min(s["ini"] + BORDA_CORTE, s["fim"]) or max(s["fim"] - BORDA_CORTE, s["ini"]) < c["ini"] < s["fim"]:
                pisca.append(f"{i + 1} ({c['ini'] - s['ini']:.2f} s)")
                break
    if pisca:
        itens.append(_item("aviso", "Trecho com pedaço de outra cena na borda", f"trechos {', '.join(pisca)}",
                           "Na aba Cortes, apare o trecho até o corte (com “Grudar nos cortes” ligado)."))
    if not curto or not p["segmentos"]:
        return itens
    planos = _planos(p)
    max_c, min_c = g.get("max_cena") or MAX_CENA_PADRAO, g.get("min_cena") or MIN_CENA_PADRAO
    longos = sorted({n for n, d, mov in planos if d > max_c and not mov})
    if longos:
        itens.append(_item("aviso", f"Planos parados por mais de {max_c:g} s", f"trechos {longos}",
                           "Divida o trecho, troque de cena ou ponha zoom no detalhe: a recomendação para Shorts é "
                           "mudar a imagem a cada 2–4 s."))
    curtos = sorted({n for n, d, _ in planos if 0.3 <= d < min_c})
    if curtos:
        itens.append(_item("aviso", f"Planos com menos de {min_c:g} s", f"trechos {curtos}",
                           "Não dá tempo de ver (ou de comparar). Alongue ou junte com o vizinho."))
    # gancho: algo escrito na tela e a fala nos primeiros instantes
    texto_inicio = bool((p.get("gancho") or {}).get("texto", "").strip())
    desl = 0.0 if projeto.relogio_da_montagem(p) else audio.migrar(p.get("audio"))["narracao"]["deslocamento"]
    primeira = min((c["palavras"][0]["start"] + desl for c in cart), default=None)
    if not texto_inicio and (primeira is None or primeira > 1.5):
        itens.append(_item("aviso", "Nada escrito na tela nos primeiros segundos",
                           "o gancho precisa funcionar sem som (imagem + texto + fala juntos nos 3 s iniciais)",
                           "Escreva o título do início na aba 6 · Textos."))
    if primeira is not None and primeira > 1.5 and p.get("legenda_origem") in ("narracao", "video"):
        itens.append(_item("dica", f"A fala começa só em {primeira:.1f} s", "", "Comece a falar no primeiro segundo."))
    if not cart:
        itens.append(_item("aviso", "Sem legenda", "a maioria assiste Shorts sem som",
                           "Aba 6 · Textos: transcreva a narração, o áudio do vídeo ou escreva à mão."))
    if 30 < total < 50:
        itens.append(_item("dica", f"Duração de {total:.0f} s", "as recomendações para Shorts favorecem < 30 s ou ~50–60 s",
                           "Corte para menos de 30 s ou desenvolva até ~50 s, se o assunto render."))
    if not timeline.tem_loop(p):
        itens.append(_item("dica", "O final não volta ao começo", "um final que emenda no início faz o replay parecer contínuo",
                           "Aba Cortes → “Fechar o loop” (repete 0,9 s do 1º plano no fim), ou termine sem despedida."))
    return itens


def _item(nivel, titulo, detalhe="", como=""):
    return {"nivel": nivel, "titulo": titulo, "detalhe": detalhe, "como_resolver": como}


def verificar_projeto(p):
    itens, d = [], projeto.pasta(p["nome"])
    total = projeto.duracao_timeline(p)
    if not p["segmentos"]:
        return [_item("erro", "A timeline está vazia", "", "Escolha os trechos na aba 2 · Cortes.")]
    for f in p["fontes"]:
        if not os.path.isfile(f["caminho"]):
            itens.append(_item("erro", f"Vídeo-fonte sumiu: {f['nome']}", f["caminho"], "Devolva o arquivo ao lugar ou adicione de novo na aba 1."))
    for tipo, nome in projeto.arquivos_de_audio(p):
        if not os.path.isfile(projeto.caminho_biblioteca(tipo, nome)):
            itens.append(_item("erro", f"Áudio da biblioteca sumiu: {nome}", f"pasta {tipo}/", "Coloque o arquivo de volta ou troque na aba 4 · Áudio."))
    curtos = [i + 1 for i, s in enumerate(p["segmentos"]) if s["fim"] - s["ini"] < 0.3]
    if curtos:
        itens.append(_item("aviso", "Trechos muito curtos (piscam na tela)", f"trechos {curtos}", "Alongue ou remova na aba Cortes."))
    # duracao x formato
    try:
        alvo = formatos.guia(p).get("duracao_alvo")
    except Exception:  # noqa: BLE001
        alvo = None
    if alvo and (total > alvo * 1.5 or total < alvo * 0.5):
        itens.append(_item("aviso", "Duração longe do alvo do formato", f"{total:.0f} s (alvo ~{alvo} s)",
                           "Ajuste os trechos ou troque o formato na aba 3 · Estilo."))
    if p.get("tipo") != "longo" and total > 180:
        itens.append(_item("aviso", "Vídeo vertical com mais de 3 minutos", f"{total:.0f} s", "Shorts aceita até 3 min; TikTok/Reels variam."))
    # narracao e legenda
    A = audio.migrar(p.get("audio"))
    narr = p.get("narracao")
    if narr:
        dn = midia.duracao(os.path.join(d, narr))
        if dn > total + 0.3 + max(A["narracao"]["deslocamento"], 0):
            itens.append(_item("aviso", "A narração é mais longa que o vídeo", f"narração {dn:.1f} s, vídeo {total:.1f} s",
                               "O fim da narração será cortado: alongue a timeline ou regrave."))
    cart_path = os.path.join(d, "legenda_cartoes.json")
    cart = json.load(open(cart_path, encoding="utf-8")) if os.path.isfile(cart_path) else []
    cart = [c for c in cart if c.get("palavras")]
    if cart:
        desl = 0.0 if projeto.relogio_da_montagem(p) else A["narracao"]["deslocamento"]
        fim_leg = max(c["palavras"][-1]["end"] for c in cart) + desl
        if fim_leg > total + 0.5:
            itens.append(_item("aviso", "Legenda passa do fim do vídeo", f"última palavra em {fim_leg:.1f} s, vídeo {total:.1f} s (o resto é cortado)",
                               "Aba 6 · Textos → 🔄 Atualizar legendas, ou exclua os cartões que sobram."))
        sobre = [i + 1 for i in range(len(cart) - 1) if cart[i + 1]["palavras"][0]["start"] < cart[i]["palavras"][0]["start"]]
        if sobre:
            itens.append(_item("erro", "Cartões de legenda fora de ordem", f"cartões {sobre}", "Corrija os tempos na aba 6 · Textos."))
        if not projeto.relogio_da_montagem(p) and not narr:
            itens.append(_item("erro", "As legendas não aparecem no vídeo", "são de uma narração e o projeto está sem narração",
                               "Aba 6 · Textos → “Mostrar no vídeo” (usa o tempo do vídeo), ou grave a narração."))
    elif narr:
        itens.append(_item("aviso", "Tem narração mas não tem legenda", "", "Aba 6 · Textos → Transcrever (legendas aumentam a retenção)."))
    itens += [i for i in verificar_retencao(p, cart, total)
              if not (i["titulo"] == "Sem legenda" and narr)]          # sem legenda com narracao ja foi avisado acima
    # react
    R = react.completar(p.get("react"))
    if R["ativo"]:
        cam = react.caminho_camera(p)
        if not cam or not os.path.isfile(cam):
            itens.append(_item("erro", "Câmera do React não encontrada", "", "Grave ou envie a câmera de novo na aba React."))
        ex = react.estado_extra(p)
        if R["recorte_ia"]["ativo"] and not ex["matte_pronto"]:
            itens.append(_item("erro", "Recorte por IA ligado mas não gerado", "", "Aba React → Gerar recorte da gravação."))
        elif R["recorte_ia"]["ativo"] and ex["matte_desatualizado"]:
            itens.append(_item("aviso", "Recorte por IA com ajustes antigos", "", "Gere o recorte de novo para aplicar os ajustes."))
        if R["modo"] == "fundo_virtual" and not R["chroma"]["ativo"] and not R["recorte_ia"]["ativo"]:
            itens.append(_item("erro", "Fundo virtual sem recorte", "a câmera inteira cobriria o jogo",
                               "Ligue o chroma key ou o recorte por IA na aba React."))
    if not [i for i in itens if i["nivel"] in ("erro", "aviso")]:       # dicas nao sao problema
        itens.append(_item("ok", "Projeto sem problemas encontrados", f"{len(p['segmentos'])} trechos, {total:.1f} s"))
    ordem = {"erro": 0, "aviso": 1, "dica": 2, "ok": 3}
    itens.sort(key=lambda i: ordem[i["nivel"]])
    return itens


def verificar_arquivo(caminho, p=None):
    """Um passe do FFmpeg no video gerado: pretos (>=0,5 s), congelado (>=2 s), silencio (>=3 s) e volume final."""
    if not os.path.isfile(caminho):
        return [_item("erro", "Arquivo não encontrado", os.path.basename(caminho), "Gere o RASCUNHO de novo.")]
    itens = []
    try:
        inf = midia.info(caminho)
    except RuntimeError as e:
        return [_item("erro", "O arquivo não abre", str(e)[:200], "Gere de novo; se repetir, veja o log do render.")]
    esperado = (1920, 1080) if (p or {}).get("tipo") == "longo" else (1080, 1920)
    if (inf["w"], inf["h"]) != esperado:
        itens.append(_item("erro", "Resolução inesperada", f"{inf['w']}×{inf['h']} (esperado {esperado[0]}×{esperado[1]})", "Gere de novo."))
    if p:
        total = projeto.duracao_timeline(p)
        if abs(inf["dur"] - total) > max(0.3, total * 0.02):
            itens.append(_item("aviso", "Duração diferente da montagem", f"{inf['dur']:.1f} s (montagem {total:.1f} s)",
                               "O projeto mudou depois deste arquivo: gere de novo."))
    if not inf["audio"]:
        itens.append(_item("erro", "Vídeo sem áudio", "", "Confira a aba 4 · Áudio (trilhas desligadas?)."))
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", caminho,
                        "-vf", "blackdetect=d=0.5:pix_th=0.10,freezedetect=n=-60dB:d=2", "-af",
                        "silencedetect=n=-45dB:d=3,ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace", creationflags=midia.SEM_JANELA)
    log = r.stderr
    pretos = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)
    if pretos:
        itens.append(_item("aviso", "Trechos pretos", ", ".join(f"{float(a):.1f}–{float(b):.1f} s" for a, b in pretos[:5]),
                           "Confira esses instantes: corte de cena escura ou trecho fora da fonte?"))
    congel = re.findall(r"freeze_start: ([\d.]+)", log)
    if congel:
        itens.append(_item("aviso", "Imagem parada por 2 s ou mais", ", ".join(f"{float(a):.1f} s" for a in congel[:5]),
                           "Normal em cena estática; se for erro, troque o trecho."))
    silencio = re.findall(r"silence_start: ([\d.]+)", log)
    if silencio:
        itens.append(_item("aviso", "Silêncio de 3 s ou mais", ", ".join(f"{float(a):.1f} s" for a in silencio[:5]),
                           "Silêncio longo derruba retenção: confira música/narração nesses pontos."))
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
    if m:
        lufs = float(m[-1])
        if not -16.5 <= lufs <= -11.5:
            itens.append(_item("aviso", "Volume final fora do padrão", f"{lufs:.1f} LUFS (alvo −14)", "Ligue a normalização na aba 4 · Áudio."))
    if not [i for i in itens if i["nivel"] != "ok"]:
        itens.append(_item("ok", "Arquivo conferido", f"{inf['w']}×{inf['h']}, {inf['dur']:.1f} s, com áudio, sem pretos/silêncios longos"))
    return itens


def rascunho_atual(p):
    c = os.path.join(projeto.pasta(p["nome"]), f"RASCUNHO_{p['nome']}.mp4")
    return c if os.path.isfile(c) and p["aprovacao"].get("rascunho_hash") == projeto.hash_conteudo(p) else None
