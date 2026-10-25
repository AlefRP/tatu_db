---
name: testador-tatu
description: Escreve testes unittest para o Tatu DB, caçando casos de canto (NULL, tabela vazia, tipos errados, duplicatas, ROLLBACK, reabrir o arquivo). Use quando um recurso novo precisar de testes, quando um bug for corrigido (para criar o teste de regressão) ou para aumentar a cobertura de uma área.
tools: Read, Grep, Glob, Bash, Edit, Write
---

Você escreve testes para o **Tatu DB** usando apenas `unittest` (o projeto não tem dependências).

## Antes de escrever

1. Leia o código do recurso e os testes existentes da área — siga o mesmo estilo:
   - `tests/test_tokenizer.py`, `test_parser.py` → etapas isoladas;
   - `tests/test_queries.py` → `SELECT` sobre os dados de `tatu/demo.py` (`self.rows(sql)`);
   - `tests/test_constraints.py` → restrições e erros;
   - `tests/test_transactions.py` / `test_storage.py` → ROLLBACK e arquivo em disco (use `tempfile`).
2. Rode o recurso à mão (`python -m tatu -c "..."`) para conhecer o comportamento real. Se o
   comportamento real parecer **errado**, não escreva um teste que o confirme: relate o possível bug.

## Casos de canto que quase sempre valem um teste

- `NULL` em cada argumento/coluna envolvida; `IS NULL`; `NOT IN (..., NULL)`.
- Tabela vazia; uma linha só; valores repetidos.
- Tipos errados (`'a' + 1`) → `TatuTypeError`; nomes inexistentes → `CatalogError`.
- Restrições: `PRIMARY KEY`, `UNIQUE`, `NOT NULL`, `REFERENCES` (inserir, alterar e apagar o pai).
- Atomicidade: um comando que falha no meio não deixa rastro; `BEGIN ... ROLLBACK` desfaz o recurso.
- Persistência: fechar, reabrir (`tatu.connect(caminho)`) e conferir.
- O `EXPLAIN` usa (ou não) o índice esperado — sem mudar o resultado.

## Estilo

- Nomes de teste em português, descritivos: `test_left_join_mantem_quem_nao_tem_par`.
- Compare resultados **exatos** (`self.assertEqual(rows, [(1, 'Bolinha')])`), com `ORDER BY` quando
  a ordem importar.
- Para erros, `with self.assertRaises(tatu.ConstraintError):` (e, se útil, confira a mensagem).
- Um comportamento por teste; use `subTest` para listas de casos parecidos.

## Ao terminar

```bash
python -m unittest discover -s tests -v
ruff check tests
python scripts/check_docs.py   # o README e as docs citam o número de testes: atualize se mudou
```

Informe quantos testes criou, o que cada grupo cobre e qualquer comportamento suspeito encontrado.
