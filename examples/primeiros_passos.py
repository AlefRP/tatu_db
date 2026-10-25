"""
🐾 Primeiros passos com o Tatu DB pelo Python.

Rode a partir da raiz do projeto:

    python examples/primeiros_passos.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tatu  # noqa: E402

# 1) Abrir um banco. Sem caminho, ele vive só na memória.
db = tatu.connect()

# 2) Criar tabelas
db.executescript("""
    CREATE TABLE tocas (
        id     INTEGER PRIMARY KEY,
        bioma  TEXT NOT NULL,
        fundura_m REAL
    );
    CREATE TABLE tatus (
        id      INTEGER PRIMARY KEY,
        apelido TEXT NOT NULL UNIQUE,
        toca_id INTEGER REFERENCES tocas(id),
        idade   INTEGER DEFAULT 0
    );
""")

# 3) Inserir dados — use ? para valores que vêm de fora (nada de SQL injection)
db.execute("INSERT INTO tocas (bioma, fundura_m) VALUES (?, ?)", ("Cerrado", 2.5))
db.execute("INSERT INTO tocas (bioma, fundura_m) VALUES (?, ?)", ("Caatinga", 1.2))
for apelido, toca, idade in [("Bolinha", 2, 3), ("Canastrão", 1, 7), ("Peba", 1, 2)]:
    db.execute("INSERT INTO tatus (apelido, toca_id, idade) VALUES (?, ?, ?)", (apelido, toca, idade))

# 4) Consultar — o Result é iterável e sabe se imprimir como tabela
resultado = db.execute("""
    SELECT c.bioma, COUNT(*) AS moradores, AVG(t.idade) AS idade_media
    FROM tatus t JOIN tocas c ON t.toca_id = c.id
    GROUP BY c.bioma
    ORDER BY moradores DESC
""")
print(resultado)
for bioma, moradores, idade_media in resultado:
    print(f"  🕳️  {bioma}: {moradores} tatu(s), idade média {idade_media:.1f}")

print(db.execute("SELECT apelido FROM tatus WHERE id = 1").scalar())  # 'Bolinha'
print(db.execute("SELECT * FROM tocas").as_dicts())

# 5) Ver o plano de execução
print(db.execute("EXPLAIN SELECT * FROM tatus WHERE apelido = 'Peba'"))

# 6) Transações: tudo ou nada
db.execute("BEGIN")
db.execute("DELETE FROM tatus")
print("Durante a transação:", db.execute("SELECT COUNT(*) FROM tatus").scalar())  # 0
db.execute("ROLLBACK")
print("Depois do ROLLBACK:", db.execute("SELECT COUNT(*) FROM tatus").scalar())   # 3

# 7) Erros são exceções com mensagens amigáveis
try:
    db.execute("INSERT INTO tatus (apelido, toca_id) VALUES ('Perdido', 99)")
except tatu.ConstraintError as erro:
    print("Ops!", erro)
