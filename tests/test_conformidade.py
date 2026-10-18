"""Verificações de conformidade (docs/cpv/04): cada regra com um caso que dispara e um que não dispara."""
import json
import os
import shutil

from clipador.core import conformidade, projeto, recursos, verificador


def _titulos(itens, nivel=None):
    return [i["titulo"] for i in itens if nivel is None or i["nivel"] == nivel]


def test_termos_de_risco_no_titulo_gancho_e_legenda_dos_7s(projeto_base):
    p = projeto_base
    assert conformidade.termos_de_risco(p) == []
    p["publicacao"]["titulo"] = "GTA 6 VAZADO: o mapa inteiro"
    p["gancho"]["texto"] = "Sorteio de um PS5!"
    cart = [{"palavras": [{"word": "muito", "start": 1.0, "end": 1.3}, {"word": "sangue", "start": 1.3, "end": 1.6}]},
            {"palavras": [{"word": "porra", "start": 9.0, "end": 9.4}]}]          # depois dos 7 s: não conta
    json.dump(cart, open(os.path.join(projeto.pasta(p["nome"]), "legenda_cartoes.json"), "w", encoding="utf-8"))
    itens = conformidade.termos_de_risco(p)
    t = " | ".join(f"{i['titulo']} ({i['regra']}): {i['detalhe']}" for i in itens)
    assert "Termo que promete algo verificável (F5)" in t and "“vazado”" in t
    assert "Recompensa por engajamento" in t and "Violência explícita" in t
    assert "Palavrão" not in t                                                  # só os primeiros 7 s
    p["publicacao"]["titulo"] = "Trailer oficial do GTA 6"
    p["gancho"]["texto"] = ""
    os.remove(os.path.join(projeto.pasta(p["nome"]), "legenda_cartoes.json"))
    assert _titulos(conformidade.termos_de_risco(p)) == ["Afirmação que pede fonte"]   # "oficial" é só dica


def test_material_de_terceiros_sem_narracao_e_short_longo(projeto_base):
    p = projeto_base
    assert "Origem do vídeo não registrada" in _titulos(conformidade.direitos(p), "dica")
    p["fontes"][0]["direitos"] = recursos.validar({"origem": "terceiros"})
    assert "Material de terceiros sem comentário seu" in _titulos(conformidade.direitos(p), "aviso")
    p["narracao"] = "narracao.wav"
    assert "Material de terceiros com narração" in _titulos(conformidade.direitos(p), "dica")
    p["segmentos"] = [dict(p["segmentos"][0], id=f"s{k}", ini=0.0, fim=11.0) for k in range(6)]   # 66 s
    assert "Short com mais de 1 min usando material sem licença registrada" in _titulos(conformidade.direitos(p), "aviso")
    p["fontes"][0]["direitos"] = recursos.validar({"origem": "proprio"})
    assert not [i for i in conformidade.direitos(p) if i["nivel"] == "aviso"]


def test_musica_sem_licenca_e_custo_no_fundo_dos_shorts(projeto_base):
    p = projeto_base
    p["audio"]["musica"]["arquivo"] = "trilha_x.mp3"
    t = _titulos(conformidade.direitos(p))
    assert "Música sem licença registrada" in t and "Música de parceiros reduz a parte do Short no fundo de receita" in t
    pasta = projeto.BIBLIOTECAS["musicas"]
    recursos.biblioteca_gravar(pasta, "trilha_x.mp3", {"origem": "licenciado", "licenca": "YouTube Audio Library"})
    try:
        assert "Música sem licença registrada" not in _titulos(conformidade.direitos(p))
    finally:
        os.remove(os.path.join(pasta, recursos.ARQ_BIBLIOTECA))


def test_duplicado_so_contra_projeto_ja_exportado(projeto_base):
    p = projeto_base
    copia = projeto.duplicar(p["nome"])
    try:
        assert conformidade.duplicados(p) == []                     # a cópia ainda não foi exportada
        open(os.path.join(projeto.pasta(copia["nome"]), "FINAL_x.mp4"), "w").write("x")
        itens = conformidade.duplicados(p)
        assert itens and itens[0]["regra"] == "F5" and copia["nome"] in itens[0]["detalhe"]
    finally:
        shutil.rmtree(projeto.pasta(copia["nome"]), ignore_errors=True)


def test_conformidade_entra_no_verificador_com_a_regra(projeto_base):
    p = projeto_base
    p["fontes"][0]["direitos"] = recursos.validar({"origem": "terceiros"})
    itens = verificador.verificar_projeto(p)
    alvo = [i for i in itens if i["titulo"] == "Material de terceiros sem comentário seu"]
    assert alvo and alvo[0]["regra"] == "F1" and itens[0]["nivel"] in ("erro", "aviso")
