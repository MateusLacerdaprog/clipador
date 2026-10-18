"""Audio multipista medido de verdade no arquivo gerado.

Cada trilha usa um tom diferente para poder ser isolada com passa-banda na medicao:
  original 440 Hz | musica 220 Hz | narracao 1 kHz (fala 1 s / pausa 1 s) | efeito 2 kHz
"""
import os
import re
import shutil
import subprocess
import threading

import pytest

from clipador.core import audio, midia, projeto, render
from conftest import sonda

SILENCIO = -60.0
PRESENTE = -50.0


def banda(arquivo, freq, ini, dur):
    """Volume medio (dB) so da frequencia `freq` num trecho."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(ini), "-t", str(dur), "-i", arquivo,
                        "-af", ",".join([f"bandpass=f={freq}:width_type=q:w=12"] * 4) + ",volumedetect",
                        "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"mean_volume: (-?[\d.]+|-inf)", r.stderr)
    return float(m.group(1)) if m else float("-inf")


@pytest.fixture()
def proj(projeto_base, midia):
    """Projeto de 6 s com musica e efeito na biblioteca e a 'voz' como narracao."""
    p = projeto_base
    for tipo, arq in (("musicas", midia["musica"]), ("efeitos", midia["efeito"])):
        os.makedirs(projeto.BIBLIOTECAS[tipo], exist_ok=True)
        shutil.copy(arq, projeto.caminho_biblioteca(tipo, os.path.basename(arq)))
    shutil.copy(midia["voz"], os.path.join(projeto.pasta(p["nome"]), "narracao.wav"))
    return p


def gerar(p, **mudancas):
    """Aplica mudancas no audio (dict por trilha), renderiza so o audio e devolve o arquivo."""
    a = audio.migrar(p["audio"])
    a["mix"]["normalizar"] = False          # mede os volumes ajustados, sem normalizacao
    for k, v in mudancas.items():
        if k == "efeitos":
            a["efeitos"] = v
        else:
            a[k].update(v)
    p["audio"] = audio.validar(a)
    s = render.render(p, "audio")
    gerar.n += 1
    copia = s.replace(".m4a", f"_{gerar.n}.m4a")   # cada chamada gera seu proprio arquivo
    shutil.copy(s, copia)
    return copia


gerar.n = 0


@pytest.mark.lento
def test_silenciar_original_nao_altera_o_video(projeto_base):
    p = projeto_base
    d = projeto.pasta(p["nome"])
    md5 = []
    for ativo in (True, False):
        a = audio.migrar(p["audio"])
        a["original"]["ativo"] = ativo
        p["audio"] = a
        cmd, total, saida = render.montar_comando(p, "rascunho", saida=os.path.join(d, f"o_{ativo}.mp4"))
        render.executar(cmd, total, d)
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", saida, "-map", "0:v", "-f", "md5", "-"],
                           capture_output=True, text=True)
        md5.append(r.stdout.strip())
        if not ativo:
            assert banda(saida, 440, 0.5, 5) < SILENCIO, "original deveria estar mudo"
        else:
            assert banda(saida, 440, 0.5, 5) > PRESENTE
    assert md5[0] == md5[1] and md5[0], "o video mudou ao silenciar o audio"


@pytest.mark.lento
def test_volume_por_trecho(proj):
    p = proj
    p["segmentos"][0]["audio"] = {"modo": "mudo"}
    p["segmentos"][1]["audio"] = {"modo": "volume", "db": -6}
    p["narracao"] = None
    s = gerar(p, musica={"arquivo": None})
    assert banda(s, 440, 0.3, 2.4) < SILENCIO                 # trecho 1 mudo
    alto = banda(s, 440, 3.3, 2.4)
    p["segmentos"][1]["audio"] = {"modo": "volume", "db": -18}
    s = gerar(p, musica={"arquivo": None})
    assert abs((alto - banda(s, 440, 3.3, 2.4)) - 12) < 1.5     # -6 dB vs -18 dB = 12 dB


@pytest.mark.lento
def test_musica_e_narracao_com_volumes_independentes(proj):
    p = proj
    p["narracao"] = "narracao.wav"
    base = dict(original={"ativo": False}, mix={"ducking": False})
    s1 = gerar(p, musica={"arquivo": "musica.mp3", "db": -6, "fade_in": 0, "fade_out": 0}, narracao={"db": 0},
               **base)
    s2 = gerar(p, musica={"arquivo": "musica.mp3", "db": -18, "fade_in": 0, "fade_out": 0}, narracao={"db": 0},
               **base)
    s3 = gerar(p, musica={"arquivo": "musica.mp3", "db": -6, "fade_in": 0, "fade_out": 0}, narracao={"db": -10},
               **base)
    m1, m2 = banda(s1, 220, 1, 4), banda(s2, 220, 1, 4)
    assert abs((m1 - m2) - 12) < 1.5                            # so a musica mudou 12 dB
    assert abs(banda(s1, 1000, 0.1, 0.8) - banda(s2, 1000, 0.1, 0.8)) < 0.5   # voz igual
    assert abs((banda(s1, 1000, 0.1, 0.8) - banda(s3, 1000, 0.1, 0.8)) - 10) < 1.5  # so a voz mudou
    assert abs(banda(s1, 220, 1, 4) - banda(s3, 220, 1, 4)) < 0.5             # musica igual


@pytest.mark.lento
def test_musica_comeca_e_termina_no_ponto_escolhido(proj):
    p = proj
    p["narracao"] = None
    s = gerar(p, original={"ativo": False},
              musica={"arquivo": "musica.mp3", "inicio_video": 2, "fim_video": 4, "fade_in": 0, "fade_out": 0})
    assert banda(s, 220, 0.2, 1.6) < SILENCIO
    assert banda(s, 220, 2.2, 1.6) > PRESENTE
    assert banda(s, 220, 4.3, 1.5) < SILENCIO
    assert abs(sonda(s)["dur"] - 6.0) < 0.15


@pytest.mark.lento
def test_musica_curta_sem_repetir_vira_silencio_e_com_repetir_continua(proj):
    p = proj
    p["narracao"] = None
    sem = gerar(p, original={"ativo": False}, musica={"arquivo": "musica.mp3", "loop": False, "fade_out": 0,
                                                      "inicio_arquivo": 2})   # sobra 3 s de musica
    assert banda(sem, 220, 0.5, 2) > PRESENTE and banda(sem, 220, 3.5, 2) < SILENCIO
    com = gerar(p, original={"ativo": False}, musica={"arquivo": "musica.mp3", "loop": True, "fade_out": 0,
                                                      "inicio_arquivo": 2})
    assert banda(com, 220, 3.5, 2) > PRESENTE


@pytest.mark.lento
def test_deslocamento_da_narracao(proj):
    p = proj
    p["narracao"] = "narracao.wav"
    s = gerar(p, original={"ativo": False}, narracao={"deslocamento": 1.0, "tratamento": False},
              musica={"arquivo": None})
    assert banda(s, 1000, 0.05, 0.85) < SILENCIO     # nada antes de 1 s
    assert banda(s, 1000, 1.1, 0.8) > PRESENTE            # 1a "fala" entre 1 e 2 s


@pytest.mark.lento
def test_efeito_toca_no_instante_certo_e_nao_e_abaixado(proj):
    p = proj
    p["narracao"] = "narracao.wav"
    fx = [{"arquivo": "efeito.wav", "em": 3.0, "db": -6}]
    s = gerar(p, original={"ativo": False}, musica={"arquivo": None}, efeitos=fx, mix={"ducking": True})
    assert banda(s, 2000, 0.5, 2.3) < SILENCIO
    assert banda(s, 2000, 3.05, 0.4) > PRESENTE
    assert banda(s, 2000, 3.7, 2) < SILENCIO


@pytest.mark.lento
def test_ducking_abaixa_a_musica_quando_a_voz_fala(proj):
    p = proj
    p["narracao"] = "narracao.wav"
    cfg = dict(original={"ativo": False}, narracao={"tratamento": False},
               musica={"arquivo": "musica.mp3", "db": -6, "fade_in": 0, "fade_out": 0})
    com = gerar(p, mix={"ducking": True, "ducking_forca": "media"}, **cfg)
    falando, pausa = banda(com, 220, 2.3, 0.6), banda(com, 220, 3.5, 0.4)   # voz em [2,3), pausa em [3,4)
    assert pausa - falando >= 6, (falando, pausa)
    sem = gerar(p, mix={"ducking": False}, **cfg)
    assert abs(banda(sem, 220, 2.3, 0.6) - banda(sem, 220, 3.5, 0.4)) < 1.5


@pytest.mark.lento
def test_previa_solo(proj):
    p = proj
    p["narracao"] = "narracao.wav"
    a = audio.migrar(p["audio"])
    a["musica"]["arquivo"] = "musica.mp3"
    p["audio"] = a
    a["musica"]["db"] = 0
    p["audio"] = a
    s = render.render(p, "audio", solo="musica")
    assert banda(s, 220, 1, 3) > PRESENTE
    assert banda(s, 440, 1, 3) < SILENCIO and banda(s, 1000, 0.1, 0.8) < SILENCIO


@pytest.mark.lento
def test_normalizacao_final_em_menos_14(proj):
    p = proj
    p["narracao"] = "narracao.wav"
    a = audio.migrar(p["audio"])
    a["musica"]["arquivo"] = "musica.mp3"
    p["audio"] = a
    s = render.render(p, "rascunho")
    assert abs(render.medir_loudness(s) + 14) <= 0.6


def test_arquivo_de_musica_ausente_da_erro_claro(proj):
    p = proj
    a = audio.migrar(p["audio"])
    a["musica"]["arquivo"] = "nao_existe.mp3"
    p["audio"] = a
    with pytest.raises(render.ErroRender, match="nao esta na biblioteca"):
        render.render(p, "audio")


@pytest.mark.lento
def test_cancelar_render(proj):
    p = proj
    ev = threading.Event()

    def progresso(f, msg=None):
        ev.set()            # cancela assim que o FFmpeg comeca a andar
    progresso.cancelar = ev
    with pytest.raises(render.Cancelado):
        render.render(p, "rascunho", progresso)
    d = projeto.pasta(p["nome"])
    assert not [f for f in os.listdir(d) if ".tmp." in f], "sobrou arquivo temporario"


def test_deteccao_de_clipping(midia):
    ok = midia_analise(midia["voz"])
    assert ok["clip_pct"] < 0.05 and not ok["avisos"]
    ruim = midia_analise(midia["estourada"])
    assert ruim["clip_pct"] > 1 and any("clipping" in a for a in ruim["avisos"])


def midia_analise(c):
    return midia.analisar_audio(c)


def test_migracao_do_formato_antigo():
    v1 = {"jogo_db": -18, "jogo_sem_narracao_db": -3, "jogo_mudo": True, "narracao_db": 2, "ducking": False,
          "musica_arquivo": "x.mp3", "musica_db": -12, "musica_inicio": 4, "musica_fade": 2, "musica_loop": False}
    a = audio.migrar(v1)
    assert a["versao"] == 2
    assert a["original"] == {"ativo": False, "db": -3.0, "db_com_narracao": -18.0}
    assert a["musica"]["arquivo"] == "x.mp3" and a["musica"]["inicio_arquivo"] == 4 and not a["musica"]["loop"]
    assert a["narracao"]["db"] == 2 and a["mix"]["ducking"] is False


def test_validacao_rejeita_lixo():
    a = audio.migrar(None)
    a["musica"]["db"] = "1;rm -rf"
    with pytest.raises(ValueError):
        audio.validar(a)
    a = audio.migrar(None)
    a["musica"]["db"] = 999
    assert audio.validar(a)["musica"]["db"] == 12      # limitado


def test_projeto_salvo_fechado_e_reaberto(proj):
    p = proj
    a = audio.migrar(p["audio"])
    a["musica"].update(arquivo="musica.mp3", db=-9)
    a["efeitos"] = [{"arquivo": "efeito.wav", "em": 1.5}]
    p["audio"] = a
    p["segmentos"][0]["audio"] = {"modo": "mudo", "db": 0}
    projeto.salvar(p)
    q = projeto.carregar(p["nome"])
    assert q["audio"]["musica"]["db"] == -9 and q["audio"]["efeitos"][0]["em"] == 1.5
    assert q["segmentos"][0]["audio"]["modo"] == "mudo"

