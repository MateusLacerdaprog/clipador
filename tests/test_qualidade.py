"""Qualidade estatica do codigo (rapido, sem midia): erros bobos que so apareciam em uso.

- todo .py compila; nenhum arquivo com BOM (quebrava a leitura de ferramentas e do proprio app);
- nenhum import sobrando e nenhum `import *` no pacote (imports explicitos: da para saber de onde vem cada nome);
- nenhuma funcao definida duas vezes no mesmo modulo Python, nem em dois arquivos JS (scripts classicos dividem o
  escopo global: a segunda definicao apagaria a primeira sem aviso);
- toda rota em web/rotas/ esta registrada no app.
"""
import ast
import os
import re
import symtable
from collections import Counter

from conftest import ESTATICO, scripts_da_interface

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACOTE = os.path.join(RAIZ, "clipador")


def _arquivos(pasta, extensoes):
    for base, dirs, nomes in os.walk(pasta):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "modelos")]
        for n in nomes:
            if n.endswith(extensoes):
                yield os.path.join(base, n)


PY = sorted(list(_arquivos(PACOTE, (".py",))) + list(_arquivos(os.path.join(RAIZ, "tests"), (".py",))))


def test_todo_python_compila_e_nada_tem_bom():
    com_bom = []
    for c in PY + sorted(_arquivos(ESTATICO, (".js", ".css", ".html"))):
        with open(c, "rb") as f:
            dados = f.read()
        if dados.startswith(b"\xef\xbb\xbf"):
            com_bom.append(os.path.relpath(c, RAIZ))
        if c.endswith(".py"):
            compile(dados.decode("utf-8"), c, "exec")
    assert not com_bom, f"arquivos com BOM (salve como UTF-8 sem BOM): {com_bom}"


def _globais_usados(src, nome):
    usados = set()

    def visita(t):
        for s in t.get_symbols():
            if s.is_referenced() and (t.get_type() == "module" or s.is_global()):
                usados.add(s.get_name())
        for filho in t.get_children():
            visita(filho)
    visita(symtable.symtable(src, nome, "exec"))
    return usados


def test_sem_import_sobrando_nem_import_estrela_no_pacote():
    problemas = []
    for c in PY:
        if not c.startswith(PACOTE) or c.endswith("__init__.py"):     # __init__ pode reexportar nomes
            continue
        with open(c, encoding="utf-8") as f:
            src = f.read()
        usados = _globais_usados(src, c)
        for n in ast.parse(src).body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    if a.name == "*":
                        problemas.append(f"{os.path.relpath(c, RAIZ)}: import *")
                    elif (a.asname or a.name).split(".")[0] not in usados:
                        problemas.append(f"{os.path.relpath(c, RAIZ)}:{n.lineno} {a.asname or a.name}")
    assert not problemas, "imports sobrando: " + ", ".join(problemas)


def test_todo_import_relativo_resolve_inclusive_dentro_de_funcao():
    """Import dentro de funcao so quebra quando a funcao roda (foi assim na divisao do app.py em rotas/)."""
    import importlib.util

    quebrados = []
    for c in PY:
        if not c.startswith(PACOTE):
            continue
        pacote = os.path.relpath(c, RAIZ)[:-3].replace(os.sep, ".").rsplit(".", 1)[0]
        with open(c, encoding="utf-8") as f:
            arvore = ast.parse(f.read())
        for n in ast.walk(arvore):
            if isinstance(n, ast.ImportFrom) and n.level:
                alvo = importlib.util.resolve_name("." * n.level + (n.module or ""), pacote)
                try:
                    ok = importlib.util.find_spec(alvo) is not None    # "from . import x": x pode ser atributo
                except ModuleNotFoundError:
                    ok = False
                if not ok:
                    quebrados.append(f"{os.path.relpath(c, RAIZ)}:{n.lineno} -> {alvo}")
    assert not quebrados, quebrados


def test_nenhuma_funcao_python_definida_duas_vezes_no_mesmo_modulo():
    repetidas = []
    for c in PY:
        with open(c, encoding="utf-8") as f:
            corpo = ast.parse(f.read()).body
        nomes = Counter(n.name for n in corpo if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
        repetidas += [f"{os.path.relpath(c, RAIZ)}: {n}" for n, q in nomes.items() if q > 1]
    assert not repetidas, repetidas


def test_nenhuma_funcao_js_definida_em_dois_lugares():
    onde = {}
    repetidas = []
    for c in scripts_da_interface():
        with open(c, encoding="utf-8") as f:
            for nome in re.findall(r"^(?:async )?function\*? ?([A-Za-z_$][\w$]*)\s*\(", f.read(), re.M):
                if nome in onde:
                    repetidas.append(f"{nome} ({onde[nome]} e {os.path.basename(c)})")
                onde.setdefault(nome, os.path.basename(c))
    assert not repetidas, repetidas


def test_todo_modulo_de_rotas_esta_registrado_no_app():
    from clipador.web.app import app

    def planas(rotas):                          # FastAPI 0.14x agrupa cada include_router num objeto so
        for r in rotas:
            sub = getattr(r, "original_router", None)
            yield from (planas(sub.routes) if sub is not None else (r,))

    no_app = {(getattr(r, "name", ""), getattr(r, "path", "")) for r in planas(app.routes)}
    pasta = os.path.join(PACOTE, "web", "rotas")
    for arq in sorted(n for n in os.listdir(pasta) if n.endswith(".py") and n != "__init__.py"):
        with open(os.path.join(pasta, arq), encoding="utf-8") as f:
            src = f.read()
        assert "@app." not in src, f"rotas/{arq} usa @app (use @router)"
        rotas = re.findall(r'^@router\.\w+\("([^"]+)"[^\n]*\)\n(?:async )?def (\w+)', src, re.M)
        assert rotas, f"rotas/{arq} nao tem rotas"
        fora = [f"{funcao} {caminho}" for caminho, funcao in rotas if (funcao, caminho) not in no_app]
        assert not fora, f"rotas/{arq}: fora do app: {fora}"
    assert ("inicio", "/") in no_app
