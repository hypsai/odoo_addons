from odoo import fields, models


class OqlTerm(models.Model):
    _name = "oql.term"
    _description = "OQL terms which are used to form query."
    _rec_name = "name"

    name = fields.Char("Name", required=True, index=True)
    description = fields.Text("Description")
    domain_ids = fields.One2many("oql.term.domain", "term_id", "Domains",
                                 help="The domains used to filter model records. They are allied in `or` logic.")

    _sql_constraints = [("name_unique", "unique(name)", "Term name must be unique.")]
