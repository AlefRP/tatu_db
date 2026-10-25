---
name: explicar-consulta
description: Explica, passo a passo e em português, como o Tatu DB executa uma consulta SQL — tokens, árvore sintática (AST), plano de execução (EXPLAIN) e resultado — ligando cada etapa ao arquivo e às linhas do código. Use quando alguém perguntar "como essa consulta funciona por dentro?", "por que o plano ficou assim?", "o que acontece quando eu rodo X?", ou quiser estudar uma consulta específica.
---

# Explicar uma consulta, etapa por etapa

O objetivo é **ensinar**. Quem pergunta está aprendendo como um banco de dados funciona; a resposta
deve seguir a jornada da consulta (capítulo `docs/01-jornada.md`) usando a consulta da própria pessoa.

## 1. Rastreie a consulta de verdade

Nunca descreva tokens, árvores ou planos "de cabeça": rode o rastreador, que carrega os dados de
exemplo (`.demo`: tabelas `especies`, `tatus`, `avistamentos`) e mostra cada etapa:

```bash
python .claude/skills/explicar-consulta/rastrear.py "SELECT apelido FROM tatus WHERE idade > 3"
python .claude/skills/explicar-consulta/rastrear.py --sem-demo "SELECT 1 + 2 * 3"
```

Se a consulta usar tabelas que não existem na demo, adapte: crie as tabelas num script ou peça à
pessoa o esquema.

## 2. Explique cada etapa, na ordem

Para cada etapa, diga **o que entra, o que sai e onde está no código** (use `arquivo:linha` — leia o
código para achar as linhas certas):

1. **🔤 Tokenizer** (`tatu/tokenizer.py`) — quais tokens surgiram; destaque algo interessante
   (palavra-chave × nome, `<=` virando um token só, textos com `''`).
2. **🌳 Parser** (`tatu/parser.py`, `tatu/nodes.py`) — mostre a árvore e explique a precedência quando
   houver expressões (`AND` × `OR`, `*` × `+`, a pegadinha do `BETWEEN ... AND`).
3. **🧭 Planejador** (`tatu/planner.py`) — leia o plano **de baixo para cima**; relacione com a ordem
   lógica `FROM → WHERE → GROUP BY → HAVING → ORDER BY → SELECT → DISTINCT → LIMIT`. Diga por que houve
   (ou não) `IndexScan`: a regra está em `_choose_index`.
4. **⚙️ Operadores** (`tatu/operators.py`) — explique o modelo Volcano (geradores puxando linhas) com
   os operadores que apareceram; aponte quais são bloqueantes (`Sort`, `HashAggregate`).
5. **🧮 Expressões** (`tatu/expressions.py`) — se houver `NULL`, funções ou agregações, explique a
   lógica de três valores e o `HashAggregate` com baldes.
6. **📋 Resultado** — mostre as linhas e ligue de volta à pergunta original.

## 3. Feche com algo para a pessoa experimentar

Sugira uma variação que mude o plano ou o resultado, por exemplo:
- criar um índice (`CREATE INDEX ...`) e rodar o `EXPLAIN` de novo;
- trocar `JOIN` por `LEFT JOIN` e ver as linhas com `NULL`;
- trocar `WHERE` por `HAVING` (ou o contrário) e entender o erro.

## Estilo

- Português do Brasil, frases curtas, sem jargão não explicado.
- Mostre a saída real do rastreador; não invente saídas.
- Ajuste a profundidade ao nível da pessoa: para iniciantes, foque em 2–3 etapas; para quem já sabe,
  mergulhe no código.
- Aponte o capítulo da trilha correspondente (`docs/0N-....md`) para leitura posterior.
