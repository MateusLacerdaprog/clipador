"""Render real com FFmpeg: layouts, quadros, aprovacao, loudness."""
import os

import pytest

from clipador.core import projeto, render
from conftest import sonda


@pytest.mark.lento
@pytest.mark.parametrize("layout", ["tela_cheia", "empilhado", "comparacao"])
def test_layouts_geram_1080x1920_com_duracao_da_timeline(projeto_base, layout):
    p = projeto_base
    p["layout"] = layout
    cmd, total, saida = render.montar_comando(p, "rascunho", saida=os.path.join(projeto.pasta(p["nome"]), "x.mp4"))
    render.executar(cmd, total, projeto.pasta(p["nome"]))
    s = sonda(saida)
    assert (s["w"], s["h"]) == (1080, 1920)
    assert abs(s["dur"] - 6.0) < 0.15 and s["audio"]


def test_tarjas_detectadas(projeto_base):
    assert projeto_base["fontes"][0]["crop"] == "1920:960:0:60"


@pytest.mark.lento
def test_quadros_distintos_com_zoom(projeto_base):
    """Regressao do zoompan do FFmpeg 9: quadros de trechos diferentes nao podem sair iguais."""
    import hashlib
    p = projeto_base
    saidas = render.quadros(p, [0.5, 2.5, 3.5, 5.5])
    d = projeto.pasta(p["nome"])
    hashes = [hashlib.md5(open(os.path.join(d, q), "rb").read()).hexdigest() for q in saidas]
    assert len(saidas) == 4 and len(set(hashes)) == 4


def test_final_bloqueado_sem_aprovacao(projeto_base):
    with pytest.raises(render.ErroRender):
        render.render(projeto_base, "final")


@pytest.mark.lento
def test_rascunho_aprovar_final_e_mudanca_invalida_aprovacao(projeto_base):
    p = projeto_base
    render.render(p, "rascunho")
    p = projeto.carregar(p["nome"])
    h = projeto.hash_conteudo(p)
    assert p["aprovacao"]["rascunho_hash"] == h
    p["aprovacao"]["aprovado_hash"] = h
    projeto.salvar(p)
    saida = render.render(projeto.carregar(p["nome"]), "final")
    assert os.path.isfile(saida) and sonda(saida)["h"] == 1920
    # qualquer mudanca depois da aprovacao bloqueia o FINAL de novo
    p = projeto.carregar(p["nome"])
    p["gancho"]["texto"] = "mudei"
    projeto.salvar(p)
    with pytest.raises(render.ErroRender):
        render.render(projeto.carregar(p["nome"]), "final")


@pytest.mark.lento
def test_loudness_final_perto_de_menos_14(projeto_base):
    saida = render.render(projeto_base, "rascunho")
    assert abs(render.medir_loudness(saida) - (-14.0)) <= 0.6


@pytest.mark.lento
def test_fonte_sem_audio_nao_quebra(projeto_base, midia):
    from clipador.core import midia as M
    p = projeto_base
    p["fontes"].append({"id": "f2", "caminho": midia["mudo"], "nome": "mudo.mp4", "info": M.info(midia["mudo"]),
                        "crop": None, "cenas": []})
    p["segmentos"].append({"id": "s3", "fonte": "f2", "ini": 0.0, "fim": 2.0})
    saida = render.render(p, "rascunho")
    s = sonda(saida)
    assert abs(s["dur"] - 8.0) < 0.15 and s["audio"]


@pytest.mark.lento
def test_arquivo_original_nao_e_modificado(projeto_base, midia):
    import hashlib
    antes = hashlib.md5(open(midia["video"], "rb").read()).hexdigest()
    render.render(projeto_base, "rascunho")
    assert hashlib.md5(open(midia["video"], "rb").read()).hexdigest() == antes
