# -*- coding: utf-8 -*-
# @Time         : 17:50 2025/10/15
# @Author       : Chris
# @Description  :
from abc import ABC, abstractmethod
from typing import Optional

from odoo import models

from .clause import SelectClause, WhereClause
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
