# -*- coding: utf-8 -*-
# @Time         : 17:50 2025/10/15
# @Author       : Chris
# @Description  :
from abc import ABC, abstractmethod
from typing import Optional

from odoo import models, _
from odoo.exceptions import AccessError

from .base import IAcl, AclUnit, UnitKind
from .clause import SelectClause, SetClause, ValuesClause, WhereClause, OrderbyClause
from .compatible import zip_c
from .field import FieldAccess
from .meta import OqlMeta
from .recs import *

_logger = logging.getLogger(__name__)


class Statement(IAcl, ABC):
    meta: OqlMeta  # Injected by transformer.

    """OQL Statement"""
    @abstractmethod
    def execute(self):
        pass


class SelectStmt(Statement):
    def __init__(self, from_: models.Model, select: SelectClause, where: Optional[WhereClause],
                 orderby: Optional[OrderbyClause], limit, offset):
        self.from_ = from_
        self.select = select
        self.where = where or WhereClause.all(from_)
        self.orderby = orderby or OrderbyClause.empty(from_)
        self.limit = limit
        self.offset = offset

    def execute(self):
        # 1 Search records.
        orderby = self.orderby.execute()
        recs = self.where.execute(self.from_, self.meta, self.offset, self.limit, orderby)

        # 2 Read fields.
        rows = self.select.execute(recs, self.meta)

        return rows

    def gather_acl_units(self, res: List[AclUnit]):
        res.append(AclUnit(self.from_, self.from_._name, UnitKind.MODEL, "read"))
        self.select.gather_acl_units(res)
        self.where.gather_acl_units(res)
        if self.orderby:
            self.orderby.gather_acl_units(res)


class UpdateStmt(Statement):
    def __init__(self, from_: models.Model, set_clause: SetClause,
                 where: Optional[WhereClause] = None, limit=None):
        self.from_ = from_
        self.set_clause = set_clause
        self.where = where or WhereClause.all(from_)
        self.limit = limit

    def execute(self):
        # 1 Search records to update.
        recs = self.where.execute(self.from_, self.meta, 0, self.limit, None, mode="write")

        # 2 Build vals and write.
        if recs:
            self.set_clause.execute(recs)

        # 3 Return updated record ids.
        return [{"id": rid} for rid in recs.ids]

    def gather_acl_units(self, res: List[AclUnit]):
        res.append(AclUnit(self.from_, self.from_._name, UnitKind.MODEL, "write"))
        self.set_clause.gather_acl_units(res)
        if self.where:
            self.where.gather_acl_units(res)


class CreateStmt(Statement):
    def __init__(self, from_: models.Model, translate: bool,
                 columns: List[FieldAccess], values: ValuesClause):
        self.from_ = from_
        self.translate = translate
        self.columns = columns
        self.values = values

    def execute(self):
        env = self.from_.env
        model_name = self.from_._name
        acl = self.meta.acl[model_name]

        # 1 Build a value dict for every row and create.
        vals = self.values.execute(self.columns)
        create_model = self.from_.with_context(lang=env.user.lang if self.translate else None)
        recs = create_model.sudo(False).create(vals)

        # 2 Check record level ACL
        domain = acl.perm_records([("id", "in", recs.ids)], "create")
        allowed_recs = self.from_.with_context(active_test=False).search(domain)
        if len(allowed_recs) != len(recs):
            id2val = dict(zip_c(recs.ids, vals, strict=True))
            bad_ids = set(recs.ids) - set(allowed_recs.ids)
            raise AccessError(_("Some created records are out of permitted domain, values: %s") % (
                [id2val[x] for x in bad_ids],
            ))

        # 3 Return created record ids.
        return [{"id": rid} for rid in recs.ids]

    def gather_acl_units(self, res: List[AclUnit]):
        res.append(AclUnit(self.from_, self.from_._name, UnitKind.MODEL, "create"))
        for fa in self.columns:
            fa.gather_acl_units(res, "write")
        self.values.gather_acl_units(res)


class DeleteStmt(Statement):
    def __init__(self, from_: models.Model, where: Optional[WhereClause] = None, limit=None):
        self.from_ = from_
        self.where = where or WhereClause.all(from_)
        self.limit = limit

    def execute(self):
        # 1 Search for records to delete.
        recs = self.where.execute(self.from_, self.meta, 0, self.limit, None, mode="unlink")

        # 2 Collect ids before deletion.
        ids = recs.ids

        # 3 Delete records.
        if recs:
            recs.unlink()

        # 4 Return deleted record ids.
        return [{"id": rid} for rid in ids]

    def gather_acl_units(self, res: List[AclUnit]):
        res.append(AclUnit(self.from_, self.from_._name, UnitKind.MODEL, "unlink"))
        self.where.gather_acl_units(res)
