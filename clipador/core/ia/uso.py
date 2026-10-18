"""Limites de uso e historico de tarefas de IA (por padrao so metadados: nada do conteudo e guardado)."""
import datetime as dt
import json
import os
import threading

from . import config

ARQ = os.path.join(config.PASTA, "ia_historico.jsonl")
_trava = threading.Lock()


def registros():
    if not os.path.isfile(ARQ):
        return []
    out = []
    with open(ARQ, encoding="utf-8") as f:
        for linha in f:
            try:
                out.append(json.loads(linha))
            except ValueError:
                continue
    return out


def registrar(reg, cfg=None):
    cfg = cfg or config.carregar()
    if not cfg["historico"]["ativo"]:
        return
    if not cfg["historico"]["guardar_conteudo"]:
        reg = {k: v for k, v in reg.items() if k not in ("enviado", "resposta")}
    os.makedirs(config.PASTA, exist_ok=True)
    with _trava, open(ARQ, "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")


def apagar():
    with _trava:
        if os.path.isfile(ARQ):
            os.remove(ARQ)


def resumo():
    hoje = dt.date.today().isoformat()
    mes = hoje[:7]
    regs = registros()
    return {"chamadas_hoje": sum(1 for r in regs if r.get("data", "").startswith(hoje)),
            "custo_mes_usd": round(sum(r.get("custo_usd") or 0 for r in regs if r.get("data", "").startswith(mes)), 4),
            "chamadas_mes": sum(1 for r in regs if r.get("data", "").startswith(mes))}


def verificar_limites(cfg):
    """Levanta ErroIA se um limite configurado ja foi atingido."""
    from .provedores import ErroIA
    lim = cfg["limites"]
    r = resumo()
    if r["chamadas_hoje"] >= int(lim["chamadas_por_dia"]):
        raise ErroIA("limite", f"limite de {lim['chamadas_por_dia']} chamadas por dia atingido (ajuste em Provedores de IA)")
    if lim.get("orcamento_mensal_usd") and r["custo_mes_usd"] >= float(lim["orcamento_mensal_usd"]):
        raise ErroIA("limite", f"orçamento mensal de US$ {lim['orcamento_mensal_usd']} atingido (só conta custos conhecidos)")
