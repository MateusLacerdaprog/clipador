"""Comandos do estúdio (canais, ideias com pontuação CPV, roteiros). Mesmas funções da API, direto no núcleo.

  python -m clipador canal semear|listar
  python -m clipador ideia nova --canal C --titulo "..." [--formato explicador] [--fonte URL ...] [--quadrado "..."]
  python -m clipador ideia avaliar ID [--nota gancho=4 ...] [--portao direitos_viaveis=sim ...]
  python -m clipador ideia aprovar|descartar ID   ·   python -m clipador ideia listar [--canal C]
  python -m clipador roteiro novo IDEIA · ver ID · bloco ID NOME "texto" · ganchos ID "g1" "g2" ...
  python -m clipador roteiro afirmacao ID "texto" URL · aprovar ID · projeto ID NOME

Aprovar (ideia/roteiro) é decisão do usuário: o Claude só roda esses comandos quando ele pedir.
"""
import argparse

from .core import canais, ideias, roteiros


def _pares(lista, conv):
    out = {}
    for item in lista or []:
        if "=" not in item:
            raise ValueError(f"use chave=valor: {item}")
        k, v = item.split("=", 1)
        out[k.strip()] = conv(v.strip())
    return out


def _bool(v):
    if v.lower() in ("sim", "s", "true", "1", "yes"):
        return True
    if v.lower() in ("nao", "não", "n", "false", "0", "no"):
        return False
    raise ValueError(f"use sim/não: {v}")


def _mostrar_roteiro(r):
    m = roteiros.metricas(r)
    linhas = [f"Roteiro {r['id']} ({r['formato']}, {r['status']}, versão {r['versao']}) — {r['titulo']}",
              f"  {m['palavras']} palavras ≈ {m['duracao_s']} s a {r['ppm']} pal/min; recompensa em {m['recompensa_em']}"]
    for k in roteiros.ORDEM:
        linhas.append(f"  [{k}] {r['blocos'].get(k) or '—'}   (guia: {r['guia'].get(k, '')})")
    linhas.append("  ganchos alternativos: " + (" | ".join(r["ganchos_alternativos"]) or "—"))
    linhas += [f"  fato: {a['texto']} → {a['fonte'] or 'SEM FONTE'}" for a in r["afirmacoes"]]
    for i in roteiros.checar(r):
        linhas.append(f"  {'✗' if i['nivel'] == 'erro' else '!' if i['nivel'] == 'aviso' else '·'} {i['titulo']} — {i['detalhe']}")
    return "\n".join(linhas)


def main(argv):
    ap = argparse.ArgumentParser(prog="python -m clipador", description="Estúdio: canais, ideias CPV e roteiros")
    sub = ap.add_subparsers(dest="grupo", required=True)
    c = sub.add_parser("canal")
    c.add_argument("acao", choices=("semear", "listar"))
    i = sub.add_parser("ideia")
    i.add_argument("acao", choices=("nova", "avaliar", "aprovar", "descartar", "listar", "fonte"))
    i.add_argument("id", nargs="?")
    i.add_argument("--canal")
    i.add_argument("--titulo")
    i.add_argument("--formato", default="explicador")
    i.add_argument("--quadrado", default="")
    i.add_argument("--justificativa", default="")
    i.add_argument("--fonte", action="append", default=[])
    i.add_argument("--nota", action="append", default=[])
    i.add_argument("--portao", action="append", default=[])
    r_ = sub.add_parser("roteiro")
    r_.add_argument("acao", choices=("novo", "ver", "bloco", "ganchos", "afirmacao", "aprovar", "projeto"))
    r_.add_argument("args", nargs="*")
    a = ap.parse_args(argv)
    try:
        if a.grupo == "canal":
            if a.acao == "semear":
                print("criados:", ", ".join(x["id"] for x in canais.semear()) or "nenhum (já existiam)")
            for x in canais.listar():
                print(f"{x['id']}: {x['nome']} · {x['nicho']} · {x['status']} · monetização {x['monetizacao']}")
        elif a.grupo == "ideia":
            if a.acao == "nova":
                x = ideias.criar({"canal": a.canal, "titulo": a.titulo, "formato": a.formato, "quadrado": a.quadrado,
                                  "justificativa": a.justificativa, "fontes": [{"url": u} for u in a.fonte]})
                print(f"ideia criada: {x['id']}")
            elif a.acao == "avaliar":
                x = ideias.avaliar(a.id, _pares(a.nota, float), _pares(a.portao, _bool))
                print(f"{x['id']}: nota {x['nota']} ({ideias.pontuar(x)[1]})")
            elif a.acao in ("aprovar", "descartar"):
                x = ideias.mudar_status(a.id, "aprovada" if a.acao == "aprovar" else "descartada")
                print(f"{x['id']}: {x['status']}")
            elif a.acao == "fonte":
                for u in a.fonte:
                    ideias.adicionar_fonte(a.id, {"url": u})
                print("fonte(s) registrada(s)")
            else:
                for x in ideias.listar(a.canal):
                    print(f"{x['id']} · {x['canal']} · {x['status']} · nota {x['nota']} · {x['titulo']}")
        else:
            arg = a.args
            if a.acao == "novo":
                print(_mostrar_roteiro(roteiros.criar(arg[0])))
            elif a.acao == "ver":
                print(_mostrar_roteiro(roteiros.obter(arg[0])))
            elif a.acao == "bloco":
                print(_mostrar_roteiro(roteiros.editar(arg[0], blocos={arg[1]: arg[2]})))
            elif a.acao == "ganchos":
                print(_mostrar_roteiro(roteiros.editar(arg[0], ganchos_alternativos=arg[1:])))
            elif a.acao == "afirmacao":
                r = roteiros.obter(arg[0])
                print(_mostrar_roteiro(roteiros.editar(arg[0], afirmacoes=r["afirmacoes"] + [{"texto": arg[1], "fonte": arg[2]}])))
            elif a.acao == "aprovar":
                print(_mostrar_roteiro(roteiros.aprovar(arg[0])))
            else:
                p = roteiros.para_projeto(arg[0], arg[1])
                print(f"projeto criado: {p['nome']} (roteiro no teleprompter da aba 5)")
    except (ValueError, FileNotFoundError, FileExistsError, IndexError) as e:
        print(f"Erro: {e}")
        return 1
    return 0
