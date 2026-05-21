# -*- coding: utf-8 -*-
# @Time         : 21:56 2026/5/15
# @Author       : Chris
# @Description  : Test cases for OQL Alias functionality

from odoo import Command
from odoo.tests import tagged, TransactionCase
from ..alias import AliasNode, AliasField, AliasJMESPath, AliasJinja2
from .test_model_defs import ensure_model_meta


@tagged("oql_alias", '-at_install', 'post_install')
class TestAliasParsing(TransactionCase):
    """Test alias parsing functionality."""

    def setUp(self):
        super().setUp()
        ensure_model_meta(self.env)

    def test_parse_dot_path(self):
        """Test parsing simple dot path."""
        node = AliasNode.parse("partner_name", "field", "partner_id.name")
        self.assertIsInstance(node, AliasField)
        self.assertEqual(node.path, "partner_id.name")
        self.assertEqual(node.alias, "partner_name")
        self.assertFalse(node.is_complex)

    def test_parse_jinja2_template(self):
        """Test parsing Jinja2 template."""
        node = AliasNode.parse("partner_info", "jinja2", 'Name is {{ rec.partner_id.name }}')
        self.assertIsInstance(node, AliasJinja2)
        self.assertEqual(node.alias, "partner_info")
        self.assertTrue(node.is_complex)

    def test_parse_jmespath_expression(self):
        """Test parsing JMESPath expression."""
        json_str = '{name: rec.partner_id.name, email: rec.partner_id.email}'
        node = AliasNode.parse("partner_data", "jmespath", json_str)
        self.assertIsInstance(node, AliasJMESPath)
        self.assertEqual(node.alias, "partner_data")
        self.assertTrue(node.is_complex)

    def test_fields_extraction_field(self):
        """Test fields extraction for Field mode."""
        node = AliasNode.parse("name", "field", "partner_id.name")
        fields = list(node.fields)
        self.assertEqual(fields, ["partner_id.name"])

    def test_fields_extraction_jinja2(self):
        """Test fields extraction for Jinja2 mode with nested fields."""
        # Simple nested field
        node = AliasNode.parse("info", "jinja2", "{{ rec.partner_id.name }}")
        fields = set(node.fields)
        self.assertIn("partner_id.name", fields)
        
        # Multiple nested fields
        node = AliasNode.parse("info", "jinja2", "{{ rec.partner_id.name }} - {{ rec.partner_id.email }}")
        fields = set(node.fields)
        self.assertIn("partner_id.name", fields)
        self.assertIn("partner_id.email", fields)
        
        # Deep nested fields
        node = AliasNode.parse("info", "jinja2", "{{ rec.partner_id.country_id.name }}")
        fields = set(node.fields)
        self.assertIn("partner_id.country_id.name", fields)
        
        # Mixed depth fields
        node = AliasNode.parse("info", "jinja2", "Name: {{ rec.name }}, Country: {{ rec.partner_id.country_id.name }}")
        fields = set(node.fields)
        self.assertIn("name", fields)
        self.assertIn("partner_id.country_id.name", fields)
        
        # Loop with nested field access
        node = AliasNode.parse("info", "jinja2", "{% for line in rec.order_lines %}{{ line.product_id.name }}{% endfor %}")
        fields = set(node.fields)
        self.assertIn("order_lines.product_id.name", fields)
        
        # Loop with multiple nested fields
        node = AliasNode.parse("info", "jinja2", "{% for item in rec.items %}{{ item.name }} - {{ item.category_id.name }}{% endfor %}")
        fields = set(node.fields)
        self.assertIn("items.name", fields)
        self.assertIn("items.category_id.name", fields)
        
        # Nested loop with deep nesting
        node = AliasNode.parse("info", "jinja2", "{% for order in rec.orders %}{% for line in order.lines %}{{ line.product_id.name }}{% endfor %}{% endfor %}")
        fields = set(node.fields)
        self.assertIn("orders.lines.product_id.name", fields)

    def test_fields_extraction_jmespath(self):
        """Test fields extraction for JMESPath mode with nested fields."""
        # Simple nested field
        node = AliasNode.parse("data", "jmespath", "{name: rec.partner_id.name}")
        fields = set(node.fields)
        self.assertIn("partner_id.name", fields)
        
        # Multiple nested fields
        node = AliasNode.parse("data", "jmespath", "{name: rec.partner_id.name, email: rec.partner_id.email}")
        fields = set(node.fields)
        self.assertIn("partner_id.name", fields)
        self.assertIn("partner_id.email", fields)
        
        # Deep nested fields
        node = AliasNode.parse("data", "jmespath", "{country: rec.partner_id.country_id.name}")
        fields = set(node.fields)
        self.assertIn("partner_id.country_id.name", fields)
        
        # Array projection with nested fields
        node = AliasNode.parse("data", "jmespath", "rec.order_lines[].{product: product_id.name, qty: quantity}")
        fields = set(node.fields)
        self.assertIn("order_lines.product_id.name", fields)
        self.assertIn("order_lines.quantity", fields)
        
        # Complex nested structure
        node = AliasNode.parse("data", "jmespath", "{customer: rec.partner_id.name, address: {city: rec.partner_id.city, country: rec.partner_id.country_id.name}}")
        fields = set(node.fields)
        self.assertIn("partner_id.name", fields)
        self.assertIn("partner_id.city", fields)
        self.assertIn("partner_id.country_id.name", fields)


@tagged("oql_alias_read", '-at_install', 'post_install')
class TestAliasReading(TransactionCase):
    """Test alias reading functionality with actual records."""

    def setUp(self):
        super().setUp()
        env = self.env
        ensure_model_meta(env)

        # Create test records
        metaProduct = env["ir.model"].search([("model", "=", "test.oql.product")], limit=1)
        
        # Create products
        self.prod_cold = env["test.oql.product"].create({"spu_name": "Cold Boot"})
        self.prod_hot = env["test.oql.product"].create({"spu_name": "Hot Boot"})
        
        # Create attributes and values
        attr_size = env["test.oql.attribute"].create({"name": "Size"})
        for prod in [self.prod_cold, self.prod_hot]:
            for value in ["5", "6", "7"]:
                env["test.oql.attribute.value"].create({
                    "name": value,
                    "product_id": prod.id,
                    "attribute_id": attr_size.id
                })
        
        # Create tags
        self.tag_waterproof = env["test.oql.tag"].create({
            "name": "Waterproof:GTX",
            "tmpl_id": self.prod_cold.tmpl_id.id
        })
        self.tag_hot = env["test.oql.tag"].create({
            "name": "Weather:Hot",
            "tmpl_id": self.prod_hot.tmpl_id.id
        })

    def test_read_field_path(self):
        """Test reading simple field path."""
        node = AliasNode.parse("name", "field", "spu_name")
        result = node.read(self.prod_cold)
        self.assertEqual(result, "Cold Boot")

    def test_read_related_field_path(self):
        """Test reading related field path through inheritance."""
        node = AliasNode.parse("template_name", "field", "tmpl_id.name")
        result = node.read(self.prod_cold)
        self.assertEqual(result, "Cold Boot")

    def test_read_jinja2_template(self):
        """Test reading Jinja2 template."""
        node = AliasNode.parse("info", "jinja2", 'Product: {{ rec.spu_name }}')
        result = node.read(self.prod_cold)
        self.assertEqual(result, "Product: Cold Boot")

    def test_read_jmespath_expression(self):
        """Test reading JMESPath expression."""
        json_str = '{name: rec.spu_name, active: rec.active}'
        node = AliasNode.parse("product_info", "jmespath", json_str)
        result = node.read(self.prod_cold)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["name"], "Cold Boot")
        self.assertEqual(result["active"], True)

    def test_read_one2many_jmespath(self):
        """Test reading One2many field with JMESPath."""
        json_str = 'rec.attribute_value_ids[].{value: name}'
        node = AliasNode.parse("attr_values", "jmespath", json_str)
        result = node.read(self.prod_cold)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        values = {item["value"] for item in result}
        self.assertEqual(values, {"5", "6", "7"})


    def test_read_multiple_records_error(self):
        """Test that reading with multiple records raises error."""
        node = AliasNode.parse("name", "field", "spu_name")
        recs = self.prod_cold | self.prod_hot
        with self.assertRaises(Exception) as context:
            node.read(recs)
        self.assertIn("single", str(context.exception))


@tagged("oql_alias_shorthand", '-at_install', 'post_install')
class TestAliasShorthand(TransactionCase):
    """Test alias shorthand resolution functionality."""

    def setUp(self):
        super().setUp()
        env = self.env
        ensure_model_meta(env)

        metaProduct = env["ir.model"].search([("model", "=", "test.oql.product")], limit=1)
        
        # Create alias rules
        self.rule = env["oql.alias"].create({"model_id": metaProduct.id})
        
        # Add shorthand lines
        env["oql.alias.line"].create({
            "alias": "attrs_records",
            "rule_id": self.rule.id,
            "path": "attribute_value_ids.attribute_id",
            "enable_shorthand": True
        })
        env["oql.alias.line"].create({
            "alias": "tag_records",
            "rule_id": self.rule.id,
            "path": "tag_ids",
            "enable_shorthand": True
        })
        env["oql.alias.line"].create({
            "alias": "tags",
            "rule_id": self.rule.id,
            "path": "tag_ids.name",
            "enable_shorthand": False
        })

        # Create test records
        self.prod_cold = env["test.oql.product"].create({"spu_name": "Cold Boot"})
        self.prod_hot = env["test.oql.product"].create({"spu_name": "Hot Boot"})
        
        attr_size = env["test.oql.attribute"].create({"name": "Size"})
        for prod in [self.prod_cold, self.prod_hot]:
            env["test.oql.attribute.value"].create({
                "name": "5",
                "product_id": prod.id,
                "attribute_id": attr_size.id
            })
        
        self.tag_waterproof = env["test.oql.tag"].create({
            "name": "Waterproof:GTX",
            "tmpl_id": self.prod_cold.tmpl_id.id
        })

    def test_shorthand_resolve_recordset(self):
        """Test shorthand resolution with RecordSet value."""
        from ..alias import AliasRule
        
        rules = AliasRule.from_orm(self.rule)
        self.assertEqual(len(rules), 1)
        
        rule = rules[0]
        
        # Test resolving with attribute RecordSet
        attrs = self.prod_cold.attribute_value_ids.attribute_id
        path = rule.get_path("=", attrs)
        self.assertEqual(path, "attribute_value_ids.attribute_id")
        
        # Test resolving with tag RecordSet
        tags = self.prod_cold.tag_ids
        path = rule.get_path("=", tags)
        self.assertEqual(path, "tag_ids")

    def test_shorthand_no_match(self):
        """Test shorthand with no matching rule."""
        from ..alias import AliasRule
        
        rules = AliasRule.from_orm(self.rule)
        rule = rules[0]
        
        # Try to resolve with incompatible value type
        with self.assertRaises(Exception) as context:
            rule.get_path("=", "string_value")
        self.assertIn("No field path rule found", str(context.exception))

    def test_shorthand_non_shorthand_field(self):
        """Test that non-shorthand fields are not included in rules."""
        from ..alias import AliasRule
        
        rules = AliasRule.from_orm(self.rule)
        rule = rules[0]
        
        # The 'tags' field has enable_shorthand=False, so it should not be in rules
        paths = [line.path for line in rule.lines]
        self.assertNotIn("tag_ids.name", paths)
        self.assertIn("attribute_value_ids.attribute_id", paths)
        self.assertIn("tag_ids", paths)

    def test_shorthand_with_string_value(self):
        """Test shorthand resolution returns None for non-matching types when raises=False."""
        from ..alias import AliasRule
        
        rules = AliasRule.from_orm(self.rule)
        rule = rules[0]
        
        # Should return None instead of raising when raises=False
        path = rule.get_path("=", "string_value", raises=False)
        self.assertIsNone(path)
