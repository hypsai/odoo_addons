from odoo import fields, models


class OqlAliasLine(models.Model):
    _name = "oql.alias.line"
    _description = "Config field path inference rules for ORM models."
    _rec_name = "alias"

    alias = fields.Char("Alias", required=True, help="An alias name for the path.")
    rule_id = fields.Many2one("oql.alias", "Rule", required=True, ondelete="cascade")
    operators = fields.Char("Operators", help="The operators this rule line applied to, split with comma. Emtpy means all operators.")
    value_model_id = fields.Many2one("ir.model", "Value Model", help="Target model the rules applied to.")
    value_types = fields.Selection([("bool", "Boolean"), ("int", "Integer"), ("float", "Float"),
                                    ("str", "String"), ("date", "Date"), ("datetime", "DateTime"), ("binary", "Binary")],
                                   "Value Types", help="The target right operand types this rule applied to.")
    path = fields.Char("Field Path", required=True,
                       help="In dot path style. When the pattern meets, will use this path to evaluate oql expression.")

    _sql_constraints = [("rule_id_alias_unique", "unique(rule_id, alias)", "Alias in each field path set must be unique.")]
