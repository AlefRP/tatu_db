# 🔤 2. Tokenizer: separando as palavras

> **Arquivo:** [`tatu/tokenizer.py`](../tatu/tokenizer.py) · [← A jornada](01-jornada.md) · [próximo: Parser →](03-parser.md)

Para o computador, `SELECT apelido FROM tatus` é só uma sequência de caracteres:
`S`, `E`, `L`, `E`, `C`, `T`, espaço, `a`, `p`… O **tokenizer** (ou *analisador léxico*) agrupa
esses caracteres em **tokens** — as "palavras" da linguagem.

```text
  S E L E C T   a p e l i d o   F R O M   t a t u s   W H E R E   i d a d e   > =   3
  └────┬────┘   └─────┬─────┘   └──┬──┘   └───┬───┘   └───┬───┘   └───┬───┘   └┬┘   │
   KEYWORD         IDENT        KEYWORD     IDENT      KEYWORD      IDENT    SYMBOL NUMBER
```

Ele **não entende gramática**. `FROM SELECT 3 >=` é uma sequência de tokens perfeitamente válida —
quem vai reclamar é o parser, no próximo capítulo.

## 🧩 Os tipos de token

| Tipo | Exemplos | Valor guardado |
|---|---|---|
| `KEYWORD` | `SELECT`, `where`, `Join` | a palavra em MAIÚSCULAS: `'WHERE'` |
| `IDENT` | `tatus`, `Apelido`, `"Nome Esquisito"` | o nome em minúsculas (ou exato, se entre aspas duplas) |
| `NUMBER` | `42`, `3.14`, `.5` | já convertido: `42` (int), `3.14` (float) |
| `STRING` | `'tatu-bola'`, `'pé-d''água'` | o texto sem as aspas: `pé-d'água` |
| `SYMBOL` | `(` `)` `,` `;` `.` `=` `<>` `<=` `\|\|` `*` | o próprio símbolo |
| `PARAM` | `?` | — (o parser numera depois) |
| `EOF` | (fim do texto) | — |

Cada token também guarda `pos`, a **posição** no texto original. Ela é a chave para mensagens de erro boas.

## 🔁 Como funciona: um laço e oito regras

O tokenizer inteiro é um `while` que olha o caractere atual e decide o que fazer:

```python
while i < n:
    ch = sql[i]
    if ch.isspace():          # 1) espaço → ignora
    if sql.startswith("--", i):   # 2) comentário → pula até o fim da linha
    if ch.isdigit():          # 3) número → consome dígitos (e talvez um ponto)
    if ch == "'":             # 4) texto → consome até a aspa de fechamento
    if ch == '"':             # 5) identificador entre aspas
    if ch.isalpha():          # 6) palavra → palavra-chave ou nome?
    if ch == "?":             # 7) parâmetro
    for symbol in SYMBOLS:    # 8) símbolos: os de 2 caracteres primeiro!
```

Dois detalhes que valem ouro:

**🥇 Símbolos longos primeiro.** A lista `SYMBOLS` começa com `"<="`, `">="`, `"<>"`… Se `"<"` viesse
antes, `<=` viraria dois tokens: `<` e `=`. Esse princípio tem nome: *maximal munch* ("mordida máxima").

**🔠 Palavra-chave ou nome?** Lemos a palavra inteira e só então perguntamos se ela está em `KEYWORDS`.
Assim, `selecao` não é confundido com `SELECT` + `ao`.

```python
if word.upper() in KEYWORDS:
    tokens.append(Token("KEYWORD", word.upper(), start))
else:
    tokens.append(Token("IDENT", word.lower(), start))  # Tatus == tatus
```

## 🧵 Textos com aspas dentro

Como colocar uma aspa dentro de um texto que é delimitado por aspas? No SQL, escrevendo **duas**:

```sql
SELECT 'pé-d''água';   -- o valor é: pé-d'água
```

O tokenizer, ao ver `'`, olha o próximo caractere: se for outra `'`, é uma aspa "de verdade";
se não, o texto acabou.

## 🎯 Erros que apontam o lugar exato

Como cada token sabe sua posição, a exceção `TatuSyntaxError` consegue desenhar uma setinha:

```text
tatu> SELECT 'sem fim;
✖ Erro de sintaxe: Texto sem aspa de fechamento (linha 1, coluna 8)
  SELECT 'sem fim;
         ^
```

O cálculo de linha e coluna está em [`errors.py`](../tatu/errors.py): contamos quantos `\n` existem antes
da posição, e a coluna é a distância até o último `\n`.

## 🧪 Experimente

```python
>>> from tatu.tokenizer import tokenize
>>> tokenize("SELECT * FROM tatus WHERE apelido = 'Bola' -- comentário")
[KEYWORD('SELECT'), SYMBOL('*'), KEYWORD('FROM'), IDENT('tatus'), KEYWORD('WHERE'),
 IDENT('apelido'), SYMBOL('='), STRING('Bola'), EOF(None)]

>>> tokenize("1<=2")          # sem espaços, e mesmo assim funciona
[NUMBER(1), SYMBOL('<='), NUMBER(2), EOF(None)]
```

## 🏋️ Para praticar

- 🐾 Faça o tokenizer aceitar comentários de bloco: `/* ... */`.
- 🐾 Aceite números com expoente: `1e3`, `2.5E-2`.
- 🐾🐾 Hoje `3abc` vira `NUMBER(3) IDENT(abc)`. Faça virar um erro claro: "número mal formado".

---

<p align="center"><a href="01-jornada.md">← A jornada</a> · <a href="03-parser.md"><b>próximo: 🌳 Parser e AST →</b></a></p>
