# -*- coding: utf-8 -*-
# @Time         : 17:35 2026/9/2
# @Author       : Chris
# @Description  :
from odoo import Command
from odoo.tests import tagged, TransactionCase

from .test_model_defs import ensure_model_meta, ensure_model_access


@tagged("oql_update", "-at_install", "post_install")
class TestOqlUpdate(TransactionCase):

    def setUp(self):
        super().setUp()
        env = self.env
        ensure_model_meta(env)
        ensure_model_access(env)

        # 1 Terms for many2many (`test.oql.tag.term_ids`) commands.
        self.term_hot = env["oql.term"].create({"name": "Hot"})
        self.term_cold = env["oql.term"].create({"name": "Cold"})
        self.tag = env["test.oql.tag"].create({"name": "Weather:Warm"})

        # 2 Product with two attribute values for one2many commands.
        self.product = env["test.oql.product"].create({"spu_name": "Cmd Boot"})
        attr_size = env["test.oql.attribute"].create({"name": "Size"})
        self.val_5 = env["test.oql.attribute.value"].create({
            "name": "5", "product_id": self.product.id, "attribute_id": attr_size.id})
        self.val_6 = env["test.oql.attribute.value"].create({
            "name": "6", "product_id": self.product.id, "attribute_id": attr_size.id})

    def test_cmd_link_unlink(self):
        """`[link X, unlink Y]` links `X` and unlinks `Y` on many2many."""
        self.tag.term_ids = [Command.link(self.term_hot.id)]
        self.env["test.oql.tag"].oql(
            f"update test.oql.tag set term_ids = [link {self.term_cold.id}, unlink {self.term_hot.id}] "
            f"where id = {self.tag.id}"
        )
        self.assertEqual(self.term_cold.ids, self.tag.term_ids.ids)

    def test_cmd_create(self):
        """`[create {...}]` creates and links a new record on one2many."""
        self.env["test.oql.product"].oql(
            "update test.oql.product set attribute_value_ids = [create {name: 'Red'}] "
            f"where id = {self.product.id}"
        )
        names = self.product.attribute_value_ids.mapped("name")
        self.assertIn("Red", names)

    def test_cmd_update(self):
        """`[update X {...}]` updates the linked record."""
        self.env["test.oql.product"].oql(
            f"update test.oql.product "
            f"set attribute_value_ids = [update {self.val_5.id} {{name: 'five'}}] "
            f"where id = {self.product.id}"
        )
        self.assertEqual("five", self.val_5.name)

    def test_cmd_delete(self):
        """`[delete X]` unlinks and removes the target record."""
        term = self.env["oql.term"].create({"name": "To Be Deleted"})
        self.tag.term_ids = [Command.link(term.id)]
        self.env["test.oql.tag"].oql(
            f"update test.oql.tag set term_ids = [delete {term.id}] where id = {self.tag.id}"
        )
        self.assertFalse(self.env["oql.term"].browse(term.id).exists())
        self.assertFalse(self.tag.term_ids)

    def test_cmd_set(self):
        """`[set [X, Y]]` replaces the whole many2many relation."""
        self.tag.term_ids = [Command.link(self.term_hot.id)]
        self.env["test.oql.tag"].oql(
            f"update test.oql.tag set term_ids = [set [{self.term_hot.id}, {self.term_cold.id}]] "
            f"where id = {self.tag.id}"
        )
        self.assertEqual({self.term_hot.id, self.term_cold.id}, set(self.tag.term_ids.ids))

    def test_cmd_set_empty_clears(self):
        """`[set []]` clears the many2many relation."""
        self.tag.term_ids = [Command.link(self.term_hot.id), Command.link(self.term_cold.id)]
        self.assertTrue(self.tag.term_ids)
        self.env["test.oql.tag"].oql(
            f"update test.oql.tag set term_ids = [set []] where id = {self.tag.id}"
        )
        self.assertFalse(self.tag.term_ids)

    def test_cmd_mixed(self):
        """Multiple commands in one statement."""
        self.env["test.oql.product"].oql(
            f"update test.oql.product set attribute_value_ids = "
            f"[create {{name: 'Blue'}}, update {self.val_5.id} {{name: 'five'}}, delete {self.val_6.id}] "
            f"where id = {self.product.id}"
        )
        names = set(self.env["test.oql.attribute.value"].search([
            ("product_id", "=", self.product.id)]).mapped("name"))
        self.assertEqual({"five", "Blue"}, names)
