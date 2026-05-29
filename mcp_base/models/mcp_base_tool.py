# -*- coding: utf-8 -*-
# @Time         : 15:37 2026/5/28
# @Author       : Chris
# @Description  : MCP Tool ORM Model - stores MCP tool definitions for config-first and code-first.
import json

from odoo import api, fields, models


class McpBaseTool(models.Model):
    _name = "mcp.base.tool"
    _description = "MCP Tool"
    _rec_name = "name"

    name = fields.Char(
        "Name", required=True, index=True,
        help="Display name for this MCP tool (e.g., 'Search Customers').",
    )
    model_id = fields.Many2one(
        "ir.model", "Model", required=True, readonly=True, ondelete="cascade", index=True,
        help="The Odoo model this tool operates on.  Immutable after creation.",
    )
    method_id = fields.Many2one(
        "mcp.base.method", "Method", required=True,
        ondelete="restrict",
        help="Python method on the selected model to expose as an MCP tool.",
        domain="[('model_id', '=', model_id)]",
    )
    docstring = fields.Text(
        "Docstring",
        help="Custom docstring in Google, NumPy, or Sphinx style. "
             "Used to generate the tool's description and input schema. "
             "For code-first tools, this is auto-filled from the method's __doc__.",
    )
    description = fields.Text(
        "Description", compute='_compute_metadata', store=True,
    )
    input_schema = fields.Text(
        "Input Schema", compute='_compute_metadata', store=True,
    )
    active = fields.Boolean("Active", default=True,
                             help="Inactive tools are hidden from MCP clients.")
    is_code_first = fields.Boolean(
        "Code First", default=False,
        help="Auto-generated from @mcp_tool decorator. "
             "Code-first tools are refreshed on module upgrade to stay in sync with the Python code.",
    )

    _sql_constraints = [
        ("model_method_unique", "unique(model_id, method_id)",
         "Each model can have at most one tool per method."),
    ]

    # ── Metadata computation ───────────────────────────────────────────

    @api.depends('model_id', 'method_id', 'docstring', 'is_code_first')
    def _compute_metadata(self):
        for rec in self:
            if not rec.model_id or not rec.method_id:
                rec.description = False
                rec.input_schema = False
                continue

            if rec.is_code_first:
                desc, schema = rec._build_metadata_from_method()
            else:
                desc, schema = rec._build_metadata_from_docstring()

            rec.description = desc
            rec.input_schema = json.dumps(schema) if schema else False

    def _build_metadata_from_method(self):
        """Build metadata from the actual Python method (code-first)."""
        from ..typeutil import OdooMro
        from ..mcputil import build_tool_info

        method_name = self.method_id.name
        model_cls = self.env.registry.get(self.model_id.model)
        if not model_cls:
            return False, False

        method = getattr(model_cls, method_name, None)
        if not method or not callable(method):
            return False, False

        custom_desc = getattr(method, '_mcp_custom_description', None)
        inherit_docs = getattr(method, '_mcp_inherit_docs', True)
        mro = OdooMro(method_name, model_cls.__bases__)
        tool_info = build_tool_info(mro, custom_desc=custom_desc, inherit_docs=inherit_docs)
        return tool_info.get('description', ''), tool_info.get('inputSchema')

    def _build_metadata_from_docstring(self):
        """Build metadata from the user-provided docstring (config-first)."""
        from ..docstring import parse_docstring

        doc = (self.docstring or '').strip()
        if not doc:
            return "Odoo Tool", {
                "type": "object",
                "properties": {},
                "required": [],
            }

        meta = parse_docstring(doc)
        properties = {}
        required = []

        for param_name, param_desc in meta.get('params', {}).items():
            json_type = meta.get('param_types', {}).get(param_name, 'string')
            prop = json_type if isinstance(json_type, dict) else {"type": json_type}
            if param_desc:
                prop["description"] = param_desc
            properties[param_name] = prop
            required.append(param_name)

        return meta.get('description', 'Odoo Tool'), {
            "type": "object",
            "properties": properties,
            "required": required,
        }
