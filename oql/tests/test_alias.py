# -*- coding: utf-8 -*-
# @Time         : 21:56 2026/5/15
# @Author       : Chris
# @Description  : Test cases for OQL Alias functionality

from odoo import Command
from odoo.tests import tagged, TransactionCase
from ..alias import AliasNode, AliasFieldPath, AliasDict, AliasString
from .test_model_defs import ensure_model_meta


@tagged("oql_alias", '-at_install', 'post_install')
class TestAliasParsing(TransactionCase):
    """Test alias parsing functionality."""

    def setUp(self):
        super().setUp()
        ensure_model_meta(self.env)

    def test_parse_dot_path(self):
        """Test parsing simple dot path."""
        node = AliasNode.parse("partner_id.name", "partner_name")
        self.assertIsInstance(node, AliasFieldPath)
        self.assertEqual(node.field, "partner_id.name")
        self.assertEqual(node.alias, "partner_name")
        self.assertFalse(node.is_complex)

    def test_parse_string_template(self):
        """Test parsing string template."""
        node = AliasNode.parse('Name is {partner_id.name}', "partner_info")
        self.assertIsInstance(node, AliasString)
        self.assertEqual(node.tmpl, 'Name is {partner_id.name}')
        self.assertEqual(node.alias, "partner_info")
        self.assertTrue(node.is_complex)

    def test_parse_json_object(self):
        """Test parsing JSON object with nested structure."""
        json_str = '{"name": "partner_id.name", "city": "partner_id.city_id.name"}'
        node = AliasNode.parse(json_str, "partner_data")
        self.assertIsInstance(node, AliasDict)
        self.assertEqual(node.alias, "partner_data")
        self.assertTrue(node.is_complex)
        self.assertIn("name", node.alias2child)
        self.assertIn("city", node.alias2child)

    def test_parse_expand_with_dot_path(self):
        """Test parsing expand prefix with dot path."""
        node = AliasNode.parse("address_ids => country_id.name", "country")
        self.assertIsInstance(node, AliasFieldPath)
        self.assertEqual(node.path, "address_ids")
        self.assertEqual(node.field, "country_id.name")
        self.assertEqual(node.alias, "country")

    def test_parse_expand_with_string_template(self):
        """Test parsing expand prefix with string template."""
        node = AliasNode.parse('address_ids => "Address: {city}"', "addr_info")
        self.assertIsInstance(node, AliasString)
        self.assertEqual(node.path, "address_ids")
        self.assertEqual(node.alias, "addr_info")

    def test_parse_expand_with_json(self):
        """Test parsing expand prefix with JSON object."""
        json_str = 'address_ids => {"city": "city", "country": "country_id.name"}'
        node = AliasNode.parse(json_str, "addresses")
        self.assertIsInstance(node, AliasDict)
        self.assertEqual(node.path, "address_ids")
        self.assertEqual(node.alias, "addresses")
        self.assertIn("city", node.alias2child)
        self.assertIn("country", node.alias2child)

    def test_parse_json_with_at_syntax(self):
        """Test parsing JSON with @ syntax for relational expansion."""
        json_str = '''{
            "name": "partner_id.name",
            "addresses @ address_ids": {
                "city": "city",
                "country": "country_id.name"
            }
        }'''
        node = AliasNode.parse(json_str, "partner_full")
        self.assertIsInstance(node, AliasDict)
        self.assertIn("name", node.alias2child)
        self.assertIn("addresses", node.alias2child)
        
        # Check nested structure
        addresses_node = node.alias2child["addresses"]
        self.assertIsInstance(addresses_node, AliasDict)
        self.assertEqual(addresses_node.path, "address_ids")
        self.assertIn("city", addresses_node.alias2child)
        self.assertIn("country", addresses_node.alias2child)

    def test_parse_invalid_json_key(self):
        """Test parsing invalid JSON key with multiple @ symbols."""
        with self.assertRaises(Exception) as context:
            AliasNode.parse('{"a @ b @ c": "value"}', "alias")
        self.assertIn("Invalid complex alias key", str(context.exception))


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
        node = AliasNode.parse("spu_name", "name")
        result = node.read(self.prod_cold)
        self.assertEqual(result, "Cold Boot")

    def test_read_related_field_path(self):
        """Test reading related field path through inheritance."""
        node = AliasNode.parse("tmpl_id.name", "template_name")
        result = node.read(self.prod_cold)
        self.assertEqual(result, "Cold Boot")

    def test_read_string_template(self):
        """Test reading string template."""
        node = AliasNode.parse('"Product: {spu_name}"', "info")
        result = node.read(self.prod_cold)
        self.assertEqual(result, "Product: Cold Boot")

    def test_read_json_dict(self):
        """Test reading JSON dict alias."""
        json_str = '{"name": "spu_name", "active": "active"}'
        node = AliasNode.parse(json_str, "product_info")
        result = node.read(self.prod_cold)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["name"], "Cold Boot")
        self.assertEqual(result["active"], True)

    def test_read_one2many_expansion(self):
        """Test reading One2many field expansion."""
        json_str = 'attribute_value_ids => {"value": "name"}'
        node = AliasNode.parse(json_str, "attr_values")
        result = node.read(self.prod_cold)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        values = {item["value"] for item in result}
        self.assertEqual(values, {"5", "6", "7"})

    def test_read_nested_json_with_at(self):
        """Test reading nested JSON with @ syntax."""
        json_str = '''{
            "product_name": "spu_name",
            "tags @ tag_ids": {
                "tag_name": "name"
            }
        }'''
        node = AliasNode.parse(json_str, "product_with_tags")
        result = node.read(self.prod_cold)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result["product_name"], "Cold Boot")
        self.assertIsInstance(result["tags"], list)
        self.assertEqual(len(result["tags"]), 1)
        self.assertEqual(result["tags"][0]["tag_name"], "Waterproof:GTX")

    def test_read_multiple_records_error(self):
        """Test that reading with multiple records raises error."""
        node = AliasNode.parse("spu_name", "name")
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
