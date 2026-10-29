"""Ponte com o editonny (skill de edicao de video por conversa, de Matheus Gomes: codigo MIT; cenas e midias do pacote
proprias ou CC0). Ver docs/EDITONNY.md.

O Clipador continua dono da montagem, das legendas (regra 2), do audio (regra 4) e da aprovacao. Do editonny vem:
- graficos animados: as 145 cenas (HTML/GSAP renderizadas pelo HyperFrames) viram uma camada TRANSPARENTE
  (WebM VP9 com alfa, 1080x1920) sobre a montagem, por baixo das legendas -> `projeto.graficos`;
- o aperto de pausas da narracao (`tighten_cut` do editonny), gravado em arquivo novo e com Desfazer.

Textos das cenas: o catalogo traz exemplos em ingles (titulos, precos, numeros). Nada e inventado: todo texto da
cena vem do usuario (ou e apagado de proposito com ""); senao a geracao recusa.
Instalacao: ~/.local/share/editonny (fora do OneDrive e do Git), registrada em ~/.claude/skills/editonny.
Telemetria do HyperFrames desligada em toda chamada; os ajudantes pagos do editonny (ElevenLabs/OpenRouter) nao sao usados.
"""
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata

from . import midia, projeto
from .midia import SEM_JANELA

REPO = "https://github.com/soumatheusgomes/editonny"
LICENCA = "editonny: código MIT; cenas e mídias do pacote próprias ou CC0"
ARQ_RE = re.compile(r"^graficos/[a-z0-9-]+_\d{1,3}\.webm$")
COR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")
DUR_MAX = 30.0
MAX_GRAFICOS = 40
TEXTO_MAX = 120
ESTILOS = ("night", "paper", "amber")
SEM_TELEMETRIA = {"HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1", "HF_CLI_TELEMETRY_DISABLED": "1",
                  # sem auto-atualização/instalação nem leitura de .env pelo HyperFrames
                  "HYPERFRAMES_NO_UPDATE_CHECK": "1", "HYPERFRAMES_NO_AUTO_INSTALL": "1",
                  "HYPERFRAMES_NO_CAPTURE_DOTENV": "1"}


class ErroEditonny(RuntimeError):
    pass


# ------------------------------------------------------------------ instalacao
def instalacao():
    """Pasta da skill instalada ou None. CLIPADOR_EDITONNY (testes, outra pasta) substitui os lugares padrao."""
    casa = os.path.expanduser("~")
    candidatos = ([os.environ["CLIPADOR_EDITONNY"]] if os.environ.get("CLIPADOR_EDITONNY") else
                  [os.path.join(casa, ".claude", "skills", "editonny"), os.path.join(casa, ".local", "share", "editonny")])
    for c in candidatos:
        if os.path.isfile(os.path.join(c, "SKILL.md")) and os.path.isfile(os.path.join(c, "visuals", "catalog.json")):
            return os.path.realpath(c)
    return None


def _exigir():
    raiz = instalacao()
    if not raiz:
        raise ErroEditonny("o editonny não está instalado (veja clipador/docs/EDITONNY.md)")
    return raiz


def _python_motor(raiz):
    c = os.path.join(raiz, "engine", ".venv", "Scripts" if os.name == "nt" else "bin",
                     "python.exe" if os.name == "nt" else "python")
    if not os.path.isfile(c):
        raise ErroEditonny("o motor do editonny não foi preparado (rode o install.py dele de novo)")
    return c


def _ambiente(raiz):
    return {**os.environ, **SEM_TELEMETRIA, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
            "EDITONNY_ENGINE_DIR": os.path.join(raiz, "engine")}


def _rodar(cmd, cwd, raiz, tempo=900):
    """Roda um passo do editonny (lista de argumentos, sem shell). Erro -> ErroEditonny com o fim da saida."""
    try:
        r = subprocess.run([str(c) for c in cmd], cwd=cwd, env=_ambiente(raiz), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=tempo, creationflags=SEM_JANELA)
    except subprocess.TimeoutExpired:
        raise ErroEditonny(f"o editonny passou de {tempo} s sem terminar e foi encerrado")
    except OSError as e:
        raise ErroEditonny(f"não deu para rodar o editonny: {e}")
    if r.returncode != 0:
        raise ErroEditonny(((r.stdout or "") + (r.stderr or "")).strip()[-1200:] or "o editonny falhou")
    return r.stdout


def _versao(raiz):
    try:
        with open(os.path.join(raiz, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def status():
    """Rapido (sem rodar nada): instalado, versao, numero de cenas e se o motor e o Node estao presentes."""
    raiz = instalacao()
    if not raiz:
        return {"instalado": False}
    try:
        _python_motor(raiz)
        motor = True
    except ErroEditonny:
        motor = False
    return {"instalado": True, "pasta": raiz, "versao": _versao(raiz), "cenas": len(_catalogo(raiz)),
            "motor": motor, "node": bool(shutil.which("npx")), "repositorio": REPO}


# ------------------------------------------------------------------ catalogo de cenas
def _catalogo(raiz):
    with open(os.path.join(raiz, "visuals", "catalog.json"), encoding="utf-8") as f:
        return json.load(f)["scenes"]


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s.casefold()) if not unicodedata.combining(c))


def textos_exigidos(cena):
    """Textos que o usuario precisa dar (o exemplo do catalogo nunca vai para o video): parametros de texto
    (string que nao e cor) e os textos fixos das cenas compostas."""
    out = []
    for k, info in (cena.get("parameters") or {}).items():
        d = (info or {}).get("default")
        if isinstance(d, str) and not COR_RE.match(d.strip()):
            out.append({"chave": k, "exemplo": d, "tipo": "parametro", "resumo": (info or {}).get("summary", "")})
    for t in cena.get("texts") or []:
        out.append({"chave": t, "exemplo": t, "tipo": "texto", "resumo": "texto fixo da cena"})
    return out


def _ajustes(cena):
    """Parametros opcionais (numero ou cor) com o padrao do editonny."""
    return {k: {"padrao": (i or {}).get("default"), "resumo": (i or {}).get("summary", "")}
            for k, i in (cena.get("parameters") or {}).items()
            if isinstance((i or {}).get("default"), (int, float)) or COR_RE.match(str((i or {}).get("default", "")))}


def _resumo(c):
    return {"id": c["id"], "nome": c.get("name", c["id"]), "categoria": c.get("category", ""),
            "quando": c.get("whenToUse", ""), "duracao": c.get("duration"), "min_duracao": c.get("minDuration"),
            "layout": c.get("layout"), "esconde_legenda": bool(c.get("hidesCaptions")),
            "som_sugerido": c.get("sound"), "textos": textos_exigidos(c), "ajustes": _ajustes(c)}


def catalogo(busca=""):
    """Cenas do editonny que contem todas as palavras da busca (sem acento, em qualquer campo do catalogo)."""
    palavras = _sem_acento(busca or "").split()
    out = []
    for c in _catalogo(_exigir()):
        alvo = _sem_acento(json.dumps(c, ensure_ascii=False))
        if all(w in alvo for w in palavras):
            out.append(_resumo(c))
    return out


def cena(cena_id):
    for c in _catalogo(_exigir()):
        if c["id"] == cena_id:
            return c
    raise ValueError(f"cena desconhecida no editonny: {cena_id}")


def _limpo(v):
    s = "".join(ch for ch in str(v) if ch == " " or ch.isprintable()).strip()
    if len(s) > TEXTO_MAX:
        raise ValueError(f"texto longo demais para a cena (máx. {TEXTO_MAX} caracteres): {s[:30]}…")
    return s


def validar_valores(c, parametros=None, textos=None):
    """-> (parametros, textos) validados. Todo texto exigido precisa vir do usuario; numero e cor sao opcionais."""
    parametros, textos = dict(parametros or {}), dict(textos or {})
    params_cena = c.get("parameters") or {}
    exigidos = textos_exigidos(c)
    tipos = {e["chave"]: e["tipo"] for e in exigidos}
    ajustes = _ajustes(c)
    p_ok, t_ok = {}, {}
    for k, v in parametros.items():
        if k not in params_cena:
            raise ValueError(f"a cena {c['id']} não tem o parâmetro '{k}'")
        if tipos.get(k) == "parametro":
            p_ok[k] = _limpo(v)
        elif isinstance(ajustes.get(k, {}).get("padrao"), (int, float)):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not -5000 <= v <= 5000:
                raise ValueError(f"'{k}' precisa ser um número entre -5000 e 5000")
            p_ok[k] = v
        elif COR_RE.match(str(v)):
            p_ok[k] = str(v)
        else:
            raise ValueError(f"'{k}' precisa ser uma cor no formato #rrggbb")
    for k, v in textos.items():
        if tipos.get(k) != "texto":
            raise ValueError(f"a cena {c['id']} não tem o texto fixo '{k}'")
        t_ok[k] = _limpo(v)
    faltando = [e for e in exigidos if e["chave"] not in (p_ok if e["tipo"] == "parametro" else t_ok)]
    if faltando:
        raise ValueError("a cena tem texto de exemplo que precisa ser trocado pelo seu (ou apagado com \"\"): "
                         + "; ".join(f"{e['chave']} (exemplo: “{e['exemplo']}”)" for e in faltando))
    return p_ok, t_ok


def aplicar_valores(conteudo, parametros, textos):
    """Troca os valores no bloco `var P = {...}` e os textos fixos (entre tags) da copia da cena no projeto."""
    if parametros:
        ini = conteudo.find("var P = {")
        fim = conteudo.find("};", ini)
        if ini < 0 or fim < 0:
            raise ErroEditonny("a cena não tem o bloco de parâmetros esperado (a versão do editonny mudou?)")
        bloco = conteudo[ini:fim]
        for k, v in parametros.items():
            lit = json.dumps(v, ensure_ascii=False).replace("</", "<\\/")
            padrao = re.compile(r"(^\s*" + re.escape(k) + r"\s*:\s*)(\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'|-?[\d.]+)",
                                re.M)
            bloco, n = padrao.subn(lambda m, lit=lit: m.group(1) + lit, bloco, count=1)
            if not n:
                raise ErroEditonny(f"parâmetro '{k}' não encontrado na cena (a versão do editonny mudou?)")
        conteudo = conteudo[:ini] + bloco + conteudo[fim:]
    for orig, novo in textos.items():
        padrao = re.compile(r"(>\s*)" + re.escape(html.escape(orig, quote=False)) + r"(\s*<)")
        conteudo, n = padrao.subn(lambda m, novo=novo: m.group(1) + html.escape(novo, quote=False) + m.group(2),
                                  conteudo)
        if not n:
            raise ErroEditonny(f"texto “{orig}” não encontrado na cena (a versão do editonny mudou?)")
    return conteudo


FUNDO_OPACO = (("html,body{", "background:#000}", "background:transparent}"),
               ("#root{", "background:#000;", "background:transparent;"))


def fundo_transparente(conteudo):
    """O index.html gerado pinta a pagina de preto; sem isso o render .mov nao tem transparencia."""
    for regra, antes, depois in FUNDO_OPACO:
        i = conteudo.find(regra)
        j = conteudo.find("}", i)
        if i < 0 or antes not in conteudo[i:j + 1]:
            raise ErroEditonny("não deu para deixar o fundo transparente (a versão do editonny mudou?)")
        conteudo = conteudo[:i] + conteudo[i:j + 1].replace(antes, depois, 1) + conteudo[j + 1:]
    return conteudo


# ------------------------------------------------------------------ graficos sobre a montagem
def caminho_grafico(d, arquivo):
    """Caminho seguro de um grafico do projeto (vira parametro do FFmpeg): so graficos/<cena>_<n>.webm."""
    if not ARQ_RE.match(str(arquivo or "")):
        raise ValueError(f"arquivo de gráfico inválido: {arquivo}")
    return os.path.join(d, *arquivo.split("/"))


def vertical(p):
    """Graficos do editonny sao 9:16: valem para o curto (o longo e sempre 16:9)."""
    return p.get("tipo") != "longo"


def _edicao_transparente(pasta_ed, dur):
    """Pasta de 'corte' que o editonny exige, com um video transparente e mudo do tamanho do grafico."""
    os.makedirs(os.path.join(pasta_ed, "transcripts"))
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        f"color=c=black@0.0:s=1080x1920:r=30:d={dur:.3f},format=yuva420p", "-f", "lavfi", "-i",
                        "anullsrc=r=48000:cl=stereo", "-t", f"{dur:.3f}", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                        "-auto-alt-ref", "0", "-c:a", "libopus", "-shortest", os.path.join(pasta_ed, "cut.webm")],
                       capture_output=True, text=True, creationflags=SEM_JANELA)
    if r.returncode:
        raise ErroEditonny(r.stderr.strip()[-600:] or "ffmpeg falhou ao preparar o grafico")
    with open(os.path.join(pasta_ed, "cut_timeline.json"), "w", encoding="utf-8") as f:
        json.dump({"duration": dur, "fps": 30, "width": 1080, "height": 1920,
                   "segments": [{"out_start": 0, "out_end": dur, "source": "cut.webm", "start": 0, "end": dur}]}, f)
    with open(os.path.join(pasta_ed, "transcripts", "cut.json"), "w", encoding="utf-8") as f:
        json.dump({"words": []}, f)


def _versao_hyperframes(pasta_proj):
    with open(os.path.join(pasta_proj, "package.json"), encoding="utf-8") as f:
        m = re.search(r"hyperframes@(\d+\.\d+\.\d+)", f.read())
    if not m:
        raise ErroEditonny("versão do HyperFrames não encontrada no projeto do editonny")
    return m.group(1)


def _proximo_arquivo(d, cena_id):
    os.makedirs(os.path.join(d, "graficos"), exist_ok=True)
    for k in range(1, 1000):
        rel = f"graficos/{cena_id}_{k}.webm"
        if not os.path.exists(os.path.join(d, *rel.split("/"))):
            return rel
    raise ErroEditonny("gráficos demais neste projeto")


def _conferir_webm(caminho, dur):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height:stream_tags",
                        "-of", "json", caminho], capture_output=True, text=True, creationflags=SEM_JANELA)
    info = json.loads(r.stdout or "{}") if r.returncode == 0 else {}
    s = (info.get("streams") or [{}])[0]
    ok_alfa = str((s.get("tags") or {}).get("alpha_mode") or (s.get("tags") or {}).get("ALPHA_MODE")) == "1"
    if (s.get("width"), s.get("height")) != (1080, 1920) or not ok_alfa or \
            abs(float((info.get("format") or {}).get("duration") or 0) - dur) > 0.2:
        raise ErroEditonny("o gráfico gerado não saiu como esperado (1080x1920 com transparência e a duração pedida)")


def conferir_pedido(nome, cena_id, inicio, duracao=None, parametros=None, textos=None, estilo="night"):
    """Valida o pedido de grafico antes da tarefa demorada -> (cena, inicio, duracao, parametros, textos)."""
    _exigir()
    c = cena(cena_id)
    p = projeto.carregar(nome)
    if not vertical(p):
        raise ValueError("os gráficos do editonny são verticais (9:16): use num vídeo curto")
    if estilo not in ESTILOS:
        raise ValueError(f"estilo inválido (use: {', '.join(ESTILOS)})")
    if len(p.get("graficos") or []) >= MAX_GRAFICOS:
        raise ValueError(f"no máximo {MAX_GRAFICOS} gráficos por projeto")
    dur = float(duracao if duracao is not None else c.get("duration") or 4.0)
    inicio = float(inicio)
    total = projeto.duracao_timeline(p)
    if not 0.2 <= dur <= DUR_MAX:
        raise ValueError(f"duração do gráfico entre 0,2 e {DUR_MAX:.0f} s")
    if c.get("minDuration") and dur < float(c["minDuration"]) - 1e-6:
        raise ValueError(f"esta cena precisa de pelo menos {c['minDuration']} s")
    if inicio < 0 or inicio + dur > total + 0.05:
        raise ValueError(f"o gráfico ({inicio:.2f}–{inicio + dur:.2f} s) passa do fim da montagem ({total:.2f} s)")
    params, txts = validar_valores(c, parametros, textos)
    return c, inicio, dur, params, txts


def gerar_grafico(nome, cena_id, inicio, duracao=None, parametros=None, textos=None, estilo="night", progresso=None):
    """Renderiza a cena do editonny (transparente) e a coloca na montagem em `inicio` (s no tempo da montagem).
    Leva 1-2 min (o 1o uso baixa o HyperFrames fixado pelo editonny). Devolve o item de projeto.graficos."""
    raiz = _exigir()
    c, inicio, dur, params, txts = conferir_pedido(nome, cena_id, inicio, duracao, parametros, textos, estilo)
    py, build = _python_motor(raiz), os.path.join(raiz, "engine", "project-template", "build.py")
    prog = progresso or (lambda f, m=None: None)
    trabalho = tempfile.mkdtemp(prefix="clipador-editonny-")
    try:
        ed, pr = os.path.join(trabalho, "edit"), os.path.join(trabalho, "proj")
        prog(0.05, "Preparando a cena…")
        _edicao_transparente(ed, dur)
        _rodar([py, build, "new", pr, "--edit", ed, "--style", estilo], trabalho, raiz, 120)
        cfg_c = os.path.join(pr, "project.json")
        with open(cfg_c, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg.update(title=cena_id, video="cut.webm", blocks=[{"scene": "fullscreen", "start": 0}])
        cfg["captions"]["enabled"] = False                 # legenda e do Clipador (regra 2)
        with open(cfg_c, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        _rodar([py, os.path.join(raiz, "visuals", "apply.py"), "--project", pr, "--use", cena_id,
                "--start", "0", "--end", f"{dur:.3f}"], trabalho, raiz, 120)
        with open(cfg_c, encoding="utf-8") as f:
            arq_cena = os.path.join(pr, *json.load(f)["scenes"][-1]["file"].split("/"))
        with open(arq_cena, encoding="utf-8") as f:
            conteudo = aplicar_valores(f.read(), params, txts)
        with open(arq_cena, "w", encoding="utf-8") as f:
            f.write(conteudo)
        prog(0.15, "Montando a composição…")
        _rodar([py, os.path.join(pr, "build.py"), "prepare"], pr, raiz, 180)     # o build.py da copia do projeto
        _rodar([py, os.path.join(pr, "build.py"), "compose"], pr, raiz, 300)
        indice = os.path.join(pr, "index.html")
        with open(indice, encoding="utf-8") as f:
            conteudo = fundo_transparente(f.read())
        with open(indice, "w", encoding="utf-8") as f:
            f.write(conteudo)
        prog(0.25, "Renderizando o gráfico (HyperFrames)…")
        mov = os.path.join(pr, "renders", "grafico.mov")
        npx = shutil.which("npx")
        if not npx:
            raise ErroEditonny("Node.js (npx) não encontrado: o HyperFrames precisa dele")
        _rodar([npx, "--yes", f"hyperframes@{_versao_hyperframes(pr)}", "render", "--format", "mov", "--quiet",
                "--output", mov, "."], pr, raiz, 1200)
        prog(0.85, "Compactando com transparência…")
        d = projeto.pasta(nome)
        rel = _proximo_arquivo(d, cena_id)
        final = os.path.join(d, *rel.split("/"))
        tmp = final[:-5] + ".tmp.webm"
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mov, "-an", "-t", f"{dur:.3f}", "-c:v", "libvpx-vp9",
                            "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "30", "-row-mt", "1", "-deadline", "good",
                            "-cpu-used", "4", tmp], capture_output=True, text=True, creationflags=SEM_JANELA)
        if r.returncode:
            raise ErroEditonny(r.stderr.strip()[-600:] or "ffmpeg falhou ao compactar o gráfico")
        _conferir_webm(tmp, dur)
        os.replace(tmp, final)
    finally:
        shutil.rmtree(trabalho, ignore_errors=True)
    item = {"arquivo": rel, "cena": cena_id, "nome": c.get("name", cena_id), "inicio": round(inicio, 3),
            "duracao": round(dur, 3), "estilo": estilo, "parametros": params, "textos": txts,
            "esconde_legenda": bool(c.get("hidesCaptions")), "som_sugerido": c.get("sound"),
            "direitos": {"origem": "licenciado", "licenca": LICENCA, "link": REPO, "obs": "", "registrado_em": None}}
    projeto.alterar(nome, lambda atual: atual.setdefault("graficos", []).append(item))
    prog(1.0, "Gráfico pronto")
    return item


def mover_grafico(nome, i, inicio):
    """Muda o instante do grafico i (o arquivo nao muda)."""
    def fn(p):
        g = (p.get("graficos") or [])
        if not 0 <= i < len(g):
            raise IndexError("gráfico não existe")
        ini = float(inicio)
        if ini < 0 or ini + g[i]["duracao"] > projeto.duracao_timeline(p) + 0.05:
            raise ValueError("o gráfico passaria do fim da montagem")
        g[i]["inicio"] = round(ini, 3)
    return projeto.alterar(nome, fn)


def remover_grafico(nome, i):
    """Tira o grafico i da montagem e apaga o arquivo dele."""
    removido = {}

    def fn(p):
        g = p.get("graficos") or []
        if not 0 <= i < len(g):
            raise IndexError("gráfico não existe")
        removido.update(g.pop(i))
    p = projeto.alterar(nome, fn)
    try:
        os.remove(caminho_grafico(projeto.pasta(nome), removido["arquivo"]))
    except (OSError, ValueError):
        pass
    return p


def filtros_graficos(graficos, entrada, vb):
    """Entradas e filtros dos graficos sobre [vb] -> (filtros, rotulo final). `entrada(caminho)` -> indice do -i.
    O WebM com alfa precisa do decodificador libvpx (o nativo do FFmpeg ignora a transparencia)."""
    filtros = []
    for k, gr in enumerate(graficos):
        ini, dur = float(gr["inicio"]), float(gr["duracao"])
        i = entrada(gr)
        filtros.append(f"[{i}:v]format=yuva420p,setpts=PTS-STARTPTS+{ini:.3f}/TB[gr{k}]")
        filtros.append(f"[{vb}][gr{k}]overlay=0:0:eof_action=pass:enable='between(t\\,{ini:.3f}\\,{ini + dur:.3f})'"
                       f"[vgr{k}]")
        vb = f"vgr{k}"
    return filtros, vb


# ------------------------------------------------------------------ narracao sem pausas
def _video_da_narracao(wav, saida):
    """O tighten_cut do editonny trabalha com video: a narracao vai sobre uma imagem parada pequena."""
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=30", "-i", wav,
                        "-shortest", "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le",
                        saida], capture_output=True, text=True, creationflags=SEM_JANELA)
    if r.returncode:
        raise ErroEditonny(r.stderr.strip()[-600:] or "ffmpeg falhou ao preparar a narração")


def plano_de_cortes(sidecar):
    """Cortes do arquivo .cut.json do tighten_cut: [{ini, fim, pausa}] em segundos da narracao original."""
    with open(sidecar, encoding="utf-8") as f:
        d = json.load(f)
    return [{"ini": round(float(c["removed"][0]), 3), "fim": round(float(c["removed"][1]), 3),
             "pausa": round(float(c["pause"][1]) - float(c["pause"][0]), 3)} for c in d.get("cuts") or []]


def apertar_narracao(nome, aplicar=False, pausa_max=0.15, pausa_min=0.25, progresso=None):
    """Plano (ou aplicacao) do aperto de pausas da narracao pelo editonny: pausas >= pausa_min viram pausa_max.
    Aplicar grava narracao_sem_pausas.wav e passa o projeto a usa-la (Desfazer volta a anterior)."""
    raiz = _exigir()
    p = projeto.carregar(nome)
    if not p.get("narracao"):
        raise ValueError("o projeto ainda não tem narração")
    if not (0.05 <= float(pausa_max) <= 1.0 and float(pausa_max) < float(pausa_min) <= 3.0):
        raise ValueError("pausas: máxima entre 0,05 e 1 s e menor que a mínima (até 3 s)")
    d = projeto.pasta(nome)
    wav = os.path.join(d, p["narracao"])
    if not os.path.isfile(wav):
        raise ValueError("arquivo da narração não encontrado na pasta do projeto")
    prog = progresso or (lambda f, m=None: None)
    trabalho = tempfile.mkdtemp(prefix="clipador-narracao-")
    try:
        mov = os.path.join(trabalho, "narracao.mov")
        _video_da_narracao(wav, mov)
        saida = os.path.join(trabalho, "apertada.mp4")
        prog(0.2, "Medindo as pausas…")
        cmd = [_python_motor(raiz), os.path.join(raiz, "engine", "helpers", "tighten_cut.py"), mov,
               "--pause-max", f"{float(pausa_max):.3f}", "--pause-min", f"{float(pausa_min):.3f}", "--output", saida]
        log = _rodar(cmd + ([] if aplicar else ["--only-plan"]), trabalho, raiz, 900)
        sidecar = next((os.path.join(trabalho, f) for f in os.listdir(trabalho) if f.endswith(".cut.json")), None)
        cortes = plano_de_cortes(sidecar) if sidecar else []
        antes = midia.duracao(wav)
        plano = {"cortes": cortes, "antes": round(antes, 2), "removido": round(sum(c["fim"] - c["ini"] for c in cortes), 2),
                 "relatorio": [l for l in log.splitlines() if l.strip()][-20:],
                 "aviso": ("A narração foi gravada sobre a montagem: tirar pausas adianta as falas seguintes em relação "
                           "à imagem. Use quando a montagem vier depois da narração, ou confira o sincronismo na prévia.")}
        if not aplicar:
            return plano
        prog(0.8, "Gravando a narração sem pausas…")
        novo = "narracao_sem_pausas.wav"
        tmp = os.path.join(d, novo + ".tmp.wav")
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", saida, "-vn", "-c:a", "pcm_s16le", "-ar", "48000", tmp],
                           capture_output=True, text=True, creationflags=SEM_JANELA)
        if r.returncode or not os.path.isfile(tmp):
            raise ErroEditonny((r.stderr or "").strip()[-600:] or "ffmpeg falhou ao extrair a narração")
        os.replace(tmp, os.path.join(d, novo))
    finally:
        shutil.rmtree(trabalho, ignore_errors=True)

    def fn(atual):
        if atual.get("narracao") != novo:
            atual["narracao_anterior"] = atual.get("narracao")
        atual["narracao"] = novo
    projeto.alterar(nome, fn)
    plano["depois"] = round(midia.duracao(os.path.join(d, novo)), 2)
    plano["arquivo"] = novo
    return plano


def desfazer_aperto(nome):
    """Volta a usar a narracao de antes do aperto (o arquivo sem pausas fica na pasta)."""
    def fn(p):
        ant = p.get("narracao_anterior")
        if not ant or not os.path.isfile(os.path.join(projeto.pasta(nome), ant)):
            raise ValueError("não há narração anterior para voltar")
        p["narracao"], p["narracao_anterior"] = ant, None
    return projeto.alterar(nome, fn)
