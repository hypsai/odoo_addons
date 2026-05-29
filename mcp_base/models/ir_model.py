# -*- coding: utf-8 -*-
from odoo import fields, models


class McpBaseIrModel(models.Model):
    _inherit = "ir.model"

    mcp_tool_ids = fields.One2many(
        "mcp.base.tool", "model_id",
        string="MCP Tools",
        help="MCP tools defined for this model.",
        context={'active_test': False},
    )
