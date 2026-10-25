import unittest

import tatu
from tatu.demo import DEMO_SQL
from tatu.errors import CatalogError, ExecutionError, TatuTypeError


class QueryTest(unittest.TestCase):
    def setUp(self):
        self.db = tatu.connect()
        self.db.executescript(DEMO_SQL)

    def rows(self, sql, params=()):
        return self.db.execute(sql, params).rows

    # ── SELECT básico ──

    def test_select_sem_from(self):
        self.assertEqual(self.rows("SELECT 1 + 2 * 3, 'a' || 'b', 7 / 2, -7 / 2, 7.0 / 2"),
                         [(7, "ab", 3, -3, 3.5)])

    def test_estrela_e_nomes_das_colunas(self):
        result = self.db.execute("SELECT * FROM tatus WHERE id = 1")
        self.assertEqual(result.columns, ["id", "apelido", "especie_id", "idade"])
        self.assertEqual(result.rows, [(1, "Bolinha", 2, 3)])
        result = self.db.execute("SELECT apelido AS nome, idade + 1 FROM tatus WHERE id = 1")
        self.assertEqual(result.columns, ["nome", "idade + 1"])

    def test_where_com_varias_condicoes(self):
        self.assertEqual(
            self.rows("SELECT apelido FROM tatus WHERE idade BETWEEN 3 AND 5 "
                      "AND apelido NOT LIKE 'D%' ORDER BY apelido"),
            [("Bolinha",), ("Fuleco",), ("Zé Mulita",)])

    def test_in_e_is_null(self):
        self.assertEqual(self.rows("SELECT apelido FROM tatus WHERE especie_id IS NULL"),
                         [("Misterioso",)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM tatus WHERE especie_id IN (1, 2)"), [(4,)])

    def test_order_by_com_nulls_desc_e_posicao(self):
        idades = [r[0] for r in self.rows("SELECT idade FROM tatus ORDER BY idade")]
        self.assertIsNone(idades[0])  # NULL vem primeiro no ASC
        idades = [r[0] for r in self.rows("SELECT idade FROM tatus ORDER BY 1 DESC")]
        self.assertEqual(idades[0], 7)
        self.assertIsNone(idades[-1])

    def test_order_by_coluna_que_nao_esta_no_select(self):
        self.assertEqual(self.rows("SELECT apelido FROM tatus ORDER BY idade DESC LIMIT 1"),
                         [("Canastrão",)])

    def test_limit_offset(self):
        self.assertEqual(self.rows("SELECT id FROM tatus ORDER BY id LIMIT 2 OFFSET 3"), [(4,), (5,)])

    def test_distinct(self):
        sql = "SELECT DISTINCT bioma FROM avistamentos WHERE bioma LIKE 'C%' ORDER BY bioma"
        self.assertEqual(self.rows(sql), [("Caatinga",), ("Cerrado",)])

    def test_funcoes(self):
        self.assertEqual(
            self.rows("SELECT UPPER('tatu'), LOWER('BOLA'), LENGTH('toca'), ABS(-3), "
                      "ROUND(2.567, 1), COALESCE(NULL, NULL, 'x'), TYPEOF(1), TRIM('  oi ')"),
            [("TATU", "bola", 4, 3, 2.6, "x", "INTEGER", "oi")])

    def test_parametros(self):
        self.assertEqual(self.rows("SELECT apelido FROM tatus WHERE id = ?", (6,)), [("Fuleco",)])
        # o parâmetro é um valor, nunca vira SQL: nada de SQL injection!
        self.assertEqual(self.rows("SELECT apelido FROM tatus WHERE apelido = ?", ("x' OR '1'='1",)), [])
        with self.assertRaises(ExecutionError):
            self.db.execute("SELECT ?", ())

    # ── NULL e lógica de três valores ──

    def test_logica_de_tres_valores(self):
        self.assertEqual(self.rows("SELECT NULL = NULL, NULL AND FALSE, NULL OR TRUE, NOT NULL, 1 + NULL"),
                         [(None, False, True, None, None)])
        self.assertEqual(self.rows("SELECT 5 IN (1, NULL), 1 IN (1, NULL), 5 NOT IN (1, 2)"),
                         [(None, True, True)])

    def test_where_com_null_nao_passa(self):
        self.assertEqual(self.rows("SELECT COUNT(*) FROM tatus WHERE idade > 0 OR idade <= 0"), [(8,)])

    # ── JOINs ──

    def test_inner_join(self):
        result = self.rows("""
            SELECT t.apelido, e.nome FROM tatus t
            JOIN especies e ON t.especie_id = e.id
            WHERE e.ameacada ORDER BY t.apelido""")
        self.assertEqual(result, [("Bolinha", "tatu-bola"), ("Canastrão", "tatu-canastra"),
                                  ("Fuleco", "tatu-bola")])

    def test_left_join_mantem_quem_nao_tem_par(self):
        result = self.rows("""
            SELECT t.apelido, e.nome FROM tatus t
            LEFT JOIN especies e ON t.especie_id = e.id
            WHERE e.id IS NULL""")
        self.assertEqual(result, [("Misterioso", None)])

    def test_join_de_tres_tabelas(self):
        result = self.rows("""
            SELECT e.nome, COUNT(*) AS total
            FROM avistamentos a
            JOIN tatus t ON a.tatu_id = t.id
            JOIN especies e ON t.especie_id = e.id
            GROUP BY e.nome ORDER BY total DESC, e.nome LIMIT 2""")
        self.assertEqual(result, [("tatu-bola", 3), ("tatu-galinha", 3)])

    def test_cross_join_com_virgula(self):
        self.assertEqual(self.rows("SELECT COUNT(*) FROM especies, tatus"), [(6 * 9,)])

    def test_coluna_ambigua(self):
        with self.assertRaises(CatalogError) as ctx:
            self.db.execute("SELECT id FROM tatus t JOIN especies e ON t.especie_id = e.id")
        self.assertIn("ambígua", str(ctx.exception))

    def test_mesma_tabela_duas_vezes_precisa_de_apelido(self):
        with self.assertRaises(CatalogError):
            self.db.execute("SELECT 1 FROM tatus JOIN tatus ON 1 = 1")
        self.assertEqual(self.rows("SELECT COUNT(*) FROM tatus a JOIN tatus b ON a.idade = b.idade "
                                   "WHERE a.id < b.id"), [(1,)])  # Bolinha e Zé Mulita, 3 anos

    # ── agregações ──

    def test_agregacoes_sem_group_by(self):
        self.assertEqual(
            self.rows("SELECT COUNT(*), COUNT(idade), SUM(idade), MIN(idade), MAX(apelido), AVG(idade) "
                      "FROM tatus"),
            [(9, 8, 31, 1, "Zé Mulita", 31 / 8)])

    def test_agregacao_em_tabela_vazia(self):
        self.db.execute("CREATE TABLE vazia (x INTEGER)")
        self.assertEqual(self.rows("SELECT COUNT(*), SUM(x), MAX(x) FROM vazia"), [(0, None, None)])
        self.assertEqual(self.rows("SELECT x, COUNT(*) FROM vazia GROUP BY x"), [])

    def test_group_by_having(self):
        self.assertEqual(
            self.rows("SELECT especie_id, COUNT(*) AS n FROM tatus "
                      "GROUP BY especie_id HAVING COUNT(*) >= 2 ORDER BY especie_id"),
            [(1, 2), (2, 2)])

    def test_count_distinct(self):
        self.assertEqual(self.rows("SELECT COUNT(DISTINCT bioma) FROM avistamentos"), [(6,)])

    def test_group_by_com_expressao(self):
        self.assertEqual(
            self.rows("SELECT idade % 2, COUNT(*) FROM tatus WHERE idade IS NOT NULL "
                      "GROUP BY idade % 2 ORDER BY 1"),
            [(0, 3), (1, 5)])

    def test_coluna_fora_do_group_by(self):
        with self.assertRaises(CatalogError) as ctx:
            self.db.execute("SELECT apelido, COUNT(*) FROM tatus")
        self.assertIn("GROUP BY", str(ctx.exception))

    def test_agregacao_no_where_e_proibida(self):
        with self.assertRaises(ExecutionError):
            self.db.execute("SELECT * FROM tatus WHERE COUNT(*) > 1")

    # ── erros de tipo ──

    def test_tipos_incompativeis(self):
        for sql in ["SELECT 'a' > 1", "SELECT 'a' + 1", "SELECT SUM(apelido) FROM tatus",
                    "SELECT UPPER(1)", "SELECT 1 LIKE 'a'"]:
            with self.subTest(sql=sql), self.assertRaises(TatuTypeError):
                self.db.execute(sql)

    def test_divisao_por_zero(self):
        with self.assertRaises(ExecutionError):
            self.db.execute("SELECT 1 / 0")

    # ── índices e EXPLAIN ──

    def test_explain_usa_indice_da_chave_primaria(self):
        plan = [r[0] for r in self.rows("EXPLAIN SELECT * FROM tatus WHERE id = 3")]
        self.assertIn("IndexScan", plan[-1])

    def test_explain_sem_indice_faz_varredura(self):
        plan = [r[0] for r in self.rows("EXPLAIN SELECT * FROM tatus WHERE idade = 3")]
        self.assertIn("SeqScan", plan[-1])
        self.assertTrue(any("Filter" in line for line in plan))

    def test_create_index_muda_o_plano_mas_nao_o_resultado(self):
        sql = "SELECT apelido FROM tatus WHERE idade = 3 ORDER BY apelido"
        before = self.rows(sql)
        self.db.execute("CREATE INDEX idx_idade ON tatus (idade)")
        plan = "\n".join(r[0] for r in self.rows("EXPLAIN " + sql))
        self.assertIn("IndexScan(tatus usando idx_idade", plan)
        self.assertEqual(self.rows(sql), before)

    def test_indice_com_tipo_errado_ainda_reclama(self):
        with self.assertRaises(TatuTypeError):
            self.db.execute("SELECT * FROM tatus WHERE id = 'um'")


if __name__ == "__main__":
    unittest.main()
