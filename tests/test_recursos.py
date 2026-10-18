"""Registro de origem/licença das mídias (docs/cpv/04): validação, migração, rotas e uso na montagem."""
import os

import pytest
from fastapi.testclient import TestClient

from clipador.core import projeto, recursos
from clipador.web.app import app
from conftest import ffmpeg


def _cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


def test_validar_exige_licenca_quando_a_origem_pede_e_link_http():
    assert recursos.validar({"origem": "proprio"})["origem"] == "proprio"
    d = recursos.validar({"origem": "dominio_publico", "licenca": "Natural Earth, domínio público",
                          "link": "https://www.naturalearthdata.com/about/terms-of-use/"})
    assert d["licenca"].startswith("Natural Earth") and d["registrado_em"]
    for ruim, trecho in (({"origem": "roubado"}, "origem inválida"), ({"origem": "licenciado"}, "licença"),
                         ({"origem": "terceiros", "link": "javascript:alert(1)"}, "http")):
        with pytest.raises(ValueError, match=trecho):
            recursos.validar(ruim)
    assert recursos.completar({"origem": "x"})["origem"] == "nao_informado"
    assert recursos.precisa_atencao(None) and recursos.precisa_atencao({"origem": "terceiros"})
    assert not recursos.precisa_atencao({"origem": "licenciado", "licenca": "x"})


def test_projeto_antigo_migra_e_registrar_licenca_nao_derruba_a_aprovacao(projeto_base):
    p = projeto.carregar(projeto_base["nome"])
    assert p["fontes"][0]["direitos"]["origem"] == "nao_informado"
    h, hp = projeto.hash_conteudo(p), projeto.hash_previa(p)
    p["fontes"][0]["direitos"] = recursos.validar({"origem": "proprio"})
    assert projeto.hash_conteudo(p) == h and projeto.hash_previa(p) == hp      # licença não muda o vídeo


def test_api_direitos_da_fonte(projeto_base):
    n, cli = projeto_base["nome"], _cli()
    r = cli.put(f"/api/projetos/{n}/fontes/f1/direitos", json={"origem": "licenciado", "licenca": "Contrato X"})
    assert r.status_code == 200 and r.json()["fontes"][0]["direitos"]["licenca"] == "Contrato X"
    assert cli.put(f"/api/projetos/{n}/fontes/f1/direitos", json={"origem": "licenciado"}).status_code == 400
    assert cli.put(f"/api/projetos/{n}/fontes/nao-existe/direitos", json={"origem": "proprio"}).status_code == 404
    assert projeto.carregar(n)["fontes"][0]["direitos"]["origem"] == "licenciado"   # o 400 não estragou nada


def test_api_direitos_da_biblioteca(midia):
    pasta = projeto.BIBLIOTECAS["musicas"]
    os.makedirs(pasta, exist_ok=True)
    arq = os.path.join(pasta, "trilha_teste_direitos.mp3")
    ffmpeg("-f", "lavfi", "-i", "sine=f=330:d=1", "-c:a", "libmp3lame", arq)
    cli = _cli()
    try:
        r = cli.put("/api/biblioteca/musicas/trilha_teste_direitos.mp3/direitos",
                    json={"origem": "licenciado", "licenca": "YouTube Audio Library", "link": "https://studio.youtube.com"})
        assert r.status_code == 200
        lista = {x["nome"]: x for x in cli.get("/api/biblioteca/musicas").json()}
        assert lista["trilha_teste_direitos.mp3"]["direitos"]["licenca"] == "YouTube Audio Library"
        assert recursos.ARQ_BIBLIOTECA not in lista                    # o registro não aparece como música
        assert cli.put("/api/biblioteca/musicas/nao_existe.mp3/direitos", json={"origem": "proprio"}).status_code == 404
        assert cli.put("/api/biblioteca/musicas/..%2Fx/direitos", json={"origem": "proprio"}).status_code in (400, 404)
    finally:
        os.remove(arq)


def test_tempo_da_montagem_por_origem(projeto_base):
    p = projeto_base                                   # 2 trechos de 3 s da fonte f1
    assert recursos.tempo_por_origem(p) == {"nao_informado": 6.0}
    p["fontes"][0]["direitos"] = recursos.validar({"origem": "terceiros"})
    assert recursos.tempo_por_origem(p) == {"terceiros": 6.0}
