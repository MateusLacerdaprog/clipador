"""Configuracao da IA (sem segredos) em config/ia.json + credenciais no cofre do Windows."""
import copy
import json
import os

from .. import projeto

PASTA = os.path.join(os.path.dirname(projeto.RAIZ), "config")
ARQ = os.path.join(PASTA, "ia.json")
SERVICO_COFRE = os.environ.get("CLIPADOR_COFRE", "Clipador-IA")

PROVEDORES = {
    "claude": {"nome": "Anthropic Claude", "env": ["ANTHROPIC_API_KEY"], "modelo_padrao": "claude-opus-5-5",
               "painel": "https://platform.claude.com/settings/keys", "precisa_chave": True},
    "openai": {"nome": "OpenAI", "env": ["OPENAI_API_KEY"], "modelo_padrao": "",
               "painel": "https://platform.openai.com/api-keys", "precisa_chave": True},
    "gemini": {"nome": "Google Gemini", "env": ["GEMINI_API_KEY", "GOOGLE_API_KEY"], "modelo_padrao": "",
               "painel": "https://aistudio.google.com/apikey", "precisa_chave": True},
    "ollama": {"nome": "Ollama (local, no seu PC)", "env": [], "modelo_padrao": "",
               "painel": "https://ollama.com/download", "precisa_chave": False},
}

PADRAO = {
    "provedor_ativo": None,
    "provedores": {pid: {"modelo": p["modelo_padrao"], "consentimento": False} for pid, p in PROVEDORES.items()},
    "ollama_url": "http://127.0.0.1:11434",
    "limites": {"chamadas_por_dia": 40, "max_tokens_saida": 8000, "orcamento_mensal_usd": 5.0},
    "historico": {"ativo": True, "guardar_conteudo": False},
}


def carregar():
    c = copy.deepcopy(PADRAO)
    if os.path.isfile(ARQ):
        try:
            with open(ARQ, encoding="utf-8") as f:
                salvo = json.load(f)
        except (OSError, ValueError):
            salvo = {}
        for k, v in salvo.items():
            if k == "provedores":
                for pid, cfg in (v or {}).items():
                    if pid in c["provedores"]:
                        c["provedores"][pid].update(cfg)
            elif isinstance(v, dict) and isinstance(c.get(k), dict):
                c[k].update(v)
            elif k in c:
                c[k] = v
    return c


def salvar(c):
    os.makedirs(PASTA, exist_ok=True)
    tmp = ARQ + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ARQ)


# ------------------------------------------------------------------ credenciais
def _keyring():
    import keyring
    return keyring


def salvar_chave(provedor, chave):
    chave = (chave or "").strip()
    if provedor not in PROVEDORES or not PROVEDORES[provedor]["precisa_chave"]:
        raise ValueError("provedor invalido")
    if len(chave) < 12 or any(ch.isspace() for ch in chave):
        raise ValueError("a chave parece incompleta")
    _keyring().set_password(SERVICO_COFRE, provedor, chave)


def apagar_chave(provedor):
    try:
        _keyring().delete_password(SERVICO_COFRE, provedor)
    except Exception:  # noqa: BLE001 - nao existia
        pass


def obter_chave(provedor):
    """(chave, origem) — origem descreve de onde veio, sem revelar a chave."""
    try:
        k = _keyring().get_password(SERVICO_COFRE, provedor)
    except Exception:  # noqa: BLE001 - cofre indisponivel
        k = None
    if k:
        return k, "cofre do Windows"
    for var in PROVEDORES.get(provedor, {}).get("env", []):
        if os.environ.get(var):
            return os.environ[var], f"variável de ambiente {var}"
    return None, None


def mascarar(chave):
    return f"••••{chave[-4:]}" if chave else None
