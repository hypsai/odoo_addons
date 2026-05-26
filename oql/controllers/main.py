# -*- coding: utf-8 -*-
# @Time         : 10:00 2026/5/16
# @Author       : Chris
# @Description  :
import logging

from odoo import http
from odoo.http import request

from ..compatible import jsonrpc

_logger = logging.getLogger(__name__)


class OqlController(http.Controller):

    # ---- Workbench page ----

    @http.route('/oql', type='http', auth='user')
    def oql_workbench(self):
        """Render the OQL Workbench SPA."""
        return request.render('oql.oql_workbench_template')

    # ---- JSON-RPC endpoints ----

    @http.route('/oql/query', type=jsonrpc, auth='user', csrf=False)
    def oql_query(self, query):
        """Execute OQL query and return result as list of dict."""
        _logger.debug("OQL query from user %s (ID %s): %s",
                       request.env.user.name, request.env.uid, query)
        return request.env["base"].oql(query)

    @http.route('/oql/models', type=jsonrpc, auth='user')
    def oql_models(self):
        """Get list of all available models."""
        try:
            models = request.env['ir.model.access'].perm_models("read")
            return {
                'success': True,
                'models': sorted(models)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/oql/user', type=jsonrpc, auth='user')
    def oql_user(self):
        """Get current user info."""
        try:
            user = request.env.user.sudo()
            return {
                'success': True,
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'login': user.login,
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/oql/hint', type=jsonrpc, auth='user', csrf=False)
    def oql_hint(self, model, content, cursor_index, limit=1000, offset=0):
        """Provide code completion hints for the OQL editor.
        
        Delegates to the model's ``oql_hint`` method (post-transform context)
        or ``hinto`` method (pre-transform context, e.g. WHERE clause).
        """
        try:
            hints = request.env[model].sudo().oql_hint(content, cursor_index,
                                                        limit=limit, offset=offset)
            return {'hints': hints}
        except Exception as e:
            _logger.debug("OQL hint error: %s", e)
            return {'hints': []}

    # ---- Workbench state sync (localStorage + cloud) ----

    @http.route('/oql/state/save', type=jsonrpc, auth='user', csrf=False)
    def oql_state_save(self, state):
        """Save workbench state to cloud for current user."""
        try:
            request.env['oql.workbench.state'].sudo().create_or_update_state(state)
            return {'success': True}
        except Exception as e:
            _logger.warning("OQL state save error: %s", e)
            return {'success': False, 'error': str(e)}

    @http.route('/oql/state/load', type=jsonrpc, auth='user')
    def oql_state_load(self):
        """Load workbench state from cloud for current user."""
        try:
            state = request.env['oql.workbench.state'].sudo().get_user_state()
            return {'success': True, 'state': state}
        except Exception as e:
            _logger.warning("OQL state load error: %s", e)
            return {'success': False, 'error': str(e)}
