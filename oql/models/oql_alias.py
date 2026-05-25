from odoo import fields, models

from ..compatible import make_sql_constraint


class OqlAlias(models.Model):
    _name = "oql.alias"
    _description = "OQL Alias"

    model_id = fields.Many2one("ir.model", "Model", help="Target model the rules applied to.",
                               required=True, ondelete="cascade", index=True)
    line_ids = fields.One2many("oql.alias.line", "rule_id", "Rule Lines")

    _sql_constraints = [make_sql_constraint("model_id_unique", "unique(model_id)", "Each model can have at most 1 field path rule, please add new rule as rule line of existing rule.")]
