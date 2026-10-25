import io
import unittest

import tatu
from tatu.repl import Paint, Shell, is_complete


class ReplTest(unittest.TestCase):
    def make_shell(self, unicode=True):
        self.out = io.StringIO()
        return Shell(tatu.connect(), Paint(False), unicode, out=self.out)

    def test_comando_completo(self):
        self.assertTrue(is_complete("SELECT 1;"))
        self.assertTrue(is_complete("SELECT 1; -- comentário"))
        self.assertFalse(is_complete("SELECT 1"))
        self.assertFalse(is_complete("SELECT 'texto; ainda aberto"))
        self.assertTrue(is_complete("SELECT @;"))  # erro: deixa rodar para mostrar a mensagem

    def test_script_com_comandos_de_ponto(self):
        shell = self.make_shell()
        ok = shell.script(io.StringIO(".demo\n.tables\nSELECT apelido\nFROM tatus\nWHERE id = 6;\n"))
        output = self.out.getvalue()
        self.assertTrue(ok)
        self.assertIn("avistamentos", output)
        self.assertIn("Fuleco", output)
        self.assertIn("╭", output)

    def test_erro_aparece_e_script_reporta_falha(self):
        shell = self.make_shell(unicode=False)
        ok = shell.script(io.StringIO("SELECT * FROM nada;\nSELECT 1;\n"))
        output = self.out.getvalue()
        self.assertFalse(ok)
        self.assertIn("Erro de catálogo", output)
        self.assertIn("+---", output)  # a consulta seguinte ainda rodou, em ASCII

    def test_quit_interrompe(self):
        shell = self.make_shell()
        shell.script(io.StringIO(".quit\nSELECT 'nunca';\n"))
        self.assertNotIn("nunca", self.out.getvalue())


if __name__ == "__main__":
    unittest.main()
