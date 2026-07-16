# -*- coding: utf-8 -*-
# @Time         : 15:38 2026/3/8
# @Author       : Chris
# @Description  : @attached decorator – dynamically attach arbitrary fields to
#                 the target model of a view action, with compute/inverse
#                 delegated to the invoker model.
import functools
import logging

from odoo import fields

from .compatible import refresh_models

_logger = logging.getLogger(__name__)


def attached(**field_mapping: fields.Field):
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
                return {
                    'name': "Members",
                    'type': 'ir.actions.act_window',
                    'res_model': 'res.partner',
                    'view_mode': 'tree,form',
                    'target': 'current',
                    'context': self.env.context,
                }

    ``_compute_note`` and ``_compute_score`` must be methods on ``MyModel``
    (the invoker); they receive the *target* recordset as their only argument.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # 1.  Execute the original action method.
            res = func(self, *args, **kwargs)
            env = self.env

            # 2.  Determine target model & ensure it is a view-action res.
            if isinstance(res, dict):
                res_model = res.get('res_model')
            else:
                # Not a view action – return unchanged.
                return res

            invoker_model = self._name
            invoker_table = self._table
            invoker_ids = self.ids
            action_method = func.__name__

            # 3.  Build field-meta for the target model.
            fields_meta = {}
            for user_fname, user_fdef in field_mapping.items():
                user_fdef.args["name_user"] = user_fname
                fields_meta[f"attached_{invoker_table}_{action_method}_{user_fname}"] = user_fdef
            attached_ctx = {
                "invoker_table": invoker_table,
                "invoker_model": invoker_model,
                "invoker_ids": invoker_ids,
                "action_method": action_method,
                "fields_meta": fields_meta,
            }
            ctx = {**env.context, '_attached_fields': attached_ctx}

            # 4.  Register pending fields + trigger refresh_models (DB migration).
            refresh_models(env(context=ctx), [res_model])

            # 5.  Inject ``_attached_fields`` into the action's client context
            #     so that ``fields_view_get`` can render the dynamic fields.
            res = dict(res)
            res['context'] = {**res.get('context', {}), '_attached_fields': attached_ctx}

            return res

        return wrapper

    return decorator
