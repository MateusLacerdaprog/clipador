"""Métricas reais do canal a partir do CSV exportado pelo YouTube Studio (modo avançado → Exportar → CSV).
Sem OAuth: o usuário exporta e o Clipador importa. Cada importação vira um "retrato" datado em estudio/metricas/.

Colunas reconhecidas por SINÔNIMOS (inglês e português); colunas desconhecidas ficam em "extra" e são listadas
como não reconhecidas — nada é descartado em silêncio. Os nomes exatos variam com o idioma do Studio:
PENDENTE validar com um export real do usuário (docs/cpv/08).
"""
import csv
import io
import os
import re
import time
import unicodedata

from . import estudio

SINONIMOS = {  # campo: regex sobre o nome da coluna (minúsculo, sem acento)
    "video_id": r"^(content|conteudo|video id|id do video)$",
    "titulo": r"^(video title|titulo do video|titulo)$",
    "publicado": r"(publish time|publication|horario de publicacao|data de publicacao)",
    "duracao_s": r"^(duration|duracao)$",
    "views": r"^(views|visualizacoes)$",
    "views_engajadas": r"(engaged views|visualizacoes engajadas)",
    "horas_exibicao": r"(watch time|tempo de exibicao)",
    "duracao_media_s": r"(average view duration|duracao media)",
    "pct_assistido": r"(average percentage viewed|porcentagem media)",
    "escolheram_assistir_pct": r"(stayed to watch|viewed vs|escolheram assistir|ficaram para assistir|deslizad)",
    "likes": r"^(likes|marcacoes gostei|gostei)$",
    "comentarios": r"^(comments added|comments|comentarios adicionados|comentarios)$",
    "compartilhamentos": r"^(shares|compartilhamentos)$",
    "inscritos": r"^(subscribers|inscritos|inscricoes)$",
    "receita_usd": r"(estimated revenue|receita estimada)",
    "rpm_usd": r"^rpm",
    "impressoes": r"^(impressions|impressoes)$",
}
TEXTO = ("video_id", "titulo", "publicado")


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"\s+", " ", s)


def _numero(v):
    v = str(v or "").strip().replace(" ", "").replace("%", "")
    if not v or v in ("-", "—"):
        return None
    if re.fullmatch(r"\d+:\d{1,2}(:\d{1,2})?", v):           # 0:00:23 ou 0:23 → segundos
        partes = [int(x) for x in v.split(":")]
        while len(partes) < 3:
            partes.insert(0, 0)
        return partes[0] * 3600 + partes[1] * 60 + partes[2]
    if "," in v and "." in v:                                # 1,234.5 (en) ou 1.234,5 (pt)
        v = v.replace(",", "") if v.rfind(".") > v.rfind(",") else v.replace(".", "").replace(",", ".")
    elif "," in v:
        v = v.replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def ler_csv(conteudo):
    """Texto do CSV → (linhas normalizadas, colunas não reconhecidas). Ignora a linha 'Total'."""
    amostra = conteudo[:2000]
    sep = ";" if amostra.count(";") > amostra.count(",") else ","
    leitor = csv.DictReader(io.StringIO(conteudo), delimiter=sep)
    mapa, desconhecidas = {}, []
    for col in leitor.fieldnames or []:
        campo = next((k for k, rx in SINONIMOS.items() if re.search(rx, _norm(col))), None)
        if campo and campo not in mapa.values():
            mapa[col] = campo
        else:
            desconhecidas.append(col)
    if "video_id" not in mapa.values():
        raise ValueError("o CSV não tem a coluna do vídeo (Content/Conteúdo): exporte a tabela por vídeo no modo avançado")
    linhas = []
    for row in leitor:
        reg = {"metricas": {}, "extra": {}}
        for col, val in row.items():
            if col in mapa:
                campo = mapa[col]
                reg[campo] = str(val or "").strip() if campo in TEXTO else None
                if campo not in TEXTO:
                    reg["metricas"][campo] = _numero(val)
            elif col:
                reg["extra"][col] = val
        vid = reg.get("video_id") or ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):          # linha "Total" e afins
            continue
        linhas.append(reg)
    return linhas, desconhecidas


def importar(caminho, canal=None):
    if not os.path.isfile(caminho):
        raise FileNotFoundError(f"arquivo não encontrado: {caminho}")
    with open(caminho, encoding="utf-8-sig") as f:
        linhas, desconhecidas = ler_csv(f.read())
    return gravar_retrato(linhas, desconhecidas, os.path.basename(caminho), canal)


def gravar_retrato(linhas, desconhecidas, arquivo, canal=None):
    snap = {"id": estudio.novo_id("metricas"), "importado_em": estudio.agora(), "ordem": time.time_ns(),
            "arquivo": str(arquivo)[:120], "canal": canal, "linhas": linhas, "colunas_nao_reconhecidas": desconhecidas}
    return estudio.gravar("metricas", snap)


def retratos():
    # "ordem" desempata importações no mesmo segundo (o último retrato tem de ser o último importado)
    return sorted(estudio.listar("metricas"), key=lambda s: (s["importado_em"], s.get("ordem", 0)))


def serie(video_id):
    """[(importado_em, linha)] do vídeo em todos os retratos, do mais antigo ao mais novo."""
    return [(s["importado_em"], l) for s in retratos() for l in s["linhas"] if l.get("video_id") == video_id]


def ultimo(video_id):
    s = serie(video_id)
    return s[-1][1] if s else None
