# -*- coding: utf-8 -*-
# @Time         : 17:02 2026/5/9
# @Author       : Chris
# @Description  :
from odoo import models, fields


class OqlIrModelAccess(models.Model):
    _inherit = "ir.model.access"

    perm_oql_fac_default_read = fields.Boolean("OQL Field Default Read Access", default=True)
    perm_oql_fac_default_write = fields.Boolean("OQL Field Default Write Access", default=True)
    oql_fac_ids = fields.One2many("oql.acl.field", "mac_id", "OQL Field ACL")

    def action_open_form_view(self):
        """Open the form view for the current access record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Access Rights',
            'res_model': 'ir.model.access',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
