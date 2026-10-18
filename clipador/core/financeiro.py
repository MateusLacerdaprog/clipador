"""Modelo financeiro (Fase 11): separa o que foi OBSERVADO do que é PROJEÇÃO.

- Custos variáveis: IA (registro de uso real, só onde o custo é conhecido), tempo de produção e licenças
  lançados pelo usuário por projeto. Custos fixos: lançamentos mensais (ferramentas, armazenamento).
- Receita observada: coluna de receita do CSV do YouTube Studio (core/metricas.py).
- Projeção: só com parâmetros DIGITADOS pelo usuário (views, RPM, % monetizável), sempre rotulada como hipótese.
Nada de RPM ou taxa de conversão inventada. Valores em US$ (receita do Studio) e tempo em horas.
"""
from . import estudio, metricas, projeto

TIPOS = ("tempo_h", "licenca_usd", "fixo_mensal_usd", "outro_usd")


def lancar(dados):
    d = dados or {}
    tipo = d.get("tipo")
    if tipo not in TIPOS:
        raise ValueError(f"tipo deve ser um de: {', '.join(TIPOS)}")
    try:
        valor = float(d.get("valor"))
    except (TypeError, ValueError):
        raise ValueError("valor precisa ser um número")
    if valor < 0:
        raise ValueError("valor não pode ser negativo")
    c = {"id": estudio.novo_id("custo"), "tipo": tipo, "valor": valor, "projeto": d.get("projeto"), "canal": d.get("canal"),
         "mes": str(d.get("mes") or estudio.agora()[:7])[:7], "descricao": str(d.get("descricao") or "")[:200],
         "lancado_em": estudio.agora()}
    return estudio.gravar("custos", c)


def custo_ia_usd(projeto_nome=None, roteiro_ids=()):
    """Custo de IA registrado (só chamadas com custo conhecido) e quantas chamadas ficaram sem custo conhecido."""
    from .ia import uso
    alvo = {projeto_nome} | {f"roteiro:{r}" for r in roteiro_ids}
    regs = [r for r in uso.registros() if r.get("projeto") in alvo and r.get("ok")]
    return round(sum(r.get("custo_usd") or 0 for r in regs), 4), sum(1 for r in regs if r.get("custo_usd") is None)


def por_projeto(nome, valor_hora_usd=None):
    p = projeto.carregar(nome)
    lanc = [c for c in estudio.listar("custos") if c.get("projeto") == nome]
    ia, sem_custo = custo_ia_usd(nome, [p["roteiro_id"]] if p.get("roteiro_id") else [])
    horas = sum(c["valor"] for c in lanc if c["tipo"] == "tempo_h")
    licencas = sum(c["valor"] for c in lanc if c["tipo"] in ("licenca_usd", "outro_usd"))
    vid = (p.get("publicacao_registro") or {}).get("video_id")
    linha = metricas.ultimo(vid) if vid else None
    receita = (linha or {}).get("metricas", {}).get("receita_usd")
    custo_dinheiro = ia + licencas + (horas * valor_hora_usd if valor_hora_usd is not None else 0)
    return {"projeto": nome, "custo_ia_usd": ia, "chamadas_ia_sem_custo_conhecido": sem_custo, "horas": horas,
            "licencas_e_outros_usd": round(licencas, 2),
            "custo_total_usd": round(custo_dinheiro, 2), "inclui_tempo": valor_hora_usd is not None,
            "receita_observada_usd": receita, "lucro_realizado_usd": round(receita - custo_dinheiro, 2) if receita is not None else None,
            "observacao": "receita = coluna do CSV do Studio (estimada pelo YouTube até o pagamento); sem receita importada não há lucro realizado"}


def projecao(views_por_video, videos_por_mes, rpm_usd, pct_monetizavel=1.0, custo_variavel_por_video_usd=0.0, fixo_mensal_usd=0.0):
    """Cenário de HIPÓTESE com parâmetros do usuário (nunca preenchidos pelo sistema)."""
    for nome, v in (("views_por_video", views_por_video), ("videos_por_mes", videos_por_mes), ("rpm_usd", rpm_usd)):
        if v is None or v < 0:
            raise ValueError(f"informe {nome} (número ≥ 0): o Clipador não inventa esse valor")
    if not 0 <= pct_monetizavel <= 1:
        raise ValueError("pct_monetizavel entre 0 e 1")
    receita = views_por_video * videos_por_mes * pct_monetizavel * rpm_usd / 1000
    custos = custo_variavel_por_video_usd * videos_por_mes + fixo_mensal_usd
    return {"tipo": "PROJEÇÃO (hipótese do usuário)", "receita_mensal_usd": round(receita, 2), "custos_mensais_usd": round(custos, 2),
            "margem_mensal_usd": round(receita - custos, 2),
            "parametros": {"views_por_video": views_por_video, "videos_por_mes": videos_por_mes, "rpm_usd": rpm_usd,
                           "pct_monetizavel": pct_monetizavel, "custo_variavel_por_video_usd": custo_variavel_por_video_usd,
                           "fixo_mensal_usd": fixo_mensal_usd},
            "aviso": "não é previsão: depende de elegibilidade no YPP (10 mi de views de Shorts/90 dias a partir de 01/02/2027) e de RPM real"}
