import unittest

from tatu.errors import TatuSyntaxError
from tatu.tokenizer import tokenize


def kinds_and_values(sql):
    return [(t.kind, t.value) for t in tokenize(sql)]


class TokenizerTest(unittest.TestCase):
    def test_comando_simples(self):
        self.assertEqual(kinds_and_values("SELECT nome FROM tatus WHERE idade >= 3"), [
            ("KEYWORD", "SELECT"), ("IDENT", "nome"), ("KEYWORD", "FROM"), ("IDENT", "tatus"),
            ("KEYWORD", "WHERE"), ("IDENT", "idade"), ("SYMBOL", ">="), ("NUMBER", 3),
            ("EOF", None),
        ])

    def test_palavras_chave_e_nomes_ignoram_maiusculas(self):
        self.assertEqual(kinds_and_values("select Tatus")[:2],
                         [("KEYWORD", "SELECT"), ("IDENT", "tatus")])

    def test_numeros(self):
        values = [t.value for t in tokenize("42 3.14 .5")][:-1]
        self.assertEqual(values, [42, 3.14, 0.5])
        self.assertIsInstance(values[0], int)
        self.assertIsInstance(values[1], float)

    def test_texto_com_aspa_escapada(self):
        self.assertEqual(tokenize("'pé-d''água'")[0].value, "pé-d'água")

    def test_identificador_entre_aspas_duplas_mantem_maiusculas(self):
        token = tokenize('"Nome Esquisito"')[0]
        self.assertEqual((token.kind, token.value), ("IDENT", "Nome Esquisito"))

    def test_comentarios_sao_ignorados(self):
        self.assertEqual(kinds_and_values("SELECT 1 -- um comentário\n;"),
                         [("KEYWORD", "SELECT"), ("NUMBER", 1), ("SYMBOL", ";"), ("EOF", None)])

    def test_identificador_com_aspa_dupla_escapada(self):
        token = tokenize('"Tatu ""Bola"""')[0]
        self.assertEqual((token.kind, token.value), ("IDENT", 'Tatu "Bola"'))
        self.assertEqual(token.pos, 0)

    def test_identificador_escapado_sem_fechamento_aponta_inicio(self):
        with self.assertRaises(TatuSyntaxError) as ctx:
            tokenize('SELECT "Tatu ""Bola')
        self.assertEqual(ctx.exception.pos, 7)
        self.assertIn("Identificador sem aspa", str(ctx.exception))

    def test_simbolos_de_dois_caracteres(self):
        values = [t.value for t in tokenize("<= <> != || <")][:-1]
        self.assertEqual(values, ["<=", "<>", "!=", "||", "<"])

    def test_parametro(self):
        self.assertEqual(tokenize("?")[0].kind, "PARAM")

    def test_texto_sem_fechamento(self):
        with self.assertRaises(TatuSyntaxError) as ctx:
            tokenize("SELECT 'oops")
        self.assertIn("aspa", str(ctx.exception))

    def test_caractere_invalido_aponta_a_posicao(self):
        with self.assertRaises(TatuSyntaxError) as ctx:
            tokenize("SELECT @")
        self.assertEqual(ctx.exception.pos, 7)
        self.assertIn("^", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
