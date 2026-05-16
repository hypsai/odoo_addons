# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class OQLWebController(http.Controller):

    @http.route('/oql', type='http', auth='user', website=True, methods=['GET'], csrf=False)
    def oql_workbench(self, **kwargs):
        """
        OQL Workbench - A Navicat-like interface for executing OQL queries.
        GET method displays the workbench UI.
        """
        return request.render('oql_web.oql_workbench_template')
    
    @http.route('/oql/workbench', type='http', auth='user', website=True, methods=['GET'], csrf=False)
    def oql_workbench_redirect(self, **kwargs):
        """
        Redirect /oql/workbench to /oql (same page, just an alias).
        """
        return request.render('oql_web.oql_workbench_template')
    
    @http.route('/oql/user', type='json', auth='user')
    def oql_get_user(self):
        """
        Get current user information.
        
        :return: User name and ID
        """
        user = request.env.user
        return {
            'success': True,
            'user': {
                'name': user.name,
                'id': user.id,
                'login': user.login
            }
        }
    
    @http.route('/oql/preferences/save', type='json', auth='user')
    def oql_save_preferences(self, preferences):
        """
        Save user preferences (tabs, queries, etc.) to localStorage via RPC.
        
        :param preferences: User preferences object
        :return: Success status
        """
        # In a real implementation, you might save to database
        # For now, we'll just acknowledge the save
        return {'success': True}
    
    @http.route('/oql/preferences/load', type='json', auth='user')
    def oql_load_preferences(self):
        """
        Load user preferences.
        
        :return: User preferences or empty object
        """
        # Return empty preferences - actual storage will be in localStorage
        return {'success': True, 'preferences': {}}
    
    @http.route('/oql/state/save', type='json', auth='user')
    def oql_save_state(self, state):
        """
        Save workbench state for current user (auto-save).
        
        :param state: Complete workbench state object
        :return: Success status
        """
        try:
            request.env['oql.workbench.state'].sudo().create_or_update_state(state)
            return {'success': True}
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/oql/state/load', type='json', auth='user')
    def oql_load_state(self):
        """
        Load workbench state for current user.
        
        :return: Workbench state or empty object
        """
        try:
            state = request.env['oql.workbench.state'].sudo().get_user_state()
            return {
                'success': True,
                'state': state
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'state': {}
            }
    
    @http.route('/oql/state/save', type='json', auth='user')
    def oql_save_state(self, state):
        """
        Save workbench state for current user (auto-save).
        
        :param state: Complete workbench state object
        :return: Success status
        """
        try:
            request.env['oql.workbench.state'].sudo().create_or_update_state(state)
            return {'success': True}
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/oql/state/load', type='json', auth='user')
    def oql_load_state(self):
        """
        Load workbench state for current user.
        
        :return: Workbench state or empty object
        """
        try:
            state = request.env['oql.workbench.state'].sudo().get_user_state()
            return {
                'success': True,
                'state': state
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'state': {}
            }
