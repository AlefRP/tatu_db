import unittest

from tatu import nodes as n
from tatu.errors import TatuSyntaxError
from tatu.parser import parse


def parse_one(sql):
    statements = parse(sql)
    assert len(statements) == 1
    return statements[0]


def parse_expr(text):
    return parse_one(f"SELECT {text}").items[0].expr


class ExpressionParserTest(unittest.TestCase):
    def test_precedencia_aritmetica(self):
        self.assertEqual(parse_expr("1 + 2 * 3"),
                         n.Binary("+", n.Literal(1), n.Binary("*", n.Literal(2), n.Literal(3))))

    def test_parenteses(self):
        self.assertEqual(parse_expr("(1 + 2) * 3"),
                         n.Binary("*", n.Binary("+", n.Literal(1), n.Literal(2)), n.Literal(3)))

    def test_and_e_mais_forte_que_or(self):
        expr = parse_expr("a OR b AND c")
        self.assertEqual(expr.op, "OR")
        self.assertEqual(expr.right.op, "AND")

    def test_numero_negativo_vira_literal(self):
        self.assertEqual(parse_expr("-5"), n.Literal(-5))

    def test_between_usa_o_and_dele(self):
        expr = parse_expr("idade BETWEEN 1 AND 3 AND ativo")
        self.assertEqual(expr.op, "AND")
        self.assertIsInstance(expr.left, n.Between)

    def test_not_in_like_is_null(self):
        self.assertEqual(parse_expr("x NOT IN (1, 2)"),
                         n.InList(n.Column("x"), (n.Literal(1), n.Literal(2)), negated=True))
        self.assertEqual(parse_expr("x NOT LIKE 'a%'"),
                         n.Like(n.Column("x"), n.Literal("a%"), negated=True))
        self.assertEqual(parse_expr("x IS NOT NULL"), n.IsNull(n.Column("x"), negated=True))

    def test_colunas_qualificadas_e_funcoes(self):
        self.assertEqual(parse_expr("t.nome"), n.Column("nome", "t"))
        self.assertEqual(parse_expr("COUNT(*)"), n.Call("COUNT", star=True))
        self.assertEqual(parse_expr("count(DISTINCT x)"), n.Call("COUNT", (n.Column("x"),), distinct=True))

    def test_diferente_tem_duas_grafias(self):
        self.assertEqual(parse_expr("a <> b"), parse_expr("a != b"))

    def test_impressao_da_expressao_volta_a_ser_sql(self):
        self.assertEqual(str(parse_expr("(a + b) * c")), "(a + b) * c")
        self.assertEqual(str(parse_expr("a - (b - c)")), "a - (b - c)")
        self.assertEqual(str(parse_expr("nome = 'Pé''de'")), "nome = 'Pé''de'")


class StatementParserTest(unittest.TestCase):
    def test_select_completo(self):
        stmt = parse_one("""
            SELECT DISTINCT e.nome AS especie, COUNT(*) total
            FROM tatus t
            LEFT JOIN especies e ON t.especie_id = e.id
            WHERE t.idade > 1
            GROUP BY e.nome HAVING COUNT(*) > 1
            ORDER BY total DESC, 1
            LIMIT 10 OFFSET 5
        """)
        self.assertTrue(stmt.distinct)
        self.assertEqual([i.alias for i in stmt.items], ["especie", "total"])
        self.assertEqual(stmt.from_, n.TableRef("tatus", "t"))
        self.assertEqual(stmt.joins[0].kind, "LEFT")
        self.assertEqual(stmt.order_by[0], n.OrderItem(n.Column("total"), desc=True))
        self.assertEqual((stmt.limit, stmt.offset), (n.Literal(10), n.Literal(5)))

    def test_create_table(self):
        stmt = parse_one("""
            CREATE TABLE IF NOT EXISTS tatus (
                id INT PRIMARY KEY,
                apelido VARCHAR(40) NOT NULL UNIQUE,
                especie_id INTEGER REFERENCES especies(id),
                ativo BOOL DEFAULT TRUE
            )
        """)
        self.assertTrue(stmt.if_not_exists)
        id_col, apelido, especie, ativo = stmt.columns
        self.assertEqual((id_col.type, id_col.primary_key), ("INTEGER", True))
        self.assertEqual((apelido.type, apelido.not_null, apelido.unique), ("TEXT", True, True))
        self.assertEqual(especie.references, ("especies", "id"))
        self.assertEqual(ativo.default, n.Literal(True))

    def test_insert_varias_linhas(self):
        stmt = parse_one("INSERT INTO t (a, b) VALUES (1, 'x'), (2, NULL)")
        self.assertEqual(stmt.columns, ("a", "b"))
        self.assertEqual(len(stmt.rows), 2)

    def test_update_delete(self):
        update = parse_one("UPDATE t SET a = a + 1, b = 'z' WHERE id = 3")
        self.assertEqual([col for col, _ in update.assignments], ["a", "b"])
        self.assertEqual(parse_one("DELETE FROM t").where, None)

    def test_parametros_sao_numerados(self):
        stmt = parse_one("SELECT * FROM t WHERE a = ? AND b = ?")
        params = [node for node in n.walk(stmt) if isinstance(node, n.Param)]
        self.assertEqual([p.index for p in params], [0, 1])

    def test_varios_comandos(self):
        self.assertEqual(len(parse("BEGIN; SELECT 1;; COMMIT;")), 3)

    def test_erros_de_sintaxe(self):
        for sql in ["SELECT", "SELECT 1 +", "SELEC 1", "CREATE TABLE t (a FOO)",
                    "SELECT (1", "SELECT 1 SELECT 2", "INSERT INTO t VALUES 1"]:
            with self.subTest(sql=sql), self.assertRaises(TatuSyntaxError):
                parse(sql)

    def test_mensagem_mostra_o_que_foi_digitado(self):
        with self.assertRaises(TatuSyntaxError) as ctx:
            parse("SELEC 1")
        self.assertIn("'SELEC'", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
