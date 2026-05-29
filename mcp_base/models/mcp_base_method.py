# -*- coding: utf-8 -*-
"""Transient helper model that provides dynamic Many2one options for tool methods.

``name_search`` is overridden to resolve methods directly from the Odoo
registry at query time, eliminating context hacks and ensuring the dropdown
always reflects the currently selected ``ir.model``.

- ``@api.model`` methods only appear on the model that *defines* them
  (they behave identically on all inheriting models).
- Recordset methods appear on every model in the MRO chain (each model may
  have different business logic).
"""
from odoo import api, fields, models

from ..compatible import is_api_model


def _method_defined_on(method_name: str, model_cls: type) -> bool:
    """Return ``True`` if *model_cls* itself defines the method.

    Odoo can assemble a model from multiple Python classes (same-``_name``
    ``_inherit``).  These are stored in ``model_cls.__bases__``.  We only
    consider classes whose ``_name`` matches ``model_cls._name`` — this
    excludes delegation-inheritance parents (different ``_name``), so that an
    ``@api.model`` method defined on ``A`` is NOT attributed to ``B(A)``.
    """
    own_name = model_cls._name
    for cls in model_cls.__bases__:
        if getattr(cls, '_name', None) == own_name and method_name in cls.__dict__:
            return True
    return False


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

        - ``@api.model`` methods are only returned for the *defining* model.
        - Recordset methods are returned for every model in the MRO chain.

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

        # 3. collect candidates from registry (source of truth),
        #    respecting @api.model vs recordset distinction
        candidates = []
        for attr in sorted(dir(model_cls)):
            if attr.startswith('_'):
                continue
            method = getattr(model_cls, attr, None)
            if not callable(method):
                continue
            if pattern and pattern not in attr.lower():
                continue

            if is_api_model(method):
                # @api.model – only visible when this model defines it
                if _method_defined_on(attr, model_cls):
                    candidates.append(attr)
            else:
                # recordset method – visible on every model in MRO
                candidates.append(attr)

            if len(candidates) >= limit:
                break

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
