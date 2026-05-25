from odoo import fields, models

from ..compatible import make_sql_constraint


class OqlTermDomain(models.Model):
    _name = "oql.term.domain"
    _description = "Domain defined for a term, which is used to retrieve related records from ORM."
    _rec_name = "name"
    _order = "term_id, model_id, name, id"

    name = fields.Char("Name", required=True, index=True,
                       help="Name that is used to identify the domain. "
                            "`self.field_name` is a naming convention, "
                            "means this domain will be applied to `res_model.field_name`."
                            "If `res_model` has a field named `field_name` refers to term of "
                            "this domain by many2one or many2many relation. This domain will"
                            "be merged into the relation term domain with `and` logic.")
    term_id = fields.Many2one("oql.term", "Term", required=True, ondelete="cascade", index=True)
    model_id = fields.Many2one("ir.model", "Model", help="Target model this term domain applied to.",
                               required=True, ondelete="cascade", index=True)
    domain = fields.Text("Domain", required=True, help="The domain used to filter model records.")

    _sql_constraints = [make_sql_constraint("term_id_model_id_name_unique", "unique(term_id, model_id, name)", "Term domain for each model should be unique.")]
