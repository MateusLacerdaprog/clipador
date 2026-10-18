"""API local: fluxo basico e protecoes (CSRF, DNS rebinding, traversal, validacao de entrada)."""
import pytest
from fastapi.testclient import TestClient

from clipador.web.app import app

LOCAL = {"Host": "127.0.0.1:8765"}


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def test_criar_listar_salvar_reabrir(cli):
    r = cli.post("/api/projetos", json={"nome": "API Fluxo"})
    assert r.status_code == 200 and r.json()["nome"] == "api-fluxo"
    assert "api-fluxo" in [p["nome"] for p in cli.get("/api/projetos").json()]
    cli.put("/api/projetos/api-fluxo", json={"gancho": {"texto": "oi", "ate": 2}})
    assert cli.get("/api/projetos/api-fluxo").json()["gancho"]["texto"] == "oi"


def test_bloqueia_post_de_outro_site(cli):
    r = cli.post("/api/projetos", json={"nome": "csrf"}, headers={"Origin": "https://site-malicioso.example"})
    assert r.status_code == 403


def test_bloqueia_host_forjado(cli):
    r = cli.get("/api/projetos", headers={"Host": "evil.example:8765"})
    assert r.status_code == 403


def test_aceita_origem_local(cli):
    r = cli.post("/api/projetos", json={"nome": "origem local"}, headers={"Origin": "http://127.0.0.1:8765"})
    assert r.status_code == 200


def test_crop_invalido_rejeitado(cli, projeto_base):
    nome = projeto_base["nome"]
    r = cli.put(f"/api/projetos/{nome}", json={"fontes": [{"id": "f1", "crop": "1:1:0:0,movie=C\\:/x"}]})
    assert r.status_code == 400
    r = cli.put(f"/api/projetos/{nome}", json={"fontes": [{"id": "f1", "crop": "1920:960:0:60"}]})
    assert r.status_code == 200


def test_traversal_bloqueado(cli, projeto_base):
    nome = projeto_base["nome"]
    assert cli.get(f"/api/projetos/{nome}/arquivo", params={"caminho": "../../../CLAUDE.md"}).status_code == 404
    assert cli.get("/api/biblioteca/musicas/..%5C..%5Cx.mp3/arquivo").status_code in (400, 404)


def test_biblioteca_upload_sem_sobrescrever_e_remocao_protegida(cli, projeto_base, midia):
    for _ in range(2):
        with open(midia["musica"], "rb") as f:
            r = cli.post("/api/biblioteca/musicas/upload", files={"arquivo": ("trilha.mp3", f, "audio/mpeg")})
        assert r.status_code == 200
    nomes = [m["nome"] for m in cli.get("/api/biblioteca/musicas").json()]
    assert "trilha.mp3" in nomes and "trilha (2).mp3" in nomes
    nome = projeto_base["nome"]
    assert cli.put(f"/api/projetos/{nome}", json={"audio": {"musica": {"arquivo": "trilha.mp3"}}}).status_code == 200
    assert cli.delete("/api/biblioteca/musicas/trilha.mp3").status_code == 400      # em uso
    assert cli.delete("/api/biblioteca/musicas/trilha (2).mp3").status_code == 200
    with open(midia["video"], "rb") as f:   # extensao de audio falsa com conteudo invalido e rejeitada
        r = cli.post("/api/biblioteca/efeitos/upload", files={"arquivo": ("x.txt", f, "text/plain")})
    assert r.status_code == 400


def test_audio_invalido_rejeitado(cli, projeto_base):
    nome = projeto_base["nome"]
    r = cli.put(f"/api/projetos/{nome}", json={"audio": {"musica": {"db": "abc"}}})
    assert r.status_code == 400
    r = cli.put(f"/api/projetos/{nome}", json={"segmentos": [{"fonte": "f1", "ini": 1, "fim": 3,
                                                               "audio": {"modo": "explodir"}}]})
    assert r.status_code == 400
    r = cli.put(f"/api/projetos/{nome}", json={"segmentos": [{"fonte": "zz", "ini": 1, "fim": 3}]})
    assert r.status_code == 400


def test_narracao_com_clipping_avisa(cli, projeto_base, midia):
    with open(midia["estourada"], "rb") as f:
        r = cli.post(f"/api/projetos/{projeto_base['nome']}/narracao",
                     files={"arquivo": ("voz.wav", f, "audio/wav")})
    assert r.status_code == 200
    assert r.json()["analise"]["avisos"] and r.json()["narracao"] == "narracao.wav"


@pytest.mark.lento
def test_previa_solo_e_cancelamento_pela_api(cli, projeto_base):
    import time
    nome = projeto_base["nome"]
    t = cli.post(f"/api/projetos/{nome}/audio/previa", json={"solo": "original"}).json()
    for _ in range(120):
        e = cli.get(f"/api/tarefas/{t['id']}").json()
        if e["estado"] in ("ok", "erro"):
            break
        time.sleep(0.25)
    assert e["estado"] == "ok", e
    assert cli.post(f"/api/projetos/{nome}/audio/previa", json={"solo": "xyz"}).status_code == 400
    t = cli.post(f"/api/projetos/{nome}/render/rascunho").json()
    assert cli.post(f"/api/tarefas/{t['id']}/cancelar").status_code == 200
    for _ in range(120):
        e = cli.get(f"/api/tarefas/{t['id']}").json()
        if e["estado"] not in ("rodando", "na_fila"):
            break
        time.sleep(0.25)
    assert e["estado"] in ("cancelada", "ok")   # se terminou antes do cancelamento chegar, tambem vale


def test_layout_invalido_rejeitado(cli, projeto_base):
    r = cli.put(f"/api/projetos/{projeto_base['nome']}", json={"layout": "rm -rf"})
    assert r.status_code == 400
