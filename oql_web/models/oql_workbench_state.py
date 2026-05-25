# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api

class OQLWorkbenchState(models.Model):
    _name = 'oql.workbench.state'
    _description = 'OQL Workbench User State'
    
    user_id = fields.Many2one(
        'res.users', 
        string='User', 
        required=True, 
        index=True,
        default=lambda self: self.env.user
    )
    state = fields.Text(
        string='Workbench State',
        default='{}',
        help='Complete workbench state including tabs, queries, and results (stored as JSON string)'
    )
    last_modified = fields.Datetime(
        string='Last Modified',
        default=fields.Datetime.now,
        readonly=True
    )

    _sql_constraints = [
        ('user_unique', 'UNIQUE(user_id)', 'Each user can only have one workbench state')
    ]

    def save_state(self, state_data):
        """Save workbench state for current user."""
        self.ensure_one()
        # Convert dict to JSON string if needed
        if isinstance(state_data, dict):
            state_json = json.dumps(state_data)
        else:
            state_json = state_data
            
        self.write({
            'state': state_json,
            'last_modified': fields.Datetime.now()
        })
        return True
    
    @api.model
    def get_user_state(self):
        """Get workbench state for current user."""
        user = self.env.user
        record = self.search([('user_id', '=', user.id)], limit=1)
        
        if record and record.state:
            try:
                return json.loads(record.state)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    @api.model
    def create_or_update_state(self, state_data):
        """Create or update workbench state for current user."""
        user = self.env.user
        record = self.search([('user_id', '=', user.id)], limit=1)
        
        # Convert dict to JSON string if needed
        if isinstance(state_data, dict):
            state_json = json.dumps(state_data)
        else:
            state_json = state_data
        
        if record:
            record.save_state(state_json)
        else:
            self.create({
                'user_id': user.id,
                'state': state_json,
                'last_modified': fields.Datetime.now()
            })
        
        return True
