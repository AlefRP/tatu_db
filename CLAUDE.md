# CLAUDE.md — Tatu DB

Banco de dados relacional **educacional**, feito do zero em Python puro, com código comentado e
documentação em português do Brasil. O objetivo é ser **lido e entendido**, não ser rápido.

## Comandos

```bash
python -m unittest discover -s tests -v   # testes (rápidos: < 1 s)
ruff check .                              # lint (configurado no pyproject.toml)
python scripts/check_docs.py              # links, âncoras, SVGs e nº de testes citado nas docs
python -m tatu                            # shell interativo (.demo carrega dados de exemplo)
python -m tatu -c "EXPLAIN SELECT ..."    # roda um comando e sai
python packaging/build_binary.py          # executável com PyInstaller (precisa de pip install pyinstaller)
```

Rode os três primeiros antes de considerar qualquer tarefa pronta.

## Arquitetura (a jornada de uma consulta)

```text
texto → tokenizer.py → parser.py (+ nodes.py) → planner.py → operators.py → storage.py
        tokens         AST imutável             plano        linhas (Volcano)  heap, índices, diário
```

- `database.py` — entrada (`connect`, `execute`), transações, autocommit e atomicidade por comando.
- `executor.py` — CREATE/DROP/INSERT/UPDATE/DELETE e restrições; SELECT vira plano no `planner.py`.
- `expressions.py` — compila expressões em closures `f(linha)`; `Scope`/`Slot` resolvem nomes;
  lógica de três valores; funções (`SCALAR_FUNCTIONS`) e agregações (`AGGREGATES`).
- `operators.py` — cada operador tem `scope` e `rows()` (gerador) e `describe()` (usado pelo EXPLAIN).
- `storage.py` — `Table` (heap `rowid → lista`, índices hash), `Journal` (undo log), arquivo JSON atômico.
- `repl.py` — shell; `result.py` — `Result` e tabelas desenhadas; `demo.py` — dados de exemplo.

## Regras do projeto (importantes)

1. **Zero dependências** em `tatu/`. Só biblioteca padrão.
2. **Python 3.10+**: nada de sintaxe 3.11+ (ex.: `except*`, `typing.Self`, f-strings com aspas iguais aninhadas).
3. **Identificadores em inglês; comentários, docstrings, mensagens de erro e docs em pt-BR**, em tom didático.
   Mensagens de erro dizem o que aconteceu *e* como resolver.
4. **Clareza > desempenho.** Otimizações que complicam o código viram exercício em `docs/09-exercicios.md`.
5. **Toda mutação no armazenamento registra o desfazer** no `Journal` (`self.journal.record(lambda: ...)`),
   senão o ROLLBACK quebra. Inclua um teste de ROLLBACK para recursos que mudam dados.
6. **Nós da AST são `@dataclass(frozen=True)`** e implementam `__str__` devolvendo SQL (usado no EXPLAIN e nos
   nomes de coluna). A igualdade estrutural é usada pelo planejador (`Scope.find_expr`).
7. **Erros** sempre são subclasses de `TatuError` (`errors.py`); erros de sintaxe passam `sql` e `pos`.
8. Todo recurso novo: **teste** em `tests/` + **referência** em `docs/08-referencia-sql.md` +
   linha no `CHANGELOG.md` (seção "Não lançado"). Se mudar o nº de testes, o `check_docs.py` exige atualizar
   o número citado no README/docs.

## Documentação

- `docs/` é uma trilha de aprendizado em capítulos (`01-jornada.md` … `09-exercicios.md`), mais
  `instalacao.md` e `faq.md`. Títulos começam com emoji; capítulos terminam com navegação ← →.
- **Toda saída mostrada nas docs (tabelas, EXPLAIN, erros) deve vir de uma execução real.**
- Evite emojis com U+FE0F (🗣️, 🕳️, 🗺️…) em títulos que recebem links: o GitHub mantém o caractere na âncora.
- Ilustrações: SVG desenhado à mão em `docs/assets/`, com fundo próprio (funciona no tema escuro).
  Use a skill `ilustracao-svg`.

## Instaladores e CI

- `scripts/install.sh` (POSIX sh, Linux/macOS) e `scripts/install.ps1` (Windows PowerShell 5.1 e 7):
  modo Python (venv) ou binário (baixa `releases/latest/download/tatu-<so>-<arq>.*`).
  O `.ps1` fica **sem BOM** (o BOM quebra `irm | iex`) e **sem "—", "→", aspas curvas** (o 5.1 lê como
  ANSI e esses bytes viram aspas) — o `check_docs.py` confere. O `.iss` do Inno Setup fica **com BOM**.
- Nomes dos pacotes **sem versão** (`tatu-windows-x86_64-setup.exe`, `tatu-linux-arm64.deb`...), para os
  links `releases/latest/download/...` nunca quebrarem.
- Workflows: `ci.yml` (lint, docs, testes 3×5, instaladores) chama `pacotes.yml` (5 plataformas);
  `versao.yml` ("Nova versão", manual) sobe a versão via `scripts/bump_version.py`, cria a tag e chama
  `release.yml`, que publica (notas via `scripts/release_notes.py`) e testa o que publicou.
- A versão mora **só** em `tatu/__init__.py` (`__version__`). Para lançar, use a skill `lancar-versao`.

## Commits

Conventional Commits em português: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `ci:`, `build:`, `chore:`.

## Skills e agentes deste repositório

- Skills (`.claude/skills/`): `explicar-consulta`, `nova-funcao-sql`, `novo-comando-sql`, `ilustracao-svg`, `lancar-versao`.
- Agentes (`.claude/agents/`): `professor-tatu` (explica), `revisor-tatu` (revisa), `testador-tatu` (testes),
  `guardiao-docs` (documentação).
