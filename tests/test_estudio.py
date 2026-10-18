"""Estúdio (docs/cpv): canais, ideias com pontuação CPV, roteiros com aprovação, sugestão da IA e CLI."""
import os
import shutil

import pytest
from fastapi.testclient import TestClient

from clipador import cli_estudio
from clipador.core import canais, conformidade, estudio, ideias, projeto, roteiros
from clipador.web.app import app

FONTE = "https://www.naturalearthdata.com/about/terms-of-use/"


@pytest.fixture(autouse=True)
def estudio_limpo():
    shutil.rmtree(estudio.RAIZ, ignore_errors=True)
    yield
    shutil.rmtree(estudio.RAIZ, ignore_errors=True)


def _cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def _ideia_aprovada(canal="mapa-esquisito", titulo="Ponto mais oriental das Américas"):
    if not estudio.existe("canais", canal):
        canais.semear()
    i = ideias.criar({"canal": canal, "titulo": titulo, "fontes": [{"url": FONTE}]})
    ideias.avaliar(i["id"], {k: 4 for k in ideias.PESOS}, {k: True for k in ideias.PORTOES})
    return ideias.mudar_status(i["id"], "aprovada")


def _roteiro_pronto(ideia_id):
    r = roteiros.criar(ideia_id)
    return roteiros.editar(r["id"], blocos={
        "gancho": "Este é o ponto mais a leste de todas as Américas, e fica no Brasil.",
        "contexto": "Muita gente acha que é em Recife.",
        "desenvolvimento": "As coordenadas mostram outra coisa: a ponta fica na Paraíba, perto de João Pessoa.",
        "tensao": "Mas tem um detalhe que quase ninguém sabe.",
        "recompensa": "A Ponta do Seixas fica a cerca de dois quilômetros mais a leste do que o farol famoso."},
        ganchos_alternativos=["Qual é o lugar mais a leste das Américas?", "O Brasil tem a ponta leste do continente."],
        afirmacoes=[{"texto": "Ponta do Seixas é o ponto mais oriental", "fonte": FONTE}])


def test_canais_validacao_semear_e_monetizacao_do_gta():
    criados = canais.semear()
    assert {c["id"] for c in criados} == {"mapa-esquisito", "historia-esquisita", "como-o-espaco-funciona", "gta-6-comparado"}
    assert canais.obter("gta-6-comparado")["monetizacao"] == "sem_receita"
    assert canais.semear() == []                                     # não duplica nem sobrescreve
    with pytest.raises(FileExistsError):
        canais.criar({"nome": "Mapa Esquisito"})
    for ruim in ({"nome": ""}, {"nome": "x", "limite_dia": 9}, {"nome": "x", "status": "viral"}):
        with pytest.raises(ValueError):
            canais.validar(ruim)
    assert canais.editar("mapa-esquisito", {"status": "ativo"})["status"] == "ativo"


def test_pontuacao_cpv_pesos_portoes_e_aprovacao():
    assert sum(p for p, _, _ in ideias.PESOS.values()) == 100
    canais.semear()
    i = ideias.criar({"canal": "mapa-esquisito", "titulo": "Fronteira seca"})
    assert ideias.pontuar(i)[0] is None
    i = ideias.avaliar(i["id"], {k: 5 for k in ideias.PESOS}, {k: True for k in ideias.PORTOES})
    assert i["nota"] == 100 and i["status"] == "pontuada"
    i = ideias.avaliar(i["id"], {"gancho": 0, "originalidade": 2.5})
    assert i["nota"] == pytest.approx(100 - 15 - 7.5)
    i = ideias.avaliar(i["id"], portoes={"direitos_viaveis": False})
    assert i["nota"] is None and "direitos_viaveis" in ideias.pontuar(i)[1]     # portão reprova antes da nota
    with pytest.raises(ValueError):
        ideias.avaliar(i["id"], {"gancho": True})                    # bool não vale como nota
    with pytest.raises(ValueError):
        ideias.avaliar(i["id"], {"viral": 5})
    ideias.avaliar(i["id"], portoes={"direitos_viaveis": True})
    with pytest.raises(ValueError, match="fonte"):
        ideias.mudar_status(i["id"], "aprovada")                     # sem fonte não aprova
    ideias.adicionar_fonte(i["id"], {"url": FONTE})
    assert ideias.mudar_status(i["id"], "aprovada")["status"] == "aprovada"
    assert [h["acao"] for h in ideias.obter(i["id"])["historico"]][:2] == ["criada", "avaliada"]
    with pytest.raises(ValueError):
        ideias.criar({"canal": "mapa-esquisito", "titulo": "x", "fontes": [{"url": "ftp://x"}]})
    with pytest.raises(FileNotFoundError):
        ideias.criar({"canal": "nao-existe", "titulo": "x"})


def test_roteiro_checagem_aprovacao_e_versoes():
    canais.semear()
    nao_aprovada = ideias.criar({"canal": "mapa-esquisito", "titulo": "x"})
    with pytest.raises(ValueError, match="APROVADA"):
        roteiros.criar(nao_aprovada["id"])
    ideia = _ideia_aprovada()
    r = roteiros.criar(ideia["id"])
    assert ideias.obter(ideia["id"])["status"] == "em_roteiro"
    erros = [i["titulo"] for i in roteiros.checar(r) if i["nivel"] == "erro"]
    assert "Bloco obrigatório vazio: gancho" in erros and any("ganchos alternativos" in e for e in erros)
    with pytest.raises(ValueError, match="não dá para aprovar"):
        roteiros.aprovar(r["id"])
    r = _roteiro_pronto(ideia["id"])
    assert not [i for i in roteiros.checar(r) if i["nivel"] == "erro"]
    m = roteiros.metricas(r)
    assert m["recompensa_em"] >= 0.6 and 10 < m["duracao_s"] < 60
    r = roteiros.aprovar(r["id"])
    assert r["status"] == "aprovado"
    r = roteiros.editar(r["id"], blocos={"fechamento": "E você, sabia?"})
    assert r["status"] == "rascunho" and len(r["versoes"]) == 2      # mexeu depois de aprovar: aprova de novo
    r = roteiros.editar(r["id"], afirmacoes=[{"texto": "fato solto", "fonte": ""}])
    assert "Afirmação sem fonte" in [i["titulo"] for i in roteiros.checar(r) if i["nivel"] == "erro"]
    r = roteiros.editar(r["id"], blocos={"gancho": "Isso VAZOU antes da hora", "recompensa": "fim"})
    assert any("Termo que promete" in i["titulo"] for i in roteiros.checar(r))


def test_recompensa_cedo_e_roteiro_parecido_no_mesmo_canal():
    a = _roteiro_pronto(_ideia_aprovada()["id"])
    b = _roteiro_pronto(_ideia_aprovada(titulo="Outra ideia")["id"])          # mesmo texto, mesmo canal
    t = [i["titulo"] for i in roteiros.checar(b)]
    assert "Parecido com outro roteiro do canal" in t
    c = _roteiro_pronto(_ideia_aprovada("historia-esquisita", "Outro canal")["id"])
    assert "Parecido com outro roteiro do canal" not in [i["titulo"] for i in roteiros.checar(c)]   # só compara no canal
    a = roteiros.editar(a["id"], blocos={"recompensa": " ".join(["resposta"] * 40), "desenvolvimento": "curto", "tensao": "",
                                          "contexto": "", "gancho": "Gancho."})
    assert "Recompensa cedo demais" in [i["titulo"] for i in roteiros.checar(a)]


def test_sugestao_da_ia_nao_entra_sem_aplicar_e_fonte_inventada_vira_a_confirmar():
    r = roteiros.criar(_ideia_aprovada()["id"])
    chamadas = []

    def falso_enviar(p, tarefa, pedido, progresso):
        chamadas.append((p, tarefa, pedido))
        return {"origem": "sugestão da IA (teste)", "custo_usd": 0.01, "dados": {
            "blocos": {"gancho": "G da IA", "desenvolvimento": "D", "recompensa": "R"},
            "ganchos_alternativos": ["A1", "A2", "A3"],
            "afirmacoes": [{"texto": "fato com fonte", "fonte": FONTE}, {"texto": "fato inventado", "fonte": "https://inventado.example"}],
            "a_confirmar": []}}

    r = roteiros.sugerir_com_ia(r["id"], enviar=falso_enviar)
    assert chamadas[0][1] == "roteiro_cpv" and FONTE in chamadas[0][2]["prompt"]
    assert r["blocos"]["gancho"] == ""                                 # nada aplicado sozinho
    assert any("inventado" in x for x in r["sugestao_ia"]["dados"]["a_confirmar"])
    r = roteiros.aplicar_sugestao(r["id"])
    assert r["blocos"]["gancho"] == "G da IA" and r["origem_texto"].startswith("sugestão da IA revisada")
    assert [a["texto"] for a in r["afirmacoes"]] == ["fato com fonte"]   # a inventada não entra


def test_roteiro_aprovado_vira_projeto_e_limite_diario_do_canal():
    ideia = _ideia_aprovada()
    r = _roteiro_pronto(ideia["id"])
    with pytest.raises(ValueError, match="aprove"):
        roteiros.para_projeto(r["id"], "proj-roteiro")
    roteiros.aprovar(r["id"])
    p = roteiros.para_projeto(r["id"], "proj-roteiro", formato="curiosidades")
    try:
        assert p["canal"] == "mapa-esquisito" and p["roteiro_id"] == r["id"] and "Ponta do Seixas" in p["roteiro"]
        assert p["formato"] == "curiosidades" and ideias.obter(ideia["id"])["status"] == "produzida"
        assert conformidade.limite_diario(p) == []
        open(os.path.join(projeto.pasta(p["nome"]), "FINAL_hoje.mp4"), "w").write("x")
        itens = conformidade.limite_diario(p)
        assert itens and itens[0]["titulo"] == "Limite diário do canal atingido"
    finally:
        shutil.rmtree(projeto.pasta("proj-roteiro"), ignore_errors=True)


def test_rotas_do_estudio_e_erros():
    cli = _cli()
    assert len(cli.post("/api/canais/semear").json()["criados"]) == 4
    assert cli.post("/api/canais", json={"nome": "Mapa Esquisito"}).status_code == 409
    assert cli.get("/api/canais/nao-existe").status_code == 404
    assert cli.get("/api/canais/..%2Fx").status_code in (400, 404)
    crit = cli.get("/api/cpv/criterios").json()
    assert sum(v["peso"] for v in crit["pesos"].values()) == 100 and "explicador" in crit["estruturas"]
    i = cli.post("/api/ideias", json={"canal": "mapa-esquisito", "titulo": "Teste", "fontes": [{"url": FONTE}]}).json()
    assert cli.post(f"/api/ideias/{i['id']}/avaliar", json={"notas": {"gancho": 9}}).status_code == 400
    r = cli.post(f"/api/ideias/{i['id']}/avaliar", json={"notas": {k: 3 for k in ideias.PESOS},
                                                          "portoes": {k: True for k in ideias.PORTOES}}).json()
    assert r["nota"] == 60
    assert cli.post(f"/api/ideias/{i['id']}/status", json={"status": "aprovada"}).json()["status"] == "aprovada"
    ro = cli.post("/api/roteiros", json={"ideia": i["id"]}).json()
    assert ro["checagem"] and ro["metricas"]["palavras"] == 0
    assert cli.post(f"/api/roteiros/{ro['id']}/aprovar").status_code == 400


def test_cli_do_estudio(capsys):
    assert cli_estudio.main(["canal", "semear"]) == 0
    assert "mapa-esquisito" in capsys.readouterr().out
    assert cli_estudio.main(["ideia", "nova", "--canal", "mapa-esquisito", "--titulo", "Teste CLI", "--fonte", FONTE]) == 0
    iid = capsys.readouterr().out.split(": ")[1].strip()
    notas = sum((["--nota", f"{k}=4"] for k in ideias.PESOS), [])
    portoes = sum((["--portao", f"{k}=sim"] for k in ideias.PORTOES), [])
    assert cli_estudio.main(["ideia", "avaliar", iid, *notas, *portoes]) == 0
    assert "nota 80.0" in capsys.readouterr().out
    assert cli_estudio.main(["ideia", "aprovar", iid]) == 0
    assert cli_estudio.main(["roteiro", "novo", iid]) == 0
    assert "Bloco obrigatório vazio: gancho" in capsys.readouterr().out
    assert cli_estudio.main(["ideia", "avaliar", iid, "--portao", "politica_ok=talvez"]) == 1
