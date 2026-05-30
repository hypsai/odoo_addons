# @Time         : 16:05 2026/5/29
# @Author       : Chris
# @Description  :
from odoo import models, fields


class McpBaseIrModelAccess(models.Model):
    _inherit = "ir.model.access"

    perm_mcp_base_tool_default_read = fields.Boolean(
        "MCP Tool Default Read Access", default=True,
        help="Default read access for MCP tools under this model. "
             "Can be overridden per-tool via Tool ACL entries.",
    )
    mcp_base_tac_ids = fields.One2many(
        "mcp.base.tool.acl", "mac_id", "MCP Tool ACL",
    )
