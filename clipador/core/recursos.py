"""Origem e licença de cada mídia (vídeo-fonte, música, efeito): base das verificações de direitos e de conteúdo
reutilizado (docs/cpv/04). Registrar não prova direito: é a declaração do usuário + o que foi verificado.

Vídeo-fonte: `projeto.fontes[i].direitos`. Biblioteca (musicas/, efeitos/): `<pasta>/_direitos.json`.
"""
import datetime as dt
import json
import os

ORIGENS = {
    "proprio": "Material próprio (gravado ou criado por você)",
    "licenciado": "Licenciado (você tem licença ou permissão)",
    "dominio_publico": "Domínio público ou licença livre",
    "terceiros": "De terceiros, sem licença (só com comentário/transformação)",
    "nao_informado": "Não informado",
}
PADRAO = {"origem": "nao_informado", "licenca": "", "link": "", "obs": "", "registrado_em": None}
ARQ_BIBLIOTECA = "_direitos.json"


def completar(d):
    out = dict(PADRAO)
    if isinstance(d, dict):
        out.update({k: d[k] for k in PADRAO if k in d})
    if out["origem"] not in ORIGENS:
        out["origem"] = "nao_informado"
    return out


def validar(d):
    """Valida o que veio do usuário. Licença é obrigatória para 'licenciado' e 'dominio_publico'."""
    d = d or {}
    origem = d.get("origem", "nao_informado")
    if origem not in ORIGENS:
        raise ValueError(f"origem inválida (use: {', '.join(ORIGENS)})")
    licenca = str(d.get("licenca") or "").strip()[:200]
    link = str(d.get("link") or "").strip()[:500]
    if link and not link.startswith(("https://", "http://")):
        raise ValueError("o link da licença/fonte precisa começar com http:// ou https://")
    if origem in ("licenciado", "dominio_publico") and not licenca:
        raise ValueError("diga qual é a licença (ex.: 'Natural Earth, domínio público', 'YouTube Audio Library')")
    return {"origem": origem, "licenca": licenca, "link": link, "obs": str(d.get("obs") or "").strip()[:500],
            "registrado_em": dt.date.today().isoformat()}


def precisa_atencao(d):
    """Mídia que não dá para defender sem comentário/transformação: de terceiros ou sem informação."""
    return completar(d)["origem"] in ("terceiros", "nao_informado")


# ------------------------------------------------------------------ biblioteca de áudio
def biblioteca_ler(pasta):
    c = os.path.join(pasta, ARQ_BIBLIOTECA)
    if not os.path.isfile(c):
        return {}
    with open(c, encoding="utf-8") as f:
        dados = json.load(f)
    return {k: completar(v) for k, v in dados.items()} if isinstance(dados, dict) else {}


def biblioteca_gravar(pasta, nome, d):
    todos = biblioteca_ler(pasta)
    todos[os.path.basename(nome)] = validar(d)
    os.makedirs(pasta, exist_ok=True)
    tmp = os.path.join(pasta, ARQ_BIBLIOTECA + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(pasta, ARQ_BIBLIOTECA))
    return todos[os.path.basename(nome)]


# ------------------------------------------------------------------ uso na montagem
def tempo_por_origem(p):
    """Segundos da montagem por origem do vídeo-fonte (na comparação A×B conta a fonte A, que fica em cima e é a
    referência do trecho). Quadro congelado conta como a fonte de onde o quadro saiu."""
    fontes = {f["id"]: completar(f.get("direitos")) for f in p.get("fontes", [])}
    out = {k: 0.0 for k in ORIGENS}
    for s in p.get("segmentos", []):
        origem = fontes.get(s.get("fonte"), PADRAO)["origem"]
        out[origem] += max(0.0, s["fim"] - s["ini"])
    return {k: round(v, 2) for k, v in out.items() if v}
