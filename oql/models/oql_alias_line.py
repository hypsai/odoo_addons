from odoo import fields, models, api
from odoo.exceptions import UserError

from ..util import get_field_def, get_field_type


class OqlAliasLine(models.Model):
    _name = "oql.alias.line"
    _description = "Alias rule for field path."
    _rec_name = "alias"

    rule_id = fields.Many2one("oql.alias", "Rule", required=True, ondelete="cascade")
    alias = fields.Char("Alias", required=True, help="An alias name for the path.")
    path = fields.Char("Field Path", required=True,
                       help="The field path this alias refers to, in dot style. e.g. `product_id.name`")
    enable_shorthand = fields.Boolean("Enable Shorthand",
                                      help="If enabled, user can omit `alias` in OQL statement."
                                           "Every value type should have at most one shorthand.")

    _sql_constraints = [("rule_id_alias_unique", "unique(rule_id, alias)", "Alias in each field path set must be unique.")]

    @api.constrains("enable_shorthand")
    def _constrains_enable_shorthand(self):
        """
        Ensure that for each rule, there is at most one shorthand enabled per value type.
        This prevents ambiguity when using shorthand syntax like `@ = 'value'`.
        """
        env = self.env
        for rec in self:
            if not rec.enable_shorthand:
                continue

            model = rec.rule_id.model_id.model
            model_recs = env[model]
            rec_field_def = get_field_def(model_recs, rec.path)
            rec_field_type = get_field_type(rec_field_def)

            for line in rec.rule_id.line_ids:
                if not line.enable_shorthand or line.id == rec.id:
                    continue
                field_def = get_field_def(model_recs, line.path)
                field_type = get_field_type(field_def)
                if rec_field_type == field_type:
                    raise UserError(
                        f"Cannot enable shorthand for alias '{rec.alias}' (path: {rec.path}) "
                        f"because it has the same field type '{rec_field_type}' as other shorthand-enabled alias: {line.alias}. "
                        f"Each value type can have at most one shorthand alias per rule."
                    )
