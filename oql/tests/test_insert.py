# -*- coding: utf-8 -*-
# @Time         : 11:47 2026/9/15
# @Author       : Chris
# @Description  :
from odoo.tests import tagged, TransactionCase

from .test_model_defs import ensure_model_meta, ensure_model_access


@tagged("oql_insert", "-at_install", "post_install")
class TestOqlInsert(TransactionCase):

    def setUp(self):
        super().setUp()
        env = self.env
        ensure_model_meta(env)
        ensure_model_access(env)

        # 1 Terms for many2many (`test.oql.tag.term_ids`) commands.
        self.term_hot = env["oql.term"].create({"name": "Hot"})
        self.term_cold = env["oql.term"].create({"name": "Cold"})
        self.term_warm = env["oql.term"].create({"name": "Warm"})

        # 2 Attribute for one2many (`test.oql.product.attribute_value_ids`) commands.
        self.attr_size = env["test.oql.attribute"].create({"name": "Size"})

    # ---- PostgreSQL style ----

    def test_single_field(self):
        """`insert into model (field) values (v)` creates one record."""
        res = self.env["test.oql.product"].oql(
            "insert into test.oql.product (spu_name) values ('SQL Boot')"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(created.spu_name, 'SQL Boot')

    def test_multi_fields(self):
        """`insert` with multiple fields in one row."""
        res = self.env["test.oql.product"].oql(
            "insert into test.oql.product (spu_name, active) values ('SQL Multi', false)"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(created.spu_name, 'SQL Multi')
        self.assertFalse(created.active)

    def test_multi_rows(self):
        """`values (..), (..)` creates one record per row, order preserved."""
        res = self.env["test.oql.product"].oql(
            "insert into test.oql.product (spu_name, active) "
            "values ('SQL Batch A', true), ('SQL Batch B', false)"
        )
        self.assertEqual(len(res), 2)
        recs = self.env["test.oql.product"].browse([x['id'] for x in res])
        self.assertEqual(recs.mapped('spu_name'), ['SQL Batch A', 'SQL Batch B'])
        self.assertEqual(recs.mapped('active'), [True, False])

    def test_trailing_commas(self):
        """Trailing commas are allowed in both the field list and the value row."""
        res = self.env["test.oql.product"].oql(
            "insert into test.oql.product (spu_name,) values ('Trailing Comma',)"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(created.spu_name, 'Trailing Comma')

    def test_string_escaping(self):
        """`''` inside a string escapes a single quote."""
        res = self.env["test.oql.tag"].oql(
            "insert into test.oql.tag (name) values ('It''s Escaped')"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.tag"].browse(res[0]['id'])
        self.assertEqual(created.name, "It's Escaped")

    def test_bool_null_values(self):
        """`true` / `false` / `null` constants as values."""
        res = self.env["test.oql.tag"].oql(
            "insert into test.oql.tag (name, tmpl_id) values ('Null Template', null)"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.tag"].browse(res[0]['id'])
        self.assertFalse(created.tmpl_id)

    def test_many2one_id(self):
        """A many2one field takes a plain id."""
        tmpl = self.env["test.oql.template"].create({"name": "SQL Template"})
        res = self.env["test.oql.tag"].oql(
            f"insert into test.oql.tag (name, tmpl_id) values ('SQL Tag', {tmpl.id})"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.tag"].browse(res[0]['id'])
        self.assertEqual(created.tmpl_id.id, tmpl.id)

    def test_translate(self):
        """`insert into model translate (...) values (...)` writes in the user's lang."""
        # fr_FR must be activated in res.lang before it can be set as user lang.
        self.env['res.lang']._activate_lang('fr_FR')
        self.env.user.lang = 'fr_FR'
        res = self.env["test.oql.product"].oql(
            "insert into test.oql.product translate (spu_name) values ('Botte SQL')"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(created.with_context(lang='fr_FR').spu_name, 'Botte SQL')

    def test_x2many_sql_array(self):
        """`(id, id)` SQL array links existing records on an x2many field."""
        res = self.env["test.oql.tag"].oql(
            f"insert into test.oql.tag (name, term_ids) "
            f"values ('SQL Array Tag', ({self.term_hot.id}, {self.term_cold.id}))"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.tag"].browse(res[0]['id'])
        self.assertEqual({self.term_hot.id, self.term_cold.id}, set(created.term_ids.ids))

    def test_row_length_mismatch(self):
        """A value row must hold as many values as the field list."""
        with self.assertRaises(ValueError):
            self.env["test.oql.product"].oql(
                "insert into test.oql.product (spu_name, active) values ('Only Name')"
            )

    def test_nonexistent_field(self):
        """A nonexistent field in the field list raises an exception."""
        with self.assertRaises(Exception):
            self.env["test.oql.product"].oql(
                "insert into test.oql.product (nonexistent_field) values ('value')"
            )

    # ---- Odoo x2many command style ----

    def test_cmd_link(self):
        """`[link X, link Y]` links existing records on many2many."""
        res = self.env["test.oql.tag"].oql(
            f"insert into test.oql.tag (name, term_ids) "
            f"values ('Cmd Tag', [link {self.term_hot.id}, link {self.term_cold.id}])"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.tag"].browse(res[0]['id'])
        self.assertEqual({self.term_hot.id, self.term_cold.id}, set(created.term_ids.ids))

    def test_cmd_link_one2many(self):
        """`[link X]` on one2many sets the inverse field of the linked record."""
        val = self.env["test.oql.attribute.value"].create({"name": "Loose Value"})
        res = self.env["test.oql.product"].oql(
            f"insert into test.oql.product (spu_name, attribute_value_ids) "
            f"values ('Cmd Link O2M', [link {val.id}])"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(val.ids, created.attribute_value_ids.ids)
        self.assertEqual(val.product_id.id, created.id)

    def test_cmd_create(self):
        """`[create {...}]` creates and links new records on one2many."""
        res = self.env["test.oql.product"].oql(
            f"insert into test.oql.product (spu_name, attribute_value_ids) "
            f"values ('Cmd Create', [create {{name: 'Red', attribute_id: {self.attr_size.id}}}])"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual(created.attribute_value_ids.mapped('name'), ['Red'])
        self.assertEqual(created.attribute_value_ids.attribute_id.id, self.attr_size.id)

    def test_cmd_create_many2many(self):
        """`[create {...}]` creates and links a new record on many2many."""
        res = self.env["test.oql.tag"].oql(
            "insert into test.oql.tag (name, term_ids) "
            "values ('Cmd Create M2M', [create {name: 'Newborn Term'}])"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.tag"].browse(res[0]['id'])
        self.assertEqual(created.term_ids.mapped('name'), ['Newborn Term'])

    def test_cmd_set(self):
        """`[set [X, Y]]` replaces the whole many2many relation."""
        res = self.env["test.oql.tag"].oql(
            f"insert into test.oql.tag (name, term_ids) "
            f"values ('Cmd Set Tag', [set [{self.term_hot.id}, {self.term_cold.id}]])"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.tag"].browse(res[0]['id'])
        self.assertEqual({self.term_hot.id, self.term_cold.id}, set(created.term_ids.ids))

    def test_cmd_empty_array(self):
        """`[]` as an x2many value links nothing."""
        res = self.env["test.oql.tag"].oql(
            "insert into test.oql.tag (name, term_ids) values ('Empty Array Tag', [])"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.tag"].browse(res[0]['id'])
        self.assertFalse(created.term_ids)

    def test_cmd_mixed(self):
        """Multiple commands mixed in one array value."""
        val = self.env["test.oql.attribute.value"].create({"name": "Loose Mixed"})
        res = self.env["test.oql.product"].oql(
            f"insert into test.oql.product (spu_name, attribute_value_ids) "
            f"values ('Cmd Mixed', "
            f"[create {{name: 'Blue', attribute_id: {self.attr_size.id}}}, link {val.id}])"
        )
        self.assertEqual(len(res), 1)
        created = self.env["test.oql.product"].browse(res[0]['id'])
        self.assertEqual({"Blue", "Loose Mixed"}, set(created.attribute_value_ids.mapped('name')))

    def test_cmd_multi_rows(self):
        """Each value row carries its own command array."""
        res = self.env["test.oql.tag"].oql(
            f"insert into test.oql.tag (name, term_ids) "
            f"values ('Row Hot', [link {self.term_hot.id}]), "
            f"       ('Row Cold', [link {self.term_cold.id}])"
        )
        self.assertEqual(len(res), 2)
        hot = self.env["test.oql.tag"].browse(res[0]['id'])
        cold = self.env["test.oql.tag"].browse(res[1]['id'])
        self.assertEqual(hot.term_ids.ids, self.term_hot.ids)
        self.assertEqual(cold.term_ids.ids, self.term_cold.ids)
