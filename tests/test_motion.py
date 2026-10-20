"""Motion automatico da skill effectcraft na edicao do editonny (core/motion.py): o plano so usa palavras FALADAS."""
import os

import pytest

from clipador.core import motion


def _w(*itens):
    return [{"text": t, "start": a, "end": b} for t, a, b in itens]


FALA = _w(("Você", 0.2, 0.4), ("sabia", 0.45, 0.8), ("disso?", 0.85, 1.3),
          ("São", 2.0, 2.2), ("3", 2.25, 2.4), ("cuidados", 2.45, 2.9), ("com", 2.95, 3.1), ("o", 3.12, 3.2),
          ("dente.", 3.25, 3.6),
          ("Primeiro", 4.4, 4.9), ("escove", 5.0, 5.4), ("bem.", 5.45, 5.9),
          ("Agende", 9.0, 9.4), ("sua", 9.45, 9.6), ("avaliação.", 9.65, 10.3))


def test_plano_usa_so_a_fala():
    p = motion.planejar(FALA, 11.0)
    assert [x["receita"] for x in p] == ["titulo", "contador", "titulo"]
    titulo, cont, fim = p
    assert titulo["texto"] == "VOCÊ SABIA DISSO?" and titulo["inicio"] == 0.1 and titulo["duracao"] <= 3.0
    assert cont["ate"] == 3 and cont["sufixo"] == " CUIDADOS" and cont["inicio"] == 2.2
    assert fim["texto"] == "AGENDE SUA AVALIAÇÃO" and fim["inicio"] + fim["duracao"] <= 11.0
    falado = {motion._limpa(w["text"]).upper() for w in FALA}
    for x in (titulo, fim):
        assert set(x["texto"].split()) <= falado                       # nenhuma palavra inventada
    assert all(x["duracao"] >= motion.MIN_LEITURA - 0.2 for x in (titulo, fim))
    for a, b in zip(p, p[1:]):
        assert a["inicio"] + a["duracao"] <= b["inicio"]               # sem sobreposicao


def test_titulo_cortado_e_destaque():
    fala = _w(("Você", 0.0, 0.2), ("tem", 0.25, 0.4), ("um", 0.45, 0.5), ("dente", 0.55, 0.9), ("que", 0.95, 1.1),
              ("precisa", 1.15, 1.5), ("tratar.", 1.55, 2.0), ("Percebe", 5.0, 5.4), ("a", 5.45, 5.5),
              ("diferença?", 5.55, 6.1), ("Então", 8.0, 8.3), ("avalie", 8.35, 8.8), ("enquanto", 8.85, 9.2),
              ("ainda", 9.25, 9.5), ("temos", 9.55, 9.8), ("o", 9.85, 9.9), ("que", 9.95, 10.1), ("preservar.", 10.15, 10.8))
    p = motion.planejar(fala, 12.0)
    assert [x["texto"] for x in p] == ["VOCÊ TEM UM DENTE", "PERCEBE A DIFERENÇA?", "AINDA TEMOS O QUE PRESERVAR"]


def test_plano_sem_fala_ou_curto():
    assert motion.planejar([], 30) == [] and motion.planejar(FALA, 3) == []
    longa = _w(*[(f"extraordinaria{i}", i * 0.3, i * 0.3 + 0.25) for i in range(12)])
    assert all(x["receita"] != "titulo" for x in motion.planejar(longa, 20))   # nem 3 palavras cabem: sem titulo


@pytest.mark.lento
@pytest.mark.skipif(not motion.disponivel(), reason="EffectCraft nao instalado")
def test_aplicar_motion_real(midia, tmp_path):
    from conftest import ffmpeg, sonda
    video = str(tmp_path / "v.mp4")
    ffmpeg("-f", "lavfi", "-i", "color=c=0x202020:s=1080x1920:r=30:d=6", "-i", midia["voz"], "-t", "6",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", video)
    saida = str(tmp_path / "s.mp4")
    feito = motion.aplicar(video, saida, [{"receita": "titulo", "texto": "TESTE", "inicio": 1.0, "duracao": 2.0}])
    s = sonda(saida)
    assert feito[0]["texto"] == "TESTE" and (s["w"], s["h"]) == (1080, 1920) and s["audio"]
    assert abs(s["dur"] - 6.0) < 0.1 and os.path.getsize(saida) > 0
