# 🧮 5. Expressões, NULL e agregações

> **Arquivo:** [`tatu/expressions.py`](../tatu/expressions.py) · [← Planejador](04-planejador.md) · [próximo: Armazenamento →](06-armazenamento.md)

Os operadores do capítulo anterior precisam calcular coisas: `idade > 3`, `UPPER(apelido)`,
`peso_kg * 1000`. Este capítulo mostra como o Tatu avalia expressões — e como lida com o
famoso (e confuso) `NULL`.

## 🏭 Compilar antes, executar depois

Um jeito ingênuo de avaliar `idade > 3` seria, **para cada linha**, procurar a coluna "idade" pelo nome.
Com um milhão de linhas, seria um milhão de buscas pelo mesmo nome.

O Tatu faz diferente: **uma vez só**, antes de executar, transforma a expressão numa função Python.

```python
compile_expr(Binary('>', Column('idade'), Literal(3)), escopo)
#  ≈  lambda linha: maior_que(linha[3], 3)
```

O nome `idade` já virou a posição `3`. Durante a execução, é só indexar a tupla. 🚀

```python
match expr:
    case Literal(value=value):
        return lambda row: value
    case Column():
        return itemgetter(scope.resolve(expr))       # nome → posição, uma vez só
    case Binary(op=op, left=left, right=right):
        fn = BINARY_OPS[op]
        fl, fr = compile_expr(left, scope), compile_expr(right, scope)
        return lambda row: fn(fl(row), fr(row))      # funções montadas com funções
```

Essas funções que "lembram" variáveis de fora (`value`, `fn`, `fl`, `fr`) são **closures**. A árvore de
expressão vira uma árvore de closures.

## 🔍 O escopo: quem é `idade`?

Cada operador tem um `scope` que descreve suas linhas: uma lista de `Slot(tabela, coluna)`.
Depois de um JOIN, por exemplo:

```text
posição:   0          1             2                3           4            5
slot:    (t, id)  (t, apelido)  (t, especie_id)  (t, idade)  (e, id)  (e, nome) ...
```

`scope.resolve(Column('apelido'))` procura slots com esse nome:

| Situação | Resultado |
|---|---|
| exatamente um | ✅ a posição dele |
| nenhum | ❌ `Coluna desconhecida: 'apelidu'` |
| mais de um (`id` existe em `t` e em `e`) | ❌ `A coluna 'id' é ambígua — diga de qual tabela: t.id, e.id` |

## 🕳️ NULL: o valor que não é valor

`NULL` significa **"não sei"**. E qualquer conta com "não sei" dá "não sei":

```sql
SELECT 1 + NULL, NULL = NULL, NULL > 3;     -- NULL, NULL, NULL
```

Sim: `NULL = NULL` **não** é verdadeiro. Se eu não sei a idade de dois tatus, não sei se são iguais!
Por isso existe `IS NULL`.

### A lógica de três valores

Com `NULL`, a lógica deixa de ter dois valores (V/F) e passa a ter três (V/F/?).
As regras saem do bom senso: *"FALSO e qualquer coisa é FALSO"*, *"VERDADEIRO ou qualquer coisa é VERDADEIRO"*.

| `AND` | **V** | **F** | **?** |
|:-:|:-:|:-:|:-:|
| **V** | V | F | ? |
| **F** | F | F | F |
| **?** | ? | F | ? |

| `OR` | **V** | **F** | **?** |
|:-:|:-:|:-:|:-:|
| **V** | V | V | V |
| **F** | V | F | ? |
| **?** | V | ? | ? |

| `NOT` | |
|:-:|:-:|
| **V** | F |
| **F** | V |
| **?** | ? |

```python
def logic_and(a, b):
    if a is False or b is False:
        return False          # FALSO AND "não sei" = FALSO
    if a is None or b is None:
        return None
    return True
```

### ⚠️ O WHERE só deixa passar o VERDADEIRO

O `Filter` testa `truth(valor) is True`. Então "não sei" **não passa**:

```sql
-- O tatu "Misterioso" tem idade NULL. Ele não aparece em NENHUMA das duas:
SELECT COUNT(*) FROM tatus WHERE idade > 3;    -- 4
SELECT COUNT(*) FROM tatus WHERE idade <= 3;   -- 4   (e são 9 tatus!)
```

E um clássico que pega até gente experiente:

```sql
SELECT 5 NOT IN (1, 2, NULL);   -- NULL, e não TRUE! (5 é diferente de "não sei"? não sei...)
```

## 🧪 Tipos: o Tatu é rigoroso

Para ensinar, o Tatu prefere reclamar a adivinhar:

```text
tatu> SELECT 'a' > 1;
✖ Erro de tipo: Não dá para comparar TEXT com INTEGER ('a' > 1)
```

Algumas escolhas (documentadas em [`expressions.py`](../tatu/expressions.py)):

- `7 / 2` com dois inteiros dá `3` (divisão inteira, como no SQL); `7.0 / 2` dá `3.5`;
- a divisão inteira **trunca em direção ao zero**: `-7 / 2` dá `-3` (em Python, `-7 // 2` daria `-4`!);
- dividir por zero é erro (o SQLite devolveria `NULL`);
- `LIKE` diferencia maiúsculas: `'Bola' LIKE 'b%'` é falso.

## 📊 Agregações e GROUP BY

```sql
SELECT especie_id, COUNT(*), AVG(idade)
FROM tatus
GROUP BY especie_id;
```

O `HashAggregate` usa um **dicionário de baldes**: a chave é o valor do `GROUP BY`, e cada balde
junta os valores de cada agregação.

```text
linhas que chegam                     groups = {
(1, 'Bolinha',      2, 3)    ──▶        (2,): [[1, 1],  [3, 4]],     ← COUNT(*) e AVG(idade)
(4, 'Dona Galinha', 1, 5)    ──▶        (1,): [[1, 1],  [5, 1]],
(5, 'Tatá',         1, 1)    ──▶        ...
(6, 'Fuleco',       2, 4)    ──▶      }
                                       ▼
                         (2, 2, 3.5), (1, 2, 3.0), ...
```

No fim, cada balde passa pela sua função: `COUNT` → `len`, `SUM` → `sum`, `AVG` → `sum / len`…
Detalhes importantes:

- agregações **ignoram NULL**: `COUNT(idade)` conta só quem tem idade; `COUNT(*)` conta linhas;
- sem `GROUP BY`, a tabela inteira é **um grupo só** — e, mesmo vazia, devolve uma linha (`COUNT(*) = 0`);
- `COUNT(DISTINCT x)` remove repetidos do balde antes de contar.

### "A coluna precisa estar no GROUP BY…" — por quê?

Depois do `HashAggregate`, o escopo **só tem** as chaves do grupo e os resultados das agregações.
O escopo é marcado como `aggregated=True`, e uma coluna que não está lá gera o erro:

```text
tatu> SELECT apelido, COUNT(*) FROM tatus;
✖ Erro de catálogo: A coluna 'apelido' precisa estar no GROUP BY ou dentro de uma agregação
```

Faz sentido: a linha de resultado representa **nove** tatus. Qual dos nove apelidos mostrar?

O truque que liga tudo: o escopo pós-agregação guarda a **expressão** de cada slot. Quando o
`SELECT` ou o `HAVING` pedem `COUNT(*)`, `scope.find_expr` acha o slot com uma expressão **igual**
(lembra das dataclasses imutáveis do [capítulo 3](03-parser.md)?) e devolve a posição. Nada é recalculado.

## 🧪 Experimente

```sql
SELECT NULL AND FALSE, NULL OR TRUE, NOT NULL;
SELECT COALESCE(idade, 0), TYPEOF(idade) FROM tatus WHERE apelido = 'Misterioso';
SELECT bioma, COUNT(*) AS n, COUNT(DISTINCT tatu_id) AS tatus
FROM avistamentos GROUP BY bioma HAVING COUNT(*) > 1 ORDER BY n DESC;
```

## 🏋️ Para praticar

- 🐾 Adicione as funções `SUBSTR(texto, inicio, tamanho)` e `REPLACE(texto, de, para)` (`SCALAR_FUNCTIONS`).
- 🐾 Crie a agregação `GROUP_CONCAT(x)` que junta textos com vírgula.
- 🐾🐾 Faça `LIKE` ignorar maiúsculas e crie `ILIKE`... ou o contrário!

---

<p align="center"><a href="04-planejador.md">← Planejador</a> · <a href="06-armazenamento.md"><b>próximo: 💾 Armazenamento →</b></a></p>
