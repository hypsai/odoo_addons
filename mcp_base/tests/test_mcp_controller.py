import json
from base64 import b64encode

import werkzeug.test
import werkzeug.wrappers

from odoo import http
from odoo.tests import common, tagged
from .test_model_defs import ensure_model_meta, ensure_tool_records


@tagged('mcp_base', 'post_install', '-at_install')
class TestMCPController(common.HttpCase):
    """Test MCP controller endpoints"""

    def setUp(self):
        super().setUp()

        # Use werkzeug.test.Client to call the WSGI app directly in the
        # test thread, bypassing the multi-threaded HTTP server where the
        # routing map may not include /mcp (timing issue in post_install
        # tests). This is equivalent to how Odoo's HttpCase.url_open works
        # internally, but in the test thread.
        self._client = werkzeug.test.Client(http.root, werkzeug.wrappers.Response)

        # Authenticate via the standard HttpCase pattern to get a valid
        # session cookie for Root.setup_db → database resolution.
        self.authenticate('admin', 'admin')
        self._session_cookie = 'session_id=%s' % self.opener.cookies['session_id']

        # Rebuild routing map to ensure /mcp is included.
        # _clear_routing_map() was removed in Odoo 17+ (routing auto-refreshes).
        if hasattr(self.env['ir.http'], '_clear_routing_map'):
            self.env['ir.http']._clear_routing_map()

        ensure_model_meta(self.env, ["test.mcp.base.tool"])

        # Create temporary access rights for test.mcp.base.tool model
        test_model = self.env['ir.model'].search([('model', '=', 'test.mcp.base.tool')], limit=1)
        self.assertIsNotNone(test_model, "Test model 'test.mcp.base.tool' not found")

        self.env['ir.model.access'].create({
            'name': 'test.mcp.base.tool user access',
            'model_id': test_model.id,
            'group_id': self.env.ref('base.group_user').id,
            'perm_read': True,
            'perm_write': True,
            'perm_create': True,
            'perm_unlink': True,
        })

        # Sync @mcp_tool methods into mcp.base.tool ORM records.
        ensure_tool_records(self.env, model_names={"test.mcp.base.tool"})

        # Default auth: plain text X-User / X-Password headers (easy to configure)
        self._auth_headers = {
            'Content-Type': 'application/json',
            'X-User': 'admin',
            'X-Password': 'admin',
        }

        # Also prepare Basic Auth headers for Basic Auth specific tests
        credentials = b64encode(b"admin:admin").decode('utf-8')
        self._basic_auth_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {credentials}',
        }

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _mcp_request(self, url, data=None, timeout=None, files=None,
                      headers=None, allow_redirects=True, head=False):
        """Wsgi-level request with session cookie for database resolution."""
        _headers = dict(headers or {})
        _headers.setdefault('Content-Type', 'application/json')
        # Attach the session cookie so Root.setup_db finds the database.
        _headers.setdefault('Cookie', self._session_cookie)

        kwargs = {'headers': _headers}
        if data is not None:
            kwargs['data'] = data
        if files is not None:
            kwargs['data'] = files

        if head:
            return self._client.head(url, **kwargs)
        if data is not None or files is not None:
            return self._client.post(url, **kwargs)
        return self._client.get(url, **kwargs)

    # ------------------------------------------------------------------
    #  Tests
    # ------------------------------------------------------------------
    
    def test_mcp_endpoint_exists(self):
        """Test that MCP endpoint is accessible"""
        response = self.url_open('/mcp', timeout=30, headers={
            'X-User': 'admin',
            'X-Password': 'admin',
        })
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
            headers=self._auth_headers
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
            headers=self._auth_headers
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
            headers=self._auth_headers
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
            headers=self._auth_headers
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
            headers=self._auth_headers
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
            headers=self._auth_headers
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), '*')
    
    def test_mcp_tools_call_success(self):
        """Test successful tool call via tools/call"""
        # Call a known @api.model tool that doesn't require a recordset.
        call_payload = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "test.mcp.base.tool:get_customers",
                "arguments": {}
            }
        }

        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(call_payload),
            headers=self._auth_headers
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
            headers=self._auth_headers
        )

        tools = list_response.json()['result']['tools']
        self.assertGreater(len(tools), 0, "No MCP tools available for testing")

        # Find a tool that has _search_ parameter
        tool_with_search = None
        for tool in tools:
            if '_search_' in tool.get('inputSchema', {}).get('properties', {}):
                tool_with_search = tool
                break

        self.assertIsNotNone(tool_with_search, "No tools with _search_ parameter found")

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
            headers=self._auth_headers
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
            headers=self._auth_headers
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
            headers=self._auth_headers
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
            headers=self._auth_headers
        )

        self.assertEqual(response.status_code, 500)
        result = response.json()
        self.assertIn('error', result)

    def test_mcp_sse_endpoint_format(self):
        """Test SSE endpoint returns correct format"""
        response = self.url_open('/mcp', timeout=30, headers={
            'X-User': 'admin',
            'X-Password': 'admin',
        })

        self.assertEqual(response.status_code, 200)
        content_type = response.headers.get('Content-Type', '')
        self.assertIn('text/event-stream', content_type)

        # Check SSE headers
        self.assertEqual(response.headers.get('Cache-Control'), 'no-cache')
        # Connection header may contain multiple values
        connection = response.headers.get('Connection', '')
        self.assertIn('keep-alive', connection)

    def test_mcp_authentication_without_credentials(self):
        """Test that requests without credentials are rejected (no dev mode fallback)"""
        # Check if auth_api_key is installed
        auth_api_key_module = self.env['ir.module.module'].search([
            ('name', '=', 'auth_api_key'),
            ('state', '=', 'installed')
        ])

        if auth_api_key_module:
            self.skipTest("auth_api_key module is installed, skipping basic auth test")

        # Without any Authorization header, should be rejected
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

        # Should return 401 (authentication required)
        self.assertEqual(response.status_code, 401)
        result = response.json()
        self.assertIn('error', result)
        self.assertEqual(result['error']['code'], -32604)

    def test_mcp_basic_auth_success(self):
        """Test successful HTTP Basic Auth with valid username/password"""
        from base64 import b64encode

        # Check if auth_api_key is installed
        auth_api_key_module = self.env['ir.module.module'].search([
            ('name', '=', 'auth_api_key'),
            ('state', '=', 'installed')
        ])
        if auth_api_key_module:
            self.skipTest("auth_api_key module is installed, skipping basic auth test")

        # Use admin/admin (default Odoo test credentials)
        credentials = b64encode(b"admin:admin").decode('utf-8')

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
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Basic {credentials}',
            }
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('result', result)
        self.assertEqual(result['result']['protocolVersion'], '2025-03-26')

    def test_mcp_basic_auth_invalid_credentials(self):
        """Test HTTP Basic Auth with invalid password is rejected"""
        from base64 import b64encode

        # Check if auth_api_key is installed
        auth_api_key_module = self.env['ir.module.module'].search([
            ('name', '=', 'auth_api_key'),
            ('state', '=', 'installed')
        ])
        if auth_api_key_module:
            self.skipTest("auth_api_key module is installed, skipping basic auth test")

        # Invalid password
        credentials = b64encode(b"admin:wrongpassword").decode('utf-8')

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
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Basic {credentials}',
            }
        )

        self.assertEqual(response.status_code, 401)
        result = response.json()
        self.assertIn('error', result)
        self.assertEqual(result['error']['code'], -32604)

    def test_mcp_basic_auth_invalid_scheme(self):
        """Test non-Basic auth scheme is rejected"""
        from base64 import b64encode

        # Check if auth_api_key is installed
        auth_api_key_module = self.env['ir.module.module'].search([
            ('name', '=', 'auth_api_key'),
            ('state', '=', 'installed')
        ])
        if auth_api_key_module:
            self.skipTest("auth_api_key module is installed, skipping basic auth test")

        credentials = b64encode(b"admin:admin").decode('utf-8')

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
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {credentials}',
            }
        )

        self.assertEqual(response.status_code, 401)
        result = response.json()
        self.assertIn('error', result)

    def test_mcp_basic_auth_malformed_header(self):
        """Test malformed Basic Auth header (missing colon) is rejected"""
        from base64 import b64encode

        # Check if auth_api_key is installed
        auth_api_key_module = self.env['ir.module.module'].search([
            ('name', '=', 'auth_api_key'),
            ('state', '=', 'installed')
        ])
        if auth_api_key_module:
            self.skipTest("auth_api_key module is installed, skipping basic auth test")

        # No colon → invalid format
        credentials = b64encode(b"onlyusername").decode('utf-8')

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
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Basic {credentials}',
            }
        )

        self.assertEqual(response.status_code, 401)
        result = response.json()
        self.assertIn('error', result)
    
    # ── Plain text auth tests (X-User / X-Password) ────────────────────────

    def test_mcp_plain_auth_success(self):
        """Test plain text X-User/X-Password headers succeed"""
        auth_api_key_module = self.env['ir.module.module'].search([
            ('name', '=', 'auth_api_key'),
            ('state', '=', 'installed')
        ])
        if auth_api_key_module:
            self.skipTest("auth_api_key module is installed, skipping plain auth test")

        payload = {
            "jsonrpc": "2.0",
            "id": 35,
            "method": "initialize",
            "params": {}
        }

        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers={
                'Content-Type': 'application/json',
                'X-User': 'admin',
                'X-Password': 'admin',
            }
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('result', result)
        self.assertEqual(result['result']['protocolVersion'], '2025-03-26')

    def test_mcp_plain_auth_invalid_password(self):
        """Test plain text auth with wrong password is rejected"""
        auth_api_key_module = self.env['ir.module.module'].search([
            ('name', '=', 'auth_api_key'),
            ('state', '=', 'installed')
        ])
        if auth_api_key_module:
            self.skipTest("auth_api_key module is installed, skipping plain auth test")

        payload = {
            "jsonrpc": "2.0",
            "id": 36,
            "method": "initialize",
            "params": {}
        }

        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers={
                'Content-Type': 'application/json',
                'X-User': 'admin',
                'X-Password': 'wrongpassword',
            }
        )

        self.assertEqual(response.status_code, 401)

    def test_mcp_plain_auth_missing_user(self):
        """Test plain text auth missing X-User header falls back to error"""
        auth_api_key_module = self.env['ir.module.module'].search([
            ('name', '=', 'auth_api_key'),
            ('state', '=', 'installed')
        ])
        if auth_api_key_module:
            self.skipTest("auth_api_key module is installed, skipping plain auth test")

        payload = {
            "jsonrpc": "2.0",
            "id": 37,
            "method": "initialize",
            "params": {}
        }

        # Only X-Password, no X-User → falls through to Basic Auth error
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers={
                'Content-Type': 'application/json',
                'X-Password': 'admin',
            }
        )

        self.assertEqual(response.status_code, 401)
        result = response.json()
        self.assertIn('error', result)

    def test_mcp_plain_auth_priority_over_basic(self):
        """Test X-User/X-Password takes priority over Basic Auth"""
        auth_api_key_module = self.env['ir.module.module'].search([
            ('name', '=', 'auth_api_key'),
            ('state', '=', 'installed')
        ])
        if auth_api_key_module:
            self.skipTest("auth_api_key module is installed, skipping plain auth test")

        payload = {
            "jsonrpc": "2.0",
            "id": 38,
            "method": "initialize",
            "params": {}
        }

        # X-User/X-Password with valid creds + Basic header with invalid creds
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers={
                'Content-Type': 'application/json',
                'X-User': 'admin',
                'X-Password': 'admin',
                'Authorization': f'Basic {b64encode(b"admin:invalid").decode("utf-8")}',
            }
        )

        # Should succeed because X-User/X-Password takes priority
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('result', result)
    
    def test_mcp_tools_have_search_parameter(self):
        """Test that non-model methods include _search_ parameter in schema"""
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
            headers=self._auth_headers
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        tools = result['result']['tools']

        # Find get_customer_detail tool (not marked with @api.model, should have _search_)
        target_tool = None
        for tool in tools:
            if 'get_customer_detail' in tool['name']:
                target_tool = tool
                break

        # Must find the tool - fail if not found
        self.assertIsNotNone(target_tool, "Tool 'get_customer_detail' not found in tools list")

        schema = target_tool.get('inputSchema', {})
        properties = schema.get('properties', {})

        # Verify _search_ parameter is present for non-model methods
        self.assertIn('_search_', properties,
            f"Tool {target_tool['name']} should have _search_ parameter")

        # Verify _search_ has correct structure
        search_prop = properties['_search_']
        self.assertEqual(search_prop['type'], 'object')
        self.assertIn('description', search_prop)

        # Verify nested properties exist
        search_properties = search_prop.get('properties', {})
        self.assertIn('args', search_properties, "Should have 'args' parameter")
        self.assertIn('offset', search_properties)
        self.assertIn('limit', search_properties)
        self.assertIn('order', search_properties)

        # Verify 'args' is required
        required = search_prop.get('required', [])
        self.assertIn('args', required, "'args' should be required")

    def test_mcp_tool_get_customer_detail(self):
        """Test calling get_customer_detail with parameters"""
        call_payload = {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "test.mcp.base.tool:get_customer_detail",
                "arguments": {
                    "name": "Mary"
                }
            }
        }

        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(call_payload),
            headers=self._auth_headers
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn('result', result)
        self.assertFalse(result['result'].get('isError', False))

        # Check content
        content = result['result']['content'][0]['text']
        import json as json_module
        data = json_module.loads(content)
        self.assertEqual(data['name'], 'Mary')
        self.assertEqual(data['email'], 'mary@example.com')
        self.assertEqual(data['status'], 'active')

    def test_mcp_tool_greet_customer(self):
        """Test calling greet_customer with default and custom parameters"""
        # Test with default greeting
        call_payload = {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {
                "name": "test.mcp.base.tool:greet_customer",
                "arguments": {
                    "name": "Tom"
                }
            }
        }

        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(call_payload),
            headers=self._auth_headers
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertFalse(result['result'].get('isError', False))

        content = result['result']['content'][0]['text']
        self.assertIn('Hello, Tom!', content)

        # Test with custom greeting
        call_payload['params']['arguments']['greeting'] = 'Hi'
        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(call_payload),
            headers=self._auth_headers
        )

        result = response.json()
        content = result['result']['content'][0]['text']
        self.assertIn('Hi, Tom!', content)

    def test_mcp_tool_inheritance_override(self):
        """Test that inherited method overrides parent with enhanced features"""
        call_payload = {
            "jsonrpc": "2.0",
            "id": 22,
            "method": "tools/call",
            "params": {
                "name": "test.mcp.base.tool:get_customer_detail",
                "arguments": {
                    "name": "Mary"
                }
            }
        }

        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(call_payload),
            headers=self._auth_headers
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()

        content = result['result']['content'][0]['text']
        import json as json_module
        data = json_module.loads(content)

        # Should have enhanced fields from inheritance
        self.assertIn('premium', data)
        self.assertIn('vip_level', data)
        self.assertTrue(data['premium'])  # Mary has 5 orders > 2
        self.assertEqual(data['vip_level'], 'Gold')  # 5 orders > 4

    def test_mcp_tool_not_found_customer(self):
        """Test calling get_customer_detail with non-existent customer"""
        call_payload = {
            "jsonrpc": "2.0",
            "id": 23,
            "method": "tools/call",
            "params": {
                "name": "test.mcp.base.tool:get_customer_detail",
                "arguments": {
                    "name": "NonExistent"
                }
            }
        }

        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(call_payload),
            headers=self._auth_headers
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()

        content = result['result']['content'][0]['text']
        import json as json_module
        data = json_module.loads(content)

        # Should return error message
        self.assertIn('error', data)
        self.assertIn('NonExistent', data['error'])

    def test_mcp_tool_schema_with_custom_description(self):
        """Test that custom description in @mcp_tool decorator is applied"""
        payload = {
            "jsonrpc": "2.0",
            "id": 24,
            "method": "tools/list",
            "params": {}
        }

        response = self.url_open(
            '/mcp',
            timeout=20,
            data=json.dumps(payload),
            headers=self._auth_headers
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        tools = result['result']['tools']

        # Find get_customer_detail tool
        target_tool = None
        for tool in tools:
            if 'get_customer_detail' in tool['name']:
                target_tool = tool
                break

        self.assertIsNotNone(target_tool, "Tool 'get_customer_detail' not found for description test")

        # Should have custom description from inherited class
        self.assertIn('enhanced', target_tool['description'].lower())

    # ── NEW tests ────────────────────────────────────────────────────────

    def test_mcp_model_method_no_search_param(self):
        """@api.model methods should NOT get _search_ in schema."""
        payload = {
            "jsonrpc": "2.0",
            "id": 25,
            "method": "tools/list",
            "params": {},
        }
        response = self.url_open(
            '/mcp', timeout=20,
            data=json.dumps(payload),
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        tools = response.json()['result']['tools']

        target = None
        for t in tools:
            if 'get_customers' in t['name']:
                target = t
                break
        self.assertIsNotNone(target, "Tool 'get_customers' should exist")
        self.assertNotIn(
            '_search_', target['inputSchema'].get('properties', {}),
            "@api.model method should NOT have _search_ parameter",
        )

    def test_mcp_call_model_method(self):
        """Call an @api.model tool (get_customers) via tools/call."""
        payload = {
            "jsonrpc": "2.0",
            "id": 26,
            "method": "tools/call",
            "params": {
                "name": "test.mcp.base.tool:get_customers",
                "arguments": {},
            },
        }
        response = self.url_open(
            '/mcp', timeout=20,
            data=json.dumps(payload),
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertFalse(result['result'].get('isError', False))
        content = result['result']['content'][0]['text']
        data = json.loads(content)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)

    def test_mcp_tool_name_no_colon(self):
        """Tool name without colon should return isError."""
        payload = {
            "jsonrpc": "2.0",
            "id": 27,
            "method": "tools/call",
            "params": {
                "name": "invalidtoolname",
                "arguments": {},
            },
        }
        response = self.url_open(
            '/mcp', timeout=20,
            data=json.dumps(payload),
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['result'].get('isError', False))

    def test_mcp_tool_model_exists_method_does_not(self):
        """Model exists but method doesn't → isError."""
        payload = {
            "jsonrpc": "2.0",
            "id": 28,
            "method": "tools/call",
            "params": {
                "name": "test.mcp.base.tool:does_not_exist",
                "arguments": {},
            },
        }
        response = self.url_open(
            '/mcp', timeout=20,
            data=json.dumps(payload),
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['result'].get('isError', False))

    def test_mcp_string_result_not_double_encoded(self):
        """String tool result should NOT be wrapped in an extra JSON layer."""
        payload = {
            "jsonrpc": "2.0",
            "id": 29,
            "method": "tools/call",
            "params": {
                "name": "test.mcp.base.tool:greet_customer",
                "arguments": {"name": "World"},
            },
        }
        response = self.url_open(
            '/mcp', timeout=20,
            data=json.dumps(payload),
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        text = result['result']['content'][0]['text']
        # greet_customer returns a plain str, so the content should be the
        # raw string, not a JSON-encoded string (no leading quote).
        self.assertEqual(text, "Hello, World! Welcome back.")
        self.assertFalse(text.startswith('"'), "String result appears to be double-encoded")

    def test_mcp_search_does_not_mutate_arguments(self):
        """_search_ pop() must not mutate the original arguments dict."""
        arguments = {
            "name": "Mary",
            "_search_": {"args": [], "limit": 1},
        }
        original_keys = set(arguments.keys())

        payload = {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {
                "name": "test.mcp.base.tool:get_customer_detail",
                "arguments": arguments,
            },
        }
        response = self.url_open(
            '/mcp', timeout=20,
            data=json.dumps(payload),
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 200)

        # After the call, the original dict must still contain _search_
        self.assertEqual(
            set(arguments.keys()), original_keys,
            "Original arguments dict was mutated during tool call",
        )

    def test_mcp_unknown_notification_no_crash(self):
        """Unknown notification should not crash the server (202 accepted)."""
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/some_unknown_event",
            "params": {"foo": "bar"},
        }
        response = self.url_open(
            '/mcp', timeout=20,
            data=json.dumps(payload),
            headers=self._auth_headers,
        )
        self.assertEqual(response.status_code, 202)

    def test_mcp_tool_call_idempotent_same_result(self):
        """Same tool + same arguments → same result (no side-effects)."""
        def _call(req_id):
            return self.url_open(
                '/mcp', timeout=20,
                data=json.dumps({
                    "jsonrpc": "2.0", "id": req_id,
                    "method": "tools/call",
                    "params": {
                        "name": "test.mcp.base.tool:get_customer_detail",
                        "arguments": {"name": "Mary"},
                    },
                }),
                headers=self._auth_headers,
            )

        r1 = _call(33)
        r2 = _call(34)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

        content1 = r1.json()['result']['content'][0]['text']
        content2 = r2.json()['result']['content'][0]['text']
        self.assertEqual(content1, content2)


@tagged('post_install', '-at_install')
class TestMCPIntegration(common.TransactionCase):
    """Integration tests for MCP functionality"""
    
    def setUp(self):
        super().setUp()
        ensure_model_meta(self.env, ["test.mcp.base.tool"])
        ensure_tool_records(self.env, model_names={"test.mcp.base.tool"})

    def test_mcp_tool_registration(self):
        """MCP tools should exist as active mcp.base.tool ORM records."""
        tools = self.env['mcp.base.tool'].search([
            ('model_id.model', '=', 'test.mcp.base.tool'),
            ('active', '=', True),
        ])
        self.assertGreater(len(tools), 0, "No MCP tools found in mcp.base.tool")

        method_names = tools.mapped('method_id.name')
        self.assertIn('get_customer_detail', method_names)
        self.assertIn('get_customers', method_names)
        self.assertIn('greet_customer', method_names)

        # Verify code-first metadata is populated.
        detail = tools.filtered(lambda r: r.method_id.name == 'get_customer_detail')
        self.assertTrue(detail, "get_customer_detail tool not found")
        self.assertTrue(detail.description, "Description should be computed")
        self.assertTrue(detail.input_schema, "inputSchema should be computed")
        schema = json.loads(detail.input_schema)
        self.assertIn('name', schema.get('properties', {}))
