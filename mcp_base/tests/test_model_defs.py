# -*- coding: utf-8 -*-
# @Time         : 11:10 2026/4/28
# @Author       : Chris
# @Description  :
from odoo import models

from ..decorators import mcp_tool


class TestMcpBaseTool(models.Model):
    _name = "test.mcp.base.tool"
    _description = "MCP Tool Test"

    @mcp_tool
    def get_customers(self):
        """Get all customers."""
        return [{"name": "Mary"}, {"name": "Lily"}, {"name": "Tom"}]


def ensure_model_meta(env, model_names):
    """
    Insert model meta into `ir.model` manually.
    """
    for model_name in model_names:
        # Search for existing model record
        meta = env["ir.model"].search([("model", "=", model_name)], limit=1)

        if not meta:
            model_class = env.registry.get(model_name)
            description = getattr(model_class, '_description', '') if model_class else ''
            is_abstract = getattr(model_class, '_abstract', False) if model_class else False
            is_transient = getattr(model_class, '_transient', False) if model_class else False

            # Create complete model metadata with all required fields
            env["ir.model"].create({
                'model': model_name,
                'name': description or model_name.replace('.', ' ').title(),
                'state': 'base',
                'info': description,
                'transient': is_transient,
                'order': 'id',  # Default ordering
            })
