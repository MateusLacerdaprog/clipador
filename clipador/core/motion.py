"""Motion automatico da skill effectcraft (do usuario, .claude/skills/effectcraft) na edicao do editonny.

Depois que o editonny corta e legenda o video de pessoa falando, entram graficos de motion do EffectCraft
(WebM com alfa) por cima, no alto da tela:
- titulo de abertura (receita `titulo`) com a 1a frase FALADA;
- contador (receita `contador`) quando a pessoa fala um numero;
- destaque (receita `titulo`) para pergunta/exclamacao curta e inteira no meio da fala;
- fechamento (receita `titulo`) com o fim da ultima frase falada.
Titulo cortado nunca termina em artigo/preposicao (a regra dos cartoes de legenda).
Nenhum texto e escrito pelo agente: tudo sai da transcricao da propria fala (regra do projeto). O plano fica em
projeto.motion_plano para o usuario ver; `projeto.motion = False` desliga.
"""
import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import tempfile

from . import editonny
from .midia import SEM_JANELA

SKILL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     ".claude", "skills", "effectcraft", "ec_grafico.py")
Y_TOPO = 230               # faixa de cima: acima do rosto e longe da legenda do editonny
MAX_PALAVRAS, MAX_CHARS = 5, 28
PAUSA = 0.35
MAX_CONTADORES = 2
NUM_RE = re.compile(r"^(\d{1,6})(%?)$")
# palavras que nao podem fechar um titulo cortado (a regra dos cartoes de legenda do Clipador)
FUNCAO = {"a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos", "em", "na", "no", "nas",
          "nos", "que", "e", "ou", "mas", "por", "para", "pra", "com", "se", "ao", "à", "sem", "sobre", "porque"}
MIN_LEITURA = 1.8          # tempo minimo de tela de um titulo


def _skill():
    if not os.path.isfile(SKILL):
        return None
    spec = importlib.util.spec_from_file_location("ec_grafico", SKILL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def disponivel():
    ec = _skill()
    return bool(ec and os.path.isfile(ec.CLI))


def _limpa(t):
    return re.sub(r"[^\w%$€£\-'’ ?!]", "", str(t), flags=re.UNICODE).strip()


def _palavra(t):
    return re.sub(r"[?!]", "", _limpa(t)).lower()


def frases(palavras, pausa=PAUSA):
    """Palavras agrupadas em frases pelas pausas da fala."""
    out = []
    for w in palavras:
        if out and (w["start"] - out[-1][-1]["end"] >= pausa or str(out[-1][-1]["text"]).rstrip().endswith((".", "?", "!"))):
            out.append([w])
        elif out:
            out[-1].append(w)
        else:
            out.append([w])
    return out


def _cabe(ws):
    txt = " ".join(_limpa(w["text"]) for w in ws).strip()
    return txt.upper() if txt and len(ws) <= MAX_PALAVRAS and len(txt) <= MAX_CHARS else None


def _trecho(ws, do_fim=False):
    """Maior pedaco da frase que cabe num titulo: a frase inteira, ou um pedaco de 3+ palavras que nao termina
    (nem comeca, se vem do fim) em artigo/preposicao. -> (palavras, texto) ou (None, None)."""
    if _cabe(ws):
        return ws, _cabe(ws)
    for n in range(MAX_PALAVRAS, 2, -1):
        p = ws[-n:] if do_fim else ws[:n]
        borda = p[0] if do_fim else p[-1]
        if _cabe(p) and _palavra(borda["text"]) not in FUNCAO:
            return p, _cabe(p).rstrip(",")
    return None, None


def planejar(palavras, duracao):
    """Plano de graficos a partir das palavras faladas (tempo do video editado). Sem sobreposicao entre eles."""
    palavras = [w for w in palavras if _limpa(w.get("text", ""))]
    if not palavras or duracao < 4:
        return []
    fr = frases(palavras)
    plano = []
    livre = lambda ini, dur: not any(ini < p["inicio"] + p["duracao"] and p["inicio"] < ini + dur for p in plano)
    ws, abertura = _trecho(fr[0])
    if abertura:
        ini = max(0.0, ws[0]["start"] - 0.1)
        fim = min(max(ws[-1]["end"] + 0.4, ini + MIN_LEITURA), ini + 3.0, duracao)
        plano.append({"receita": "titulo", "texto": abertura, "inicio": round(ini, 2), "duracao": round(fim - ini, 2)})
    for f in fr[1:-1]:                     # pergunta/exclamacao curta e inteira no meio: vira destaque
        txt = _cabe(f)
        if txt and len(f) <= 4 and txt.endswith(("?", "!")):
            ini = round(max(0.0, f[0]["start"] - 0.05), 2)
            dur = round(min(max(f[-1]["end"] - ini + 0.4, MIN_LEITURA), duracao - ini), 2)
            if livre(ini, dur):
                plano.append({"receita": "titulo", "texto": txt, "inicio": ini, "duracao": dur})
    for i, w in enumerate(palavras):
        m = NUM_RE.match(_limpa(w["text"]))
        if not m or len([p for p in plano if p["receita"] == "contador"]) >= MAX_CONTADORES:
            continue
        valor = int(m.group(1))
        if not 2 <= valor <= 100000:
            continue
        prox = _limpa(palavras[i + 1]["text"]) if i + 1 < len(palavras) else ""
        sufixo = m.group(2) or (" " + prox.upper() if prox.isalpha() and len(prox) <= 10 else "")
        ini, dur = round(max(0.0, w["start"] - 0.05), 2), 1.8
        if ini + dur > duracao or not livre(ini, dur):
            continue
        plano.append({"receita": "contador", "de": 0, "ate": valor, "sufixo": sufixo, "inicio": ini, "duracao": dur})
    if len(fr) >= 3:
        ultima, txt = _trecho(fr[-1], do_fim=True)
        if txt:
            ini = round(max(0.0, ultima[0]["start"] - 0.1), 2)
            dur = round(min(duracao - ini, max(ultima[-1]["end"] - ini + 0.6, MIN_LEITURA)), 2)
            if dur >= 1.2 and livre(ini, dur):
                plano.append({"receita": "titulo", "texto": txt, "inicio": ini, "duracao": dur})
    return sorted(plano, key=lambda p: p["inicio"])


def _args(item):
    base = {"receita": item["receita"], "texto": item.get("texto"), "duracao": item["duracao"], "x": 540, "y": Y_TOPO,
            "cor": "#FFDE00", "tamanho": 96, "raio": 150, "animacao": item.get("animacao", "typewriter"),
            "de": item.get("de", 0), "ate": item.get("ate", 100), "sufixo": item.get("sufixo", "")}
    if item["receita"] == "contador":
        base["tamanho"] = 130
    return argparse.Namespace(**base)


def aplicar(video_in, video_out, plano, progresso=None):
    """Renderiza cada grafico na skill effectcraft e queima sobre o video do editonny (som copiado)."""
    ec = _skill()
    if not ec:
        raise editonny.ErroEditonny("a skill effectcraft não está em .claude/skills/effectcraft")
    with tempfile.TemporaryDirectory(prefix="clipador-motion-") as pasta:
        graficos = []
        for k, item in enumerate(plano):
            a = _args(item)
            ec.validar(a)
            webm = os.path.join(pasta, f"g{k}.webm")
            if progresso:
                progresso(k / max(len(plano), 1), f"Motion {k + 1}/{len(plano)}: {item['receita']}")
            ec.gerar(a, webm)
            graficos.append({**item, "arquivo": webm})
        entradas = ["-i", video_in]

        def entrada(gr):
            entradas.extend(["-c:v", "libvpx-vp9", "-i", gr["arquivo"]])
            return entradas.count("-i") - 1
        filtros, vb = editonny.filtros_graficos(graficos, entrada, "0:v")
        tmp = os.path.join(pasta, "saida.mp4")
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", *entradas, "-filter_complex", ";".join(filtros),
                            "-map", f"[{vb}]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", tmp],
                           capture_output=True, text=True, creationflags=SEM_JANELA)
        if r.returncode:
            raise editonny.ErroEditonny(r.stderr.strip()[-800:] or "ffmpeg falhou ao aplicar o motion")
        shutil.move(tmp, video_out)
    return [{k: v for k, v in g.items() if k != "arquivo"} for g in graficos]
