from odoo import fields, models


class OqlAlias(models.Model):
    _name = "oql.alias"
    _description = "Config field path inference rules for ORM models."

    model_id = fields.Many2one("ir.model", "Model", help="Target model the rules applied to.",
                               required=True, ondelete="cascade", index=True)
    line_ids = fields.One2many("oql.alias.line", "rule_id", "Rule Lines")

    _sql_constraints = [("model_id_unique", "unique(model_id)",
                         "Each model can have at most 1 field path rule, please add new rule as rule line of existing rule.")]
