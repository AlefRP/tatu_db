# 📝 Histórico de mudanças

Todas as mudanças importantes do Tatu DB ficam registradas aqui.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o
[Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.1.0] - 2026-10-25

A primeira versão do tatu saiu da toca! 🐾

### 🧠 Banco de dados

- Tokenizer com mensagens de erro que apontam linha e coluna (`^`).
- Parser descendente recursivo com precedência de operadores e AST imutável.
- Planejador no modelo Volcano: `SeqScan`, `IndexScan`, `Filter`, `NestedLoopJoin`, `HashAggregate`,
  `Sort`, `Project`, `Distinct` e `Limit`, com `EXPLAIN` mostrando a árvore do plano.
- SQL: `CREATE TABLE`, `DROP TABLE`, `CREATE [UNIQUE] INDEX`, `INSERT`, `UPDATE`, `DELETE`, `SELECT` com
  `WHERE`, `[INNER|LEFT|CROSS] JOIN`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT/OFFSET` e `DISTINCT`.
- Tipos `INTEGER`, `REAL`, `TEXT` e `BOOLEAN`; restrições `PRIMARY KEY` (com auto-incremento),
  `NOT NULL`, `UNIQUE`, `DEFAULT` e `REFERENCES`.
- Lógica de três valores para `NULL`, funções (`UPPER`, `LOWER`, `LENGTH`, `TRIM`, `ABS`, `ROUND`,
  `COALESCE`, `TYPEOF`) e agregações (`COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, com `DISTINCT`).
- Índices hash automáticos (PK/UNIQUE) e manuais, usados pelo planejador em `coluna = valor`.
- Transações com diário de desfazer: `BEGIN`, `COMMIT`, `ROLLBACK` e atomicidade por comando.
- Arquivo `.tatu` em JSON legível, gravado de forma atômica (`fsync` + `os.replace`).
- Parâmetros `?` contra SQL injection; API Python com `connect`, `execute`, `executescript` e `Result`.

### 🖥️ Shell

- Shell interativo colorido com tabelas desenhadas, `.tables`, `.schema`, `.demo`, `.read`.
- Modo de comando único (`-c`) e leitura de scripts pelo pipe.

### 📚 Documentação

- Trilha de aprendizado em 9 capítulos, guia de instalação e perguntas frequentes.
- Ilustrações em SVG: o mascote, o banner, a arquitetura, a árvore do plano e a toca do armazenamento.

### 📦 Instalação

- Instaladores de uma linha: `install.sh` (Linux e macOS) e `install.ps1` (Windows).
- Executáveis sem Python (PyInstaller), `setup.exe` (Windows), `.pkg` (macOS) e `.deb` (Linux).

### ⚙️ Projeto

- 88 testes; CI em Windows, macOS e Linux com Python 3.10 a 3.14; workflows de pacotes e release.
- Configuração para o Claude Code: `CLAUDE.md`, skills, agentes, hook de testes e workflow `@claude`.

[Não lançado]: https://github.com/AlefRP/tatu_db/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AlefRP/tatu_db/releases/tag/v0.1.0
