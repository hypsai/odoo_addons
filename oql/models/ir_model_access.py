# @Time         : 17:02 2026/5/9
# @Author       : Chris
# @Description  :
from typing import Literal, Set

from odoo import models, fields, api

from ..compatible import model_flush

ModelMode = Literal["read", "write", "create", "unlink"]


class OqlIrModelAccess(models.Model):
    _inherit = "ir.model.access"

    perm_oql_fac_default_read = fields.Boolean("OQL Field Default Read Access", default=True)
    perm_oql_fac_default_write = fields.Boolean("OQL Field Default Write Access", default=True)
    oql_fac_ids = fields.One2many("oql.acl.field", "mac_id", "OQL Field ACL")
    perm_oql_aac_default_read = fields.Boolean("OQL Alias Default Read Access", default=False)
    perm_oql_aac_default_write = fields.Boolean("OQL Alias Default Write Access", default=False)
    oql_aac_ids = fields.One2many("oql.acl.alias", "mac_id", "OQL Alias ACL")

    # ---- Cache invalidation ----
    # `oql.acl.field._perm_fields` / `oql.acl.alias._perm_aliases` results
    # depend on `ir.model.access` rows (group, perms, active, oql defaults),
    # so any change here must invalidate them. Odoo 15's clear_caches()
    # clears the shared registry cache, so this also covers other caches.

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env['oql.acl.field'].clear_caches()
        self.env['oql.acl.alias'].clear_caches()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env['oql.acl.field'].clear_caches()
        self.env['oql.acl.alias'].clear_caches()
        return result

    def unlink(self):
        result = super().unlink()
        self.env['oql.acl.field'].clear_caches()
        self.env['oql.acl.alias'].clear_caches()
        return result

    def perm_models(self, mode: ModelMode) -> Set[str]:
        """Return model names that have the specified `mode` access."""
        env = self.env
        if env.su:
            # Superuser has access to all models
            return set(env.registry.models.keys())

        # Query ir.model.access to find models with the specified permission
        model_flush(env["ir.model.access"])

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
