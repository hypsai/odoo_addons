from odoo import Command
from odoo.tests import tagged, TransactionCase
from ..oql import reader, OqlTransformer
from .test_model_defs import ensure_model_meta


@tagged("oql", '-at_install', 'post_install')
class TestOql(TransactionCase):

    def setUp(self):
        super().setUp()
        env = self.env

        # 1 Load model meta.
        ensure_model_meta(env, ['test.oql.product', 'test.oql.attribute', 'test.oql.attribute.value', 'test.oql.tag'])
        metaProduct = env["ir.model"].search([("model", "=", "test.oql.product")], limit=1)
        metaAttribute = env["ir.model"].search([("model", "=", "test.oql.attribute")], limit=1)
        metaTag = env["ir.model"].search([("model", "=", "test.oql.tag")], limit=1)

        # 2 Create test records.
        # 2.1 Product
        prod_cold = env["test.oql.product"].create({"name": "Cold Boot"})
        prod_hot = env["test.oql.product"].create({"name": "Hot Boot"})
        # 2.2 Attribute
        attr_size = env["test.oql.attribute"].create({"name": "Size"})
        attr_width = env["test.oql.attribute"].create({"name": "Width"})
        # 2.3 Attribute Value
        for prod in [prod_cold, prod_hot]:
            for attr, values in [(attr_size, ["5", "6", "7"]),
                                 (attr_width, ["D", "EE"])]:
                for value in values:
                    env["test.oql.attribute.value"].create({
                        "name": value,
                        "product_id": prod.id,
                        "attribute_id": attr.id})
        # 2.4 Tag
        tag_waterproof = env["test.oql.tag"].create({"name": "Waterproof:GTX", "product_id": prod_cold.id})
        tag_temperate = env["test.oql.tag"].create({"name": "Weather:Cold", "product_id": prod_cold.id})
        tag_hot = env["test.oql.tag"].create({"name": "Weather:Hot", "product_id": prod_hot.id})

        # 3 Terms
        # 3.1 Attr
        term_size = env["oql.term"].create({"name": "Size"})
        term_width = env["oql.term"].create({"name": "Width"})
        attr_size.term_ids = [Command.link(term_size.id)]
        attr_width.term_ids = [Command.link(term_width.id)]
        # 3.2 Tag
        term_hot = env["oql.term"].create({"name": "Hot"})
        term_waterproof = env["oql.term"].create({"name": "Waterproof"})
        term_weather = env["oql.term"].create({"name": "WeatherAware"})
        term_weather_domain = env["oql.term.domain"].create({
            "name": "WeatherSelector",
            "term_id": term_weather.id,
            "model_id": metaTag.id,
            "domain": "[('name', '=like', 'Weather:%')]"
        })
        tag_hot.term_ids = [Command.link(term_hot.id)]
        tag_waterproof.term_ids = [Command.link(term_waterproof.id)]

        # 4 Alias rules.
        rule1 = env["oql.alias"].create({"model_id": metaProduct.id})
        line1 = env["oql.alias.line"].create({"alias": "attr_val_records", "rule_id": rule1.id, "path": "attribute_value_ids", 'enable_shorthand': True})
        line3 = env["oql.alias.line"].create({"alias": "attrs_records", "rule_id": rule1.id, "path": "attribute_value_ids.attribute_id", 'enable_shorthand': True})
        line2 = env["oql.alias.line"].create({"alias": "tag_records", "rule_id": rule1.id, "path": "tag_ids", 'enable_shorthand': True})
        line3 = env["oql.alias.line"].create({"alias": "tags", "rule_id": rule1.id, "path": "tag_ids.name", 'enable_shorthand': False})

    def tearDown(self):
        super().tearDown()

    def test_grammar_parse(self):
        """Test basic OQL grammar parsing."""
        parsed = reader.query("tag_ids.name = 'Waterproof:GTX'", self._get_transformer())
        self.assertIsNotNone(parsed)

    def test_simple_search(self):
        """Test search with field path navigation."""
        res = reader.query("name = 'Hot Boot'", self._get_transformer())
        # Should return both products
        self.assertEqual({"Hot Boot"}, set(res.mapped("name")))

    def test_searcho(self):
        """Test direct simple searcho."""
        # Search products with name
        res = self.env["test.oql.product"].searcho("name='Cold Boot'")
        self.assertEqual({"Cold Boot"}, set(res.mapped("name")))

        # Search products with Waterproof tag
        res = self.env["test.oql.product"].searcho("tag_ids.name='Waterproof:GTX'")
        self.assertEqual({"Cold Boot"}, set(res.mapped("name")))

    def test_searcho_term(self):
        """Test searcho with term-based queries."""
        # Attribute.
        res = self.env["test.oql.product"].searcho("Size='5'")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("name")))

        # Tag
        res = self.env["test.oql.product"].searcho("Waterproof")
        self.assertEqual({"Cold Boot"}, set(res.mapped("name")))

        res = self.env["test.oql.product"].searcho("WeatherAware")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("name")))

    def test_searcho_alias(self):
        res = self.env["test.oql.product"].searcho("tags='Waterproof:GTX'")
        self.assertEqual({"Cold Boot"}, set(res.mapped("name")))

    def test_searcho_logic(self):
        """Test logical operators in OQL queries."""
        # Test AND logic - not applicable for tag model in current setup
        # Instead test product queries with multiple conditions
        res = self.env["test.oql.product"].searcho("tag_ids.name='Waterproof:GTX' and tag_ids.name='Weather:Cold'")
        self.assertEqual({"Cold Boot"}, set(res.mapped("name")))
        
        # Test OR logic
        res = self.env["test.oql.product"].searcho("tag_ids.name='Weather:Cold' or tag_ids.name='Weather:Hot'")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("name")))

    def test_searcho_una_expr(self):
        """Test unary expressions (boolean field checks)."""
        # Test that products with tags are found
        res = self.env["test.oql.product"].searcho("tag_ids")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("name")))
        
        # Test products with attribute values
        res = self.env["test.oql.product"].searcho("attribute_value_ids")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("name")))

    def test_searcho_has_term(self):
        """Test querying by term existence."""
        # Products with Size term (through attributes)
        res = self.env["test.oql.product"].searcho("Size")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("name")))
        
        # Products with Waterproof term (through tags)
        res = self.env["test.oql.product"].searcho("Waterproof")
        self.assertEqual({"Cold Boot"}, set(res.mapped("name")))

    def test_searcho_term_in(self):
        """Test term queries with IN operator."""
        res = self.env["test.oql.product"].searcho("Size in ('5', '6')")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("name")))
        
        res = self.env["test.oql.product"].searcho("Width in ('D', 'EE')")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("name")))

    def test_searcho_parenthesis(self):
        """Test parenthesis for grouping expressions."""
        # Group weather-related tags
        res = self.env["test.oql.product"].searcho("(tag_ids.name='Weather:Cold' or tag_ids.name='Weather:Hot')")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("name")))
        
        # Combine waterproof with weather
        res = self.env["test.oql.product"].searcho("tag_ids.name='Waterproof:GTX' and (tag_ids.name='Weather:Cold')")
        self.assertEqual({"Cold Boot"}, set(res.mapped("name")))

    def assertHints(self, expected, actual):
        self.assertEqual(expected, {x["value"] for x in actual})

    def _get_transformer(self):
        return OqlTransformer(self.env, "test.oql.product")
