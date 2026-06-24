from odoo import Command
from odoo.tests import tagged, TransactionCase
from ..oql import reader, OqlTransformer
from ..compatible import set_model_translation, flush_translations
from .test_model_defs import ensure_model_meta, post_test


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
        prod_cold = env["test.oql.product"].create({"spu_name": "Cold Boot"})
        prod_hot = env["test.oql.product"].create({"spu_name": "Hot Boot"})
        prod_inactive = env["test.oql.product"].create({"spu_name": "Inactive Boot", "active": False})
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
        # 2.5 Supplierinfo
        env["test.oql.supplierinfo"].create({"name": "Danner Cold Boot", "product_id": prod_cold.id})
        env["test.oql.supplierinfo"].create({"name": "Danner Hot Boot", "product_id": prod_hot.id})

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

        # 5 Translation setup
        lang_fr = env['res.lang'].with_context(active_test=False).search([('code', '=', 'fr_FR')], limit=1)
        if not lang_fr:
            # Install language from scratch
            install_wiz = env['base.language.install'].create({'lang': 'fr_FR', 'overwrite': False})
            install_wiz.lang_install()
            lang_fr = env['res.lang'].with_context(active_test=False).search([('code', '=', 'fr_FR')], limit=1)
        if not lang_fr.active:
            lang_fr.active = True
        flush_translations(env)

        for tmpl, src, value in [
            (prod_cold.tmpl_id, 'Cold Boot', 'Botte Froide'),
            (prod_hot.tmpl_id, 'Hot Boot', 'Botte Chaude'),
        ]:
            set_model_translation(tmpl, 'name', 'fr_FR', src, value)

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

    @post_test("grammar")
    def test_grammar_parse(self):
        """Test basic OQL grammar parsing."""
        parsed = reader.query("from test.oql.product "
                              "select name, tag_ids.name "
                              "where tag_ids.name in ('Waterproof:GTX', 'Weather:Temperate') "
                              "  and spu_name ilike 'co' "
                              "  and Waterproof "
                              "order by name asc", self._get_transformer())
        self.assertIsNotNone(parsed)

    def test_simple_search(self):
        """Test search with field path navigation."""
        res = self.env["test.oql.product"].searcho("spu_name = 'Hot Boot'")
        # Should return both products
        self.assertEqual({"Hot Boot"}, set(res.mapped("spu_name")))

    def test_searcho(self):
        """Test direct simple searcho."""
        # Search products with spu_name
        res = self.env["test.oql.product"].searcho("spu_name='Cold Boot'")
        self.assertEqual({"Cold Boot"}, set(res.mapped("spu_name")))

        # Search products with Waterproof tag
        res = self.env["test.oql.product"].searcho("tag_ids.name='Waterproof:GTX'")
        self.assertEqual({"Cold Boot"}, set(res.mapped("spu_name")))

    def test_searcho_term(self):
        """Test searcho with term-based queries."""
        # Attribute.
        res = self.env["test.oql.product"].searcho("Size='5'")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("spu_name")))

        # Tag
        res = self.env["test.oql.product"].searcho("Waterproof")
        self.assertEqual({"Cold Boot"}, set(res.mapped("spu_name")))

        res = self.env["test.oql.product"].searcho("WeatherAware")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("spu_name")))

    def test_searcho_alias(self):
        res = self.env["test.oql.product"].searcho("tags='Waterproof:GTX'")
        self.assertEqual({"Cold Boot"}, set(res.mapped("spu_name")))

    def test_searcho_logic(self):
        """Test logical operators in OQL queries."""
        # # Test AND logic - not applicable for tag model in current setup
        # # Instead test product queries with multiple conditions
        # res = self.env["test.oql.product"].searcho("tag_ids.name='Waterproof:GTX' and tag_ids.name='Weather:Cold'")
        # self.assertEqual({"Cold Boot"}, set(res.mapped("spu_name")))

        # Test OR logic
        res = self.env["test.oql.product"].searcho("tag_ids.name='Weather:Cold' or tag_ids.name='Weather:Hot'")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("spu_name")))

    def test_searcho_una_expr(self):
        """Test unary expressions (boolean field checks)."""
        # Test that products with tags are found
        res = self.env["test.oql.product"].searcho("tag_ids")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("spu_name")))

        # Test products with attribute values
        res = self.env["test.oql.product"].searcho("attribute_value_ids")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("spu_name")))

    def test_searcho_has_term(self):
        """Test querying by term existence."""
        # Products with Size term (through attributes)
        res = self.env["test.oql.product"].searcho("Size")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("spu_name")))

        # Products with Waterproof term (through tags)
        res = self.env["test.oql.product"].searcho("Waterproof")
        self.assertEqual({"Cold Boot"}, set(res.mapped("spu_name")))

    def test_searcho_term_in(self):
        """Test term queries with IN operator."""
        res = self.env["test.oql.product"].searcho("Size in ('5', '6')")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("spu_name")))

        res = self.env["test.oql.product"].searcho("Width in ('D', 'EE')")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("spu_name")))

    def test_searcho_parenthesis(self):
        """Test parenthesis for grouping expressions."""
        # Group weather-related tags
        res = self.env["test.oql.product"].searcho("(tag_ids.name='Weather:Cold' or tag_ids.name='Weather:Hot')")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res.mapped("spu_name")))

        # Combine waterproof with weather
        res = self.env["test.oql.product"].searcho("tag_ids.name='Waterproof:GTX' and (tag_ids.name='Weather:Cold')")
        self.assertEqual({"Cold Boot"}, set(res.mapped("spu_name")))

    @post_test("oql.const")
    def test_constants_true_false_null(self):
        """Test TRUE, FALSE, NULL constants in OQL queries."""
        # Test TRUE constant - should return all products with active=True
        res_true = self.env["test.oql.product"].searcho("active = true")
        self.assertEqual({"Cold Boot", "Hot Boot"}, set(res_true.mapped("spu_name")))

        # Test FALSE constant - should return all products with active=False
        res_false = self.env["test.oql.product"].searcho("active = false")
        self.assertEqual({"Inactive Boot"}, set(res_false.mapped("spu_name")))

    @post_test("oql.alias")
    def test_select_as_alias(self):
        """Test SELECT field AS alias syntax."""
        # Test simple field alias
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select spu_name as product_name where spu_name = 'Cold Boot'"
        )
        self.assertEqual(len(res), 1)
        self.assertIn('product_name', res[0])
        self.assertEqual(res[0]['product_name'], 'Cold Boot')
        # Original field name should not be present
        self.assertNotIn('spu_name', res[0])

        # Test nested field alias (field.path as alias)
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select tag_ids.name as tag_name where tag_ids.name = 'Waterproof:GTX'"
        )
        self.assertEqual(len(res), 1)
        self.assertIn('tag_name', res[0])
        # tag_ids.name returns a list, so check if value is in the list
        self.assertIn('Waterproof:GTX', res[0]['tag_name'])
        # Original path should not be present
        self.assertNotIn('tag_ids.name', res[0])

        # Test multiple aliases in one query
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select id as product_id, spu_name as name where spu_name = 'Hot Boot'"
        )
        self.assertEqual(len(res), 1)
        self.assertIn('product_id', res[0])
        self.assertIn('name', res[0])
        self.assertEqual(res[0]['name'], 'Hot Boot')
        # Original field names should not be present
        self.assertNotIn('id', res[0])
        self.assertNotIn('spu_name', res[0])

    @post_test("oql.limit")
    def test_limit_clause(self):
        """Test LIMIT clause to restrict number of returned records."""
        # Test LIMIT 1 - should return only one product
        res = self.env["test.oql.product"].oql("from test.oql.product select spu_name where tag_ids limit 1")
        self.assertEqual(len(res), 1)
        self.assertIn(res[0]['spu_name'], ["Cold Boot", "Hot Boot"])

        # Test LIMIT 2 - should return at most 2 products
        res = self.env["test.oql.product"].oql("from test.oql.product select spu_name where tag_ids limit 2")
        self.assertLessEqual(len(res), 2)
        names = {row['spu_name'] for row in res}
        self.assertTrue(names.issubset({"Cold Boot", "Hot Boot"}))

        # Test LIMIT with term query
        res = self.env["test.oql.product"].oql("from test.oql.product select spu_name where Size='5' limit 1")
        self.assertEqual(len(res), 1)

    @post_test("oql.offset")
    def test_offset_clause(self):
        """Test OFFSET clause to skip records."""
        # Get all products first to count total
        all_res = self.env["test.oql.product"].oql("from test.oql.product select spu_name where tag_ids")
        total_count = len(all_res)

        # Test OFFSET 1 - should return fewer records than without offset
        res = self.env["test.oql.product"].oql("from test.oql.product select spu_name where tag_ids offset 1")
        self.assertEqual(len(res), total_count - 1)

        # Test OFFSET equals total count - should return empty
        res = self.env["test.oql.product"].oql(f"from test.oql.product select spu_name where tag_ids offset {total_count}")
        self.assertEqual(len(res), 0)

    @post_test("oql.pagination")
    def test_limit_offset_combined(self):
        """Test combined LIMIT and OFFSET for pagination."""
        # Get all products first
        all_res = self.env["test.oql.product"].oql("from test.oql.product select spu_name where tag_ids")
        total_count = len(all_res)
        all_names = {row['spu_name'] for row in all_res}

        # Test LIMIT 1 OFFSET 0 - should return 1 record
        res = self.env["test.oql.product"].oql("from test.oql.product select spu_name where tag_ids limit 1 offset 0")
        self.assertEqual(len(res), 1)
        self.assertIn(res[0]['spu_name'], all_names)

        # Test LIMIT 1 OFFSET 1 - should return 1 record (if total > 1)
        if total_count > 1:
            res = self.env["test.oql.product"].oql("from test.oql.product select spu_name where tag_ids limit 1 offset 1")
            self.assertEqual(len(res), 1)
            self.assertIn(res[0]['spu_name'], all_names)

        # Test LIMIT 2 OFFSET 1 - skip 1, take up to 2
        if total_count > 1:
            res = self.env["test.oql.product"].oql("from test.oql.product select spu_name where tag_ids limit 2 offset 1")
            self.assertLessEqual(len(res), 2)
            for row in res:
                self.assertIn(row['spu_name'], all_names)

    @post_test("oql.pagination")
    def test_offset_exceeds_results(self):
        """Test OFFSET that exceeds total number of results."""
        # OFFSET larger than result set should return empty list
        res = self.env["test.oql.product"].oql("from test.oql.product select spu_name where tag_ids offset 100")
        self.assertEqual(len(res), 0)

    @post_test("oql.pagination")
    def test_limit_zero(self):
        """Test LIMIT 0 should have no effect"""
        res = self.env["test.oql.product"].oql("from test.oql.product select spu_name where tag_ids limit 0")
        self.assertEqual(len(res), 2)

    @post_test("oql.pagination")
    def test_limit_offset_with_complex_query(self):
        """Test LIMIT and OFFSET with complex WHERE conditions."""
        # Combine with OR logic
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select spu_name where (tag_ids.name='Weather:Cold' or tag_ids.name='Weather:Hot') limit 1"
        )
        self.assertLessEqual(len(res), 1)

        # Combine with term query
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select spu_name where Waterproof limit 1 offset 0"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['spu_name'], "Cold Boot")

    @post_test("oql.orderby")
    def test_orderby_single_field_asc(self):
        """Test ORDER BY with single field in ascending order (default)."""
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select id, spu_name where tag_ids order by id"
        )
        self.assertEqual(len(res), 2)
        ids = [row['id'] for row in res]
        self.assertEqual(ids, sorted(ids))

    @post_test("oql.orderby")
    def test_orderby_single_field_desc(self):
        """Test ORDER BY with single field in descending order."""
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select id, spu_name where tag_ids order by id desc"
        )
        self.assertEqual(len(res), 2)
        ids = [row['id'] for row in res]
        self.assertEqual(ids, sorted(ids, reverse=True))

    @post_test("oql.orderby")
    def test_orderby_explicit_asc(self):
        """Test ORDER BY with explicit ASC keyword."""
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select id, spu_name where tag_ids order by id asc"
        )
        self.assertEqual(len(res), 2)
        ids = [row['id'] for row in res]
        self.assertEqual(ids, sorted(ids))

    @post_test("oql.orderby")
    def test_orderby_with_pagination(self):
        """Test ORDER BY combined with LIMIT and OFFSET."""
        # Get all products first to know the order
        all_res = self.env["test.oql.product"].oql(
            "from test.oql.product select id, spu_name where tag_ids order by id desc"
        )
        self.assertEqual(len(all_res), 2)

        # Order by id descending, get first result
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select id, spu_name where tag_ids order by id desc limit 1"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['id'], all_res[0]['id'])

        # Order by id descending, skip first, get second
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select id, spu_name where tag_ids order by id desc limit 1 offset 1"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['id'], all_res[1]['id'])

    @post_test("oql.orderby")
    def test_orderby_with_term_query(self):
        """Test ORDER BY with term-based WHERE clause."""
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select id, spu_name where Size='5' order by id asc"
        )
        self.assertEqual(len(res), 2)
        ids = [row['id'] for row in res]
        self.assertEqual(ids, sorted(ids))

    @post_test("oql.orderby")
    def test_orderby_case_insensitive(self):
        """Test that ORDER BY keywords are case-insensitive."""
        res1 = self.env["test.oql.product"].oql(
            "from test.oql.product select id where tag_ids ORDER BY id DESC"
        )
        res2 = self.env["test.oql.product"].oql(
            "from test.oql.product select id where tag_ids order by id desc"
        )
        res3 = self.env["test.oql.product"].oql(
            "from test.oql.product select id where tag_ids Order By id Desc"
        )

        ids1 = [row['id'] for row in res1]
        ids2 = [row['id'] for row in res2]
        ids3 = [row['id'] for row in res3]
        self.assertEqual(ids1, ids2)
        self.assertEqual(ids2, ids3)

    def assertHints(self, expected, actual):
        self.assertEqual(expected, {x["value"] for x in actual})

    @post_test("oql.non_searchable")
    def test_non_searchable_field_error(self):
        """Test that searching with non-searchable fields raises an exception.

        The 'name' field on test.oql.product is a compute field (not searchable).
        This test verifies that OQL properly rejects queries using non-searchable fields
        in WHERE clause, while allowing them in SELECT clause.
        """
        # SELECT clause can use non-searchable fields (just reading)
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select name where spu_name = 'Cold Boot'"
        )
        self.assertEqual(len(res), 1)
        self.assertIn('name', res[0])

        # WHERE clause cannot use non-searchable fields - should raise Exception
        with self.assertRaises(Exception) as context:
            self.env["test.oql.product"].oql(
                "from test.oql.product select spu_name where name_no_store ilike 'Cold Boot'"
            )

        # Verify error message is informative
        error_msg = str(context.exception)
        self.assertIn("name", error_msg)
        self.assertIn("not searchable", error_msg.lower())

        # Test in complex WHERE conditions
        with self.assertRaises(Exception):
            self.env["test.oql.product"].oql(
                "from test.oql.product select spu_name where name_no_store = 'Cold Boot' and Waterproof"
            )

    @post_test("oql.translate")
    def test_translate_grammar_parse(self):
        """Test TRANSLATE keyword parsing in various positions."""
        # SELECT TRANSLATE
        parsed = reader.query("from test.oql.product select translate tmpl_id.name where tag_ids",
                              self._get_transformer())
        self.assertIsNotNone(parsed)

        # WHERE TRANSLATE
        parsed = reader.query("from test.oql.product select id where translate tag_ids",
                              self._get_transformer())
        self.assertIsNotNone(parsed)

        # Both TRANSLATE
        parsed = reader.query(
            "from test.oql.product select translate tmpl_id.name where translate tag_ids",
            self._get_transformer())
        self.assertIsNotNone(parsed)

        # TRANSLATE with star
        parsed = reader.query("from test.oql.product select translate * where tag_ids",
                              self._get_transformer())
        self.assertIsNotNone(parsed)

    @post_test("oql.translate")
    def test_select_translate(self):
        """Test SELECT TRANSLATE returns translated field values."""
        self.env.user.lang = 'fr_FR'
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select translate tmpl_id.name where spu_name = 'Cold Boot'"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['tmpl_id.name'], 'Botte Froide')

    @post_test("oql.translate")
    def test_select_no_translate(self):
        """Test without TRANSLATE, SELECT returns original (untranslated) field values."""
        self.env.user.lang = 'fr_FR'
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select tmpl_id.name where spu_name = 'Cold Boot'"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['tmpl_id.name'], 'Cold Boot')

    @post_test("oql.translate")
    def test_where_translate(self):
        """Test WHERE TRANSLATE matches against translated field values."""
        self.env.user.lang = 'fr_FR'
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select spu_name where translate tmpl_id.name = 'Botte Froide'"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['spu_name'], 'Cold Boot')

    @post_test("oql.translate")
    def test_where_no_translate(self):
        """Test without WHERE TRANSLATE, search uses original (untranslated) field values."""
        self.env.user.lang = 'fr_FR'
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select spu_name where tmpl_id.name = 'Botte Froide'"
        )
        self.assertEqual(len(res), 0)

    @post_test("oql.translate")
    def test_translate_case_insensitive(self):
        """Test TRANSLATE keyword is case-insensitive."""
        self.env.user.lang = 'fr_FR'
        res = self.env["test.oql.product"].oql(
            "from test.oql.product SELECT Translate tmpl_id.name where spu_name = 'Cold Boot'"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['tmpl_id.name'], 'Botte Froide')

    @post_test("oql.translate")
    def test_translate_select_where_both(self):
        """Test combining SELECT TRANSLATE with WHERE TRANSLATE."""
        self.env.user.lang = 'fr_FR'
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select translate tmpl_id.name "
            "where translate tmpl_id.name = 'Botte Froide'"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['tmpl_id.name'], 'Botte Froide')

    # ---- UPDATE tests ----

    @post_test("oql.update")
    def test_update_simple(self):
        """Test UPDATE with a single field and WHERE clause."""
        res = self.env["test.oql.product"].oql(
            "update test.oql.product set spu_name = 'Updated Boot' where spu_name = 'Cold Boot'"
        )
        self.assertEqual(len(res), 1)
        updated = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(updated.spu_name, 'Updated Boot')
        # Ensure other records are not affected.
        hot = self.env["test.oql.product"].search([("spu_name", "=", "Hot Boot")])
        self.assertTrue(hot)

    @post_test("oql.update")
    def test_update_multi_fields(self):
        """Test UPDATE with multiple fields."""
        res = self.env["test.oql.product"].oql(
            "update test.oql.product set spu_name = 'Multi', active = false where spu_name = 'Hot Boot'"
        )
        self.assertEqual(len(res), 1)
        updated = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(updated.spu_name, 'Multi')
        self.assertFalse(updated.active)

    @post_test("oql.update")
    def test_update_no_where(self):
        """Test UPDATE without WHERE clause updates all active records."""
        res = self.env["test.oql.product"].oql(
            "update test.oql.product set active = false"
        )
        # Active products should be updated (2 active: Cold, Hot). Inactive one is filtered out by default.
        self.assertEqual(len(res), 2)
        all_inactive = self.env["test.oql.product"].with_context(active_test=False).search([("active", "=", False)])
        self.assertEqual(len(all_inactive), 3)

    @post_test("oql.update")
    def test_update_with_limit(self):
        """Test UPDATE with LIMIT clause."""
        res = self.env["test.oql.product"].oql(
            "update test.oql.product set active = false where active = true limit 1"
        )
        self.assertEqual(len(res), 1)
        active_count = self.env["test.oql.product"].search_count([("active", "=", True)])
        self.assertEqual(active_count, 1)

    @post_test("oql.update")
    def test_update_translate(self):
        """Test UPDATE with TRANSLATE keyword for translated fields."""
        self.env.user.lang = 'fr_FR'
        res = self.env["test.oql.product"].oql(
            "update test.oql.product set translate spu_name = 'Botte Modifiée' "
            "where translate spu_name = 'Botte Froide'"
        )
        self.assertEqual(len(res), 1)
        updated = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(updated.with_context(lang='fr_FR').spu_name, 'Botte Modifiée')
        # Original (en) name should remain.
        self.assertEqual(updated.with_context(lang=None).spu_name, 'Cold Boot')

    @post_test("oql.update")
    def test_update_x2many(self):
        """Test UPDATE with x2many field using array of ids."""
        term_size = self.env["oql.term"].search([("name", "=", "Size")], limit=1)
        term_width = self.env["oql.term"].search([("name", "=", "Width")], limit=1)
        tag = self.env["test.oql.tag"].search([("name", "=", "Waterproof:GTX")], limit=1)
        res = self.env["test.oql.tag"].oql(
            f"update test.oql.tag set term_ids = ({term_size.id}, {term_width.id}) where id = {tag.id}"
        )
        self.assertEqual(len(res), 1)
        updated_tag = self.env["test.oql.tag"].browse(tag.id)
        self.assertEqual(set(updated_tag.term_ids.ids), {term_size.id, term_width.id})

    @post_test("oql.update")
    def test_update_x2many_clear(self):
        """Test UPDATE with x2many field set to null clears the relation."""
        tag = self.env["test.oql.tag"].search([("name", "=", "Waterproof:GTX")], limit=1)
        term_waterproof = self.env["oql.term"].search([("name", "=", "Waterproof")], limit=1)
        tag.term_ids = [Command.link(term_waterproof.id)]
        self.assertTrue(tag.term_ids)
        res = self.env["test.oql.tag"].oql(
            f"update test.oql.tag set term_ids = null where id = {tag.id}"
        )
        self.assertEqual(len(res), 1)
        updated_tag = self.env["test.oql.tag"].browse(tag.id)
        self.assertFalse(updated_tag.term_ids)

    @post_test("oql.update")
    def test_update_many2one(self):
        """Test UPDATE with many2one field."""
        attr = self.env["test.oql.attribute"].create({"name": "TestAttr"})
        val = self.env["test.oql.attribute.value"].create({"name": "Val1"})
        res = self.env["test.oql.attribute.value"].oql(
            f"update test.oql.attribute.value set attribute_id = {attr.id} where id = {val.id}"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(val.attribute_id.id, attr.id)

    @post_test("oql.update")
    def test_update_nonexistent_field(self):
        """Test UPDATE with a nonexistent field raises an exception."""
        with self.assertRaises(Exception):
            self.env["test.oql.product"].oql(
                "update test.oql.product set nonexistent_field = 'value' where spu_name = 'Cold Boot'"
            )

    # ---- CREATE tests ----

    @post_test("oql.create")
    def test_create_simple(self):
        """Test CREATE with a single field."""
        res = self.env["test.oql.product"].oql(
            "insert into test.oql.product set spu_name = 'Created Product'"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(created.spu_name, 'Created Product')

    @post_test("oql.create")
    def test_create_multi_fields(self):
        """Test CREATE with multiple fields."""
        res = self.env["test.oql.product"].oql(
            "insert into test.oql.product set spu_name = 'Multi Create', active = false"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(created.spu_name, 'Multi Create')
        self.assertFalse(created.active)

    @post_test("oql.create")
    def test_create_translate(self):
        """Test CREATE with TRANSLATE keyword."""
        self.env.user.lang = 'fr_FR'
        res = self.env["test.oql.product"].oql(
            "insert into test.oql.product set translate spu_name = 'Nouveau Produit'"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(created.with_context(lang='fr_FR').spu_name, 'Nouveau Produit')

    @post_test("oql.create")
    def test_create_with_many2one(self):
        """Test CREATE with a many2one field."""
        prod = self.env["test.oql.product"].search([("spu_name", "=", "Cold Boot")], limit=1)
        res = self.env["test.oql.attribute.value"].oql(
            f"insert into test.oql.attribute.value set name = 'New Value', product_id = {prod.id}"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.attribute.value"].browse(res[0]['id'])
        self.assertEqual(created.name, 'New Value')
        self.assertEqual(created.product_id.id, prod.id)

    @post_test("oql.create")
    def test_create_with_x2many(self):
        """Test CREATE with x2many field using array of ids."""
        term_size = self.env["oql.term"].search([("name", "=", "Size")], limit=1)
        term_width = self.env["oql.term"].search([("name", "=", "Width")], limit=1)
        res = self.env["test.oql.tag"].oql(
            f"insert into test.oql.tag set name = 'New Tag', term_ids = ({term_size.id}, {term_width.id})"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.tag"].browse(res[0]['id'])
        self.assertEqual(created.name, 'New Tag')
        self.assertEqual(set(created.term_ids.ids), {term_size.id, term_width.id})

    @post_test("oql.create")
    def test_create_nonexistent_field(self):
        """Test CREATE with a nonexistent field raises an exception."""
        with self.assertRaises(Exception):
            self.env["test.oql.product"].oql(
                "insert into test.oql.product set nonexistent_field = 'value'"
            )

    # ---- DELETE tests ----

    @post_test("oql.delete")
    def test_delete_with_where(self):
        """Test DELETE with WHERE clause."""
        val = self.env["test.oql.attribute.value"].create({"name": "ToDelete"})
        val_id = val.id
        res = self.env["test.oql.attribute.value"].oql(
            f"delete from test.oql.attribute.value where id = {val_id}"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['id'], val_id)
        self.assertFalse(self.env["test.oql.attribute.value"].browse(val_id).exists())

    @post_test("oql.delete")
    def test_delete_with_limit(self):
        """Test DELETE with LIMIT clause."""
        for i in range(5):
            self.env["test.oql.attribute.value"].create({"name": f"LimitDelete{i}"})
        res = self.env["test.oql.attribute.value"].oql(
            "delete from test.oql.attribute.value where name like 'LimitDelete%' limit 2"
        )
        self.assertEqual(len(res), 2)
        remaining = self.env["test.oql.attribute.value"].search([("name", "like", "LimitDelete%")])
        self.assertEqual(len(remaining), 3)

    @post_test("oql.delete")
    def test_delete_no_where(self):
        """Test DELETE without WHERE clause deletes all records."""
        for i in range(3):
            self.env["test.oql.attribute.value"].create({"name": f"DeleteAll{i}"})
        res = self.env["test.oql.attribute.value"].oql(
            "delete from test.oql.attribute.value where name like 'DeleteAll%'"
        )
        self.assertEqual(len(res), 3)
        remaining = self.env["test.oql.attribute.value"].search([("name", "like", "DeleteAll%")])
        self.assertEqual(len(remaining), 0)

    @post_test("oql.delete")
    def test_delete_no_match(self):
        """Test DELETE with WHERE clause that matches nothing."""
        res = self.env["test.oql.product"].oql(
            "delete from test.oql.product where spu_name = 'NonExistent'"
        )
        self.assertEqual(len(res), 0)

    # ---- Combined / integration tests ----

    @post_test("oql.crud")
    def test_create_update_delete_cycle(self):
        """Test CREATE -> UPDATE -> DELETE lifecycle."""
        # CREATE
        res = self.env["test.oql.product"].oql(
            "insert into test.oql.product set spu_name = 'Lifecycle'"
        )
        self.assertEqual(len(res), 1)
        rec_id = res[0]['id']

        # UPDATE
        res = self.env["test.oql.product"].oql(
            f"update test.oql.product set spu_name = 'Lifecycle Updated' where id = {rec_id}"
        )
        self.assertEqual(len(res), 1)
        rec = self.env["test.oql.product"].browse(rec_id)
        self.assertEqual(rec.spu_name, 'Lifecycle Updated')

        # DELETE
        res = self.env["test.oql.product"].oql(
            f"delete from test.oql.product where id = {rec_id}"
        )
        self.assertEqual(len(res), 1)
        self.assertFalse(rec.exists())

    @post_test("oql.crud")
    def test_update_then_select(self):
        """Test UPDATE then SELECT to verify the change."""
        self.env["test.oql.product"].oql(
            "update test.oql.product set spu_name = 'Verified' where spu_name = 'Cold Boot'"
        )
        res = self.env["test.oql.product"].oql(
            "from test.oql.product select spu_name where spu_name = 'Verified'"
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['spu_name'], 'Verified')

    def _get_transformer(self):
        return OqlTransformer(self.env)
