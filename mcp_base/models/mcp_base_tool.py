# @Time         : 15:37 2026/5/28
# @Author       : Chris
# @Description  : MCP Tool ORM Model - stores MCP tool definitions for config-first and code-first.
import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


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

    # ── Code-first auto-sync ────────────────────────────────────────────

    @api.model
    def _register_hook(self):
        """At every server startup, scan all @mcp_tool decorated methods
        and sync them into mcp.base.tool records."""
        super()._register_hook()
        try:
            self._sync_tools_from_registry()
        except Exception:
            _logger.warning("mcp.base.tool: sync failed at startup", exc_info=True)

    @api.model
    def _sync_tools_from_registry(self):
        """Scan the registry for ``@mcp_tool`` decorated methods and
        create / update the corresponding ``mcp.base.tool`` records.

        - New methods → create with ``is_code_first=True``
        - Existing code-first tools → update ``docstring`` only
        - Config-first tools (``is_code_first=False``) → left untouched

        All DB operations are batched for performance.
        """
        # ── Phase 1: collect all @mcp_tool candidates purely in Python ──
        # (model_name, method_name, docstring)
        # Respect @api.model vs recordset: api.model methods only create tools
        # on the *defining* model; recordset methods create on every model in the MRO.
        from ..compatible import is_api_model
        from ..models.mcp_base_method import _method_defined_on

        candidates: list[tuple[str, str, str]] = []  # (model_name, method_name, docstring)
        for model_name, model_cls in self.env.registry.models.items():
            for attr_name in dir(model_cls):
                if attr_name.startswith('_'):
                    continue
                method = getattr(model_cls, attr_name, None)
                if not callable(method) or not getattr(method, '_is_mcp_tool', False):
                    continue

                if is_api_model(method):
                    # @api.model — only create tool on the defining model
                    if _method_defined_on(attr_name, model_cls):
                        candidates.append((model_name, attr_name, method.__doc__ or ''))
                else:
                    # recordset method — create tool on every model
                    candidates.append((model_name, attr_name, method.__doc__ or ''))

        if not candidates:
            return

        # ── Phase 2: batch-load ir.model id mapping ──
        model_names = {c[0] for c in candidates}
        ir_models = self.env['ir.model'].search([('model', 'in', list(model_names))])
        if not ir_models:
            return
        model_name_to_ir_id = {r.model: r.id for r in ir_models}
        valid_model_ids = list(model_name_to_ir_id.values())

        # ── Phase 3: batch-load existing method & tool records ──
        existing_methods = self.env['mcp.base.method'].search([
            ('model_id', 'in', valid_model_ids),
        ])
        method_map = {(r.model_id.id, r.name): r.id for r in existing_methods}  # (ir_id, name) → id

        existing_tools = self.search([('model_id', 'in', valid_model_ids)])
        tool_map = {(r.model_id.id, r.method_id.id): r for r in existing_tools}  # (ir_id, method_id) → rec

        # ── Phase 4: partition candidates ──
        method_ids_to_create: list[dict] = []
        tools_to_create: list[dict] = []
        tools_to_update: list[tuple[int, str]] = []  # (tool_id, new_docstring)
        deferred: list[tuple[str, str, str]] = []  # (model_name, method_name, docstring) waiting for method creation

        for model_name, method_name, docstring in candidates:
            ir_id = model_name_to_ir_id.get(model_name)
            if not ir_id:
                continue

            m_key = (ir_id, method_name)
            method_id = method_map.get(m_key)

            if not method_id:
                method_ids_to_create.append({'name': method_name, 'model_id': ir_id})
                deferred.append((model_name, method_name, docstring))
            else:
                t_key = (ir_id, method_id)
                tool = tool_map.get(t_key)
                if tool:
                    if tool.is_code_first and tool.docstring != docstring:
                        tools_to_update.append((tool.id, docstring))
                else:
                    tools_to_create.append({
                        'name': f"{model_name}:{method_name}",
                        'model_id': ir_id,
                        'method_id': method_id,
                        'docstring': docstring,
                        'is_code_first': True,
                    })

        # ── Phase 5: batch-create missing methods, then handle deferred tools ──
        if method_ids_to_create:
            new_methods = self.env['mcp.base.method'].create(method_ids_to_create)
            for rec in new_methods:
                method_map[(rec.model_id.id, rec.name)] = rec.id

            for model_name, method_name, docstring in deferred:
                ir_id = model_name_to_ir_id[model_name]
                method_id = method_map[(ir_id, method_name)]
                tools_to_create.append({
                    'name': f"{model_name}:{method_name}",
                    'model_id': ir_id,
                    'method_id': method_id,
                    'docstring': docstring,
                    'is_code_first': True,
                })

        # ── Phase 6: batch-create tools ──
        if tools_to_create:
            self.create(tools_to_create)

        # ── Phase 7: batch-update docstrings (grouped by value to minimise UPDATEs) ──
        if tools_to_update:
            by_docstring: dict[str, list[int]] = {}
            for tid, ds in tools_to_update:
                by_docstring.setdefault(ds, []).append(tid)
            for ds, ids in by_docstring.items():
                self.browse(ids).write({'docstring': ds})

        count_create = len(tools_to_create)
        count_update = len(tools_to_update)
        if count_create or count_update:
            _logger.info(
                "mcp.base.tool: synced %d new + %d updated code-first tools from registry",
                count_create, count_update,
            )
