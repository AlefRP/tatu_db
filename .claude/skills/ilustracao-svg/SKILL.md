---
name: ilustracao-svg
description: Cria ou edita ilustrações SVG da documentação do Tatu DB no estilo da casa (paleta terrosa, mascote tatu, cartões com fundo próprio) e confere o resultado renderizando num navegador headless. Use quando pedirem um diagrama, desenho, figura, gravura ou ilustração para o README ou para os capítulos em docs/.
---

# Ilustrações no estilo do Tatu DB

As ilustrações ficam em `docs/assets/` e são **SVG escrito à mão** (sem ferramentas de desenho): leve,
versionável e nítido em qualquer tamanho. Referências: `banner.svg`, `arquitetura.svg`, `plano.svg`,
`toca.svg` e o mascote `tatu.svg`.

## Regras de estilo

- **Fundo próprio sempre** (um cartão `rect` com `rx="22"` e cor clara), para funcionar nos temas claro
  e escuro do GitHub. A exceção é o mascote solto, cujas cores médias funcionam nos dois.
- **Paleta:**

  | Uso | Cores |
  |---|---|
  | texto principal / contornos | `#4A2A12`, `#5A3519`, `#3B2412` |
  | texto secundário | `#6B4423`, `#7A5A3A`, `#8A6A4A` |
  | fundo do cartão | `#FFF8EE` com borda `#E9D5B7` |
  | casco do tatu | gradiente `#E8B57A` → `#B8783F`, faixas `#6E4220` |
  | leitura (scans) | `#DCEBF5` / `#6FA8C7` |
  | filtro / junção | `#E5F2D6` / `#8DB872` |
  | agrupamento | `#FDE7CF` / `#E0A96D` |
  | acabamento (sort, project, limit) | `#ECE0F5` / `#A784C2` |
  | armazenamento | `#F7DEDA` / `#D08A80` |
  | código (fundo escuro) | `#2B1B10`, texto `#FFF1DC`, palavras-chave `#FFB86B`, números `#8FD3D6` |

- **Fontes:** títulos `'Trebuchet MS','Segoe UI','Helvetica Neue',Arial,sans-serif` (26px, peso 800);
  código `Consolas,'Cascadia Code','DejaVu Sans Mono',monospace`. Não use fontes externas.
- **Sem emoji dentro do SVG** (renderizam diferente em cada sistema): desenhe ícones simples com formas.
- **Acessibilidade:** `role="img"`, `<title>` com uma frase descritiva e `aria-labelledby`.
- **Mascote:** copie o grupo `<g id="tatu">` de `docs/assets/tatu.svg` (com os `defs` de gradiente,
  padrão de escamas e `clipPath`) e posicione com `transform="translate(x y) scale(s)"`.
  `scale(-s s)` espelha (olhando para a esquerda). Os pés ficam em y≈184 nas coordenadas do mascote.
- Espaços em `<text>` são colapsados: para recuar uma linha de código, mude o `x`.

## Fluxo

1. Esboce o layout em coordenadas (largura típica: 1000–1200; altura conforme o conteúdo).
2. Escreva o SVG em `docs/assets/<nome>.svg`.
3. **Renderize e olhe** — nunca entregue sem ver:

   ```bash
   python .claude/skills/ilustracao-svg/renderizar.py docs/assets/<nome>.svg
   ```

   O script gera um PNG com a ilustração sobre fundo claro e escuro (precisa de Chrome, Edge ou
   Chromium instalado) e imprime o caminho. Abra o PNG (ferramenta Read) e procure textos sobrepostos,
   cortes nas bordas e alinhamentos tortos. Corrija e renderize de novo.
4. Use no Markdown com texto alternativo: `![descrição](assets/<nome>.svg)` ou
   `<img src="..." alt="..." width="100%">` para centralizar.
5. `python scripts/check_docs.py` confere se o SVG é XML válido e se os links apontam para ele.
