# -*- coding: utf-8 -*-
# @Time         : 20:33 2026/5/9
# @Author       : Chris
# @Description  :
from typing import Literal, List

from odoo import fields, models, api


class OqlAclField(models.Model):
    _name = "oql.acl.field"
    _description = "OQL Field Level Access Control"
    _rec_name = "field_id"

    mac_id = fields.Many2one("ir.model.access", "Model Access", required=True, ondelete="cascade")
    field_id = fields.Many2one("ir.model.fields", "Field", required=True, ondelete="cascade",
                               domain="[('model_id', '=', model_id)]")
    perm_read = fields.Boolean("Read Access")
    perm_write = fields.Boolean("Write Access")

    # Aux
    model_id = fields.Many2one(related="mac_id.model_id")

    _sql_constraints = [("mac_field_unique", "unique(mac_id, field_id)",
                         "Field must be unique in a model's field access collection.")]

    @api.model
    def check_fields(self, model: str, mode: Literal["read", "write"]) -> List[str]:
        """Check field access rights of the given model, and return all the fields that have given `mode` access right."""
        if self.env.su:
            # User root have all accesses
            return list(self.env[model]._fields)

        self.flush(self._fields)

        sql = f"""
        SELECT d.name
        FROM res_groups_users_rel a
            JOIN ir_model_access b ON a.gid = b.group_id
            JOIN ir_model c ON b.model_id = c.id
            JOIN ir_model_fields d ON b.model_id = d.model_id
            LEFT JOIN oql_acl_field e ON (b.id = e.mac_id AND d.id = e.field_id)
        WHERE a.uid = %s AND c.model = %s
        GROUP BY d.id
        HAVING BOOL_OR(COALESCE(e.perm_{mode}, b.perm_oql_fac_default_{mode}, FALSE))
        """
        self._cr.execute(sql, (self._uid, model))
        field_names = [row[0] for row in self._cr.fetchall()]

        if mode == "read" and "id" not in field_names:
            field_names.append("id")  # ID is always readable.

        return field_names
