"""Ponte com o editonny (core/editonny.py): catalogo, textos do usuario, camada de graficos no render, narracao sem
pausas e a versao 4:5 do Instagram. Os testes rapidos usam uma instalacao FALSA (CLIPADOR_EDITONNY); os lentos usam a
instalacao real e sao pulados quando o editonny nao esta instalado."""
import json
import os
import shutil

import pytest
from fastapi.testclient import TestClient

from clipador.core import editonny, projeto, publicacao, render
from clipador.web.app import app
from conftest import sonda

CENA_HTML = """<div id="c3-title">Just <i>3 steps</i></div>
<script>
  var P = {
    x: 540, // centro
    title: "The universe in 3D", // Top-pill text.
    color: "#ff6a1f", // cor
  };
  var title = "fora do bloco";
</script>"""

CATALOGO = {"scenes": [
    {"id": "solar-system", "name": "Solar system", "category": "Scene objects", "whenToUse": "When introducing the universe",
     "duration": 5.0, "layout": "overlay", "sound": "sparkle",
     "parameters": {"x": {"default": 540, "summary": "centro"}, "title": {"default": "The universe in 3D", "summary": "t"},
                    "color": {"default": "#ff6a1f", "summary": "cor"}}, "texts": []},
    {"id": "three-steps", "name": "Three steps", "category": "General", "whenToUse": "method in three steps",
     "duration": 6, "layout": "fullscreen", "hidesCaptions": True, "texts": ["Just", "3 steps"]},
]}


@pytest.fixture()
def falso(tmp_path, monkeypatch):
    raiz = tmp_path / "editonny"
    (raiz / "visuals").mkdir(parents=True)
    (raiz / "SKILL.md").write_text("---\nname: editonny\n---\n", encoding="utf-8")
    (raiz / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (raiz / "visuals" / "catalog.json").write_text(json.dumps(CATALOGO), encoding="utf-8")
    monkeypatch.setenv("CLIPADOR_EDITONNY", str(raiz))
    return raiz


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def test_status_e_catalogo(falso, tmp_path, monkeypatch, cli):
    s = editonny.status()
    assert s["instalado"] and s["versao"] == "1.0.0" and s["cenas"] == 2 and s["motor"] is False
    assert [c["id"] for c in editonny.catalogo("universe")] == ["solar-system"]
    assert [c["id"] for c in editonny.catalogo("")] == ["solar-system", "three-steps"]
    c = editonny.catalogo("three")[0]
    assert [t["chave"] for t in c["textos"]] == ["Just", "3 steps"] and c["esconde_legenda"]
    sol = editonny.catalogo("solar")[0]
    assert [t["chave"] for t in sol["textos"]] == ["title"]            # cor e numero nao sao texto
    assert set(sol["ajustes"]) == {"x", "color"}
    assert cli.get("/api/editonny/cenas", params={"busca": "solar"}).json()["cenas"][0]["id"] == "solar-system"
    monkeypatch.setenv("CLIPADOR_EDITONNY", str(tmp_path / "nao-existe"))
    assert editonny.status() == {"instalado": False}
    assert cli.get("/api/editonny/cenas").status_code == 400


def test_textos_vem_do_usuario(falso):
    c = editonny.cena("solar-system")
    with pytest.raises(ValueError, match="exemplo: “The universe in 3D”"):
        editonny.validar_valores(c, {"x": 300})
    p, t = editonny.validar_valores(c, {"title": "  O Sol  ", "x": 300, "color": "#00AAFF"})
    assert p == {"title": "O Sol", "x": 300, "color": "#00AAFF"} and t == {}
    assert editonny.validar_valores(c, {"title": ""})[0] == {"title": ""}          # apagar de proposito vale
    for ruim in ({"title": "x", "nao_existe": 1}, {"title": "x", "x": "300"}, {"title": "x", "x": True},
                 {"title": "x", "color": "red"}, {"title": "x" * 200}):
        with pytest.raises(ValueError):
            editonny.validar_valores(c, ruim)
    passos = editonny.cena("three-steps")
    with pytest.raises(ValueError, match="3 steps"):
        editonny.validar_valores(passos, textos={"Just": "Só"})
    with pytest.raises(ValueError):
        editonny.validar_valores(passos, textos={"Just": "Só", "3 steps": "3", "outro": "x"})


def test_aplicar_valores_e_fundo():
    out = editonny.aplicar_valores(CENA_HTML, {"title": 'A "lua" </script>', "x": 300}, {"3 steps": "3 <passos>"})
    assert 'title: "A \\"lua\\" <\\/script>", // Top-pill text.' in out and "x: 300, // centro" in out
    assert 'var title = "fora do bloco"' in out                       # so o bloco var P muda
    assert "<i>3 &lt;passos&gt;</i>" in out and "Just <i>" in out
    with pytest.raises(editonny.ErroEditonny):
        editonny.aplicar_valores(CENA_HTML, {"nao_tem": "x"}, {})
    with pytest.raises(editonny.ErroEditonny):
        editonny.aplicar_valores(CENA_HTML, {}, {"Texto que nao existe": "x"})
    pagina = "html,body{width:1080px;height:1920px;overflow:hidden;background:#000}\n#root{position:relative;background:#000;color:#1}"
    t = editonny.fundo_transparente(pagina)
    assert t.count("background:transparent") == 2 and "#000" not in t
    with pytest.raises(editonny.ErroEditonny):
        editonny.fundo_transparente("body{background:#fff}")


def test_plano_de_cortes(tmp_path):
    c = tmp_path / "x.cut.json"
    c.write_text(json.dumps({"cuts": [{"pause": [6.38, 7.55], "removed": [6.4667, 7.4667], "dur": 1.0}]}), encoding="utf-8")
    assert editonny.plano_de_cortes(str(c)) == [{"ini": 6.467, "fim": 7.467, "pausa": 1.17}]


def _com_grafico(p, d, arquivo="graficos/solar-system_1.webm", inicio=1.0, duracao=2.0):
    os.makedirs(os.path.join(d, "graficos"), exist_ok=True)
    open(os.path.join(d, *arquivo.split("/")), "wb").close()
    p["graficos"] = [{"arquivo": arquivo, "cena": "solar-system", "nome": "Solar system", "inicio": inicio,
                      "duracao": duracao}]
    return p


def test_camada_de_graficos_no_comando(projeto_base):
    p = projeto_base
    d = projeto.pasta(p["nome"])
    sem, _, _ = render.montar_comando(p, "rascunho")
    assert "libvpx-vp9" not in sem
    h_sem, hp_sem = projeto.hash_conteudo(p), projeto.hash_previa(p)
    p2 = dict(p)
    p2.pop("graficos")
    assert projeto.hash_conteudo(p2) == h_sem and projeto.hash_previa(p2) == hp_sem   # vazio = impressao antiga
    _com_grafico(p, d)
    cmd, _, _ = render.montar_comando(p, "rascunho")
    k = cmd.index(os.path.join(d, "graficos", "solar-system_1.webm"))
    assert cmd[k - 3:k - 1] == ["-c:v", "libvpx-vp9"] and cmd[k - 1] == "-i"
    grafo = cmd[cmd.index("-filter_complex") + 1]
    assert "setpts=PTS-STARTPTS+1.000/TB" in grafo and "between(t\\,1.000\\,3.000)" in grafo
    assert grafo.index("[vgr0]ass=legenda.ass") > grafo.index("overlay=0:0:eof_action=pass")   # legenda por cima
    assert projeto.hash_conteudo(p) != h_sem and projeto.hash_previa(p) != hp_sem
    assert "libvpx-vp9" not in render.montar_comando(p, "audio")[0]
    for ruim in ({"arquivo": "../../x.webm"}, {"inicio": "1;drawtext"}, {"duracao": 99}):
        q = _com_grafico(dict(p), d)
        q["graficos"][0].update(ruim)
        with pytest.raises(render.ErroRender):
            render.montar_comando(q, "rascunho")
    longo = _com_grafico(dict(p, tipo="longo"), d)
    with pytest.raises(render.ErroRender, match="9:16"):
        render.montar_comando(longo, "rascunho")


def test_rotas_de_graficos(falso, projeto_base, cli):
    n = projeto_base["nome"]
    base = f"/api/projetos/{n}/graficos"
    r = cli.post(base, json={"cena": "solar-system", "inicio": 1})
    assert r.status_code == 400 and "The universe in 3D" in r.json()["detail"]
    assert cli.post(base, json={"cena": "nao-existe", "inicio": 1, "parametros": {}}).status_code == 400
    assert "fim da montagem" in cli.post(base, json={"cena": "solar-system", "inicio": 5.5, "parametros": {"title": "x"}}).json()["detail"]
    assert cli.post(base, json={"cena": "solar-system", "inicio": 1, "estilo": "neon", "parametros": {"title": "x"}}).status_code == 400
    assert cli.put(f"{base}/0", json={"inicio": 1}).status_code == 404
    assert cli.delete(f"{base}/3").status_code == 404
    p = _com_grafico(projeto.carregar(n), projeto.pasta(n))
    projeto.salvar(p)
    assert cli.put(f"{base}/0", json={"inicio": 3.5}).json()["graficos"][0]["inicio"] == 3.5
    assert cli.put(f"{base}/0", json={"inicio": 5.0}).status_code == 400          # passaria do fim (6 s)
    assert cli.delete(f"{base}/0").json()["graficos"] == []
    assert not os.path.exists(os.path.join(projeto.pasta(n), "graficos", "solar-system_1.webm"))
    assert cli.post(f"/api/projetos/{n}/narracao/apertar", json={}).status_code == 400   # sem narracao
    assert cli.post(f"/api/projetos/{n}/narracao/apertar/desfazer").status_code == 400
    assert "_4x5.mp4" in publicacao.VARIANTES


# ------------------------------------------------------------------ lentos (render de verdade)
def _esperar(cli, t):
    import time
    for _ in range(1200):
        e = cli.get(f"/api/tarefas/{t['id']}").json()
        if e["estado"] in ("ok", "erro", "cancelada"):
            return e
        time.sleep(0.25)
    raise AssertionError("tarefa nao terminou")


@pytest.mark.lento
def test_exportar_4x5(cli, projeto_base):
    n = projeto_base["nome"]
    rasc = render.render(projeto.carregar(n), "rascunho")
    e = _esperar(cli, cli.post(f"/api/projetos/{n}/exportar_4x5", json={"arquivo": os.path.basename(rasc)}).json())
    assert e["estado"] == "ok", e["erro"]
    s = sonda(os.path.join(projeto.pasta(n), e["resultado"]["saida"]))
    assert (s["w"], s["h"]) == (1080, 1350) and s["audio"] and abs(s["dur"] - sonda(rasc)["dur"]) < 0.1
    assert e["resultado"]["saida"] in cli.get(f"/api/projetos/{n}").json()["saidas"]
    de_novo = cli.post(f"/api/projetos/{n}/exportar_4x5", json={"arquivo": e["resultado"]["saida"]}).json()
    assert "4:5" in _esperar(cli, de_novo)["erro"]
    cli.put(f"/api/projetos/{n}", json={"layout": "empilhado"})
    q = render.exportar_4x5(projeto.carregar(n), os.path.basename(render.render(projeto.carregar(n), "rascunho")))
    assert (sonda(q)["w"], sonda(q)["h"]) == (1080, 1350)
    cli.put(f"/api/projetos/{n}", json={"layout": "comparacao"})
    assert cli.post(f"/api/projetos/{n}/exportar_4x5", json={"arquivo": os.path.basename(rasc)}).status_code == 400


real = pytest.mark.skipif(not os.environ.get("CLIPADOR_EDITONNY") and not editonny.instalacao(),
                          reason="editonny nao instalado")


def _pixel(video, t, x, y):
    import subprocess
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1", "-vf",
                        f"crop=1:1:{x}:{y},format=rgb24", "-f", "rawvideo", "-"], capture_output=True)
    return tuple(r.stdout[:3])


@pytest.mark.lento
@real
def test_grafico_real_sobre_o_rascunho(cli, projeto_base):
    n = projeto_base["nome"]
    t = cli.post(f"/api/projetos/{n}/graficos", json={"cena": "solar-system", "inicio": 1.0, "duracao": 3.0,
                                                       "parametros": {"title": "O Sol"}}).json()
    e = _esperar(cli, t)
    assert e["estado"] == "ok", e["erro"]
    g = projeto.carregar(n)["graficos"][0]
    assert g["arquivo"] == "graficos/solar-system_1.webm" and g["parametros"] == {"title": "O Sol"}
    assert g["direitos"]["origem"] == "licenciado" and g["direitos"]["link"].startswith("https://github.com/")
    rasc = render.render(projeto.carregar(n), "rascunho")
    assert sonda(rasc)["dur"] == pytest.approx(6.0, abs=0.1)
    sol_x, sol_y = 540, 520                                    # centro do Sol na cena
    assert _pixel(rasc, 2.5, sol_x, sol_y) != _pixel(rasc, 5.5, sol_x, sol_y)
    r, g_, b = _pixel(rasc, 2.5, sol_x, sol_y)
    assert r > 150 and r > b                                   # alaranjado do Sol (transparencia em volta)


@pytest.mark.lento
@real
def test_narracao_sem_pausas_real(cli, projeto_base, midia):
    n = projeto_base["nome"]
    d = projeto.pasta(n)
    shutil.copy(midia["voz"], os.path.join(d, "narracao.wav"))
    p = projeto.carregar(n)
    p["narracao"] = "narracao.wav"
    projeto.salvar(p)
    plano = _esperar(cli, cli.post(f"/api/projetos/{n}/narracao/apertar", json={}).json())
    assert plano["estado"] == "ok", plano["erro"]
    assert plano["resultado"]["cortes"] and plano["resultado"]["removido"] > 1.0          # pausas de 1 s
    assert projeto.carregar(n)["narracao"] == "narracao.wav"                              # plano nao muda nada
    feito = _esperar(cli, cli.post(f"/api/projetos/{n}/narracao/apertar", json={"aplicar": True}).json())
    assert feito["estado"] == "ok", feito["erro"]
    r = feito["resultado"]
    assert r["arquivo"] == "narracao_sem_pausas.wav" and r["depois"] < r["antes"] - 1.0
    p = projeto.carregar(n)
    assert p["narracao"] == "narracao_sem_pausas.wav" and p["narracao_anterior"] == "narracao.wav"
    assert cli.post(f"/api/projetos/{n}/narracao/apertar/desfazer").json()["narracao"] == "narracao.wav"


def test_verificador_de_graficos(projeto_base):
    from clipador.core import verificador
    p = projeto_base
    d = projeto.pasta(p["nome"])
    p["gancho"] = {"texto": "Título", "ate": 3.0}
    _com_grafico(p, d, inicio=1.0)
    p["graficos"][0]["esconde_legenda"] = True
    titulos = {i["titulo"] for i in verificador.verificar_graficos(p, 6.0, tem_legenda=True)}
    assert titulos == {"Gráfico junto com o título do início", "Gráfico de tela cheia com a legenda por cima"}
    p["graficos"][0].update(inicio=3.5, esconde_legenda=False)
    assert verificador.verificar_graficos(p, 6.0, tem_legenda=True) == []
    p["graficos"][0].update(inicio=5.0)
    assert [i["titulo"] for i in verificador.verificar_graficos(p, 6.0, False)] == ["Gráfico passa do fim do vídeo"]
    os.remove(os.path.join(d, "graficos", "solar-system_1.webm"))
    assert verificador.verificar_graficos(p, 6.0, False)[0]["nivel"] == "erro"
    assert any(i["titulo"] == "Gráfico do editonny não encontrado" for i in verificador.verificar_projeto(p))


def test_linha_de_comando(falso, projeto_base, capsys):
    from clipador import cli_editonny
    assert cli_editonny.main(["cenas", "solar"]) == 0
    saida = capsys.readouterr().out
    assert "solar-system" in saida and "--param title" in saida and "1 cena(s)" in saida
    assert cli_editonny.main(["grafico", projeto_base["nome"], "solar-system", "--inicio", "1"]) == 1
    assert "The universe in 3D" in capsys.readouterr().out                 # sem texto do usuario: recusa
    assert cli_editonny.main(["remover", projeto_base["nome"], "0"]) == 1


# ------------------------------------------------------------------ editor editonny (pessoa falando) e aprovacao
def _pal(*itens):
    return [{"text": t, "start": a, "end": b} for t, a, b in itens]


def test_frases_e_edl_so_com_fala(projeto_base):
    from clipador.core import editonny_fala as EF
    pal = _pal(("um", 1.0, 1.3), ("dois", 1.4, 1.7), ("tres", 2.5, 2.8), ("quatro", 2.9, 3.4), ("fora", 7.0, 7.3))
    assert EF.frases(pal, 1.0, 4.0) == [(1.0, 1.82), (2.45, 3.52)]
    p = projeto_base                                       # trechos 1-4 s e 6-9 s da fonte f1
    with pytest.raises(ValueError, match="pessoa falando"):
        EF.montar_edl(p, {"f1": pal})                      # 5 palavras, pouca voz: fica com o Clipador
    muitas = _pal(*[(f"p{i}", 1.0 + i * 0.25, 1.2 + i * 0.25) for i in range(12)]
                  + [(f"q{i}", 6.0 + i * 0.25, 6.2 + i * 0.25) for i in range(12)])
    edl = EF.montar_edl(p, {"f1": muitas})
    assert edl["output"]["format"] == "vertical" and set(edl["sources"]) == {"f1"}
    assert [(r["start"], r["end"]) for r in edl["ranges"]] == [(1.0, 4.0), (6.0, 9.0)]


def test_editor_por_projeto_e_fila(falso, projeto_base, cli, midia):
    from clipador.core import aprovacao
    n = projeto_base["nome"]
    h0 = projeto.hash_conteudo(projeto.carregar(n))
    assert cli.put(f"/api/projetos/{n}/editor", json={"editor": "outro"}).status_code == 400
    p = projeto.carregar(n)
    p["fontes"].append({"id": "f2", "caminho": midia["mudo"], "nome": "mudo.mp4", "info": {"dur": 6, "audio": False}, "cenas": []})
    p["segmentos"][1]["fonte"] = "f2"
    projeto.salvar(p)
    assert "não tem som" in cli.put(f"/api/projetos/{n}/editor", json={"editor": "editonny"}).json()["detail"]
    p["segmentos"][1]["fonte"] = "f1"
    projeto.salvar(p)
    assert cli.put(f"/api/projetos/{n}/editor", json={"editor": "editonny"}).json()["editor"] == "editonny"
    p = projeto.carregar(n)
    h = projeto.hash_conteudo(p)
    assert h != h0                                          # outro editor = outro video: aprovacao antiga nao vale
    assert aprovacao.item(p) is None                        # sem video ainda: fora da fila
    d = projeto.pasta(n)
    shutil.copy(midia["video"], os.path.join(d, f"RASCUNHO_{n}.mp4"))
    assert aprovacao.item(p)["estado"] == "desatualizado"
    assert cli.post(f"/api/aprovacao/{n}/aprovar").status_code == 400
    projeto.alterar(n, lambda a: a["aprovacao"].update(rascunho_hash=h))
    assert [i for i in cli.get("/api/aprovacao").json()["itens"] if i["nome"] == n][0]["estado"] == "aguardando"
    r = cli.post(f"/api/aprovacao/{n}/ajuste", json={"nota": "corta o começo"}).json()
    assert r["nota"] == "corta o começo" and projeto.carregar(n)["revisao_nota"] == "corta o começo"
    e = _esperar(cli, cli.post(f"/api/aprovacao/{n}/aprovar").json())
    assert e["estado"] == "ok", e["erro"]
    assert e["resultado"]["arquivo"] == f"FINAL_{n}.mp4"    # editonny: o FINAL e o rascunho aprovado, copiado
    assert sonda(os.path.join(d, f"FINAL_{n}.mp4"))["dur"] == pytest.approx(sonda(midia["video"])["dur"], abs=0.1)
    assert aprovacao.item(projeto.carregar(n))["estado"] == "aprovado"
    assert os.path.isfile(os.path.join(d, "PUBLICACAO.md"))
    t = cli.post(f"/api/projetos/{n}/render/rascunho").json()  # rascunho do editonny vai para o editonny
    assert t["tipo"] == "rascunho" and "motor" in _esperar(cli, t)["erro"]


VOZ_REAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "minha_narracao_gta6.wav")


@pytest.mark.lento
@real
@pytest.mark.skipif(not os.path.isfile(VOZ_REAL), reason="sem gravacao de voz real nesta maquina")
def test_editonny_edita_pessoa_falando(cli, midia, tmp_path):
    from conftest import ffmpeg
    from clipador.core import editonny_fala, midia as M
    video = str(tmp_path / "fala.mp4")
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=16", "-ss", "0", "-t", "16", "-i", VOZ_REAL,
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", video)
    p = projeto.criar("t-editonny-fala")
    p["fontes"].append({"id": "f1", "caminho": video, "nome": "fala.mp4", "info": M.info(video), "cenas": []})
    projeto.salvar(p)
    editonny_fala.definir_editor(p["nome"], "editonny")
    r = editonny_fala.editar(p["nome"])
    s = sonda(os.path.join(projeto.pasta(p["nome"]), r["arquivo"]))
    assert (s["w"], s["h"]) == (1080, 1920) and s["audio"] and 3 < s["dur"] <= 16.1
    assert cli.get(f"/api/projetos/{p['nome']}").json()["rascunho_atual"]
