"""Fila de aprovacao de todos os projetos (aba Aprovacao): rascunhos esperando o usuario e FINAIS aprovados.
Aprovar e sempre um clique do usuario; o FINAL so sai do rascunho atual aprovado (hash em projeto.aprovacao)."""
import os

from . import projeto


def item(p):
    """Estado de aprovacao de um projeto, ou None se ainda nao tem rascunho nem FINAL."""
    d = projeto.pasta(p["nome"])
    h = projeto.hash_conteudo(p)
    ap = p["aprovacao"]
    rasc, fin = f"RASCUNHO_{p['nome']}.mp4", f"FINAL_{p['nome']}.mp4"
    tem_r, tem_f = os.path.isfile(os.path.join(d, rasc)), os.path.isfile(os.path.join(d, fin))
    if ap.get("aprovado_hash") == h and (tem_f or tem_r):
        estado = "aprovado" if tem_f else "aprovado_sem_final"
    elif tem_r and ap.get("rascunho_hash") == h:
        estado = "aguardando"
    elif tem_r or tem_f:
        estado = "desatualizado"                 # o projeto mudou depois do ultimo video: gerar de novo
    else:
        return None
    alvo = os.path.join(d, fin if estado == "aprovado" else rasc if tem_r else fin)
    return {"nome": p["nome"], "tipo": p.get("tipo", "curto"), "editor": p.get("editor") or "clipador",
            "estado": estado, "rascunho": rasc if tem_r else None, "final": fin if tem_f else None,
            "publicacao": os.path.isfile(os.path.join(d, "PUBLICACAO.md")), "nota": p.get("revisao_nota") or "",
            "atualizado": int(os.path.getmtime(alvo))}


ORDEM = {"aguardando": 0, "aprovado_sem_final": 1, "desatualizado": 2, "aprovado": 3}


def fila():
    out = []
    for nome in projeto.listar():
        try:
            i = item(projeto.carregar(nome))
        except (OSError, ValueError, KeyError):
            continue
        if i:
            out.append(i)
    return sorted(out, key=lambda i: (ORDEM[i["estado"]], -i["atualizado"]))


def pedir_ajuste(nome, nota):
    """Recado do usuario para a proxima versao (o Claude le em projeto.revisao_nota). Vazio apaga."""
    nota = str(nota or "").strip()[:2000]
    return projeto.alterar(nome, lambda p: p.update(revisao_nota=nota))
