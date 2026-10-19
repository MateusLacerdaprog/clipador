"""Comandos do editonny no Clipador (core/editonny.py; ver docs/EDITONNY.md).

  python -m clipador editonny status
  python -m clipador editonny cenas [busca ...]            (catálogo: quando usar, textos que você precisa dar)
  python -m clipador editonny grafico NOME CENA --inicio S [--duracao S] [--param chave=valor ...]
                                                   [--texto "exemplo=seu texto" ...] [--estilo night|paper|amber]
  python -m clipador editonny remover NOME INDICE
  python -m clipador editonny apertar NOME [--aplicar] [--pausa-max 0.15] [--pausa-min 0.25]
  python -m clipador editonny desfazer-aperto NOME

Os textos das cenas são do usuário: o Claude não inventa título, número ou preço (memória e CLAUDE.md).
"""
import argparse
import json

from .core import editonny


def _pares(lista):
    out = {}
    for item in lista or []:
        if "=" not in item:
            raise ValueError(f"use chave=valor: {item}")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _numeros(params, c):
    """--param x=300 chega como texto: vira numero quando o padrao da cena e numero."""
    ajustes = {k: i for k, i in (c.get("parameters") or {}).items() if isinstance((i or {}).get("default"), (int, float))}
    return {k: (float(v) if k in ajustes else v) for k, v in params.items()}


def _mostrar_cena(c):
    linhas = [f"{c['id']} · {c['categoria']} · {c['duracao']} s · {c['layout']}"
              + (" · cobre a tela" if c["esconde_legenda"] else ""), f"   quando: {c['quando']}"]
    for t in c["textos"]:
        linhas.append(f"   texto {'--param' if t['tipo'] == 'parametro' else '--texto'} {t['chave']}  (exemplo: “{t['exemplo']}”)")
    return "\n".join(linhas)


def main(argv):
    ap = argparse.ArgumentParser(prog="python -m clipador editonny", description="Cenas e limpeza de narração do editonny")
    sub = ap.add_subparsers(dest="acao", required=True)
    sub.add_parser("status")
    c_ = sub.add_parser("cenas")
    c_.add_argument("busca", nargs="*")
    g_ = sub.add_parser("grafico")
    g_.add_argument("projeto")
    g_.add_argument("cena")
    g_.add_argument("--inicio", type=float, required=True)
    g_.add_argument("--duracao", type=float)
    g_.add_argument("--param", action="append", default=[])
    g_.add_argument("--texto", action="append", default=[])
    g_.add_argument("--estilo", default="night", choices=editonny.ESTILOS)
    r_ = sub.add_parser("remover")
    r_.add_argument("projeto")
    r_.add_argument("indice", type=int)
    a_ = sub.add_parser("apertar")
    a_.add_argument("projeto")
    a_.add_argument("--aplicar", action="store_true")
    a_.add_argument("--pausa-max", type=float, default=0.15)
    a_.add_argument("--pausa-min", type=float, default=0.25)
    d_ = sub.add_parser("desfazer-aperto")
    d_.add_argument("projeto")
    a = ap.parse_args(argv)
    try:
        if a.acao == "status":
            print(json.dumps(editonny.status(), ensure_ascii=False, indent=1))
        elif a.acao == "cenas":
            cenas = editonny.catalogo(" ".join(a.busca))
            print("\n".join(_mostrar_cena(c) for c in cenas) + f"\n{len(cenas)} cena(s).")
        elif a.acao == "grafico":
            c = editonny.cena(a.cena)
            item = editonny.gerar_grafico(a.projeto, a.cena, a.inicio, a.duracao, _numeros(_pares(a.param), c),
                                          _pares(a.texto), a.estilo,
                                          progresso=lambda f, m=None: m and print(f"  {m}"))
            print(f"Gráfico {item['nome']} em {item['inicio']:.2f}–{item['inicio'] + item['duracao']:.2f} s: {item['arquivo']}")
        elif a.acao == "remover":
            editonny.remover_grafico(a.projeto, a.indice)
            print("Gráfico removido.")
        elif a.acao == "apertar":
            r = editonny.apertar_narracao(a.projeto, a.aplicar, a.pausa_max, a.pausa_min,
                                          progresso=lambda f, m=None: m and print(f"  {m}"))
            print("\n".join(r["relatorio"]))
            print(f"{len(r['cortes'])} pausa(s), {r['removido']:.2f} s a menos (narração de {r['antes']:.2f} s).")
            print(f"Narração nova: {r['arquivo']} ({r['depois']:.2f} s). Desfazer: python -m clipador editonny "
                  f"desfazer-aperto {a.projeto}" if a.aplicar else "Só o plano: nada mudou. Use --aplicar para gravar.")
            print("Aviso: " + r["aviso"])
        elif a.acao == "desfazer-aperto":
            print(f"Narração de volta: {editonny.desfazer_aperto(a.projeto)['narracao']}")
    except (ValueError, IndexError, editonny.ErroEditonny) as e:
        print(f"Erro: {e}")
        return 1
    return 0
