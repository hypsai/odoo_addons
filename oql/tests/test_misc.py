# -*- coding: utf-8 -*-
# @Time         : 17:35 2026/9/2
# @Author       : Chris
# @Description  :
from odoo.tests import tagged, TransactionCase

from .test_model_defs import ensure_model_meta, ensure_model_access


@tagged("oql_misc", "-at_install", "post_install")
class TestOqlMisc(TransactionCase):

    def setUp(self):
        super().setUp()
        env = self.env
        ensure_model_meta(env)
        ensure_model_access(env)
        self.prod_active = env["test.oql.product"].create({"spu_name": "Active Boot"})
        self.prod_archived = env["test.oql.product"].create({"spu_name": "Archived Boot", "active": False})

    def test_ctx_clause_sets_context(self):
        """`with context <key> = <value>` executes the statement under a modified context."""
        # 1 Default: Odoo's `active_test` keeps archived records out.
        plain = self.env["test.oql.product"].oql("from test.oql.product select id")
        self.assertEqual([self.prod_active.id], [r["id"] for r in plain])
        # 2 `with context active_test = false` brings them back.
        with_ctx = self.env["test.oql.product"].oql(
            "with context active_test = false from test.oql.product select id")
        self.assertEqual({self.prod_active.id, self.prod_archived.id}, {r["id"] for r in with_ctx})
