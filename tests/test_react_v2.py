"""React: refinamento da borda do recorte por IA, fundo virtual posicionavel, despill pela cor e ajustes validados."""
import numpy as np
from fastapi.testclient import TestClient

from clipador.core import projeto, react
from clipador.web.app import app


def _cruzamento(perfil, nivel):
    """Primeira coluna (com interpolacao) em que o perfil cai abaixo de `nivel` (pessoa a esquerda)."""
    i = int(np.argmax(perfil < nivel))
    a, b = perfil[i - 1], perfil[i]
    return i - 1 + (a - nivel) / max(a - b, 1e-9)


def _caso(desvio_px_modelo):
    """Quadro 640x360 com borda real em x=300; mascara do modelo em 256 px (borda macia, deslocada), ampliada."""
    import cv2
    h, w, borda_real = 360, 640, 300.0
    x = np.arange(w, dtype=np.float32)
    guia = np.tile(np.where(x < borda_real, 0.85, 0.15), (h, 1)).astype(np.float32)        # pessoa clara, fundo escuro
    xm = np.arange(256, dtype=np.float32) * w / 256
    centro = borda_real + desvio_px_modelo * w / 256
    conf_256 = np.tile(np.clip(0.5 - (xm - centro) / (4 * w / 256), 0, 1), (144, 1)).astype(np.float32)
    conf = cv2.resize(conf_256, (w, h), interpolation=cv2.INTER_LINEAR)
    antigo = np.clip((conf - 0.35) / 0.4, 0, 1)[h // 2]                                     # conta anterior
    novo = react.refinar_mascara(conf, guia, limiar=0.5, borda=0.3)[h // 2]
    med = lambda a: (abs(_cruzamento(a, 0.5) - borda_real), _cruzamento(a, 0.1) - _cruzamento(a, 0.9))
    return med(antigo), med(novo), conf, guia


def test_filtro_guiado_deixa_a_borda_nitida_onde_a_imagem_tem_borda():
    # caso comum: a mascara so esta borrada (ampliada de 256 px) -> transicao estreita e no lugar certo
    (erro_a, larg_a), (erro_n, larg_n), conf, guia = _caso(0)
    assert erro_n <= 2 and larg_n < larg_a / 3, (erro_a, larg_a, erro_n, larg_n)
    # mascara deslocada pelo modelo: o filtro nao inventa a borda certa, mas tambem nao piora
    (erro_a, _), (erro_n, _), _, _ = _caso(3)
    assert erro_n <= erro_a + 0.5, (erro_a, erro_n)
    # "borda suave" maior = transicao mais larga (cabelo mais natural); menor = recorte mais duro
    dura = react.refinar_mascara(conf, guia, limiar=0.5, borda=0.0)[180]
    macia = react.refinar_mascara(conf, guia, limiar=0.5, borda=1.0)[180]
    faixa = lambda a: int(((a > 0.05) & (a < 0.95)).sum())
    assert faixa(macia) >= faixa(dura)


def test_fundo_virtual_usa_posicao_e_tamanho_proprios_e_despill_segue_a_cor():
    p = {"nome": "x", "react": react.completar({"modo": "fundo_virtual", "arquivo": "camera.mp4",
                                                 "info": {"w": 1280, "h": 720, "dur": 5},
                                                 "recorte": {"x": 0.0, "y": 0.5, "w": 0.5},
                                                 "chroma": {"ativo": True, "cor": "#0000FF"}})}
    f, _ = react.aplicar(p, "vb", 1, None, "out", 1080, 1920)
    g = ";".join(f)
    assert "scale=540:304" in g and "overlay=0:808" in g                     # 540 px de largura, x=0, y=(1920-304)/2
    assert "despill=type=blue" in g
    p["react"]["chroma"]["cor"] = "#00FF00"
    assert "despill=type=green" in ";".join(react.aplicar(p, "vb", 1, None, "out", 1080, 1920)[0])
    # padrao continua igual ao de antes: pessoa embaixo, centralizada, 95% da largura
    p["react"] = react.completar({"modo": "fundo_virtual", "info": {"w": 1280, "h": 720}})
    g = ";".join(react.aplicar(p, "vb", 1, None, "out", 1080, 1920)[0])
    assert "scale=1026:578" in g and "overlay=27:1342" in g


def test_api_valida_ajustes_e_avisa_mascara_desatualizada(projeto_base):
    n = projeto_base["nome"]
    cli = TestClient(app, base_url="http://127.0.0.1:8765")
    assert cli.put(f"/api/projetos/{n}", json={"react": {"recorte_ia": {"limiar": 0.95}}}).status_code == 400
    assert cli.put(f"/api/projetos/{n}", json={"react": {"recorte": {"w": 2}}}).status_code == 400
    r = cli.put(f"/api/projetos/{n}", json={"react": {"recorte_ia": {"limiar": 0.6, "borda": 0.2}, "recorte": {"x": 0.2}}}).json()
    assert r["react"]["recorte_ia"]["limiar"] == 0.6 and r["react"]["recorte"]["x"] == 0.2
    assert r["react"]["recorte_ia"]["ativo"] is False                    # mexer nos ajustes nao liga o recorte
    # matte gerado com outros ajustes -> a interface avisa para gerar de novo
    p = projeto.carregar(n)
    import os
    os.makedirs(react.pasta(p), exist_ok=True)
    open(react.caminho_matte(p), "wb").write(b"x")
    p["react"]["recorte_ia"]["gerado_com"] = {"limiar": 0.5, "borda": 0.4, "estabilidade": 0.4}
    projeto.salvar(p)
    e = cli.get(f"/api/projetos/{n}").json()["react_extra"]
    assert e["matte_pronto"] and e["matte_desatualizado"] and isinstance(e["matte_versao"], int)
