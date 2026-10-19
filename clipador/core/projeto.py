"""Modelo do projeto: um projeto.json por pasta em projetos/<nome>/ (versionado, migrado ao carregar)."""
import copy
import hashlib
import json
import os
import re
import threading
import time
import uuid

from . import audio

RAIZ = os.environ.get("CLIPADOR_PROJETOS") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "projetos")
VERSAO = 2

PADRAO = {
    "versao": VERSAO,
    "nome": "",
    "tipo": "curto",       # curto (vertical 9:16) | longo (horizontal 16:9)
    "formato": None,       # guias | noticias | gameplay | curiosidades | compilados | None (livre)
    "formato_cfg": {"ranking": False, "capitulos": False, "duracao_alvo": None},
    "fontes": [],          # [{id, caminho, nome, info{dur,w,h,fps,audio}, crop, cenas[]}]
    "segmentos": [],       # [{id, fonte, ini, fim, foco_x, zoom, fonte_b, ini_b, rotulo_a, rotulo_b, audio{}}]
    "layout": "tela_cheia",  # tela_cheia | empilhado | comparacao
    "gancho": {"texto": "", "ate": 3.0},
    "legenda": {"estilo": "karaoke", "pos_y": None, "maiusculas": False, "plataforma": None, "fonte": None,
                "tamanho": None, "contorno": None, "sombra": None, "cor": None, "destaque": None, "animacao": None},
    "audio": None,         # trilhas de audio (formato em core/audio.py; migrado automaticamente)
    "narracao": None,      # nome do arquivo .wav dentro da pasta do projeto
    "roteiro": "",
    "publicacao": {"titulo": "", "descricao": "", "hashtags": []},   # texto para postar por rede (core/publicacao.py)
    "referencia": None,    # id do perfil de referencia editorial escolhido
    "react": None,         # camera sobre o video (formato em core/react.py)
    "marca": {"arquivo": None, "pos": "sup_dir", "tamanho": 0.14, "opacidade": 0.85},  # logo (core/kits.py)
    # layout comparacao: video A (em cima) e B (embaixo) padrao dos trechos, rotulos, de onde vem o som, linha
    "comparacao": {"fonte_a": None, "fonte_b": None, "rotulo_a": "", "rotulo_b": "", "audio": "a", "divisoria": True},
    "aprovacao": {"rascunho_hash": None, "aprovado_hash": None},
    "legenda_origem_anterior": None,   # origem dos cartoes guardados para o Desfazer (legenda_cartoes.anterior.json)
    "legenda_base": None,          # base_legenda() na hora da transcricao (detecta legenda desatualizada)
    "legenda_origem": "narracao",   # narracao (tempos no relogio da narracao) | video (audio do video, relogio da montagem)
    "proxy_hash": None,             # versao da montagem usada na ultima previa (proxy.mp4)
    "canal": None,                  # canal do estudio (core/canais.py) — limite diario, originalidade, resultados
    "roteiro_id": None,             # roteiro aprovado que originou o projeto (core/roteiros.py)
    "publicacao_registro": None,    # {url, video_id, registrado_em}: o USUARIO publicou e informou o link (core/esteira.py)
    "graficos": [],                 # cenas do editonny sobre a montagem: [{arquivo, cena, inicio, duracao, ...}] (core/editonny.py)
    "narracao_anterior": None,      # narracao de antes do aperto de pausas (Desfazer)
    "editor": "clipador",           # clipador | editonny (pessoa falando: legenda e layout do editonny; core/editonny_fala.py)
    "revisao_nota": "",             # pedido de ajuste escrito pelo usuario na aba Aprovacao
}

# bibliotecas de audio compartilhadas entre projetos (o usuario coloca os arquivos)
BIBLIOTECAS = {
    "musicas": os.path.join(os.path.dirname(RAIZ), "musicas"),
    "efeitos": os.path.join(os.path.dirname(RAIZ), "efeitos"),
}
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".opus", ".webm", ".mp4")
CROP_RE = re.compile(r"^\d{1,5}:\d{1,5}:\d{1,5}:\d{1,5}$")


def caminho_biblioteca(tipo, nome):
    """Caminho seguro de um arquivo da biblioteca (basename: nunca sai da pasta)."""
    if tipo not in BIBLIOTECAS:
        raise ValueError("biblioteca desconhecida")
    base = os.path.basename(str(nome or "").replace("\\", "/"))
    if not base or base in (".", ".."):
        raise ValueError("nome de arquivo invalido")
    return os.path.join(BIBLIOTECAS[tipo], base)


def caminho_musica(nome):
    return caminho_biblioteca("musicas", nome)


def slug(nome):
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", nome.strip().lower()).strip("-")
    return s or "projeto"


def pasta(nome):
    return os.path.join(RAIZ, slug(nome))


def novo_id():
    return uuid.uuid4().hex[:8]


def _completar(p):
    out = copy.deepcopy(PADRAO)
    for k, v in p.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    out["audio"] = audio.migrar(out.get("audio"))
    from . import publicacao, react, recursos
    out["react"] = react.completar(out.get("react"))
    out["publicacao"] = publicacao.completar(out.get("publicacao"))
    for f in out["fontes"]:                    # origem/licenca de cada video (projetos antigos: "nao_informado")
        f["direitos"] = recursos.completar(f.get("direitos"))
    out["versao"] = VERSAO
    return out


def listar():
    if not os.path.isdir(RAIZ):
        return []
    return sorted(d for d in os.listdir(RAIZ) if os.path.isfile(os.path.join(RAIZ, d, "projeto.json")))


def criar(nome):
    s = slug(nome)
    d = pasta(s)
    if os.path.exists(os.path.join(d, "projeto.json")):
        raise FileExistsError(f"projeto '{s}' ja existe")
    os.makedirs(d, exist_ok=True)
    p = _completar({"nome": s})
    salvar(p)
    return p


_TRAVAS, _TRAVA_GERAL = {}, threading.Lock()


def trava(nome):
    """Trava do projeto (reentrante): leitura-alteracao-gravacao de tarefas em segundo plano nao se atropela."""
    with _TRAVA_GERAL:
        return _TRAVAS.setdefault(slug(nome), threading.RLock())


def _com_nova_tentativa(acao, tentativas=6):
    """OneDrive e antivirus seguram o arquivo por instantes (PermissionError no Windows): tenta de novo, com espera curta."""
    for i in range(tentativas):
        try:
            return acao()
        except PermissionError:
            if i == tentativas - 1:
                raise
            time.sleep(0.1 * (i + 1))


def carregar(nome):
    def ler():
        with open(os.path.join(pasta(nome), "projeto.json"), encoding="utf-8") as f:
            return json.load(f)
    return _completar(_com_nova_tentativa(ler))


def salvar(p):
    """Gravacao atomica (temporario unico + replace, com nova tentativa): uma queda no meio nunca corrompe o projeto,
    e duas gravacoes ao mesmo tempo (outra tarefa, outro processo) nao disputam o mesmo temporario."""
    d = pasta(p["nome"])
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f"projeto.json.{os.getpid()}.{threading.get_ident()}.tmp")
    with trava(p["nome"]):
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=1)
        try:
            _com_nova_tentativa(lambda: os.replace(tmp, os.path.join(d, "projeto.json")))
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


def alterar(nome, fn):
    """Le o projeto do disco, aplica fn(p) e grava, tudo sob a trava: para tarefas longas mudarem SO o que e delas
    sem apagar o que o usuario editou enquanto elas rodavam. Devolve o projeto gravado."""
    with trava(nome):
        p = carregar(nome)
        fn(p)
        salvar(p)
        return p


def nome_livre(base):
    """Primeiro nome sem projeto: base-b, base-c, ... (teste A/B de gancho: a copia leva a letra da variacao)."""
    raiz = re.sub(r"-[b-z]$", "", slug(base))
    for letra in "bcdefghijklmnopqrstuvwxyz":
        n = f"{raiz}-{letra}"
        if not os.path.exists(pasta(n)):
            return n
    raise FileExistsError("variações demais deste projeto")


def duplicar(origem, novo=None):
    """Copia o projeto (montagem, narracao, legendas, camera, caches) para testar outra versao, por exemplo outro
    gancho. Os videos-fonte nao sao copiados (o caminho e o mesmo) e RASCUNHO/FINAL/quadros ficam de fora: a copia
    comeca sem aprovacao. Devolve o projeto novo."""
    import shutil
    p = carregar(origem)
    novo = slug(novo) if novo else nome_livre(origem)
    d_o, d_n = pasta(origem), pasta(novo)
    if os.path.exists(d_n):
        raise FileExistsError(f"projeto '{novo}' ja existe")

    def ignorar(dirpath, nomes):
        if os.path.normcase(os.path.abspath(dirpath)) != os.path.normcase(os.path.abspath(d_o)):
            return []
        return [n for n in nomes if n.startswith(("RASCUNHO_", "FINAL_")) or n == "quadros" or ".tmp" in n]
    with trava(origem):
        shutil.copytree(d_o, d_n, ignore=ignorar)
    p["nome"] = novo
    p["aprovacao"] = {"rascunho_hash": None, "aprovado_hash": None}
    salvar(p)
    return carregar(novo)


def fonte(p, fid):
    for f in p["fontes"]:
        if f["id"] == fid:
            return f
    raise KeyError(f"fonte {fid} nao existe")


def duracao_timeline(p):
    return sum(max(0.0, s["fim"] - s["ini"]) for s in p["segmentos"])


def arquivos_de_audio(p):
    """[(tipo, nome)] dos arquivos de biblioteca usados pelo projeto."""
    a = p["audio"]
    usados = []
    if a["musica"].get("arquivo"):
        usados.append(("musicas", a["musica"]["arquivo"]))
    usados += [("efeitos", e["arquivo"]) for e in a["efeitos"] if e.get("arquivo")]
    return usados


def _assinatura(caminho):
    try:
        st = os.stat(caminho)
        return f"{st.st_size}:{int(st.st_mtime)}"
    except OSError:
        return "ausente"


def hash_previa(p):
    """Impressao digital do que aparece na PREVIA (proxy.mp4): imagem, gancho, legenda, logo e som do jogo/musica.
    Narracao e camera ficam de fora (a previa e justamente a base para grava-las)."""
    relevante = copy.deepcopy({k: p.get(k) for k in ("fontes", "segmentos", "layout", "gancho", "audio",
                                                     "tipo", "formato_cfg", "marca", "comparacao")})
    for f in relevante["fontes"]:
        f.pop("cenas", None)
        f.pop("destaques", None)
        f.pop("direitos", None)               # registro de licenca nao muda a imagem
    if relevante.get("audio"):
        relevante["audio"] = {k: v for k, v in relevante["audio"].items() if k != "narracao"}
    if relevante["layout"] != "comparacao":      # so muda o video na comparacao (nao invalida projetos antigos)
        relevante.pop("comparacao")
    if p.get("graficos"):
        relevante["graficos"] = [{k: gr.get(k) for k in ("arquivo", "inicio", "duracao")} for gr in p["graficos"]]
    return hashlib.sha1(json.dumps(relevante, sort_keys=True).encode()).hexdigest()[:16]


ORIGENS_LEGENDA = ("narracao", "video", "manual")


def relogio_da_montagem(p):
    """Legenda no tempo do VIDEO (audio do video ou escrita a mao) e sempre visivel. A da narracao fica no
    relogio da narracao (o deslocamento da trilha entra no render) e some sem narracao."""
    return p.get("legenda_origem") in ("video", "manual")


def base_legenda(p, origem=None):
    """Impressao digital do que a legenda transcreveu: a narracao (arquivo) ou os trechos da montagem (audio do
    video). Se mudar depois de transcrever, a legenda esta desatualizada (botao "Atualizar legendas").
    Legenda escrita a mao nao depende de nada: nunca fica desatualizada."""
    origem = origem or p.get("legenda_origem") or "narracao"
    if origem == "manual":
        return "manual"
    if origem == "video":
        usadas = {s["fonte"] for s in p["segmentos"]}
        dados = [[(s["fonte"], s["ini"], s["fim"]) for s in p["segmentos"]],
                 sorted((f["id"], _assinatura(f["caminho"])) for f in p["fontes"] if f["id"] in usadas)]
    else:
        n = p.get("narracao")
        dados = [n, _assinatura(os.path.join(pasta(p["nome"]), n)) if n else None]
    return hashlib.sha1(json.dumps([origem, dados]).encode()).hexdigest()[:16]


def hash_conteudo(p):
    """Impressao digital de tudo que muda o video final (para o fluxo rascunho -> aprovar -> final).

    Arquivos externos entram por tamanho+data (rapido; nao le o conteudo inteiro a cada consulta).
    """
    relevante = copy.deepcopy({k: p.get(k) for k in ("fontes", "segmentos", "layout", "gancho", "legenda", "audio",
                                                     "narracao", "tipo", "formato_cfg", "react", "legenda_origem", "marca", "comparacao")})
    for f in relevante["fontes"]:
        f.pop("cenas", None)
        f.pop("destaques", None)          # analisar momentos nao muda o video: nao pode invalidar a aprovacao
        f.pop("direitos", None)           # registrar a licenca tambem nao
    if relevante["layout"] != "comparacao":
        relevante.pop("comparacao")
    graficos = p.get("graficos") or []
    if p.get("editor") == "editonny":     # o mesmo corte editado por outro editor e outro video
        relevante["editor"] = "editonny"
    if graficos:                          # so entra quando existe: projetos sem graficos mantem a mesma impressao
        relevante["graficos"] = [{k: gr.get(k) for k in ("arquivo", "inicio", "duracao")} for gr in graficos]
    h = hashlib.sha1(json.dumps(relevante, sort_keys=True).encode())
    d = pasta(p["nome"])
    for gr in graficos:
        h.update(_assinatura(os.path.join(d, *str(gr.get("arquivo") or "").split("/"))).encode())
    for tipo, nome in arquivos_de_audio(p):
        h.update(_assinatura(caminho_biblioteca(tipo, nome)).encode())
    for nome in ("legenda_cartoes.json", p.get("narracao") or "",
                 os.path.join("react", (p.get("react") or {}).get("arquivo") or ""),
                 os.path.join("react", "matte.mp4")):
        if nome and not nome.endswith(os.sep) and not nome.endswith("react" + os.sep):
            h.update(_assinatura(os.path.join(d, nome)).encode())
    return h.hexdigest()[:16]
