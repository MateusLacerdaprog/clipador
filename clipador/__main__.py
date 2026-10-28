"""python -m clipador  -> abre o Clipador no navegador (http://127.0.0.1:8765).
python -m clipador montar|finalizar ...  -> montagem automatica ate o RASCUNHO (clipador/automacao.py).
python -m clipador editonny ...  -> cenas animadas e narracao sem pausas do editonny (clipador/cli_editonny.py)."""
import argparse
import sys
import threading
import webbrowser

import uvicorn


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("montar", "finalizar", "referencia", "reels"):
        from . import automacao
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")     # console do Windows: aspas e acentos
        sys.exit(automacao.main(sys.argv[1:]))
    if len(sys.argv) > 1 and sys.argv[1] in ("canal", "ideia", "roteiro", "esteira", "metricas", "experimento", "custo"):
        from . import cli_estudio
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.exit(cli_estudio.main(sys.argv[1:]))
    if len(sys.argv) > 1 and sys.argv[1] == "editonny":
        from . import cli_editonny
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.exit(cli_editonny.main(sys.argv[2:]))
    ap = argparse.ArgumentParser(description="Clipador - Shorts de games")
    ap.add_argument("--porta", type=int, default=8765)
    ap.add_argument("--sem-navegador", action="store_true")
    a = ap.parse_args()
    url = f"http://127.0.0.1:{a.porta}"
    if not a.sem_navegador:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"Clipador rodando em {url}  (feche esta janela para encerrar)")
    uvicorn.run("clipador.web.app:app", host="127.0.0.1", port=a.porta, log_level="warning")


if __name__ == "__main__":
    main()
