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

    def _create_tool(self, method, **overrides):
        """Create a basic config-first tool record."""
        model = self._ensure_test_model('test.mcp.base.tool', 'MCP Tool Test')
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
        rec = self._create_tool(
            'get_customers',
            docstring='Get all customers.\n\n:return: list of customers',
        )
        self.assertTrue(rec.description, 'Description should be computed from docstring')
        self.assertIn('customers', rec.description.lower())
        self.assertTrue(rec.input_schema, 'inputSchema should be computed')
        self.assertFalse(rec.is_code_first)

    def test_create_code_first_tool(self):
        """A code-first tool computes metadata from the actual Python method."""
        rec = self._create_tool(
            'get_customer_detail',
            is_code_first=True,
            docstring='',
        )
        self.assertTrue(rec.description)
        self.assertIn('customer', rec.description.lower())
        schema = json.loads(rec.input_schema)
        self.assertIsNotNone(schema)
        self.assertIn('name', schema.get('properties', {}))

    def test_code_first_writes_docstring(self):
        """Updating docstring on a code-first tool updates computed fields."""
        rec = self._create_tool('get_customers', is_code_first=True, docstring='')
        rec.docstring = 'Get all customers.\n\n:return: list of customers'
        # Force recompute by triggering write
        rec.write({'docstring': rec.docstring})
        self.assertIn('customers', rec.description.lower())

    def test_active_filtering(self):
        """Inactive tools can be hidden."""
        rec = self._create_tool('get_customers')
        self.assertTrue(rec.active)
        active = self.Tool.search([('active', '=', True), ('id', '=', rec.id)])
        self.assertTrue(active)
        rec.active = False
        inactive = self.Tool.search([('active', '=', True), ('id', '=', rec.id)])
        self.assertFalse(inactive)

    # ── uniqueness constraint ───────────────────────────────────────────

    def test_unique_model_method(self):
        """Each (model_id, method) pair must be unique."""
        self._create_tool('get_customers')
        # _sql_constraints violations may surface as psycopg2.UniqueViolation
        # (raw) or odoo.exceptions.ValidationError depending on Odoo version.
        # Catch Exception for v13–v19 compatibility.
        with self.assertRaises(Exception):
            self._create_tool('get_customers')

    def test_same_method_different_model(self):
        """Same method name on different models is allowed."""
        model1 = self._ensure_test_model('test.mcp.base.tool', 'MCP Tool Test')
        model2 = self._ensure_test_model('test.mcp.base.tool2', 'MCP Tool Test 2')
        ref1 = self.env['mcp.base.method'].create({
            'name': 'get_customers',
            'model_id': model1.id,
        })
        ref2 = self.env['mcp.base.method'].create({
            'name': 'get_customers',
            'model_id': model2.id,
        })
        rec1 = self.Tool.create({
            'name': 'Tool get_customers',
            'model_id': model1.id,
            'method_id': ref1.id,
            'docstring': '',
            'is_code_first': False,
        })
        rec2 = self.Tool.create({
            'name': 'Tool get_customers 2',
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
            'get_customers',
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
            'get_customer_detail',
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
            'get_customer_detail',
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
        rec = self._create_tool('get_customers')
        schema = json.loads(rec.input_schema)
        self.assertEqual(schema['type'], 'object')
        self.assertEqual(schema['properties'], {})
        self.assertEqual(schema['required'], [])
        self.assertEqual(rec.description, 'Odoo Tool')

    # ── onchange ───────────────────────────────────────────────────────

    def test_onchange_model_id_resets_method(self):
        """Changing the model resets the method selection."""
        rec = self._create_tool('get_customers')
        self.assertEqual(rec.method_id.name, 'get_customers')

        rec.model_id = self._ensure_test_model(
            'test.mcp.base.tool2', 'MCP Tool Test 2',
        )
        rec._onchange_model_id()
        self.assertFalse(rec.method_id, 'Method should be reset after model change')

    # ── ir.model integration ───────────────────────────────────────────

    def test_ir_model_has_tool_ids(self):
        """ir.model extended with One2many to tools."""
        im = self._ensure_test_model('test.mcp.base.tool', 'MCP Tool Test')
        rec = self._create_tool('get_customers')
        self.assertIn(rec.id, im.mcp_tool_ids.ids)

    def test_ir_model_tool_count(self):
        """One2many shows correct number of tools per model."""
        im = self._ensure_test_model('test.mcp.base.tool', 'MCP Tool Test')
        self.assertEqual(len(im.mcp_tool_ids), 0)

        rec1 = self._create_tool('get_customers')
        self.assertEqual(len(im.mcp_tool_ids), 1)
        self.assertIn(rec1.id, im.mcp_tool_ids.ids)

        rec2 = self._create_tool('get_customer_detail')
        self.assertEqual(len(im.mcp_tool_ids), 2)
        self.assertIn(rec2.id, im.mcp_tool_ids.ids)
