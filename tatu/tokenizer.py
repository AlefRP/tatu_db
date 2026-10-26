"""
🔤 Etapa 1 — Tokenizer (analisador léxico).

Transforma o texto SQL em uma lista de *tokens*: as "palavras" da linguagem.

    "SELECT nome FROM tatus WHERE idade > 3"

vira

    KEYWORD(SELECT) IDENT(nome) KEYWORD(FROM) IDENT(tatus)
    KEYWORD(WHERE) IDENT(idade) SYMBOL(>) NUMBER(3) EOF

O tokenizer não sabe nada de gramática: ele só reconhece palavras,
números, textos e símbolos. Quem dá sentido à sequência é o parser.
"""

from dataclasses import dataclass

from .errors import TatuSyntaxError

KEYWORDS = frozenset("""
    SELECT FROM WHERE AND OR NOT AS DISTINCT
    INSERT INTO VALUES UPDATE SET DELETE
    CREATE TABLE DROP INDEX ON IF EXISTS
    PRIMARY KEY UNIQUE REFERENCES DEFAULT NULL
    TRUE FALSE IS IN BETWEEN LIKE
    JOIN INNER LEFT OUTER CROSS
    GROUP BY HAVING ORDER ASC DESC LIMIT OFFSET
    BEGIN COMMIT ROLLBACK TRANSACTION EXPLAIN
""".split())

# Símbolos de dois caracteres vêm primeiro: "<=" não pode virar "<" e "=".
SYMBOLS = ("<=", ">=", "<>", "!=", "||",
           "=", "<", ">", "+", "-", "*", "/", "%", "(", ")", ",", ";", ".")


@dataclass(frozen=True)
class Token:
    kind: str     # KEYWORD, IDENT, NUMBER, STRING, SYMBOL, PARAM ou EOF
    value: object  # palavra normalizada, número já convertido, texto sem aspas...
    pos: int      # posição no SQL original (para as mensagens de erro)

    def __repr__(self) -> str:
        return f"{self.kind}({self.value!r})"


def tokenize(sql: str) -> list[Token]:
    """Quebra ``sql`` em tokens. O último é sempre ``EOF`` (fim do texto)."""
    tokens: list[Token] = []
    i, n = 0, len(sql)

    while i < n:
        ch = sql[i]

        # 1) espaços em branco não significam nada
        if ch.isspace():
            i += 1
            continue

        # 2) comentários: de "--" até o fim da linha
        if sql.startswith("--", i):
            end = sql.find("\n", i)
            i = n if end == -1 else end
            continue

        # 3) números: 42, 3.14, .5
        if ch.isdigit() or (ch == "." and i + 1 < n and sql[i + 1].isdigit()):
            start = i
            while i < n and sql[i].isdigit():
                i += 1
            if i < n and sql[i] == ".":
                i += 1
                while i < n and sql[i].isdigit():
                    i += 1
                tokens.append(Token("NUMBER", float(sql[start:i]), start))
            else:
                tokens.append(Token("NUMBER", int(sql[start:i]), start))
            continue

        # 4) textos: 'olá' — duas aspas seguidas ('') representam uma aspa
        if ch == "'":
            start = i
            i += 1
            chars = []
            while True:
                if i >= n:
                    raise TatuSyntaxError("Texto sem aspa de fechamento", sql, start)
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        chars.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                chars.append(sql[i])
                i += 1
            tokens.append(Token("STRING", "".join(chars), start))
            continue

        # 5) identificadores entre aspas duplas: "Nome Com Espaço"
        if ch == '"':
            start = i
            i += 1
            chars = []
            while True:
                if i >= n:
                    raise TatuSyntaxError("Identificador sem aspa de fechamento", sql, start)
                if sql[i] == '"':
                    if i + 1 < n and sql[i + 1] == '"':
                        chars.append('"')
                        i += 2
                        continue
                    i += 1
                    break
                chars.append(sql[i])
                i += 1
            tokens.append(Token("IDENT", "".join(chars), start))
            continue

        # 6) palavras: ou são palavras-chave (SELECT) ou nomes (tatus)
        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (sql[i].isalnum() or sql[i] == "_"):
                i += 1
            word = sql[start:i]
            if word.upper() in KEYWORDS:
                tokens.append(Token("KEYWORD", word.upper(), start))
            else:
                # nomes não diferenciam maiúsculas: Tatus == tatus
                tokens.append(Token("IDENT", word.lower(), start))
            continue

        # 7) parâmetros: o "?" de execute("... WHERE id = ?", (3,))
        if ch == "?":
            tokens.append(Token("PARAM", None, i))
            i += 1
            continue

        # 8) símbolos e operadores
        for symbol in SYMBOLS:
            if sql.startswith(symbol, i):
                tokens.append(Token("SYMBOL", symbol, i))
                i += len(symbol)
                break
        else:
            raise TatuSyntaxError(f"Caractere inesperado {ch!r}", sql, i)

    tokens.append(Token("EOF", None, n))
    return tokens
