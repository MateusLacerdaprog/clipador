"""Graficos de motion do EffectCraft (motor estilo After Effects, MIT/Apache) para o Clipador.

Cada receita vira um script JSX, o effectcraft-cli renderiza um WebM VP9 1080x1920 COM ALFA e, com --projeto,
o grafico entra em projeto.graficos (a mesma camada dos graficos do editonny: sobre a montagem, sob a legenda).

    python ec_grafico.py receitas
    python ec_grafico.py gerar --receita titulo --texto "..." --duracao 2.5 --saida g.webm
    python ec_grafico.py gerar --receita circulo --x 700 --y 820 --projeto NOME --inicio 4.2
    python ec_grafico.py quadros --receita titulo --texto "..." --saida previa.png   (3 quadros lado a lado)

Textos sao SEMPRE do usuario: nenhuma receita tem texto padrao.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

CLI = os.environ.get("EFFECTCRAFT_CLI", r"C:\Program Files\EffectCraft\effectcraft-cli.exe")
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))   # pasta do Clipador
W, H, FPS = 1080, 1920, 30
COR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
PRESETS_TEXTO = ("typewriter", "fadeUpCharacters", "bounceInWords", "trackingIn", "scramble", "blurIn", "jitter",
                 "dropInLines")
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

RECEITAS = {
    "titulo": "texto que entra com 'pop' (escala com overshoot) e sai com fade; sombra. Pede --texto.",
    "texto": "texto com preset de animação por letra/palavra (--animacao: " + ", ".join(PRESETS_TEXTO) + "). Pede --texto.",
    "contador": "número contando de --de até --ate (com --sufixo opcional, ex.: ' MIL'). Sem texto livre.",
    "circulo": "círculo que se desenha em volta de um ponto (--x --y --raio): 'olha aqui' no gameplay.",
    "flash": "clarão branco de tela cheia (transição de corte), 0,3–1 s.",
}


def _cor(h):
    if not COR_RE.match(h):
        raise ValueError(f"cor inválida: {h} (use #RRGGBB)")
    return [round(int(h[i:i + 2], 16) / 255, 4) for i in (1, 3, 5)]


def _js(s):
    return json.dumps(s, ensure_ascii=False)


def _texto_jsx(a):
    """Camada de texto 'T' com Arial Black, contorno preto e encolhida para caber em 960 px."""
    return f"""
var t = c.layers.addText({_js(a.texto)}); t.name = "T";
var d = t.property("Source Text").value;
d.font = "Arial-Black"; d.fontSize = {a.tamanho}; d.fillColor = {_cor(a.cor)};
d.applyStroke = true; d.strokeColor = [0,0,0]; d.strokeWidth = 10; d.strokeOverFill = false;
d.justification = ParagraphJustification.CENTER_JUSTIFY;
t.property("Source Text").setValue(d);
try {{ var r = t.sourceRectAtTime(0, false); if (r.width > 960) {{ d.fontSize = Math.floor({a.tamanho} * 960 / r.width);
  t.property("Source Text").setValue(d); }} }} catch (e) {{}}
t.property("Position").setValue([{a.x}, {a.y}]);
var sh = t.property("Effects").addProperty("Drop Shadow");
"""


def jsx(a):
    dur = a.duracao
    corpo = f'var c = app.project.items.addComp("G", {W}, {H}, 1, {dur:.3f}, {FPS});\n'
    fade_out = (f'o.setValueAtTime({max(dur - 0.25, 0):.3f}, 100); o.setValueAtTime({dur:.3f}, 0);\n'
                if dur > 0.8 else "")
    if a.receita == "titulo":
        corpo += _texto_jsx(a) + f"""
var s = t.property("Scale"); s.setValueAtTime(0, [0,0]); s.setValueAtTime(0.18, [118,118]); s.setValueAtTime(0.3, [100,100]);
var o = t.property("Opacity"); o.setValueAtTime(0, 100); {fade_out}"""
    elif a.receita == "texto":
        corpo += _texto_jsx(a) + f'var o = t.property("Opacity"); o.setValueAtTime(0, 100); {fade_out}'
    elif a.receita == "contador":
        corpo += _texto_jsx(argparse.Namespace(**{**vars(a), "texto": f"{a.ate}{a.sufixo}"})) + f"""
t.property("Source Text").expression = {_js(f"Math.round(linear(time, 0, {min(1.2, dur * 0.7):.3f}, {a.de}, {a.ate})) + {_js(a.sufixo)}")};
var o = t.property("Opacity"); o.setValueAtTime(0, 100); {fade_out}"""
    elif a.receita == "circulo":
        corpo += f"""
var L = c.layers.addShape(); L.name = "C";
var g = L.property("Contents").addProperty("ADBE Vector Group");
var el = g.property("Contents").addProperty("ADBE Vector Shape - Ellipse"); el.property("Size").setValue([{2 * a.raio}, {2 * a.raio}]);
var st = g.property("Contents").addProperty("ADBE Vector Graphic - Stroke");
st.property("Stroke Width").setValue(14); st.property("Color").setValue({_cor(a.cor)});
var tp = g.property("Contents").addProperty("ADBE Vector Filter - Trim");
tp.property("End").setValueAtTime(0, 0); tp.property("End").setValueAtTime(0.45, 100);
var tr = L.property("Transform");   // L.property("Position") pegaria o transform do GRUPO (no EffectCraft)
tr.property("Position").setValue([{a.x}, {a.y}]); tr.property("Rotation").setValue(-90);
var sh = L.property("Effects").addProperty("Drop Shadow");
var o = tr.property("Opacity"); o.setValueAtTime(0, 100); {fade_out}"""
    elif a.receita == "flash":
        corpo += f"""
var L = c.layers.addSolid([1,1,1], "F", {W}, {H}, 1);
var o = L.property("Opacity"); o.setValueAtTime(0, 0); o.setValueAtTime({dur * 0.3:.3f}, 85); o.setValueAtTime({dur:.3f}, 0);"""
    return corpo + '\nwriteLn("ok");\n'


def validar(a):
    if a.receita not in RECEITAS:
        raise ValueError(f"receita desconhecida (use: {', '.join(RECEITAS)})")
    if a.receita in ("titulo", "texto") and not (a.texto or "").strip():
        raise ValueError("esta receita precisa de --texto (o texto é do usuário)")
    if a.texto and len(a.texto) > 60:
        raise ValueError("texto com mais de 60 caracteres não cabe num gráfico de Short")
    if a.receita == "texto" and a.animacao not in PRESETS_TEXTO:
        raise ValueError(f"--animacao inválida (use: {', '.join(PRESETS_TEXTO)})")
    if a.receita == "flash" and not 0.3 <= a.duracao <= 1.0:
        raise ValueError("flash entre 0,3 e 1 s")
    if not 0.2 <= a.duracao <= 30:
        raise ValueError("duração entre 0,2 e 30 s")
    if not (0 <= a.x <= W and 0 <= a.y <= H and 20 <= a.tamanho <= 300 and 20 <= a.raio <= 500):
        raise ValueError("posição/tamanho fora da tela")
    _cor(a.cor)


def _rodar(args, tempo=600):
    r = subprocess.run([CLI, *args], capture_output=True, text=True, timeout=tempo, creationflags=SEM_JANELA)
    if r.returncode:
        raise RuntimeError(f"effectcraft-cli falhou: {(r.stderr or r.stdout).strip()[-800:]}")
    return r.stdout


def montar(a, pasta):
    """Cria o .ecproj da receita em `pasta` e devolve o caminho."""
    if not os.path.isfile(CLI):
        raise RuntimeError(f"EffectCraft não encontrado em {CLI} (ou defina EFFECTCRAFT_CLI)")
    script, proj = os.path.join(pasta, "g.jsx"), os.path.join(pasta, "g.ecproj")
    with open(script, "w", encoding="utf-8") as f:
        f.write(jsx(a))
    _rodar(["script", script, "--empty", "--save-as", proj], 120)
    if a.receita == "texto":
        _rodar(["--project", proj, "run", "layer.applyTextPreset",
                json.dumps({"layer": "T", "preset": a.animacao}), "--save"], 120)
    return proj


def conferir(webm, dur):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height:stream_tags",
                        "-of", "json", webm], capture_output=True, text=True, creationflags=SEM_JANELA)
    info = json.loads(r.stdout or "{}") if r.returncode == 0 else {}
    s = (info.get("streams") or [{}])[0]
    alfa = str((s.get("tags") or {}).get("alpha_mode") or (s.get("tags") or {}).get("ALPHA_MODE")) == "1"
    d = float((info.get("format") or {}).get("duration") or 0)
    if (s.get("width"), s.get("height")) != (W, H) or not alfa or abs(d - dur) > 0.2:
        raise RuntimeError(f"gráfico fora do esperado: {s.get('width')}x{s.get('height')}, alfa={alfa}, {d:.2f}s")


def gerar(a, saida):
    with tempfile.TemporaryDirectory(prefix="clipador-ec-") as pasta:
        proj = montar(a, pasta)
        tmp = os.path.join(pasta, "g.webm")
        _rodar(["render", "--project", proj, "--comp", "G", "--out", tmp, "--format", "webm",
                "--channels", "rgba", "--audio", "off", "--webm-codec", "vp9"])
        conferir(tmp, a.duracao)
        shutil.move(tmp, saida)


def quadros(a, saida):
    """3 quadros (início, meio, fim) lado a lado sobre xadrez cinza, para revisar sem renderizar o vídeo."""
    with tempfile.TemporaryDirectory(prefix="clipador-ec-") as pasta:
        proj = montar(a, pasta)
        pngs = []
        for k, t in enumerate((min(0.15, a.duracao / 4), a.duracao / 2, max(a.duracao - 0.05, 0))):
            p = os.path.join(pasta, f"q{k}.png")
            _rodar(["render-frame", "--project", proj, "--comp", "G", "--time", f"{t:.3f}", "--max-side", "640",
                    "--transparent", "--out", p], 120)
            pngs.append(p)
        filtro = ";".join(f"color=c=0x3a3a3a:s=360x640[b{k}];[{k}:v]scale=360:640[v{k}];[b{k}][v{k}]overlay[o{k}]"
                          for k in range(3)) + ";[o0][o1][o2]hstack=3"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *sum((["-i", p] for p in pngs), []),
                            "-filter_complex", filtro, "-frames:v", "1", saida],
                           capture_output=True, text=True, creationflags=SEM_JANELA)
        if r.returncode:
            raise RuntimeError(r.stderr.strip()[-600:])


def no_projeto(a, nome, inicio):
    """Renderiza direto para projetos/<nome>/graficos/ec-<receita>_N.webm e registra em projeto.graficos."""
    sys.path.insert(0, RAIZ)
    from clipador.core import editonny, projeto
    p = projeto.carregar(nome)
    if not editonny.vertical(p):
        raise ValueError("gráficos 9:16: só no vídeo curto")
    if len(p.get("graficos") or []) >= editonny.MAX_GRAFICOS:
        raise ValueError(f"no máximo {editonny.MAX_GRAFICOS} gráficos por projeto")
    if inicio < 0 or inicio + a.duracao > projeto.duracao_timeline(p) + 0.05:
        raise ValueError("o gráfico passa do fim da montagem")
    d = projeto.pasta(nome)
    rel = editonny._proximo_arquivo(d, f"ec-{a.receita}")
    gerar(a, os.path.join(d, *rel.split("/")))
    item = {"arquivo": rel, "cena": f"ec-{a.receita}", "nome": f"EffectCraft · {a.receita}",
            "inicio": round(inicio, 3), "duracao": round(a.duracao, 3), "estilo": "effectcraft",
            "parametros": {k: getattr(a, k) for k in ("x", "y", "cor", "tamanho", "raio", "animacao", "de", "ate",
                                                       "sufixo")},
            "textos": {"texto": a.texto} if a.texto else {}, "esconde_legenda": a.receita == "flash",
            "som_sugerido": None,
            "direitos": {"origem": "proprio", "licenca": "feito no EffectCraft (MIT OR Apache-2.0)",
                         "link": "", "obs": "", "registrado_em": None}}
    projeto.alterar(nome, lambda atual: atual.setdefault("graficos", []).append(item))
    return item


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")
    ap =argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=("receitas", "gerar", "quadros"))
    ap.add_argument("--receita")
    ap.add_argument("--texto")
    ap.add_argument("--duracao", type=float, default=2.5)
    ap.add_argument("--x", type=int, default=540)
    ap.add_argument("--y", type=int, default=230, help="padrão 230: faixa de cima, acima do bloco nítido (y=300)")
    ap.add_argument("--cor", default="#FFDE00")
    ap.add_argument("--tamanho", type=int, default=110)
    ap.add_argument("--raio", type=int, default=150)
    ap.add_argument("--animacao", default="typewriter")
    ap.add_argument("--de", type=int, default=0)
    ap.add_argument("--ate", type=int, default=100)
    ap.add_argument("--sufixo", default="")
    ap.add_argument("--saida")
    ap.add_argument("--projeto")
    ap.add_argument("--inicio", type=float, default=0.0)
    a = ap.parse_args()
    try:
        if a.acao == "receitas":
            for k, v in RECEITAS.items():
                print(f"{k:10} {v}")
            return 0
        validar(a)
        if a.acao == "quadros":
            quadros(a, a.saida or "previa_grafico.png")
            print(f"quadros -> {a.saida or 'previa_grafico.png'}")
        elif a.projeto:
            print(json.dumps(no_projeto(a, a.projeto, a.inicio), ensure_ascii=False, indent=1))
        else:
            if not a.saida:
                raise ValueError("use --saida ARQ.webm ou --projeto NOME --inicio S")
            gerar(a, a.saida)
            print(f"ok -> {a.saida}")
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
