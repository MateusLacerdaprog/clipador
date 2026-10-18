"""Assistente de ritmo: acha pausas longas na fala dos trechos, marca as que talvez valha manter e corta so quando pedido."""
import json
import os

from fastapi.testclient import TestClient

from clipador.core import pedido, projeto
from clipador.web.app import app


def test_pausas_sugeridas_marcadas_e_cortadas(projeto_base):
    n = projeto_base["nome"]                                     # trechos 1-4 s e 6-9 s da fonte (12 s, sem acao)
    f = projeto_base["fontes"][0]
    pal = [{"w": "olha", "start": 1.1, "end": 1.4}, {"w": "isso", "start": 2.6, "end": 2.9},          # pausa de 1,2 s
           {"w": "viu?", "start": 6.1, "end": 6.4}, {"w": "pois", "start": 7.6, "end": 7.9},           # pausa apos pergunta
           {"w": "e", "start": 8.0, "end": 8.2}]                                                     # pausa curta: ignora
    c = pedido.caminho_cache(projeto.pasta(n), f["id"])
    os.makedirs(os.path.dirname(c), exist_ok=True)
    json.dump({"assinatura": pedido._assinatura(f["caminho"]), "palavras": pal}, open(c, "w", encoding="utf-8"))
    cli = TestClient(app, base_url="http://127.0.0.1:8765")
    r = cli.get(f"/api/projetos/{n}/ritmo").json()
    s = r["sugestoes"]
    assert r["transcrito"] and len(s) == 2
    assert s[0]["trecho"] == 0 and (s[0]["ini"], s[0]["fim"]) == (1.55, 2.45) and s[0]["talvez_manter"] is None
    assert s[1]["trecho"] == 1 and "pergunta" in s[1]["talvez_manter"]
    assert r["economia_s"] == 0.9 and abs(s[0]["na_montagem_s"] - 0.4) < 0.01
    antes = cli.get(f"/api/projetos/{n}").json()["duracao"]
    e = cli.post(f"/api/projetos/{n}/timeline", json={"op": "cortar_intervalo", "i": 0, "ini": s[0]["ini"], "fim": s[0]["fim"]}).json()
    assert abs(e["duracao"] - (antes - 0.9)) < 0.01
    assert len(cli.get(f"/api/projetos/{n}/ritmo").json()["sugestoes"]) == 1      # so sobrou a da pergunta
