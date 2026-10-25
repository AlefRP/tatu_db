---
name: nova-funcao-sql
description: Adiciona ao Tatu DB uma função escalar (como SUBSTR, REPLACE, INITCAP) ou uma agregação (como GROUP_CONCAT), com tratamento de NULL e de tipos, testes, documentação e changelog. Use quando pedirem uma "função nova", "suporte a X()" ou uma agregação nova no SQL do Tatu.
---

# Adicionar uma função ou agregação SQL

Funções moram em `tatu/expressions.py`. Não é preciso mexer no tokenizer nem no parser: qualquer
`NOME(args)` já vira um nó `Call` com o nome em maiúsculas.

## 1. Escalar ou agregação?

| Tipo | Recebe | Exemplo | Onde |
|---|---|---|---|
| escalar | os valores de **uma linha** | `UPPER(apelido)` | dicionário `SCALAR_FUNCTIONS` |
| agregação | a **lista** de valores de um grupo (já sem `NULL`) | `SUM(idade)` | dicionário `AGGREGATES` |

## 2a. Função escalar

Cada entrada de `SCALAR_FUNCTIONS` é `NOME: (mínimo_de_args, máximo_de_args_ou_None, função)`.
O número de argumentos é conferido na compilação — não repita essa checagem.

Regras:
- **NULL entra, NULL sai** (a não ser que a função exista justamente para lidar com NULL, como
  `COALESCE`): embrulhe com `_null_in_null_out`.
- **Confira os tipos** e lance `TatuTypeError` com mensagem em português: use `_text_fn(...)` para
  funções de texto e `_require_numbers(...)` para números.
- Siga a convenção do SQL, não a do Python (ex.: `SUBSTR` conta a partir de **1**).

```python
def _substr(text, start, length=None):
    if not isinstance(text, str):
        raise TatuTypeError(f"SUBSTR() espera TEXT, mas recebeu {type_of(text)}")
    _require_numbers("SUBSTR", start, *([] if length is None else [length]))
    begin = max(int(start) - 1, 0)          # o SQL conta a partir de 1
    return text[begin:] if length is None else text[begin:begin + int(length)]

SCALAR_FUNCTIONS = {
    ...
    "SUBSTR": (2, 3, _null_in_null_out(_substr)),
}
```

## 2b. Agregação

A função recebe a lista de valores **sem NULLs** (o `HashAggregate` já filtra) e devolve um valor.
Lista vazia → `NULL` (`None`), exceto contagens. `DISTINCT` já é tratado antes de chamar a função.
Se precisar de números, use `_require_aggregate_numbers`.

```python
def _group_concat(values):
    return ", ".join(v if isinstance(v, str) else sql_literal(v) for v in values) if values else None

AGGREGATES = {..., "GROUP_CONCAT": _group_concat}
```

Agregações aceitam exatamente 1 argumento (conferido em `planner.collect_aggregates`).

## 3. Testes (`tests/test_queries.py`)

Escreva pelo menos: o caso feliz, o caso com `NULL`, o erro de tipo e (agregação) a tabela vazia e o
`GROUP BY`. Siga o estilo de `test_funcoes` e `test_agregacoes_sem_group_by`.

## 4. Documentação

- `docs/08-referencia-sql.md` → tabela **🛠️ Funções** (ou a linha das agregações).
- `README.md` → linha **Funções:** na seção "O SQL que o tatu entende".
- `CHANGELOG.md` → uma linha em `## [Não lançado]` (`### Adicionado`).
- Copie exemplos de saída de uma execução real: `python -m tatu -c "SELECT SUBSTR('tatu-bola', 6)"`.

## 5. Confira tudo

```bash
python -m unittest discover -s tests
ruff check .
python scripts/check_docs.py      # atualize o nº de testes citado no README e nas docs, se mudou
```
