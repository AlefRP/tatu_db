"""
🌵 Dados de demonstração: espécies de tatu, tatus e avistamentos.

Carregue no shell com ``.demo``. Os números são aproximados — servem
para brincar com SQL, não para um trabalho de biologia!
"""

DEMO_SQL = """
CREATE TABLE especies (
  id              INTEGER PRIMARY KEY,
  nome            TEXT NOT NULL UNIQUE,
  nome_cientifico TEXT,
  faixas          INTEGER,
  peso_kg         REAL,
  ameacada        BOOLEAN DEFAULT FALSE
);

INSERT INTO especies VALUES
  (1, 'tatu-galinha',      'Dasypus novemcinctus',    9,  4.5, FALSE),
  (2, 'tatu-bola',         'Tolypeutes tricinctus',   3,  1.4, TRUE),
  (3, 'tatu-canastra',     'Priodontes maximus',     12, 32.0, TRUE),
  (4, 'tatu-peba',         'Euphractus sexcinctus',   6,  4.8, FALSE),
  (5, 'tatu-de-rabo-mole', 'Cabassous unicinctus',   12,  3.5, FALSE),
  (6, 'tatu-mulita',       'Dasypus septemcinctus',   7,  1.6, FALSE);

CREATE TABLE tatus (
  id         INTEGER PRIMARY KEY,
  apelido    TEXT NOT NULL,
  especie_id INTEGER REFERENCES especies(id),
  idade      INTEGER
);

INSERT INTO tatus (apelido, especie_id, idade) VALUES
  ('Bolinha',      2, 3),
  ('Canastrão',    3, 7),
  ('Peba',         4, 2),
  ('Dona Galinha', 1, 5),
  ('Tatá',         1, 1),
  ('Fuleco',       2, 4),
  ('Cavucador',    5, 6),
  ('Zé Mulita',    6, 3),
  ('Misterioso',   NULL, NULL);

CREATE TABLE avistamentos (
  id      INTEGER PRIMARY KEY,
  tatu_id INTEGER NOT NULL REFERENCES tatus(id),
  bioma   TEXT NOT NULL,
  data    TEXT
);

INSERT INTO avistamentos (tatu_id, bioma, data) VALUES
  (1, 'Caatinga',       '2026-01-12'),
  (1, 'Caatinga',       '2026-02-03'),
  (6, 'Caatinga',       '2026-02-20'),
  (2, 'Pantanal',       '2026-03-01'),
  (2, 'Cerrado',        '2026-03-15'),
  (3, 'Cerrado',        '2026-03-18'),
  (4, 'Mata Atlântica', '2026-04-02'),
  (5, 'Mata Atlântica', '2026-04-02'),
  (4, 'Pampa',          '2026-04-27'),
  (7, 'Amazônia',       '2026-05-09'),
  (8, 'Cerrado',        '2026-05-30'),
  (9, 'Amazônia',       NULL);

CREATE INDEX idx_tatus_especie ON tatus (especie_id);
"""

DEMO_QUERIES = [
    "SELECT * FROM especies WHERE ameacada;",
    "SELECT t.apelido, e.nome AS especie FROM tatus t LEFT JOIN especies e ON t.especie_id = e.id;",
    "SELECT bioma, COUNT(*) AS vezes FROM avistamentos GROUP BY bioma ORDER BY vezes DESC, bioma;",
    "EXPLAIN SELECT apelido FROM tatus WHERE especie_id = 2;",
]
