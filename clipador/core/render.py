"""Monta o video vertical a partir do projeto: segmentos -> layout -> legenda/gancho -> audio.

modos:
  proxy    : previa leve 540x960 sem legenda/narracao (base para gravar a narracao sincronizada)
  quadros  : PNGs de conferencia em instantes da timeline
  rascunho : RASCUNHO_<nome>.mp4 para revisao
  final    : FINAL_<nome>.mp4 - so depois que o rascunho atual foi aprovado
"""
import json
import os
import re
import subprocess
import threading
import time

from . import audio, editonny, formatos, kits, layouts, legendas, midia, projeto, react
from .midia import SEM_JANELA

CODIFICACAO = {
    "proxy": ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-c:a", "aac", "-b:a", "128k"],
    "rascunho": ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k"],
    "final": ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-c:a", "aac", "-b:a", "192k"],
}


class ErroRender(RuntimeError):
    pass


def _cartoes(d):
    c = os.path.join(d, "legenda_cartoes.json")
    if not os.path.isfile(c):
        return []
    with open(c, encoding="utf-8") as f:
        return json.load(f)


def preparar_ass(p, d=None):
    """Escreve o .ass (legenda + gancho + rotulos) na pasta do projeto. (A previa/proxy nao usa .ass: sai limpa,
    e e sobre ela que a aba Legendas desenha a previa ao vivo.)"""
    d = d or projeto.pasta(p["nome"])
    rotulos, t = [], 0.0
    C = p.get("comparacao") or {}
    for s in p["segmentos"]:
        dur = s["fim"] - s["ini"]
        if layout_efetivo(p) == "comparacao":       # rotulo do trecho ou o padrao do projeto (ex.: GTA 5 / GTA 6)
            rotulos.append((t, t + dur, s.get("rotulo_a") or C.get("rotulo_a", ""), s.get("rotulo_b") or C.get("rotulo_b", "")))
        t += dur
    L = p["legenda"]
    cfg = p.get("formato_cfg") or {}
    rank = formatos.ranking(p) if cfg.get("ranking") and len(p["segmentos"]) >= 2 else None
    caps = formatos.capitulos(p)["capitulos"] if cfg.get("capitulos") else None
    cartoes = _cartoes(d)
    if projeto.relogio_da_montagem(p):
        pass                       # audio do video ou escrita a mao: os tempos ja estao no relogio da montagem
    # sem narracao so entram legendas provisorias (tempo estimado do roteiro, para conferir o visual)
    elif not p.get("narracao"):
        cartoes = [c for c in cartoes if c.get("provisorio")]
    else:
        # legenda da narracao acompanha a trilha: mesmo deslocamento; some se a narracao estiver desligada
        n = audio.migrar(p["audio"])["narracao"]
        desl = n["deslocamento"]
        if not n["ativo"]:
            cartoes = [c for c in cartoes if c.get("provisorio")]
        elif desl:
            prov = [c for c in cartoes if c.get("provisorio")]
            cartoes = prov + legendas.deslocar([c for c in cartoes if not c.get("provisorio")], desl)
    cartoes = legendas.limitar(cartoes, t)        # nunca passa do fim do video (narracao mais longa que a montagem)
    return legendas.gerar_ass(os.path.join(d, "legenda.ass"), cartoes, estilo=L["estilo"], layout=layout_efetivo(p),
                              pos_y=L.get("pos_y"), maiusculas=L.get("maiusculas", False),
                              gancho=p["gancho"], rotulos=rotulos, dur_total=t, ranking=rank, capitulos=caps,
                              visual=L)


def legenda_srt(p):
    """Texto .srt da legenda (mesmo tempo do video: deslocamento da narracao aplicado)."""
    d = projeto.pasta(p["nome"])
    cartoes = _cartoes(d)
    if projeto.relogio_da_montagem(p):
        cartoes = [c for c in cartoes if not c.get("provisorio")]
    elif p.get("narracao"):
        n = audio.migrar(p["audio"])["narracao"]
        cartoes = legendas.deslocar([c for c in cartoes if not c.get("provisorio")], n["deslocamento"]) if n["ativo"] else []
    total = projeto.duracao_timeline(p) or None
    return legendas.gerar_srt(legendas.limitar(cartoes, total), p["legenda"].get("maiusculas", False), total)


def layout_efetivo(p):
    """Video longo e sempre 16:9 horizontal; curto nunca usa o horizontal."""
    if p.get("tipo") == "longo":
        return "horizontal"
    R = p.get("react") or {}
    if R.get("ativo") and R.get("arquivo") and R.get("modo") == "dividido":
        return "dividido"
    return "tela_cheia" if p["layout"] == "horizontal" else p["layout"]


def react_ativo(p, modo):
    """True se o render deve incluir a camera (a previa de gravacao e a de audio nao incluem)."""
    R = p.get("react") or {}
    return bool(R.get("ativo") and R.get("arquivo") and modo in ("rascunho", "final", "quadros"))


TRILHAS = ("original", "musica", "narracao", "efeitos")


def _audio_efetivo(p, solo=None):
    """Config de audio validada; com `solo`, so a trilha pedida fica ativa (pre-escuta)."""
    A = audio.migrar(p["audio"])
    if solo:
        if solo not in TRILHAS:
            raise ErroRender(f"trilha desconhecida: {solo}")
        A["original"]["ativo"] &= solo == "original"
        A["musica"]["ativo"] &= solo == "musica"
        A["narracao"]["ativo"] &= solo == "narracao"
        for e in A["efeitos"]:
            e["ativo"] &= solo == "efeitos"
        A["mix"]["ducking"] = False
        A["mix"]["normalizar"] = False   # ouve a trilha no volume que voce ajustou
    return A


def fonte_b_do_trecho(p, s):
    """Video de baixo da comparacao: o do trecho, senao o B padrao do projeto, senao o proprio video A."""
    return s.get("fonte_b") or (p.get("comparacao") or {}).get("fonte_b") or s["fonte"]


def _congelar(filtros, entrada, dur, rotulo):
    """1o quadro da entrada repetido por `dur` s (tpad clona o quadro; nada de zoompan/loop de imagem)."""
    filtros.append(f"[{entrada}:v]trim=end_frame=1,setpts=PTS-STARTPTS,"
                   f"tpad=stop_mode=clone:stop_duration={dur:.3f},trim=duration={dur:.3f}[{rotulo}]")
    return rotulo


class _Grafo:
    """Entradas (-i) e filtros do -filter_complex em montagem. `entrada()` devolve o indice usado em [i:v]/[i:a]."""

    def __init__(self):
        self.entradas, self.filtros = [], []

    def entrada(self, caminho, ini=None, dur=None, pre=()):
        self.entradas.extend(pre)
        if ini is not None:
            self.entradas.extend(["-ss", f"{ini:.3f}", "-t", f"{dur:.3f}"])
        self.entradas.extend(["-i", caminho])
        return self.entradas.count("-i") - 1


def _tela(layout):
    return (1920, 1080) if layout == "horizontal" else (1080, 1920)


def _conferir_fonte(f, ausente):
    """Recorte validado (vira parametro do FFmpeg) e arquivo presente; `ausente` = mensagem com {} no caminho."""
    if f.get("crop") and not projeto.CROP_RE.match(str(f["crop"])):
        raise ErroRender(f"recorte invalido na fonte {f['nome']}")
    if not os.path.isfile(f["caminho"]):
        raise ErroRender(ausente.format(f["caminho"]))


def _narracao_do_render(p, d, modo):
    """Caminho da narracao se ela entra neste modo (rascunho/final/audio) e o arquivo existe; senao None."""
    narr = p.get("narracao")
    narr_path = os.path.join(d, narr) if narr else None
    if modo in ("rascunho", "final", "audio") and narr_path and os.path.isfile(narr_path):
        return narr_path
    return None


def _entrada_do_trecho(g, caminho, ini, dur, congelado, rotulo):
    """Entrada de um trecho -> (indice, video). Congelado le so o comeco e repete o 1o quadro por `dur` s."""
    i = g.entrada(caminho, ini, min(dur, 0.5) if congelado else dur)
    return i, (_congelar(g.filtros, i, dur, rotulo) if congelado else i)


def _filtro_do_layout(layout):
    return {"empilhado": layouts.empilhado, "horizontal": layouts.horizontal,
            "dividido": layouts.dividido_topo}.get(layout, layouts.tela_cheia)


def _comparacao_do_trecho(g, p, s, i, dur, congelado, a, v):
    """Video B embaixo do A. `a` = (indice, video, fonte) do A -> de onde vem o som: [(indice, fonte)]."""
    ia, va, fa = a
    C = p.get("comparacao") or {}
    fb = projeto.fonte(p, fonte_b_do_trecho(p, s))
    _conferir_fonte(fb, "arquivo do vídeo B não encontrado: {} (foi movido ou apagado?)")
    ib, vb = _entrada_do_trecho(g, fb["caminho"], float(s.get("ini_b", s["ini"])), dur, congelado, f"cgb{i}")
    g.filtros.append(layouts.comparacao(va, vb, s, fa, fb, dur, v, divisoria=C.get("divisoria", True)))
    return {"a": [(ia, fa)], "b": [(ib, fb)], "ambos": [(ia, fa), (ib, fb)]}.get(C.get("audio", "a"), [(ia, fa)])


def _video_do_trecho(g, p, s, i, dur, layout):
    """Entrada(s) e filtro do layout do trecho i -> (rotulo do video, [(indice, fonte)] de onde vem o som)."""
    fa = projeto.fonte(p, s["fonte"])
    _conferir_fonte(fa, "arquivo de video nao encontrado: {} (foi movido ou apagado?)")
    congelado = bool(s.get("congelado"))       # quadro congelado: o 1o quadro do trecho parado por `dur` s
    ia, va = _entrada_do_trecho(g, fa["caminho"], s["ini"], dur, congelado, f"cg{i}")
    v = f"v{i}"
    if layout == "comparacao":
        sons = _comparacao_do_trecho(g, p, s, i, dur, congelado, (ia, va, fa), v)
    else:
        g.filtros.append(_filtro_do_layout(layout)(va, s, fa, dur, v))
        sons = [(ia, fa)]                      # de onde vem o som do trecho (trilha "original")
    if congelado:
        sons = []                              # imagem parada: sem o som do jogo (narracao/musica continuam)
    return v, sons


def _som_do_trecho(g, s, i, dur, sons, A, tem_voz):
    """[a{i}]: trilha "original" do trecho no volume dele (padrao da trilha, volume proprio ou mudo); sem som do
    video vira silencio do tamanho do trecho."""
    nivel = audio.nivel_trecho(s, A, tem_voz)
    vol = "volume=0" if nivel is None else f"volume={10 ** (nivel / 20):.4f}"
    sons = [(k, f) for k, f in sons if f["info"].get("audio")]
    if len(sons) == 2:                         # comparacao com o som dos dois videos
        for j, (k, _) in enumerate(sons):
            g.filtros.append(f"[{k}:a]{audio.FORMATO},apad,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS[a{i}_{j}]")
        g.filtros.append(f"[a{i}_0][a{i}_1]amix=inputs=2:duration=first:normalize=0,{vol}[a{i}]")
    elif sons:
        g.filtros.append(f"[{sons[0][0]}:a]{audio.FORMATO},apad,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,{vol}[a{i}]")
    else:
        g.filtros.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{dur:.3f}[a{i}]")


def _trechos(g, p, layout, A, tem_voz):
    """Video e som de cada trecho, emendados num so: [vcat][acat]."""
    pares = []
    for i, s in enumerate(p["segmentos"]):
        dur = s["fim"] - s["ini"]
        if dur <= 0.05:
            raise ErroRender(f"segmento {i + 1} tem duracao invalida")
        v, sons = _video_do_trecho(g, p, s, i, dur, layout)
        _som_do_trecho(g, s, i, dur, sons, A, tem_voz)
        pares.append(f"[{v}][a{i}]")
    g.filtros.append("".join(pares) + f"concat=n={len(pares)}:v=1:a=1[vcat][acat]")


def _camera_react(g, p, layout, total):
    """Camera do React (e o recorte por IA) sobre [vcat] -> [vreact]. Deslocamento negativo pula o comeco dela."""
    R = react.completar(p["react"])
    cam = react.caminho_camera(p)
    if not os.path.isfile(cam):
        raise ErroRender("o vídeo da câmera do React não está na pasta do projeto (react/camera.mp4)")
    d_cam = float(R["deslocamento"])
    ini, dur = (-d_cam, total - d_cam) if d_cam < 0 else (None, None)
    ci = g.entrada(cam, ini=ini, dur=dur)
    mi = None
    if R["recorte_ia"]["ativo"]:
        mt = react.caminho_matte(p)
        if not os.path.isfile(mt):
            raise ErroRender("o recorte por IA ainda não foi gerado (aba React → Gerar recorte)")
        mi = g.entrada(mt, ini=ini, dur=dur)
    extra, _ = react.aplicar(p, "vcat", ci, mi, "vreact", *_tela(layout))
    g.filtros.extend(extra)
    return "vreact"


def _logo_do_canal(g, marca, layout, total, vb):
    """Logo do kit sobre o video (por baixo das legendas) -> [vmarca]."""
    try:
        logo = kits.caminho_logo(marca["arquivo"])
    except ValueError as e:
        raise ErroRender(str(e))
    if not os.path.isfile(logo):
        raise ErroRender(f"logo não encontrado em kits/logos: {marca['arquivo']}")
    li = g.entrada(logo, pre=("-loop", "1", "-t", f"{total:.3f}"))
    g.filtros.append(kits.filtro_marca(kits.validar_marca(marca), li, vb, "vmarca", *_tela(layout)))
    return "vmarca"


def _graficos_editonny(g, p, d, vb):
    """Graficos do editonny (WebM VP9 com transparencia, 1080x1920) sobre o video, por baixo das legendas."""
    if not editonny.vertical(p):
        raise ErroRender("os gráficos do editonny são verticais (9:16) e este vídeo é 16:9: remova-os")
    for gr in p["graficos"]:
        try:
            ini, dur = float(gr["inicio"]), float(gr["duracao"])
        except (KeyError, TypeError, ValueError):
            raise ErroRender("gráfico do editonny com tempo inválido")
        if ini < 0 or not 0 < dur <= editonny.DUR_MAX:
            raise ErroRender("gráfico do editonny com tempo inválido")

    def entrada(gr):
        try:
            c = editonny.caminho_grafico(d, gr.get("arquivo"))
        except ValueError as e:
            raise ErroRender(str(e))
        if not os.path.isfile(c):
            raise ErroRender(f"gráfico não encontrado: {gr['arquivo']} (gere de novo ou remova)")
        return g.entrada(c, pre=("-c:v", "libvpx-vp9"))       # o decodificador nativo ignora a transparencia
    filtros, vb = editonny.filtros_graficos(p["graficos"], entrada, vb)
    g.filtros.extend(filtros)
    return vb


def _arquivo_da_biblioteca(tipo, nome, rotulo):
    """Caminho seguro em musicas/ ou efeitos/ (o nome vira parametro do FFmpeg) e arquivo presente."""
    try:
        c = projeto.caminho_biblioteca(tipo, nome)
    except ValueError as e:
        raise ErroRender(str(e))
    if not os.path.isfile(c):
        raise ErroRender(f"{rotulo} '{nome}' nao esta na biblioteca (pasta {tipo}/)")
    return c


def _camadas_de_audio(g, A, total, modo, narr_path):
    """Entradas de musica, narracao e efeitos + grafo de mixagem ([acat] ... -> [aout])."""
    musica = None
    m = A["musica"]
    if m["arquivo"] and m["ativo"]:
        mc = _arquivo_da_biblioteca("musicas", m["arquivo"], "musica")
        pre = ["-stream_loop", "-1"] if m["loop"] else []
        musica = (g.entrada(mc, pre=pre + ["-ss", f"{m['inicio_arquivo']:.3f}"]), midia.duracao(mc))
    voz = (g.entrada(narr_path), midia.duracao(narr_path)) if narr_path else None
    efeitos = []
    for e in A["efeitos"]:
        if e["ativo"] and e["arquivo"]:
            ec = _arquivo_da_biblioteca("efeitos", e["arquivo"], "efeito")
            efeitos.append((g.entrada(ec), e, midia.duracao(ec)))
    norm = False if modo == "proxy" else None
    return audio.grafo_mix("acat", A, total, voz=voz, musica=musica, efeitos=efeitos, normalizar=norm)


def _quadros_pedidos(tempos, total):
    quadros = sorted({int(round(t * layouts.FPS)) for t in tempos or [] if 0 <= t < total})
    if not quadros:
        raise ErroRender("nenhum instante valido para os quadros")
    return quadros


def _fechar_grafo(g, p, d, modo, layout, vb, total, tempos, mixar):
    """[vout] conforme o modo (previa reduzida, legenda .ass ou quadros escolhidos) e [aout] (mixar()).
    Devolve os quadros pedidos (modo quadros) ou None."""
    if modo == "proxy":
        g.filtros.append(f"[{vb}]scale=960:540[vout]" if layout == "horizontal" else f"[{vb}]scale=540:960[vout]")
        g.filtros.append(mixar())   # ouve jogo + musica + efeitos enquanto grava a voz
        return None
    preparar_ass(p, d)
    if modo == "quadros":
        quadros = _quadros_pedidos(tempos, total)
        sel = "+".join(f"eq(n\\,{q})" for q in quadros)
        g.filtros.append(f"[{vb}]ass=legenda.ass,select='{sel}'[vout]")
        g.filtros.append("[acat]anullsink")
        return quadros
    g.filtros.append(f"[{vb}]nullsink" if modo == "audio" else f"[{vb}]ass=legenda.ass[vout]")
    g.filtros.append(mixar())
    return None


def _linha_de_comando(g, p, d, modo, total, saida, quadros):
    """ffmpeg + entradas + grafo + mapeamento e codificacao do modo -> (cmd, total, saida ou quadros)."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats"]
    cmd += g.entradas + ["-filter_complex", ";".join(g.filtros)]
    if modo == "audio":
        saida = saida or os.path.join(d, "previa_audio.m4a")
        cmd += ["-map", "[aout]", "-t", f"{total:.3f}", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", saida]
        return cmd, total, saida
    cmd += ["-map", "[vout]"]
    if modo == "quadros":
        os.makedirs(os.path.join(d, "quadros"), exist_ok=True)
        saida = saida or os.path.join(d, "quadros", "q_%03d.png")
        cmd += ["-an", "-fps_mode", "passthrough", saida]
        return cmd, total, quadros
    cmd += ["-map", "[aout]", "-t", f"{total:.3f}"] + CODIFICACAO[modo]
    cmd += ["-ar", "48000", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if saida is None:
        saida = os.path.join(d, {"proxy": "proxy.mp4", "rascunho": f"RASCUNHO_{p['nome']}.mp4",
                                 "final": f"FINAL_{p['nome']}.mp4"}[modo])
    cmd.append(saida)
    return cmd, total, saida


def montar_comando(p, modo, tempos=None, saida=None, solo=None):
    """Comando FFmpeg do modo: trechos -> camera do React -> logo -> graficos do editonny -> legenda/quadros -> audio
    -> saida. A ordem das entradas (-i) faz parte do comando: trechos, camera, recorte, logo, graficos, musica,
    narracao, efeitos."""
    if not p["segmentos"]:
        raise ErroRender("o projeto nao tem segmentos (escolha os cortes primeiro)")
    if p["layout"] not in layouts.LAYOUTS:
        raise ErroRender(f"layout desconhecido: {p['layout']}")
    layout = layout_efetivo(p)
    d = projeto.pasta(p["nome"])
    try:
        A = _audio_efetivo(p, solo)
    except ValueError as e:
        raise ErroRender(str(e))
    narr_path = _narracao_do_render(p, d, modo)
    tem_voz = bool(narr_path and A["narracao"]["ativo"])
    g = _Grafo()
    _trechos(g, p, layout, A, tem_voz)
    total = projeto.duracao_timeline(p)
    vb = "vcat"                                   # rotulo do video montado (com a camera e o logo, se houver)
    if react_ativo(p, modo):
        vb = _camera_react(g, p, layout, total)
    marca = p.get("marca") or {}
    if marca.get("arquivo") and modo != "audio":
        vb = _logo_do_canal(g, marca, layout, total, vb)
    if p.get("graficos") and modo != "audio":
        vb = _graficos_editonny(g, p, d, vb)
    quadros = _fechar_grafo(g, p, d, modo, layout, vb, total, tempos,
                            mixar=lambda: _camadas_de_audio(g, A, total, modo, narr_path))
    return _linha_de_comando(g, p, d, modo, total, saida, quadros)


class Cancelado(ErroRender):
    pass


def executar(cmd, total, cwd, progresso=None, cancelar=None, limite_parado=180):
    """Roda o ffmpeg na pasta do projeto (por causa do ass=legenda.ass) e informa o progresso 0-1.

    - stderr e drenado numa thread (sem isso o pipe enche e o FFmpeg trava esperando);
    - `cancelar` (threading.Event) encerra o processo; FFmpeg parado ha `limite_parado` s tambem.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace",
                            cwd=cwd, creationflags=SEM_JANELA)
    ultimo = [time.time()]
    motivo = []
    erros = []

    def drenar():
        for linha in proc.stderr:
            erros.append(linha)
            del erros[:-60]

    def vigia():
        while proc.poll() is None:
            time.sleep(0.5)
            if cancelar is not None and cancelar.is_set():
                motivo.append("cancelado")
            elif time.time() - ultimo[0] > limite_parado:
                motivo.append("travado")
            if motivo:
                proc.kill()
                return

    threading.Thread(target=drenar, daemon=True).start()
    threading.Thread(target=vigia, daemon=True).start()
    for linha in proc.stdout:
        ultimo[0] = time.time()
        if linha.startswith("out_time_us=") and progresso and total > 0:
            try:
                progresso(min(int(linha.split("=")[1]) / 1e6 / total, 0.999))
            except ValueError:
                pass
    codigo = proc.wait()
    time.sleep(0.05)
    if "cancelado" in motivo:
        raise Cancelado("tarefa cancelada")
    if codigo != 0:
        if motivo:
            raise ErroRender(f"o FFmpeg travou ({limite_parado} s sem avancar) e foi encerrado. Tente de novo.")
        raise ErroRender("".join(erros).strip()[-1500:] or "ffmpeg falhou")
    if progresso:
        progresso(1.0)


def verificar_saida(caminho, total, video=True, audio=True):
    """Confere se o arquivo gerado abre, tem a duracao esperada e as trilhas certas (audio=False: exige SEM audio)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                        "-of", "json", caminho], capture_output=True, text=True, creationflags=SEM_JANELA)
    if r.returncode != 0:
        raise ErroRender("o arquivo gerado esta corrompido (ffprobe nao conseguiu abrir)")
    info = json.loads(r.stdout)
    tipos = [s.get("codec_type") for s in info.get("streams", [])]
    dur = float(info.get("format", {}).get("duration") or 0)
    if ("audio" in tipos) != audio or (video and "video" not in tipos):
        raise ErroRender("o arquivo gerado esta sem video ou com as trilhas de audio erradas")
    if abs(dur - total) > max(0.25, total * 0.02):
        raise ErroRender(f"duracao inesperada no arquivo gerado ({dur:.2f} s, esperado {total:.2f} s)")
    if video:
        v = next(s for s in info["streams"] if s.get("codec_type") == "video")
        if (v.get("width"), v.get("height")) not in ((1080, 1920), (540, 960), (1920, 1080), (960, 540), (1080, 1080), (1080, 1350)):
            raise ErroRender(f"resolucao inesperada: {v.get('width')}x{v.get('height')}")
    return {"dur": round(dur, 3)}


# layouts com versao 1:1 e o fundo minimo da faixa (empilhado: bloco nitido termina em 1164)
FAIXA_1X1 = {"empilhado": 1170, "tela_cheia": 0, "horizontal": None}


def faixa_1x1(p, layout):
    """(topo, base) em px de 1080x1920 que precisam aparecer: gancho/logo em cima, legenda (2 linhas) embaixo."""
    leg = p["legenda"].get("pos_y") or legendas.POSICOES[layout]["legenda"]
    return 270, max(FAIXA_1X1[layout], int(leg) + 110)


def exportar_1x1(p, arquivo, progresso=None):
    """Versao quadrada (1080x1080) de um RASCUNHO/FINAL ja gerado, sem renderizar de novo: recorta a faixa que
    contem a acao e a legenda. Comparacao (A em cima, B embaixo) nao cabe num quadrado."""
    d, base, origem = _saida_pronta(p, arquivo)
    layout = layout_efetivo(p)
    if layout not in FAIXA_1X1:
        raise ErroRender("este layout (comparação A×B ou React em tela dividida) não cabe em 1:1 sem cortar metade")
    i = midia.info(origem)
    if i["w"] == i["h"]:
        raise ErroRender("este arquivo já é a versão 1:1")
    if i["w"] * 5 == i["h"] * 4:
        raise ErroRender("escolha o vídeo vertical, não a versão 4:5")
    if layout == "horizontal":
        crop = f"crop=1080:1080:{(i['w'] - 1080) // 2}:0" if i["h"] == 1080 else f"crop=ih:ih,scale=1080:1080"
    else:
        topo, base_ = faixa_1x1(p, layout)
        k = i["h"] / 1920                                   # proxy em meia resolucao tambem funciona
        alt = base_ - topo
        if alt <= 1080:                                     # cabe: quadrado centrado na faixa
            y = min(max(0, topo - (1080 - alt) // 2), 1920 - 1080)
            crop = f"crop={i['w']}:{i['w']}:0:{int(y * k)},scale=1080:1080"
        else:                                               # nao cabe: faixa inteira + laterais desfocadas
            h = int(alt * k) // 2 * 2
            crop = (f"crop={i['w']}:{h}:0:{int(topo * k)},split[a][b];[b]scale={h}:{h},boxblur=30:3,"
                    f"eq=brightness=-0.2[f];[f][a]overlay=(W-w)/2:0,scale=1080:1080")
    saida = os.path.join(d, base[:-4] + "_1x1.mp4")
    sem_audio = not i["audio"]                                  # a 1:1 da versao sem audio continua sem audio
    _recodificar(["-i", origem, "-vf", crop, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                  *(["-an"] if sem_audio else ["-c:a", "copy"])], saida[:-4] + ".tmp.mp4", saida, i["dur"], d,
                 progresso, audio=not sem_audio)
    return saida


def exportar_4x5(p, arquivo, progresso=None):
    """Versao 4:5 (1080x1350, o retrato do feed do Instagram) de um RASCUNHO/FINAL ja gerado, sem renderizar de novo:
    recorta a faixa com o gancho, a acao e a legenda (a mesma da 1:1). Comparacao A×B nao cabe."""
    d, base, origem = _saida_pronta(p, arquivo)
    layout = layout_efetivo(p)
    if layout not in FAIXA_1X1:
        raise ErroRender("este layout (comparação A×B ou React em tela dividida) não cabe em 4:5 sem cortar metade")
    i = midia.info(origem)
    if i["w"] == i["h"] or i["w"] * 5 == i["h"] * 4:            # ja e a versao 1:1 ou 4:5
        raise ErroRender("escolha o vídeo vertical (não a versão 1:1 ou 4:5)")
    if layout == "horizontal":
        crop = "crop=ih*4/5:ih,scale=1080:1350"                # centro do 16:9
    else:
        topo, base_ = faixa_1x1(p, layout)
        k = i["h"] / 1920                                   # proxy em meia resolucao tambem funciona
        alt = base_ - topo
        if alt <= 1350:                                     # cabe: retrato 4:5 centrado na faixa
            y = min(max(0, topo - (1350 - alt) // 2), 1920 - 1350)
            crop = f"crop={i['w']}:{int(i['w'] * 5 / 4) // 2 * 2}:0:{int(y * k)},scale=1080:1350"
        else:                                               # nao cabe: faixa inteira + laterais desfocadas
            h = int(alt * k) // 2 * 2
            crop = (f"crop={i['w']}:{h}:0:{int(topo * k)},scale=-2:1350,split[a][b];[b]scale=1080:1350,boxblur=30:3,"
                    f"eq=brightness=-0.2[f];[f][a]overlay=(W-w)/2:0")
    saida = os.path.join(d, base[:-4] + "_4x5.mp4")
    sem_audio = not i["audio"]
    _recodificar(["-i", origem, "-vf", crop, "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                  *(["-an"] if sem_audio else ["-c:a", "copy"])], saida[:-4] + ".tmp.mp4", saida, i["dur"], d,
                 progresso, audio=not sem_audio)
    return saida

def _recodificar(args, tmp, saida, dur, d, progresso, audio=True):
    """Gera `saida` a partir de um RASCUNHO/FINAL pronto: grava no .tmp, confere com ffprobe e so entao renomeia."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats", *args,
           "-movflags", "+faststart", tmp]
    try:
        executar(cmd, dur, d, lambda f: progresso and progresso(f * 0.95), getattr(progresso, "cancelar", None))
        verificar_saida(tmp, dur, audio=audio)
        os.replace(tmp, saida)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _saida_pronta(p, arquivo):
    d = projeto.pasta(p["nome"])
    base = os.path.basename(arquivo or "")
    if not (base.startswith(("RASCUNHO_", "FINAL_")) and base.endswith(".mp4")) or ".tmp." in base:
        raise ErroRender("escolha um RASCUNHO ou FINAL já gerado")
    origem = os.path.join(d, base)
    if not os.path.isfile(origem):
        raise ErroRender("arquivo não encontrado na pasta do projeto")
    return d, base, origem


def exportar_sem_audio(p, arquivo, progresso=None):
    """Copia de um RASCUNHO/FINAL sem nenhuma trilha de audio (imagem copiada, sem recodificar): para colocar a
    musica licenciada da propria rede (TikTok/Reels so deixam fazer isso dentro do app delas)."""
    d, base, origem = _saida_pronta(p, arquivo)
    if base.endswith("_sem_audio.mp4"):
        raise ErroRender("este arquivo já é a versão sem áudio")
    dur = midia.info(origem)["dur"]
    saida = os.path.join(d, base[:-4] + "_sem_audio.mp4")
    _recodificar(["-i", origem, "-map", "0:v:0", "-c:v", "copy", "-an"], saida[:-4] + ".tmp.mp4", saida, dur, d,
                 progresso, audio=False)
    return saida


def render(p, modo, progresso=None, solo=None):
    """Gera proxy/rascunho/final/audio. Grava num .tmp e so troca pelo nome final depois de verificar."""
    d = projeto.pasta(p["nome"])
    if modo == "final":
        h = projeto.hash_conteudo(p)
        if h != p["aprovacao"].get("aprovado_hash"):
            raise ErroRender("o FINAL so pode ser gerado depois de aprovar o rascunho atual "
                             "(algo mudou desde a aprovacao, ou nada foi aprovado)")
    marca = projeto.hash_conteudo(p) if modo == "rascunho" else projeto.hash_previa(p) if modo == "proxy" else None
    cmd, total, saida = montar_comando(p, modo, solo=solo)
    base, ext = os.path.splitext(saida)
    tmp = f"{base}.tmp{ext}"
    cmd[-1] = tmp
    cancelar = getattr(progresso, "cancelar", None)
    try:
        executar(cmd, total, d, lambda f: progresso and progresso(f * 0.9), cancelar)
        if modo in ("rascunho", "final") and audio.migrar(p["audio"])["mix"]["normalizar"]:
            ajustar_loudness(tmp)
        verificar_saida(tmp, total, video=modo != "audio")
        os.replace(tmp, saida)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if progresso:
        progresso(1.0)
    if marca:
        # grava SO a marca desta saida (sob a trava): o usuario pode ter editado o projeto durante o render
        def marcar(atual):
            if modo == "rascunho":
                atual["aprovacao"]["rascunho_hash"] = marca
            else:
                atual["proxy_hash"] = marca
        projeto.alterar(p["nome"], marcar)
    return saida


def medir_loudness(caminho):
    """Loudness integrado (LUFS) do arquivo, ou None."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", caminho, "-vn", "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace", creationflags=SEM_JANELA)
    achados = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(achados[-1]) if achados else None


def ajustar_loudness(caminho, alvo=-14.0, tolerancia=0.5):
    """2a passada: o loudnorm de uma passada erra 1-2 dB em videos curtos; corrige o ganho sem recodificar o video."""
    medido = medir_loudness(caminho)
    if medido is None or abs(medido - alvo) <= tolerancia:
        return medido
    tmp = caminho + ".tmp.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", caminho, "-map", "0", "-c:v", "copy",
                        "-af", f"volume={alvo - medido:.2f}dB,alimiter=limit=0.89:level=false",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", tmp],
                       capture_output=True, text=True, errors="replace", creationflags=SEM_JANELA)
    if r.returncode == 0:
        os.replace(tmp, caminho)
    elif os.path.exists(tmp):
        os.remove(tmp)
    return medir_loudness(caminho)


def quadros(p, tempos, progresso=None):
    d = projeto.pasta(p["nome"])
    pasta_q = os.path.join(d, "quadros")
    os.makedirs(pasta_q, exist_ok=True)
    for f in os.listdir(pasta_q):
        if f.endswith(".png"):
            os.remove(os.path.join(pasta_q, f))
    cmd, total, idx_quadros = montar_comando(p, "quadros", tempos)
    executar(cmd, total, d, progresso, getattr(progresso, "cancelar", None))
    saidas = []
    for k, q in enumerate(idx_quadros, start=1):
        orig = os.path.join(pasta_q, f"q_{k:03d}.png")
        novo = os.path.join(pasta_q, f"quadro_{q / layouts.FPS:06.2f}s.png")
        if os.path.isfile(orig):
            os.replace(orig, novo)
            saidas.append(os.path.relpath(novo, d).replace("\\", "/"))
    return saidas


