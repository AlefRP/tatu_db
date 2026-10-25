---
name: lancar-versao
description: Prepara e publica uma versão nova do Tatu DB — escolhe o número (SemVer), revisa o CHANGELOG, dispara o workflow "Nova versão" do GitHub Actions (que sobe a versão, cria a tag e publica o Release com os instaladores de Windows, macOS e Linux) e acompanha até o fim. Use quando pedirem para "lançar", "publicar", "soltar uma versão", "fazer release" ou "criar a tag".
disable-model-invocation: true
---

# Lançar uma versão

O lançamento é feito pelo GitHub Actions:

- `.github/workflows/versao.yml` ("Nova versão") — roda os testes, sobe `__version__` em
  `tatu/__init__.py`, fecha `## [Não lançado]` no `CHANGELOG.md` (montando as notas a partir dos
  commits se a seção estiver vazia), faz o commit, cria a tag `vX.Y.Z` e chama o release;
- `.github/workflows/release.yml` — gera e testa todos os pacotes (`pacotes.yml`), publica o GitHub
  Release com notas, tabela de downloads e `SHA256SUMS.txt`, e instala o que publicou em cada sistema.

## 1. Escolha o tipo (Versionamento Semântico)

Leia `## [Não lançado]` no `CHANGELOG.md`, a versão atual em `tatu/__init__.py` e os commits desde a
última tag (`git log $(git describe --tags --abbrev=0)..HEAD --oneline`):

| Mudou… | Tipo | Exemplo |
|---|---|---|
| algo que quebra uso antigo (sintaxe, API Python, formato do `.tatu`) | `major` | 0.4.2 → 1.0.0 |
| recurso novo compatível | `minor` | 0.4.2 → 0.5.0 |
| só correções | `patch` | 0.4.2 → 0.4.3 |

Mostre à pessoa a versão resultante e as notas (ensaio, sem gravar nada):

```bash
python scripts/bump_version.py --tipo minor --dry-run
```

Se as notas geradas pelos commits ficarem pobres, sugira escrever a seção `## [Não lançado]` à mão
(e commitar) antes de lançar.

## 2. Verifique

```bash
python -m unittest discover -s tests
ruff check .
python scripts/check_docs.py
```

O CI do `main` precisa estar verde. Se o formato do arquivo `.tatu` mudou, confira que
`FILE_FORMAT_VERSION` em `tatu/storage.py` subiu e que arquivos antigos ainda abrem.

## 3. Dispare — só com confirmação explícita

Publicar uma versão é visível para todo mundo: **confirme o tipo/versão com a pessoa antes**.

- Com o `gh` logado: `gh workflow run versao.yml -f tipo=minor` (ou `-f versao=1.0.0`).
- Sem o `gh`: peça para a pessoa ir em **Actions → Nova versão → Run workflow** e escolher o tipo.

## 4. Acompanhe

`gh run watch` (com o `gh` logado) ou a aba **Actions**. A versão leva alguns minutos: são pacotes
para Windows, macOS (Apple Silicon e Intel) e Linux (x64 e ARM64), cada um instalado e testado.

Se algo falhar:

- **antes da tag** (testes, docs) → corrija no `main` e dispare de novo;
- **num pacote, depois da tag** → corrija no `main` e use **Actions → Release → Run workflow** com a
  mesma tag para republicar (os arquivos são substituídos) — ou lance uma versão `patch`.

Ao final, confira a página do Release: `setup.exe` e `.zip` (Windows), `.pkg` e `.tar.gz` (macOS arm64 e
x86_64), `.deb`, `.rpm` e `.tar.gz` (Linux x86_64 e arm64), a wheel, o sdist e o `SHA256SUMS.txt`.
