# -*- coding: utf-8 -*-
# Generic Dagster job model.
import yaml
from odoo import models, fields, api

from .util import get_dagster_client
from ..utils import strutil, yamlutil
from ..utils.dagster import PARTITION_NAME_TAG, RUN_KEY_TAG
from ..utils.strutil import parse_vars


class DagsterJob(models.Model):
    _name = "dagster.job"
    _description = "Manage DagsterJob."
    _rec_name = "name"

    name = fields.Char("Name", required=True)
    key = fields.Char("Key", required=True, help="Job name in Dagster.")
    run_config_tmpl = fields.Text("Run Config Template (Yaml)")
    run_ids = fields.One2many("dagster.run", "job_id", "Runs")

    # Aux
    run_config_tmpl_hints_html = fields.Html("Run Config Template Vars", compute="_compute_run_config_tmpl_hints_html")

    @api.depends("run_config_tmpl")
    def _compute_run_config_tmpl_hints_html(self):
        for rec in self:
            list_vars = parse_vars(rec.run_config_tmpl) if rec.run_config_tmpl else None
            if list_vars:
                html = "<span>, </span>".join(f"<b>{x.name}</b>" if x.required else f"<span>{x.name} (optional)</span>"
                                              for x in list_vars)
            else:
                html = "<span>(no variables)</span>"
            rec.run_config_tmpl_hints_html = html

    def get_job(self, key: str):
        job = self.search([("key", "=", key)])
        if not job:
            raise Exception(f"Dagster job '{key}' not found in database.")
        return job

    def _get_dagster_client(self):
        """Extension point: client to use for this recordset."""
        return get_dagster_client(self)

    def run(self, platform: str, run_key: str = None, run_config=None, tags=None):
        DagsterRun = self.env["dagster.run"]
        runs = []
        client = self._get_dagster_client()
        for rec in self:
            if client is None:
                continue
            run_id = client.graphql.submit_job_execution(rec.key,
                                                         tags={
                                                             "fodoo": platform,
                                                             PARTITION_NAME_TAG: platform,
                                                             RUN_KEY_TAG: run_key,
                                                             **(tags or {}),
                                                         },
                                                         run_config=run_config)
            runs.append(DagsterRun.create({"key": run_id, "job_id": rec.id}))
        return DagsterRun.concat(*runs)

    def call(self, platform: str, run_key: str = None, tags=None, **kwargs):
        """Run with run_config_tmpl filled by kwargs."""
        DagsterRun = self.env["dagster.run"]
        runs = []
        client = self._get_dagster_client()
        for rec in self:
            if client is None:
                continue
            if rec.run_config_tmpl:
                safe_kwargs = {k: yamlutil.escape_dump(v) for k, v in kwargs.items()}
                str_run_config = strutil.substitute(rec.run_config_tmpl, safe_kwargs)
                run_config = yaml.safe_load(str_run_config)
            else:
                run_config = None
            run_id = client.graphql.submit_job_execution(rec.key,
                                                         tags={
                                                             "fodoo": platform,
                                                             PARTITION_NAME_TAG: platform,
                                                             RUN_KEY_TAG: run_key,
                                                             **(tags or {}),
                                                         },
                                                         run_config=run_config)
            runs.append(DagsterRun.create({"key": run_id, "job_id": rec.id}))
        return DagsterRun.concat(*runs)

    def action_open_detail(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'views': [(self.env.ref('dagster.dagster_job_from_view').id, 'form')],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'dialog_size': 'large',
            },
        }
