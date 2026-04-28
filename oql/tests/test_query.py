from odoo.tests import tagged, TransactionCase
from ..oql import reader, OqlTransformer
from .test_model_defs import ensure_model_meta


@tagged("oql", '-at_install', 'post_install')
class TestOql(TransactionCase):

    def setUp(self):
        super().setUp()
        env = self.env

        # Load model meta.
        ensure_model_meta(env, ['test.oql.a', 'test.oql.b', 'test.oql.c'])
        metaA = env["ir.model"].search([("model", "=", "test.oql.a")], limit=1)
        metaB = env["ir.model"].search([("model", "=", "test.oql.b")], limit=1)
        metaC = env["ir.model"].search([("model", "=", "test.oql.c")], limit=1)

        # Terms
        term1 = env["oql.term"].create({"name": "Size"})
        term2 = env["oql.term"].create({"name": "ItemA"})
        env["oql.term.domain"].create({"name": "domain1", "term_id": term2.id, "model_id": metaA.id, "domain": "[]"})

        # Path rules.
        rule1 = env["oql.alias"].create({"model_id": metaA.id})
        line1 = env["oql.alias.line"].create({"alias": "attr", "rule_id": rule1.id, "path": "attr_value_ids", 'enable_shorthand': True})
        line2 = env["oql.alias.line"].create({"alias": "bs", "rule_id": rule1.id, "path": "b_ids", 'enable_shorthand': True})
        line3 = env["oql.alias.line"].create({"alias": "c", "rule_id": rule1.id, "path": "b_ids.c_ids", 'enable_shorthand': False})

        # a.b.c
        c1 = env["test.oql.c"].create({"name": "c1", "age": 22, "gender": "male", "height": 175, "enrolled": False})
        c2 = env["test.oql.c"].create({"name": "c2", "age": 18, "gender": "female", "height": 155, "enrolled": True})
        c3 = env["test.oql.c"].create({"name": "c3", "age": 20, "gender": "female", "height": 160, "enrolled": True})

        a1 = env["test.oql.a"].create({"name": "a1", "attr_value_ids": [c1.id, c2.id]})
        a2 = env["test.oql.a"].create({"name": "a2", "attr_value_ids": [c2.id]})

        b1 = env["test.oql.b"].create({"name": "b1", "a_id": a1.id, "c_ids": [c1.id, c2.id], "term_ids": [term1.id]})

    def tearDown(self):
        super().tearDown()

    def test_grammar_parse(self):
        parsed = reader.query("b_ids.c_ids.name = 'c1'", self._get_transformer())
        print("Hello Odoo tests")

    def test_search(self):
        res = reader.query("b_ids.c_ids.name='c1' or b_ids.c_ids.name='c2'", self._get_transformer())
        print(res)

    def test_searcho(self):
        res = self.env["test.oql.a"].searcho("b_ids.c_ids.name='c1' or b_ids.c_ids.name='c2'")
        self.assertEqual({"a1"}, set(res.mapped("name")))
        print(res)

    def test_searcho_term(self):
        res = self.env["test.oql.a"].searcho("Size='c1'")
        self.assertEqual({"a1"}, set(res.mapped("name")))
        res = self.env["test.oql.a"].searcho("Size='c2'")
        self.assertEqual({"a1", "a2"}, set(res.mapped("name")))
        print(res)

    def test_searcho_logic(self):
        res = self.env["test.oql.c"].searcho("age >= 18 and gender='female' and height > 150")
        self.assertEqual({"c2", "c3"}, set(res.mapped("name")))
        res = self.env["test.oql.c"].searcho("age >= 20 and gender='female' or age >= 22 and gender='male'")
        self.assertEqual({"c1", "c3"}, set(res.mapped("name")))
        print(res.mapped("name"))

    def test_searcho_una_expr(self):
        res = self.env["test.oql.c"].searcho("enrolled")
        self.assertEqual({"c2", "c3"}, set(res.mapped("name")))
        res = self.env["test.oql.a"].searcho("b_ids")
        self.assertEqual({"a1"}, set(res.mapped("name")))

    def test_searcho_has_term(self):
        res = self.env["test.oql.a"].searcho("Size")
        self.assertEqual({"a1"}, set(res.mapped("name")))

    def test_searcho_term_in(self):
        res = self.env["test.oql.a"].searcho("Size in ('c1')")
        self.assertEqual({"a1"}, set(res.mapped("name")))

    def test_searcho_parenthesis(self):
        res = self.env["test.oql.c"].searcho("(age > 20 or height < 160)")
        self.assertEqual({"c1", "c2"}, set(res.mapped("name")))

    def test_searcho_alias(self):
        res = self.env["test.oql.a"].searcho("c='c1'")
        self.assertEqual({"a1"}, set(res.mapped("name")))

    def assertHints(self, expected, actual):
        self.assertEqual(expected, {x["value"] for x in actual})

    def _get_transformer(self):
        return OqlTransformer(self.env, "test.oql.a")
