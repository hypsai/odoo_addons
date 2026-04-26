from odoo.tests import tagged, TransactionCase
from odoo import fields, models
from ..oql import reader, OqlTransformer


class A(models.Model):
    _name = 'test.a'

    name = fields.Char()
    b_ids = fields.One2many("test.b", "a_id")
    attr_value_ids = fields.Many2many("test.c")


class B(models.Model):
    _name = "test.b"

    name = fields.Char()
    a_id = fields.Many2one("test.a")
    c_ids = fields.Many2many("test.c")
    term_ids = fields.Many2many("oql.term")

    def __oql_bin__(self, term, opr, value, value_term):
        if term.domain == "self.term_ids":
            return self.c_ids.search([("id", "in", self.c_ids.ids), ("name", opr, value)])
        raise NotImplementedError()

    def __oql_hnt__(self, opr: str):
        if opr == "?":
            return self.c_ids
        else:
            return self.c_ids.mapped("name")


class C(models.Model):
    _name = "test.c"

    name = fields.Char()
    age = fields.Integer()
    gender = fields.Selection([("male", "男"), ("female", "女")])
    height = fields.Float()
    enrolled = fields.Boolean()


@tagged("oql")
class TestOql(TransactionCase):

    def setUp(self):
        super().setUp()
        env = self.env
        # 在注册表中注册临时模型
        for Model in [A, B, C]:
            model_name = Model._name
            self.registry.models[model_name] = Model._build_model(
                self.registry, self.cr
            )
            self.registry.setup_models(self.cr)
            self.registry.init_models(
                self.cr, [model_name], {"module": "test"}, install=True
            )
        # Model meta.
        metaA = env["ir.model"].search([("model", "=", "test.a")])
        metaB = env["ir.model"].search([("model", "=", "test.b")])
        metaC = env["ir.model"].search([("model", "=", "test.c")])

        # Terms
        term1 = env["oql.term"].create({"name": "Size"})
        term2 = env["oql.term"].create({"name": "ItemA"})
        env["oql.term.domain"].create({"name": "domain1", "term_id": term2.id, "model_id": metaA.id, "domain": "[]"})

        # Path rules.
        rule1 = env["oql.alias"].create({"model_id": metaA.id})
        line1 = env["oql.alias.line"].create({"alias": "attr", "rule_id": rule1.id, "value_model_id": metaC.id, "path": "attr_value_ids"})
        line2 = env["oql.alias.line"].create({"alias": "bs", "rule_id": rule1.id, "value_model_id": metaB.id, "path": "b_ids"})
        line3 = env["oql.alias.line"].create({"alias": "c", "rule_id": rule1.id, "path": "b_ids.c_ids"})

        # a.b.c
        c1 = env["test.c"].create({"name": "c1", "age": 22, "gender": "male", "height": 175, "enrolled": False})
        c2 = env["test.c"].create({"name": "c2", "age": 18, "gender": "female", "height": 155, "enrolled": True})
        c3 = env["test.c"].create({"name": "c3", "age": 20, "gender": "female", "height": 160, "enrolled": True})

        a1 = env["test.a"].create({"name": "a1", "attr_value_ids": [c1.id, c2.id]})
        a2 = env["test.a"].create({"name": "a2", "attr_value_ids": [c2.id]})

        b1 = env["test.b"].create({"name": "b1", "a_id": a1.id, "c_ids": [c1.id, c2.id], "term_ids": [term1.id]})

    def tearDown(self):
        super().tearDown()

    def _test_grammar_parse(self):
        parsed = reader.query("b.c.name='c1'", self._get_transformer())
        print("Hello Odoo tests")

    def _test_search(self):
        res = reader.query("b_ids.c_ids.name='c1' or b_ids.c_ids.name='c2'", self._get_transformer())
        print(res)

    def _test_searcho(self):
        res = self.env["test.a"].searcho("b_ids.c_ids.name='c1' or b_ids.c_ids.name='c2'")
        self.assertEqual({"a1"}, set(res.mapped("name")))
        print(res)

    def _test_searcho_term(self):
        res = self.env["test.a"].searcho("Size='c1'")
        self.assertEqual({"a1"}, set(res.mapped("name")))
        res = self.env["test.a"].searcho("Size='c2'")
        self.assertEqual({"a1", "a2"}, set(res.mapped("name")))
        print(res)

    def _test_searcho_logic(self):
        res = self.env["test.c"].searcho("age >= 18 and gender='female' and height > 150")
        self.assertEqual({"c2", "c3"}, set(res.mapped("name")))
        res = self.env["test.c"].searcho("age >= 20 and gender='female' or age >= 22 and gender='male'")
        self.assertEqual({"c1", "c3"}, set(res.mapped("name")))
        print(res.mapped("name"))

    def _test_searcho_una_expr(self):
        res = self.env["test.c"].searcho("enrolled")
        self.assertEqual({"c2", "c3"}, set(res.mapped("name")))
        res = self.env["test.a"].searcho("b_ids")
        self.assertEqual({"a1"}, set(res.mapped("name")))

    def _test_searcho_has_term(self):
        res = self.env["test.a"].searcho("Size")
        self.assertEqual({"a1"}, set(res.mapped("name")))

    def _test_searcho_term_in(self):
        res = self.env["test.a"].searcho("Size in ('c1')")
        self.assertEqual({"a1"}, set(res.mapped("name")))

    def _test_searcho_parenthesis(self):
        res = self.env["test.c"].searcho("(age > 20 or height < 160)")
        self.assertEqual({"c1", "c2"}, set(res.mapped("name")))

    def _test_searcho_alias(self):
        res = self.env["test.a"].searcho("c='c1'")
        self.assertEqual({"a1"}, set(res.mapped("name")))

    def assertHints(self, expected, actual):
        self.assertEqual(expected, {x["value"] for x in actual})

    def _get_transformer(self):
        return OqlTransformer(self.env, "test.a")
