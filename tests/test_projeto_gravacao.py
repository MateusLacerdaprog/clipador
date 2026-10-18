"""Gravacao do projeto: aguenta o OneDrive/antivirus segurando o arquivo e nao perde edicoes com tarefas em paralelo."""
import os
import threading

import pytest

from clipador.core import projeto


def test_salvar_tenta_de_novo_quando_o_arquivo_esta_preso(projeto_base, monkeypatch):
    real, falhas = os.replace, {"n": 0}

    def preso(a, b):
        if b.endswith("projeto.json") and falhas["n"] < 3:     # como o OneDrive: 3 recusas seguidas
            falhas["n"] += 1
            raise PermissionError(5, "Acesso negado")
        return real(a, b)

    monkeypatch.setattr(os, "replace", preso)
    p = projeto.carregar(projeto_base["nome"])
    p["roteiro"] = "gravou mesmo com o arquivo preso"
    projeto.salvar(p)
    assert falhas["n"] == 3 and projeto.carregar(p["nome"])["roteiro"] == "gravou mesmo com o arquivo preso"
    assert not [f for f in os.listdir(projeto.pasta(p["nome"])) if f.endswith(".tmp")]     # nao sobra temporario


def test_salvar_desiste_com_erro_claro_se_o_arquivo_continua_preso(projeto_base, monkeypatch):
    monkeypatch.setattr(os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError(5, "Acesso negado")))
    with pytest.raises(PermissionError):
        projeto.salvar(projeto.carregar(projeto_base["nome"]))
    monkeypatch.undo()
    assert not [f for f in os.listdir(projeto.pasta(projeto_base["nome"])) if f.endswith(".tmp")]


def test_alterar_em_paralelo_nao_perde_nenhuma_edicao(projeto_base):
    n = projeto_base["nome"]
    projeto.alterar(n, lambda p: p.update(roteiro=""))

    def soma(letra):
        for _ in range(25):
            projeto.alterar(n, lambda p: p.update(roteiro=p["roteiro"] + letra))

    ths = [threading.Thread(target=soma, args=(c,)) for c in "ab"]
    [t.start() for t in ths]
    [t.join() for t in ths]
    r = projeto.carregar(n)["roteiro"]
    assert r.count("a") == 25 and r.count("b") == 25                # 50 alteracoes, nenhuma perdida


def test_salvar_pela_tela_nao_apaga_a_marca_gravada_por_uma_tarefa(projeto_base, monkeypatch):
    """A rota que salva o projeto le, muda e grava sob a trava: uma tarefa que grava no meio (marca do render) espera."""
    from fastapi.testclient import TestClient

    from clipador.web.app import app
    from clipador.web.rotas import projetos as rp
    n, cli = projeto_base["nome"], TestClient(app, base_url="http://127.0.0.1:8765")
    leu, real = threading.Event(), rp._carregar

    def carregar_devagar(nome):
        p = real(nome)
        leu.set()
        threading.Event().wait(0.3)               # a tarefa tenta gravar enquanto a rota esta no meio
        return p

    monkeypatch.setattr(rp, "_carregar", carregar_devagar)
    tarefa = threading.Thread(target=lambda: (leu.wait(5), projeto.alterar(n, lambda p: p.update(proxy_hash="marca"))))
    tarefa.start()
    assert cli.put(f"/api/projetos/{n}", json={"roteiro": "editado"}).status_code == 200
    tarefa.join()
    p = projeto.carregar(n)
    assert p["proxy_hash"] == "marca" and p["roteiro"] == "editado"


def test_tarefas_terminadas_ha_muito_tempo_saem_da_memoria(monkeypatch):
    import time

    from clipador.core import tarefas
    velha = tarefas.iniciar("x", lambda progresso: 1, pesada=False)
    for _ in range(100):
        if velha["estado"] == "ok":
            break
        time.sleep(0.02)
    velha["fim"] -= tarefas.GUARDAR_S + 1
    nova = tarefas.iniciar("x", lambda progresso: 1, pesada=False)
    assert tarefas.obter(velha["id"]) is None and tarefas.obter(nova["id"]) is not None
