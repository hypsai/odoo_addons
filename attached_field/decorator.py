# -*- coding: utf-8 -*-
# @Time         : 15:38 2026/3/8
# @Author       : Chris
# @Description  : @attached decorator – dynamically attach arbitrary fields to
#                 the target model of a view action, with compute/inverse
#                 delegated to the invoker model.
import functools
import logging

from odoo import models

from .compatible import refresh_models

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pending-field registry.
#
# Key:   (target_model, invoker_model, action_method)
# Value: dict with keys "invoker_table", "action_method", "fields_meta"
#
# Populated at decoration time, consumed by base.py/_setup_base.
# ---------------------------------------------------------------------------
_PENDING_ATTACHED = {}  # type: ignore


def attached(**field_mapping):
    """Decorator for action methods that dynamically attaches fields to the
    target model of the returned view action.

    Field names on the target model are generated as:
        ``<invoker_table>_<action_method>_<user_field_name>``

    Usage::

        class MyModel(models.Model):
            _name = 'my.model'

            @attached(
                note=fields.Char(compute='_compute_note'),
                score=fields.Integer(compute='_compute_score', inverse='_inverse_score', view={'widget': 'progress'}),
            )
            def action_open_view(self):
                return self.env['other.model'].search([])

    ``_compute_note`` and ``_compute_score`` must be methods on ``MyModel``
    (the invoker); they receive the *target* recordset as their only argument.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # 1.  Execute the original action method.
            result = func(self, *args, **kwargs)
            env = self.env

            # 2.  Determine target model & ensure it is a view-action result.
            res_model = None
            if isinstance(result, models.Model):
                res_model = result._name
            elif isinstance(result, dict):
                res_model = result.get('res_model')
            if not res_model:
                # Not a view action – return unchanged.
                return result

            invoker_model = self._name
            invoker_table = self._table
            invoker_ids = self.ids
            action_method = func.__name__

            # 3.  Build field-meta for the target model.
            fields_meta = {}
            for user_fname, user_fdef in field_mapping.items():
                field_def, view_config = user_fdef, user_fdef.args.get("view", {})
                actual_fname = f"{invoker_table}_{action_method}_{user_fname}"
                fields_meta[user_fname] = {
                    "actual_fname": actual_fname,
                    "field_def": field_def,
                    "view_config": view_config,
                }

            # 4.  Register pending fields + trigger refresh_models (DB migration).
            registry_key = (res_model, invoker_model, action_method)
            if registry_key not in _PENDING_ATTACHED:
                _PENDING_ATTACHED[registry_key] = {
                    "invoker_table": invoker_table,
                    "action_method": action_method,
                    "fields_meta": fields_meta,
                }
                refresh_models(env, [res_model])

            # 5.  Inject ``_attached_fields`` into the action's client context
            #     so that ``fields_view_get`` can render the dynamic fields.
            client_meta = {}
            for user_fname, info in fields_meta.items():
                client_meta[user_fname] = {
                    "actual_fname": info["actual_fname"],
                    "view_config": info["view_config"],
                }

            attached_ctx = {
                "invoker_model": invoker_model,
                "invoker_ids": invoker_ids,
                "action_method": action_method,
                "fields_meta": client_meta,
            }

            if isinstance(result, models.Model):
                return {
                    'name': 'Attached Field',
                    'type': 'ir.actions.act_window',
                    'res_model': res_model,
                    'view_mode': 'tree,form',
                    'target': 'current',
                    'domain': [('id', 'in', result.ids)],
                    'context': {**env.context, '_attached_fields': attached_ctx},
                }

            # result is a dict – inject context.
            result = dict(result)
            result['context'] = {**result.get('context', {}), '_attached_fields': attached_ctx}
            return result

        wrapper._attached_fields_meta = field_mapping
        return wrapper

    return decorator
