# 🧭 4. Planejador e operadores: de árvore em árvore

> **Arquivos:** [`tatu/planner.py`](../tatu/planner.py) · [`tatu/operators.py`](../tatu/operators.py) · [← Parser](03-parser.md) · [próximo: Expressões →](05-expressoes.md)

A AST diz **o que** você quer. O **plano** diz **como** buscar. O planejador transforma uma árvore na outra.

![Um plano é uma árvore de operadores](assets/plano.svg)

## 🔀 A ordem lógica do SQL

Escrevemos o `SELECT` numa ordem, mas o banco precisa executá-lo em outra:

```mermaid
flowchart LR
    F["① FROM<br/>+ JOIN"] --> W["② WHERE"] --> G["③ GROUP BY<br/>+ agregações"] --> H["④ HAVING"] --> O["⑤ ORDER BY"] --> S["⑥ SELECT<br/>(colunas)"] --> D["⑦ DISTINCT"] --> L["⑧ LIMIT<br/>OFFSET"]
    classDef a fill:#DCEBF5,stroke:#6FA8C7,color:#3B2412
    classDef b fill:#E5F2D6,stroke:#8DB872,color:#3B2412
    classDef c fill:#FDE7CF,stroke:#E0A96D,color:#3B2412
    classDef d fill:#ECE0F5,stroke:#A784C2,color:#3B2412
    class F a
    class W,H b
    class G c
    class O,S,D,L d
```

Isso explica várias "regras estranhas" do SQL:

- ❓ *Por que não posso usar `COUNT(*)` no `WHERE`?* Porque o `WHERE` (②) roda **antes** de agrupar (③). Para filtrar grupos existe o `HAVING` (④).
- ❓ *Por que posso ordenar por uma coluna que não está no `SELECT`?* Porque o `ORDER BY` (⑤) roda **antes** da projeção (⑥) — a coluna ainda existe.
- ❓ *Por que `ORDER BY total` funciona se `total` é um apelido?* O Tatu troca o apelido pela expressão do `SELECT` antes de planejar (veja `_resolve_order_item`). O mesmo vale para `ORDER BY 2`.

A função `plan_select` em [`planner.py`](../tatu/planner.py) é literalmente essa lista, de cima para baixo:

```python
node = SeqScan(...)                                   # ① FROM
node = NestedLoopJoin(node, SeqScan(...), ...)        # ① JOIN
node = Filter(node, where)                            # ② WHERE
node = HashAggregate(node, group_by, agregações)      # ③ GROUP BY
node = Filter(node, having)                           # ④ HAVING
node = Sort(node, order_by)                           # ⑤ ORDER BY
node = Project(node, itens_do_select)                 # ⑥ SELECT
node = Distinct(node)                                 # ⑦ DISTINCT
node = Limit(node, limit, offset)                     # ⑧ LIMIT
```

Cada operador **embrulha** o anterior. O último embrulho é a raiz da árvore.

## 🌋 O modelo Volcano: geradores puxando geradores

Cada operador tem um método `rows()` que é um **gerador Python**: ele entrega (`yield`) uma linha de cada
vez, e só calcula a próxima quando alguém pedir. É o **modelo Volcano** (ou de iteradores), usado por
PostgreSQL, SQLite, MySQL e muitos outros.

Veja como o `Filter` é curto:

```python
class Filter(Operator):
    def rows(self):
        for row in self.children[0].rows():        # pede uma linha ao filho...
            if truth(self.predicate(row)) is True:  # ...testa...
                yield row                           # ...e, se passar, entrega ao pai
```

Quando você pede linhas à raiz, o pedido **desce** pela árvore até os `SeqScan`, e as linhas **sobem**
uma a uma. Ninguém precisa guardar a tabela inteira na memória.

### 🦥 Preguiça é uma virtude

Como tudo é sob demanda, o `LIMIT` pode simplesmente **parar de pedir**:

```python
class Limit(Operator):
    def rows(self):
        yield from islice(self.children[0].rows(), self.offset, self.offset + self.limit)
```

`SELECT * FROM tatus LIMIT 1` lê **uma** linha e para — mesmo que a tabela tenha um milhão.

> [!WARNING]
> Alguns operadores **não conseguem** ser preguiçosos: o `Sort` precisa ver todas as linhas antes de
> saber qual é a primeira, e o `HashAggregate` precisa ver todas para fechar os grupos. Eles são
> chamados de operadores **bloqueantes**. `SELECT ... ORDER BY x LIMIT 1` ainda lê a tabela inteira.

## 🧰 A caixa de ferramentas

| Operador | Papel | Preguiçoso? |
|---|---|:-:|
| `SingleRow` | uma linha vazia, para `SELECT 1 + 1` sem `FROM` | ✅ |
| `SeqScan` | varre a tabela inteira, linha por linha | ✅ |
| `IndexScan` | vai direto às linhas com `coluna = valor`, usando um índice | ✅ |
| `Filter` | deixa passar só as linhas em que a condição é **verdadeira** | ✅ |
| `NestedLoopJoin` | para cada linha da esquerda, percorre a direita inteira | ✅ (esquerda) |
| `HashAggregate` | agrupa num dicionário e calcula `COUNT`, `SUM`… | ❌ |
| `Sort` | ordena | ❌ |
| `Project` | calcula as colunas do `SELECT` | ✅ |
| `Distinct` | descarta linhas repetidas (lembrando as que já viu) | ✅ |
| `Limit` | entrega no máximo *n* linhas | ✅ |

### 🔗 O JOIN mais simples do mundo

```python
for left_row in left.rows():
    for right_row in right_rows:                  # lado direito lido uma vez e guardado
        if condição(left_row + right_row):
            yield left_row + right_row
    # LEFT JOIN: se ninguém combinou, sai com NULLs à direita
```

São dois `for` encaixados: com 1.000 tatus e 1.000 espécies, são 1.000.000 de comparações.
Bancos reais têm alternativas — o **hash join** está nos [exercícios](09-exercicios.md). 🏋️

## ⚡ Índices: a primeira otimização

Se o `WHERE` tem uma condição do tipo `coluna = constante` e essa coluna tem índice, o planejador troca
o `SeqScan` por um `IndexScan`. A função é `_choose_index`:

1. quebra o `WHERE` nos `AND`s: `a AND b AND c` → `[a, b, c]` (`split_and`);
2. procura um item no formato `coluna = literal` (ou `literal = coluna`);
3. confere se a coluna é da **primeira tabela** do `FROM` e se ela tem índice;
4. se achou, usa o índice e **remove** essa condição da lista — o resto vira um `Filter` normal.

```text
tatu> EXPLAIN SELECT apelido FROM tatus WHERE idade > 3;
╭────────────────────────╮
│ plano                  │
├────────────────────────┤
│ Project(apelido)       │
│ └── Filter(idade > 3)  │
│     └── SeqScan(tatus) │      ← sem índice em idade: varre tudo
╰────────────────────────╯

tatu> CREATE INDEX idx_idade ON tatus (idade);
✔ Índice 'idx_idade' criado em tatus(idade)

tatu> EXPLAIN SELECT apelido FROM tatus WHERE idade = 3;
╭──────────────────────────────────────────────────╮
│ plano                                            │
├──────────────────────────────────────────────────┤
│ Project(apelido)                                 │
│ └── IndexScan(tatus usando idx_idade: idade = 3) │      ← direto ao ponto!
╰──────────────────────────────────────────────────╯
```

> [!NOTE]
> Repare que com `idade > 3` o índice **não ajuda**: um índice hash só sabe responder "quem tem
> exatamente este valor?". Para intervalos, bancos usam **B-trees** — outro [exercício](09-exercicios.md).

Chaves primárias e colunas `UNIQUE` ganham índice automaticamente (é ele que impede valores repetidos),
então `WHERE id = 3` sempre usa `IndexScan`.

## 🧪 Experimente

No shell, depois de `.demo`:

```sql
EXPLAIN SELECT * FROM tatus WHERE id = 3;
EXPLAIN SELECT * FROM tatus WHERE id = 3 OR id = 4;   -- OR não é quebrado: SeqScan
EXPLAIN SELECT t.apelido, e.nome
        FROM tatus t JOIN especies e ON t.especie_id = e.id
        WHERE t.especie_id = 2;                        -- índice na tabela da esquerda
EXPLAIN SELECT bioma, COUNT(*) FROM avistamentos GROUP BY bioma ORDER BY 2 DESC LIMIT 1;
```

## 🏋️ Para praticar

- 🐾🐾 **Empurrar filtros para baixo** (*predicate pushdown*): hoje, `WHERE e.ameacada` roda **depois**
  do JOIN. Se a condição só usa colunas de uma tabela, ela poderia filtrar essa tabela **antes**.
- 🐾🐾 Use o índice também para `coluna IN (1, 2, 3)`.
- 🐾🐾🐾 Implemente um **hash join** para condições `a.x = b.y`.

---

<p align="center"><a href="03-parser.md">← Parser</a> · <a href="05-expressoes.md"><b>próximo: 🧮 Expressões, NULL e agregações →</b></a></p>
