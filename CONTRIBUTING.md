# 🤝 Contribuindo com o Tatu DB

Que bom que você quer cavar junto! 🐾 Este guia explica como o projeto funciona por dentro — não do
banco (isso é a [trilha de aprendizado](docs/README.md)), mas do **repositório**: ambiente, estilo,
testes, documentação, pacotes e versões.

## 🧭 Os princípios do projeto

Antes de qualquer linha de código, vale combinar o que o Tatu **é**:

1. **Clareza acima de desempenho.** Se uma otimização deixa o código difícil de ler, ela vira um
   [exercício](docs/09-exercicios.md), não uma mudança.
2. **Zero dependências.** O pacote `tatu` só usa a biblioteca padrão do Python. Ferramentas de
   desenvolvimento (ruff, PyInstaller) são bem-vindas — no pacote, não.
3. **Python 3.10+.** Nada de sintaxe mais nova (o CI testa do 3.10 ao 3.14).
4. **Código em inglês, explicação em português.** Nomes de classes, funções e variáveis em inglês
   (como em qualquer banco de dados); comentários, docstrings, mensagens de erro e documentação em
   português do Brasil, num tom de quem está ensinando.
5. **Toda mudança no banco é desfazível.** Se você mexe no armazenamento, registra o "como desfazer"
   no diário (`journal.record(...)`). Veja o [capítulo 7](docs/07-transacoes.md).
6. **Toda funcionalidade tem teste e documentação.**

## 🛠️ Preparando o ambiente

```bash
git clone https://github.com/AlefRP/tatu_db.git
cd tatu_db
python -m tatu                               # já funciona!

python -m pip install ruff                   # o linter (opcional, mas o CI usa)
python -m unittest discover -s tests -v      # os testes
ruff check .                                 # o estilo
python scripts/check_docs.py                 # a documentação
```

Não precisa de ambiente virtual para rodar ou testar — o projeto não tem dependências. Se quiser o
comando `tatu` apontando para a sua cópia: `python -m pip install -e .`.

## 🔁 O fluxo de uma contribuição

1. Abra (ou comente) uma [issue](https://github.com/AlefRP/tatu_db/issues) contando o que pretende fazer.
2. Crie um branch: `git switch -c feat/drop-index`.
3. Faça a mudança **com testes** e **com documentação**.
4. Rode os três comandos da seção anterior.
5. Faça commits pequenos, no estilo [Conventional Commits](https://www.conventionalcommits.org/pt-br/), em português:

   | Prefixo | Quando | Exemplo |
   |---|---|---|
   | `feat:` | recurso novo | `feat: adiciona DROP INDEX` |
   | `fix:` | correção | `fix: NOT IN com NULL devolvia FALSE` |
   | `docs:` | só documentação | `docs: explica o hash join no capítulo 4` |
   | `test:` | só testes | `test: casos de canto do BETWEEN` |
   | `refactor:` | muda o código sem mudar o comportamento | `refactor: separa o Sort em duas funções` |
   | `ci:` / `build:` | workflows / empacotamento | `ci: testa no Python 3.15` |

6. Abra o pull request — o [modelo](.github/PULL_REQUEST_TEMPLATE.md) tem um checklist.

## ➕ Adicionando um recurso ao SQL: o checklist

Um recurso novo costuma atravessar o banco inteiro. Siga a jornada da consulta:

| Etapa | Arquivo | O que fazer |
|---|---|---|
| 🔤 palavras novas | `tatu/tokenizer.py` | acrescentar em `KEYWORDS` |
| 🌳 árvore | `tatu/nodes.py` | criar o nó (`@dataclass(frozen=True)`) com `__str__` que devolve SQL |
| 🌳 gramática | `tatu/parser.py` | um método por regra; erros com `self.error(...)` |
| 🧭 plano | `tatu/planner.py` / `tatu/operators.py` | se for consulta: operador novo ou ajuste no plano |
| 🧮 expressões | `tatu/expressions.py` | se for expressão/função: um `case` em `compile_expr` |
| 🏃 execução | `tatu/executor.py` | se for comando: um `case` em `execute` |
| 💾 armazenamento | `tatu/storage.py` | toda mudança registra o desfazer no diário |
| 🧪 testes | `tests/` | caso feliz, `NULL`, erro de tipo, `ROLLBACK` |
| 📖 referência | `docs/08-referencia-sql.md` | a sintaxe nova |
| ✨ README | `README.md` | a tabela "O que ele sabe fazer", se for algo grande |
| 📝 histórico | `CHANGELOG.md` | uma linha em "Não lançado" |

> [!TIP]
> Usa o Claude Code? As skills `/novo-comando-sql` e `/nova-funcao-sql` seguem exatamente esse checklist.

## 📚 Escrevendo documentação

- **Português do Brasil**, frases curtas, tom de conversa. Explique o *porquê*, não só o *como*.
- Títulos com um **emoji** no começo (`## 🔎 Índices`); evite emojis com o seletor invisível U+FE0F
  (como 🗣️ e 🕳️) em títulos que recebem links — eles mudam a âncora.
- Todo exemplo de saída (tabelas, `EXPLAIN`, mensagens de erro) deve ser **copiado de uma execução real**.
- Capítulos terminam com a navegação `← anterior · próximo →`.
- Diagramas de fluxo em **Mermaid**; ilustrações em **SVG** desenhado à mão, na paleta do projeto:

  | Cor | Uso |
  |---|---|
  | `#4A2A12` `#5A3519` | textos e contornos (marrom-escuro) |
  | `#B8783F` `#E8B57A` | casco do tatu |
  | `#FFF8EE` `#FFF4DE` | fundos claros (sempre com fundo próprio: funciona no tema escuro) |
  | `#DCEBF5`/`#6FA8C7` · `#E5F2D6`/`#8DB872` · `#FDE7CF`/`#E0A96D` · `#ECE0F5`/`#A784C2` | caixas: leitura, filtro, agrupamento, acabamento |

- Antes de enviar: `python scripts/check_docs.py` (links, âncoras, SVGs e o número de testes citado).

## 📦 Pacotes e instaladores

Tudo é gerado pelo CI ([`pacotes.yml`](.github/workflows/pacotes.yml)), mas dá para gerar localmente:

```bash
python -m pip install pyinstaller build
python -m build                          # wheel + sdist em dist/
python packaging/build_binary.py         # executável + .zip/.tar.gz em dist/release/
sh packaging/linux/build_deb.sh          # Linux: .deb
sh packaging/macos/build_pkg.sh          # macOS: .pkg
iscc /DAppVersion=0.1.0 packaging\windows\tatu.iss   # Windows: setup.exe (precisa do Inno Setup 6)
```

| Arquivo | O que é |
|---|---|
| [`scripts/install.sh`](scripts/install.sh) | instalador de uma linha para Linux e macOS (`curl … \| sh`) |
| [`scripts/install.ps1`](scripts/install.ps1) | instalador de uma linha para Windows (`irm … \| iex`) — salvo **sem BOM** de propósito |
| [`packaging/build_binary.py`](packaging/build_binary.py) | executável com PyInstaller + teste de fumaça |
| [`packaging/windows/tatu.iss`](packaging/windows/tatu.iss) | instalador do Windows (Inno Setup) — salvo **com BOM**, para os acentos |
| [`packaging/linux/build_deb.sh`](packaging/linux/build_deb.sh) | pacote Debian/Ubuntu |
| [`packaging/macos/build_pkg.sh`](packaging/macos/build_pkg.sh) | pacote do macOS |
| [`packaging/icons/`](packaging/icons/) | ícone (SVG de origem, PNG e ICO) |

## 🚀 Lançando uma versão

1. Atualize `__version__` em [`tatu/__init__.py`](tatu/__init__.py) — é a **única** fonte da versão
   (o `pyproject.toml` lê dali).
2. Em [`CHANGELOG.md`](CHANGELOG.md), troque `## [Não lançado]` por `## [X.Y.Z] - AAAA-MM-DD` e abra uma
   seção nova de "Não lançado" acima.
3. Commit (`chore: versão X.Y.Z`), tag e push:

   ```bash
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```

4. O workflow [`release.yml`](.github/workflows/release.yml) confere se a tag bate com a versão, gera todos
   os pacotes, testa cada instalador e cria o **GitHub Release** com as notas do CHANGELOG.
5. *(Opcional)* Para publicar também no PyPI: configure o *trusted publishing* do projeto no PyPI
   (ambiente `pypi`) e crie a variável de repositório `PUBLICAR_NO_PYPI = true`.

## 🤖 Claude Code no projeto

O repositório vem configurado para o [Claude Code](https://claude.com/claude-code):

| Caminho | O que é |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | as regras do projeto (o Claude lê no começo de cada sessão) |
| [`.claude/settings.json`](.claude/settings.json) | permissões para os comandos do dia a dia e o *hook* de testes |
| [`.claude/hooks/testes_rapidos.py`](.claude/hooks/testes_rapidos.py) | roda os testes sempre que o Claude edita um `.py` do banco |
| [`.claude/skills/`](.claude/skills/) | receitas: `/explicar-consulta`, `/nova-funcao-sql`, `/novo-comando-sql`, `/ilustracao-svg`, `/lancar-versao` |
| [`.claude/agents/`](.claude/agents/) | ajudantes: `professor-tatu`, `revisor-tatu`, `testador-tatu`, `guardiao-docs` |
| [`.github/workflows/claude.yml`](.github/workflows/claude.yml) | responde a menções `@claude` em issues e PRs |

Para ativar o `@claude` no GitHub, rode `/install-github-app` dentro do Claude Code (ele configura tudo),
ou crie à mão o segredo **`ANTHROPIC_API_KEY`** em *Settings → Secrets and variables → Actions*.

---

Dúvidas? Abra uma [issue](https://github.com/AlefRP/tatu_db/issues/new/choose). Obrigado por ajudar o tatu a cavar mais fundo! 🐾
