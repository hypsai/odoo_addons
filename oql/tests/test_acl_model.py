# -*- coding: utf-8 -*-
# @Time         : 14:16 2026/9/8
# @Author       : Chris
# @Description  : Test OQL model-level ACL on `test.oql.product`.
#
# Model-level ACL means the permission verdicts derived straight from
# `ir.model.access`:
#   * basic ACL initialization / access on a model;
#   * model read vs. write granted through an `ir.model.access` row;
#   * DML statements (INSERT/UPDATE/DELETE) gated by the model-level
#     create / write / unlink permissions, plus the field-level write gate on
#     the target column (oql default).
# The former TestOqlRecordRule DML tests that do NOT involve any `ir.rule`
# record rule live here too (they only exercise model-level access).
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .test_model_defs import post_test
from .test_acl_common import OqlAclProductCase


@tagged("oql_acl", "-at_install", 'post_install')
class TestOqlAclModel(OqlAclProductCase):
    """Model-level ACL: access rows decide model read/write/create/unlink."""

    # ------------------------------------------------------------------
    # Basic ACL initialization & model access
    # ------------------------------------------------------------------

    @post_test("acl.basic")
    def test_acl_initialization(self):
        """Test basic ACL initialization and model access."""
        acl = self.acl()
        self.assertIsNotNone(acl)

        # Test that we can get model ACL
        product_acl = acl["test.oql.product"]
        self.assertIsNotNone(product_acl)
        self.assertEqual(product_acl.model_name, "test.oql.product")

    @post_test("acl.temp_access")
    def test_create_temp_model_access(self):
        """Test creating temporary ir.model.access records for testing."""
        env = self.env

        # Create a temporary model access record
        temp_access = env["ir.model.access"].create({
            'name': 'Temporary Test Access',
            'model_id': self.metaProduct.id,
            'perm_read': True,
            'perm_write': True,
            'perm_create': False,
            'perm_unlink': False,
            'perm_oql_fac_default_read': True,
            'perm_oql_fac_default_write': False,
        })

        self.assertIsNotNone(temp_access)
        self.assertEqual(temp_access.model_id, self.metaProduct)
        self.assertTrue(temp_access.perm_read)
        self.assertTrue(temp_access.perm_oql_fac_default_read)
        self.assertFalse(temp_access.perm_oql_fac_default_write)

    @post_test("acl.with_user")
    def test_acl_with_regular_user(self):
        """Test ACL with a regular (non-sudo) user to verify actual permission
        enforcement: a read-only `ir.model.access` row grants the model's
        fields on the read side while nothing is writable."""
        env = self.env

        # Create access record granting read but not write.
        temp_access = env["ir.model.access"].create({
            'name': 'Test User Product Access',
            'model_id': self.metaProduct.id,
            'group_id': self.user_group.id,
            'perm_read': True,
            'perm_write': False,
            'perm_create': False,
            'perm_unlink': False,
            'perm_oql_fac_default_read': True,
            'perm_oql_fac_default_write': False,
        })
        self.assertTrue(temp_access.exists())

        # Switch to test user context
        user_env = self.user_env()
        acl = self.acl(user_env)

        # Check that the user has read but not write access
        product_acl = acl["test.oql.product"]
        readable_fields = product_acl.perm_fields("read")
        writable_fields = product_acl.perm_fields("write")

        # Should have read access to fields
        self.assertIn("name", readable_fields)
        self.assertIn("id", readable_fields)

        # Should NOT have write access (perm_write=False and default_write=False)
        self.assertNotIn("name", writable_fields)

    # ------------------------------------------------------------------
    # ACL for UPDATE / CREATE / DELETE statements
    # ------------------------------------------------------------------

    @post_test("acl.crud.model")
    def test_acl_update_no_write_access(self):
        """UPDATE should raise AccessError when user lacks model-level write access."""
        # Grant read only.
        self.grant_model("test.oql.product", perm_read=True, perm_write=False)
        user_env = self.user_env()
        with self.assertRaises(AccessError):
            user_env["test.oql.product"].oql(
                f"update test.oql.product set spu_name = 'X' where id = {self.prod_cold.id}"
            )

    @post_test("acl.crud.model")
    def test_acl_update_with_write_access(self):
        """UPDATE should succeed when user has model-level write access."""
        self.grant_model("test.oql.product", perm_read=True, perm_write=True,
                         default_write=True)
        # `spu_name` is a related field pointing at `test.oql.template.name`;
        # writing it triggers `_inverse_related` which writes the template.
        self.grant_model("test.oql.template", perm_read=True, perm_write=True,
                         default_write=True)
        user_env = self.user_env()
        res = user_env["test.oql.product"].oql(
            f"update test.oql.product set spu_name = 'Updated' where id = {self.prod_cold.id}"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(self.prod_cold.spu_name, 'Updated')

    @post_test("acl.crud.model")
    def test_acl_create_no_create_access(self):
        """CREATE should raise AccessError when user lacks model-level create access."""
        self.grant_model("test.oql.product", perm_read=True, perm_create=False)
        user_env = self.user_env()
        with self.assertRaises(AccessError):
            user_env["test.oql.product"].oql(
                "insert into test.oql.product (spu_name) values ('New')"
            )

    @post_test("acl.crud.model")
    def test_acl_create_with_create_access(self):
        """CREATE should succeed when user has model-level create access.

        Note: CREATE also requires model-level write access because OQL's
        field-level ACL ties field write permission to model-level write.
        """
        self.grant_model("test.oql.product", perm_read=True, perm_write=True,
                         perm_create=True, default_write=True)
        # `spu_name` delegates to `test.oql.template.name`, so creating a
        # product also creates (and writes) the underlying template record.
        self.grant_model("test.oql.template", perm_read=True, perm_write=True,
                         perm_create=True, default_write=True)
        user_env = self.user_env()
        res = user_env["test.oql.product"].oql(
            "insert into test.oql.product (spu_name) values ('Created')"
        )
        self.assertEqual(len(res), 1)

    @post_test("acl.crud.model")
    def test_acl_delete_no_unlink_access(self):
        """DELETE should raise AccessError when user lacks model-level unlink access."""
        self.grant_model("test.oql.product", perm_read=True, perm_unlink=False)
        user_env = self.user_env()
        with self.assertRaises(AccessError):
            user_env["test.oql.product"].oql(
                f"delete from test.oql.product where id = {self.prod_cold.id}"
            )

    @post_test("acl.crud.model")
    def test_acl_delete_with_unlink_access(self):
        """DELETE should succeed when user has model-level unlink access."""
        self.grant_model("test.oql.product", perm_read=True, perm_unlink=True)
        user_env = self.user_env()
        res = user_env["test.oql.product"].oql(
            f"delete from test.oql.product where id = {self.prod_cold.id}"
        )
        self.assertEqual(len(res), 1)
        self.assertFalse(self.prod_cold.exists())

    @post_test("acl.crud.field")
    def test_acl_update_field_no_write_access(self):
        """UPDATE should raise AccessError when user lacks field-level write access."""
        # Grant model write but deny field-level write by default.
        self.grant_model("test.oql.product", perm_read=True, perm_write=True,
                         default_write=False)
        user_env = self.user_env()
        with self.assertRaises(AccessError):
            user_env["test.oql.product"].oql(
                f"update test.oql.product set spu_name = 'X' where id = {self.prod_cold.id}"
            )

    @post_test("acl.crud.field")
    def test_acl_update_field_with_write_access(self):
        """UPDATE should succeed when user has field-level write access on the
        target field."""
        self.grant_model("test.oql.product", perm_read=True, perm_write=True,
                         default_write=False)
        # `spu_name` is related to `test.oql.template.name`, so the template
        # model must also be writable for `_inverse_related` to succeed.
        self.grant_model("test.oql.template", perm_read=True, perm_write=True,
                         default_write=True)
        # Grant write access to spu_name field only.
        self.grant_field("test.oql.product", "spu_name", perm_write=True)
        user_env = self.user_env()
        res = user_env["test.oql.product"].oql(
            f"update test.oql.product set spu_name = 'Field OK' where id = {self.prod_cold.id}"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(self.prod_cold.spu_name, 'Field OK')
