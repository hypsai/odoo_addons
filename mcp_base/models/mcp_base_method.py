# -*- coding: utf-8 -*-
"""Transient helper model that provides dynamic Many2one options for tool methods.

``name_search`` is overridden to resolve methods directly from the Odoo
registry at query time, eliminating context hacks and ensuring the dropdown
always reflects the currently selected ``ir.model``.
"""
from odoo import api, fields, models


class McpBaseMethod(models.Model):
    _name = "mcp.base.method"
    _description = "MCP Method Reference"
    _log_access = False  # no create_date / write_date overhead

    name = fields.Char("Method Name", required=True)
    model_id = fields.Many2one(
        "ir.model", "Model", required=True, index=True, ondelete="cascade",
    )

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Registry-first lazy search — the ``model_id`` is always provided
        by the ``domain`` on the ``mcp.base.tool.method_id`` Many2one field.

        Only methods that *currently* exist in the Python registry appear in
        the dropdown; stale DB records from a previous server session are
        ignored.
        """
        # 1. extract model_id from domain args
        model_id = None
        for item in (args or []):
            if isinstance(item, (list, tuple)) and len(item) >= 3 and item[0] == 'model_id':
                model_id = int(item[2])
                break
        if not model_id:
            return super().name_search(name, args, operator, limit=limit)

        # 2. resolve model class from registry
        ir_model = self.env['ir.model'].sudo().browse(model_id)
        model_name = ir_model.model if ir_model.exists() else False
        if not model_name or model_name not in self.env.registry:
            return []

        model_cls = self.env.registry[model_name]
        pattern = (name or '').lower()

        # 3. collect candidates from registry (source of truth)
        candidates = [
            attr for attr in sorted(dir(model_cls))
            if not attr.startswith('_')
            and callable(getattr(model_cls, attr, None))
            and (not pattern or pattern in attr.lower())
        ][:limit]

        if not candidates:
            return []

        # 4. sync to DB — look up existing records, create missing ones
        existing = {
            rec.name: rec.id
            for rec in self.search([('model_id', '=', model_id), ('name', 'in', candidates)])
        }
        to_create = [
            {'name': n, 'model_id': model_id}
            for n in candidates if n not in existing
        ]
        if to_create:
            for rec in self.create(to_create):
                existing[rec.name] = rec.id

        return [(existing[n], n) for n in candidates]
