"""Editor editonny por projeto: video de PESSOA FALANDO editado pelo editonny (limpeza de pausas, enquadramento e
legenda automaticos dele) ate o RASCUNHO; a aprovacao continua do usuario (aba Aprovacao) e o FINAL e a copia do
rascunho aprovado. Sem fala de pessoa o projeto fica com o editor do Clipador (regras 2 e 3 do CLAUDE.md).

Trabalho em projetos/<n>/editonny/ (edit/ = transcricoes, EDL e corte; proj/ = composicao do HyperFrames), que o
Claude pode refinar depois com a skill /editonny.
"""
import json
import os
import shutil
import subprocess

from . import editonny, midia, motion, projeto
from .midia import SEM_JANELA

EDITORES = ("clipador", "editonny")
FALA_MIN = 0.30          # fracao minima do tempo dos trechos com voz para contar como "pessoa falando"
PALAVRAS_MIN = 8
PAUSA_FRASE = 0.35       # mesma pausa da regra 2: separa as frases do EDL
MODELO = "small"         # o mesmo modelo de transcricao do Clipador (ja baixado)


def pasta_trabalho(nome):
    return os.path.join(projeto.pasta(nome), "editonny")


def definir_editor(nome, editor):
    """Clipador (padrao) ou editonny. O editonny exige som nos videos-fonte; a fala e conferida ao editar."""
    if editor not in EDITORES:
        raise ValueError(f"editor inválido (use: {', '.join(EDITORES)})")

    def fn(p):
        if editor == "editonny":
            if not editonny.instalacao():
                raise ValueError("o editonny não está instalado")
            usadas = {s["fonte"] for s in p["segmentos"]} or {f["id"] for f in p["fontes"]}
            if not usadas:
                raise ValueError("adicione o vídeo da pessoa falando antes")
            if any(not projeto.fonte(p, fid)["info"].get("audio") for fid in usadas):
                raise ValueError("o editonny edita vídeo de pessoa falando: um dos vídeos não tem som")
        p["editor"] = editor
    return projeto.alterar(nome, fn)


def frases(palavras, ini, fim, pausa=PAUSA_FRASE):
    """Intervalos [a, b] de frases (palavras separadas por pausa >= `pausa`) dentro do trecho [ini, fim]."""
    dentro = [w for w in palavras if w["start"] >= ini - 0.05 and w["end"] <= fim + 0.05]
    out = []
    for w in dentro:
        if out and w["start"] - out[-1][1] < pausa:
            out[-1][1] = w["end"]
        else:
            out.append([w["start"], w["end"]])
    return [(round(max(ini, a - 0.05), 3), round(min(fim, b + 0.12), 3)) for a, b in out if b > a]


def _voz(palavras, ini, fim):
    return sum(max(0.0, min(w["end"], fim) - max(w["start"], ini)) for w in palavras)


def montar_edl(p, transcricoes):
    """EDL do editonny a partir dos trechos da timeline (ou do video inteiro): uma faixa por frase falada.
    `transcricoes` = {fonte_id: [palavras]}. Recusa quando nao ha uma pessoa falando."""
    segs = p["segmentos"] or [{"fonte": f["id"], "ini": 0.0, "fim": f["info"]["dur"]} for f in p["fontes"][:1]]
    faixas, voz, total, n_pal = [], 0.0, 0.0, 0
    for s in segs:
        pal = transcricoes.get(s["fonte"]) or []
        ini, fim = float(s["ini"]), float(s["fim"])
        total += fim - ini
        voz += _voz(pal, ini, fim)
        n_pal += len([w for w in pal if ini <= w["start"] < fim])
        for a, b in frases(pal, ini, fim):
            faixas.append({"id": f"r{len(faixas) + 1}", "source": s["fonte"], "start": a, "end": b})
    if n_pal < PALAVRAS_MIN or not total or voz / total < FALA_MIN:
        raise ValueError(f"não achei uma pessoa falando nos trechos ({n_pal} palavras, voz em {voz / max(total, 1e-6):.0%} "
                         "do tempo): use o editor do Clipador neste projeto")
    fontes = {s["fonte"]: projeto.fonte(p, s["fonte"])["caminho"] for s in segs}
    return {"sources": fontes, "ranges": faixas,
            "output": {"format": "horizontal" if p.get("tipo") == "longo" else "vertical"}}


def _helper(raiz, nome, *args, cwd, tempo=1800):
    return editonny._rodar([editonny._python_motor(raiz), os.path.join(raiz, "engine", "helpers", f"{nome}.py"), *args],
                           cwd, raiz, tempo)


def _palavras(edit, video):
    stem = os.path.splitext(os.path.basename(video))[0]
    with open(os.path.join(edit, "transcripts", f"{stem}.json"), encoding="utf-8") as f:
        return [w for w in json.load(f).get("words", []) if str(w.get("text", "")).strip()]


def _copiar_fontes(edit, p, fids):
    """O editonny nomeia a transcricao pelo nome do arquivo: cada fonte vira um link/copia <id>.<ext> no edit/."""
    out = {}
    for fid in fids:
        f = projeto.fonte(p, fid)
        dst = os.path.join(edit, "fontes", fid + os.path.splitext(f["caminho"])[1].lower())
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(f["caminho"]):
            try:
                os.link(f["caminho"], dst)               # mesmo disco: nao ocupa espaco
            except OSError:
                shutil.copy2(f["caminho"], dst)
        out[fid] = dst
    return out


def editar(nome, progresso=None, modelo=MODELO):
    """Edicao completa pelo editonny ate o RASCUNHO_<nome>.mp4 (marcado como o rascunho atual para aprovar)."""
    raiz = editonny._exigir()
    p = projeto.carregar(nome)
    if p.get("editor") != "editonny":
        raise ValueError("este projeto usa o editor do Clipador")
    prog = progresso or (lambda f, m=None: None)
    marca = projeto.hash_conteudo(p)
    wd = pasta_trabalho(nome)
    edit, proj = os.path.join(wd, "edit"), os.path.join(wd, "proj")
    os.makedirs(edit, exist_ok=True)
    fids = list(dict.fromkeys(s["fonte"] for s in p["segmentos"])) or [p["fontes"][0]["id"]]
    copias = _copiar_fontes(edit, p, fids)
    prog(0.05, "Transcrevendo a fala (local)…")
    transc = {}
    for fid, c in copias.items():
        _helper(raiz, "transcribe", c, "--edit-dir", edit, "--model", modelo, cwd=wd)
        transc[fid] = _palavras(edit, c)
    edl = montar_edl(p, transc)
    edl["sources"] = copias
    with open(os.path.join(edit, "edl_manual.json"), "w", encoding="utf-8") as f:
        json.dump(edl, f, ensure_ascii=False, indent=1)
    prog(0.3, "Cortando pausas e respirações…")
    _helper(raiz, "waveform_cut", os.path.join(edit, "edl_manual.json"), "-o", os.path.join(edit, "edl.json"), cwd=wd)
    _helper(raiz, "render_cut", os.path.join(edit, "edl.json"), cwd=wd)
    prog(0.45, "Transcrevendo o corte (legenda)…")
    _helper(raiz, "transcribe", os.path.join(edit, "cut.mp4"), "--edit-dir", edit, "--model", modelo, "--force", cwd=wd)
    for h, args in (("face_layout", ("--edit-dir", edit, "--force")), ("align_words", (edit,))):
        try:                                         # melhoram enquadramento e tempo das palavras; sem rosto segue
            _helper(raiz, h, *args, cwd=wd, tempo=900)
        except editonny.ErroEditonny:
            pass
    prog(0.55, "Montando layout e legenda do editonny…")
    shutil.rmtree(proj, ignore_errors=True)
    py = editonny._python_motor(raiz)
    editonny._rodar([py, os.path.join(raiz, "engine", "project-template", "build.py"), "new", proj, "--edit", edit,
                     "--style", "paper"], wd, raiz, 120)
    cfg_c = os.path.join(proj, "project.json")
    with open(cfg_c, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.update(title=nome, format="16:9" if p.get("tipo") == "longo" else "9:16")
    with open(cfg_c, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    editonny._rodar([py, os.path.join(proj, "build.py"), "prepare"], proj, raiz, 180)
    editonny._rodar([py, os.path.join(proj, "build.py"), "compose"], proj, raiz, 600)
    prog(0.65, "Renderizando (HyperFrames)…")
    saida_hf = os.path.join(proj, "renders", "rascunho.mp4")
    npx = shutil.which("npx")
    if not npx:
        raise editonny.ErroEditonny("Node.js (npx) não encontrado: o HyperFrames precisa dele")
    editonny._rodar([npx, "--yes", f"hyperframes@{editonny._versao_hyperframes(proj)}", "render", "--quiet",
                     "--quality", "standard", "--output", saida_hf, "."], proj, raiz, 3600)
    d = projeto.pasta(nome)
    final = os.path.join(d, f"RASCUNHO_{p['nome']}.mp4")
    tmp = final[:-4] + ".tmp.mp4"
    plano_motion = []
    if p.get("motion", True) and motion.disponivel():       # skill effectcraft do usuario: motion com a propria fala
        prog(0.9, "Motion da skill effectcraft…")
        plano = motion.planejar(_palavras(edit, os.path.join(edit, "cut.mp4")), midia.info(saida_hf)["dur"])
        plano_motion = motion.aplicar(saida_hf, tmp, plano) if plano else []
    if not plano_motion:
        shutil.copy2(saida_hf, tmp)
    i = midia.info(tmp)
    if not i["audio"] or i["dur"] < 1:
        os.remove(tmp)
        raise editonny.ErroEditonny("o vídeo do editonny saiu sem som ou vazio")
    os.replace(tmp, final)

    def marcar(atual):
        atual["aprovacao"]["rascunho_hash"] = marca
        atual["motion_plano"] = plano_motion
    projeto.alterar(nome, marcar)
    prog(1.0, "Rascunho do editonny pronto")
    return {"arquivo": os.path.basename(final), "duracao": round(i["dur"], 2), "faixas": len(edl["ranges"]),
            "motion": plano_motion}


def final_por_copia(p):
    """FINAL do editor editonny = o RASCUNHO aprovado, copiado (sem renderizar de novo)."""
    d = projeto.pasta(p["nome"])
    origem = os.path.join(d, f"RASCUNHO_{p['nome']}.mp4")
    if not os.path.isfile(origem):
        raise ValueError("o rascunho aprovado não está mais na pasta: gere de novo")
    saida = os.path.join(d, f"FINAL_{p['nome']}.mp4")
    tmp = saida[:-4] + ".tmp.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", origem, "-c", "copy", "-movflags", "+faststart", tmp],
                       capture_output=True, text=True, creationflags=SEM_JANELA)
    if r.returncode:
        raise editonny.ErroEditonny(r.stderr.strip()[-400:] or "ffmpeg falhou ao copiar o rascunho")
    os.replace(tmp, saida)
    return saida
