"""Medicao otimizada de Reels de referencia (core/reels.py): uma leitura do FFmpeg por video,
Whisper so onde ha som, folhas agrupadas e videos apagados no fim."""
import json
import os
import shutil

import pytest

from clipador import automacao
from clipador.core import midia, reels
from conftest import ffmpeg

STDERR = """
[Parsed_metadata_2 @ 0] frame:0    pts:0       pts_time:0
[Parsed_metadata_2 @ 0] lavfi.scene_score=0.000000
[Parsed_metadata_2 @ 0] frame:60   pts:60000   pts_time:2.002
[Parsed_metadata_2 @ 0] lavfi.scene_score=0.812000
[Parsed_metadata_2 @ 0] frame:61   pts:61000   pts_time:2.035
[Parsed_metadata_2 @ 0] lavfi.scene_score=0.004000
[Parsed_metadata_2 @ 0] frame:120  pts:120000  pts_time:4.004
[Parsed_metadata_2 @ 0] lavfi.scene_score=0.530000
[silencedetect @ 0] silence_start: 1.5
[silencedetect @ 0] silence_end: 2.5 | silence_duration: 1
[silencedetect @ 0] silence_start: 5.4
[Parsed_ebur128_4 @ 0] Summary:

  Integrated loudness:
    I:         -14.2 LUFS
    Threshold: -24.3 LUFS

  Loudness range:
    LRA:         3.1 LU

  True peak:
    Peak:       -1.4 dBFS
"""


def test_item_aceita_id_e_link_e_recusa_formato_errado():
    assert reels.item("[terceiro]:[terceiro]", "top") == {
        "conta": "[terceiro]", "id": "[terceiro]", "url": "https://www.instagram.com/reel/[terceiro]/", "grupo": "top"}
    it = reels.item("bk:https://www.instagram.com/reels/[terceiro]/", "controle")
    assert it["id"] == "[terceiro]" and it["url"].startswith("https://www.instagram.com/reels/")
    for ruim in ("semdoispontos", ":DearWEX", "[terceiro]:", "con ta:ID", "x:https://site.com/qualquer"):
        with pytest.raises(ValueError):
            reels.item(ruim, "top")


def test_ler_saida_tira_cortes_loudness_e_silencio_ate_o_fim():
    s = reels.ler_saida(STDERR, 6.0)
    assert s["cortes"] == [2.0, 4.0]
    assert (s["lufs"], s["lra"], s["true_peak"]) == (-14.2, 3.1, -1.4)
    assert s["silencio"] == round((1.0 + 0.6) / 6.0, 3)     # 1 s no meio + 0,6 s que vai ate o fim
    assert reels.ler_saida(STDERR, 6.0, limiar=0.6)["cortes"] == [2.0]   # limiar aplicado depois


def test_planos_por_video():
    p = reels.planos([2.0, 4.0, 9.0], 12.0)
    assert p == {"cortes": 3, "plano_medio": 3.0, "plano_mediana": 2.5, "plano_max": 5.0,
                 "primeiro_corte": 2.0, "cortes_10s": 3}
    assert reels.planos([], 8.0)["primeiro_corte"] is None


def test_fala_guarda_so_numeros_e_os_3_primeiros_segundos():
    pal = [{"w": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate("um dois tres quatro cinco seis sete oito".split())]
    f = reels.resumo_fala(pal)
    assert f["palavras"] == 8 and f["primeira_palavra"] == 0.0 and f["texto_3s"] == "um dois tres quatro cinco seis"
    assert "oito" not in json.dumps(f)
    assert reels.resumo_fala([]) == {"palavras": 0}


def test_resumo_separa_top_e_controle():
    base = {"dur": 30, "plano_mediana": 1.0, "plano_max": 4, "primeiro_corte": 0.5, "cortes_10s": 8,
            "lufs": -14, "silencio": 0}
    med = {"a": {**base, "grupo": "top", "fala": {"palavras": 50, "ppm": 200, "primeira_palavra": 0.0}},
           "b": {**base, "grupo": "top", "plano_mediana": 3.0, "fala": {"palavras": 0}},
           "c": {**base, "grupo": "controle", "plano_mediana": 6.0, "fala": {"palavras": 40, "ppm": 150, "primeira_palavra": 1.0}},
           "d": {"grupo": "top", "erro": "erro: fora do ar"}}
    r = reels.resumo(med)
    assert r["top"]["n"] == 2 and r["top"]["plano_mediana"] == 2.0 and r["top"]["fala_no_quadro_0"] == 1
    assert r["controle"]["plano_mediana"] == 6.0 and r["controle"]["fala_no_quadro_0"] == 0


def test_comando_sem_audio_nao_pede_trilha_de_som():
    cmd = reels.comando_medicao("v.mp4", "v.wav", com_audio=False)
    assert "[0:a]" not in " ".join(cmd) and "v.wav" not in cmd


def test_cli_recusa_item_mal_formado(capsys):
    assert automacao.main(["reels", "x", "--top", "semdoispontos"]) == 1
    assert "conta:ID" in capsys.readouterr().out


def _video(destino, com_som=True):
    """6 s com 2 cortes secos (vermelho, azul, verde) e som com 1 s de silencio no meio."""
    cores = "".join(f"color=c={c}:s=360x640:d=2:r=30[c{i}];" for i, c in enumerate(("red", "blue", "green")))
    som = ["-f", "lavfi", "-i", "sine=f=440:d=6,volume='if(between(t,2,3),0,1)':eval=frame"] if com_som else []
    ffmpeg(*som, "-filter_complex", cores + "[c0][c1][c2]concat=n=3:v=1:a=0[v]",
           "-map", "[v]", *(["-map", "0:a", "-c:a", "aac"] if com_som else []), "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "-t", "6", destino)
    return destino


@pytest.mark.lento
def test_medir_numa_leitura_bate_com_a_deteccao_do_clipador(tmp_path):
    v = _video(str(tmp_path / "v.mp4"))
    m, wav = reels.medir(v)
    assert m["cortes"] == 2 and [round(t) for t in m["tempos_corte"]] == [2, 4]
    assert m["tempos_corte"] == [round(t, 2) for t in midia.cortes_de_cena(v, 0.3)]   # mesma qualidade
    assert m["lufs"] is not None and 0.1 < m["silencio"] < 0.3
    assert wav and os.path.getsize(wav) > 0
    sem = _video(str(tmp_path / "mudo.mp4"), com_som=False)
    m2, wav2 = reels.medir(sem)
    assert m2["cortes"] == 2 and m2["lufs"] is None and wav2 is None
    parado = str(tmp_path / "parado.mp4")                       # sem nenhum corte: a saida nao pode ficar vazia
    ffmpeg("-f", "lavfi", "-i", "color=c=gray:s=360x640:d=3:r=30", "-c:v", "libx264", "-pix_fmt", "yuv420p", parado)
    assert reels.medir(parado)[0]["cortes"] == 0


@pytest.mark.lento
def test_lote_grava_medidas_folhas_e_apaga_os_videos(tmp_path, monkeypatch):
    origem = _video(str(tmp_path / "origem.mp4"))
    baixados = []

    def baixar_falso(itens, destino, cookies_navegador=None):
        out = {}
        for it in itens:
            chave = f"{it['conta']}_{it['id']}"
            if it["id"] == "foradoar":
                out[chave] = "erro: video indisponivel"
                continue
            out[chave] = shutil.copy(origem, os.path.join(destino, chave + ".mp4"))
            baixados.append(out[chave])
        return out
    falas = {}
    monkeypatch.setattr(reels, "baixar", baixar_falso)
    monkeypatch.setattr(reels, "transcrever_todos",
                        lambda wavs, modelo, paralelo: falas.update(wavs) or {k: {"palavras": 3, "ppm": 180.0,
                                                                                 "primeira_palavra": 0.0} for k in wavs})
    monkeypatch.setattr(reels, "PASTA", str(tmp_path / "reels"))
    itens = [reels.item("loja:AAA1", "top"), reels.item("loja:foradoar", "top"), reels.item("loja:BBB2", "controle")]
    d = reels.medir_lote("Teste Lote", itens, log=lambda *_: None)
    assert set(d["videos"]) == {"loja_AAA1", "loja_foradoar", "loja_BBB2"}
    assert "erro" in d["videos"]["loja_foradoar"] and d["videos"]["loja_AAA1"]["cortes"] == 2
    assert d["resumo"]["top"]["n"] == 1 and d["resumo"]["controle"]["n"] == 1
    assert set(falas) == {"loja_AAA1", "loja_BBB2"}                       # so os que tem som
    assert d["folhas"] and d["folhas"][0]["videos"] == ["loja_AAA1", "loja_BBB2"]
    pasta = reels.pasta("Teste Lote")
    assert os.path.exists(os.path.join(pasta, "folhas", d["folhas"][0]["imagem"]))
    assert json.load(open(os.path.join(pasta, "medidas.json"), encoding="utf-8"))["nome"] == "Teste Lote"
    assert baixados and not any(os.path.exists(b) for b in baixados)      # videos apagados no fim
