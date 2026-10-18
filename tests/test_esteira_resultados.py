"""Esteira de etapas, métricas por CSV do Studio, experimentos e finanças (Fases 8.4, 10 e 11)."""
import json
import os
import shutil

import pytest
from fastapi.testclient import TestClient

from clipador.core import (canais, esteira, estudio, experimentos, financeiro, ideias, metricas, projeto, recursos,
                           roteiros)
from clipador.web.app import app

FONTE = "https://www.naturalearthdata.com/about/terms-of-use/"
CSV_EN = """Content,Video title,Video publish time,Duration,Views,Engaged views,Average view duration,Stayed to watch (%),Likes,Estimated revenue (USD),Something new
Total,,,,3000,2500,,,,1.20,
abcdefghijk,Map oddity 1,"Oct 1, 2026",45,2000,1800,0:00:31,72.5,150,0.80,x
bcdefghijkl,Map oddity 2,"Oct 2, 2026",50,1000,700,0:00:20,61.0,40,0.40,y
"""
CSV_PT = """Conteúdo;Título do vídeo;Duração;Visualizações;Duração média da visualização;Porcentagem média visualizada (%);Receita estimada (USD)
abcdefghijk;Mapa 1;45;2500;0:00:33;74,2;1,05
"""


@pytest.fixture(autouse=True)
def estudio_limpo():
    shutil.rmtree(estudio.RAIZ, ignore_errors=True)
    yield
    shutil.rmtree(estudio.RAIZ, ignore_errors=True)


def _csv(tmp_path, nome, texto):
    c = tmp_path / nome
    c.write_text(texto, encoding="utf-8")
    return str(c)


def test_esteira_deduz_as_etapas_do_estado_real(projeto_base):
    st = esteira.estado(projeto_base)
    ok = {e["etapa"]: e["ok"] for e in st["etapas"]}
    assert st["atual"] == "ideia" and ok["montagem"] and not ok["narracao"] and not ok["revisao_direitos"]
    canais.semear()
    i = ideias.criar({"canal": "mapa-esquisito", "titulo": "Teste", "fontes": [{"url": FONTE}]})
    ideias.avaliar(i["id"], {k: 4 for k in ideias.PESOS}, {k: True for k in ideias.PORTOES})
    ideias.mudar_status(i["id"], "aprovada")
    r = roteiros.criar(i["id"])
    roteiros.editar(r["id"], blocos={"gancho": "G", "desenvolvimento": "D " * 20, "recompensa": "R"},
                    ganchos_alternativos=["a", "b"], afirmacoes=[{"texto": "fato", "fonte": FONTE}])
    roteiros.aprovar(r["id"])
    p = projeto.carregar(projeto_base["nome"])
    p.update(roteiro_id=r["id"], canal="mapa-esquisito")
    p["fontes"][0]["direitos"] = recursos.validar({"origem": "proprio"})
    st = esteira.estado(p)
    ok = {e["etapa"]: e["ok"] for e in st["etapas"]}
    assert ok["ideia"] and ok["roteiro"] and ok["verificacao_factual"] and ok["revisao_direitos"]
    assert st["atual"] == "narracao"                                   # retoma da primeira etapa que falta


def test_publicacao_so_pelo_usuario_com_final_e_link_valido(projeto_base):
    n = projeto_base["nome"]
    with pytest.raises(ValueError, match="link"):
        esteira.marcar_publicado(n, "https://example.com/video")
    with pytest.raises(ValueError, match="FINAL"):
        esteira.marcar_publicado(n, "https://youtube.com/shorts/abcdefghijk")
    open(os.path.join(projeto.pasta(n), "FINAL_x.mp4"), "w").write("x")
    reg = esteira.marcar_publicado(n, "https://youtube.com/shorts/abcdefghijk")
    assert reg["video_id"] == "abcdefghijk" and projeto.carregar(n)["publicacao_registro"]["url"].endswith("abcdefghijk")
    assert esteira.log(n)[-1]["etapa"] == "publicacao_autorizada"


def test_trava_contra_execucao_duplicada(projeto_base):
    n = projeto_base["nome"]
    esteira.adquirir(n, "teste 1")
    with pytest.raises(RuntimeError, match="já está rodando"):
        esteira.adquirir(n, "teste 2")
    with open(esteira._trava(n), "w", encoding="utf-8") as f:            # trava velha (> 30 min) não bloqueia
        json.dump({"dono": "antigo", "em": "2020-01-01T00:00:00"}, f)
    esteira.adquirir(n, "teste 3")
    esteira.liberar(n)
    assert not os.path.exists(esteira._trava(n))


def test_csv_do_studio_em_ingles_e_portugues(tmp_path):
    s = metricas.importar(_csv(tmp_path, "en.csv", CSV_EN), canal="mapa-esquisito")
    assert len(s["linhas"]) == 2 and s["colunas_nao_reconhecidas"] == ["Something new"]   # "Total" ignorado
    m = s["linhas"][0]["metricas"]
    assert m["views"] == 2000 and m["views_engajadas"] == 1800 and m["duracao_media_s"] == 31
    assert m["escolheram_assistir_pct"] == 72.5 and m["receita_usd"] == 0.8 and s["linhas"][0]["extra"] == {"Something new": "x"}
    pt = metricas.importar(_csv(tmp_path, "pt.csv", CSV_PT))
    mp = pt["linhas"][0]["metricas"]
    assert mp["views"] == 2500 and mp["pct_assistido"] == 74.2 and mp["receita_usd"] == 1.05 and mp["duracao_media_s"] == 33
    assert metricas.ultimo("abcdefghijk")["metricas"]["views"] == 2500 and len(metricas.serie("abcdefghijk")) == 2
    with pytest.raises(ValueError, match="Content"):
        metricas.importar(_csv(tmp_path, "ruim.csv", "Views,Likes\n10,1\n"))


def test_experimento_inconclusivo_com_amostra_pequena_e_diferenca_clara(tmp_path):
    with pytest.raises(ValueError):
        experimentos.criar({"hipotese": "curta", "variavel": "gancho"})
    e = experimentos.criar({"hipotese": "Gancho com pergunta aumenta views", "variavel": "gancho", "metrica": "views"})
    linhas = ["Content,Views"] + [f"a{k:010d},{100 + k}" for k in range(12)] + [f"b{k:010d},{1000 + k * 3}" for k in range(12)]
    metricas.importar(_csv(tmp_path, "x.csv", "\n".join(linhas) + "\n"))
    for k in range(3):
        experimentos.ligar(e["id"], "A", f"a{k:010d}")
        experimentos.ligar(e["id"], "B", f"b{k:010d}")
    r = experimentos.analisar(e["id"])
    assert r["veredito"] == "inconclusivo" and "amostra pequena" in r["motivo"]
    with pytest.raises(ValueError):
        experimentos.ligar(e["id"], "B", "a0000000000")                  # vídeo já no experimento
    for k in range(3, 12):
        experimentos.ligar(e["id"], "A", f"a{k:010d}")
        experimentos.ligar(e["id"], "B", f"b{k:010d}")
    r = experimentos.analisar(e["id"])
    assert r["veredito"] == "B acima de A" and "não prova causa" in r["motivo"] and r["ic95_diferenca_B_menos_A"][0] > 0


def test_financas_observado_separado_de_projecao(projeto_base, monkeypatch, tmp_path):
    from clipador.core.ia import uso
    n = projeto_base["nome"]
    monkeypatch.setattr(uso, "registros", lambda: [
        {"projeto": n, "ok": True, "custo_usd": 0.02}, {"projeto": n, "ok": True, "custo_usd": None},
        {"projeto": "outro", "ok": True, "custo_usd": 5.0}])
    financeiro.lancar({"tipo": "tempo_h", "valor": 1.5, "projeto": n})
    financeiro.lancar({"tipo": "licenca_usd", "valor": 2, "projeto": n})
    with pytest.raises(ValueError):
        financeiro.lancar({"tipo": "tempo_h", "valor": -1})
    r = financeiro.por_projeto(n)
    assert r["custo_ia_usd"] == 0.02 and r["chamadas_ia_sem_custo_conhecido"] == 1 and r["horas"] == 1.5
    assert r["receita_observada_usd"] is None and r["lucro_realizado_usd"] is None      # sem receita importada
    metricas.importar(_csv(tmp_path, "r.csv", "Content,Estimated revenue (USD)\nabcdefghijk,3.10\n"))
    projeto.alterar(n, lambda p: p.update(publicacao_registro={"url": "u", "video_id": "abcdefghijk"}))
    r = financeiro.por_projeto(n, valor_hora_usd=10)
    assert r["receita_observada_usd"] == 3.1 and r["custo_total_usd"] == 17.02 and r["lucro_realizado_usd"] == -13.92
    with pytest.raises(ValueError, match="não inventa"):
        financeiro.projecao(None, 30, 0.05)
    pj = financeiro.projecao(5000, 30, 0.05, 0.5, 0.1, 10)
    assert pj["tipo"].startswith("PROJEÇÃO") and pj["receita_mensal_usd"] == 3.75 and pj["margem_mensal_usd"] == -9.25


def test_rotas_de_esteira_metricas_e_financeiro(projeto_base):
    cli, n = TestClient(app, base_url="http://127.0.0.1:8765"), projeto_base["nome"]
    st = cli.get(f"/api/projetos/{n}/esteira").json()
    assert st["atual"] == "ideia" and len(st["etapas"]) == 12
    assert cli.post(f"/api/projetos/{n}/esteira/publicado", json={"url": "x"}).status_code == 400
    r = cli.post("/api/metricas/importar", files={"arquivo": ("t.csv", CSV_EN.encode("utf-8"), "text/csv")}).json()
    assert r["videos"] == 2 and cli.get("/api/metricas/abcdefghijk").json()[0]["metricas"]["views"] == 2000
    assert cli.get(f"/api/projetos/{n}/financeiro").json()["custo_total_usd"] >= 0
