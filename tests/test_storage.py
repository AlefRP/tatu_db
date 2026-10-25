import json
import os
import tempfile
import unittest

import tatu
from tatu.demo import DEMO_SQL
from tatu.errors import TatuError


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "zoo.tatu")

    def tearDown(self):
        self.dir.cleanup()

    def test_tudo_sobrevive_a_reabertura(self):
        with tatu.connect(self.path) as db:
            db.executescript(DEMO_SQL)
            expected = {t: db.execute(f"SELECT * FROM {t}").rows for t in db.tables()}
            schemas = {t: db.schema(t) for t in db.tables()}

        with tatu.connect(self.path) as db:
            self.assertEqual({t: db.execute(f"SELECT * FROM {t}").rows for t in db.tables()}, expected)
            self.assertEqual({t: db.schema(t) for t in db.tables()}, schemas)
            # índices e restrições também voltam
            plan = db.execute("EXPLAIN SELECT * FROM tatus WHERE especie_id = 1").rows
            self.assertIn("idx_tatus_especie", plan[-1][0])
            with self.assertRaises(tatu.ConstraintError):
                db.execute("INSERT INTO tatus (apelido, especie_id) VALUES ('x', 99)")
            # o auto-incremento continua de onde parou
            db.execute("INSERT INTO tatus (apelido) VALUES ('Novo')")
            self.assertEqual(db.execute("SELECT id FROM tatus WHERE apelido = 'Novo'").scalar(), 10)

    def test_arquivo_e_json_legivel(self):
        with tatu.connect(self.path) as db:
            db.executescript("CREATE TABLE t (id INTEGER PRIMARY KEY, nome TEXT); "
                             "INSERT INTO t VALUES (1, 'Pé de Pano');")
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["formato"], "tatu-db")
        self.assertEqual(data["tabelas"][0]["linhas"], [[1, 1, "Pé de Pano"]])
        self.assertFalse(os.path.exists(self.path + ".tmp"))  # o temporário foi renomeado

    def test_select_nao_regrava_o_arquivo(self):
        with tatu.connect(self.path) as db:
            db.execute("CREATE TABLE t (x INTEGER)")
            before = os.stat(self.path).st_mtime_ns
            db.execute("SELECT * FROM t")
            self.assertEqual(os.stat(self.path).st_mtime_ns, before)

    def test_banco_em_memoria_nao_cria_arquivo(self):
        with tatu.connect(":memory:") as db:
            db.execute("CREATE TABLE t (x INTEGER)")
        self.assertEqual(os.listdir(self.dir.name), [])

    def test_arquivo_estranho_e_recusado(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write('{"outra": "coisa"}')
        with self.assertRaises(TatuError):
            tatu.connect(self.path)

    def test_banco_fechado(self):
        db = tatu.connect()
        db.close()
        with self.assertRaises(TatuError):
            db.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
