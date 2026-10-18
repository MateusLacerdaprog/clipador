"""Pacote de publicacao por rede: limites medidos, declaracoes nunca preenchidas pelo app, mencao tripla da
palavra-chave, adaptar para TikTok/Instagram, capa e PUBLICACAO.md."""
import json
import os
import re
import subprocess

from fastapi.testclient import TestClient

from clipador.core import projeto, publicacao
from clipador.web.app import app
from conftest import ESTATICO, ffmpeg


def _cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _titulos(itens, nivel=None):
    return [i["titulo"] for i in itens if nivel is None or i["nivel"] == nivel]


def test_projeto_antigo_ganha_os_campos_novos_sem_perder_o_texto(projeto_base):
    n = projeto_base["nome"]
    c = os.path.join(projeto.pasta(n), "projeto.json")
    bruto = json.load(open(c, encoding="utf-8"))
    bruto["publicacao"] = {"titulo": "GTA 6 trailer", "descricao": "desc", "hashtags": ["#gta6"]}  # formato antigo
    json.dump(bruto, open(c, "w", encoding="utf-8"))
    pub = projeto.carregar(n)["publicacao"]
    assert (pub["titulo"], pub["descricao"], pub["hashtags"]) == ("GTA 6 trailer", "desc", ["#gta6"])
    assert pub["youtube"]["feito_para_criancas"] is None and pub["instagram"] == {"legenda": "", "hashtags": []}


def test_validar_limpa_campos_e_nunca_inventa_declaracao():
    pub = publicacao.validar({"hashtags": "gta6 #GTA6 #gta 6 #fyp", "youtube": {"tags": "gta 6, GTA 6, rockstar",
                              "feito_para_criancas": "sim", "conteudo_alterado": False}}, {})
    assert pub["hashtags"] == ["#gta6", "#gta", "#6", "#fyp"]          # sem repetir, sem espaco
    assert pub["youtube"]["tags"] == ["gta 6", "rockstar"]
    assert pub["youtube"]["feito_para_criancas"] is None               # so aceita True/False de verdade
    assert pub["youtube"]["conteudo_alterado"] is False
    for ruim in ({"youtube": {"categoria": "999"}}, {"youtube": {"privacidade": "todo mundo"}}):
        try:
            publicacao.validar(ruim, {})
            raise AssertionError(ruim)
        except ValueError:
            pass


def test_verificar_cobra_o_obrigatorio_e_mede_os_limites(projeto_base):
    p = projeto_base
    itens = publicacao.verificar(p)
    erros = _titulos(itens, "erro")
    assert "Sem título" in erros and any("feito para crianças" in t for t in erros)
    assert itens[0]["nivel"] == "erro"                                  # erros primeiro
    p["publicacao"] = publicacao.validar({
        "titulo": "Tudo o que eu reparei no trailer novo e que ninguem comentou sobre GTA 6 trailer ok",
        "palavra_chave": "gta 6 trailer", "hashtags": "#gta6 #viral",
        "instagram": {"legenda": "x", "hashtags": "#a #b #c #d #e #f"},
        "youtube": {"feito_para_criancas": False, "conteudo_alterado": False}}, p["publicacao"])
    itens = publicacao.verificar(p)
    t = " | ".join(_titulos(itens))
    assert "Instagram: 6 hashtags (limite 5)" in _titulos(itens, "erro")
    assert re.search(r"Título com \d+ caracteres", t) and "Palavra-chave fora do começo do título" in t
    assert "YouTube: hashtags genéricas" in t and not any("feito para crianças" in x for x in _titulos(itens, "erro"))


def test_mencao_tripla_da_palavra_chave(projeto_base):
    n = projeto_base["nome"]
    cart = [{"palavras": [{"word": "o", "start": 0.1, "end": 0.3}, {"word": "GTA", "start": 0.3, "end": 0.6},
                          {"word": "6", "start": 0.6, "end": 0.8}, {"word": "trailer", "start": 0.8, "end": 1.2}]}]
    json.dump(cart, open(os.path.join(projeto.pasta(n), "legenda_cartoes.json"), "w", encoding="utf-8"))
    p = projeto.carregar(n)
    p["legenda_origem"] = "narracao"
    p["gancho"]["texto"] = "Você viu isso?"
    p["publicacao"] = publicacao.validar({"palavra_chave": "gta 6 trailer", "titulo": "GTA 6 Trailer: 5 detalhes"}, {})
    m = publicacao.mencoes(p)
    assert m["falada"] is True and m["na_tela"] is True and m["post"]["youtube"] is True   # legenda queimada conta na tela
    assert m["post"]["instagram"] is False
    p["legenda_origem"] = "manual"                                     # escrita a mao: nao da para saber se foi dita
    assert publicacao.mencoes(p)["falada"] is None
    p["publicacao"]["palavra_chave"] = "rockstar"
    falta = [t for t in _titulos(publicacao.verificar(p)) if t.startswith("Palavra-chave “rockstar”")]
    assert falta and "na tela" in falta[0] and "título/descrição" in falta[0]


def test_adaptar_respeita_o_limite_do_instagram_e_tira_genericas(projeto_base):
    p = projeto_base
    p["publicacao"] = publicacao.validar({"titulo": "GTA 6 trailer", "descricao": "Os detalhes.\nMais coisa.",
                                          "credito": "Imagens: Rockstar Games",
                                          "hashtags": "#fyp #gta6 #gta #rockstar #trailer #jogos #ps5 #xbox"}, {})
    s = publicacao.adaptar(p)
    assert s["instagram"]["hashtags"] == ["#gta6", "#gta", "#rockstar", "#trailer", "#jogos"]
    assert s["instagram"]["legenda"].startswith("GTA 6 trailer\n\nOs detalhes.") and "Rockstar Games" in s["tiktok"]["legenda"]


def test_api_salva_verifica_exporta_e_gera_capa(projeto_base):
    n, cli = projeto_base["nome"], _cli()
    r = cli.put(f"/api/projetos/{n}", json={"publicacao": {
        "titulo": "GTA 6 trailer: o que mudou", "palavra_chave": "gta 6 trailer", "descricao": "Análise rápida.",
        "youtube": {"feito_para_criancas": False, "conteudo_alterado": False, "categoria": "20", "tags": "gta 6 trailer"},
        "tiktok": {"legenda": "gta 6 trailer em 20 s", "hashtags": "#gta6"}}})
    assert r.status_code == 200 and r.json()["publicacao"]["tiktok"]["hashtags"] == ["#gta6"]
    assert cli.put(f"/api/projetos/{n}", json={"publicacao": {"youtube": {"categoria": "x"}}}).status_code == 400
    v = cli.get(f"/api/projetos/{n}/publicacao/verificar").json()
    assert v["mencoes"]["post"]["tiktok"] is True and "erro" not in [i["nivel"] for i in v["itens"]]
    # capa: sem video pronto e um erro claro; com FINAL, sai do FINAL na resolucao dele
    assert cli.post(f"/api/projetos/{n}/publicacao/capa", json={"tempo": 1}).status_code == 400
    final = os.path.join(projeto.pasta(n), "FINAL_teste.mp4")
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=2", "-c:v", "libx264", "-preset", "ultrafast",
           "-pix_fmt", "yuv420p", final)
    assert cli.post(f"/api/projetos/{n}/publicacao/capa", json={"tempo": 99}).status_code == 400
    e = cli.post(f"/api/projetos/{n}/publicacao/capa", json={"tempo": 1.0}).json()
    assert e["publicacao"]["capa"] == {"tempo": 1.0, "arquivo": "capa.png", "video": "FINAL_teste.mp4"}
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                        os.path.join(projeto.pasta(n), "capa.png")], capture_output=True, text=True)
    assert r.stdout.strip() == "1080,1920"
    assert e["publicacao"]["titulo"] == "GTA 6 trailer: o que mudou"   # gerar a capa nao apaga o texto
    md = cli.post(f"/api/projetos/{n}/publicacao/exportar").json()
    texto = open(os.path.join(projeto.pasta(n), "PUBLICACAO.md"), encoding="utf-8").read()
    assert md["arquivo"] == "PUBLICACAO.md" and texto == md["texto"]
    for trecho in ("## YouTube (Shorts)", "**Título:** GTA 6 trailer: o que mudou", "FINAL_teste.mp4",
                   "**Feito para crianças:** Não", "## TikTok", "gta 6 trailer em 20 s", "## Instagram Reels",
                   "capa.png (quadro em 1.0 s)", "## Verificação", "Sem previsão de views"):
        assert trecho in texto, trecho


def test_interface_da_publicacao_bate_com_o_servidor():
    html = open(os.path.join(ESTATICO, "index.html"), encoding="utf-8").read()
    opcoes = re.findall(r'<option value="(\d+)">', html.split('id="pub-categoria"')[1].split("</select>")[0])
    assert sorted(opcoes) == sorted(publicacao.CATEGORIAS)
    js = open(os.path.join(ESTATICO, "js", "publicacao.js"), encoding="utf-8").read()
    campos = js.split("const PUB_CAMPOS = {")[1].split("};")[0]
    for id_ in re.findall(r'"(pub-[a-z-]+)":', campos):
        assert f'id="{id_}"' in html, id_
    for nome in ("pub-criancas", "pub-alterado"):                       # declaracao: nenhuma opcao marcada de inicio
        assert f'name="{nome}"' in html and not re.search(rf'name="{nome}"[^>]*checked', html)
