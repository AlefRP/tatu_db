"""Regressões de escala: fontes legíveis sem esticar editor nem colunas."""

import gc
import unittest
from contextlib import contextmanager

from tatu.toca import TocaApp, tk, tkfont


class TocaDisplayTest(unittest.TestCase):
    def setUp(self):
        # Pule o teste inteiro quando o Tk não está disponível. Um skip em
        # cada subTest continuaria até os cálculos finais com listas vazias.
        if tk is None:
            self.skipTest("Tkinter não está instalado")
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk não tem uma tela disponível: {error}")
        root.destroy()

    def tearDown(self):
        # Objetos Tcl devem ser coletados pela mesma thread que os criou.
        gc.collect()

    @contextmanager
    def scaled_app(self, factor):
        if tk is None:
            self.skipTest("Tkinter não está instalado")
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk não tem uma tela disponível: {error}")
        root.withdraw()
        # Muda só este interpretador Tk: a escala do Windows permanece intacta.
        root.tk.call("tk", "scaling", factor * 96 / 72)
        app = None
        try:
            app = TocaApp(root)
            root.after_cancel(app._startup_job)
            app._startup_job = None
            yield app
        finally:
            if app is None:
                root.destroy()
            else:
                app.session.dirty = False
                app._saved_sql = app.editor.get("1.0", "end-1c")
                app.close()

    def test_linhas_acomodam_fontes_em_100_150_e_200_por_cento(self):
        for factor in (1, 1.5, 2):
            with self.subTest(escala=factor), self.scaled_app(factor) as app:
                line = tkfont.Font(root=app.root, font=app.body_font).metrics("linespace")
                row = int(app.style.lookup("Treeview", "rowheight"))
                catalog_row = int(app.style.lookup("Catalog.Treeview", "rowheight"))
                self.assertGreaterEqual(row, line + app.dp(4))
                self.assertGreaterEqual(catalog_row, line + app.dp(4))
                self.assertAlmostEqual(app.dp(100), factor * 100, delta=2)

    def test_lateral_e_icone_mantem_proporcao_com_o_texto(self):
        ratios = []
        for factor in (1, 1.5, 2):
            with self.subTest(escala=factor), self.scaled_app(factor) as app:
                line = tkfont.Font(root=app.root, font=app.body_font).metrics("linespace")
                ratios.append(int(app.sidebar.cget("width")) / line)
                self.assertIsNotNone(app.icon)
                self.assertGreaterEqual(app.icon.width(), app.dp(44))
                self.assertLessEqual(app.icon.width(), app.dp(52))
        self.assertLess(max(ratios) / min(ratios), 1.2)

    def test_janela_ampla_preserva_largura_das_colunas_e_altura_do_editor(self):
        for factor in (1, 1.5, 2):
            with self.subTest(escala=factor), self.scaled_app(factor) as app:
                report = app.session.run("SELECT nome, peso_kg FROM especies ORDER BY id;")
                app._show_report(report)
                app.root.deiconify()
                app.root.update_idletasks()
                columns = app.result_tree["columns"]
                before = [app.result_tree.column(column, "width") for column in columns]
                editor_height = app.editor_frame.winfo_height()
                app.root.geometry("3840x2160")
                app.root.update_idletasks()
                after = [app.result_tree.column(column, "width") for column in columns]
                self.assertEqual(before, after)
                self.assertTrue(all(not app.result_tree.column(column, "stretch") for column in columns))
                self.assertAlmostEqual(app.editor_frame.winfo_height(), editor_height, delta=app.dp(2))
                line = tkfont.Font(root=app.root, font=app.mono_font).metrics("linespace")
                self.assertLessEqual(app.editor_frame.winfo_height(), 12 * line + app.dp(55))
