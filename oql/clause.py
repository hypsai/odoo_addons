# @Time         : 16:23 2026/6/23
# @Author       : Chris
# @Description  :
from typing import Any, Union

from odoo import _
from odoo import models

from .compatible import zip_c
from .field import FieldAccess
from .meta import OqlMeta
from .recs import *


class SelectClause:
    def __init__(self, translate: bool, fas: List[FieldAccess]):
        self.translate = translate
        self.fas = fas

    def execute(self, recs: models.Model, meta: OqlMeta) -> List[Dict[str, Any]]:
        env = recs.env
        model_name = recs._name  # noqa
        fas = self.fas
        # 1 Ensure `id` is in result.
        if not any(f.path == "id" for f in fas):
            fas = [FieldAccess(recs, ["id"], meta)] + fas

        # 2 Read fields.
        recs = recs.sudo()
        recs = recs.with_context(lang=env.user.lang if self.translate else None)
        rows = [{
            f.as_: val for f, val in zip_c(fas, val_row, strict=True)
        } for val_row in zip_c(*(f.read(recs) for f in fas), strict=True)]

        return rows


class WhereClause:
    def __init__(self, translate: bool, rec_sets: RecordSets):
        self.translate = translate
        self.rec_set = rec_sets[0]

    def execute(self, model: models.Model, meta: OqlMeta, offset: int, limit: int, orderby: str, count: bool = False) \
            -> Union[models.Model, int]:
        env = model.env
        domain = self.rec_set.domain.domain
        # domain = meta.acl[model._name].perm_records(domain, "read")  # Record level ACL, use odoo's built-in ACL here.
        where_model = model.with_context(lang=env.user.lang if self.translate else None)
        if count:
            # Odoo 17 and over do not support `count` parameter in `search`, so use `search_count` here.
            res = where_model.search_count(domain)
        else:
            res = where_model.search(domain, offset, limit, orderby)  # recs
        return res


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
