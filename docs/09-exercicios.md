# 🏋️ 9. Exercícios: hora de cavar

> [← Referência](08-referencia-sql.md) · [índice](README.md)

Ler um banco de dados ensina muito. **Mudar** um ensina ainda mais. Os exercícios abaixo vão do
aquecimento ao "agora eu entendo o PostgreSQL". Cada um diz por onde começar.

| Dificuldade | Significa |
|:-:|---|
| 🐾 | uma tarde: um arquivo, poucas linhas |
| 🐾🐾 | um fim de semana: mexe em duas ou três etapas |
| 🐾🐾🐾 | um projeto: muda uma peça inteira do banco |

> [!TIP]
> Antes de mudar qualquer coisa, rode `python -m unittest discover -s tests`. Depois de mudar,
> **escreva um teste novo** para o seu recurso e rode tudo de novo. Os 126 testes existentes são sua rede de segurança.

---

## 🐾 Aquecimento

### 1. `DROP INDEX`

Hoje dá para criar índices, mas não apagar.
- **Parser:** em `drop()`, aceite `INDEX nome` além de `TABLE`. Crie o nó `DropIndex` em `nodes.py`.
- **Executor:** encontre o índice (`storage.find_index`), recuse apagar índices automáticos (`index.automatic`)
  e lembre do **diário**: `journal.record(...)` para o `ROLLBACK` devolver o índice.

### 2. Novas funções: `SUBSTR`, `REPLACE` e `INITCAP`

- **Onde:** o dicionário `SCALAR_FUNCTIONS` em `expressions.py`. Cada entrada é `(mínimo, máximo, função)`.
- Atenção: no SQL, `SUBSTR('tatu', 1, 2)` é `'ta'` — a contagem começa em **1**, não em 0!

### 3. Comentários de bloco e números com expoente

- `/* comentário */` e `1.5e3` no `tokenizer.py`. Não esqueça a mensagem para `/*` sem fechamento.

### 4. Prompt de transação

- No `repl.py`, mostre `tatu*>` quando `db.in_transaction` for verdadeiro. Pequeno, mas muito útil!

### 5. Agregação `GROUP_CONCAT(x)`

- Junta os textos de um grupo com vírgula: `SELECT especie_id, GROUP_CONCAT(apelido) FROM tatus GROUP BY especie_id`.
- **Onde:** o dicionário `AGGREGATES`. A função recebe a lista de valores do grupo.

---

## 🐾🐾 Intermediário

### 6. `CASE WHEN`

```sql
SELECT apelido, CASE WHEN idade >= 5 THEN 'veterano' ELSE 'jovem' END AS fase FROM tatus;
```

- Adicione `CASE`, `WHEN`, `THEN`, `ELSE`, `END` em `KEYWORDS`.
- Novo nó `Case(whens: tuple[(cond, valor)], default)`; leia-o em `primary()`.
- Em `compile_expr`, avalie as condições em ordem: a primeira **verdadeira** ganha (`NULL` não conta!).

### 7. Empurrar filtros para baixo (*predicate pushdown*)

```sql
EXPLAIN SELECT * FROM tatus t JOIN especies e ON t.especie_id = e.id WHERE e.ameacada;
```

Hoje o `Filter(e.ameacada)` fica **acima** do JOIN: o banco junta tudo e só depois joga fora.
- Em `plan_select`, para cada condição do `WHERE`, descubra quais tabelas ela usa.
- Se usar só uma tabela, aplique o `Filter` **direto em cima do scan dela**.
- ⚠️ Cuidado com o `LEFT JOIN`: filtrar o lado **direito** antes da junção muda o resultado! Por quê?

### 8. Índice também para `IN`

`WHERE id IN (1, 5, 9)` poderia fazer três buscas no índice em vez de varrer tudo.
- Generalize `IndexScan` para receber uma **lista** de valores e estenda `_choose_index`.

### 9. `INSERT INTO ... SELECT`

```sql
INSERT INTO ameacados (apelido) SELECT t.apelido FROM tatus t JOIN especies e ON ... WHERE e.ameacada;
```

- Em `insert()` do parser, aceite `SELECT` no lugar de `VALUES`.
- No executor, rode o plano do `SELECT` e insira cada linha (as validações já existem!).

### 10. `ON DELETE CASCADE`

- Guarde a ação no `Column.references` (e no arquivo `.tatu`).
- Em `_check_not_referenced`, em vez de reclamar, apague as linhas filhas — que podem ter suas próprias filhas…

### 11. `SAVEPOINT`

```sql
BEGIN; INSERT ...; SAVEPOINT antes_do_perigo; DELETE ...; ROLLBACK TO antes_do_perigo; COMMIT;
```

- Um savepoint é só um nome para um `journal.mark()`. O `ROLLBACK TO` chama `journal.rollback_to(marca)`.

---

## 🐾🐾🐾 Avançado

### 12. Hash join

Para `ON a.x = b.y`, em vez de dois `for` encaixados (*n × m* comparações):
1. leia o lado direito montando um dicionário `valor de b.y → [linhas]`;
2. para cada linha da esquerda, busque `a.x` no dicionário.

Fica *n + m*. Crie o operador `HashJoin`, faça o planejador escolhê-lo quando o `ON` for uma igualdade
entre colunas das duas tabelas, e compare os tempos com uma tabela de 10.000 linhas.

### 13. Índice B-tree (ou, para começar, um índice ordenado)

Um índice hash não ajuda em `idade > 3`. Um índice **ordenado** ajuda:
- versão 1: mantenha uma lista ordenada de `(valor, rowid)` com o módulo `bisect`;
- versão 2: implemente uma B-tree de verdade, com nós que se dividem;
- crie um `IndexRangeScan` para `<`, `<=`, `>`, `>=` e `BETWEEN` — e use-o também para evitar o `Sort` no `ORDER BY`!

### 14. Páginas em disco

Troque o JSON por um arquivo binário dividido em **páginas de 4 KB**:
- codifique cada linha em bytes (`struct` ajuda muito);
- um *buffer pool* guarda na memória só algumas páginas e escreve de volta as alteradas;
- o `SeqScan` passa a ler página por página.

É assim que o SQLite e o PostgreSQL guardam os dados.

### 15. WAL — *write-ahead log*

Hoje cada `COMMIT` regrava o arquivo inteiro. Com um WAL:
1. cada mudança confirmada é **acrescentada** ao fim de um arquivo de log (rápido!);
2. de tempos em tempos, um *checkpoint* aplica o log no arquivo principal e o zera;
3. ao abrir o banco, se existir log, ele é **reaplicado** — é a recuperação após uma queda.

Teste matando o processo no meio de um script (`os._exit`) e confira que nada confirmado se perdeu.

### 16. Vários usuários

Hoje dois processos no mesmo arquivo se atropelam. Comece com um **arquivo de trava** (`.lock`);
depois, se quiser ir longe, estude **MVCC** (cada linha com versões) e implemente o isolamento *snapshot*.

---

<p align="center">
  <img src="assets/tatu.svg" alt="O tatu, mascote do Tatu DB" width="160"><br>
  <b>Terminou algum? Parabéns — você acabou de mexer nas entranhas de um banco de dados. 🎉</b><br>
  <a href="README.md">← voltar ao índice</a>
</p>
