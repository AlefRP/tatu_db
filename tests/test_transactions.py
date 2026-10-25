import os
import tempfile
import unittest

import tatu
from tatu.errors import ConstraintError, TransactionError


class TransactionTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "toca.tatu")
        self.db = tatu.connect(self.path)
        self.db.executescript("""
            CREATE TABLE tatus (id INTEGER PRIMARY KEY, apelido TEXT);
            INSERT INTO tatus (apelido) VALUES ('Bolinha'), ('Fuleco');
        """)

    def tearDown(self):
        self.db.close()
        self.dir.cleanup()

    def apelidos(self, db=None):
        return [r[0] for r in (db or self.db).execute("SELECT apelido FROM tatus ORDER BY id")]

    def test_rollback_desfaz_tudo(self):
        self.db.executescript("""
            BEGIN;
            INSERT INTO tatus (apelido) VALUES ('Peba');
            UPDATE tatus SET apelido = 'BOLA' WHERE id = 1;
            DELETE FROM tatus WHERE id = 2;
            CREATE TABLE temporaria (x INTEGER);
            CREATE INDEX idx_apelido ON tatus (apelido);
        """)
        self.assertEqual(self.apelidos(), ["BOLA", "Peba"])
        self.db.execute("ROLLBACK")
        self.assertEqual(self.apelidos(), ["Bolinha", "Fuleco"])
        self.assertNotIn("temporaria", self.db.tables())
        self.assertNotIn("idx_apelido", self.db.storage.get_table("tatus").indexes)

    def test_rollback_recupera_tabela_apagada(self):
        self.db.executescript("BEGIN; DROP TABLE tatus;")
        self.assertEqual(self.db.tables(), [])
        self.db.execute("ROLLBACK")
        self.assertEqual(self.apelidos(), ["Bolinha", "Fuleco"])

    def test_indices_continuam_certos_depois_do_rollback(self):
        self.db.executescript("BEGIN; UPDATE tatus SET id = id + 10; ROLLBACK;")
        self.assertEqual(self.db.execute("SELECT apelido FROM tatus WHERE id = 1").rows, [("Bolinha",)])
        self.assertEqual(self.db.execute("SELECT apelido FROM tatus WHERE id = 11").rows, [])

    def test_commit_grava_no_disco(self):
        self.db.executescript("BEGIN; INSERT INTO tatus (apelido) VALUES ('Peba'); COMMIT;")
        with tatu.connect(self.path) as other:
            self.assertEqual(self.apelidos(other), ["Bolinha", "Fuleco", "Peba"])

    def test_sem_commit_nada_chega_ao_disco(self):
        self.db.executescript("BEGIN; INSERT INTO tatus (apelido) VALUES ('Fantasma');")
        with tatu.connect(self.path) as other:
            self.assertEqual(self.apelidos(other), ["Bolinha", "Fuleco"])
        self.db.close()  # fechar com transação aberta = ROLLBACK
        with tatu.connect(self.path) as other:
            self.assertEqual(self.apelidos(other), ["Bolinha", "Fuleco"])

    def test_erro_dentro_da_transacao_desfaz_so_o_comando(self):
        self.db.execute("BEGIN")
        self.db.execute("INSERT INTO tatus (apelido) VALUES ('Peba')")
        with self.assertRaises(ConstraintError):
            self.db.execute("INSERT INTO tatus (id, apelido) VALUES (10, 'a'), (1, 'repetido')")
        self.assertEqual(self.apelidos(), ["Bolinha", "Fuleco", "Peba"])
        self.db.execute("COMMIT")
        with tatu.connect(self.path) as other:
            self.assertEqual(self.apelidos(other), ["Bolinha", "Fuleco", "Peba"])

    def test_uso_errado(self):
        with self.assertRaises(TransactionError):
            self.db.execute("COMMIT")
        with self.assertRaises(TransactionError):
            self.db.execute("ROLLBACK")
        self.db.execute("BEGIN")
        with self.assertRaises(TransactionError):
            self.db.execute("BEGIN")


if __name__ == "__main__":
    unittest.main()
