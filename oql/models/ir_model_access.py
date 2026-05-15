# -*- coding: utf-8 -*-
# @Time         : 17:02 2026/5/9
# @Author       : Chris
# @Description  :
from typing import Literal, Set

from odoo import models, fields


class OqlIrModelAccess(models.Model):
    _inherit = "ir.model.access"

    perm_oql_fac_default_read = fields.Boolean("OQL Field Default Read Access", default=True)
    perm_oql_fac_default_write = fields.Boolean("OQL Field Default Write Access", default=True)
    oql_fac_ids = fields.One2many("oql.acl.field", "mac_id", "OQL Field ACL")
    oql_aac_ids = fields.One2many("oql.acl.alias", "mac_id", "OQL Alias ACL")

    def perm_models(self, mode: Literal["read", "write"]) -> Set[str]:
        """Return model names that have the specified `mode` access."""
        env = self.env
        if env.su:
            # Superuser has access to all models
            return set(env.registry.models.keys())

        # Query ir.model.access to find models with the specified permission
        env["ir.model.access"].flush()

        sql = f"""
        SELECT DISTINCT c.model
        FROM res_groups_users_rel a
            JOIN ir_model_access b ON a.gid = b.group_id
            JOIN ir_model c ON b.model_id = c.id
        WHERE b.active AND a.uid = %s AND b.perm_{mode} = true
        """
        env.cr.execute(sql, (env.uid,))
        model_names = {row[0] for row in env.cr.fetchall()}

        return model_names

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
