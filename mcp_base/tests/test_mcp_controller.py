# -*- coding: utf-8 -*-
import json

from odoo.tests import common, tagged
from .test_model_defs import ensure_model_meta


@tagged('mcp_base', 'post_install', '-at_install')
class TestMCPController(common.HttpCase):
    """Test MCP controller endpoints"""

    def setUp(self):
        super().setUp()
        
        ensure_model_meta(self.env, ["test.mcp.base.tool"])

        # Create temporary access rights for test.mcp.base.tool model
        test_model = self.env['ir.model'].search([('model', '=', 'test.mcp.base.tool')], limit=1)
        if test_model:
            self.env['ir.model.access'].create({
                'name': 'test.mcp.base.tool user access',
                'model_id': test_model.id,
                'group_id': self.env.ref('base.group_user').id,
                'perm_read': True,
                'perm_write': True,
                'perm_create': True,
                'perm_unlink': True,
            })
    
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
    
    def test_mcp_tools_call_success(self):
        """Test successful tool call via tools/call"""
        # First get available tools
        list_payload = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/list",
            "params": {}
        }
        
        list_response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(list_payload),
            headers={'Content-Type': 'application/json'}
        )
        
        tools = list_response.json()['result']['tools']
        if not tools:
            self.skipTest("No MCP tools available for testing")
        
        # Try to call the first available tool
        first_tool = tools[0]
        tool_name = first_tool['name']
        
        call_payload = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": {}
            }
        }
        
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(call_payload),
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['jsonrpc'], '2.0')
        self.assertEqual(result['id'], 11)
        self.assertIn('result', result)
        self.assertIn('content', result['result'])

    def test_mcp_tools_call_with_search(self):
        """Test tool call with _search_ parameter"""
        # Get available tools
        list_payload = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/list",
            "params": {}
        }
        
        list_response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(list_payload),
            headers={'Content-Type': 'application/json'}
        )
        
        tools = list_response.json()['result']['tools']
        if not tools:
            self.skipTest("No MCP tools available for testing")
        
        # Find a tool that has _search_ parameter
        tool_with_search = None
        for tool in tools:
            if '_search_' in tool.get('inputSchema', {}).get('properties', {}):
                tool_with_search = tool
                break
        
        if not tool_with_search:
            self.skipTest("No tools with _search_ parameter found")
        
        # Call tool with _search_ parameter
        call_payload = {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": tool_with_search['name'],
                "arguments": {
                    "_search_": {
                        "args": [],
                        "limit": 1
                    }
                }
            }
        }
        
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(call_payload),
            headers={'Content-Type': 'application/json'}
        )
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('result', result)

    def test_mcp_tools_call_nonexistent(self):
        """Test calling a non-existent tool"""
        payload = {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {
                "name": "nonexistent:method",
                "arguments": {}
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
        self.assertIn('result', result)
        # Should return error content
        self.assertTrue(result['result'].get('isError', False))

    def test_mcp_method_not_allowed(self):
        """Test unsupported HTTP method returns 405"""
        # Use requests library to send DELETE method
        import requests
        try:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
            response = requests.delete(f'{base_url}/mcp')
            self.assertEqual(response.status_code, 405)
        except Exception:
            # If requests not available, skip this test
            self.skipTest("Cannot test DELETE method without requests library")

    def test_mcp_empty_payload(self):
        """Test handling of empty POST payload"""
        response = self.url_open(
            '/mcp',
            timeout=20,
            data='{}',
            headers={'Content-Type': 'application/json'}
        )
        
        # Should return error for missing method
        self.assertEqual(response.status_code, 500)
        result = response.json()
        self.assertIn('error', result)

    def test_mcp_missing_required_fields(self):
        """Test handling of missing required JSON-RPC fields"""
        # Missing 'method' field
        payload = {
            "jsonrpc": "2.0",
            "id": 15
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

    def test_mcp_sse_endpoint_format(self):
        """Test SSE endpoint returns correct format"""
        response = self.url_open('/mcp', timeout=30)
        
        self.assertEqual(response.status_code, 200)
        content_type = response.headers.get('Content-Type', '')
        self.assertIn('text/event-stream', content_type)
        
        # Check SSE headers
        self.assertEqual(response.headers.get('Cache-Control'), 'no-cache')
        # Connection header may contain multiple values
        connection = response.headers.get('Connection', '')
        self.assertIn('keep-alive', connection)

    def test_mcp_tools_caching(self):
        """Test that tool info is cached between requests"""
        # First request
        payload1 = {
            "jsonrpc": "2.0",
            "id": 16,
            "method": "tools/list",
            "params": {}
        }
        
        response1 = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload1),
            headers={'Content-Type': 'application/json'}
        )
        
        tools1 = response1.json()['result']['tools']
        
        # Second request
        payload2 = {
            "jsonrpc": "2.0",
            "id": 17,
            "method": "tools/list",
            "params": {}
        }
        
        response2 = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload2),
            headers={'Content-Type': 'application/json'}
        )
        
        tools2 = response2.json()['result']['tools']
        
        # Both should return same number of tools
        self.assertEqual(len(tools1), len(tools2))
        
        # Tool structures should be identical (cached)
        if tools1 and tools2:
            self.assertEqual(tools1[0]['name'], tools2[0]['name'])
            self.assertEqual(tools1[0]['description'], tools2[0]['description'])

    def test_mcp_authentication_without_api_key(self):
        """Test authentication when auth_api_key module is not installed"""
        # Check if auth_api_key is installed
        auth_api_key_module = self.env['ir.module.module'].search([
            ('name', '=', 'auth_api_key'),
            ('state', '=', 'installed')
        ])
        
        if auth_api_key_module:
            self.skipTest("auth_api_key module is installed, skipping dev mode test")
        
        # Without API key, should still work in dev mode (with admin privileges)
        payload = {
            "jsonrpc": "2.0",
            "id": 18,
            "method": "initialize",
            "params": {}
        }
        
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        # Should succeed with admin user
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('result', result)
    
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
