"""Tarefas de assistencia editorial. Cada uma: monta o texto (que o usuario pode ver antes), envia ao provedor
ativo e devolve SUGESTOES editaveis. Nada e aplicado ao projeto sem o usuario clicar."""
import datetime as dt
import json
import os

from .. import formatos, projeto, referencias
from . import config, uso
from .provedores import ErroIA, criar

SISTEMA = (
    "Você é editor de vídeos de games para YouTube Shorts, TikTok, Reels e YouTube. Escreve em português do Brasil, "
    "de forma direta. Baseie-se apenas nas informações do projeto enviadas; não invente fatos sobre jogos "
    "(se algo não estiver no material, diga que precisa ser confirmado). Não prometa views nem viralização. "
    "Nunca copie títulos, falas ou bordões de criadores citados como referência: use só as técnicas descritas."
)

_S = {"type": "string"}
SCHEMAS = {
    "titulos": {"type": "object", "properties": {
        "titulos": {"type": "array", "items": {"type": "object", "properties": {"texto": _S, "porque": _S},
                                               "required": ["texto", "porque"]}},
        "ganchos": {"type": "array", "items": {"type": "object", "properties": {"texto": _S, "porque": _S},
                                               "required": ["texto", "porque"]}},
        "descricao": _S, "hashtags": {"type": "array", "items": _S}},
        "required": ["titulos", "ganchos", "descricao", "hashtags"]},
    "roteiro": {"type": "object", "properties": {
        "roteiro": _S, "gancho": _S, "duracao_estimada_s": {"type": "number"},
        "notas": {"type": "array", "items": _S}, "a_confirmar": {"type": "array", "items": _S}},
        "required": ["roteiro", "gancho", "notas", "a_confirmar"]},
    "revisao": {"type": "object", "properties": {
        "pontos_fortes": {"type": "array", "items": _S},
        "problemas": {"type": "array", "items": {"type": "object", "properties": {
            "item": _S, "sugestao": _S, "prioridade": {"type": "string", "enum": ["alta", "media", "baixa"]}},
            "required": ["item", "sugestao", "prioridade"]}},
        "nota_gancho": {"type": "integer"}, "resumo": _S},
        "required": ["pontos_fortes", "problemas", "nota_gancho", "resumo"]},
}
TAREFAS = {"titulos": "Títulos, ganchos, descrição e hashtags", "roteiro": "Roteiro no formato do projeto",
           "revisao": "Revisão editorial do projeto"}


def _texto_legenda(p):
    c = os.path.join(projeto.pasta(p["nome"]), "legenda_cartoes.json")
    if not os.path.isfile(c):
        return ""
    with open(c, encoding="utf-8") as f:
        return " ".join(w["w"] for cart in json.load(f) for w in cart["palavras"])[:6000]


def contexto(p, perfil_id=None):
    g = formatos.guia({**p, "duracao_atual": projeto.duracao_timeline(p)})
    linhas = [f"Tipo: vídeo {'longo (YouTube 16:9)' if p.get('tipo') == 'longo' else 'curto (Shorts/TikTok/Reels 9:16)'}",
              f"Formato: {g['nome']} — {g['descricao']}",
              f"Duração atual da montagem: {projeto.duracao_timeline(p):.0f} s (alvo do formato: {g['duracao_alvo'] or 'livre'} s)",
              "Estrutura recomendada do formato: " + "; ".join(f"{b['nome']} ({b['dica']})" for b in g["estrutura"]),
              f"Gancho na tela: {p['gancho'].get('texto') or '(nenhum)'}",
              f"Trechos/capítulos: {', '.join(s['rotulo'] for s in p['segmentos'] if s.get('rotulo')) or '(sem rótulos)'}",
              f"Roteiro atual:\n{(p.get('roteiro') or '(vazio)')[:4000]}"]
    leg = _texto_legenda(p)
    if leg:
        linhas.append(f"Transcrição da narração:\n{leg}")
    if perfil_id:
        perf = referencias.carregar(perfil_id)
        cmp = referencias.comparar(p, perf)
        linhas.append(f"Perfil de referência editorial '{perf['nome']}' (técnicas medidas; não copie conteúdo): "
                      + json.dumps(perf["derivado"].get(p.get("tipo", "curto"), {}), ensure_ascii=False))
        linhas.append("Comparação automática com a referência: " + "; ".join(
            f"{i['aspecto']}: ref {i['referencia']} / projeto {i['seu_projeto']}" for i in cmp["itens"]))
    return "\n".join(linhas)


def montar(p, tarefa, extra="", perfil_id=None):
    if tarefa not in TAREFAS:
        raise ErroIA("config", "tarefa desconhecida")
    pedidos = {
        "titulos": "Sugira 5 títulos e 3 textos de gancho para a tela (curtos, impactantes, sem clickbait enganoso), "
                   "uma descrição pronta para colar (com os capítulos se houver) e até 8 hashtags. Explique cada escolha em uma frase.",
        "roteiro": "Escreva um roteiro de narração para este projeto seguindo a estrutura do formato, com gancho na "
                   "primeira frase e final que emende no começo (sem despedida). Liste o que precisa ser confirmado.",
        "revisao": "Revise o projeto como editor: pontos fortes, problemas com sugestão concreta e prioridade, e uma "
                   "nota de 0 a 10 para o gancho. Seja específico para este material.",
    }
    prompt = f"{contexto(p, perfil_id)}\n\nPedido: {pedidos[tarefa]}"
    if extra.strip():
        prompt += f"\nObservações do usuário: {extra.strip()[:1500]}"
    return {"sistema": SISTEMA, "prompt": prompt, "schema": SCHEMAS[tarefa]}


def executar(p, tarefa, extra="", perfil_id=None, progresso=lambda f, m=None: None, base_url=None):
    resultado = enviar(p, tarefa, montar(p, tarefa, extra, perfil_id), progresso, base_url)
    resultado["perfil"] = perfil_id
    _guardar_sugestao(p["nome"], resultado)
    return resultado


def enviar(p, tarefa, pedido, progresso=lambda f, m=None: None, base_url=None):
    """Envia {sistema, prompt, schema} ao provedor ativo com as mesmas regras de consentimento, limites e historico."""
    cfg = config.carregar()
    pid = cfg.get("provedor_ativo")
    if not pid:
        raise ErroIA("config", "nenhum provedor de IA ativo. Configure em Provedores de IA (a edição manual continua funcionando).")
    if not cfg["provedores"][pid].get("consentimento"):
        raise ErroIA("config", "confirme em Provedores de IA que aceita enviar o texto do projeto para este provedor")
    uso.verificar_limites(cfg)
    progresso(0.2, f"enviando para {config.PROVEDORES[pid]['nome']}")
    prov = criar(pid, cfg, base_url)
    reg = {"data": dt.datetime.now().isoformat(timespec="seconds"), "provedor": pid, "modelo": prov.modelo,
           "tarefa": tarefa, "projeto": p["nome"]}
    try:
        r = prov.gerar(pedido["sistema"], pedido["prompt"], pedido["schema"], int(cfg["limites"]["max_tokens_saida"]))
    except ErroIA as e:
        uso.registrar({**reg, "ok": False, "erro": e.tipo, "enviado": pedido["prompt"]}, cfg)
        raise
    uso.registrar({**reg, "ok": True, "tokens_entrada": r.tokens_entrada, "tokens_saida": r.tokens_saida,
                   "custo_usd": r.custo_usd, "duracao_s": r.duracao_s, "enviado": pedido["prompt"],
                   "resposta": r.texto}, cfg)
    return {"tarefa": tarefa, "data": reg["data"], "origem": f"sugestão da IA ({config.PROVEDORES[pid]['nome']}, {r.modelo})",
            "dados": r.dados, "tokens": {"entrada": r.tokens_entrada, "saida": r.tokens_saida}, "custo_usd": r.custo_usd}


def _guardar_sugestao(nome, resultado):
    c = os.path.join(projeto.pasta(nome), "ia_sugestoes.json")
    lista = []
    if os.path.isfile(c):
        try:
            with open(c, encoding="utf-8") as f:
                lista = json.load(f)
        except ValueError:
            lista = []
    lista = ([resultado] + lista)[:20]
    with open(c + ".tmp", "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=1)
    os.replace(c + ".tmp", c)


def sugestoes(nome):
    c = os.path.join(projeto.pasta(nome), "ia_sugestoes.json")
    if not os.path.isfile(c):
        return []
    with open(c, encoding="utf-8") as f:
        return json.load(f)
