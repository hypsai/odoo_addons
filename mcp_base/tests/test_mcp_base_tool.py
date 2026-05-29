# -*- coding: utf-8 -*-
"""Unit tests for the ``mcp.base.tool`` ORM model."""
import json
import logging

from odoo.tests import common, tagged

_logger = logging.getLogger(__name__)


@tagged('mcp_base', 'post_install', '-at_install')
class TestMcpBaseToolORM(common.TransactionCase):
    """Exercise the mcp.base.tool model directly (no HTTP)."""

    def setUp(self):
        super().setUp()
        self.IrModel = self.env['ir.model']
        self.Tool = self.env['mcp.base.tool']

        # Ensure test model metadata exists.
        self._ensure_test_model('test.mcp.base.tool', 'MCP Tool Test')

    def _ensure_test_model(self, model_name, description):
        """Create an ir.model record if it doesn't already exist."""
        existing = self.IrModel.search([('model', '=', model_name)], limit=1)
        if existing:
            return existing
        return self.IrModel.create({
            'model': model_name,
            'name': description,
            'state': 'base',
        })

    def _get_model(self, model_name='test.mcp.base.tool'):
        """Return ir.model for *model_name*."""
        return self._ensure_test_model(model_name, model_name)

    def _get_code_first_tool(self, method_name, model=None):
        """Fetch the code-first tool for *method_name* on *model* (created by post_init_hook)."""
        if model is None:
            model = self._get_model()
        tool = self.Tool.search([
            ('model_id', '=', model.id),
            ('method_id.name', '=', method_name),
            ('is_code_first', '=', True),
        ], limit=1)
        self.assertTrue(tool, f'Code-first tool for {method_name} should exist after post_init_hook')
        return tool

    def _create_tool(self, method, **overrides):
        """Create a basic config-first tool record."""
        model = self._get_model()
        method_ref = self.env['mcp.base.method'].search([
            ('name', '=', method),
            ('model_id', '=', model.id),
        ], limit=1)
        if not method_ref:
            method_ref = self.env['mcp.base.method'].create({
                'name': method,
                'model_id': model.id,
            })
        vals = {
            'name': f'Tool {method}',
            'model_id': model.id,
            'method_id': method_ref.id,
            'docstring': '',
            'is_code_first': False,
        }
        vals.update(overrides)
        return self.Tool.create(vals)

    # ── basic CRUD ─────────────────────────────────────────────────────

    def test_create_config_first_tool(self):
        """A config-first tool can be created with a docstring."""
        # cfg_ prefix: non-@mcp_tool name to avoid collisions with
        # code-first tools created by _sync_tools_from_registry().
        rec = self._create_tool(
            'cfg_get_customers',
            docstring='Get all customers.\n\n:return: list of customers',
        )
        self.assertTrue(rec.description, 'Description should be computed from docstring')
        self.assertIn('customers', rec.description.lower())
        self.assertTrue(rec.input_schema, 'inputSchema should be computed')
        self.assertFalse(rec.is_code_first)

    def test_code_first_tool_from_hook(self):
        """post_init_hook syncs @mcp_tool methods — verify metadata is computed."""
        rec = self._get_code_first_tool('get_customer_detail')
        self.assertTrue(rec.is_code_first)
        self.assertTrue(rec.description)
        self.assertIn('customer', rec.description.lower())
        schema = json.loads(rec.input_schema)
        self.assertIsNotNone(schema)
        self.assertIn('name', schema.get('properties', {}))

    def test_code_first_hook_updates_on_sync(self):
        """Re-syncing a code-first tool updates computed fields from docstring."""
        rec = self._get_code_first_tool('get_customers')
        rec.docstring = 'Get all customers.\n\n:return: list of customers'
        rec.write({'docstring': rec.docstring})
        self.assertIn('customers', rec.description.lower())

    def test_active_filtering(self):
        """Inactive tools can be hidden."""
        rec = self._create_tool('cfg_get_customers')
        self.assertTrue(rec.active)
        active = self.Tool.search([('active', '=', True), ('id', '=', rec.id)])
        self.assertTrue(active)
        rec.active = False
        inactive = self.Tool.search([('active', '=', True), ('id', '=', rec.id)])
        self.assertFalse(inactive)

    # ── uniqueness constraint ───────────────────────────────────────────

    def test_unique_model_method(self):
        """Each (model_id, method) pair must be unique."""
        # Use a non-@mcp_tool method name to avoid collisions with
        # _sync_tools_from_registry() which creates code-first tools for
        # all decorated methods across the entire registry.
        self._create_tool('config_unique_test')
        # _sql_constraints violations may surface as psycopg2.UniqueViolation
        # (raw) or odoo.exceptions.ValidationError depending on Odoo version.
        # The raw psycopg2 error aborts the current transaction, which poisons
        # the outer TransactionCase savepoint.  Nest a savepoint here so we
        # can roll back to it *after* catching the expected exception, keeping
        # the outer transaction clean for subsequent tests.
        self.env.cr.execute('SAVEPOINT test_unique_model_method')
        try:
            with self.assertRaises(Exception):
                self._create_tool('config_unique_test')
        finally:
            self.env.cr.execute(
                'ROLLBACK TO SAVEPOINT test_unique_model_method')

    def test_same_method_different_model(self):
        """Same method name on different models is allowed."""
        model1 = self._ensure_test_model('test.mcp.base.tool', 'MCP Tool Test')
        model2 = self._ensure_test_model('test.mcp.base.tool2', 'MCP Tool Test 2')
        ref1 = self.env['mcp.base.method'].create({
            'name': 'cfg_same_method',
            'model_id': model1.id,
        })
        ref2 = self.env['mcp.base.method'].create({
            'name': 'cfg_same_method',
            'model_id': model2.id,
        })
        rec1 = self.Tool.create({
            'name': 'Tool cfg_same_method',
            'model_id': model1.id,
            'method_id': ref1.id,
            'docstring': '',
            'is_code_first': False,
        })
        rec2 = self.Tool.create({
            'name': 'Tool cfg_same_method 2',
            'model_id': model2.id,
            'method_id': ref2.id,
            'docstring': '',
            'is_code_first': False,
        })
        self.assertNotEqual(rec1.id, rec2.id)

    # ── metadata computation ────────────────────────────────────────────

    def test_description_from_plain_docstring(self):
        """First paragraph of docstring becomes the description."""
        rec = self._create_tool(
            'cfg_get_customers',
            docstring=(
                'Retrieve all customer records.\n'
                '\n'
                ':return: list of customer dicts\n'
            ),
        )
        self.assertIn('Retrieve all customer records', rec.description)

    def test_schema_from_docstring_params(self):
        """Params in docstring generate inputSchema properties."""
        rec = self._create_tool(
            'cfg_get_customer_detail',
            docstring=(
                'Look up a customer.\n'
                '\n'
                ':param name: Customer name to find\n'
                ':param age: Customer age filter\n'
                ':return: dict\n'
            ),
        )
        schema = json.loads(rec.input_schema)
        self.assertIn('name', schema.get('properties', {}))
        self.assertIn('age', schema.get('properties', {}))
        self.assertIn('name', schema.get('required', []))
        self.assertIn('age', schema.get('required', []))

    def test_schema_with_param_types(self):
        """``:type:`` directives in docstring affect JSON types."""
        rec = self._create_tool(
            'cfg_get_customer_detail',
            docstring=(
                'Look up a customer.\n'
                '\n'
                ':param name: Customer name\n'
                ':type name: str\n'
                ':param age: Customer age\n'
                ':type age: int\n'
                ':return: dict\n'
            ),
        )
        props = json.loads(rec.input_schema).get('properties', {})
        self.assertEqual(props['name']['type'], 'string')
        self.assertEqual(props['age']['type'], 'integer')

    def test_empty_docstring_default_schema(self):
        """An empty docstring yields a default schema."""
        rec = self._create_tool('cfg_get_customers')
        schema = json.loads(rec.input_schema)
        self.assertEqual(schema['type'], 'object')
        self.assertEqual(schema['properties'], {})
        self.assertEqual(schema['required'], [])
        self.assertEqual(rec.description, 'Odoo Tool')

    # ── ir.model integration ───────────────────────────────────────────

    def test_ir_model_has_tool_ids(self):
        """ir.model extended with One2many to tools."""
        im = self._ensure_test_model('test.mcp.base.tool', 'MCP Tool Test')
        rec = self._create_tool('cfg_get_customers')
        self.assertIn(rec.id, im.mcp_tool_ids.ids)

    def test_ir_model_tool_count(self):
        """One2many shows correct number of tools per model."""
        im = self._ensure_test_model('test.mcp.base.tool', 'MCP Tool Test')
        baseline = len(im.mcp_tool_ids)  # code-first tools from post_init_hook

        rec1 = self._create_tool('cfg_get_customers')
        self.assertEqual(len(im.mcp_tool_ids), baseline + 1)
        self.assertIn(rec1.id, im.mcp_tool_ids.ids)

        rec2 = self._create_tool('cfg_get_customer_detail')
        self.assertEqual(len(im.mcp_tool_ids), baseline + 2)
        self.assertIn(rec2.id, im.mcp_tool_ids.ids)

    # ── @api.model vs recordset filtering ───────────────────────────────

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure ir.model records exist for the delegation-inheritance pair.
        for mn in ('test.mcp.base.tool.parent', 'test.mcp.base.tool.child'):
            if not cls.env['ir.model'].search([('model', '=', mn)], limit=1):
                cls.env['ir.model'].create({
                    'model': mn,
                    'name': mn,
                    'state': 'base',
                })

    def _get_ir_id(self, model_name):
        return self.env['ir.model'].search([('model', '=', model_name)], limit=1).id

    # ── name_search — method dropdown ──────────────────────────────

    def test_name_search_api_model_filtered(self):
        """@api.model methods from parent must NOT appear in child dropdown."""
        parent_id = self._get_ir_id('test.mcp.base.tool.parent')
        child_id = self._get_ir_id('test.mcp.base.tool.child')
        Method = self.env['mcp.base.method']

        # Parent: parent_api_model_method should show
        parent_results = Method.name_search(
            args=[('model_id', '=', parent_id)],
        )
        parent_names = {name for _id, name in parent_results}
        self.assertIn('parent_api_model_method', parent_names,
                      'parent_api_model_method should appear for parent model')

        # Child: parent_api_model_method should NOT show
        child_results = Method.name_search(
            args=[('model_id', '=', child_id)],
        )
        child_names = {name for _id, name in child_results}
        self.assertNotIn('parent_api_model_method', child_names,
                         '@api.model parent method must NOT appear for child model')

    def test_name_search_recordset_visible_on_child(self):
        """Recordset methods on parent are visible on child model dropdown."""
        parent_id = self._get_ir_id('test.mcp.base.tool.parent')
        child_id = self._get_ir_id('test.mcp.base.tool.child')
        Method = self.env['mcp.base.method']

        child_results = Method.name_search(
            args=[('model_id', '=', child_id)],
        )
        child_names = {name for _id, name in child_results}

        # parent_recordset_method is a recordset method → should inherit
        self.assertIn('parent_recordset_method', child_names,
                      'Recordset method from parent should appear for child')
        # child's own method should also be there
        self.assertIn('child_method', child_names)

    def test_name_search_filter_by_pattern(self):
        """name_search respects the name= parameter for filtering."""
        parent_id = self._get_ir_id('test.mcp.base.tool.parent')
        Method = self.env['mcp.base.method']

        results = Method.name_search(
            name='parent_record',
            args=[('model_id', '=', parent_id)],
        )
        names = {name for _id, name in results}
        self.assertIn('parent_recordset_method', names)
        self.assertNotIn('parent_api_model_method', names)

    # ── _sync_tools_from_registry ───────────────────────────────────

    def test_sync_tools_api_model_only_on_parent(self):
        """_sync_tools_from_registry only creates @api.model tool on defining model."""
        # Wipe any existing tools from previous tests
        parent_id = self._get_ir_id('test.mcp.base.tool.parent')
        child_id = self._get_ir_id('test.mcp.base.tool.child')
        self.Tool.search([
            ('model_id', 'in', [parent_id, child_id]),
            ('is_code_first', '=', True),
        ]).unlink()
        self.env['mcp.base.method'].search([
            ('model_id', 'in', [parent_id, child_id]),
        ]).unlink()

        self.Tool._sync_tools_from_registry()

        # parent_api_model_method must only exist for parent
        parent_api_tools = self.Tool.search([
            ('model_id', '=', parent_id),
            ('method_id.name', '=', 'parent_api_model_method'),
        ])
        self.assertEqual(len(parent_api_tools), 1,
                         'parent_api_model_method should be created on parent')

        child_api_tools = self.Tool.search([
            ('model_id', '=', child_id),
            ('method_id.name', '=', 'parent_api_model_method'),
        ])
        self.assertEqual(len(child_api_tools), 0,
                         'parent_api_model_method must NOT be created on child')

    def test_sync_tools_recordset_on_both(self):
        """Recordset @mcp_tool on parent is synced to both parent and child."""
        parent_id = self._get_ir_id('test.mcp.base.tool.parent')
        child_id = self._get_ir_id('test.mcp.base.tool.child')

        # Wipe first
        self.Tool.search([
            ('model_id', 'in', [parent_id, child_id]),
            ('is_code_first', '=', True),
        ]).unlink()
        self.env['mcp.base.method'].search([
            ('model_id', 'in', [parent_id, child_id]),
        ]).unlink()

        self.Tool._sync_tools_from_registry()

        parent_tools = self.Tool.search([
            ('model_id', '=', parent_id),
            ('method_id.name', '=', 'parent_recordset_method'),
        ])
        self.assertEqual(len(parent_tools), 1,
                         'parent_recordset_method should exist on parent')

        child_tools = self.Tool.search([
            ('model_id', '=', child_id),
            ('method_id.name', '=', 'parent_recordset_method'),
        ])
        self.assertEqual(len(child_tools), 1,
                         'parent_recordset_method should also exist on child')

    def test_sync_tools_code_first_flag(self):
        """Tools created by _sync_tools_from_registry are marked is_code_first."""
        parent_id = self._get_ir_id('test.mcp.base.tool.parent')
        child_id = self._get_ir_id('test.mcp.base.tool.child')
        self.Tool.search([
            ('model_id', 'in', [parent_id, child_id]),
            ('is_code_first', '=', True),
        ]).unlink()
        self.env['mcp.base.method'].search([
            ('model_id', 'in', [parent_id, child_id]),
        ]).unlink()

        self.Tool._sync_tools_from_registry()

        tools = self.Tool.search([
            ('model_id', 'in', [parent_id, child_id]),
        ])
        self.assertTrue(len(tools) >= 3)  # parent_api_model + parent_recordset on parent, + parent_recordset + child_method on child
        for t in tools:
            self.assertTrue(t.is_code_first,
                            f'Tool {t.name} should be is_code_first=True')

    def test_sync_tools_idempotent(self):
        """Calling _sync_tools_from_registry twice does not duplicate tools."""
        parent_id = self._get_ir_id('test.mcp.base.tool.parent')
        child_id = self._get_ir_id('test.mcp.base.tool.child')
        self.Tool.search([
            ('model_id', 'in', [parent_id, child_id]),
            ('is_code_first', '=', True),
        ]).unlink()
        self.env['mcp.base.method'].search([
            ('model_id', 'in', [parent_id, child_id]),
        ]).unlink()

        self.Tool._sync_tools_from_registry()
        count1 = self.Tool.search_count([
            ('model_id', 'in', [parent_id, child_id]),
        ])

        self.Tool._sync_tools_from_registry()
        count2 = self.Tool.search_count([
            ('model_id', 'in', [parent_id, child_id]),
        ])

        self.assertEqual(count1, count2,
                         'Second sync must not create duplicate tools')
