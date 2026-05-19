# -*- coding: utf-8 -*-
# @Time         : 19:16 2026/4/27
# @Author       : Chris
# @Description  :
from odoo.release import version_info

ODOO_VERSION = version_info[0]


def model_flush(model, fields=None):
    if ODOO_VERSION >= 16:
        model._flush(fields)
    else:
        model.flush(fields)
