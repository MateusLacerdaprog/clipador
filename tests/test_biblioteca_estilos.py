"""Biblioteca de estilos: kits editados sem projeto (em branco, duplicar, renomear, editar), presets de zoom do
usuario e o zoom padrao do kit aplicado so nos trechos sem zoom (com o estado de antes para desfazer).

Tudo pela API real (FastAPI TestClient) e com render real do FFmpeg; kits e presets ficam na pasta temporaria.
"""
import os

import pytest
from fastapi.testclient import TestClient

from clipador.core import kits, projeto, render, zoom
from clipador.web.app import app
from conftest import ffmpeg, js_da_interface


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


@pytest.fixture()
def logo(cli, tmp_path):
    c = str(tmp_path / "logo bib.png")
    ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=120x60", "-frames:v", "1", c)
    with open(c, "rb") as f:
        return cli.post("/api/kits/logos", files={"arquivo": ("logo bib.png", f, "image/png")}).json()["logo"]


# ------------------------------------------------------------------ presets de zoom do usuario
def test_presets_de_zoom_do_usuario(cli, projeto_base):
    corpo = {"nome": "Soco Forte", "intensidade": 1.6, "inicio": 0.2, "duracao": 0.1, "curva": "rapida",
             "volta": True, "segura": 0.4, "dica": "tiro e batida"}
    r = cli.post("/api/zoom/presets", json=corpo).json()
    assert r["id"] == "soco-forte" and r["presets"]["soco-forte"]["usuario"] is True
    assert r["presets"]["soco-forte"]["intensidade"] == 1.6 and r["embutidos"] == ["destaque", "impacto", "reacao", "lento"]
    assert set(zoom.PRESETS) <= set(cli.get("/api/zoom/presets").json()["presets"])        # os 4 embutidos continuam
    for ruim in ({**corpo, "nome": "Impacto"}, {**corpo, "nome": "personalizado"}, {**corpo, "intensidade": 9},
                 {**corpo, "curva": "doida"}, {**corpo, "nome": "  "}, {**corpo, "x": 1}):
        assert cli.post("/api/zoom/presets", json=ruim).status_code == 400, ruim
    assert zoom.PRESETS["impacto"]["intensidade"] == 1.45                                   # embutido intacto
    # o arquivo dos presets nunca aparece como kit (bug visto na verificacao: virava um kit sem nome)
    assert os.path.dirname(zoom.caminho_usuario()) != kits.PASTA
    assert all(k.get("id") and k.get("nome") for k in cli.get("/api/kits").json()["kits"])
    with open(os.path.join(kits.PASTA, "lixo.json"), "w", encoding="utf-8") as f:
        f.write('{"x": 1}')
    assert "lixo" not in [k["id"] for k in cli.get("/api/kits").json()["kits"]]
    assert cli.put("/api/kits/lixo", json={"layout": "empilhado"}).status_code == 404
    os.remove(os.path.join(kits.PASTA, "lixo.json"))

    # o trecho aceita o preset do usuario; os valores ficam guardados no trecho
    n = projeto_base["nome"]
    segs = projeto_base["segmentos"]
    segs[0]["zoom_fx"] = {"preset": "soco-forte", **{k: corpo[k] for k in zoom.VALORES}, "foco_x": 0.3, "foco_y": 0.6}
    fx = cli.put(f"/api/projetos/{n}", json={"segmentos": segs}).json()["segmentos"][0]["zoom_fx"]
    assert fx["preset"] == "soco-forte" and fx["intensidade"] == 1.6 and fx["volta"] is True and fx["foco_x"] == 0.3

    # excluir: embutido nao pode; o trecho que usava vira "personalizado" com os MESMOS valores (o video nao muda)
    assert cli.delete("/api/zoom/presets/impacto").status_code == 404
    assert "soco-forte" not in cli.delete("/api/zoom/presets/soco-forte").json()["presets"]
    assert cli.delete("/api/zoom/presets/soco-forte").status_code == 404
    p = cli.put(f"/api/projetos/{n}", json={"segmentos": cli.get(f"/api/projetos/{n}").json()["segmentos"]}).json()
    fx2 = p["segmentos"][0]["zoom_fx"]
    assert fx2["preset"] == "personalizado" and {k: fx2[k] for k in zoom.VALORES} == {k: fx[k] for k in zoom.VALORES}
    with pytest.raises(ValueError):                                                         # preset inventado sem valores
        zoom.validar({"preset": "nao-existe"})


# ------------------------------------------------------------------ kits sem projeto
def test_kit_em_branco_duplicar_renomear_e_editar(cli, logo):
    k = cli.post("/api/kits", json={"nome": "Canal Base"}).json()                         # sem projeto
    assert k["id"] == "canal-base" and k["layout"] == projeto.PADRAO["layout"] and k["zoom_padrao"] is None
    assert k["legenda"] == projeto.PADRAO["legenda"] and k["marca"] == kits.MARCA_PADRAO
    assert cli.post("/api/kits", json={"nome": "Canal Base"}).json()["id"] == "canal-base-2"   # nao sobrescreve
    assert cli.post("/api/kits", json={"nome": " "}).status_code == 400

    # editar: legenda, layout, logo, gancho e zoom padrao, tudo validado
    mud = {"layout": "empilhado", "gancho_ate": 2.5, "legenda": {"estilo": "caixa", "cor": "#00ff00", "tamanho": 96},
           "marca": {"arquivo": logo, "pos": "inf_esq", "opacidade": 0.5},
           "zoom_padrao": {"preset": "destaque", "foco_y": 0.4}}
    e = cli.put("/api/kits/canal-base", json=mud).json()
    assert e["layout"] == "empilhado" and e["gancho_ate"] == 2.5 and e["legenda"]["estilo"] == "caixa"
    assert e["legenda"]["cor"] == "#00ff00" and e["legenda"]["tamanho"] == 96 and e["legenda"]["maiusculas"] is False
    assert e["marca"] == {"arquivo": logo, "pos": "inf_esq", "tamanho": 0.14, "opacidade": 0.5}
    assert e["zoom_padrao"]["preset"] == "destaque" and e["zoom_padrao"]["intensidade"] == 1.25 and e["zoom_padrao"]["foco_y"] == 0.4
    assert cli.get("/api/kits/canal-base").json() == e                                     # gravado no disco
    for ruim in ({"layout": "horizontal"}, {"layout": "xx"}, {"legenda": {"estilo": "neon"}}, {"legenda": {"cor": "red"}},
                 {"marca": {"pos": "meio"}}, {"marca": {"arquivo": "nao_existe.png"}}, {"zoom_padrao": {"preset": "impacto", "intensidade": 9}},
                 {"gancho_ate": -1}, {"nome": ""}, {"segredo": 1}):
        assert cli.put("/api/kits/canal-base", json=ruim).status_code == 400, ruim
    assert cli.get("/api/kits/canal-base").json() == e                                     # nada parcial gravado
    assert cli.put("/api/kits/nao-existe", json={"layout": "empilhado"}).status_code == 404

    # duplicar (nome automatico e escolhido): copia tudo, id novo
    c1 = cli.post("/api/kits/canal-base/duplicar", json={}).json()
    assert c1["nome"] == "Canal Base (cópia)" and c1["id"] == projeto.slug("Canal Base (cópia)") and kits.existe(c1["id"])
    assert c1["legenda"] == e["legenda"] and c1["zoom_padrao"] == e["zoom_padrao"]
    c2 = cli.post("/api/kits/canal-base/duplicar", json={"nome": "Canal Notícias"}).json()
    assert c2["nome"] == "Canal Notícias" and c2["marca"] == e["marca"]
    assert cli.post("/api/kits/nao-existe/duplicar", json={}).status_code == 404

    # renomear: troca o arquivo; nome de outro kit e recusado (nao sobrescreve)
    r = cli.put(f"/api/kits/{c2['id']}", json={"nome": "Canal Shorts"}).json()
    assert r["id"] == "canal-shorts" and r["nome"] == "Canal Shorts" and not kits.existe(c2["id"])
    assert cli.put("/api/kits/canal-shorts", json={"nome": "Canal Base"}).status_code == 409
    assert cli.get("/api/kits/canal-base").json()["layout"] == "empilhado"                # o outro ficou intacto
    assert cli.put("/api/kits/canal-shorts", json={"nome": "canal shorts"}).json()["id"] == "canal-shorts"  # so maiusculas

    # o kit editado sem projeto vale ao criar projeto novo
    novo = cli.post("/api/projetos", json={"nome": "t-bib-novo", "tipo": "curto", "kit": "canal-shorts"}).json()
    assert novo["layout"] == "empilhado" and novo["legenda"]["estilo"] == "caixa" and novo["gancho"]["ate"] == 2.5
    assert novo["marca"]["arquivo"] == logo
    for kid in ("canal-base", "canal-base-2", c1["id"], "canal-shorts"):
        assert cli.delete(f"/api/kits/{kid}").status_code == 200


def test_salvar_do_projeto_por_cima_mantem_o_zoom_padrao(cli, projeto_base):
    n = projeto_base["nome"]
    cli.post("/api/kits", json={"nome": "Kit Zoom", "projeto": n})
    cli.put("/api/kits/kit-zoom", json={"zoom_padrao": {"preset": "lento"}})
    cli.put(f"/api/projetos/{n}", json={"legenda": {"estilo": "palavra"}})
    k = cli.post("/api/kits", json={"nome": "Kit Zoom", "projeto": n}).json()             # atualiza o mesmo kit
    assert k["legenda"]["estilo"] == "palavra" and k["zoom_padrao"]["preset"] == "lento"
    # kit antigo (sem o campo) carrega com zoom_padrao None
    c = os.path.join(kits.PASTA, "kit-zoom.json")
    import json
    d = json.load(open(c, encoding="utf-8"))
    d.pop("zoom_padrao")
    json.dump(d, open(c, "w", encoding="utf-8"))
    assert kits.carregar("kit-zoom")["zoom_padrao"] is None
    cli.delete("/api/kits/kit-zoom")


# ------------------------------------------------------------------ zoom padrao do kit nos trechos sem zoom
@pytest.mark.lento
def test_zoom_do_kit_so_nos_trechos_sem_zoom_e_desfazer(cli, projeto_base):
    n = projeto_base["nome"]
    segs = projeto_base["segmentos"]                                  # s1 sem zoom, s2 com o zoom antigo 1.15
    segs.append({"id": "s3", "fonte": "f1", "ini": 9.5, "fim": 11.0, "foco_x": 0.5, "zoom": 1.0,
                 "zoom_fx": {"preset": "impacto"}})
    antes = cli.put(f"/api/projetos/{n}", json={"segmentos": segs, "layout": "tela_cheia"}).json()["segmentos"]

    cli.post("/api/kits", json={"nome": "Sem Zoom"})
    assert cli.post(f"/api/projetos/{n}/kit/zoom", json={"kit": "sem-zoom"}).status_code == 400
    assert cli.post(f"/api/projetos/{n}/kit/zoom", json={"kit": "nao-existe"}).status_code == 404
    cli.post("/api/kits", json={"nome": "Com Zoom"})
    cli.put("/api/kits/com-zoom", json={"zoom_padrao": {"preset": "reacao", "foco_x": 0.7}})

    r = cli.post(f"/api/projetos/{n}/kit/zoom", json={"kit": "com-zoom"}).json()
    assert r["aplicados"] == [1]                                       # so o trecho sem zoom
    s1, s2, s3 = r["segmentos"]
    assert s1["zoom_fx"]["preset"] == "reacao" and s1["zoom_fx"]["foco_x"] == 0.7 and s1["zoom_fx"]["volta"] is True
    assert "zoom_fx" not in s2 and s2["zoom"] == 1.15 and s3["zoom_fx"]["preset"] == "impacto"
    assert cli.post(f"/api/projetos/{n}/kit/zoom", json={"kit": "com-zoom"}).json()["aplicados"] == []   # nada a mais

    # o render real aceita o grafo e o zoom entra nos 3 trechos (kit + antigo + impacto)
    p = projeto.carregar(n)
    cmd, _, _ = render.montar_comando(p, "rascunho")
    assert cmd[cmd.index("-filter_complex") + 1].count("perspective") == 3
    assert render.render(p, "rascunho")

    # desfazer = a interface manda de volta os trechos de antes
    volta = cli.put(f"/api/projetos/{n}", json={"segmentos": antes}).json()["segmentos"]
    assert "zoom_fx" not in volta[0] and volta == antes

    # layout sem zoom (comparacao) recusa
    cli.put(f"/api/projetos/{n}", json={"layout": "comparacao"})
    assert cli.post(f"/api/projetos/{n}/kit/zoom", json={"kit": "com-zoom"}).status_code == 400
    for kid in ("sem-zoom", "com-zoom"):
        cli.delete(f"/api/kits/{kid}")


def test_interface_tem_a_biblioteca_de_estilos():
    est = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "clipador", "web", "static")
    html = open(os.path.join(est, "index.html"), encoding="utf-8").read()
    js = js_da_interface()
    for id_ in ("dlg-kits", "abrir-kits", "bk-duplicar", "bk-salvar", "bk-zoom", "bz-salvar", "kit-zoom", "kit-biblioteca"):
        assert f'id="{id_}"' in html, id_
    for rota in ("/kit/zoom", "/duplicar", '"/api/zoom/presets"', 'api("PUT", `/api/kits/'):
        assert rota in js, rota
    editaveis = js.split("const EDITAVEIS = [")[1].split("]")[0]
    assert 'data-acao="zoom-preset"' in js and '"marca"' in editaveis   # salvar zoom do trecho como preset; undo do logo
    assert '"comparacao"' in editaveis                                   # undo da config A x B
