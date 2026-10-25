import unittest

import tatu
from tatu.errors import CatalogError, ConstraintError, TatuTypeError


class ConstraintTest(unittest.TestCase):
    def setUp(self):
        self.db = tatu.connect()
        self.db.executescript("""
            CREATE TABLE especies (id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE);
            CREATE TABLE tatus (
                id INTEGER PRIMARY KEY,
                apelido TEXT NOT NULL,
                especie_id INTEGER REFERENCES especies(id),
                peso REAL DEFAULT 1.0
            );
            INSERT INTO especies VALUES (1, 'tatu-bola'), (2, 'tatu-peba');
            INSERT INTO tatus (apelido, especie_id) VALUES ('Bolinha', 1);
        """)

    def count(self, table):
        return self.db.execute(f"SELECT COUNT(*) FROM {table}").scalar()

    def test_primary_key_repetida(self):
        with self.assertRaises(ConstraintError):
            self.db.execute("INSERT INTO especies VALUES (1, 'outra')")

    def test_unique(self):
        with self.assertRaises(ConstraintError):
            self.db.execute("INSERT INTO especies VALUES (3, 'tatu-bola')")
        with self.assertRaises(ConstraintError):
            self.db.execute("UPDATE especies SET nome = 'tatu-bola' WHERE id = 2")

    def test_not_null(self):
        with self.assertRaises(ConstraintError):
            self.db.execute("INSERT INTO tatus (especie_id) VALUES (1)")

    def test_auto_incremento_e_default(self):
        self.db.execute("INSERT INTO tatus (apelido) VALUES ('Novo')")
        self.assertEqual(self.db.execute("SELECT id, peso FROM tatus WHERE apelido = 'Novo'").rows,
                         [(2, 1.0)])

    def test_tipos_sao_conferidos_e_convertidos_sem_perda(self):
        with self.assertRaises(TatuTypeError):
            self.db.execute("INSERT INTO tatus (apelido) VALUES (42)")
        self.db.execute("INSERT INTO tatus (apelido, peso) VALUES ('Inteiro', 3)")
        self.assertEqual(self.db.execute("SELECT peso FROM tatus WHERE apelido = 'Inteiro'").scalar(), 3.0)

    def test_references_no_insert_e_update(self):
        with self.assertRaises(ConstraintError):
            self.db.execute("INSERT INTO tatus (apelido, especie_id) VALUES ('Fantasma', 99)")
        with self.assertRaises(ConstraintError):
            self.db.execute("UPDATE tatus SET especie_id = 99")
        self.db.execute("INSERT INTO tatus (apelido, especie_id) VALUES ('Sem espécie', NULL)")

    def test_references_impede_apagar_o_pai(self):
        with self.assertRaises(ConstraintError):
            self.db.execute("DELETE FROM especies WHERE id = 1")
        with self.assertRaises(ConstraintError):
            self.db.execute("UPDATE especies SET id = 10 WHERE id = 1")
        with self.assertRaises(ConstraintError):
            self.db.execute("DROP TABLE especies")
        self.db.execute("DELETE FROM especies WHERE id = 2")  # ninguém usa a 2
        self.assertEqual(self.count("especies"), 1)

    def test_references_precisa_apontar_para_chave(self):
        with self.assertRaises(CatalogError):
            self.db.execute("CREATE TABLE x (nome TEXT REFERENCES tatus(apelido))")

    def test_comando_que_falha_no_meio_nao_deixa_rastro(self):
        # a 3ª linha repete a chave: as duas primeiras também são desfeitas
        with self.assertRaises(ConstraintError):
            self.db.execute("INSERT INTO especies VALUES (5, 'a'), (6, 'b'), (5, 'c')")
        self.assertEqual(self.count("especies"), 2)

    def test_update_que_falha_no_meio_nao_deixa_rastro(self):
        self.db.execute("INSERT INTO especies VALUES (3, 'tatu-galinha')")
        with self.assertRaises(ConstraintError):
            self.db.execute("UPDATE especies SET nome = 'mesmo nome'")
        names = [r[0] for r in self.db.execute("SELECT nome FROM especies ORDER BY id")]
        self.assertEqual(names, ["tatu-bola", "tatu-peba", "tatu-galinha"])

    def test_catalogo(self):
        with self.assertRaises(CatalogError):
            self.db.execute("CREATE TABLE especies (id INTEGER)")
        self.db.execute("CREATE TABLE IF NOT EXISTS especies (id INTEGER)")
        with self.assertRaises(CatalogError):
            self.db.execute("SELECT * FROM nao_existe")
        with self.assertRaises(CatalogError):
            self.db.execute("CREATE TABLE dupla (a INTEGER, a TEXT)")
        with self.assertRaises(CatalogError):
            self.db.execute("CREATE TABLE duas_pk (a INTEGER PRIMARY KEY, b INTEGER PRIMARY KEY)")
        self.db.execute("DROP TABLE IF EXISTS nao_existe")

    def test_indice_unico_com_repetidos_falha(self):
        self.db.execute("INSERT INTO tatus (apelido) VALUES ('Bolinha')")
        with self.assertRaises(ConstraintError):
            self.db.execute("CREATE UNIQUE INDEX uq_apelido ON tatus (apelido)")
        self.assertNotIn("uq_apelido", self.db.storage.get_table("tatus").indexes)

    def test_unique_aceita_varios_nulls(self):
        self.db.execute("CREATE TABLE u (x INTEGER UNIQUE)")
        self.db.execute("INSERT INTO u VALUES (NULL), (NULL), (1)")
        self.assertEqual(self.count("u"), 3)


if __name__ == "__main__":
    unittest.main()
