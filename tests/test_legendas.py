"""Regras de legenda do CLAUDE.md (regra 2): limites, sem sobreposicao, sem duracao minima artificial."""
import re

from clipador.core import legendas


def _palavras(texto, inicio=0.0, passo=0.3, pausa_em=()):
    out, t = [], inicio
    for i, w in enumerate(texto.split()):
        if i in pausa_em:
            t += 0.6
        out.append({"w": w, "start": round(t, 3), "end": round(t + passo * 0.9, 3)})
        t += passo
    return out


TEXTO = ("O novo trailer de lançamento do GTA VI acabou de confirmar as missões desse jogo, "
         "vão ser as mais insanas da história da Rockstar. Repara bem nessa cena de perseguição.")


def test_limites_por_estilo():
    for estilo, E in legendas.ESTILOS.items():
        cart = legendas.construir_cartoes(_palavras(TEXTO), estilo)
        for c in cart:
            txt = " ".join(p["w"] for p in c["palavras"])
            assert len(c["palavras"]) <= E["max_palavras"], (estilo, txt)
            assert len(txt) <= E["max_chars"] or len(c["palavras"]) == 1, (estilo, txt)


def test_sem_sobreposicao_e_sem_duracao_minima(tmp_path):
    cart = legendas.construir_cartoes(_palavras(TEXTO, passo=0.12), "karaoke")
    ass = tmp_path / "l.ass"
    legendas.gerar_ass(str(ass), cart, "karaoke", "empilhado")
    eventos = []
    for linha in ass.read_text(encoding="utf-8").splitlines():
        if linha.startswith("Dialogue: 0,"):
            _, ini, fim = linha.split(",")[:3]
            conv = lambda s: int(s[0]) * 3600 + int(s[2:4]) * 60 + float(s[5:])  # noqa: E731
            eventos.append((conv(ini), conv(fim)))
    assert eventos
    for (a0, a1), (b0, b1) in zip(eventos, eventos[1:]):
        assert a1 <= b0 + 1e-6, "legendas se sobrepoem"
    # sem duracao minima: palavras rapidas (0.12 s) geram eventos curtos
    assert min(b - a for a, b in eventos) < 0.3


def test_quebra_em_pausa_e_pontuacao():
    cart = legendas.construir_cartoes(_palavras("um dois tres. quatro cinco", pausa_em=()), "karaoke")
    textos = [" ".join(p["w"] for p in c["palavras"]) for c in cart]
    assert textos[0] == "um dois tres"
    cart = legendas.construir_cartoes(_palavras("um dois tres quatro", pausa_em=(2,)), "karaoke")
    assert [" ".join(p["w"] for p in c["palavras"]) for c in cart][0] == "um dois"


def test_nao_termina_em_preposicao_quando_cabe():
    cart = legendas.construir_cartoes(_palavras("vão ser as mais insanas da história da Rockstar"), "palavra")
    for c in cart[:-1]:
        ultima = c["palavras"][-1]["w"].lower()
        if ultima in legendas.LIGACAO:
            # so pode sobrar se o proximo cartao estiver cheio
            assert len(cart[cart.index(c) + 1]["palavras"]) >= legendas.ESTILOS["palavra"]["max_palavras"]


def test_edicao_mantem_tempo_e_tira_pontuacao():
    cart = legendas.construir_cartoes(_palavras("ola mundo bonito"), "karaoke")
    antes = [(p["start"], p["end"]) for p in cart[0]["palavras"]]
    legendas.aplicar_texto(cart[0], "Olá, mundo bonito!")
    assert [p["w"] for p in cart[0]["palavras"]] == ["Olá", "mundo", "bonito"]
    assert [(p["start"], p["end"]) for p in cart[0]["palavras"]] == antes
    legendas.aplicar_texto(cart[0], "duas palavras")
    assert len(cart[0]["palavras"]) == 2 and cart[0]["palavras"][-1]["end"] == antes[-1][1]


def test_ass_escapa_chaves_e_barras(tmp_path):
    cart = [{"palavras": [{"w": "{\\pos(0,0)}hack", "start": 0, "end": 1}]}]
    ass = tmp_path / "x.ass"
    legendas.gerar_ass(str(ass), cart, "karaoke", "empilhado", gancho={"texto": "a{b}\\c", "ate": 2})
    corpo = ass.read_text(encoding="utf-8").split("[Events]")[1]
    assert "\\pos(0,0)}hack" not in corpo and "{b}" not in corpo


def test_gancho_sem_palavra_orfa():
    t = legendas._quebra_titulo("O QUE NINGUÉM VIU NO TRAILER DE GTA 6")
    linhas = t.split("\\N")
    assert len(linhas) >= 2 and all(len(l.split()) >= 2 for l in linhas), linhas


def test_estilo_karaoke_usa_amarelo_e_posicao_safe_zone(tmp_path):
    cart = legendas.construir_cartoes(_palavras("teste de cor"), "karaoke")
    ass = tmp_path / "k.ass"
    legendas.gerar_ass(str(ass), cart, "karaoke", "empilhado")
    corpo = ass.read_text(encoding="utf-8")
    assert "\\c&H00DEFF&" in corpo and re.search(r"\\pos\(\d+,1330\)", corpo)
    assert "Arial Black,88" in corpo
