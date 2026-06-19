# @Time         : 10:26 2026/4/24
# @Author       : Chris
# @Description  :
import json
import logging
import traceback
from base64 import b64decode

from odoo import http
from odoo.exceptions import AccessDenied
from odoo.http import request
from werkzeug.wrappers import Response as WerkzeugResponse

from ..compatible import request_update_env, root_patch_get_request, is_api_model, session_authenticate
from .. import jsonutil

_logger = logging.getLogger(__name__)
_MCP_HANDLERS = {
    'initialize': '_handle_initialize',
    'tools/list': '_handle_list_tools',
    'tools/call': '_handle_call_tool',
}
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
        - Otherwise: uses Odoo built-in HTTP Basic Auth (username + password)
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
        - If auth_api_key is NOT installed: Use Odoo built-in HTTP Basic Auth (username + password)

        Returns:
            str: Error message if authentication failed, None if successful
        """
        # Check if auth_api_key module provides the authentication method
        ir_http = request.env['ir.http']
        api_key_header = request.httprequest.environ.get('HTTP_API_KEY')

        if api_key_header and hasattr(ir_http, '_auth_method_api_key'):
            # Module is installed - API key is MANDATORY

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
                request_update_env(request, request.uid)
                return None  # Success
            except AccessDenied:
                error_msg = (
                    "Invalid API key. Authentication failed. "
                    "Please check your API key configuration."
                )
                _logger.warning(f"MCP authentication failed: Invalid API key provided")
                return error_msg
        else:
            # auth_api_key not installed - try plain text headers first, then Basic Auth
            user_header = request.httprequest.environ.get('HTTP_X_USER', '')
            pass_header = request.httprequest.environ.get('HTTP_X_PASSWORD', '')

            if user_header and pass_header:
                # Plain text credentials via X-User / X-Password headers
                return self._authenticate_with_credentials(user_header, pass_header)

            # Fall back to standard Basic Auth (base64 encoded)
            auth_header = request.httprequest.environ.get('HTTP_AUTHORIZATION', '')
            if auth_header and auth_header.startswith('Basic '):
                try:
                    decoded = b64decode(auth_header[6:]).decode('utf-8')
                    if ':' not in decoded:
                        return "Invalid credentials format in Basic Auth header."
                    username, password = decoded.split(':', 1)
                    return self._authenticate_with_credentials(username, password)
                except Exception as e:
                    _logger.error(f"MCP Basic Auth decode error: {e}")
                    return f"Authentication error: {str(e)}"

            _logger.debug("MCP: No valid credentials provided")
            return (
                "Authentication required. "
                "Use X-User/X-Password headers or HTTP Basic Auth."
            )

    def _authenticate_with_credentials(self, username, password):
        """Authenticate with username/password and set request uid."""
        try:
            uid = session_authenticate(request, username, password)
            if not uid:
                raise AccessDenied("Invalid username or password")

            _logger.debug(f"MCP authenticated user: {username}")
            request_update_env(request, uid)
            return None  # Success
        except AccessDenied:
            _logger.warning("MCP authentication failed: Invalid credentials")
            return "Authentication failed. Invalid username or password."
        except Exception as e:
            _logger.error(f"MCP authentication error: {e}")
            return f"Authentication error: {str(e)}"

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
        payload = None
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
            _logger.error(f"MCP Error: {e}\n{traceback.format_exc()}")

            return self._json_response({
                "jsonrpc": "2.0",
                "id": payload.get('id') if payload else None,
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
            jsonutil.dumps(data),
            status=status,
            mimetype='application/json',
            headers={'Access-Control-Allow-Origin': '*'}
        )

    def _process_mcp_method(self, method, params):
        """Route MCP method to handler."""
        handler_name = _MCP_HANDLERS.get(method)
        if not handler_name:
            raise Exception(f"Method not found: {method}")

        return getattr(self, handler_name)(params)

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
        """Handle tools/list request. Reads tool definitions from the ORM,
        filtered by per-tool ACL."""
        tools = []
        Tool = request.env['mcp.base.tool']
        AclTool = request.env['mcp.base.tool.acl'].sudo()
        permitted_ids = AclTool.perm_tools()
        if not permitted_ids:
            return {"tools": []}

        for rec in Tool.search([('id', 'in', list(permitted_ids))]):
            model_name = rec.model_id.model
            method_name = rec.method_id.name

            input_schema = rec.input_schema
            if input_schema:
                input_schema = json.loads(input_schema)
            else:
                input_schema = {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }

            tool_info = {
                "name": f"{model_name}:{method_name}",
                "description": rec.description or "",
                "inputSchema": input_schema,
            }

            # Add _search_ built-in property if the target method is not an API model.
            model_cls = request.env.registry.get(model_name)
            if model_cls:
                method = getattr(model_cls, method_name, None)
                if method and not is_api_model(method):
                    tool_info["inputSchema"] = self._add_built_in_properties(
                        method, tool_info["inputSchema"],
                    )

            tools.append(tool_info)

        _logger.debug(f"MCP found {len(tools)} tools")
        return {"tools": tools}
    
    def _handle_call_tool(self, params):
        """Handle tools/call request."""
        name = params.get('name')
        arguments = dict(params.get('arguments', {}))

        _logger.info(f"User[{request.env.user.id}] calling MCP tool: {name} with args: {arguments}")

        try:
            model_name, method_name = name.split(':')

            # Verify the tool is registered and active in ORM.
            tool = request.env['mcp.base.tool'].sudo().search([
                ('model_id.model', '=', model_name),
                ('method_id.name', '=', method_name),
                ('active', '=', True),
            ], limit=1)
            if not tool:
                return {
                    "content": [{"type": "text", "text": f"Tool not found: {name}"}],
                    "isError": True,
                }

            # Verify the user is permitted to call this tool (ACL).
            permitted_ids = request.env['mcp.base.tool.acl'].sudo().perm_tools()
            if tool.id not in permitted_ids:
                return {
                    "content": [{"type": "text", "text": f"Tool not permitted: {name}"}],
                    "isError": True,
                }

            model = request.env[model_name]

            # Extract `_search_` parameter if present
            search = arguments.pop('_search_', None)

            # If `search` is provided and not empty, filter records
            if search:
                recordset = model.search(**search)
                result = getattr(recordset, method_name)(**arguments)
            else:
                result = getattr(model, method_name)(**arguments)

            return {
                "content": [{
                    "type": "text",
                    "text": jsonutil.dumps(result) if not isinstance(result, str) else result
                }]
            }

        except Exception as e:
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
        if not is_api_model(method):
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
