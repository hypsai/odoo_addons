# -*- coding: utf-8 -*-
# @Time         : 15:38 2026/3/8
# @Author       : Chris
# @Description  :
from odoo.api import _
from odoo import models


def picker(compute_picked: str, inverse_picked: str, title: str = _("Picker")):
    def decorator(func):
        def wrapper(*args, **kwargs):
            invoker_recs = args[0]
            env = invoker_recs.env
            # 1 Call function and format result as action.
            res = func(*args, **kwargs)
            if isinstance(res, models.Model):
                picker_meta = {
                    "invoker_model": invoker_recs._name,
                    "invoker_ids": invoker_recs.ids,
                    "compute_picked": compute_picked,
                    "inverse_picked": inverse_picked,
                }
                action = {
                    'name': title,
                    'type': 'ir.actions.act_window',
                    'res_model': res._name,
                    'view_mode': 'tree,form',  # Use 'tree,form' for Odoo 17 and below
                    'target': 'current',  # Opens in the main window
                    "domain": [("id", "in", res.ids)],
                    'context': {**env.context, **res.env.context, "_record_picker": picker_meta},
                }
                return action
            elif isinstance(res, dict):  # Result is an action, just return it untouched.
                return res
            else:
                raise NotImplementedError(f"Unsupported result type `{type(res)}`")
        return wrapper
    return decorator
