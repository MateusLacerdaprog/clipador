"""Montagem automatica pelo proprio Clipador: o pedido vem pela conversa (ou pelo terminal) e o video sai ate o
RASCUNHO. Usa a mesma API da tela, dentro do processo (mesmas validacoes, mesmas tarefas), sem abrir servidor.

  python -m clipador montar NOME --fonte VIDEO_OU_LINK [--formato curiosidades] [--tipo curto] [--layout empilhado]
                           [--trechos 14-20,31.5-36 | --pedido "o que e dito no video" | (padrao) melhor momento]
                           [--duracao 20] [--kit ID]
  python -m clipador finalizar NOME [--narracao voz.wav] [--modelo small]

montar: projeto + fonte + cortes (+ foco automatico na tela cheia) + previa (base para gravar a narracao) + RASCUNHO.
finalizar: (narracao gravada na aba 5 ou enviada aqui) -> legendas da narracao -> RASCUNHO novo.
Nenhum texto e escrito pelo agente (titulo, legenda manual) e o FINAL nunca sai daqui: so depois da aprovacao no app.
"""
import argparse
import os
import time

from fastapi.testclient import TestClient


class ErroAutomacao(RuntimeError):
    pass


class Clipador:
    def __init__(self, log=print):
        from .web.app import app
        self.cli = TestClient(app, base_url="http://127.0.0.1:8765")   # Host local: passa na protecao do app
        self.log = log

    def _req(self, metodo, url, **kw):
        r = self.cli.request(metodo, url, **kw)
        if r.status_code >= 400:
            try:
                det = r.json().get("detail")
            except ValueError:
                det = r.text
            raise ErroAutomacao(f"{metodo} {url}: {det}")
        return r.json()

    def _esperar(self, tarefa, rotulo):
        """Acompanha uma tarefa em segundo plano (mostra as mensagens novas) e devolve o resultado."""
        ultima = None
        while True:
            t = self._req("GET", f"/api/tarefas/{tarefa['id']}")
            if t.get("mensagem") and t["mensagem"] != ultima:
                ultima = t["mensagem"]
                self.log(f"  {rotulo}: {ultima}")
            if t["estado"] == "ok":
                return t["resultado"]
            if t["estado"] in ("erro", "cancelada"):
                raise ErroAutomacao(f"{rotulo}: {t.get('erro') or t['estado']}")
            time.sleep(0.5)

    def _rascunho(self, nome):
        b = f"/api/projetos/{nome}"
        self.log("Gerando o RASCUNHO…")
        arq = self._esperar(self._req("POST", f"{b}/render/rascunho"), "rascunho")["arquivo"]
        itens = [i for i in self._req("GET", f"{b}/verificar")["itens"] if i["nivel"] in ("erro", "aviso")]
        return {"projeto": nome, "rascunho": os.path.join(_pasta(nome), arq), "problemas": itens}

    def montar(self, nome, fonte, formato=None, tipo="curto", layout=None, trechos=None, pedido=None,
               duracao=None, kit=None, referencia=None):
        perfil = None
        if referencia:                      # erro de nome antes de criar qualquer coisa
            perfil = self._req("GET", f"/api/referencias/{referencia}")
        e = self._req("POST", "/api/projetos", json={"nome": nome, "tipo": tipo, "formato": formato, "kit": kit})
        nome = e["nome"]
        b = f"/api/projetos/{nome}"
        if perfil:
            self._req("POST", f"{b}/referencia/{perfil['id']}/aplicar")
            self.log(f"Seguindo a referência “{perfil['nome']}”.")
        duracao = duracao or ((perfil or {}).get("derivado", {}).get(tipo, {}).get("duracao_alvo")) or 20.0
        self.log(f"Projeto “{nome}” criado. Importando o vídeo…")
        if fonte.startswith(("http://", "https://")):
            t = self._req("POST", f"{b}/fontes/url", json={"url": fonte})
        else:
            if not os.path.isfile(fonte):
                raise ErroAutomacao(f"vídeo não encontrado: {fonte}")
            t = self._req("POST", f"{b}/fontes/caminho", json={"caminho": os.path.abspath(fonte)})
        fid = self._esperar(t, "vídeo")["fonte"]
        if layout:
            self._req("PUT", b, json={"layout": layout})
        if trechos:
            self.log(f"Montando {len(trechos)} trecho(s) pedido(s)…")
            self._req("PUT", b, json={"segmentos": [{"fonte": fid, "ini": a, "fim": z} for a, z in trechos]})
        else:
            if pedido:
                self.log("Transcrevendo a fala do vídeo para achar o trecho pedido…")
                self._esperar(self._req("POST", f"{b}/fontes/{fid}/transcrever"), "transcrição")
                r = self._req("POST", f"{b}/fontes/{fid}/pedido", json={"texto": pedido, "duracao": duracao, "quantidade": 1})
                if not r.get("encontrados"):
                    raise ErroAutomacao(f"não achei “{pedido}” na fala do vídeo; tente outras palavras ou --trechos")
            else:
                self.log("Procurando o melhor momento do vídeo…")
                self._esperar(self._req("POST", f"{b}/fontes/{fid}/destaques", json={"duracao": duracao, "quantidade": 1}),
                              "momentos")
            self._req("POST", f"{b}/fontes/{fid}/destaques/aplicar", json={"indice": 0})
        e = self._req("GET", b)
        if e["layout"] == "tela_cheia":                      # recorte 9:16: segue a acao em cada trecho
            self._req("POST", f"{b}/foco_auto", json={})
        self.log("Gerando a prévia (base para gravar a narração)…")
        self._esperar(self._req("POST", f"{b}/proxy"), "prévia")
        return self._rascunho(nome)

    def finalizar(self, nome, narracao=None, modelo="small"):
        b = f"/api/projetos/{nome}"
        self._req("GET", b)
        if narracao:
            if not os.path.isfile(narracao):
                raise ErroAutomacao(f"arquivo de narração não encontrado: {narracao}")
            with open(narracao, "rb") as f:
                self._req("POST", f"{b}/narracao", files={"arquivo": (os.path.basename(narracao), f)})
        if not self._req("GET", b).get("narracao"):
            raise ErroAutomacao("o projeto ainda não tem narração: grave na aba 5 · Narração do Clipador "
                                "(ou passe --narracao arquivo.wav)")
        self.log("Transcrevendo a narração (legendas)…")
        self._esperar(self._req("POST", f"{b}/legendas/transcrever", json={"modelo": modelo, "origem": "narracao"}),
                      "legendas")
        return self._rascunho(nome)


def referencia(nome, com_fala=True, log=print):
    """Mede os videos de referencias/videos/<nome>/ e grava o perfil (aparece em Referencias no app)."""
    from .core import referencias
    os.makedirs(referencias.pasta_videos(nome), exist_ok=True)
    try:
        perfil = referencias.analisar_videos(nome, lambda f, m=None: m and log(f"  {m}"), com_fala=com_fala)
    except RuntimeError as e:
        raise ErroAutomacao(str(e))
    referencias.salvar(perfil)
    return perfil


def resumo_referencia(perfil):
    o = perfil["observado"]
    linhas = [f"\nPerfil “{perfil['nome']}” (id {perfil['id']}) a partir de {len(perfil['fonte']['videos'])} vídeo(s):"]
    for v in o["por_video"]:
        f = v["fala"]
        linhas.append(f"  {v['arquivo']}: {v['dur']} s, {'vertical' if v['vertical'] else 'horizontal'}, "
                      f"plano médio {v['plano_medio_s']} s ({v['cortes_por_min']} cortes/min)"
                      + (f", {f['ppm']} palavras/min, 1ª fala em {f['primeira_fala_s']} s" if f else ", sem fala medida"))
    linhas.append(f"Use: python -m clipador montar NOME --fonte VIDEO --referencia {perfil['id']}")
    return "\n".join(linhas)


def _pasta(nome):
    from .core import projeto
    return projeto.pasta(nome)


def _trechos(txt):
    """'14-20,31.5-36' -> [(14.0, 20.0), (31.5, 36.0)]"""
    out = []
    for parte in (txt or "").split(","):
        try:
            a, z = (float(x) for x in parte.strip().split("-"))
        except ValueError:
            raise argparse.ArgumentTypeError(f"trecho inválido: “{parte.strip()}” (use início-fim em segundos, ex.: 14-20)")
        if z <= a:
            raise argparse.ArgumentTypeError(f"trecho inválido: “{parte.strip()}” (o fim precisa ser depois do início)")
        out.append((a, z))
    return out


def relatorio(r):
    linhas = [f"\nRASCUNHO pronto para revisão: {r['rascunho']}"]
    if r["problemas"]:
        linhas.append("Conferir antes de aprovar:")
        linhas += [f"  {'✗' if i['nivel'] == 'erro' else '!'} {i['titulo']}"
                   + (f" — {i['como_resolver']}" if i.get("como_resolver") else "") for i in r["problemas"]]
    linhas.append(f"Ajustes e aprovação: abra o projeto “{r['projeto']}” no Clipador. O FINAL só depois de aprovar.")
    return "\n".join(linhas)


def main(argv):
    ap = argparse.ArgumentParser(prog="python -m clipador", description="Montagem automática até o RASCUNHO")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("montar", help="cria o projeto e monta até o RASCUNHO (sem narração)")
    m.add_argument("nome")
    m.add_argument("--fonte", required=True, help="caminho do vídeo ou link")
    m.add_argument("--formato", default=None, help="guias, noticias, gameplay, curiosidades, compilados, comparacao")
    m.add_argument("--tipo", default="curto", choices=("curto", "longo"))
    m.add_argument("--layout", default=None, help="empilhado, tela_cheia… (padrão: o do formato)")
    m.add_argument("--kit", default=None, help="kit do canal (estilo salvo)")
    m.add_argument("--duracao", type=float, default=None,
                   help="duração do momento procurado, em segundos (padrão: a da referência, ou 20)")
    m.add_argument("--referencia", default=None, help="perfil de referência (python -m clipador referencia NOME)")
    g = m.add_mutually_exclusive_group()
    g.add_argument("--trechos", type=_trechos, help="início-fim em segundos, separados por vírgula: 14-20,31.5-36")
    g.add_argument("--pedido", help="trecho pelo que é dito no vídeo (busca local na transcrição)")
    f = sub.add_parser("finalizar", help="legendas da narração + RASCUNHO novo")
    f.add_argument("nome")
    f.add_argument("--narracao", default=None, help="arquivo de voz (se não gravou na aba 5)")
    f.add_argument("--modelo", default="small", help="modelo do Whisper (tiny, base, small, medium)")
    r_ = sub.add_parser("referencia", help="mede os vídeos de referencias/videos/NOME e cria o perfil")
    r_.add_argument("nome")
    r_.add_argument("--sem-fala", action="store_true", help="não transcreve (mais rápido; sem ritmo de fala)")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "referencia":
            print(resumo_referencia(referencia(a.nome, com_fala=not a.sem_fala)))
            return 0
        c = Clipador()
        if a.cmd == "montar":
            r = c.montar(a.nome, a.fonte, a.formato, a.tipo, a.layout, a.trechos, a.pedido, a.duracao, a.kit,
                         a.referencia)
        else:
            r = c.finalizar(a.nome, a.narracao, a.modelo)
    except ErroAutomacao as e:
        print(f"Erro: {e}")
        return 1
    print(relatorio(r))
    return 0
