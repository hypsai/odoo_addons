# -*- coding: utf-8 -*-
# @Description  : Test cases for OQL chained SELECT expressions, e.g.
#   `attribute_value_ids[0].name`, `attribute_value_ids.mapped('name')`, `.read(['id'])[0].id`.
from odoo.tests import tagged, TransactionCase

from ..chain import Chain, StepAttr, StepCall, StepIndex
from ..field import FieldAccess
from ..libs.lark.exceptions import UnexpectedToken
from ..oql import reader, OqlTransformer
from .test_model_defs import ensure_model_meta, ensure_model_access


@tagged("oql_chain", "-at_install", "post_install")
class TestOqlChain(TransactionCase):

    def setUp(self):
        super().setUp()
        env = self.env
        ensure_model_meta(env)
        ensure_model_access(env)
        self.p_red_blue = env["test.oql.product"].create({"spu_name": "Cold Boot"})
        self.p_green = env["test.oql.product"].create({"spu_name": "Hot Boot"})
        self.p_empty = env["test.oql.product"].create({"spu_name": "Empty Boot"})
        self.p_pad = env["test.oql.product"].create({"spu_name": "  Pad Boot  "})
        for name in ("Red", "Blue"):
            env["test.oql.attribute.value"].create({
                "name": name, "product_id": self.p_red_blue.id})
        env["test.oql.attribute.value"].create({
            "name": "Green", "product_id": self.p_green.id})

    # ------------------------------------------------------------------
    # Helpers.
    # ------------------------------------------------------------------

    def _transform_clause(self, oql_str: str, start: str = "select_clause"):
        """Parse + transform `oql_str` with the given start rule, without executing."""
        transformer = OqlTransformer(self.env)
        transformer.init_model("test.oql.product", "read")
        return reader.parse(oql_str, transformer, start=start)

    def _query(self, sql: str) -> list:
        return self.env["test.oql.product"].oql(sql)

    # ------------------------------------------------------------------
    # Structure (transform only).
    # ------------------------------------------------------------------

    def test_struct_index_chain(self):
        """`attribute_value_ids[0].name` folds to a `Chain`; default alias = its text."""
        clause = self._transform_clause("select attribute_value_ids[0].name")
        chain = clause.fas[0]
        self.assertIsInstance(chain, Chain)
        self.assertEqual(3, len(chain.steps))
        self.assertIsInstance(chain.steps[0], StepAttr)
        self.assertEqual("attribute_value_ids", chain.steps[0].name)
        self.assertIsInstance(chain.steps[1], StepIndex)
        self.assertEqual(0, chain.steps[1].index)
        self.assertIsInstance(chain.steps[2], StepAttr)
        self.assertEqual("name", chain.steps[2].name)
        self.assertEqual("attribute_value_ids[0].name", chain.text)
        self.assertEqual(chain.text, chain.as_)
        self.assertEqual(chain.text, chain.path)
        self.assertFalse(chain.is_agg)

        clause = self._transform_clause("select attribute_value_ids[0].name as first_val")
        self.assertEqual("first_val", clause.fas[0].as_)

    def test_struct_method_chain(self):
        """A method call carries its name and literal args in one `StepCall`."""
        clause = self._transform_clause("select attribute_value_ids.mapped('name') as names")
        chain = clause.fas[0]
        self.assertIsInstance(chain, Chain)
        self.assertEqual(2, len(chain.steps))
        self.assertIsInstance(chain.steps[0], StepAttr)
        self.assertEqual("attribute_value_ids", chain.steps[0].name)
        self.assertIsInstance(chain.steps[1], StepCall)
        self.assertEqual("mapped", chain.steps[1].name)
        self.assertEqual(("name",), chain.steps[1].args)

    def test_struct_head_chain(self):
        """`.read(['id'])[0].id` folds the dotted bound-call head into a `StepCall`."""
        clause = self._transform_clause("select .read(['id'])[0].id")
        chain = clause.fas[0]
        self.assertIsInstance(chain, Chain)
        head = chain.steps[0]
        self.assertIsInstance(head, StepCall)
        self.assertEqual("read", head.name)
        self.assertEqual((['id'],), head.args)
        self.assertFalse(head.is_agg)
        self.assertEqual(2, len(chain.steps[1:]))
        self.assertIsInstance(chain.steps[1], StepIndex)
        self.assertEqual(0, chain.steps[1].index)
        self.assertIsInstance(chain.steps[2], StepAttr)
        self.assertEqual("id", chain.steps[2].name)
        self.assertEqual("read(...)[0].id", chain.text)

    def test_struct_pure_dotted_stays_field(self):
        """A pure attribute chain never becomes a `Chain` (kept as `FieldAccess`)."""
        clause = self._transform_clause("select attribute_value_ids.name")
        self.assertIsInstance(clause.fas[0], FieldAccess)

    def test_struct_head_only_call_is_chain(self):
        """A bound-call head without further steps is a single-step `Chain`."""
        clause = self._transform_clause("select .read(['id']) as x")
        chain = clause.fas[0]
        self.assertIsInstance(chain, Chain)
        self.assertEqual(1, len(chain.steps))
        self.assertIsInstance(chain.steps[0], StepCall)
        self.assertFalse(chain.is_agg)

    def test_struct_agg_step_mark(self):
        """`@` marks a step aggregate; the chain still continues after it."""
        clause = self._transform_clause("select @attribute_value_ids.mapped('name') as x")
        chain = clause.fas[0]
        self.assertIsInstance(chain, Chain)
        self.assertTrue(chain.steps[0].is_agg)
        self.assertIsInstance(chain.steps[1], StepCall)

    def test_struct_agg_mark_on_step(self):
        """`@` attaches to a single step, not to the whole chain."""
        clause = self._transform_clause("select @attribute_value_ids[0].name as x")
        chain = clause.fas[0]
        self.assertIsInstance(chain, Chain)
        self.assertTrue(chain.steps[0].is_agg)
        self.assertIsInstance(chain.steps[1], StepIndex)
        self.assertIsInstance(chain.steps[2], StepAttr)
        self.assertFalse(chain.steps[2].is_agg)

    # ------------------------------------------------------------------
    # Evaluation.
    # ------------------------------------------------------------------

    def test_eval_index_first_child(self):
        """`[0]` selects the first row of each record's x2m set."""
        res = self._query(
            f"from test.oql.product select attribute_value_ids[0].name "
            f"where id = {self.p_red_blue.id}")
        self.assertEqual(1, len(res))
        self.assertEqual("Red", res[0]["attribute_value_ids[0].name"])  # default alias.

        res = self._query(
            f"from test.oql.product select attribute_value_ids[0].name as first_val "
            f"where id = {self.p_green.id}")
        self.assertEqual("Green", res[0]["first_val"])

    def test_eval_index_rows_aligned(self):
        """Chains are evaluated per row and stay aligned with the WHERE result."""
        res = self._query(
            f"from test.oql.product select id as pid, attribute_value_ids[0].name as first_val "
            f"where id in ({self.p_red_blue.id}, {self.p_green.id}) order by id")
        self.assertEqual(2, len(res))
        self.assertEqual(self.p_red_blue.id, res[0]["pid"])
        self.assertEqual("Red", res[0]["first_val"])
        self.assertEqual(self.p_green.id, res[1]["pid"])
        self.assertEqual("Green", res[1]["first_val"])

    def test_eval_index_second_child(self):
        """`[1]` indexes the second row of the x2m set."""
        res = self._query(
            f"from test.oql.product select attribute_value_ids[1].name as second_val "
            f"where id = {self.p_red_blue.id}")
        self.assertEqual("Blue", res[0]["second_val"])

    def test_eval_method_mapped(self):
        """`mapped('name')` runs the ORM method on each record's x2m set."""
        res = self._query(
            f"from test.oql.product select attribute_value_ids.mapped('name') as names "
            f"where id = {self.p_red_blue.id}")
        self.assertEqual(["Red", "Blue"], res[0]["names"])

    def test_eval_scalar_methods(self):
        """String methods run with real Python semantics on the previous value."""
        res = self._query(
            f"from test.oql.product select spu_name.lower() as low, "
            f"spu_name.lower().replace('boot', 'sock') as replaced "
            f"where id = {self.p_red_blue.id}")
        self.assertEqual("cold boot", res[0]["low"])
        self.assertEqual("cold sock", res[0]["replaced"])

        res = self._query(
            f"from test.oql.product select spu_name.lower().strip() as s "
            f"where id = {self.p_pad.id}")
        self.assertEqual("pad boot", res[0]["s"])

    def test_eval_empty_x2m(self):
        """An empty x2m still runs its bound method (returns `[]`), like Python."""
        res = self._query(
            f"from test.oql.product select attribute_value_ids.mapped('name') as names "
            f"where id = {self.p_empty.id}")
        self.assertEqual([], res[0]["names"])

    def test_eval_head_call_chain(self):
        """`.read([...])[0].field` chains on the per-record bound-call result."""
        res = self._query(
            f"from test.oql.product select .read(['id'])[0].id as rid, "
            f".read(['id', 'spu_name'])[0].spu_name as sn "
            f"where id = {self.p_red_blue.id}")
        self.assertEqual(self.p_red_blue.id, res[0]["rid"])
        self.assertEqual("Cold Boot", res[0]["sn"])

    def test_eval_empty_where(self):
        """A chain select over zero matching records yields no rows, no error."""
        res = self._query(
            "from test.oql.product select attribute_value_ids[0].name "
            "where id = -1")
        self.assertEqual([], res)

    # ------------------------------------------------------------------
    # Errors.
    # ------------------------------------------------------------------

    def test_error_index_out_of_range(self):
        """Indexing a plain (list) value out of range fails with a chain-aware message."""
        sql = (f"from test.oql.product select attribute_value_ids.mapped('name')[1] as x "
               f"where id = {self.p_green.id}")
        with self.assertRaises(Exception) as cm:
            self._query(sql)
        self.assertIn("can't index", str(cm.exception))

    def test_error_index_empty_set(self):
        """Indexing an empty (list) value fails with a chain-aware message."""
        sql = (f"from test.oql.product select attribute_value_ids.mapped('name')[0] as x "
               f"where id = {self.p_empty.id}")
        with self.assertRaises(Exception) as cm:
            self._query(sql)
        self.assertIn("can't index", str(cm.exception))

    def test_error_missing_attr_after_method(self):
        """A missing attribute on the previous value names the chain in the error."""
        sql = (f"from test.oql.product select attribute_value_ids.mapped('name').length as x "
               f"where id = {self.p_green.id}")
        with self.assertRaises(Exception) as cm:
            self._query(sql)
        self.assertIn("has no attribute `length`", str(cm.exception))

    # ------------------------------------------------------------------
    # Parsing only.
    # ------------------------------------------------------------------

    def test_parse_variants(self):
        """Chained select items parse with any step ordering / alias."""
        for oql_str in (
            "select attribute_value_ids[0].name as first",
            "select attribute_value_ids[0].name.lower() as low",
            "select attribute_value_ids.mapped('name') as names",
            "select spu_name.lower().replace('boot', 'sock')",
            "select .read(['id'])[0].id as rid",
        ):
            reader.parser.parse(oql_str, "select_clause")

    def test_negative_parse(self):
        """Chains are SELECT-only, not accepted in WHERE / ORDER BY."""
        for oql_str in (
            "from test.oql.product select id where attribute_value_ids[0].name = 'Red'",
            "from test.oql.product select id order by attribute_value_ids[0].name",
        ):
            with self.assertRaises(UnexpectedToken):
                reader.parser.parse(oql_str, "start")
