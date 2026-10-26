import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tatu.database import Database
from tatu.errors import CatalogError, TatuError, TransactionError
from tatu.result import Result
from tatu.storage import Storage
from tatu.toca_session import Session, export_csv, read_sql, write_sql


class TocaSessionTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.folder = Path(self.directory.name)
        self.session = Session(demo=False)

    def tearDown(self):
        self.session.close()
        self.directory.cleanup()

    def create(self):
        report = self.session.run(
            "CREATE TABLE tatus(id INTEGER PRIMARY KEY, apelido TEXT NOT NULL);"
            "INSERT INTO tatus(apelido) VALUES('Tatá');"
        )
        self.assertTrue(report.ok, report.error)

    def test_demo_fica_isolada_do_banco_anterior(self):
        path = self.folder / "meu.tatu"
        self.session.new(path)
        self.create()
        self.session.load_demo()
        self.assertIsNone(self.session.path)
        self.assertEqual(self.session.tables(), ["avistamentos", "especies", "tatus"])
        self.assertFalse(self.session.dirty)
        with Database(str(path)) as original:
            self.assertEqual(original.tables(), ["tatus"])
            self.assertEqual(original.execute("SELECT apelido FROM tatus").scalar(), "Tatá")

    def test_salvar_como_preserva_tipos_indices_e_novo_destino(self):
        self.create()
        self.assertTrue(self.session.dirty)
        self.session.run("CREATE INDEX ix_apelido ON tatus(apelido);")
        path = self.folder / "salvo.tatu"
        self.session.save_as(path)
        self.assertEqual(self.session.path, str(path))
        self.assertFalse(self.session.dirty)
        with Database(str(path)) as reopened:
            self.assertEqual(reopened.execute("SELECT apelido FROM tatus").scalar(), "Tatá")
            self.assertIn("ix_apelido", reopened.storage.get_table("tatus").indexes)
        self.session.run("INSERT INTO tatus(apelido) VALUES('Bolinha');")
        with Database(str(path)) as reopened:
            self.assertEqual(reopened.execute("SELECT COUNT(*) FROM tatus").scalar(), 2)

    def test_falha_ao_salvar_mantem_conexao_destino_e_dados(self):
        self.create()
        previous = self.session.db
        path = self.folder / "falhou.tatu"
        with (
            patch.object(Storage, "save", side_effect=OSError("disco cheio")),
            self.assertRaisesRegex(TatuError, "disco cheio"),
        ):
            self.session.save_as(path)
        self.assertIs(self.session.db, previous)
        self.assertIsNone(self.session.path)
        self.assertTrue(self.session.dirty)
        self.assertEqual(self.session.run("SELECT apelido FROM tatus").last.scalar(), "Tatá")
        other = Session(demo=False)
        try:
            other.new(path)
        finally:
            other.close()

    def test_abrir_arquivo_invalido_preserva_banco_atual(self):
        self.create()
        previous = self.session.db
        for name, contents in (
            ("texto.tatu", "arquivo qualquer"),
            ("formato.tatu", '{"formato":"outro","versao":1,"tabelas":[]}'),
            ("versao.tatu", '{"formato":"tatu-db","versao":999,"tabelas":[]}'),
            ("incompleto.tatu", '{"formato":"tatu-db","versao":1,"tabelas":[{}]}'),
        ):
            with self.subTest(name=name):
                path = self.folder / name
                path.write_text(contents, encoding="utf-8")
                with self.assertRaises(TatuError):
                    self.session.open(path)
                self.assertIs(self.session.db, previous)
                self.assertEqual(self.session.tables(), ["tatus"])

    def test_novo_nao_sobrescreve_arquivo_existente(self):
        path = self.folder / "importante.tatu"
        path.write_text("não substituir", encoding="utf-8")
        with self.assertRaises(TatuError):
            self.session.new(path)
        self.assertEqual(path.read_text(encoding="utf-8"), "não substituir")

    def test_salvar_como_exige_confirmacao_e_recusa_arquivo_corrompido(self):
        self.create()
        path = self.folder / "existente.tatu"
        path.write_text("texto importante", encoding="utf-8")
        for overwrite in (False, True):
            with self.assertRaises(TatuError):
                self.session.save_as(path, overwrite=overwrite)
        self.assertEqual(path.read_text(encoding="utf-8"), "texto importante")
        path.unlink()
        other = Session(demo=False)
        other.new(path)
        other.close()
        with self.assertRaises(TatuError):
            self.session.save_as(path)
        self.session.save_as(path, overwrite=True)
        self.assertEqual(self.session.run("SELECT apelido FROM tatus").last.scalar(), "Tatá")

    def test_duas_sessoes_nao_editam_mesmo_arquivo(self):
        path = self.folder / "aberto.tatu"
        self.session.new(path)
        second = Session(demo=False)
        try:
            with self.assertRaisesRegex(TatuError, "outra janela"):
                second.open(self.folder / "." / "aberto.tatu")
            with self.assertRaisesRegex(TatuError, "outra janela"):
                second.save_as(path, overwrite=True)
            self.session.close()
            second.open(path)
            self.assertEqual(second.tables(), [])
        finally:
            second.close()

    def test_transacao_bloqueia_troca_e_fechar_desfaz(self):
        path = self.folder / "transacao.tatu"
        self.session.new(path)
        self.create()
        self.assertTrue(self.session.begin().ok)
        self.session.run("INSERT INTO tatus(apelido) VALUES('descartar');")
        for action in (self.session.new, self.session.load_demo,
                       lambda: self.session.open(path), lambda: self.session.save_as(path)):
            with self.assertRaises(TransactionError):
                action()
        self.session.close()
        with Database(str(path)) as reopened:
            self.assertEqual(reopened.execute("SELECT COUNT(*) FROM tatus").scalar(), 1)

    def test_rollback_recupera_dados_e_estado_de_memoria(self):
        self.session.load_demo()
        self.assertFalse(self.session.dirty)
        self.assertTrue(self.session.begin().ok)
        self.assertTrue(self.session.run("DELETE FROM avistamentos;").ok)
        self.assertTrue(self.session.dirty)
        self.assertTrue(self.session.rollback().ok)
        self.assertFalse(self.session.dirty)
        self.assertEqual(self.session.run("SELECT COUNT(*) FROM avistamentos").last.scalar(), 12)

    def test_relatorio_mantem_resultado_antes_de_erro(self):
        report = self.session.run("SELECT 42 AS resposta; SELECT * FROM faltando; SELECT 99;")
        self.assertFalse(report.ok)
        self.assertIsInstance(report.error, CatalogError)
        self.assertEqual(len(report.results), 1)
        self.assertEqual(report.last.rows, [(42,)])
        self.assertGreaterEqual(report.elapsed_ms, 0)
        self.assertFalse(self.session.history[0].ok)
        self.assertEqual(self.session.history[0].rows, 1)

    def test_sintaxe_invalida_nao_executa_primeiro_comando(self):
        report = self.session.run("CREATE TABLE nunca(id INTEGER); SELECT FROM;")
        self.assertFalse(report.ok)
        self.assertEqual(report.results, [])
        self.assertEqual(self.session.tables(), [])

    def test_catalogo_e_sql_escapam_identificadores(self):
        name = 'tatu "bola" de nome longo ' + "á" * 60
        quoted = '"' + name.replace('"', '""') + '"'
        report = self.session.run(
            f'CREATE TABLE {quoted}("nome próprio" TEXT DEFAULT \'Tatá\');'
            f'INSERT INTO {quoted}("nome próprio") VALUES(\'Bolinha\');'
            f'CREATE INDEX "índice nome" ON {quoted}("nome próprio");'
        )
        self.assertTrue(report.ok, report.error)
        info = self.session.table_info(name)
        self.assertEqual(info.row_count, 1)
        self.assertEqual(info.columns[0].name, "nome próprio")
        self.assertEqual(info.indexes[0].name, "índice nome")
        query = self.session.table_query(name)
        self.assertEqual(self.session.run(query).last.rows, [("Bolinha",)])
        with Database() as reconstructed:
            reconstructed.executescript(info.sql)
            self.assertEqual(reconstructed.tables(), [name])

    def test_arquivos_sql_suportam_bom_e_unicode(self):
        path = self.folder / "consulta.sql"
        sql = "SELECT 'Tatá' AS apelido;\n-- comentário\n"
        write_sql(path, sql)
        self.assertEqual(read_sql(path), sql)
        path.write_text(sql, encoding="utf-8-sig")
        self.assertEqual(read_sql(path), sql)
        path.write_bytes(b"\xff\xfe\x00")
        with self.assertRaises(TatuError):
            read_sql(path)

    def test_csv_preserva_aspas_quebras_unicode_e_precisao(self):
        path = self.folder / "resultado.csv"
        result = Result(columns=["apelido", "observação", "real", "nulo"],
                        rows=[('Tatá "Bola"', "linha 1\nlinha 2, caatinga", 1.234567890123456, None)])
        export_csv(path, result)
        with path.open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.reader(source))
        self.assertEqual(rows[0], result.columns)
        self.assertEqual(rows[1], ['Tatá "Bola"', "linha 1\nlinha 2, caatinga", "1.234567890123456", ""])

    def test_exportacao_falha_sem_destruir_arquivo_anterior(self):
        path = self.folder / "consulta.sql"
        path.write_text("anterior", encoding="utf-8")
        with (
            patch("tatu.toca_session.os.replace", side_effect=OSError("disco cheio")),
            self.assertRaises(TatuError),
        ):
            write_sql(path, "novo")
        self.assertEqual(path.read_text(encoding="utf-8"), "anterior")
        self.assertEqual(list(self.folder.glob(".toca-*.tmp")), [])

    def test_novo_banco_vazio_grava_json_valido(self):
        path = self.folder / "vazio.tatu"
        self.session.new(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["formato"], "tatu-db")
        self.assertEqual(data["tabelas"], [])


if __name__ == "__main__":
    unittest.main()
