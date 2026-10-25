---
name: novo-comando-sql
description: Adiciona ao Tatu DB um comando ou cláusula SQL novo (ex. DROP INDEX, CASE WHEN, INSERT ... SELECT, SAVEPOINT, ON DELETE CASCADE) atravessando todas as etapas — tokenizer, AST, parser, planejador/executor, armazenamento com diário de desfazer — com testes e documentação. Use para qualquer mudança na gramática do SQL do Tatu.
---

# Adicionar um comando ou cláusula ao SQL

Um recurso novo segue a mesma jornada de uma consulta. Faça **uma etapa de cada vez**, rodando os
testes entre elas. Os exercícios em `docs/09-exercicios.md` têm dicas específicas para vários recursos.

## Etapas

### 1. 🔤 Tokenizer — `tatu/tokenizer.py`
Acrescente as palavras novas em `KEYWORDS`. ⚠️ Toda palavra-chave nova deixa de poder ser nome de
coluna/tabela: procure nos testes e na demo (`tatu/demo.py`) se alguma já é usada como nome.

### 2. 🌳 AST — `tatu/nodes.py`
Crie o nó como `@dataclass(frozen=True)` herdando de `Node`. Campos com listas são **tuplas**.
Se for expressão, implemente `__str__` devolvendo SQL (aparece no `EXPLAIN` e no nome da coluna).

### 3. 🌳 Parser — `tatu/parser.py`
- Comando novo: registre o método no dicionário `handlers` de `statement()`.
- Expressão nova: encaixe no degrau certo da escada de precedência (`primary()` para coisas como
  `CASE ... END`).
- Use `expect_kw`/`expect_sym` para o obrigatório e `accept_*` para o opcional; mensagens de erro
  vêm de `self.error("Esperava ...")`.

### 4. 🧭 Planejamento / 🏃 execução
- Consulta (SELECT): ajuste `plan_select` em `tatu/planner.py` e, se preciso, crie um operador em
  `tatu/operators.py` com `scope`, `rows()` (gerador) e `describe()`.
- Expressão: um `case` em `compile_expr` (`tatu/expressions.py`), respeitando a lógica de três valores.
- Comando: um `case` em `Executor.execute` (`tatu/executor.py`) que devolve `Result(message=...)`.

### 5. 💾 Armazenamento — `tatu/storage.py`
**Toda** mudança de estado registra como desfazê-la: `self.journal.record(lambda: ...)`.
Sem isso, `ROLLBACK` e a atomicidade por comando quebram silenciosamente.
Se o recurso precisa ser persistido (ex.: uma opção nova de coluna), atualize `schema.py`
(`_column_to_dict` / `_column_from_dict`) e confira que o arquivo antigo ainda abre.

### 6. 🧪 Testes
- `tests/test_parser.py`: a AST produzida e os erros de sintaxe.
- `tests/test_queries.py` / `test_constraints.py`: o comportamento.
- `tests/test_transactions.py`: o `ROLLBACK` desfaz o recurso novo.
- `tests/test_storage.py`: sobrevive a fechar e reabrir o arquivo (se persistir algo).

### 7. 📚 Documentação
- `docs/08-referencia-sql.md` — sintaxe e regras.
- O capítulo da etapa que mais mudou (ex.: operador novo → `docs/04-planejador.md`).
- `README.md` — tabela "O que ele sabe fazer", se for um recurso de destaque.
- `CHANGELOG.md` — `## [Não lançado]`.
- Se o recurso era um exercício de `docs/09-exercicios.md`, troque-o por outro desafio ou marque como
  "já implementado — leia o código em ...".
- Todas as saídas mostradas vêm de execuções reais.

### 8. ✅ Confira
```bash
python -m unittest discover -s tests
ruff check .
python scripts/check_docs.py
```
Depois peça uma revisão ao agente `revisor-tatu`.
