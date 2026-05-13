from odoo import Command
from odoo.tests import tagged, TransactionCase
from ..oql import reader, OqlTransformer
from .test_model_defs import ensure_model_meta


@tagged("oql_query", '-at_install', 'post_install')
class TestOql(TransactionCase):

    def setUp(self):
        super().setUp()
        env = self.env

        # 1 Load model meta.
        ensure_model_meta(env)
        metaProduct = env["ir.model"].search([("model", "=", "test.oql.product")], limit=1)
        metaAttribute = env["ir.model"].search([("model", "=", "test.oql.attribute")], limit=1)
        metaTag = env["ir.model"].search([("model", "=", "test.oql.tag")], limit=1)

        # 2 Create test records.
        # 2.1 Product
        prod_cold = env["test.oql.product"].create({"name": "Cold Boot"})
        prod_hot = env["test.oql.product"].create({"name": "Hot Boot"})
        prod_inactive = env["test.oql.product"].create({"name": "Inactive Boot", "active": False})
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
        tag_waterproof = env["test.oql.tag"].create({"name": "Waterproof:GTX", "tmpl_id": prod_cold.tmpl_id.id})
        tag_temperate = env["test.oql.tag"].create({"name": "Weather:Cold", "tmpl_id": prod_cold.tmpl_id.id})
        tag_hot = env["test.oql.tag"].create({"name": "Weather:Hot", "tmpl_id": prod_hot.tmpl_id.id})

        # 3 Terms
        # 3.1 Attr
        term_size = env["oql.term"].create({"name": "Size"})
        term_width = env["oql.term"].create({"name": "Width"})
        attr_size.term_ids = [Command.link(term_size.id)]
        attr_width.term_ids = [Command.link(term_width.id)]
        # 3.2 Tag
        term_hot = self._create("oql.term", {"name": "Hot"}, "name")
        term_waterproof = self._create("oql.term", {"name": "Waterproof"}, "name")
        term_weather = self._create("oql.term", {"name": "WeatherAware"}, "name")
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

    def _create(self, model: str, data: dict, key_field: str = None):
        Model = self.env[model]
        if key_field:
            key_value = data.get(key_field)
            if key_value is None:
                raise ValueError(f"Missing `{key_field}` from `{data}`.")
            recs = Model.search([(key_field, "=", key_value)], limit=1)
            if recs:
                return recs
        return Model.create(data)

    def tearDown(self):
        super().tearDown()

    @tagged("grammar")
    def test_grammar_parse(self):
        """Test basic OQL grammar parsing."""
        parsed = reader.query("from test.oql.product "
                              "select name, tag_ids.name "
                              "where tag_ids.name in ('Waterproof:GTX', 'Weather:Temperate') "
                              "  and name ilike 'co' "
                              "  and Waterproof", self._get_transformer())
        self.assertIsNotNone(parsed)

    def test_simple_search(self):
        """Test search with field path navigation."""
        res = self.env["test.oql.product"].searcho("name = 'Hot Boot'")
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
        # # Test AND logic - not applicable for tag model in current setup
        # # Instead test product queries with multiple conditions
        # res = self.env["test.oql.product"].searcho("tag_ids.name='Waterproof:GTX' and tag_ids.name='Weather:Cold'")
        # self.assertEqual({"Cold Boot"}, set(res.mapped("name")))

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

    @tagged("oql.const")
    def test_constants_true_false_null(self):
        """Test TRUE, FALSE, NULL constants in OQL queries."""
        # Test TRUE constant - should return all products with active=True
        res_true = self.env["test.oql.product"].searcho("active = true")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res_true.mapped("name")))

        # Test FALSE constant - should return all products with active=False
        res_false = self.env["test.oql.product"].searcho("active = false")
        self.assertEqual({"Inactive Boot"}, set(res_false.mapped("name")))

    @tagged("oql.limit")
    def test_limit_clause(self):
        """Test LIMIT clause to restrict number of returned records."""
        # Test LIMIT 1 - should return only one product
        res = self.env["test.oql.product"].oql("from test.oql.product select name where tag_ids limit 1")
        self.assertEqual(len(res), 1)
        self.assertIn(res[0]['name'], ["Cold Boot", "Hot Boot"])

        # Test LIMIT 2 - should return at most 2 products
        res = self.env["test.oql.product"].oql("from test.oql.product select name where tag_ids limit 2")
        self.assertLessEqual(len(res), 2)
        names = {row['name'] for row in res}
        self.assertTrue(names.issubset({"Cold Boot", "Hot Boot"}))

        # Test LIMIT with term query
        res = self.env["test.oql.product"].oql("from test.oql.product select name where Size='5' limit 1")
        self.assertEqual(len(res), 1)

    @tagged("oql.offset")
    def test_offset_clause(self):
        """Test OFFSET clause to skip records."""
        # Get all products first to count total
        all_res = self.env["test.oql.product"].oql("from test.oql.product select name where tag_ids")
        total_count = len(all_res)

        # Test OFFSET 1 - should return fewer records than without offset
        res = self.env["test.oql.product"].oql("from test.oql.product select name where tag_ids offset 1")
        self.assertEqual(len(res), total_count - 1)

        # Test OFFSET equals total count - should return empty
        res = self.env["test.oql.product"].oql(f"from test.oql.product select name where tag_ids offset {total_count}")
        self.assertEqual(len(res), 0)

    @tagged("oql.pagination")
    def test_limit_offset_combined(self):
        """Test combined LIMIT and OFFSET for pagination."""
        # Get all products first
        all_res = self.env["test.oql.product"].oql("from test.oql.product select name where tag_ids")
        total_count = len(all_res)
        all_names = {row['name'] for row in all_res}

        # Test LIMIT 1 OFFSET 0 - should return 1 record
        res = self.env["test.oql.product"].oql("from test.oql.product select name where tag_ids limit 1 offset 0")
        self.assertEqual(len(res), 1)
        self.assertIn(res[0]['name'], all_names)

        # Test LIMIT 1 OFFSET 1 - should return 1 record (if total > 1)
        if total_count > 1:
            res = self.env["test.oql.product"].oql("from test.oql.product select name where tag_ids limit 1 offset 1")
            self.assertEqual(len(res), 1)
            self.assertIn(res[0]['name'], all_names)

        # Test LIMIT 2 OFFSET 1 - skip 1, take up to 2
        if total_count > 1:
            res = self.env["test.oql.product"].oql("from test.oql.product select name where tag_ids limit 2 offset 1")
            self.assertLessEqual(len(res), 2)
            for row in res:
                self.assertIn(row['name'], all_names)

    @tagged("oql.pagination")
    def test_offset_exceeds_results(self):
        """Test OFFSET that exceeds total number of results."""
        # OFFSET larger than result set should return empty list
        res = self.env["test.oql.product"].oql("from test.oql.product select name where tag_ids offset 100")
        self.assertEqual(len(res), 0)

    @tagged("oql.pagination")
    def test_limit_zero(self):
        """Test LIMIT 0 should have no effect"""
        res = self.env["test.oql.product"].oql("from test.oql.product select name where tag_ids limit 0")
        self.assertEqual(len(res), 2)

    @tagged("oql.pagination")
    def test_limit_offset_with_complex_query(self):
        """Test LIMIT and OFFSET with complex WHERE conditions."""
        # Combine with OR logic
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select name where (tag_ids.name='Weather:Cold' or tag_ids.name='Weather:Hot') limit 1"
        )
        self.assertLessEqual(len(res), 1)

        # Combine with term query
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select name where Waterproof limit 1 offset 0"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['name'], "Cold Boot")

    def assertHints(self, expected, actual):
        self.assertEqual(expected, {x["value"] for x in actual})

    def _get_transformer(self):
        return OqlTransformer(self.env)
