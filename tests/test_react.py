"""React: camera sobre o video (janela, circulo, dividido, chroma key, recorte por IA) medido em pixels reais.

A "camera" de teste e sintetica (fundo verde + caixa magenta + tom de 300 Hz como voz), gravada em webm como o
navegador faz. Isso valida a MECANICA (composicao, chroma, formas, sincronia, narracao). A qualidade do recorte
de pessoa por IA em fotos reais de camera NAO e validada aqui (nao ha pessoa nos arquivos de teste).
"""
import os
import socket
import subprocess

import cv2
import pytest
from fastapi.testclient import TestClient

from clipador.core import projeto, react, render
from clipador.web.app import app
from conftest import ffmpeg, sonda


@pytest.fixture(scope="session")
def camera_webm(midia):
    out = os.path.join(midia["dir"], "camera_verde.webm")
    ffmpeg("-f", "lavfi", "-i", "color=c=0x00FF00:s=1280x720:r=30:d=6,drawbox=x=480:y=160:w=320:h=400:color=0xFF00FF:t=fill",
           "-f", "lavfi", "-i", "sine=f=300:d=6", "-c:v", "libvpx", "-b:v", "2M", "-c:a", "libopus", "-shortest", out)
    return out


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


@pytest.fixture()
def com_camera(cli, projeto_base, camera_webm):
    with open(camera_webm, "rb") as f:
        r = cli.post(f"/api/projetos/{projeto_base['nome']}/react/gravacao", files={"arquivo": ("grav.webm", f, "video/webm")})
    assert r.status_code == 200, r.text
    return projeto.carregar(projeto_base["nome"])


def pixel(png, x, y):
    img = cv2.imread(png)
    b, g, r = (int(v) for v in img[y, x])
    return r, g, b


def quadro(p, t=2.0):
    q = render.quadros(p, [t])
    return os.path.join(projeto.pasta(p["nome"]), q[0])


def eh_verde(c):
    r, g, b = c
    return g > 180 and r < 90 and b < 90


def eh_magenta(c):
    r, g, b = c
    return r > 170 and b > 170 and g < 90


def salvar_react(p, **mud):
    R = react.completar(p["react"])
    for k, v in mud.items():
        if isinstance(v, dict):
            R[k].update(v)
        else:
            R[k] = v
    p["react"] = R
    projeto.salvar(p)
    return projeto.carregar(p["nome"])


# posicao do canto/centro da janela padrao (curto 1080x1920, w=0.34, retangulo 16:9, x=.95, y=.92)
W_PX = 368
H_PX = 208
X0 = round(0.95 * (1080 - W_PX))
Y0 = round(0.92 * (1920 - H_PX))


def test_gravacao_vira_camera_e_narracao(com_camera):
    p = com_camera
    assert p["react"]["arquivo"] == "camera.mp4" and p["react"]["ativo"] and p["narracao"] == "narracao.wav"
    s = sonda(react.caminho_camera(p))
    assert (s["w"], s["h"]) == (1280, 720) and abs(s["dur"] - 6.0) < 0.2 and not s["audio"]    # so imagem
    assert os.path.isfile(os.path.join(projeto.pasta(p["nome"]), "narracao.wav"))


@pytest.mark.lento
def test_janela_sem_chroma_mostra_camera_com_fundo_verde(com_camera):
    png = quadro(salvar_react(com_camera, modo="janela", janela={"forma": "retangulo", "borda": False}))
    assert eh_verde(pixel(png, X0 + 12, Y0 + 12))                 # fundo da camera
    assert eh_magenta(pixel(png, X0 + W_PX // 2, Y0 + H_PX // 2))  # "pessoa"


@pytest.mark.lento
def test_chroma_key_remove_o_verde_e_mantem_a_pessoa(com_camera):
    p = salvar_react(com_camera, modo="janela", janela={"forma": "retangulo", "borda": False},
                     chroma={"ativo": True, "cor": "#00FF00", "similaridade": 0.2, "mistura": 0.05})
    png = quadro(p)
    assert not eh_verde(pixel(png, X0 + 12, Y0 + 12))             # verde sumiu: aparece o video do jogo
    assert eh_magenta(pixel(png, X0 + W_PX // 2, Y0 + H_PX // 2))  # pessoa continua


@pytest.mark.lento
def test_circulo_corta_os_cantos_sem_chroma(com_camera):
    p = salvar_react(com_camera, modo="janela", janela={"forma": "circulo", "w": 0.34, "x": 0.95, "y": 0.92})
    png = quadro(p)
    x0, y0 = round(0.95 * (1080 - 368)), round(0.92 * (1920 - 368))
    assert not eh_verde(pixel(png, x0 + 6, y0 + 6))                   # canto cortado pelo circulo
    assert eh_magenta(pixel(png, x0 + 184, y0 + 184))                 # centro


@pytest.mark.lento
def test_fundo_virtual_com_chroma_pessoa_sobre_o_jogo(com_camera):
    p = salvar_react(com_camera, modo="fundo_virtual", chroma={"ativo": True, "similaridade": 0.2, "mistura": 0.05})
    png = quadro(p)
    wpx = 1026                                                         # 95% da largura
    hpx = 578
    px, py = (1080 - wpx) // 2, 1920 - hpx
    assert not eh_verde(pixel(png, px + 20, py + 20))
    assert eh_magenta(pixel(png, 540, py + hpx // 2))


@pytest.mark.lento
def test_dividido_jogo_em_cima_camera_embaixo(com_camera):
    p = salvar_react(com_camera, modo="dividido")
    png = quadro(p)
    assert render.layout_efetivo(p) == "dividido"
    assert eh_magenta(pixel(png, 540, 1440)) and not eh_magenta(pixel(png, 540, 480))
    assert eh_verde(pixel(png, 60, 1440))                              # fundo verde da camera na metade de baixo


def test_validacoes(cli, com_camera, projeto_base):
    nome = projeto_base["nome"]
    ok = lambda body: cli.put(f"/api/projetos/{nome}", json={"react": body}).status_code  # noqa: E731
    assert ok({"modo": "explodir"}) == 400
    assert ok({"janela": {"forma": "estrela"}}) == 400
    assert ok({"janela": {"w": 7}}) == 400
    assert ok({"chroma": {"cor": "verde"}}) == 400
    assert ok({"chroma": {"similaridade": 5}}) == 400
    assert ok({"modo": "janela", "chroma": {"ativo": True, "cor": "#00ff00"}}) == 200
    # tela dividida nao existe em video longo
    cli.post(f"/api/projetos/{nome}/formato", json={"formato": "gameplay"})
    p = projeto.carregar(nome)
    p["tipo"] = "longo"
    projeto.salvar(p)
    assert ok({"modo": "dividido"}) == 400


def test_dividido_liga_chroma_e_ia_para_evitar_alpha_perdido(cli, com_camera):
    nome = com_camera["nome"]
    r = cli.put(f"/api/projetos/{nome}", json={"react": {"modo": "dividido", "chroma": {"ativo": True}}}).json()
    assert r["react"]["chroma"]["ativo"] is False


@pytest.mark.lento
def test_rascunho_completo_com_react_tem_audio_da_voz(com_camera):
    p = salvar_react(com_camera, modo="janela", chroma={"ativo": True})
    saida = render.render(p, "rascunho")
    s = sonda(saida)
    assert (s["w"], s["h"]) == (1080, 1920) and abs(s["dur"] - 6.0) < 0.2 and s["audio"]


@pytest.mark.lento
def test_deslocamento_atrasa_a_camera(com_camera):
    p = salvar_react(com_camera, modo="janela", janela={"forma": "retangulo", "borda": False}, deslocamento=3.0)
    antes = pixel(quadro(p, 1.0), X0 + 12, Y0 + 12)       # camera ainda nao entrou
    depois = pixel(quadro(p, 4.5), X0 + 12, Y0 + 12)
    assert not eh_verde(antes)
    assert eh_verde(depois)


@pytest.mark.lento
@pytest.mark.parametrize("desl,t_esperado_vermelho", [(2.0, 2.0), (-1.5, 0.0)])
def test_sincronia_a_camera_comeca_no_instante_certo(cli, projeto_base, midia, desl, t_esperado_vermelho):
    """Camera que MUDA com o tempo (verde ate 3 s, magenta depois): mede em que instante do video aparece cada cor."""
    cam = os.path.join(midia["dir"], "camera_muda.mp4")
    ffmpeg("-f", "lavfi", "-i", "color=c=0x00FF00:s=640x360:r=30:d=3", "-f", "lavfi", "-i", "color=c=0xFF00FF:s=640x360:r=30:d=3",
           "-filter_complex", "[0][1]concat=n=2:v=1:a=0", "-c:v", "libx264", "-pix_fmt", "yuv420p", cam)
    with open(cam, "rb") as f:
        cli.post(f"/api/projetos/{projeto_base['nome']}/react/gravacao", params={"usar_audio": False},
                 files={"arquivo": ("c.mp4", f, "video/mp4")})
    p = salvar_react(projeto.carregar(projeto_base["nome"]), modo="janela", deslocamento=desl,
                     janela={"forma": "retangulo", "borda": False, "w": 0.5, "x": 0.5, "y": 0.5})
    x, y = 540, 960
    def cor_em(t):
        return pixel(quadro(p, t), x, y)
    # camera troca de verde para magenta em t_cam=3 s -> no video isso acontece em 3 + desl
    troca = 3.0 + desl
    assert eh_verde(cor_em(max(troca - 0.5, 0.2))) or desl < 0      # antes da troca: verde (ou ainda ausente)
    assert eh_magenta(cor_em(min(troca + 0.5, 5.8)))


def test_camera_ausente_da_erro_claro(com_camera):
    p = salvar_react(com_camera)
    os.remove(react.caminho_camera(p))
    with pytest.raises(render.ErroRender, match="câmera"):
        render.render(p, "rascunho")


@pytest.mark.lento
def test_react_desligado_nao_altera_o_video(com_camera):
    p = salvar_react(com_camera, ativo=False)
    png = quadro(p)
    assert not eh_verde(pixel(png, X0 + 12, Y0 + 12)) and not eh_magenta(pixel(png, X0 + 184, Y0 + 104))


def test_remover_camera_nao_apaga_arquivos(cli, com_camera):
    nome = com_camera["nome"]
    r = cli.delete(f"/api/projetos/{nome}/react").json()
    assert r["react"]["arquivo"] is None and not r["react"]["ativo"]
    assert os.path.isfile(os.path.join(projeto.pasta(nome), "react", "camera.mp4"))


def tem_internet():
    try:
        socket.create_connection(("storage.googleapis.com", 443), timeout=3).close()
        return True
    except OSError:
        return False


@pytest.mark.lento
@pytest.mark.skipif(not tem_internet(), reason="o modelo de segmentacao precisa ser baixado (sem internet)")
def test_recorte_ia_mecanica_gera_matte_e_compoe(cli, com_camera):
    """MECANICA do recorte por IA (modelo real do MediaPipe). Sem pessoa no video o resultado e um recorte vazio:
    a qualidade em pessoas reais precisa ser conferida pelo usuario com a propria camera."""
    nome = com_camera["nome"]
    assert react.ia_disponivel()["ok"]
    t = cli.post(f"/api/projetos/{nome}/react/recorte").json()
    import time
    for _ in range(240):
        e = cli.get(f"/api/tarefas/{t['id']}").json()
        if e["estado"] in ("ok", "erro"):
            break
        time.sleep(0.5)
    assert e["estado"] == "ok", e
    p = projeto.carregar(nome)
    ia = p["react"]["recorte_ia"]
    assert ia["ativo"] and ia["pronto"] and ia["gerado_com"] == {"limiar": 0.5, "borda": 0.4, "estabilidade": 0.4}
    s = sonda(react.caminho_matte(p))
    assert (s["w"], s["h"]) == (1280, 720) and abs(s["dur"] - 6.0) < 0.3
    saida = render.render(salvar_react(p, modo="fundo_virtual"), "rascunho")     # alphamerge no render real
    assert (sonda(saida)["w"], sonda(saida)["h"]) == (1080, 1920)
