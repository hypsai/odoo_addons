# -*- coding: utf-8 -*-
"""Per-tool read access control layered on top of ``ir.model.access``.

A tool appears in ``tools/list`` when:

1. The user has ``ir.model.access.perm_read = True`` for the tool's model, AND
2. The tool's ``perm_read`` is True — either set explicitly on the ACL record,
   or falling back to ``perm_mcp_tool_default_read`` on the ``ir.model.access``.
"""
from odoo import fields, models, api

from ..compatible import model_flush


class McpBaseToolAcl(models.Model):
    _name = "mcp.base.tool.acl"
    _description = "MCP Tool Access Control"
    _rec_name = "tool_id"

    mac_id = fields.Many2one(
        "ir.model.access", "Model Access", required=True, ondelete="cascade",
    )
    tool_id = fields.Many2one(
        "mcp.base.tool", "Tool", required=True, ondelete="cascade",
        domain="[('model_id', '=', model_id)]",
    )
    perm_read = fields.Boolean("Read Access", default=True)

    # Aux
    model_id = fields.Many2one(related="mac_id.model_id")

    _sql_constraints = [
        ("mac_tool_unique", "unique(mac_id, tool_id)",
         "Tool must be unique per model access record."),
    ]

    @api.model
    def perm_tools(self):
        """Return the set of ``mcp.base.tool`` ids visible to the current user.

        A tool is visible when the user has ``perm_read`` on the model AND
        the tool-level ACL (or its default) allows read.
        """
        if self.env.su:
            Tool = self.env['mcp.base.tool'].sudo()
            return set(Tool.search([('active', '=', True)]).ids)

        model_flush(self.env["ir.model.access"])
        model_flush(self)
        model_flush(self.env["mcp.base.tool"], ["active"])

        self.env.cr.execute("""
            SELECT DISTINCT d.id
            FROM res_groups_users_rel a
                JOIN ir_model_access b ON a.gid = b.group_id AND b.perm_read = TRUE
                JOIN ir_model c ON b.model_id = c.id
                JOIN mcp_base_tool d ON c.id = d.model_id AND d.active = TRUE
                LEFT JOIN mcp_base_tool_acl e
                    ON (b.id = e.mac_id AND d.id = e.tool_id)
            WHERE b.active AND a.uid = %s
            GROUP BY d.id
            HAVING BOOL_OR(
                COALESCE(e.perm_read, b.perm_mcp_base_tool_default_read, FALSE)
            )
        """, (self.env.uid,))
        return {row[0] for row in self.env.cr.fetchall()}
