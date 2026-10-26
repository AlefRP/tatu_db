"""Integração dos widgets com o motor; sem diálogos nem arquivos do usuário."""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tatu.errors import TatuError
from tatu.result import Result
from tatu.toca import TocaApp, _smoke_test, tk
from tatu.toca_session import RunReport


class TocaUiTest(unittest.TestCase):
    def setUp(self):
        if tk is None:
            self.skipTest("Tkinter não está instalado")
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk não tem uma tela disponível: {error}")
        self.root.withdraw()
        self.app = TocaApp(self.root)
        self.wait_for(lambda: bool(self.app._results) and not self.app._busy)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def tearDown(self):
        if hasattr(self, "app") and not self.app._closed:
            if self.app.session.in_transaction:
                self.app.session.rollback()
            self.app.session.dirty = False
            self.app._saved_sql = self.app.editor.get("1.0", "end-1c")
            self.app.close()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.root.update()
            if predicate():
                return
            time.sleep(0.01)
        self.fail("A interface não concluiu a operação em 5 segundos")

    def execute(self, sql):
        self.app.set_sql(sql)
        self.app.run_query()
        self.wait_for(lambda: not self.app._busy)

    def test_consulta_atualiza_grade_e_historico(self):
        self.execute("SELECT apelido FROM tatus WHERE especie_id=2 ORDER BY apelido;")
        self.assertEqual(self.app._displayed_rows, [("Bolinha",), ("Fuleco",)])
        self.assertEqual(len(self.app.result_tree.get_children()), 2)
        self.assertTrue(self.app.history_tree.get_children())

    def test_verificacao_do_pacote_executa_sql_e_fecha_sem_dialogos(self):
        # A janela de teste já terminou a consulta inicial; a verificação
        # agenda outra consulta, como faz no executável instalado.
        self.app._startup_job = self.root.after(10000, lambda: None)
        with patch("tatu.toca.messagebox.askyesnocancel") as ask:
            self.assertEqual(_smoke_test(self.app), 0)
        ask.assert_not_called()
        self.assertTrue(self.app._closed)
        self.assertIsNone(self.app.session.path)

    def test_verificacao_do_pacote_recusa_resultado_incorreto(self):
        self.app._startup_job = self.root.after(10000, lambda: None)
        wrong = RunReport(results=[Result(columns=["resposta"], rows=[(41,)])])
        with patch.object(self.app.session, "run", return_value=wrong):
            self.assertEqual(_smoke_test(self.app), 1)
        self.assertTrue(self.app._closed)

    def test_execucao_respeita_selecao_do_editor(self):
        self.app.set_sql("SELECT 7; SELECT * FROM inexistente;")
        self.app.editor.tag_add("sel", "1.0", "1.9")
        self.app.run_query()
        self.wait_for(lambda: not self.app._busy)
        self.assertEqual(self.app._displayed_rows, [(7,)])
        self.assertEqual(len(self.app._results), 1)

    def test_copiar_respeita_linha_selecionada_pelo_teclado(self):
        self.execute("SELECT apelido FROM tatus WHERE especie_id=2 ORDER BY apelido;")
        self.app._selected_cell = (0, 0)
        self.app.result_tree.selection_set("row-1")
        self.app.copy_result()
        self.assertEqual(self.root.clipboard_get(), "Fuleco")

    def test_erro_mantem_resultados_anteriores_do_script(self):
        self.execute("SELECT 42; SELECT * FROM inexistente;")
        self.assertEqual(self.app._results[0].rows, [(42,)])
        self.assertEqual(self.app.notebook.select(), str(self.app.messages_tab))
        self.assertIn("inexistente", self.app.messages.get("1.0", "end"))

    def test_falha_ao_abrir_sql_aparece_sem_perder_editor(self):
        old_sql = self.app.editor.get("1.0", "end-1c")
        path = str(Path(self.directory.name) / "inexistente.sql")
        with patch("tatu.toca.filedialog.askopenfilename", return_value=path), \
                patch.object(self.app, "_show_error") as show:
            self.app.load_query()
        self.assertIsInstance(show.call_args.args[1], TatuError)
        self.assertEqual(self.app.editor.get("1.0", "end-1c"), old_sql)

    def test_falha_ao_salvar_sql_e_csv_e_exibida(self):
        path = str(Path(self.directory.name) / "consulta.sql")
        with patch("tatu.toca.filedialog.asksaveasfilename", return_value=path), \
                patch("tatu.toca.write_sql", side_effect=TatuError("sem espaço")), \
                patch.object(self.app, "_show_error") as show:
            self.assertFalse(self.app.save_query())
        self.assertIsInstance(show.call_args.args[1], TatuError)
        with patch("tatu.toca.filedialog.asksaveasfilename", return_value=path), \
                patch("tatu.toca.export_csv", side_effect=TatuError("sem permissão")), \
                patch.object(self.app, "_show_error") as show:
            self.app.export_result()
        self.assertIsInstance(show.call_args.args[1], TatuError)

    def test_cancelar_fechamento_preserva_transacao(self):
        self.execute("BEGIN; UPDATE tatus SET idade=99 WHERE id=1;")
        with patch("tatu.toca.messagebox.askyesnocancel", return_value=None):
            self.app.close()
        self.assertFalse(self.app._closed)
        self.assertTrue(self.app.session.in_transaction)

    def test_salvar_criar_e_reabrir_banco(self):
        original = str(Path(self.directory.name) / "laboratorio.tatu")
        other = str(Path(self.directory.name) / "novo.tatu")
        with patch("tatu.toca.filedialog.asksaveasfilename", return_value=original):
            self.assertTrue(self.app.save_database())
        with patch("tatu.toca.filedialog.asksaveasfilename", return_value=other):
            self.app.new_database()
        self.assertEqual(self.app.session.tables(), [])
        with patch("tatu.toca.filedialog.askopenfilename", return_value=original):
            self.app.open_database()
        self.assertEqual(self.app.session.tables(), ["avistamentos", "especies", "tatus"])
        self.assertTrue(Path(original).is_file())
