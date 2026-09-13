# -*- coding: utf-8 -*-
# @Time         : 14:40 2026/9/10
# @Author       : Chris
# @Description  : Test OQL chained SELECT expressions under model / field ACL.
#
# These tests exercise chain permission control ONLY through real queries
# (`model.oql(...)`), never through the bare ACL APIs; every case asserts either
# an `AccessError` or the exact rows the query returns.
#
# How a chain SELECT is gated:
#   * the `from` model needs read access -- `SelectStmt` adds a MODEL unit;
#   * each field a chain step navigates needs field read access: `Chain`
#     resolves the leading attribute steps into `StepField` units, which
#     `OqlReader._check_perms` verifies against `OqlAclField` (e.g. the
#     `attribute_value_ids` in `attribute_value_ids[0].name`);
#   * method steps (`mapped`, `read`, `lower`, ...) are executed with the ACL
#     degraded to Odoo's built-in checks (`util.degrade_acl`), because no static
#     verdict is possible for an arbitrary method call.
#
# The fixture (`OqlAclProductCase`) gives two active products, each carrying the
# attribute values `5`, `6`, `7` (Size) and `D`, `EE` (Width); the restricted
# user only holds `base.group_user`.
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .test_model_defs import post_test
from .test_acl_common import OqlAclProductCase


@tagged("oql_acl_chain", "-at_install", "post_install")
class TestOqlAclChain(OqlAclProductCase):
    """Chain SELECT expressions honour base-model / stepped-field read access."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _query(self, sql: str, env=None):
        """Run `sql` on the product model as the restricted user (`env`
        overrides the env, used only for the superuser sanity check)."""
        env = env if env is not None else self.user_env()
        return env["test.oql.product"].oql(sql)

    def _first_attr_name(self) -> str:
        """Name of the first attribute value of the cold product (admin)."""
        return self.prod_cold.attribute_value_ids[0].name

    def _all_attr_names(self) -> list:
        """Names of every attribute value of the cold product (admin)."""
        return list(self.prod_cold.attribute_value_ids.mapped("name"))

    # ------------------------------------------------------------------
    # Sanity: superuser runs chains with no ACL configuration
    # ------------------------------------------------------------------

    @post_test("acl_chain.sanity")
    def test_chain_superuser_sanity(self):
        """The superuser runs the index chain without any access configuration."""
        res = self._query(
            "from test.oql.product select attribute_value_ids[0].name as x "
            "where id = %d" % self.prod_cold.id, env=self.env)
        self.assertEqual([{"x": self._first_attr_name()}], res)

    # ------------------------------------------------------------------
    # Model-level read gate on the `from` model
    # ------------------------------------------------------------------

    @post_test("acl_chain.model")
    def test_chain_denied_without_model_read(self):
        """The `from` model read is a hard prerequisite: fields are readable
        here, yet dropping the model read rejects the chain query."""
        self.grant_model("test.oql.product", perm_read=False, default_read=True)
        with self.assertRaises(AccessError) as cm:
            self._query("from test.oql.product select attribute_value_ids[0].name as x")
        self.assertIn("MODEL", str(cm.exception))

    # ------------------------------------------------------------------
    # Field-level read gate on chain steps
    # ------------------------------------------------------------------

    @post_test("acl_chain.field")
    def test_chain_denied_when_step_field_denied(self):
        """`attribute_value_ids[0].name` is gated by the stepped field."""
        self.grant_model("test.oql.product", default_read=False)
        self.grant_model("test.oql.attribute.value", default_read=True)
        with self.assertRaises(AccessError) as cm:
            self._query(
                "from test.oql.product select attribute_value_ids[0].name as x "
                "where id = %d" % self.prod_cold.id)
        self.assertIn("attribute_value_ids", str(cm.exception))

    @post_test("acl_chain.field")
    def test_chain_allowed_when_step_field_granted(self):
        """Granting only the stepped field is enough for the index chain."""
        self.grant_model("test.oql.product", default_read=False)
        self.grant_field("test.oql.product", "attribute_value_ids", perm_read=True)
        self.grant_model("test.oql.attribute.value", default_read=True)
        res = self._query(
            "from test.oql.product select attribute_value_ids[0].name as x "
            "where id = %d" % self.prod_cold.id)
        self.assertEqual([{"x": self._first_attr_name()}], res)

    @post_test("acl_chain.field")
    def test_method_chain_denied_when_step_field_denied(self):
        """The method chain `attribute_value_ids.mapped('name')` is gated by
        the same stepped field as the index chain."""
        self.grant_model("test.oql.product", default_read=False)
        self.grant_model("test.oql.attribute.value", default_read=True)
        with self.assertRaises(AccessError):
            self._query(
                "from test.oql.product select attribute_value_ids.mapped('name') as names "
                "where id = %d" % self.prod_cold.id)

    @post_test("acl_chain.field")
    def test_method_chain_allowed_when_step_field_granted(self):
        """With the stepped field granted, the method chain runs and maps the
        related records (invoked under the user's own ACL)."""
        self.grant_model("test.oql.product", default_read=False)
        self.grant_field("test.oql.product", "attribute_value_ids", perm_read=True)
        # `mapped('name')` is executed on the related records out of sudo mode.
        self.grant_model("test.oql.attribute.value", default_read=True)
        res = self._query(
            "from test.oql.product select attribute_value_ids.mapped('name') as names "
            "where id = %d" % self.prod_cold.id)
        self.assertEqual([{"names": self._all_attr_names()}], res)

    # ------------------------------------------------------------------
    # Scalar method chain (`spu_name.lower()`)
    # ------------------------------------------------------------------

    @post_test("acl_chain.scalar")
    def test_scalar_method_chain_denied_when_field_denied(self):
        """A string method chain is gated by the field it is applied to."""
        self.grant_model("test.oql.product", default_read=False)
        with self.assertRaises(AccessError) as cm:
            self._query(
                "from test.oql.product select spu_name.lower() as low "
                "where id = %d" % self.prod_cold.id)
        self.assertIn("spu_name", str(cm.exception))

    @post_test("acl_chain.scalar")
    def test_scalar_method_chain_allowed_when_field_granted(self):
        """With the field granted, the string method runs with Python semantics."""
        self.grant_model("test.oql.product", default_read=False)
        self.grant_field("test.oql.product", "spu_name", perm_read=True)
        res = self._query(
            "from test.oql.product select spu_name.lower() as low "
            "where id = %d" % self.prod_cold.id)
        self.assertEqual([{"low": self.prod_cold.spu_name.lower()}], res)

    # ------------------------------------------------------------------
    # Every SELECT item is checked
    # ------------------------------------------------------------------

    @post_test("acl_chain.items")
    def test_chain_denies_when_any_item_field_denied(self):
        """One denied field among several chain items rejects the whole query."""
        self.grant_model("test.oql.product", default_read=False)
        self.grant_field("test.oql.product", "attribute_value_ids", perm_read=True)
        self.grant_model("test.oql.attribute.value", default_read=True)
        with self.assertRaises(AccessError) as cm:
            self._query(
                "from test.oql.product select attribute_value_ids[0].name as a, "
                "spu_name.lower() as b where id = %d" % self.prod_cold.id)
        self.assertIn("spu_name", str(cm.exception))

    # ------------------------------------------------------------------
    # Bound-call head chain (`.read([...])`)
    # ------------------------------------------------------------------

    @post_test("acl_chain.head_call")
    def test_head_call_chain_allowed_for_internal_user(self):
        """A public (non-underscore) head-call method is allowed for an internal
        user; the chain navigates on the per-record `read()` result."""
        self.grant_model("test.oql.product", default_read=False)
        res = self._query(
            "from test.oql.product select .read(['id'])[0].id as rid "
            "where id = %d" % self.prod_cold.id)
        self.assertEqual([{"rid": self.prod_cold.id}], res)

    # ------------------------------------------------------------------
    # Delegated relation-field chain (`tag_ids[0].name`)
    # ------------------------------------------------------------------

    @post_test("acl_chain.relation")
    def test_delegated_relation_chain_denied_when_step_field_denied(self):
        """`tag_ids[0].name` is gated by the delegated `tag_ids` field: the tag
        model itself is readable, yet dropping the field denies the chain."""
        self.grant_model("test.oql.product", default_read=False)
        self.grant_model("test.oql.tag", default_read=True)
        with self.assertRaises(AccessError) as cm:
            self._query(
                "from test.oql.product select tag_ids[0].name as x "
                "where id = %d" % self.prod_cold.id)
        self.assertIn("tag_ids", str(cm.exception))

    @post_test("acl_chain.relation")
    def test_delegated_relation_chain_allowed_when_step_field_granted(self):
        """Granting the delegated `tag_ids` field is enough for the index chain."""
        self.grant_model("test.oql.product", default_read=False)
        self.grant_field("test.oql.product", "tag_ids", perm_read=True)
        self.grant_model("test.oql.tag", default_read=True)
        res = self._query(
            "from test.oql.product select tag_ids[0].name as x "
            "where id = %d" % self.prod_cold.id)
        self.assertEqual([{"x": self.prod_cold.tag_ids[0].name}], res)
