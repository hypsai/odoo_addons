# -*- coding: utf-8 -*-
# @Time         : 15:42 2026/5/12
# @Author       : Chris
# @Description  : Test OQL ACL functionality
from odoo.exceptions import AccessError
from odoo.tests import tagged, TransactionCase

from .test_model_defs import ensure_model_meta
from ..acl import OqlAcl
from ..compatible import res_users_data, res_users_group_id


@tagged("oql_acl", "-at_install", 'post_install')
class TestOqlAcl(TransactionCase):

    def setUp(self):
        super().setUp()
        env = self.env

        # 1. Load model meta
        ensure_model_meta(env)
        metaProduct = env["ir.model"].search([("model", "=", "test.oql.product")], limit=1)
        metaAttribute = env["ir.model"].search([("model", "=", "test.oql.attribute")], limit=1)
        metaAttributeValue = env["ir.model"].search([("model", "=", "test.oql.attribute.value")], limit=1)
        metaTag = env["ir.model"].search([("model", "=", "test.oql.tag")], limit=1)

        # 2. Create test records (as admin for setup)
        prod_cold = env["test.oql.product"].create({"spu_name": "Cold Boot"})
        prod_hot = env["test.oql.product"].create({"spu_name": "Hot Boot"})

        attr_size = env["test.oql.attribute"].create({"name": "Size"})
        attr_width = env["test.oql.attribute"].create({"name": "Width"})

        for prod in [prod_cold, prod_hot]:
            for attr, values in [(attr_size, ["5", "6", "7"]),
                                 (attr_width, ["D", "EE"])]:
                for value in values:
                    env["test.oql.attribute.value"].create({
                        "name": value,
                        "product_id": prod.id,
                        "attribute_id": attr.id})

        tag_waterproof = env["test.oql.tag"].create({"name": "Waterproof:GTX", "tmpl_id": prod_cold.tmpl_id.id})
        tag_temperate = env["test.oql.tag"].create({"name": "Weather:Cold", "tmpl_id": prod_cold.tmpl_id.id})

        # 3. Store references for tests
        self.prod_cold = prod_cold
        self.prod_hot = prod_hot
        self.metaProduct = metaProduct
        self.metaAttribute = metaAttribute
        self.metaAttributeValue = metaAttributeValue
        self.metaTag = metaTag

        # 4. Create a test user with limited permissions
        self.test_user = env['res.users'].create(res_users_data({
            'name': 'Test ACL User',
            'login': 'test_acl_user',
            'email': 'test_acl@example.com',
            'groups_id': [(6, 0, [env.ref('base.group_user').id])],  # Internal User group
        }))

    def _get_acl(self):
        """Get OqlAcl instance."""
        return OqlAcl(self.env)

    @tagged("acl.basic")
    def test_acl_initialization(self):
        """Test basic ACL initialization and model access."""
        acl = self._get_acl()
        self.assertIsNotNone(acl)

        # Test that we can get model ACL
        product_acl = acl["test.oql.product"]
        self.assertIsNotNone(product_acl)
        self.assertEqual(product_acl.model_name, "test.oql.product")

    @tagged("acl.field")
    def test_acl_field_check_read(self):
        """Test field-level read access check."""
        acl = self._get_acl()

        # In superuser mode, all fields should be accessible
        product_acl = acl["test.oql.product"]

        # Check individual field ACL
        name_acl = product_acl["name"]
        self.assertTrue(name_acl.check("read"))
        self.assertTrue(name_acl.perm_read)

        active_acl = product_acl["active"]
        self.assertTrue(active_acl.check("read"))

    @tagged("acl.field")
    def test_acl_field_check_write(self):
        """Test field-level write access check."""
        acl = self._get_acl()
        product_acl = acl["test.oql.product"]

        # In superuser mode, all fields should be writable
        name_acl = product_acl["name"]
        self.assertTrue(name_acl.check("write"))
        self.assertTrue(name_acl.perm_write)

    @tagged("acl.fields")
    def test_acl_perm_fields(self):
        """Test getting permitted fields for a model."""
        acl = self._get_acl()
        product_acl = acl["test.oql.product"]

        # Get all readable fields
        readable_fields = product_acl.perm_fields("read")
        self.assertIsInstance(readable_fields, set)
        self.assertIn("name", readable_fields)
        self.assertIn("id", readable_fields)  # ID is always readable

        # Get all writable fields
        writable_fields = product_acl.perm_fields("write")
        self.assertIsInstance(writable_fields, set)
        self.assertIn("name", writable_fields)

    @tagged("acl.path_permission")
    def test_acl_perm_paths_with_user(self):
        """Test path permission checking with a regular user."""
        env = self.env

        # Get user group
        user_group = self.test_user.groups_id.filtered(lambda g: g.name == 'Internal User')

        # Create access with default deny
        temp_access = env["ir.model.access"].create({
            'name': 'Path Test Access',
            'model_id': self.metaProduct.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_write': False,
            'perm_oql_fac_default_read': False,
            'perm_oql_fac_default_write': False,
        })

        # Grant access to specific fields
        name_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaProduct.id),
            ('name', '=', 'name')
        ], limit=1)

        tag_ids_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaProduct.id),
            ('name', '=', 'tag_ids')
        ], limit=1)

        env["oql.acl.field"].create({
            'mac_id': temp_access.id,
            'field_id': name_field.id,
            'perm_read': True,
        })

        env["oql.acl.field"].create({
            'mac_id': temp_access.id,
            'field_id': tag_ids_field.id,
            'perm_read': True,
        })

        # Also grant access to tag model's name field
        tag_name_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaTag.id),
            ('name', '=', 'name')
        ], limit=1)

        tag_access = env["ir.model.access"].create({
            'name': 'Tag Model Access',
            'model_id': self.metaTag.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_oql_fac_default_read': True,  # Allow all tag fields
        })

        # Switch to test user
        user_env = env(user=self.test_user)
        acl = OqlAcl(user_env)

        # Test paths
        paths = [
            "name",  # Should be allowed
            "active",  # Should NOT be allowed (not granted)
            "tag_ids.name",  # Should be allowed (both levels granted)
        ]

        allowed_paths = acl.perm_paths("test.oql.product", paths, "read")

        self.assertIn("name", allowed_paths)
        self.assertNotIn("active", allowed_paths)
        self.assertIn("tag_ids.name", allowed_paths)

    @tagged("acl.check_field")
    def test_acl_check_field_with_user(self):
        """Test field access check with a regular user."""
        env = self.env

        # Get user group
        user_group = self.test_user.groups_id.filtered(lambda g: g.name == 'Internal User')

        # Create access record
        temp_access = env["ir.model.access"].create({
            'name': 'Field Check Test Access',
            'model_id': self.metaProduct.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_write': False,
            'perm_oql_fac_default_read': False,
            'perm_oql_fac_default_write': False,
        })

        # Grant read access to 'name' field only
        name_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaProduct.id),
            ('name', '=', 'name')
        ], limit=1)

        env["oql.acl.field"].create({
            'mac_id': temp_access.id,
            'field_id': name_field.id,
            'perm_read': True,
        })

        # Switch to test user
        user_env = env(user=self.test_user)
        acl = OqlAcl(user_env)

        # Should not raise for accessible field
        recs = user_env["test.oql.product"].browse([self.prod_cold.id])
        acl.check_field(recs, "name", "read")

        # Should raise AccessError for non-accessible field
        with self.assertRaises(AccessError):
            acl.check_field(recs, "active", "read")

    @tagged("acl.multi_model")
    def test_acl_multiple_models_with_user(self):
        """Test ACL across multiple models with a regular user."""
        env = self.env

        # Get user group
        user_group = self.test_user.groups_id.filtered(lambda g: g.name == 'Internal User')

        # Create access for product model
        product_access = env["ir.model.access"].create({
            'name': 'Product Model Access',
            'model_id': self.metaProduct.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_oql_fac_default_read': True,
        })

        # Create access for attribute model
        attribute_access = env["ir.model.access"].create({
            'name': 'Attribute Model Access',
            'model_id': self.metaAttribute.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_oql_fac_default_read': True,
        })

        # Create access for tag model
        tag_access = env["ir.model.access"].create({
            'name': 'Tag Model Access',
            'model_id': self.metaTag.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_oql_fac_default_read': True,
        })

        # Switch to test user
        user_env = env(user=self.test_user)
        acl = OqlAcl(user_env)

        # Test different models
        product_acl = acl["test.oql.product"]
        attribute_acl = acl["test.oql.attribute"]
        tag_acl = acl["test.oql.tag"]

        # All should have read access to name field
        self.assertIn("name", product_acl.perm_fields("read"))
        self.assertIn("name", attribute_acl.perm_fields("read"))
        self.assertIn("name", tag_acl.perm_fields("read"))

    @tagged("acl.relational")
    def test_acl_relational_fields_with_user(self):
        """Test ACL for relational fields with a regular user."""
        env = self.env

        # Get user group
        user_group = self.test_user.groups_id.filtered(lambda g: g.name == 'Internal User')

        # Create access with default deny
        temp_access = env["ir.model.access"].create({
            'name': 'Relational Field Access',
            'model_id': self.metaProduct.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_oql_fac_default_read': False,
        })

        # Grant access only to tag_ids, not attribute_value_ids
        tag_ids_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaProduct.id),
            ('name', '=', 'tag_ids')
        ], limit=1)

        env["oql.acl.field"].create({
            'mac_id': temp_access.id,
            'field_id': tag_ids_field.id,
            'perm_read': True,
        })

        # Switch to test user
        user_env = env(user=self.test_user)
        acl = OqlAcl(user_env)
        product_acl = acl["test.oql.product"]

        readable_fields = product_acl.perm_fields("read")

        # Should have access to tag_ids (granted)
        self.assertIn("tag_ids", readable_fields)

        # Should NOT have access to attribute_value_ids (not granted)
        self.assertNotIn("attribute_value_ids", readable_fields)

    @tagged("acl.comprehensive")
    def test_acl_complete_workflow(self):
        """Test complete ACL workflow with paths and fields."""
        acl = self._get_acl()

        # 1. Check model ACL exists
        product_acl = acl["test.oql.product"]
        self.assertIsNotNone(product_acl)

        # 2. Check field permissions
        readable = product_acl.perm_fields("read")
        self.assertIn("name", readable)
        self.assertIn("id", readable)

        # 3. Check path permissions
        paths = ["name", "attribute_value_ids.name", "tag_ids.name"]
        allowed = acl.perm_paths("test.oql.product", paths, "read")
        self.assertEqual(len(allowed), len(paths))

        # 4. Verify field check doesn't raise
        recs = self.env["test.oql.product"].browse([self.prod_cold.id])
        acl.check_field(recs, "name", "read")

    @tagged("acl.temp_access")
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

    @tagged("acl.with_user")
    def test_acl_with_regular_user(self):
        """Test ACL with a regular (non-sudo) user to verify actual permission enforcement."""
        env = self.env

        # Create model access for the test user's group
        user_group = self.test_user.groups_id.filtered(lambda g: g.name == 'Internal User')
        self.assertTrue(user_group.exists())

        # Create access record granting read but not write
        temp_access = env["ir.model.access"].create({
            'name': 'Test User Product Access',
            'model_id': self.metaProduct.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_write': False,
            'perm_create': False,
            'perm_unlink': False,
            'perm_oql_fac_default_read': True,
            'perm_oql_fac_default_write': False,
        })

        # Switch to test user context
        user_env = env(user=self.test_user)
        acl = OqlAcl(user_env)

        # Check that the user has read but not write access
        product_acl = acl["test.oql.product"]
        readable_fields = product_acl.perm_fields("read")
        writable_fields = product_acl.perm_fields("write")

        # Should have read access to fields
        self.assertIn("name", readable_fields)
        self.assertIn("id", readable_fields)

        # Should NOT have write access (perm_write=False and perm_oql_fac_default_write=False)
        self.assertNotIn("name", writable_fields)

    @tagged("acl.field_restriction")
    def test_acl_field_level_restriction(self):
        """Test field-level ACL restrictions with a regular user."""
        env = self.env

        # Get user group
        user_group = self.test_user.groups_id.filtered(lambda g: g.name == 'Internal User')

        # Create access with default deny for read
        temp_access = env["ir.model.access"].create({
            'name': 'Restricted Field Access',
            'model_id': self.metaProduct.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_write': False,
            'perm_oql_fac_default_read': False,  # Default: no read access to fields
            'perm_oql_fac_default_write': False,
        })

        # Get field metadata
        name_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaProduct.id),
            ('name', '=', 'name')
        ], limit=1)

        active_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaProduct.id),
            ('name', '=', 'active')
        ], limit=1)

        # Grant explicit read access only to 'name' field
        env["oql.acl.field"].create({
            'mac_id': temp_access.id,
            'field_id': name_field.id,
            'perm_read': True,
            'perm_write': False,
        })

        # Switch to test user
        user_env = env(user=self.test_user)
        acl = OqlAcl(user_env)
        product_acl = acl["test.oql.product"]

        # Check field permissions
        readable_fields = product_acl.perm_fields("read")

        # Should have access to 'name' (explicitly granted)
        self.assertIn("name", readable_fields)

        # Should NOT have access to 'active' (not granted and default is False)
        self.assertNotIn("active", readable_fields)

        # ID should always be readable
        self.assertIn("id", readable_fields)

    @tagged("acl.temp_acl_field")
    def test_create_temp_acl_field(self):
        """Test creating temporary oql.acl.field records."""
        env = self.env

        # First create a model access record
        temp_access = env["ir.model.access"].create({
            'name': 'Test Access for ACL Field',
            'model_id': self.metaProduct.id,
            'perm_read': True,
            'perm_write': True,
            'perm_oql_fac_default_read': False,  # Default to false
            'perm_oql_fac_default_write': False,
        })

        # Get field metadata
        name_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaProduct.id),
            ('name', '=', 'name')
        ], limit=1)

        active_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaProduct.id),
            ('name', '=', 'active')
        ], limit=1)

        self.assertTrue(name_field.exists())
        self.assertTrue(active_field.exists())

        # Create ACL field records
        acl_name = env["oql.acl.field"].create({
            'mac_id': temp_access.id,
            'field_id': name_field.id,
            'perm_read': True,
            'perm_write': True,
        })

        acl_active = env["oql.acl.field"].create({
            'mac_id': temp_access.id,
            'field_id': active_field.id,
            'perm_read': True,
            'perm_write': False,
        })

        # Verify creation
        self.assertTrue(acl_name.exists())
        self.assertTrue(acl_active.exists())
        self.assertEqual(acl_name.mac_id, temp_access)
        self.assertEqual(acl_name.field_id, name_field)
        self.assertTrue(acl_name.perm_read)
        self.assertTrue(acl_name.perm_write)
        self.assertTrue(acl_active.perm_read)
        self.assertFalse(acl_active.perm_write)

    @tagged("acl.temp_with_check")
    def test_acl_with_temp_records_user_context(self):
        """Test ACL checking with temporary access records in user context."""
        env = self.env

        # Get user group
        user_group = self.test_user.groups_id.filtered(lambda g: g.name == 'Internal User')

        # Create temporary model access with restrictive defaults
        temp_access = env["ir.model.access"].create({
            'name': 'Restrictive Test Access',
            'model_id': self.metaProduct.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_write': False,
            'perm_oql_fac_default_read': False,  # Default: no read access
            'perm_oql_fac_default_write': False,  # Default: no write access
        })

        # Get field metadata
        name_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaProduct.id),
            ('name', '=', 'name')
        ], limit=1)

        active_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaProduct.id),
            ('name', '=', 'active')
        ], limit=1)

        # Grant explicit read access only to 'name' field
        acl_name = env["oql.acl.field"].create({
            'mac_id': temp_access.id,
            'field_id': name_field.id,
            'perm_read': True,
            'perm_write': False,
        })

        # Switch to test user and verify ACL
        user_env = env(user=self.test_user)
        acl = OqlAcl(user_env)
        product_acl = acl["test.oql.product"]

        # Verify field permissions for the user
        readable_fields = product_acl.perm_fields("read")
        writable_fields = product_acl.perm_fields("write")

        # Should have read access to 'name' (explicitly granted)
        self.assertIn("name", readable_fields)

        # Should NOT have read access to 'active' (not granted)
        self.assertNotIn("active", readable_fields)

        # Should NOT have write access to any field
        self.assertNotIn("name", writable_fields)
        self.assertNotIn("active", writable_fields)

    @tagged("acl.multiple_temp_records")
    def test_multiple_temp_acl_fields_user_context(self):
        """Test creating multiple temporary ACL field records with user context."""
        env = self.env

        # Get user group
        user_group = self.test_user.groups_id.filtered(lambda g: g.name == 'Internal User')

        # Create model access with default deny
        temp_access = env["ir.model.access"].create({
            'name': 'Multi-Field Test Access',
            'model_id': self.metaProduct.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_write': False,
            'perm_oql_fac_default_read': False,
            'perm_oql_fac_default_write': False,
        })

        # Get multiple fields and grant selective access
        fields_to_grant = ['name', 'active']  # Only grant these two
        acl_records = []

        for field_name in fields_to_grant:
            field = env["ir.model.fields"].search([
                ('model_id', '=', self.metaProduct.id),
                ('name', '=', field_name)
            ], limit=1)

            if field.exists():
                acl_rec = env["oql.acl.field"].create({
                    'mac_id': temp_access.id,
                    'field_id': field.id,
                    'perm_read': True,
                    'perm_write': False,
                })
                acl_records.append(acl_rec)

        # Verify all records were created
        self.assertEqual(len(acl_records), len(fields_to_grant))

        # Switch to test user and verify permissions
        user_env = env(user=self.test_user)
        acl = OqlAcl(user_env)
        product_acl = acl["test.oql.product"]

        readable_fields = product_acl.perm_fields("read")
        writable_fields = product_acl.perm_fields("write")

        # Should have read access to granted fields
        self.assertIn("name", readable_fields)
        self.assertIn("active", readable_fields)

        # Should NOT have write access
        self.assertNotIn("name", writable_fields)
        self.assertNotIn("active", writable_fields)

        # Should NOT have access to non-granted relational fields
        self.assertNotIn("attribute_value_ids", readable_fields)
        self.assertNotIn("tag_ids", readable_fields)

    @tagged("acl.cleanup")
    def test_temp_records_cleanup(self):
        """Test that temporary records can be properly cleaned up."""
        env = self.env

        # Create temporary records
        temp_access = env["ir.model.access"].create({
            'name': 'Cleanup Test Access',
            'model_id': self.metaProduct.id,
            'perm_read': True,
            'perm_write': True,
        })

        name_field = env["ir.model.fields"].search([
            ('model_id', '=', self.metaProduct.id),
            ('name', '=', 'name')
        ], limit=1)

        acl_field = env["oql.acl.field"].create({
            'mac_id': temp_access.id,
            'field_id': name_field.id,
            'perm_read': True,
            'perm_write': True,
        })

        # Verify records exist
        self.assertTrue(temp_access.exists())
        self.assertTrue(acl_field.exists())

        # Delete the access record (should cascade delete ACL fields)
        temp_access.unlink()

        # Verify both are deleted
        self.assertFalse(temp_access.exists())
        self.assertFalse(acl_field.exists())

    @tagged("acl.inheritance")
    def test_acl_inherited_model_permissions(self):
        """Test that permissions on parent model fields are inherited by child model."""
        env = self.env

        # Get user group
        user_group = res_users_group_id(self.test_user).filtered(lambda g: g.name == 'Internal User')

        # Get template model metadata
        metaTemplate = env["ir.model"].search([("model", "=", "test.oql.template")], limit=1)

        # Create access for template model with default deny
        template_access = env["ir.model.access"].create({
            'name': 'Template Model Access',
            'model_id': metaTemplate.id,
            'group_id': user_group.id,
            'perm_read': True,
            'perm_write': False,
            'perm_oql_fac_default_read': False,  # Default: no read access
            'perm_oql_fac_default_write': False,
        })

        # Get tag_ids field from template model
        tag_ids_field = env["ir.model.fields"].search([
            ('model_id', '=', metaTemplate.id),
            ('name', '=', 'tag_ids')
        ], limit=1)

        self.assertTrue(tag_ids_field.exists(), "tag_ids field should exist in template model")

        # Grant read access to tag_ids field in template model
        env["oql.acl.field"].create({
            'mac_id': template_access.id,
            'field_id': tag_ids_field.id,
            'perm_read': True,
            'perm_write': False,
        })

        # Switch to test user
        user_env = env(user=self.test_user)
        acl = OqlAcl(user_env)

        # Check that product model (which inherits template) has access to tag_ids
        product_acl = acl["test.oql.product"]
        readable_fields = product_acl.perm_fields("read")

        # tag_ids should be readable in product model due to inheritance
        self.assertIn("tag_ids", readable_fields,
                      "tag_ids field should be readable in product model through inheritance")

        # Also verify we can check the field without raising an error
        recs = user_env["test.oql.product"].browse([self.prod_cold.id])
        acl.check_field(recs, "tag_ids", "read")


@tagged("oql_record_rule", "-at_install", 'post_install')
class TestOqlRecordRule(TransactionCase):
    """Test record-level permission control via ir.rule integration.

    OQL's record-level ACL is fully aligned with Odoo's native design,
    using ir.rule domain restrictions applied via
    `self.env['ir.rule']._compute_domain(self.model_name, mode=mode)`.
    """

    def setUp(self):
        super().setUp()
        env = self.env

        # 1. Load model meta.
        ensure_model_meta(env)
        self.metaProduct = env["ir.model"].search([("model", "=", "test.oql.product")], limit=1)
        self.metaAttribute = env["ir.model"].search([("model", "=", "test.oql.attribute")], limit=1)
        self.metaAttributeValue = env["ir.model"].search([("model", "=", "test.oql.attribute.value")], limit=1)
        self.metaTag = env["ir.model"].search([("model", "=", "test.oql.tag")], limit=1)
        self.metaTemplate = env["ir.model"].search([("model", "=", "test.oql.template")], limit=1)

        # 2. Create test records.
        self.prod_cold = env["test.oql.product"].create({"spu_name": "Cold Boot"})
        self.prod_hot = env["test.oql.product"].create({"spu_name": "Hot Boot"})
        self.prod_inactive = env["test.oql.product"].create({"spu_name": "Inactive Boot", "active": False})

        attr_size = env["test.oql.attribute"].create({"name": "Size"})
        attr_width = env["test.oql.attribute"].create({"name": "Width"})
        for prod in [self.prod_cold, self.prod_hot]:
            for attr, values in [(attr_size, ["5", "6", "7"]),
                                 (attr_width, ["D", "EE"])]:
                for value in values:
                    env["test.oql.attribute.value"].create({
                        "name": value,
                        "product_id": prod.id,
                        "attribute_id": attr.id})

        self.tag_waterproof = env["test.oql.tag"].create(
            {"name": "Waterproof:GTX", "tmpl_id": self.prod_cold.tmpl_id.id})
        self.tag_cold = env["test.oql.tag"].create({"name": "Weather:Cold", "tmpl_id": self.prod_cold.tmpl_id.id})
        self.tag_hot = env["test.oql.tag"].create({"name": "Weather:Hot", "tmpl_id": self.prod_hot.tmpl_id.id})

        # 3. Create a test user with Internal User group.
        self.test_user = env['res.users'].create(res_users_data({
            'name': 'Record Rule Test User',
            'login': 'record_rule_test_user',
            'email': 'record_rule@example.com',
            'groups_id': [(6, 0, [env.ref('base.group_user').id])],
        }))
        self.user_group = env.ref('base.group_user')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _grant_model_access(self, model_meta, perm_read=True, group=None):
        """Create an ir.model.access record granting read access to a model."""
        env = self.env
        return env["ir.model.access"].create({
            'name': f'Test Access {model_meta.model}',
            'model_id': model_meta.id,
            'group_id': (group or self.user_group).id,
            'perm_read': perm_read,
            'perm_write': False,
            'perm_create': False,
            'perm_unlink': False,
            'perm_oql_fac_default_read': True,
            'perm_oql_fac_default_write': False,
        })

    def _create_ir_rule(self, model_meta, domain_force, groups=None):
        """Create an ir.rule record for record-level permission control."""
        env = self.env
        vals = {
            'name': f'Test Record Rule for {model_meta.model}',
            'model_id': model_meta.id,
            'domain_force': domain_force,
        }
        if groups is not None:
            vals['groups'] = groups
        return env['ir.rule'].create(vals)

    def _get_user_env(self):
        """Get environment for the test user."""
        return self.env(user=self.test_user)

    # ------------------------------------------------------------------
    # Tests: Basic record-level rule filtering
    # ------------------------------------------------------------------

    @tagged("record_rule.basic")
    def test_record_rule_filter_by_name(self):
        """An ir.rule that restricts visible products by spu_name should
        be respected by searcho."""
        # Grant model access and create a record rule: only see spu_name containing "Cold"
        self._grant_model_access(self.metaProduct)
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', '=like', 'Cold%')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        res = user_env["test.oql.product"].searcho("tag_ids")
        names = set(res.mapped("spu_name"))
        self.assertEqual({"Cold Boot"}, names)

    @tagged("record_rule.basic")
    def test_record_rule_no_restriction(self):
        """Without any ir.rule, a user with model access should see all records."""
        self._grant_model_access(self.metaProduct)

        user_env = self._get_user_env()
        res = user_env["test.oql.product"].searcho("tag_ids")
        names = set(res.mapped("spu_name"))
        self.assertEqual({"Cold Boot", "Hot Boot"}, names)

    @tagged("record_rule.basic")
    def test_record_rule_filter_active(self):
        """An ir.rule filtering active=True should exclude inactive records."""
        self._grant_model_access(self.metaProduct)
        self._create_ir_rule(
            self.metaProduct,
            "[('active', '=', True)]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        # Search without any additional filter — should only see active products
        res = user_env["test.oql.product"].searcho("id > 0")
        names = set(res.mapped("spu_name"))
        self.assertIn("Cold Boot", names)
        self.assertIn("Hot Boot", names)
        self.assertNotIn("Inactive Boot", names)

    # ------------------------------------------------------------------
    # Tests: oql() queries with record rules
    # ------------------------------------------------------------------

    @tagged("record_rule.oql")
    def test_record_rule_with_oql_select(self):
        """Verify oql() results are filtered by ir.rule."""
        self._grant_model_access(self.metaProduct)
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', 'ilike', 'hot')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        res = user_env["test.oql.product"].oql(
            "from test.oql.product select spu_name where tag_ids"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['spu_name'], "Hot Boot")

    @tagged("record_rule.oql")
    def test_record_rule_oql_combined_where(self):
        """Record rule domain AND user's WHERE clause are combined."""
        self._grant_model_access(self.metaProduct)
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', 'ilike', 'boot')]",  # restricts to Boot products
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        res = user_env["test.oql.product"].oql(
            "from test.oql.product select spu_name where tag_ids"
        )
        # Both Cold Boot and Hot Boot should match
        names = {row['spu_name'] for row in res}
        self.assertEqual({"Cold Boot", "Hot Boot"}, names)

    @tagged("record_rule.oql")
    def test_record_rule_oql_empty_result(self):
        """When record rule matches nothing, query should return empty."""
        self._grant_model_access(self.metaProduct)
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', '=', 'Nonexistent Product')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        res = user_env["test.oql.product"].oql(
            "from test.oql.product select spu_name where tag_ids"
        )
        self.assertEqual(len(res), 0)

    # ------------------------------------------------------------------
    # Tests: Multiple rules (AND logic)
    # ------------------------------------------------------------------

    @tagged("record_rule.multi")
    def test_record_rule_global_and(self):
        """Two global ir.rule records are intersected (AND logic).

        In Odoo's ir.rule._compute_domain:
          AND(global_domains + [OR(group_domains)])
        Global rules (no groups) are AND-ed together.
        """
        self._grant_model_access(self.metaProduct)
        # Rule 1 (global): spu_name contains "Boot"
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', 'ilike', 'Boot')]",
        )
        # Rule 2 (global): active = True
        self._create_ir_rule(
            self.metaProduct,
            "[('active', '=', True)]",
        )

        user_env = self._get_user_env()
        res = user_env["test.oql.product"].searcho("id > 0")
        names = set(res.mapped("spu_name"))
        # AND of two global rules: only active Boot products
        self.assertNotIn("Inactive Boot", names)
        self.assertEqual({"Cold Boot", "Hot Boot"}, names)

    @tagged("record_rule.multi")
    def test_record_rule_group_or(self):
        """Two group ir.rule records are OR-ed together.

        In Odoo's ir.rule._compute_domain:
          AND(global_domains + [OR(group_domains)])
        Group rules (with groups) are OR-ed together within a group domain.
        """
        self._grant_model_access(self.metaProduct)
        # Rule 1 (group): only Cold Boot
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', '=', 'Cold Boot')]",
            groups=[(4, self.user_group.id)],
        )
        # Rule 2 (group): only Hot Boot
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', '=', 'Hot Boot')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        res = user_env["test.oql.product"].searcho("id > 0")
        names = set(res.mapped("spu_name"))
        # OR of group rules: Cold Boot OR Hot Boot = both
        self.assertEqual({"Cold Boot", "Hot Boot"}, names)

    @tagged("record_rule.multi")
    def test_record_rule_global_and_group(self):
        """Global rule AND group rules OR: global AND (group1 OR group2).

        Verdict: global(active=True) AND (group(spu_name=Cold) OR group(spu_name=Hot))
        Should only see active Boot products.
        """
        self._grant_model_access(self.metaProduct)
        # Global rule: active = True (excludes Inactive Boot)
        self._create_ir_rule(
            self.metaProduct,
            "[('active', '=', True)]",
        )
        # Group rule 1: spu_name = Cold Boot
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', '=', 'Cold Boot')]",
            groups=[(4, self.user_group.id)],
        )
        # Group rule 2: spu_name = Hot Boot (note: NOT created, to show OR)
        # Actually let's create it to test full OR behavior
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', '=', 'Hot Boot')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        res = user_env["test.oql.product"].searcho("id > 0")
        names = set(res.mapped("spu_name"))
        # global(active=True) AND (group(Cold Boot) OR group(Hot Boot))
        # = {Cold Boot, Hot Boot} (Inactive Boot excluded by global)
        self.assertEqual({"Cold Boot", "Hot Boot"}, names)
        self.assertNotIn("Inactive Boot", names)

    # ------------------------------------------------------------------
    # Tests: Record rules with orderby / limit / offset
    # ------------------------------------------------------------------

    @tagged("record_rule.oql")
    def test_record_rule_with_limit(self):
        """LIMIT clause should work correctly under record rule filtering."""
        self._grant_model_access(self.metaProduct)
        # No restriction rule => all 2 products visible
        user_env = self._get_user_env()
        res = user_env["test.oql.product"].oql(
            "from test.oql.product select spu_name where tag_ids limit 1"
        )
        self.assertEqual(len(res), 1)

    @tagged("record_rule.oql")
    def test_record_rule_with_orderby(self):
        """ORDER BY should work correctly with record rules."""
        self._grant_model_access(self.metaProduct)
        user_env = self._get_user_env()
        res = user_env["test.oql.product"].oql(
            "from test.oql.product select spu_name where tag_ids order by name desc"
        )
        self.assertEqual(len(res), 2)
        # "Hot Boot" should come before "Cold Boot" in descending order
        self.assertEqual(res[0]['spu_name'], "Hot Boot")
        self.assertEqual(res[1]['spu_name'], "Cold Boot")

    # ------------------------------------------------------------------
    # Tests: Record rules combined with field-level ACL
    # ------------------------------------------------------------------

    @tagged("record_rule.field_acl")
    def test_record_rule_with_field_restriction(self):
        """Record-level rule + field-level ACL should both be enforced."""
        env = self.env

        # Create model access with restricted field access.
        temp_access = env["ir.model.access"].create({
            'name': 'Restricted Access',
            'model_id': self.metaProduct.id,
            'group_id': self.user_group.id,
            'perm_read': True,
            'perm_write': False,
            'perm_oql_fac_default_read': False,
            'perm_oql_fac_default_write': False,
        })

        # Grant read access only to spu_name and tag_ids.
        for field_name in ['spu_name', 'tag_ids']:
            field = env["ir.model.fields"].search([
                ('model_id', '=', self.metaProduct.id),
                ('name', '=', field_name),
            ], limit=1)
            env["oql.acl.field"].create({
                'mac_id': temp_access.id,
                'field_id': field.id,
                'perm_read': True,
            })

        # Create record rule: only see spu_name containing "Boot"
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', 'ilike', 'Boot')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        res = user_env["test.oql.product"].oql(
            "from test.oql.product select spu_name where tag_ids"
        )
        names = {row['spu_name'] for row in res}
        self.assertEqual({"Cold Boot", "Hot Boot"}, names)

    # ------------------------------------------------------------------
    # Tests: Record rule with no groups (user-specific rule)
    # ------------------------------------------------------------------

    @tagged("record_rule.basic")
    def test_record_rule_non_group_rule(self):
        """A rule without groups should still be computed by _compute_domain
        (Odoo applies non-global rules to all users)."""
        self._grant_model_access(self.metaProduct)
        # Create a rule without groups — Odoo treats this as a global rule
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', '=', 'Cold Boot')]",
            groups=None,  # No group restriction => global rule
        )

        user_env = self._get_user_env()
        res = user_env["test.oql.product"].searcho("id > 0")
        names = set(res.mapped("spu_name"))
        self.assertEqual({"Cold Boot"}, names)

    # ------------------------------------------------------------------
    # Tests: Record rules across inherited models
    # ------------------------------------------------------------------

    @tagged("record_rule.inherit")
    def test_record_rule_inherited_model(self):
        """Record rules on _inherits parent model are per-model, do NOT cascade.

        Odoo's ir.rule._compute_domain only looks up rules for the exact model
        being queried. A rule on test.oql.template does NOT restrict
        test.oql.product (which _inherits template). This test verifies that
        template rules correctly restrict direct template queries.
        """
        self._grant_model_access(self.metaTemplate)
        # Create a rule on the template (parent) model
        self._create_ir_rule(
            self.metaTemplate,
            "[('name', 'ilike', 'Cold')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        # Query the template model directly — rule applies here
        res = user_env["test.oql.template"].searcho("id > 0")
        names = set(res.mapped("name"))
        self.assertEqual({"Cold Boot"}, names)

    # ------------------------------------------------------------------
    # Tests: Admin/sudo should NOT be affected
    # ------------------------------------------------------------------

    @tagged("record_rule.admin")
    def test_record_rule_admin_not_affected(self):
        """Admin/sudo user should bypass ir.rule restrictions."""
        self._grant_model_access(self.metaProduct)
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', '=', 'Cold Boot')]",
            groups=[(4, self.user_group.id)],
        )

        # Admin with .sudo() should see all active products
        # (Inactive Boot has active=False, excluded by Odoo's default filtering)
        res = self.env["test.oql.product"].sudo().searcho("id > 0")
        names = set(res.mapped("spu_name"))
        self.assertEqual({"Cold Boot", "Hot Boot"}, names)

    # ------------------------------------------------------------------
    # Tests: Direct perm_records method
    # ------------------------------------------------------------------

    @tagged("record_rule.read_only")
    def test_record_rule_perm_records_direct(self):
        """Directly test perm_records method with an ir.rule in place."""
        from ..acl import OqlAcl

        self._grant_model_access(self.metaProduct)
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', '=', 'Cold Boot')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        acl = OqlAcl(user_env)
        product_acl = acl["test.oql.product"]

        # perm_records should merge the rule domain via AND
        result_domain = product_acl.perm_records([('id', '>', 0)], "read")

        # Should produce a combined AND domain
        self.assertIsInstance(result_domain, list)
        # Verify the AND structure: [('id', '>', 0)] AND [rule domain]
        self.assertTrue(len(result_domain) > 1)

    @tagged("record_rule.searcho")
    def test_record_rule_searcho_and_direct_search(self):
        """Record rule via searcho should match direct Odoo search behavior."""
        self._grant_model_access(self.metaProduct)
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', '=like', 'Cold%')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()

        # searcho result
        res_oql = user_env["test.oql.product"].searcho("id > 0")
        names_oql = set(res_oql.mapped("spu_name"))

        # Direct search with the same domain should return same result
        res_direct = user_env["test.oql.product"].search([('id', '>', 0)])
        names_direct = set(res_direct.mapped("spu_name"))

        self.assertEqual(names_oql, names_direct)
        self.assertEqual({"Cold Boot"}, names_oql)

    @tagged("record_rule.searcho")
    def test_record_rule_searcho_id_query(self):
        """Record rule applied to a specific ID query."""
        self._grant_model_access(self.metaProduct)
        # Rule: only Cold Boot
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', '=', 'Cold Boot')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        # Try to get Hot Boot by ID — should be empty because record rule blocks it
        res = user_env["test.oql.product"].searcho(f"id = {self.prod_hot.id}")
        self.assertEqual(len(res), 0)

        # Try to get Cold Boot by ID — should succeed
        res = user_env["test.oql.product"].searcho(f"id = {self.prod_cold.id}")
        self.assertEqual(len(res), 1)
        self.assertEqual(res.spu_name, "Cold Boot")

    @tagged("record_rule.searcho")
    def test_record_rule_searcho_una_expr(self):
        """Record rule combined with unary expression (bool field check)."""
        self._grant_model_access(self.metaProduct)
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', 'ilike', 'Cold')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        # Unary expression: products that have tag_ids
        res = user_env["test.oql.product"].searcho("tag_ids")
        names = set(res.mapped("spu_name"))
        self.assertEqual({"Cold Boot"}, names)

    # ------------------------------------------------------------------
    # Tests: Additional edge cases
    # ------------------------------------------------------------------

    @tagged("record_rule.edge")
    def test_record_rule_or_logic(self):
        """OR logic in WHERE clause should be properly intersected with record rule."""
        self._grant_model_access(self.metaProduct)
        # Rule: all Boot products
        self._create_ir_rule(
            self.metaProduct,
            "[('spu_name', 'ilike', 'Boot')]",
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        # WHERE: Cold Boot OR Hot Boot by name
        res = user_env["test.oql.product"].searcho(
            "spu_name='Cold Boot' or spu_name='Hot Boot'"
        )
        names = set(res.mapped("spu_name"))
        self.assertEqual({"Cold Boot", "Hot Boot"}, names)

    @tagged("record_rule.edge")
    def test_record_rule_matching_no_record(self):
        """Record rule matching no records should still allow searcho (returns empty)."""
        self._grant_model_access(self.metaProduct)
        self._create_ir_rule(
            self.metaProduct,
            "[('id', '<', 0)]",  # impossible condition
            groups=[(4, self.user_group.id)],
        )

        user_env = self._get_user_env()
        res = user_env["test.oql.product"].searcho("id > 0")
        self.assertEqual(len(res), 0)
