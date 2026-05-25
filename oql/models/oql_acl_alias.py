# -*- coding: utf-8 -*-
# @Time         : 20:33 2026/5/9
# @Author       : Chris
# @Description  :
from typing import Literal, Set

from odoo import fields, models, api

from ..compatible import sql_constraints


@sql_constraints(
    ("mac_alias_unique", "unique(mac_id, alias_id)",
     "Alias must be unique in a model's alias access collection."),
)
class OqlAclAlias(models.Model):
    """
    OQL Alias ACL can penetrate Odoo ACL. Which means if the alias's access right is defined by the ACL of itself.
    """

    _name = "oql.acl.alias"
    _description = "OQL Alias Access Control"
    _rec_name = "alias_id"

    mac_id = fields.Many2one("ir.model.access", "Model Access", required=True, ondelete="cascade")
    alias_id = fields.Many2one("oql.alias.line", "Alias", required=True, ondelete="cascade",
                               domain="[('model_id', '=', model_id)]")
    perm_read = fields.Boolean("Read Access")
    perm_write = fields.Boolean("Write Access")

    # Aux
    model_id = fields.Many2one(related="mac_id.model_id")

    @api.model
    def perm_aliases(self, model: str, mode: Literal["read", "write"]) -> Set[str]:
        """Check field access rights of the given model, and return all the fields that have given `mode` access right."""
        if self.env.su:
            # User root have all accesses
            return set(self.env["oql.alias.line"].search([("model_id.model", "=", model)]).mapped("alias"))

        self.env["ir.model.access"].flush()
        self.flush(self._fields)

        sql = f"""
        SELECT d.alias
        FROM res_groups_users_rel a
            JOIN ir_model_access b ON a.gid = b.group_id
            JOIN ir_model c ON b.model_id = c.id
            JOIN oql_alias_line d ON b.model_id = d.model_id
            LEFT JOIN oql_acl_alias e ON (b.id = e.mac_id AND d.id = e.alias_id)
        WHERE b.active AND a.uid = %s AND c.model = %s
        GROUP BY d.id
        HAVING BOOL_OR(b.perm_{mode} AND COALESCE(e.perm_{mode}, b.perm_oql_aac_default_{mode}, FALSE))
        """
        self.env.cr.execute(sql, (self.env.uid, model))
        field_names = {row[0] for row in self.env.cr.fetchall()}

        return field_names
