from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

from ..util import get_field_def, get_field_type
from ..alias import AliasNode
class OqlAliasLine(models.Model):
    _name = "oql.alias.line"
    _description = "Alias rule for field path."
    _rec_name = "alias"

    rule_id = fields.Many2one("oql.alias", "Rule", required=True, ondelete="cascade")
    model_id = fields.Many2one(related="rule_id.model_id", store=True, index=True)
    alias = fields.Char("Alias", required=True, help="An alias name for the path.")
    mode = fields.Selection([("field", "Field"), ("jmespath", "JMESPath"), ("jinja2", "Jinja2")],
                            "Path Mode", default="field", required=True)
    path = fields.Text("Field Path", required=True,
                       help="The field path this alias refers to. Could be simple field path or complex path, depends on `mode`.")
    enable_shorthand = fields.Boolean("Enable Shorthand",
                                      help="If enabled, user can omit `alias` in OQL statement."
                                           "Every value type should have at most one shorthand.")
    help = fields.Text("Help Text")

    _sql_constraints = [("rule_id_alias_unique", "unique(rule_id, alias)", "Alias in each field path set must be unique.")]

    @api.constrains("path")
    def _constrains_path(self):
        """Check path format."""
        for rec in self:
            if not rec.path:
                continue
            try:
                root = AliasNode.parse(rec.alias, rec.mode, rec.path)
                __ = root.read(self.env[self.model_id.model].sudo(), _check=True)  # Check field existence.
            except Exception as e:
                raise UserError(str(e))

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
            if rec.mode != "field":
                raise ValidationError(_("Only `Field` alias `%s` can be used as shorthand.") % (rec.path,))

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
