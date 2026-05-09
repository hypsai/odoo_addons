from odoo import fields, models


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
