# -*- coding: utf-8 -*-
# @Time         : 16:23 2026/6/23
# @Author       : Chris
# @Description  :
from typing import Any, List, Tuple

from odoo import _
from odoo import fields, models

from .field import FieldAccess
from .meta import OqlMeta
from .recs import *


class SelectClause:
    def __init__(self, translate: bool, fas: List[FieldAccess]):
        self.translate = translate
        self.fas = fas


class WhereClause:
    def __init__(self, translate: bool, rec_sets: RecordSets):
        self.translate = translate
        self.rec_set = rec_sets[0]


class SetClause:
    """Holds field=value assignments for UPDATE/CREATE statements."""

    def __init__(self, assignments: List[Tuple[str, Any]]):
        self.assignments = assignments

    def to_vals(self, model: models.Model, meta: OqlMeta) -> dict:
        """Convert assignments to an Odoo vals dict, checking field-level write ACL."""
        vals = {}
        acl = meta.acl
        model_name = model._name
        _fields = model._fields
        for field_name, value in self.assignments:
            f_meta: fields.Field = _fields.get(field_name)
            if not f_meta:
                raise Exception(_("Field `%s` not found on model `%s`.") % (field_name, model_name))
            # Check field-level write access.
            acl.check_field(model, field_name, "write")
            # Convert value based on field type.
            if f_meta.type in ('one2many', 'many2many'):
                if value is None:
                    vals[field_name] = [(5,)]  # Clear all.
                elif isinstance(value, (list, tuple)):
                    vals[field_name] = [(6, 0, list(value))]
                else:
                    raise Exception(_("Expected array of ids for x2many field `%s`, got `%s`.")
                                    % (field_name, type(value).__name__))
            else:
                vals[field_name] = value
        return vals
