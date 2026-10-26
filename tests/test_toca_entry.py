"""A entrada gráfica não muda o shell nem exige Tk para importar o motor."""

import unittest
from unittest.mock import patch

from tatu.repl import main
from tatu.toca import main as gui_main


class TocaEntryTest(unittest.TestCase):
    def test_verificacao_do_pacote_nao_aceita_arquivo_nem_demo(self):
        for arguments in (["--smoke-test", "importante.tatu"], ["--smoke-test", "--demo"]):
            with self.subTest(arguments=arguments), patch("sys.stderr"), \
                    patch("tatu.toca.tk") as tkinter, self.assertRaises(SystemExit) as context:
                gui_main(arguments)
            self.assertEqual(context.exception.code, 2)
            tkinter.Tk.assert_not_called()

    def test_gui_encaminha_arquivo_sem_abrir_shell(self):
        with patch("tatu.toca.main", return_value=0) as gui_main:
            self.assertEqual(main(["--gui", "meu banco.tatu"]), 0)
        gui_main.assert_called_once_with(["meu banco.tatu"])

    def test_gui_sem_arquivo_encaminha_demonstracao(self):
        with patch("tatu.toca.main", return_value=0) as gui_main:
            self.assertEqual(main(["--gui"]), 0)
        gui_main.assert_called_once_with([])

    def test_gui_e_comando_sql_sao_exclusivos(self):
        with patch("sys.stderr"), self.assertRaises(SystemExit) as context:
            main(["--gui", "-c", "SELECT 1"])
        self.assertEqual(context.exception.code, 2)
