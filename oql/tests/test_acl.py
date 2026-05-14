# -*- coding: utf-8 -*-
# @Time         : 15:42 2026/5/12
# @Author       : Chris
# @Description  : Test OQL ACL functionality
from odoo.exceptions import AccessError
from odoo.tests import tagged, TransactionCase

from .test_model_defs import ensure_model_meta
from ..acl import OqlAcl


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
        self.test_user = env['res.users'].create({
            'name': 'Test ACL User',
            'login': 'test_acl_user',
            'email': 'test_acl@example.com',
            'groups_id': [(6, 0, [env.ref('base.group_user').id])],  # Internal User group
        })

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
        user_group = self.test_user.groups_id.filtered(lambda g: g.name == 'Internal User')
        
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
