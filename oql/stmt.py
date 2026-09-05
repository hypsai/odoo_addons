# -*- coding: utf-8 -*-
# @Time         : 17:50 2025/10/15
# @Author       : Chris
# @Description  :
from abc import ABC, abstractmethod
from typing import Optional

from odoo import models

from .clause import SelectClause, SetClause, WhereClause
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
        # 1 Search records.
        if self.where:
            filtered_recs = self.where.execute(self.from_, self.meta, self.offset, self.limit, self.orderby)
        else:
            filtered_recs = self.from_.search([], self.offset, self.limit, self.orderby)

        # 2 Read fields.
        rows = self.select.execute(filtered_recs, self.meta)

        return rows


class UpdateStmt(Statement):
    def __init__(self, from_: models.Model, set_clause: SetClause,
                 where: Optional[WhereClause] = None, limit=None):
        self.from_ = from_
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
            self.set_clause.execute(recs)

        # 4 Return updated record ids.
        return [{"id": rid} for rid in recs.ids]


class CreateStmt(Statement):
    def __init__(self, from_: models.Model, set_clause: SetClause):
        self.from_ = from_
        self.set_clause = set_clause

    def execute(self):
        env = self.from_.env
        model_name = self.from_._name
        acl = self.meta.acl[model_name]

        # 1 Check model-level create access.
        acl.check("create", True)

        # 2 Build vals and create.
        vals = self.set_clause.to_vals(self.from_, self.meta)
        create_model = self.from_.with_context(lang=env.user.lang if self.set_clause.translate else None)
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
            domain = acl.perm_records(domain, "unlink")  # Record level ACL
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
