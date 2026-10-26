# 📖 8. Referência do SQL

> [← Transações](07-transacoes.md) · [próximo: Exercícios →](09-exercicios.md)

Tudo o que o Tatu DB entende, num lugar só. Palavras-chave e nomes **não** diferenciam maiúsculas
(`select`, `SELECT` e `SeLeCt` são iguais; `Tatus` e `tatus` também). Comandos terminam com `;`.

Identificadores entre aspas duplas permitem espaços e palavras reservadas, como
`"minha tabela"`. Uma aspa no nome é escapada dobrando-a: `"tatu""bola"`.

## 🧱 Tipos

| Tipo | Apelidos aceitos | Valores | Exemplo |
|---|---|---|---|
| `INTEGER` | `INT`, `BIGINT`, `SMALLINT` | inteiros | `42`, `-7` |
| `REAL` | `FLOAT`, `DOUBLE`, `NUMERIC`, `DECIMAL` | números com casas decimais | `3.14`, `.5` |
| `TEXT` | `VARCHAR(n)`, `CHAR(n)`, `STRING` | textos (o `n` é aceito e ignorado) | `'tatu-bola'`, `'pé-d''água'` |
| `BOOLEAN` | `BOOL` | `TRUE`, `FALSE` | `TRUE` |

`NULL` cabe em qualquer tipo (a menos que a coluna seja `NOT NULL`). Conversões automáticas só
acontecem sem perda: um `INTEGER` numa coluna `REAL` vira `3.0`; um `3.0` numa coluna `INTEGER` vira `3`.

## 🏗️ Definição de dados

```sql
CREATE TABLE [IF NOT EXISTS] nome (
    coluna TIPO [PRIMARY KEY] [NOT NULL] [UNIQUE] [DEFAULT valor] [REFERENCES outra(coluna)],
    ...
);
```

| Restrição | Significa |
|---|---|
| `PRIMARY KEY` | identifica a linha: única e nunca `NULL`. Uma por tabela. Se for `INTEGER` e vier sem valor, ganha o próximo número |
| `NOT NULL` | não aceita `NULL` |
| `UNIQUE` | não aceita valores repetidos (mas aceita vários `NULL`) |
| `DEFAULT valor` | valor usado quando a coluna fica fora do `INSERT` |
| `REFERENCES t(c)` | chave estrangeira: o valor precisa existir em `t.c` (que deve ser `PRIMARY KEY` ou `UNIQUE`). Impede apagar a linha "pai" enquanto alguém aponta para ela |

```sql
CREATE [UNIQUE] INDEX nome ON tabela (coluna);   -- índice hash: acelera "coluna = valor"
DROP TABLE [IF EXISTS] nome;                     -- falha se outra tabela tem REFERENCES para ela
```

## ✍️ Manipulação de dados

```sql
INSERT INTO tabela [(col1, col2, ...)] VALUES (v1, v2, ...), (v1, v2, ...);
UPDATE tabela SET col = expr [, col = expr ...] [WHERE condição];
DELETE FROM tabela [WHERE condição];
```

- No `UPDATE`, todas as expressões usam os valores **antigos** da linha: `SET a = b, b = a` troca os dois.
- Sem `WHERE`, `UPDATE` e `DELETE` afetam **todas** as linhas. Cuidado! 🙈
- Cada comando é atômico: se uma linha falhar, nenhuma é alterada.

## 🔎 Consultas

```sql
SELECT [DISTINCT] * | tabela.* | expr [[AS] apelido], ...
[FROM tabela [[AS] apelido]
    [ [INNER] JOIN tabela [[AS] apelido] ON condição
    | LEFT [OUTER] JOIN tabela [[AS] apelido] ON condição
    | CROSS JOIN tabela [[AS] apelido]
    | , tabela [[AS] apelido] ] ...]
[WHERE condição]
[GROUP BY expr, ...]
[HAVING condição]
[ORDER BY expr | apelido | posição [ASC | DESC], ...]
[LIMIT n [OFFSET m]];

EXPLAIN SELECT ...;     -- mostra o plano em vez de executar
```

- `ORDER BY` aceita um apelido do `SELECT` (`ORDER BY total`) ou uma posição (`ORDER BY 2`).
- `NULL` vem **primeiro** no `ASC` e por último no `DESC` (como no SQLite).
- `SELECT` sem `FROM` funciona: `SELECT 2 + 2;`.
- A mesma tabela duas vezes precisa de apelidos: `FROM tatus a JOIN tatus b ON ...`.

## 🧮 Expressões

| Categoria | Operadores | Observações |
|---|---|---|
| aritmética | `+` `-` `*` `/` `%` | inteiro ÷ inteiro dá inteiro (truncado em direção ao zero); divisão por zero é erro |
| texto | `\|\|` | concatena: `'tatu' \|\| '-' \|\| 'bola'` |
| comparação | `=` `!=` `<>` `<` `<=` `>` `>=` | só entre valores da mesma família (números, textos ou booleanos) |
| lógica | `AND` `OR` `NOT` | lógica de três valores (veja o [capítulo 5](05-expressoes.md)) |
| nulos | `IS NULL`, `IS NOT NULL` | o único jeito certo de testar `NULL` |
| conjunto | `x [NOT] IN (a, b, ...)` | |
| intervalo | `x [NOT] BETWEEN a AND b` | inclui as pontas |
| padrão | `x [NOT] LIKE 'padrão'` | `%` = qualquer sequência, `_` = um caractere; diferencia maiúsculas |
| parâmetro | `?` | valor passado em `execute(sql, params)` |

**Precedência** (da mais fraca para a mais forte): `OR` → `AND` → `NOT` → comparações → `+ - ||` → `* / %` → `-` unário. Use parênteses na dúvida.

## 🛠️ Funções

| Função | Exemplo | Resultado |
|---|---|---|
| `UPPER(t)` / `LOWER(t)` | `UPPER('bola')` | `'BOLA'` |
| `LENGTH(t)` | `LENGTH('toca')` | `4` |
| `TRIM(t)` | `TRIM('  oi ')` | `'oi'` |
| `ABS(n)` | `ABS(-3)` | `3` |
| `ROUND(n [, casas])` | `ROUND(2.567, 1)` | `2.6` |
| `COALESCE(a, b, ...)` | `COALESCE(NULL, 'x')` | o primeiro não nulo: `'x'` |
| `TYPEOF(x)` | `TYPEOF(3.5)` | `'REAL'` |

**Agregações** (ignoram `NULL`): `COUNT(*)`, `COUNT(x)`, `SUM(x)`, `AVG(x)`, `MIN(x)`, `MAX(x)` —
todas aceitam `DISTINCT`: `COUNT(DISTINCT bioma)`. Só podem aparecer no `SELECT`, no `HAVING` e no `ORDER BY`.

## 🔁 Transações

```sql
BEGIN [TRANSACTION];
COMMIT;
ROLLBACK;
```

Fora de uma transação, cada comando é gravado sozinho (*autocommit*).

## 🖥️ Comandos do shell

| Comando | O que faz |
|---|---|
| `.help` | ajuda |
| `.tables` | lista as tabelas com quantidade de colunas e linhas |
| `.schema [tabela]` | mostra o `CREATE TABLE` e os `CREATE INDEX` |
| `.demo` | carrega `especies`, `tatus` e `avistamentos` |
| `.read arquivo.sql` | executa um arquivo |
| `.quit` / `.exit` | sai |

```bash
python -m tatu [arquivo.tatu] [-c "SQL"]     # sem arquivo: banco em memória
python -m tatu arquivo.tatu < script.sql      # executa um script (com comandos de ponto, inclusive)
```

## 🦔 Cliente gráfico Toca

O Toca executa o mesmo SQL desta referência e usa o mesmo formato de arquivo `.tatu`.
Abra com `python -m tatu.toca [arquivo.tatu]`, `python -m tatu --gui [arquivo.tatu]` ou,
depois da instalação Python, `toca [arquivo.tatu]`.

**Ctrl+Enter** e **F5** executam a seleção do editor, ou o texto inteiro quando não há seleção.
Os controles de transação correspondem a `BEGIN`, `COMMIT` e `ROLLBACK`.
Para atalhos, arquivos SQL e exportação CSV, veja o [guia do cliente](toca.md).

## 🐍 API Python

```python
import tatu

db = tatu.connect("zoo.tatu")      # ou tatu.connect() / tatu.connect(":memory:")
r = db.execute(sql, params=())     # um comando → Result
rs = db.executescript(sql)         # vários comandos → [Result, ...]
db.tables()                        # ['especies', 'tatus', ...]
db.schema("tatus")                 # 'CREATE TABLE tatus (...);'
db.in_transaction                  # há um BEGIN aberto?
db.close()                         # ou: with tatu.connect(...) as db: ...
```

| `Result` | |
|---|---|
| `r.columns` | nomes das colunas |
| `r.rows` / `for linha in r` / `r[0]` / `len(r)` | as linhas (tuplas) |
| `r.scalar()` | o primeiro valor da primeira linha |
| `r.as_dicts()` | lista de dicionários |
| `r.message` / `r.rowcount` | para comandos que não são `SELECT`: `"3 linha(s) inserida(s)"`, `3` |
| `print(r)` | desenha a tabela |

## 🚨 Erros

Todos herdam de `tatu.TatuError`:

| Exceção | Quando | Exemplo |
|---|---|---|
| `TatuSyntaxError` | o SQL não pôde ser lido | `SELEC 1` |
| `CatalogError` | tabela, coluna, índice ou função inexistente/duplicada; coluna ambígua | `SELECT x FROM nada` |
| `ConstraintError` | violou `PRIMARY KEY`, `UNIQUE`, `NOT NULL` ou `REFERENCES` | id repetido |
| `TatuTypeError` | tipo errado | `SELECT 'a' + 1` |
| `ExecutionError` | erro ao executar | `SELECT 1 / 0` |
| `TransactionError` | `BEGIN`/`COMMIT`/`ROLLBACK` fora de hora | `COMMIT` sem `BEGIN` |

---

<p align="center"><a href="07-transacoes.md">← Transações</a> · <a href="09-exercicios.md"><b>próximo: 🏋️ Exercícios →</b></a></p>
