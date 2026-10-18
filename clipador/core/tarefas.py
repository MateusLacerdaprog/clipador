"""Tarefas demoradas (render, transcricao, cenas, download) em segundo plano, com progresso consultavel."""
import threading
import time
import traceback
import uuid

_tarefas = {}
_eventos = {}
_trava = threading.Lock()
GUARDAR_S = 3600
# ffmpeg/whisper ja usam todos os nucleos: uma tarefa pesada por vez evita travar o PC
_fila_pesada = threading.Semaphore(1)


def iniciar(tipo, funcao, *args, pesada=True, **kw):
    tid = uuid.uuid4().hex[:10]
    t = {"id": tid, "tipo": tipo, "estado": "na_fila", "progresso": 0.0, "mensagem": "",
         "resultado": None, "erro": None, "inicio": time.time()}
    with _trava:
        # tarefa terminada ha mais de GUARDAR_S sai da memoria (a interface ja leu o resultado)
        for velha in [k for k, v in _tarefas.items() if v.get("fim", time.time()) < time.time() - GUARDAR_S]:
            _tarefas.pop(velha, None)
            _eventos.pop(velha, None)
        _tarefas[tid] = t

    cancelar = threading.Event()

    def progresso(f, msg=None):
        t["progresso"] = round(float(f), 3)
        if msg:
            t["mensagem"] = msg

    progresso.cancelar = cancelar          # o render consulta isto para encerrar o FFmpeg
    _eventos[tid] = cancelar

    def rodar():
        sem = _fila_pesada if pesada else None
        try:
            if sem:
                sem.acquire()
            if cancelar.is_set():
                raise RuntimeError("tarefa cancelada")
            t["estado"] = "rodando"
            t["resultado"] = funcao(*args, progresso=progresso, **kw)
            t["progresso"] = 1.0
            t["estado"] = "ok"
        except Exception as e:  # noqa: BLE001 - erro vai para a interface
            t["estado"] = "cancelada" if cancelar.is_set() else "erro"
            t["erro"] = str(e) or e.__class__.__name__
            t["detalhe"] = traceback.format_exc()[-2000:]
        finally:
            if sem:
                sem.release()
            t["fim"] = time.time()

    threading.Thread(target=rodar, daemon=True).start()
    return t


def obter(tid):
    t = _tarefas.get(tid)
    if t and t["estado"] in ("rodando", "na_fila"):
        t["decorrido"] = round(time.time() - t["inicio"], 1)
        p = t["progresso"]
        if t["estado"] == "rodando" and 0.03 < p < 1:  # estimativa simples de tempo restante
            t["restante"] = round(t["decorrido"] * (1 - p) / p, 0)
    return t


def cancelar(tid):
    ev = _eventos.get(tid)
    if ev is None:
        return False
    ev.set()
    return True
