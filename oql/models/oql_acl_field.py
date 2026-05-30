# @Time         : 20:33 2026/5/9
# @Author       : Chris
# @Description  :
from typing import Literal, Set

from odoo import fields, models, api

from ..compatible import model_flush


class OqlAclField(models.Model):
    """
    OQL field ACL follows different rules from Odoo's ACL.
    1. Related field.
    Example field: `name = fields.Char(related="tmpl_id.name")`
    1.1 From up to down, related field's access right is defined by itself, it can penetrate Odoo ACL.
        e.g. If `name` is configured readable for a user, the user will be able to read `name`
             no matter he has or has not access right to `tmpl_id` or the relational model or the relational model's `name` field.
    2.2 From down to up, Related field can inherit access from its target field.
        e.g. If related `tmpl_id.name` is readable, then `name` field itself is readable.
    """

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
    def perm_fields(self, model: str, mode: Literal["read", "write"]) -> Set[str]:
        """Check field access rights of the given model, and return all the fields that have given `mode` access right."""
        if self.env.su:
            # User root have all accesses
            return set(self.env[model]._fields)

        model_flush(self.env["ir.model.access"])
        model_flush(self, self._fields)

        sql = f"""
        SELECT d.name
        FROM res_groups_users_rel a
            JOIN ir_model_access b ON a.gid = b.group_id
            JOIN ir_model c ON b.model_id = c.id
            JOIN ir_model_fields d ON b.model_id = d.model_id
            LEFT JOIN oql_acl_field e ON (b.id = e.mac_id AND d.id = e.field_id)
        WHERE b.active AND a.uid = %s AND c.model = %s
        GROUP BY d.id
        HAVING BOOL_OR(b.perm_{mode} AND COALESCE(e.perm_{mode}, b.perm_oql_fac_default_{mode}, FALSE))
        """
        self.env.cr.execute(sql, (self.env.uid, model))
        field_names = {row[0] for row in self.env.cr.fetchall()}

        if mode == "read" and "id" not in field_names:
            field_names.add("id")  # ID is always readable.

        return field_names
