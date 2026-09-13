# -*- coding: utf-8 -*-
# @Time         : 16:23 2026/6/23
# @Author       : Chris
# @Description  :
from abc import ABC
from typing import Any, Union, Optional

from odoo import _
from odoo import models

from .compatible import zip_c
from .expr import Expr
from .field import FieldAccess
from .meta import OqlMeta
from .recs import *
from .base import IRecsReader, IAcl, AclUnit, UnitKind, ModelMode


class Clause(IAcl, ABC):
    pass


class SelectClause(Clause):
    def __init__(self, translate: bool, fas: List[IRecsReader]):
        self.translate = translate
        self.fas = fas
        # Check agg.
        agg_readers = [x for x in fas if x.is_agg]
        if agg_readers and len(agg_readers) != len(fas):
            raise Exception(f"Mixture of aggregate and non-aggregate readers is invalid. Agg readers: {agg_readers}")

    def execute(self, recs: models.Model, meta: OqlMeta, load='_classic_read') -> List[Dict[str, Any]]:
        env = recs.env
        model_name = recs._name  # noqa
        fas = self.fas

        # Read fields.
        recs = recs.with_context(lang=env.user.lang if self.translate else None)
        rows = [{
            f.as_: val for f, val in zip_c(fas, val_row, strict=True)
        } for val_row in zip_c(*(f.read(recs, load) for f in fas), strict=True)]

        return rows

    def gather_acl_units(self, res: List[AclUnit]):
        for fa in self.fas:
            fa.gather_acl_units(res, "read")


class WhereClause(Clause):
    def __init__(self, translate: bool, expr: Expr, model: models.Model):
        self.translate = translate
        self.expr = expr
        self.model = model

    @classmethod
    def all(cls, model: models.Model):
        return WhereClause(False, Expr.empty(model), model)

    def execute(self, model: models.Model, meta: OqlMeta, offset: int, limit: int,
                orderby: Optional[str], count: bool = False, mode: ModelMode = "read") \
            -> Union[models.Model, int]:
        env = model.env
        rec_sets = self.expr.eval_rec_sets()
        domain = rec_sets[0].domain.domain
        domain = meta.acl[model._name].perm_records(domain, mode)  # Record level ACL, use odoo's built-in ACL here.
        where_model = model.with_context(lang=env.user.lang if self.translate else None)
        if count:
            # Odoo 17 and over do not support `count` parameter in `search`, so use `search_count` here.
            res = where_model.search_count(domain)
        else:
            res = where_model.search(domain, offset, limit, orderby)  # recs
        return res

    def gather_acl_units(self, res: List[AclUnit]):
        res.append(AclUnit(self.model, self.model._name, UnitKind.MODEL, "read"))
        self.expr.gather_acl_units(res)


class OrderbyClause(Clause):
    def __init__(self, model: models.Model, fields: List[Tuple[str, str]]):
        self.model = model
        self.fields = fields
        self.validate(model)

    @classmethod
    def empty(cls, model: models.Model):
        return OrderbyClause(model, [])

    def execute(self):
        return ','.join(f"{t[0]} {t[1]}" for t in self.fields)

    def validate(self, model: models.Model):
        _fields = model._fields  # noqa
        for name, __ in self.fields:
            f_meta: fields.Field = _fields.get(name)
            if not f_meta:
                raise Exception(_("Order-by field `%s` not found on model `%s`.") % (name, self.model_name))
            if not f_meta.store:
                raise Exception(_("Can't order by `%s`, it's not a stored field.") % (name,))

    def gather_acl_units(self, res: List[AclUnit]):
        for fname, __ in self.fields:
            res.append(AclUnit(self.model, fname, UnitKind.FIELD, "read"))


class SetClause(Clause):
    """Holds field=value assignments for UPDATE/CREATE statements."""

    def __init__(self, translate: bool, assignments: Iterable[Tuple[FieldAccess, Any]], env):
        self.translate = translate
        self.assignments = tuple(assignments)
        self.env = env

    def execute(self):
        vals = {}
        for fa, val in self.assignments:
            vals[fa.path] = self._r_execute(val)
        return vals

    def gather_acl_units(self, res: List[AclUnit]):
        for fa, value in self.assignments:
            fa.gather_acl_units(res, "write")
            self._r_gather_val_acl(fa.rear_field, value, res)

    @classmethod
    def _r_execute(cls, node):
        if isinstance(node, list):
            return [cls._r_execute(x) for x in node]
        elif isinstance(node, tuple):
            return tuple(cls._r_execute(x) for x in node)
        elif isinstance(node, dict):
            return {cls._r_execute(k): cls._r_execute(v) for k, v in node.items()}
        else:
            return node

    @classmethod
    def _r_gather_val_acl(cls, field: fields.Field, node, res: List[AclUnit]):
        if isinstance(node, tuple) and len(node) == 3:
            pass
        elif isinstance(node, list):
            for item in node:
                cls._r_gather_val_acl(field, item, res)
        elif isinstance(node, IRecsReader):
            node.gather_acl_units(res, "read")
