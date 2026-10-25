# ❓ Perguntas frequentes

> [← índice](README.md) · [README](../README.md)

## 🏭 Posso usar o Tatu DB em produção?

**Não.** Ele guarda tudo na memória, regrava o arquivo inteiro a cada mudança, atende um usuário por vez
e foi escrito para ser **lido**, não para ser rápido. Para produção, use [SQLite](https://sqlite.org/)
(embutido) ou [PostgreSQL](https://www.postgresql.org/) (servidor). Use o Tatu para entender como eles funcionam.

## 🐢 Por que Python, se bancos de verdade são escritos em C, C++, Rust…?

Porque o objetivo é que **qualquer pessoa consiga ler o código**. Em Python, um operador de JOIN cabe em
dez linhas e um gerador (`yield`) mostra o modelo Volcano sem cerimônia. As ideias são exatamente as
mesmas dos bancos "de verdade" — só a velocidade é que muda.

## 🆚 Qual a diferença para o SQLite?

O SQLite é um banco completo, com 25 anos de estrada e bilhões de instalações. O Tatu é um modelo de
estudo. As **peças** são as mesmas (tokenizer, parser, planejador, operadores, armazenamento,
diário), mas o Tatu escolhe sempre a versão mais simples de cada uma. Algumas diferenças de
comportamento que você pode notar:

| | SQLite | Tatu DB |
|---|---|---|
| tipos | flexíveis (`'a' > 1` funciona) | rigorosos (`'a' > 1` é erro) — para ensinar |
| `1 / 0` | `NULL` | erro de divisão por zero |
| `LIKE` | ignora maiúsculas | diferencia maiúsculas |
| arquivo | binário, em páginas | JSON legível |

## 🕳️ Por que `NULL = NULL` não é verdadeiro?

Porque `NULL` quer dizer **"não sei"**. Se eu não sei a idade de dois tatus, não sei se são iguais.
O resultado é "não sei" de novo — `NULL`. Para perguntar se algo é nulo, use `IS NULL`.
O [capítulo 5](05-expressoes.md#%EF%B8%8F-null-o-valor-que-não-é-valor) explica a lógica de três valores com tabelas-verdade.

## 🔍 Por que `WHERE coluna = NULL` não traz nenhuma linha?

Pelo mesmo motivo: `coluna = NULL` é sempre `NULL`, e o `WHERE` só deixa passar o que é **verdadeiro**.
Escreva `WHERE coluna IS NULL`.

## 📄 Por que o arquivo é JSON e não um formato binário?

Para você poder **abrir e ler** os seus dados num editor de texto e ver como o banco os organiza.
Bancos reais usam páginas binárias de tamanho fixo, o que é bem mais eficiente — e virou o
[exercício 14](09-exercicios.md#14-páginas-em-disco).

## 🌲 Por que os índices são hash e não B-tree?

Um índice hash é um dicionário Python: dá para entender em um minuto. A desvantagem é que ele só
responde "quem tem **exatamente** este valor?". Uma B-tree também responde `<`, `>`, `BETWEEN` e
`ORDER BY`, mas é bem mais complexa — é o [exercício 13](09-exercicios.md#13-índice-b-tree-ou-para-começar-um-índice-ordenado).

## 👥 Dá para dois programas usarem o mesmo arquivo ao mesmo tempo?

Não. Cada um carrega o banco na memória e grava por cima do outro. Controle de concorrência
(travas, MVCC) é o [exercício 16](09-exercicios.md#16-vários-usuários).

## 📏 Qual o tamanho máximo de um banco?

O que couber na memória do seu computador. Na prática, alguns milhares (ou poucos milhões) de linhas
funcionam bem — e fica divertido medir a diferença entre um `SeqScan` e um `IndexScan`!

## 🔢 O que é o `rowid`?

Um número interno, único e permanente que o armazenamento dá a cada linha. Os índices apontam para
rowids. Ele é diferente da sua chave primária: um `UPDATE` pode mudar o `id`, mas não o rowid.
Veja o [capítulo 6](06-armazenamento.md).

## 🐍 Funciona com qual versão do Python?

Do **3.10** em diante, no Windows, macOS e Linux. O CI testa todas as combinações a cada mudança.
Os [instaladores](instalacao.md#-instaladores) nem precisam de Python.

## 🤖 O que são as pastas `.claude/` e o arquivo `CLAUDE.md`?

Configurações para o [Claude Code](https://claude.com/claude-code): regras do projeto, *skills*
(receitas para tarefas comuns, como adicionar uma função SQL) e *agentes* (um revisor, um professor,
um testador...). Veja a seção de IA no [guia de contribuição](../CONTRIBUTING.md#-claude-code-no-projeto).

## 🙋 Achei um bug / tenho uma ideia. E agora?

Abra uma [issue](https://github.com/AlefRP/tatu_db/issues/new/choose)! E se quiser colocar a mão na massa,
o [guia de contribuição](../CONTRIBUTING.md) explica o passo a passo.
