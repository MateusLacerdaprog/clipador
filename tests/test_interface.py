"""Guardas da interface (HTML/CSS/JS estaticos): acessibilidade, contraste medido e organizacao das abas.

Nao abre navegador: le os arquivos de clipador/web/static e confere regras que ja quebraram uma vez
(controles sem nome, texto abaixo de 12 px, contraste dos tokens, tecla Espaco sequestrada, microfone pedido sozinho).
"""
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from conftest import js_da_interface, scripts_da_interface

ESTATICO = Path(__file__).resolve().parent.parent / "clipador" / "web" / "static"
HTML = (ESTATICO / "index.html").read_text(encoding="utf-8")
CSS = (ESTATICO / "style.css").read_text(encoding="utf-8")
JS = js_da_interface()


PREENCHIDOS_PELO_JS = {"proximo-ir", "aviso-acao"}     # o texto vem do JS (proximoPasso / aviso)


class Coletor(HTMLParser):
    """Guarda cada elemento, seus atributos e o texto que contem (para calcular o nome acessivel)."""

    def __init__(self):
        super().__init__()
        self.pilha, self.itens, self.ids = [], [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        el = {"tag": tag, "a": a, "texto": "", "em_label": any(p["tag"] == "label" for p in self.pilha),
              "label_texto": None}
        if a.get("id"):
            self.ids.add(a["id"])
        if tag not in ("input", "br", "img", "meta", "link"):
            self.pilha.append(el)
        self.itens.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i]["tag"] == tag:
                del self.pilha[i:]
                break

    def handle_data(self, d):
        if any(p["a"].get("aria-hidden") == "true" for p in self.pilha):
            return                               # escondido do leitor de tela: nao conta no nome acessivel
        for p in self.pilha:
            p["texto"] += d


def _coletar():
    c = Coletor()
    c.feed(HTML)
    return c


def _labels_for(c):
    return {i["a"]["for"] for i in c.itens if i["tag"] == "label" and "for" in i["a"]}


def test_todo_controle_do_html_tem_nome_acessivel():
    c = _coletar()
    com_for = _labels_for(c)
    sem_nome = []
    for el in c.itens:
        a, tag = el["a"], el["tag"]
        if tag == "input" and a.get("type") in ("hidden",):
            continue
        if tag not in ("input", "select", "textarea", "button"):
            continue
        nome = a.get("aria-label") or a.get("title") if tag != "button" else None
        if tag == "button":
            if a.get("id") in PREENCHIDOS_PELO_JS:
                continue
            nome = a.get("aria-label") or re.sub(r"[✕✔▶●■⏸📷↶↷↑↓⌨\s]", "", el["texto"])
        elif not nome:
            nome = el["em_label"] or a.get("id") in com_for
        if not nome:
            sem_nome.append(f"<{tag} id={a.get('id')!r} class={a.get('class')!r}>")
    assert not sem_nome, "controles sem nome acessivel:\n" + "\n".join(sem_nome)


def test_botoes_so_com_simbolo_tem_aria_label():
    for el in _coletar().itens:
        if el["tag"] == "button" and re.fullmatch(r"[\s✕✔▶●■⏸↶↷↑↓⌨]*", el["texto"]) and el["a"].get("id") not in PREENCHIDOS_PELO_JS:
            assert el["a"].get("aria-label"), f"botao sem texto e sem aria-label: {el['a']}"


def test_estrutura_de_navegacao_e_pontos_de_referencia():
    c = _coletar()
    assert 'class="pular" href="#principal"' in HTML and 'id="principal" tabindex="-1"' in HTML
    navs = [i for i in c.itens if i["tag"] == "nav"]
    assert navs and all(n["a"].get("aria-label") for n in navs)
    abas = re.findall(r'<button type="button" data-aba="(\w+)"', HTML)
    paineis = re.findall(r'<section data-painel="(\w+)"', HTML)
    assert abas == ["fonte", "cortes", "estilo", "audio", "narracao", "legendas", "revisar", "assistente", "react"]
    assert sorted(abas) == sorted(paineis), "toda aba precisa de um painel e vice-versa"
    assert 'id="aviso"' in HTML and 'role="status"' in HTML and 'id="aviso-alerta"' in HTML and 'role="alert"' in HTML
    assert 'id="proximo"' in HTML


def test_nada_clicavel_que_o_teclado_nao_alcance():
    assert not re.search(r"<li[^>]*(onclick|tabindex)", JS), "itens de lista clicaveis devem ser botoes"
    assert 'class="cena-add"' in JS and 'class="cena"' in JS and "data-n=" in JS
    assert not re.search(r'<span class="saida', JS), "saidas geradas devem ser botoes"
    assert '<div class="cena" data-i="${i}" title=' not in JS


def test_atalhos_de_uma_tecla_nao_sequestram_botoes_nem_microfone_nao_e_pedido_sozinho():
    assert 'e.target.closest("#tlv")' in JS, "atalhos S/D/Delete/Espaco so com o foco na timeline (WCAG 2.1.4)"
    assert 'e.target === document.body' in JS
    assert 'dataset.aba === "narracao") prepararMic' not in JS, "o navegador nao deve pedir o microfone ao abrir a aba"
    assert 'id="mic-ativar"' in HTML


def test_ia_e_acoes_reversiveis_usam_desfazer_em_vez_de_confirmar():
    assert 'confirm("Substituir a timeline atual' not in JS
    assert 'rotulo: "Desfazer"' in JS
    assert "salvar-estilo" not in JS and "salvar-estilo" not in HTML, "o Estilo salva na hora, como o resto do app"


def test_fontes_nunca_abaixo_de_12px_e_em_rem():
    tamanhos = re.findall(r"font-size:\s*([\d.]+)(px|rem)", CSS)
    assert tamanhos
    assert not [t for t in tamanhos if t[1] == "px"], "font-size deve ser em rem (respeita o tamanho do navegador)"
    assert not [t for t in tamanhos if float(t[0]) * 16 < 11.99], "texto abaixo de 12 px"
    assert not re.search(r"font:[^;]*\b(10|11)px", CSS)


def _lum(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _razao(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _tokens():
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", CSS.split("}")[0]))


def test_contraste_dos_tokens_de_cor():
    t = _tokens()
    # texto (WCAG 1.4.3 AA = 4.5:1) sobre as superficies em que aparece
    for fundo in ("painel", "painel2", "fundo"):
        assert _razao(t["apagado"], t[fundo]) >= 4.5, f"texto apagado sobre {fundo}"
        assert _razao(t["texto"], t[fundo]) >= 7
    assert _razao("#ffffff", t["perigo"]) >= 4.5, "botao Gravar: branco sobre perigo"
    assert _razao("#111111", t["acento"]) >= 4.5, "botao primario: preto sobre amarelo"
    assert _razao(t["rosa"], t["painel"]) >= 4.5, "mensagens de erro em rosa"
    # limites de campos (1.4.11 = 3:1) sobre o fundo do proprio campo e dos cartoes
    for fundo in ("#101014", t["painel"], t["painel2"]):
        assert _razao(t["borda-controle"], fundo) >= 3.0, f"borda do campo sobre {fundo}"


def test_movimento_reduzido_e_telas_estreitas_previstos():
    assert "prefers-reduced-motion: reduce" in CSS
    assert re.search(r"@media \(max-width: 760px\)[^}]*\{[^}]*body \{ flex-direction: column", CSS, re.S)
    assert "minmax(0, 1fr)" in CSS and ".duas-colunas > * { min-width: 0; }" in CSS


def test_pagina_e_arquivos_estaticos_sao_sempre_revalidados():
    from fastapi.testclient import TestClient

    from clipador.web.app import app

    cli = TestClient(app, base_url="http://127.0.0.1:8765")
    for caminho in ("/", "/static/js/base.js", "/static/js/inicio.js", "/static/style.css", "/static/index.html"):
        r = cli.get(caminho)
        assert r.status_code == 200 and r.headers.get("cache-control") == "no-cache", caminho
    assert "cache-control" not in cli.get("/api/projetos").headers or cli.get("/api/projetos").headers["cache-control"] != "no-cache"


def test_reproducao_da_timeline_usa_dois_players_e_requestanimationframe():
    assert 'id="player-fonte-b"' in HTML and ".tl-oculto" in CSS
    assert "function vigiarTL" in JS and "requestAnimationFrame(vigiarTL)" in JS
    assert 'addEventListener("timeupdate"' not in JS.split("function pararTimeline")[0].split("async function tocarTimeline")[-1], \
        "o fim do trecho nao pode depender do timeupdate (so dispara ~4x/s)"


def test_scripts_carregados_em_ordem_e_nenhum_esquecido():
    """O JS e dividido por area em js/*.js (scripts classicos, escopo global compartilhado). Todo arquivo da pasta
    tem de estar no index.html (senao a funcao some da tela), base.js primeiro e inicio.js (que roda tudo) por ultimo."""
    carregados = [Path(c).name for c in scripts_da_interface()]
    na_pasta = sorted(p.name for p in (ESTATICO / "js").glob("*.js"))
    assert sorted(carregados) == na_pasta and len(set(carregados)) == len(carregados)
    assert carregados[0] == "base.js" and carregados[-1] == "inicio.js"
    assert not (ESTATICO / "app.js").exists()


@pytest.mark.skipif(not shutil.which("node"), reason="node nao instalado")
def test_sintaxe_do_javascript():
    for c in scripts_da_interface():
        r = subprocess.run(["node", "--check", c], capture_output=True, text=True)
        assert r.returncode == 0, (c, r.stderr)


@pytest.mark.skipif(not shutil.which("node"), reason="node nao instalado")
def test_scripts_carregam_sem_erro_de_ordem():
    """Funcao declarada num arquivo so existe para os outros DEPOIS que ele carrega (o hoisting e por arquivo).
    Executa todos os js/*.js em sequencia, num DOM falso que aceita qualquer coisa, e exige zero ReferenceError."""
    falso = r"""
const vm = require("vm");
const fs = require("fs");
const nada = new Proxy(function () {}, {
  get: (t, k) => k === Symbol.toPrimitive ? () => "" : k === Symbol.iterator ? function* () {} :
    k === "then" ? undefined : nada,
  apply: () => nada, construct: () => nada, set: () => true,
});
const ctx = { document: nada, window: nada, localStorage: nada, navigator: nada, location: nada, history: nada,
  console, setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
  requestAnimationFrame: () => 0, cancelAnimationFrame() {}, fetch: () => new Promise(() => {}),
  matchMedia: () => nada, getComputedStyle: () => nada, Audio: nada, MediaRecorder: nada, AudioContext: nada,
  URL, Blob: nada, FormData: nada, Image: nada, HTMLElement: nada, Event: nada, CustomEvent: nada,
  ResizeObserver: nada, IntersectionObserver: nada, MutationObserver: nada, performance: { now: () => 0 } };
ctx.globalThis = ctx;
vm.createContext(ctx);
for (const arq of process.argv.slice(1)) {
  try { vm.runInContext(fs.readFileSync(arq, "utf8"), ctx, { filename: arq }); }
  catch (e) { if (e && (e.name === "ReferenceError" || e.name === "SyntaxError")) { console.error(arq + ": " + e.message); process.exit(1); } }
}
"""
    r = subprocess.run(["node", "-e", falso, *scripts_da_interface()], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_emoji_dos_botoes_nao_e_lido_pelo_leitor_de_tela():
    """Leitor de tela lia "cesto de lixo Excluir projeto": o emoji do botao fica em aria-hidden."""
    emoji = r"(?:[\u2190-\u2BFF\u2600-\u27BF]|[\U0001F000-\U0001FAFF])"
    soltos = re.findall(rf"<button\b[^>]*>\s*{emoji}", HTML)
    assert not soltos, soltos[:5]
