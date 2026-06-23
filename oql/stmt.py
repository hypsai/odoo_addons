# -*- coding: utf-8 -*-
# @Time         : 17:50 2025/10/15
# @Author       : Chris
# @Description  :
from abc import ABC, abstractmethod
from typing import Optional

from odoo import models

from .clause import SelectClause, SetClause, WhereClause
from .compatible import zip_c
from .field import FieldAccess
from .meta import OqlMeta
from .recs import *

_logger = logging.getLogger(__name__)


class Statement(ABC):
    meta: OqlMeta  # Injected by transformer.

    """OQL Statement"""
    @abstractmethod
    def execute(self):
        pass


class SelectStmt(Statement):
    def __init__(self, from_: models.Model, select: SelectClause, where: Optional[WhereClause], orderby, limit, offset):
        self.from_ = from_
        self.select = select
        self.where = where
        self.orderby = orderby
        self.limit = limit
        self.offset = offset

    def execute(self):
        env = self.from_.env
        model_name = self.from_._name
        # 1 Ensure `id` is in result.
        if not any(f.path == "id" for f in self.select.fas):
            self.select.fas = [FieldAccess(self.from_, ["id"], self.meta)] + self.select.fas

        # 2 Search records.
        if self.where:
            domain = self.where.rec_set.domain.domain
            domain = self.meta.acl[model_name].perm_records(domain, "read")  # Record level ACL
            where_model = self.from_.with_context(lang=env.user.lang if self.where.translate else None)
        else:
            domain = []
            where_model = self.from_
        select_recs = where_model.search(domain, self.offset, self.limit, self.orderby)

        # 3 Read fields.
        select_recs = select_recs.with_context(lang=env.user.lang if self.select.translate else None)
        rows = [{
            f.as_: val for f, val in zip_c(self.select.fas, val_row, strict=True)
        } for val_row in zip_c(*(f.read(select_recs) for f in self.select.fas), strict=True)]

        return rows


class UpdateStmt(Statement):
    def __init__(self, from_: models.Model, translate, set_clause: SetClause,
                 where: Optional[WhereClause] = None, limit=None):
        self.from_ = from_
        self.translate = bool(translate)
        self.set_clause = set_clause
        self.where = where
        self.limit = limit

    def execute(self):
        env = self.from_.env
        model_name = self.from_._name
        acl = self.meta.acl[model_name]

        # 1 Check model-level write access.
        acl.check("write", True)

        # 2 Search records to update.
        if self.where:
            domain = self.where.rec_set.domain.domain
            domain = acl.perm_records(domain, "write")  # Record level ACL
            where_model = self.from_.with_context(lang=env.user.lang if self.where.translate else None)
        else:
            domain = []
            where_model = self.from_
        recs = where_model.search(domain, limit=self.limit)

        # 3 Build vals and write.
        if recs:
            vals = self.set_clause.to_vals(self.from_, self.meta)
            write_recs = recs.with_context(lang=env.user.lang if self.translate else None)
            write_recs.write(vals)

        # 4 Return updated record ids.
        return [{"id": rid} for rid in recs.ids]


class CreateStmt(Statement):
    def __init__(self, from_: models.Model, translate, set_clause: SetClause):
        self.from_ = from_
        self.translate = bool(translate)
        self.set_clause = set_clause

    def execute(self):
        env = self.from_.env
        model_name = self.from_._name
        acl = self.meta.acl[model_name]

        # 1 Check model-level create access.
        acl.check("create", True)

        # 2 Build vals and create.
        vals = self.set_clause.to_vals(self.from_, self.meta)
        create_model = self.from_.with_context(lang=env.user.lang if self.translate else None)
        rec = create_model.create(vals)

        # 3 Return created record ids.
        return [{"id": rid} for rid in rec.ids]


class DeleteStmt(Statement):
    def __init__(self, from_: models.Model, where: Optional[WhereClause] = None, limit=None):
        self.from_ = from_
        self.where = where
        self.limit = limit

    def execute(self):
        env = self.from_.env
        model_name = self.from_._name
        acl = self.meta.acl[model_name]

        # 1 Check model-level unlink access.
        acl.check("unlink", True)

        # 2 Search records to delete.
        if self.where:
            domain = self.where.rec_set.domain.domain
            domain = acl.perm_records(domain, "write")  # Record level ACL
            where_model = self.from_.with_context(lang=env.user.lang if self.where.translate else None)
        else:
            domain = []
            where_model = self.from_
        recs = where_model.search(domain, limit=self.limit)

        # 3 Collect ids before deletion.
        ids = recs.ids

        # 4 Delete records.
        if recs:
            recs.unlink()

        # 5 Return deleted record ids.
        return [{"id": rid} for rid in ids]
