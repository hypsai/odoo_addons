# -*- coding: utf-8 -*-
# @Time         : 10:30 2026/9/3
# @Author       : Chris
# @Description  : Test cases for the OQL `function` grammar (SELECT-only, e.g. `lower(name)`, `count() as cnt`).
from odoo.tests import tagged, TransactionCase

from ..field import FieldAccess
from ..func import FuncCall
from ..libs.lark.exceptions import UnexpectedToken
from ..oql import reader, OqlTransformer
from .test_model_defs import ensure_model_meta, ensure_model_access


@tagged("oql_func", "-at_install", "post_install")
class TestOqlFunc(TransactionCase):

    def setUp(self):
        super().setUp()
        env = self.env
        ensure_model_meta(env)
        ensure_model_access(env)
        self.product = env["test.oql.product"].create({"spu_name": "Func Boot"})
        env["test.oql.attribute.value"].create({
            "name": "5", "product_id": self.product.id})

    def _transform_clause(self, oql_str: str, start: str = "select_clause"):
        """Parse and transform `oql_str` with the given start rule, WITHOUT executing it."""
        transformer = OqlTransformer(self.env)
        transformer.init_model("test.oql.product", "read")
        return reader.parse(oql_str, transformer, start=start)

    # ------------------------------------------------------------------
    # Structure.
    # ------------------------------------------------------------------

    def test_func_in_select_structure(self):
        """`lower(x) as alias` becomes a `FuncCall` in the select clause."""
        clause = self._transform_clause("select lower(spu_name) as low")
        fas = clause.fas
        self.assertEqual(1, len(fas))
        func = fas[0]
        self.assertIsInstance(func, FuncCall)
        self.assertEqual("lower", func.name)
        self.assertEqual("low", func.as_)
        self.assertFalse(func.is_agg)  # `lower` is registered as non-aggregate.
        self.assertEqual(1, len(func.args))
        self.assertIsInstance(func.args[0], FieldAccess)
        self.assertEqual("spu_name", func.args[0].path)
        self.assertFalse(func.args[0].is_agg)

    def test_func_mixed_with_plain_fields(self):
        """Functions mix with plain fields; alias defaults to the function name."""
        clause = self._transform_clause("select spu_name, lower(spu_name) as low")
        fas = clause.fas
        self.assertEqual(2, len(fas))
        self.assertIsInstance(fas[0], FieldAccess)
        self.assertEqual("spu_name", fas[0].path)
        self.assertIsInstance(fas[1], FuncCall)
        self.assertEqual("low", fas[1].as_)

    def test_func_nested_and_empty_args(self):
        """Nested calls and the `count(*)` / `count()` equivalence."""
        clause = self._transform_clause("select lower(lower(spu_name))")
        func = clause.fas[0]
        self.assertIsInstance(func.args[0], FuncCall)
        self.assertEqual("lower", func.args[0].name)

        for oql_str in ("select count(*)", "select count()"):
            clause = self._transform_clause(oql_str)
            self.assertEqual([], clause.fas[0].args)  # `*` is filtered from the tree.

    def test_func_args_mix_values_and_fields(self):
        """Args can be fields, literals, sets and booleans."""
        clause = self._transform_clause("select f(attribute_value_ids, 1, 'x', (1, 2), true)")
        func = clause.fas[0]
        self.assertIsInstance(func.args[0], FieldAccess)
        self.assertEqual("attribute_value_ids", func.args[0].path)
        self.assertEqual(1, func.args[1])
        self.assertEqual("x", func.args[2])
        self.assertEqual((1, 2), func.args[3])
        self.assertIs(True, func.args[4])

    def test_func_agg_mark(self):
        """`@` marks aggregate functions and field args: `count(@x)`."""
        clause = self._transform_clause("select count(@attribute_value_ids) as cnt")
        func = clause.fas[0]
        self.assertIsInstance(func, FuncCall)
        self.assertTrue(func.is_agg)  # `count` is registered as aggregate.
        self.assertTrue(func.args[0].is_agg)
        self.assertEqual("cnt", func.as_)

    def test_func_agg_mismatch(self):
        """Aggregate functions reject non-aggregate (`@`-less) field args."""
        with self.assertRaisesRegex(Exception, "can't be called on"):
            self._transform_clause("select count(attribute_value_ids) as cnt")

    # ------------------------------------------------------------------
    # Evaluation.
    # ------------------------------------------------------------------

    def test_func_read_dispatch(self):
        """SELECT functions dispatch to registered globals: `lower` / `count`."""
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select lower(spu_name) as low where spu_name = 'Func Boot'")
        self.assertEqual(1, len(res))
        self.assertEqual("func boot", res[0]["low"])

        res = self.env["test.oql.product"].oql(
            "from test.oql.product select count() as cnt where spu_name = 'Func Boot'")
        self.assertEqual(1, len(res))
        self.assertEqual(1, res[0]["cnt"])  # `count()` counts the filtered records.

    def test_func_read_method(self):
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select read(['id']) as read where spu_name = 'Func Boot'")
        self.assertIsInstance(res[0]["read"], list)

    def test_func_read_unregistered(self):
        """Unregistered functions fail explicitly in `FuncCall.read`."""
        with self.assertRaisesRegex(NotImplementedError, "nonexistent_func"):
            self.env["test.oql.product"].oql(
                "from test.oql.product select nonexistent_func(spu_name) as x")

    # ------------------------------------------------------------------
    # Parsing only.
    # ------------------------------------------------------------------

    def test_func_parse_variants(self):
        """Functions parse in the SELECT field list, with all arg forms."""
        for oql_str in (
            "select lower(spu_name) as low",
            "select lower(lower(spu_name))",
            "select count(attribute_value_ids,) as cnt",  # Trailing comma.
            "select f(attribute_value_ids, 1, 'x', (1, 2), true)",
            "select count(@attribute_value_ids) as cnt",
            "select @count(attribute_value_ids)",  # Parses; agg-consistency is checked at transform.
        ):
            reader.parser.parse(oql_str, "select_clause")

    def test_func_negative_parse(self):
        """Per the grammar, functions are SELECT-only: not in WHERE / ORDER BY / values."""
        for oql_str in (
            "from test.oql.product select id where lower(spu_name)",        # In WHERE.
            "from test.oql.product select id where spu_name = lower('x')",  # As value.
            "from test.oql.product select id order by lower(spu_name)",     # In order by.
            "from test.oql.product select id where lower(spu_name = 'x')",  # Unbalanced.
        ):
            with self.assertRaises(UnexpectedToken):
                reader.parser.parse(oql_str, "start")

    def test_plain_select_regression(self):
        """Functions don't disturb plain queries."""
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select spu_name where spu_name = 'Func Boot'")
        self.assertEqual(1, len(res))
        self.assertEqual("Func Boot", res[0]["spu_name"])
