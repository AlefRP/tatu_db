"""Ponto de entrada usado pelo PyInstaller para gerar o executável `tatu`.

O PyInstaller precisa de um script "de verdade" (fora do pacote), porque o
``tatu/__main__.py`` usa imports relativos.
"""

from tatu.repl import main

raise SystemExit(main())
