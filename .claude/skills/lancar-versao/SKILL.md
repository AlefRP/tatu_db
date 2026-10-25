---
name: lancar-versao
description: Prepara e publica uma versão nova do Tatu DB — escolhe o número (SemVer), atualiza tatu/__init__.py e o CHANGELOG, roda todas as verificações, cria o commit e a tag vX.Y.Z e acompanha o workflow de release que gera instaladores para Windows, macOS e Linux. Use quando pedirem para "lançar", "publicar", "soltar uma versão", "fazer release" ou "criar a tag".
disable-model-invocation: true
---

# Lançar uma versão

O workflow `.github/workflows/release.yml` faz o trabalho pesado quando recebe uma tag `vX.Y.Z`:
confere a versão, gera wheel, executáveis, `setup.exe`, `.pkg` e `.deb`, testa cada um e cria o
GitHub Release com as notas do `CHANGELOG.md`. Esta skill prepara tudo para isso dar certo.

## 1. Escolha o número (Versionamento Semântico)

Leia `## [Não lançado]` no `CHANGELOG.md` e a versão atual em `tatu/__init__.py`:

| Mudou… | Versão | Exemplo |
|---|---|---|
| algo que quebra uso antigo (sintaxe, API Python, formato do `.tatu`) | **maior** | 0.4.2 → 1.0.0 |
| recurso novo compatível | **menor** | 0.4.2 → 0.5.0 |
| só correções | **correção** | 0.4.2 → 0.4.3 |

Enquanto a versão for `0.x`, mudanças que quebram podem subir só o número do meio — mas avise no CHANGELOG.
Confirme o número com a pessoa antes de seguir.

## 2. Atualize os arquivos

1. `tatu/__init__.py` → `__version__ = "X.Y.Z"` (é a **única** fonte da versão).
2. `CHANGELOG.md`:
   - renomeie `## [Não lançado]` para `## [X.Y.Z] - AAAA-MM-DD` (data de hoje);
   - crie um `## [Não lançado]` vazio acima;
   - atualize os links do rodapé (`[Não lançado]: .../compare/vX.Y.Z...HEAD` e `[X.Y.Z]: .../releases/tag/vX.Y.Z`).
3. Se o formato do arquivo `.tatu` mudou, confira que `FILE_FORMAT_VERSION` em `tatu/storage.py` subiu
   e que arquivos antigos ainda abrem (ou que há uma mensagem clara).

## 3. Verifique tudo

```bash
python -m unittest discover -s tests
ruff check .
python scripts/check_docs.py
python scripts/release_notes.py X.Y.Z      # as notas que irão para o Release
```

Garanta que o CI do `main` está verde antes de lançar.

## 4. Commit, tag e push — só com confirmação explícita

Publicar uma versão é visível para todo mundo. **Mostre o resumo (versão, notas) e peça confirmação
antes de rodar:**

```bash
git add tatu/__init__.py CHANGELOG.md
git commit -m "chore: versão X.Y.Z"
git tag vX.Y.Z
git push origin main vX.Y.Z
```

## 5. Acompanhe o release

O workflow leva alguns minutos (gera e testa pacotes nos três sistemas). Acompanhe com
`gh run watch` (se o `gh` estiver logado) ou na aba **Actions**. Se falhar:

- **"A tag não bate com a versão"** → a tag e o `__version__` divergem; apague a tag
  (`git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z`), corrija e repita.
- **falha num pacote** → leia o log do job, corrija no `main` e crie uma versão de correção.

Ao final, confira a página do Release: devem estar lá o `setup.exe`, o `.zip` do Windows, o `.pkg` e o
`.tar.gz` do macOS, o `.deb` e o `.tar.gz` do Linux, a wheel e o sdist.
