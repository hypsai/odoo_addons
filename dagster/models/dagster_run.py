# -*- coding: utf-8 -*-
# Generic Dagster run model.
from odoo import models, fields


class DagsterRun(models.Model):
    _name = "dagster.run"
    _description = "Dagster Run"
    _rec_name = "key"

    job_id = fields.Many2one("dagster.job", required=True, ondelete="cascade")
    key = fields.Char("Key", required=True, help="Dagster Run ID")
