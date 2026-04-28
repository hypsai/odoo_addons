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
        return [{"name": "Mary"}, {"name", "Lily"}, {"name": "Tom"}]
