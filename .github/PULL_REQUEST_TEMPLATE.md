## O que muda

<!-- Uma ou duas frases. Se fecha uma issue: "Fecha #123". -->

## Por quê

<!-- Que problema resolve ou o que ensina? -->

## Checklist

- [ ] `python -m unittest discover -s tests` passa
- [ ] `ruff check .` passa
- [ ] `python scripts/check_docs.py` passa
- [ ] Testes novos cobrem o caso feliz, `NULL`, erros e (se muda dados) o `ROLLBACK`
- [ ] Mudanças no armazenamento registram o desfazer no diário (`journal.record`)
- [ ] Sem dependências novas em `tatu/` e sem sintaxe além do Python 3.10
- [ ] Documentação atualizada (`docs/08-referencia-sql.md`, capítulo da etapa, README se for destaque)
- [ ] Linha no `CHANGELOG.md` em `## [Não lançado]`
- [ ] Exemplos de saída nas docs copiados de uma execução real
