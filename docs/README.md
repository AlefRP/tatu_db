<p align="center">
  <img src="assets/tatu.svg" alt="O tatu, mascote do Tatu DB" width="220">
</p>

<h1 align="center">📚 Trilha de aprendizado do Tatu DB</h1>

<p align="center"><i>Um banco de dados, cavado camada por camada.</i></p>

---

Esta trilha segue um comando SQL desde o momento em que você aperta Enter até as linhas
aparecerem na tela. Cada capítulo cobre **uma etapa** e aponta para **um arquivo** de [`tatu/`](../tatu/).
A ideia é ler o capítulo com o código aberto ao lado.

## 🧭 O mapa

| | Capítulo | Arquivos | Tempo |
|:-:|---|---|:-:|
| 🗺️ | [1. A jornada de uma consulta](01-jornada.md) | [`database.py`](../tatu/database.py) | ☕ |
| 🔤 | [2. Tokenizer](02-tokenizer.md) | [`tokenizer.py`](../tatu/tokenizer.py) | ☕ |
| 🌳 | [3. Parser e AST](03-parser.md) | [`parser.py`](../tatu/parser.py), [`nodes.py`](../tatu/nodes.py) | ☕☕ |
| 🧭 | [4. Planejador e operadores](04-planejador.md) | [`planner.py`](../tatu/planner.py), [`operators.py`](../tatu/operators.py) | ☕☕☕ |
| 🧮 | [5. Expressões, NULL e agregações](05-expressoes.md) | [`expressions.py`](../tatu/expressions.py) | ☕☕ |
| 💾 | [6. Armazenamento: a toca](06-armazenamento.md) | [`storage.py`](../tatu/storage.py), [`executor.py`](../tatu/executor.py) | ☕☕ |
| 🔁 | [7. Transações e o diário](07-transacoes.md) | [`storage.py`](../tatu/storage.py), [`database.py`](../tatu/database.py) | ☕ |
| 📖 | [8. Referência do SQL](08-referencia-sql.md) | — | consulta |
| 🏋️ | [9. Exercícios](09-exercicios.md) | todos! | 🐾 a 🐾🐾🐾 |

E também: 📦 [Instalação](instalacao.md) (Windows, macOS e Linux) · ❓ [Perguntas frequentes](faq.md) ·
🦔 [Toca: cliente gráfico](toca.md) · 🤝 [Como contribuir](../CONTRIBUTING.md)

## 🎒 Antes de começar

- Você precisa saber **Python** (funções, classes, dicionários) e um pouco de **SQL** (`SELECT ... FROM ... WHERE`).
- Os capítulos 4 e 5 usam **geradores** (`yield`) e **closures** (funções que guardam variáveis). Se forem novidade,
  não tem problema: o texto explica quando aparecem.
- Deixe um shell aberto: `python -m tatu`, depois `.demo`. Sempre que um capítulo mostrar um comando, rode-o!
- Se preferir uma janela, abra `python -m tatu.toca`: o Toca já começa com o banco de exemplo,
  e **Ctrl+Enter** executa a consulta no editor.

> [!TIP]
> O comando mais útil desta trilha é o **`EXPLAIN`**. Ele mostra o plano que o Tatu montou para a sua consulta.
> Mude a consulta, rode `EXPLAIN` de novo e veja o plano mudar.

## 🗣️ Um pequeno glossário

| Termo | Em português claro |
|---|---|
| **Relação / tabela** | um conjunto de linhas com as mesmas colunas |
| **Tupla / linha** | um registro: `(1, 'Bolinha', 2, 3)` |
| **Esquema** | a "planta" da tabela: nomes, tipos e restrições das colunas |
| **Token** | uma "palavra" do SQL: `SELECT`, `idade`, `>=`, `'texto'` |
| **AST** | *Abstract Syntax Tree*: o comando SQL transformado em objetos Python |
| **Plano** | a árvore de operadores que vai de fato buscar as linhas |
| **Heap** | o lugar onde as linhas da tabela ficam guardadas, sem ordem especial |
| **Índice** | uma estrutura extra que acha linhas rápido, sem olhar a tabela inteira |
| **Transação** | um grupo de mudanças que acontece por inteiro — ou não acontece |

<p align="center">
  <a href="01-jornada.md"><b>Começar pelo capítulo 1 →</b></a>
</p>
