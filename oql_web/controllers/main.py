# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class OQLWebController(http.Controller):

    @http.route('/oql', type='http', auth='user', website=True, methods=['GET'], csrf=False)
    def oql_workbench(self, **kwargs):
        """
        OQL Query Workbench - A Navicat-like interface for executing OQL queries.
        GET method displays the workbench UI.
        """
        return request.render('oql_web.oql_workbench_template')
    
    @http.route('/oql/models', type='json', auth='user')
    def oql_get_models(self):
        """
        Get list of all available models.
        
        :return: List of model names
        """
        try:
            models = request.env['ir.model'].sudo().search([]).mapped('model')
            return {
                'success': True,
                'models': sorted(models)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
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
