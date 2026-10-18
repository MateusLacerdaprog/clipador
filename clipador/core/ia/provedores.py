"""Adaptadores: mesma interface para todos os provedores.

    listar_modelos() -> [str]
    gerar(sistema, prompt, schema=None, max_tokens=...) -> Resposta

Claude usa o SDK oficial `anthropic`; OpenAI usa `openai`; Gemini usa `google-genai`; Ollama usa a API HTTP
local dele. Erros viram ErroIA com tipo e mensagem em portugues, sem nunca incluir a chave.
"""
import json
import time
from dataclasses import dataclass, field

from . import config

# precos por 1M tokens (entrada, saida) — so onde ha fonte confiavel (tabela oficial da Anthropic, out/2026)
PRECOS_CLAUDE = {
    "claude-fable-5-1": (10.0, 50.0), "claude-fable-5": (10.0, 50.0), "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0), "claude-opus-4-8": (5.0, 25.0), "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0), "claude-haiku-5-5": (0.10, 0.50), "claude-haiku-4-5": (1.0, 5.0),
}
# modelos em que o fallback do servidor ("default") e recomendado para recusas falsas
COM_FALLBACK = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
COM_EFFORT = ("claude-opus-5", "claude-sonnet-5", "claude-fable-5", "claude-haiku-5", "claude-opus-4-8",
              "claude-opus-4-7")


class ErroIA(RuntimeError):
    def __init__(self, tipo, mensagem):
        super().__init__(mensagem)
        self.tipo = tipo           # credencial | limite | rede | modelo | recusa | resposta | config | outro


@dataclass
class Resposta:
    texto: str
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    dados: dict | list | None = None
    custo_usd: float | None = None
    duracao_s: float = 0.0
    extra: dict = field(default_factory=dict)


def custo(modelo, ent, sai):
    p = PRECOS_CLAUDE.get(modelo)
    return round((ent * p[0] + sai * p[1]) / 1e6, 5) if p else None


def _json(texto):
    t = texto.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("\n") + 1:] if "\n" in t else t
    try:
        return json.loads(t)
    except ValueError:
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except ValueError:
                pass
    raise ErroIA("resposta", "a IA respondeu num formato inesperado (não era JSON). Tente de novo.")


class Provedor:
    id = ""

    def __init__(self, modelo, chave=None, base_url=None):
        self.modelo, self.chave, self.base_url = modelo, chave, base_url

    def listar_modelos(self):
        raise NotImplementedError

    def gerar(self, sistema, prompt, schema=None, max_tokens=8000):
        if not self.modelo:
            raise ErroIA("config", "escolha um modelo para este provedor (Testar conexão lista os disponíveis)")
        t0 = time.time()
        r = self._gerar(sistema, prompt, schema, max_tokens)
        r.duracao_s = round(time.time() - t0, 2)
        if schema is not None and r.dados is None:
            r.dados = _json(r.texto)
        r.custo_usd = custo(r.modelo, r.tokens_entrada, r.tokens_saida)
        return r


# ------------------------------------------------------------------ Claude (SDK oficial anthropic)
class Claude(Provedor):
    id = "claude"

    def _cliente(self):
        import anthropic
        kw = {"max_retries": 2, "timeout": 120.0}
        if self.base_url:
            kw["base_url"] = self.base_url
        # sem chave salva, o SDK resolve sozinho (ANTHROPIC_API_KEY ou perfil do `ant auth login`)
        return anthropic.Anthropic(api_key=self.chave, **kw) if self.chave else anthropic.Anthropic(**kw)

    def _erro(self, e):
        import anthropic
        if isinstance(e, anthropic.AuthenticationError):
            return ErroIA("credencial", "chave da Anthropic inválida ou revogada")
        if isinstance(e, anthropic.PermissionDeniedError):
            return ErroIA("credencial", "a chave não tem permissão para este modelo/recurso")
        if isinstance(e, anthropic.NotFoundError):
            return ErroIA("modelo", f"modelo '{self.modelo}' não encontrado para esta conta")
        if isinstance(e, anthropic.RateLimitError):
            return ErroIA("limite", "limite de uso da Anthropic atingido; tente mais tarde")
        if isinstance(e, anthropic.BadRequestError):
            return ErroIA("outro", f"pedido recusado pela API: {getattr(e, 'message', e)}"[:300])
        if isinstance(e, anthropic.APIStatusError):
            return ErroIA("rede" if e.status_code >= 500 else "outro", f"erro da API ({e.status_code})")
        if isinstance(e, anthropic.APIConnectionError):
            return ErroIA("rede", "sem conexão com a Anthropic (internet ou firewall)")
        return ErroIA("outro", str(e)[:300])

    def listar_modelos(self):
        try:
            return [m.id for m in self._cliente().models.list(limit=100)]
        except Exception as e:  # noqa: BLE001
            raise self._erro(e) from None

    def _gerar(self, sistema, prompt, schema, max_tokens):
        kw = {"model": self.modelo, "max_tokens": max_tokens, "system": sistema,
              "messages": [{"role": "user", "content": prompt}]}
        oc = {}
        if self.modelo.startswith(COM_EFFORT):
            oc["effort"] = "medium"
        if schema is not None:
            oc["format"] = {"type": "json_schema", "schema": schema}
        if oc:
            kw["output_config"] = oc
        try:
            cli = self._cliente()
            if self.modelo in COM_FALLBACK:
                # recusa por engano do classificador e refeita no servidor por outro modelo (opt-in recomendado)
                r = cli.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
            else:
                r = cli.messages.create(**kw)
        except Exception as e:  # noqa: BLE001
            raise self._erro(e) from None
        if r.stop_reason == "refusal":
            raise ErroIA("recusa", "o modelo recusou este pedido. Reformule o texto e tente de novo.")
        texto = "".join(b.text for b in r.content if b.type == "text")
        if r.stop_reason == "max_tokens" and schema is not None:
            raise ErroIA("resposta", "a resposta foi cortada (limite de tokens de saída). Aumente o limite nas configurações.")
        return Resposta(texto=texto, modelo=r.model, tokens_entrada=r.usage.input_tokens,
                        tokens_saida=r.usage.output_tokens)


# ------------------------------------------------------------------ OpenAI (SDK oficial openai)
class OpenAI(Provedor):
    id = "openai"

    def _cliente(self):
        import openai
        kw = {"max_retries": 2, "timeout": 120.0}
        if self.base_url:
            kw["base_url"] = self.base_url
        return openai.OpenAI(api_key=self.chave, **kw)

    def _erro(self, e):
        import openai
        if isinstance(e, openai.AuthenticationError):
            return ErroIA("credencial", "chave da OpenAI inválida ou revogada")
        if isinstance(e, openai.NotFoundError):
            return ErroIA("modelo", f"modelo '{self.modelo}' não encontrado para esta conta")
        if isinstance(e, openai.RateLimitError):
            return ErroIA("limite", "limite de uso ou de crédito da OpenAI atingido")
        if isinstance(e, openai.APIStatusError):
            return ErroIA("rede" if e.status_code >= 500 else "outro", f"erro da API ({e.status_code})")
        if isinstance(e, openai.APIConnectionError):
            return ErroIA("rede", "sem conexão com a OpenAI (internet ou firewall)")
        return ErroIA("outro", str(e)[:300])

    def listar_modelos(self):
        if not self.chave:
            raise ErroIA("credencial", "falta a chave da OpenAI")
        try:
            return sorted(m.id for m in self._cliente().models.list())
        except Exception as e:  # noqa: BLE001
            raise self._erro(e) from None

    def _gerar(self, sistema, prompt, schema, max_tokens):
        if not self.chave:
            raise ErroIA("credencial", "falta a chave da OpenAI")
        kw = {"model": self.modelo, "instructions": sistema, "input": prompt, "max_output_tokens": max_tokens}
        if schema is not None:
            kw["text"] = {"format": {"type": "json_schema", "name": "resposta", "schema": schema, "strict": False}}
        try:
            r = self._cliente().responses.create(**kw)
        except Exception as e:  # noqa: BLE001
            raise self._erro(e) from None
        u = r.usage
        return Resposta(texto=r.output_text or "", modelo=r.model or self.modelo,
                        tokens_entrada=getattr(u, "input_tokens", 0) or 0,
                        tokens_saida=getattr(u, "output_tokens", 0) or 0)


# ------------------------------------------------------------------ Gemini (SDK oficial google-genai)
class Gemini(Provedor):
    id = "gemini"

    def _cliente(self):
        from google import genai
        from google.genai import types
        kw = {"api_key": self.chave}
        if self.base_url:
            kw["http_options"] = types.HttpOptions(base_url=self.base_url)
        return genai.Client(**kw)

    def _erro(self, e):
        from google.genai import errors
        if isinstance(e, errors.ClientError):
            cod = getattr(e, "code", 400)
            if cod in (401, 403) or "API_KEY" in str(e).upper():
                return ErroIA("credencial", "chave do Gemini inválida ou sem permissão")
            if cod == 404:
                return ErroIA("modelo", f"modelo '{self.modelo}' não encontrado")
            if cod == 429:
                return ErroIA("limite", "limite de uso do Gemini atingido")
            return ErroIA("outro", f"pedido recusado pelo Gemini ({cod})")
        if isinstance(e, errors.ServerError):
            return ErroIA("rede", "o Gemini está com instabilidade; tente mais tarde")
        if "connect" in type(e).__name__.lower() or "timeout" in type(e).__name__.lower():
            return ErroIA("rede", "sem conexão com o Gemini (internet ou firewall)")
        return ErroIA("outro", str(e)[:300])

    def listar_modelos(self):
        if not self.chave:
            raise ErroIA("credencial", "falta a chave do Gemini")
        try:
            cli = self._cliente()   # manter a referencia: o Client do genai se fecha ao ser coletado
            return sorted((m.name or "").removeprefix("models/") for m in cli.models.list())
        except Exception as e:  # noqa: BLE001
            raise self._erro(e) from None

    def _gerar(self, sistema, prompt, schema, max_tokens):
        from google.genai import types
        if not self.chave:
            raise ErroIA("credencial", "falta a chave do Gemini")
        cfg = {"system_instruction": sistema, "max_output_tokens": max_tokens}
        if schema is not None:
            cfg.update(response_mime_type="application/json", response_json_schema=schema)
        try:
            cli = self._cliente()
            r = cli.models.generate_content(model=self.modelo, contents=prompt, config=types.GenerateContentConfig(**cfg))
        except Exception as e:  # noqa: BLE001
            raise self._erro(e) from None
        u = r.usage_metadata
        return Resposta(texto=r.text or "", modelo=self.modelo,
                        tokens_entrada=getattr(u, "prompt_token_count", 0) or 0,
                        tokens_saida=getattr(u, "candidates_token_count", 0) or 0)


# ------------------------------------------------------------------ Ollama (local, HTTP)
class Ollama(Provedor):
    id = "ollama"

    def _url(self, caminho):
        return (self.base_url or config.carregar()["ollama_url"]).rstrip("/") + caminho

    def _http(self, metodo, caminho, corpo=None, timeout=300):
        import httpx
        try:
            r = httpx.request(metodo, self._url(caminho), json=corpo, timeout=timeout)
        except httpx.HTTPError:
            raise ErroIA("rede", "o Ollama não está rodando neste PC (instale e abra o Ollama)") from None
        if r.status_code == 404:
            raise ErroIA("modelo", f"modelo '{self.modelo}' não instalado no Ollama (rode: ollama pull {self.modelo})")
        if r.status_code >= 400:
            raise ErroIA("outro", f"o Ollama respondeu com erro {r.status_code}")
        return r.json()

    def listar_modelos(self):
        return sorted(m["name"] for m in self._http("GET", "/api/tags", timeout=5).get("models", []))

    def _gerar(self, sistema, prompt, schema, max_tokens):
        corpo = {"model": self.modelo, "stream": False, "options": {"num_predict": max_tokens},
                 "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": prompt}]}
        if schema is not None:
            corpo["format"] = schema
        d = self._http("POST", "/api/chat", corpo)
        return Resposta(texto=(d.get("message") or {}).get("content", ""), modelo=d.get("model", self.modelo),
                        tokens_entrada=d.get("prompt_eval_count", 0) or 0, tokens_saida=d.get("eval_count", 0) or 0)


CLASSES = {"claude": Claude, "openai": OpenAI, "gemini": Gemini, "ollama": Ollama}


def criar(provedor, cfg=None, base_url=None):
    if provedor not in CLASSES:
        raise ErroIA("config", "provedor desconhecido")
    cfg = cfg or config.carregar()
    chave, _ = config.obter_chave(provedor)
    return CLASSES[provedor](cfg["provedores"][provedor].get("modelo") or "", chave, base_url)
