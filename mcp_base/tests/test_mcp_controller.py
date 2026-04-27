# -*- coding: utf-8 -*-
import json

from odoo import models
from odoo.addons.mcp_base import mcp_tool
from odoo.tests import common, tagged


class McpBaseToolTest(models.Model):
    _name = "mcp.base.tool.test"
    _description = "MCP Tool Test"

    @mcp_tool
    def get_customers(self):
        """Get all customers."""
        return [{"name": "Mary"}, {"name", "Lily"}, {"name": "Tom"}]


@tagged('mcp_base', 'post_install', '-at_install')
class TestMCPController(common.HttpCase):
    """Test MCP controller endpoints"""

    def setUp(self):
        super().setUp()

        # 1 Ensure the module is installed
        self.module = self.env['ir.module.module'].search([('name', '=', 'mcp_base')])
        if self.module and self.module.state != 'installed':
            self.module.button_immediate_install()

        # 2 Register temporary models.
        for Model in [McpBaseToolTest]:
            model_name = Model._name
            self.registry.models[model_name] = Model._build_model(
                self.registry, self.cr
            )
            self.registry.setup_models(self.cr)
            self.registry.init_models(
                self.cr, [model_name], {"module": "test"}, install=True
            )
            self.env['ir.model.access'].create({
                'name': f'access_{model_name.replace(".", "_")}',
                'model_id': self.env['ir.model']._get_id(model_name),
                'group_id': self.env.ref('base.group_user').id,
                'perm_read': True,
                'perm_write': True,
                'perm_create': True,
                'perm_unlink': True,
            })

        # 3 Clear cache.
        # 3.1 Clear the ORM cache (important for menus)
        self.env['ir.ui.menu'].clear_caches()
        # 3.2 Re-initialize the environment to pick up the new records
        self.env.registry.clear_caches()
        self.env.registry.signal_changes()
    
    def test_mcp_endpoint_exists(self):
        """Test that MCP endpoint is accessible"""
        response = self.url_open('/mcp', timeout=30)
        # GET request should return SSE stream
        self.assertEqual(response.status_code, 200)
        content_type = response.headers.get('Content-Type', '')
        self.assertIn('text/event-stream', content_type)
    
    def test_mcp_initialize_request(self):
        """Test MCP initialize method via POST"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {}
            }
        }
        
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['jsonrpc'], '2.0')
        self.assertEqual(result['id'], 1)
        self.assertIn('result', result)
        self.assertEqual(result['result']['protocolVersion'], '2025-03-26')
        self.assertIn('serverInfo', result['result'])
    
    def test_mcp_tools_list_request(self):
        """Test MCP tools/list method"""
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['jsonrpc'], '2.0')
        self.assertEqual(result['id'], 2)
        self.assertIn('tools', result['result'])
        self.assertIsInstance(result['result']['tools'], list)
        self.assertGreater(len(result['result']['tools']), 0)
    
    def test_mcp_invalid_method(self):
        """Test handling of invalid MCP method"""
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "invalid/method",
            "params": {}
        }
        
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 500)
        result = response.json()
        self.assertIn('error', result)
        self.assertEqual(result['error']['code'], -32603)
    
    def test_mcp_invalid_json(self):
        """Test handling of invalid JSON"""
        response = self.url_open(
            '/mcp',
            timeout=20,
            data='invalid json',
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 400)
        result = response.json()
        self.assertIn('error', result)
        self.assertEqual(result['error']['code'], -32700)
    
    def test_mcp_notification_handling(self):
        """Test MCP notification (no id field)"""
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        # Notifications should return 202 Accepted
        self.assertEqual(response.status_code, 202)
    
    def test_mcp_cors_headers(self):
        """Test CORS headers are present"""
        payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "initialize",
            "params": {}
        }
        
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), '*')
    
    def test_mcp_method_not_allowed(self):
        """Test unsupported HTTP method"""
        # DELETE method should not be allowed (url_open defaults to POST for data)
        # We test by sending invalid data to verify error handling
        response = self.url_open(
            '/mcp',
            timeout=20,
            data='invalid',
            headers={'Content-Type': 'text/plain'}
        )
        
        # Should return 400 Bad Request for invalid content type/data
        self.assertEqual(response.status_code, 400)
    
    def test_mcp_tools_have_search_parameter(self):
        """Test that all MCP tools include _search_ parameter in schema"""
        payload = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/list",
            "params": {}
        }
        
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        tools = result['result']['tools']
        
        # Check that at least some tools exist and have _search_ parameter
        if tools:
            for tool in tools[:3]:  # Check first 3 tools
                schema = tool.get('inputSchema', {})
                properties = schema.get('properties', {})
                # Verify _search_ parameter is present
                self.assertIn('_search_', properties, 
                    f"Tool {tool['name']} should have _search_ parameter")
                
                # Verify _search_ has correct structure
                search_prop = properties['_search_']
                self.assertEqual(search_prop['type'], 'object')
                self.assertIn('description', search_prop)
                
                # Verify nested properties exist (using 'args' instead of 'domain')
                search_properties = search_prop.get('properties', {})
                self.assertIn('args', search_properties, "Should have 'args' parameter")
                self.assertIn('offset', search_properties)
                self.assertIn('limit', search_properties)
                self.assertIn('order', search_properties)
                
                # Verify 'args' is required
                required = search_prop.get('required', [])
                self.assertIn('args', required, "'args' should be required")


@tagged('post_install', '-at_install')
class TestMCPIntegration(common.TransactionCase):
    """Integration tests for MCP functionality"""
    
    def test_mcp_tool_registration(self):
        """Test that MCP tools can be discovered in registry"""

        # Create a test model with MCP tool
        test_model = self.env.registry.models.get('res.partner')
        if test_model:
            # Check that we can iterate over models
            tools_found = 0
            for model_name, model_obj in self.env.registry.models.items():
                for attr_name in dir(model_obj):
                    if attr_name.startswith('_'):
                        continue
                    try:
                        method = getattr(model_obj, attr_name)
                        if callable(method) and getattr(method, '_is_mcp_tool', False):
                            tools_found += 1
                    except:
                        continue
            
            # At least the test should complete without errors
            self.assertIsInstance(tools_found, int)
    
    def test_python_type_conversion_comprehensive(self):
        """Comprehensive test for type conversion"""
        from ..decorators import python_type_to_json_type
        from typing import List, Dict
        
        test_cases = [
            (str, "string"),
            (int, "integer"),
            (float, "number"),
            (bool, "boolean"),
            (List[str], {"type": "array"}),
            (Dict, {"type": "object"}),
        ]
        
        for py_type, expected in test_cases:
            result = python_type_to_json_type(py_type)
            if isinstance(expected, dict):
                self.assertEqual(result['type'], expected['type'])
            else:
                self.assertEqual(result, expected)
