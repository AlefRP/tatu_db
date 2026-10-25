# 🔐 Segurança

## O Tatu DB não é para produção

O Tatu DB é um projeto **educacional**. Ele não tem controle de acesso, criptografia, isolamento entre
usuários nem proteção contra arquivos `.tatu` adulterados — e não pretende ter. **Não guarde dados
sensíveis nele** e não o exponha numa rede.

## O que nos interessa saber

Mesmo sendo educacional, alguns problemas merecem atenção imediata:

- 🛠️ **Instaladores e pacotes** (`scripts/install.sh`, `scripts/install.ps1`, os executáveis e
  instaladores dos Releases) — por exemplo, algo que permita executar código inesperado na máquina de
  quem instala.
- ⚙️ **Workflows do GitHub Actions** — por exemplo, algo que exponha segredos do repositório.
- 🧠 **O banco em si** — por exemplo, uma consulta que faça o Python executar código arbitrário, ou
  parâmetros `?` que deixem passar SQL injection.

## Como relatar

Use o **relato privado de vulnerabilidades** do GitHub: aba **Security → Report a vulnerability**
neste repositório. Conte o que encontrou, como reproduzir e qual o impacto.

Se não for algo sensível (por exemplo, um travamento com uma consulta estranha), uma
[issue comum](https://github.com/AlefRP/tatu_db/issues/new/choose) já resolve.

## Versões cobertas

Só a versão mais recente (a do branch `main` e o último Release) recebe correções.
