# -*- coding: utf-8 -*-
# @Time         : 10:26 2026/4/24
# @Author       : Chris
# @Description  :
import json
import logging

from odoo import http
from odoo.exceptions import AccessDenied
from odoo.http import request
from werkzeug.wrappers import Response as WerkzeugResponse

from ..compatible import request_update_env, root_patch_get_request

_logger = logging.getLogger(__name__)
root_patch_get_request()


class McpController(http.Controller):

    @http.route('/mcp', type='http', auth='public', csrf=False, methods=['GET', 'POST'])
    def mcp_endpoint(self, **kwargs):
        """
        Unified Streamable HTTP endpoint for MCP protocol.
        
        GET  → SSE stream for server notifications
        POST → JSON-RPC message handling
        
        Authentication:
        - If auth_api_key is installed: supports API key via 'Api-Key' header
        - Otherwise: runs with admin privileges (development mode)
        """
        # Try to authenticate with API key if available
        auth_error = self._try_api_key_auth()
        
        # Handle authentication errors
        if auth_error:
            if request.httprequest.method == 'POST':
                # POST requests get JSON-RPC error response
                return self._json_response({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32604,
                        "message": "Authentication failed",
                        "data": auth_error
                    }
                }, 401)
            else:
                # GET requests (SSE) get HTTP 401 with plain text
                return WerkzeugResponse(
                    f"401 Unauthorized: {auth_error}",
                    status=401,
                    mimetype='text/plain',
                    headers={'Access-Control-Allow-Origin': '*'}
                )
        
        if request.httprequest.method == 'GET':
            return self._handle_sse_stream()
        elif request.httprequest.method == 'POST':
            return self._handle_json_rpc()
        else:
            return WerkzeugResponse('Method Not Allowed', status=405)

    def _try_api_key_auth(self):
        """
        Attempt API key authentication using auth_api_key's standard method.
        
        Security Policy:
        - If auth_api_key is installed: API key is REQUIRED
        - If auth_api_key is NOT installed: Use admin with security warning (dev mode)
        
        Returns:
            str: Error message if authentication failed, None if successful
        """
        try:
            # Check if auth_api_key module provides the authentication method
            ir_http = request.env['ir.http']
            
            if hasattr(ir_http, '_auth_method_api_key'):
                # Module is installed - API key is MANDATORY
                api_key_header = request.httprequest.environ.get('HTTP_API_KEY')
                
                if not api_key_header:
                    error_msg = (
                        "API key is required but not provided. "
                        "Please configure your MCP client to include the 'Api-Key' header. "
                        "Example: Api-Key: your-api-key-here"
                    )
                    _logger.warning(f"MCP authentication failed: {error_msg}")
                    return error_msg
                
                # Try to authenticate with provided API key
                try:
                    ir_http._auth_method_api_key()
                    _logger.debug(f"MCP authenticated via API key for user ID: {request.uid}")
                    return None  # Success
                except AccessDenied:
                    error_msg = (
                        "Invalid API key. Authentication failed. "
                        "Please check your API key configuration."
                    )
                    _logger.warning(f"MCP authentication failed: Invalid API key provided")
                    return error_msg
            else:
                # Module not installed - Development mode with warning
                if not hasattr(request, '_mcp_auth_warning_logged'):
                    _logger.warning(
                        "MCP Security Warning: Running with sudo() privileges. "
                        "For production use, please install 'auth_api_key' module for proper authentication. "
                        "Install from: https://apps.odoo.com/apps/modules/browse?search=auth_api_key"
                    )
                    request._mcp_auth_warning_logged = True
                
                # Set to admin user
                request_update_env(request, request.env.ref('base.user_admin').id)

                return None  # Success (with warning logged)
                
        except Exception as e:
            error_msg = f"Authentication error: {str(e)}"
            _logger.error(f"MCP authentication error: {e}")
            return error_msg

    def _handle_sse_stream(self):
        """Handle GET request - establish SSE stream."""
        def stream():
            yield "event: endpoint\ndata: /mcp\n\n"

        return WerkzeugResponse(
            stream(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
                'Access-Control-Allow-Origin': '*',
            }
        )

    def _handle_json_rpc(self):
        """Handle POST request - process JSON-RPC messages."""
        try:
            payload = json.loads(request.httprequest.get_data(as_text=True))
            method = payload.get('method')
            
            # Check if this is a notification (no id field)
            is_notification = payload.get('id') is None
            
            # Handle notifications - no response needed
            if is_notification and method.startswith('notifications/'):
                self._handle_notification(method, payload.get('params', {}))
                return WerkzeugResponse('', status=202)
            
            # Handle regular requests
            result = self._process_mcp_method(method, payload.get('params', {}))
            
            return self._json_response({
                "jsonrpc": "2.0",
                "id": payload.get('id'),
                "result": result
            })

        except json.JSONDecodeError:
            return self._json_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }, 400)
            
        except Exception as e:
            import traceback
            _logger.error(f"MCP Error: {e}\n{traceback.format_exc()}")
            
            return self._json_response({
                "jsonrpc": "2.0",
                "id": payload.get('id') if 'payload' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                    "data": traceback.format_exc()
                }
            }, 500)

    def _handle_notification(self, method, params):
        """Handle JSON-RPC notifications (no response required)."""
        _logger.debug(f"MCP notification received: {method}")
        
        if method == 'notifications/initialized':
            _logger.debug("MCP client initialization complete")

    def _json_response(self, data, status=200):
        """Create JSON response with CORS headers."""
        return WerkzeugResponse(
            json.dumps(data, ensure_ascii=False),
            status=status,
            mimetype='application/json',
            headers={'Access-Control-Allow-Origin': '*'}
        )

    def _process_mcp_method(self, method, params):
        """Route MCP method to handler."""
        handlers = {
            'initialize': self._handle_initialize,
            'tools/list': self._handle_list_tools,
            'tools/call': self._handle_call_tool,
        }
        
        handler = handlers.get(method)
        if not handler:
            raise Exception(f"Method not found: {method}")
        
        return handler(params)
    
    def _handle_initialize(self, params):
        """Handle initialize request."""
        _logger.debug(f"MCP initialize called with params: {params}")
        
        return {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "Odoo-MCP-Server",
                "version": "1.0.0"
            }
        }
    
    def _handle_list_tools(self, params):
        """Handle tools/list request."""
        tools = []
        
        for model_name, model_cls in request.env.registry.models.items():
            for attr_name, method in model_cls.__base__.__dict__.items():  # Get from definition type.
                if callable(method) and getattr(method, '_is_mcp_tool', False):
                    # Get the original schema
                    schema = getattr(method, '_mcp_schema', {"type": "object"})
                    
                    # Add built-in properties to schema.
                    schema = self._add_built_in_properties(method, schema)
                    
                    tools.append({
                        "name": f"{model_name}:{attr_name}",
                        "description": getattr(method, '_mcp_desc', ""),
                        "inputSchema": schema
                    })
        
        _logger.debug(f"MCP found {len(tools)} tools")
        return {"tools": tools}
    
    def _handle_call_tool(self, params):
        """Handle tools/call request."""
        name = params.get('name')
        arguments = params.get('arguments', {})
        
        _logger.debug(f"MCP calling tool: {name} with args: {arguments}")
        
        try:
            model_name, method_name = name.split(':')
            # Use the already authenticated request.env
            model = request.env[model_name]
            
            # Extract `_search_` parameter if present
            search = arguments.pop('_search_', None)
            
            # If `search` is provided and not empty, filter records
            if search:
                # For recordset methods, apply search to get filtered recordset
                recordset = model.search(**search)
                result = getattr(recordset, method_name)(**arguments)
            else:
                # No search, call method on model directly (for @api.model or empty recordset)
                result = getattr(model, method_name)(**arguments)
            
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result) if not isinstance(result, str) else result
                }]
            }
            
        except Exception as e:
            import traceback
            _logger.error(f"MCP tool execution error: {e}\n{traceback.format_exc()}")
            
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True
            }

    @classmethod
    def _add_built_in_properties(cls, method: callable, schema: dict) -> dict:
        """Add built-in properties to tool schema.

        Args:
            method: The MCP tool method.
            schema: The JSON schema to modify
        """
        schema = schema.copy()
        properties = schema.get("properties", {}).copy()

        # Add `_search_` parameter for recordset level method with all search() options.
        odoo_api = getattr(method, "_api", None)
        if odoo_api != "model" and odoo_api != "model_create":
            properties['_search_'] = {
                "type": "object",
                "description": "Parameters for Odoo ORM model's `search` method. "
                               "If specified, this method will be invoked on search result recordset. "
                               "If not, this method will be invoked on model level.",
                "properties": {
                    "args": {
                        "type": "array",
                        "description": "Odoo ORM domain: [[field, op, value], ...]. "
                                       "Empty list means all records, use it with caution.",
                        "default": []
                    },
                    "offset": {"type": "integer", "default": 0},
                    "limit": {"type": "integer", "default": None},
                    "order": {"type": "string", "description": "e.g. 'name asc'", "default": None},
                },
                "required": ["args"],
                "additionalProperties": False,
                "default": None
            }

        # Update schema.
        if properties:
            schema["properties"] = properties

        return schema
