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

    def __init__(self, translate: bool):
        self.translate = translate

    def _update_context(self, model: models.Model) -> models.Model:
        context: dict = dict(model.env.context)
        if self.translate:
            if not context.get("lang"):
                context["lang"] = model.env.user.lang
        else:
            context["lang"] = None
        return model.with_context(**context)


class SelectClause(Clause):
    def __init__(self, translate: bool, fas: List[IRecsReader]):
        super().__init__(translate)
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
        recs = self._update_context(recs)
        rows = [{
            f.as_: val for f, val in zip_c(fas, val_row, strict=True)
        } for val_row in zip_c(*(f.read(recs, load) for f in fas), strict=True)]

        return rows

    def gather_acl_units(self, res: List[AclUnit]):
        for fa in self.fas:
            fa.gather_acl_units(res, "read")


class WhereClause(Clause):
    def __init__(self, translate: bool, expr: Expr, model: models.Model):
        super().__init__(translate)
        self.expr = expr
        self.model = model

    @classmethod
    def all(cls, model: models.Model):
        return WhereClause(False, Expr.empty(model), model)

    def execute(self, model: models.Model, meta: OqlMeta, offset: int, limit: int,
                orderby: Optional[str], count: bool = False, mode: ModelMode = "read") \
            -> Union[models.Model, int]:
        rec_sets = self.expr.eval_rec_sets()
        domain = rec_sets[0].domain.domain
        domain = meta.acl[model._name].perm_records(domain, mode)  # Record level ACL, use odoo's built-in ACL here.
        where_model = self._update_context(model)
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
        super().__init__(False)
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
    """Update values for recs."""

    def __init__(self, translate: bool, assignments: Iterable[Tuple[FieldAccess, Any]], env):
        super().__init__(translate)
        self.assignments = tuple(assignments)
        self.env = env

    def execute(self, recs):
        recs = recs.sudo(False)  # Downgrade.
        recs = self._update_context(recs)
        for rec in recs:
            vals = {}
            for fa, val in self.assignments:
                vals[fa.path] = self._r_execute(val, rec)
            rec.write(vals)

    def gather_acl_units(self, res: List[AclUnit]):
        for fa, value in self.assignments:
            fa.gather_acl_units(res, "write")
            self._r_gather_val_acl(fa.rear_field, value, res)

    @classmethod
    def _r_execute(cls, node, rec):
        if isinstance(node, list):
            return [cls._r_execute(x, rec) for x in node]
        elif isinstance(node, tuple):
            return tuple(cls._r_execute(x, rec) for x in node)
        elif isinstance(node, dict):
            return {cls._r_execute(k, rec): cls._r_execute(v, rec) for k, v in node.items()}
        elif isinstance(node, IRecsReader):
            return node.read(rec)[0]
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


class ValuesClause(Clause):
    """Holds the `VALUES` rows of an INSERT statement."""

    def __init__(self, rows: List[List[Any]], model: models.Model):
        super().__init__(False)
        self.rows = rows
        self.model = model

    def execute(self, fas: List[FieldAccess]) -> List[Dict[str, Any]]:
        """Map every value row onto `fas`, e.g. `{'spu_name': 'Boot'}`.

        Each row must hold as many values as `fas`, else `zip_c` raises.
        """
        return [{fa.path: self._r_execute(val, self.model)
                 for fa, val in zip_c(fas, row, strict=True)}
                for row in self.rows]

    def gather_acl_units(self, res: List[AclUnit]):
        self._r_gather_val_acl(self.rows,res)

    @classmethod
    def _r_execute(cls, node, model):
        if isinstance(node, list):
            return [cls._r_execute(x, model) for x in node]
        elif isinstance(node, tuple):
            return tuple(cls._r_execute(x, model) for x in node)
        elif isinstance(node, dict):
            return {cls._r_execute(k, model): cls._r_execute(v, model) for k, v in node.items()}
        else:
            return node

    @classmethod
    def _r_gather_val_acl(cls, node, res: List[AclUnit]):
        if isinstance(node, tuple) and len(node) == 3:
            pass
        elif isinstance(node, list):
            for item in node:
                cls._r_gather_val_acl(item, res)
        elif isinstance(node, IRecsReader):
            node.gather_acl_units(res, "read")
