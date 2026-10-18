"""Camada de IA.

REAL      : cofre do Windows (keyring), erros de chave invalida nas APIs oficiais (rede, sem custo), limites,
            privacidade do historico, chave nunca exposta.
SIMULADO  : respostas de SUCESSO vem de um servidor local que imita cada API (marcado `simulado`), porque
            nao ha chave real nos testes. Valida montagem do pedido, leitura da resposta, JSON, tokens e custo.
"""
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from clipador.core import projeto
from clipador.core.ia import assistente, config, uso
from clipador.core.ia.provedores import ErroIA, criar
from clipador.web.app import app

CHAVE_FALSA = "sk-teste-NAO-E-REAL-1234567890abcdef"
JSON_TITULOS = {"titulos": [{"texto": "O detalhe escondido de GTA 6", "porque": "curiosidade"}],
                "ganchos": [{"texto": "VOCÊ VIU ISSO?", "porque": "pergunta"}],
                "descricao": "Descrição de teste", "hashtags": ["#gta6"]}


@pytest.fixture()
def cli():
    return TestClient(app, base_url="http://127.0.0.1:8765")


@pytest.fixture(autouse=True)
def limpar_ia():
    for p in config.PROVEDORES:
        config.apagar_chave(p)
    uso.apagar()
    config.salvar(json.loads(json.dumps(config.PADRAO)))
    yield
    for p in config.PROVEDORES:
        config.apagar_chave(p)
    uso.apagar()


def tem_internet():
    try:
        socket.create_connection(("api.anthropic.com", 443), timeout=3).close()
        return True
    except OSError:
        return False


# ------------------------------------------------------------------ servidor que imita as APIs (SIMULADO)
class Imitador(BaseHTTPRequestHandler):
    pedidos = []

    def log_message(self, *a):
        pass

    def _resp(self, obj, cod=200):
        corpo = json.dumps(obj).encode()
        self.send_response(cod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        Imitador.pedidos.append(("GET", self.path, dict(self.headers), None))
        if self.path.startswith("/api/tags"):
            return self._resp({"models": [{"name": "modelo-local"}]})
        self._resp({"error": "nao encontrado"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        corpo = json.loads(self.rfile.read(n) or b"{}")
        Imitador.pedidos.append(("POST", self.path, dict(self.headers), corpo))
        texto = json.dumps(JSON_TITULOS, ensure_ascii=False)
        if self.path.startswith("/v1/messages"):          # Anthropic
            return self._resp({"id": "msg_1", "type": "message", "role": "assistant", "model": corpo["model"],
                               "content": [{"type": "text", "text": texto}], "stop_reason": "end_turn",
                               "stop_sequence": None, "usage": {"input_tokens": 1000, "output_tokens": 200}})
        if self.path.startswith("/v1/responses") or self.path.startswith("/responses"):   # OpenAI
            return self._resp({"id": "resp_1", "object": "response", "created_at": 0, "model": corpo["model"],
                               "status": "completed", "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
                               "output": [{"type": "message", "id": "m1", "status": "completed", "role": "assistant",
                                           "content": [{"type": "output_text", "text": texto, "annotations": []}]}],
                               "usage": {"input_tokens": 900, "output_tokens": 150, "total_tokens": 1050,
                                         "input_tokens_details": {"cached_tokens": 0},
                                         "output_tokens_details": {"reasoning_tokens": 0}}})
        if ":generateContent" in self.path:                # Gemini
            return self._resp({"candidates": [{"content": {"role": "model", "parts": [{"text": texto}]}}],
                               "usageMetadata": {"promptTokenCount": 800, "candidatesTokenCount": 120}})
        if self.path.startswith("/api/chat"):              # Ollama
            return self._resp({"model": corpo["model"], "message": {"role": "assistant", "content": texto},
                               "prompt_eval_count": 700, "eval_count": 90})
        self._resp({"error": "rota desconhecida"}, 404)


@pytest.fixture()
def imitador():
    srv = HTTPServer(("127.0.0.1", 0), Imitador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    Imitador.pedidos = []
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


# ------------------------------------------------------------------ REAL
def test_chave_vai_para_o_cofre_e_nunca_volta_inteira(cli):
    r = cli.post("/api/ia/credencial", json={"provedor": "claude", "chave": CHAVE_FALSA})
    assert r.status_code == 200 and CHAVE_FALSA not in r.text
    est = cli.get("/api/ia").text
    assert CHAVE_FALSA not in est and "••••cdef" in est and "cofre do Windows" in est
    assert config.obter_chave("claude") == (CHAVE_FALSA, "cofre do Windows")   # gravado no cofre real
    assert not any(CHAVE_FALSA in open(f, encoding="utf-8").read()
                   for f in [config.ARQ] if __import__("os").path.isfile(f))       # nem no arquivo de config
    cli.delete("/api/ia/credencial/claude")
    assert config.obter_chave("claude") == (None, None)


def test_chave_invalida_rejeitada(cli):
    assert cli.post("/api/ia/credencial", json={"provedor": "claude", "chave": "curta"}).status_code == 400
    assert cli.post("/api/ia/credencial", json={"provedor": "xyz", "chave": CHAVE_FALSA}).status_code == 400


@pytest.mark.skipif(not tem_internet(), reason="sem internet")
@pytest.mark.parametrize("prov", ["claude", "openai", "gemini"])
def test_api_oficial_recusa_chave_falsa_com_erro_claro(prov):
    """Chamada REAL ao endpoint oficial (listar modelos, sem custo) com chave falsa."""
    p = criar(prov)
    p.chave = CHAVE_FALSA
    with pytest.raises(ErroIA) as e:
        p.listar_modelos()
    assert e.value.tipo == "credencial", str(e.value)
    assert CHAVE_FALSA not in str(e.value)


def test_sem_provedor_ou_sem_consentimento_nao_envia_e_edicao_continua(cli, projeto_base):
    p = projeto_base
    with pytest.raises(ErroIA, match="nenhum provedor"):
        assistente.executar(p, "titulos")
    cfg = config.carregar()
    cfg["provedor_ativo"] = "claude"
    config.salvar(cfg)
    with pytest.raises(ErroIA, match="confirme"):
        assistente.executar(p, "titulos")
    # a edicao manual nao depende da IA
    assert cli.put(f"/api/projetos/{p['nome']}", json={"gancho": {"texto": "manual", "ate": 2}}).status_code == 200


def test_limite_diario(projeto_base):
    cfg = config.carregar()
    cfg.update(provedor_ativo="ollama")
    cfg["provedores"]["ollama"].update(consentimento=True, modelo="x")
    cfg["limites"]["chamadas_por_dia"] = 1
    config.salvar(cfg)
    import datetime as dt
    uso.registrar({"data": dt.datetime.now().isoformat(), "provedor": "ollama", "ok": True})
    with pytest.raises(ErroIA, match="limite"):
        assistente.executar(projeto_base, "titulos")


def test_ollama_desligado_da_erro_claro():
    with pytest.raises(ErroIA) as e:
        criar("ollama", base_url="http://127.0.0.1:9").listar_modelos()
    assert e.value.tipo == "rede" and "Ollama" in str(e.value)


def test_previa_mostra_o_que_sera_enviado_sem_midia(cli, projeto_base):
    r = cli.post(f"/api/projetos/{projeto_base['nome']}/ia/previa/titulos", json={"extra": "foco no trailer"}).json()
    assert r["envia_midia"] is False and "Formato:" in r["prompt"] and "foco no trailer" in r["prompt"]


# ------------------------------------------------------------------ SIMULADO (servidor local imita a API)
@pytest.mark.parametrize("prov,modelo", [("claude", "claude-opus-5-5"), ("openai", "modelo-openai"),
                                         ("gemini", "modelo-gemini"), ("ollama", "modelo-local")])
def test_simulado_tarefa_completa_por_provedor(projeto_base, imitador, prov, modelo):
    if prov != "ollama":
        config.salvar_chave(prov, CHAVE_FALSA)
    cfg = config.carregar()
    cfg["provedor_ativo"] = prov
    cfg["provedores"][prov].update(modelo=modelo, consentimento=True)
    config.salvar(cfg)
    r = assistente.executar(projeto_base, "titulos", base_url=imitador)
    assert r["dados"]["titulos"][0]["texto"] == "O detalhe escondido de GTA 6"
    assert "sugestão da IA" in r["origem"]
    if prov == "claude":
        assert r["custo_usd"] == round((1000 * 4 + 200 * 20) / 1e6, 5)        # tabela oficial da Opus 5.5
        metodo, caminho, cab, corpo = [x for x in Imitador.pedidos if x[0] == "POST"][-1]
        assert corpo["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in cab.get("anthropic-beta", "")
        assert corpo["output_config"]["format"]["type"] == "json_schema"
    else:
        assert r["custo_usd"] is None                                         # sem tabela confiavel: nao inventa
    corpo = [x for x in Imitador.pedidos if x[0] == "POST"][-1][3]
    assert "video" not in json.dumps(corpo).lower() or "Tipo: vídeo" in json.dumps(corpo, ensure_ascii=False)
    # historico: so metadados por padrao, e nunca a chave
    regs = uso.registros()
    assert regs[-1]["ok"] and "enviado" not in regs[-1] and "resposta" not in regs[-1]
    assert CHAVE_FALSA not in open(uso.ARQ, encoding="utf-8").read()
    assert assistente.sugestoes(projeto_base["nome"])[0]["tarefa"] == "titulos"


def test_simulado_historico_com_conteudo_so_se_o_usuario_pedir(projeto_base, imitador):
    cfg = config.carregar()
    cfg.update(provedor_ativo="ollama")
    cfg["provedores"]["ollama"].update(modelo="m", consentimento=True)
    cfg["historico"]["guardar_conteudo"] = True
    config.salvar(cfg)
    assistente.executar(projeto_base, "titulos", base_url=imitador)
    assert "enviado" in uso.registros()[-1]


def test_simulado_testar_conexao_lista_modelos(cli, imitador, monkeypatch):
    cfg = config.carregar()
    cfg["ollama_url"] = imitador
    config.salvar(cfg)
    r = cli.post("/api/ia/testar", json={"provedor": "ollama"}).json()
    assert r == {"ok": True, "modelos": ["modelo-local"]}


def test_ollama_so_local(cli):
    assert cli.put("/api/ia/config", json={"ollama_url": "http://evil.example:11434"}).status_code == 400
