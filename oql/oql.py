# -*- coding: utf-8 -*-
# @Time         : 17:50 2025/10/15
# @Author       : Chris
# @Description  :
import os.path
from typing import Optional

import odoo.fields
from odoo import models, _

from .clause import SelectClause, SetClause, WhereClause
from .field import FieldAccess
from .libs import lark
from .libs.lark.exceptions import VisitError
from .meta import OqlMeta
from .recs import *
from .stmt import Statement, SelectStmt, UpdateStmt, CreateStmt, DeleteStmt
from .util import tn

_logger = logging.getLogger(__name__)


@lark.v_args(inline=True)
class OqlTransformer(lark.Transformer):

    CNAME = str
    INT = int
    FLOAT = float

    select_stmt = SelectStmt

    def __init__(self, env: odoo.api.Environment):
        super().__init__(True)
        env = env(
            context={**env.context, "lang": None}  # Default no translation.
        )
        self.env = env
        self.model_name = None
        self.recs = None
        self._meta = OqlMeta(env)

    def query(self, stmt: Statement):
        stmt.meta = self._meta
        return stmt.execute()

    def _init_model(self, model_name: str):
        """Initialize model for non-SELECT statements."""
        acl = self._meta.acl
        acl[model_name].check("read", True)
        self.model_name = model_name
        self.recs = self.env[model_name].sudo()

    def from_clause(self, model: str):
        self._init_model(model)
        return self.recs

    def update_stmt(self, model_name: str, _set, translate, set_clause: SetClause,
                    where: Optional[WhereClause] = None, limit=None):
        return UpdateStmt(self.recs, translate, set_clause, where, limit)

    def insert_stmt(self, model_name: str, _set, translate, set_clause: SetClause):
        return CreateStmt(self.recs, translate, set_clause)

    def delete_stmt(self, model_name: str, where: Optional[WhereClause] = None, limit=None):
        return DeleteStmt(self.recs, where, limit)

    def select_clause(self, translate: Optional[str], fields="*"):
        if fields == "*":
            fields = self._meta.acl[self.model_name].perm_fields("read")
            fields = [FieldAccess(self.recs, [x], self._meta) for x in fields]
        return SelectClause(bool(translate), fields)

    def set_clause(self, *assignments):
        return SetClause(list(assignments))

    def assignment(self, name: str, value):
        return (name, value)

    def where_clause(self, translate: Optional[str], rec_sets: RecordSets):
        return WhereClause(bool(translate), rec_sets)

    def orderby_clause(self, __, fields):
        # Check.
        _fields = self.recs._fields
        for name, __ in fields:
            f_meta: odoo.fields.Field = _fields.get(name)
            if not f_meta:
                raise Exception(_("Order-by field `%s` not found on model `%s`.") % (name, self.model_name))
            if not f_meta.store:
                raise Exception(_("Can't order by `%s`, it's not a stored field.") % (name, ))
        return ','.join(f"{t[0]} {t[1]}" for t in fields)

    def offset_clause(self, num: int):
        return num

    def limit_clause(self, num: int):
        return num

    def or_expr(self, left, right):
        if isinstance(left, RecordSets) or isinstance(right, RecordSets):
            return left | right
        return left or right

    def and_expr(self, left, right):
        if isinstance(left, RecordSets) or isinstance(right, RecordSets):
            return left & right
        return left and right

    def bin_expr(self, left: FieldAccess, opr: str, right):
        opr = " ".join(opr.lower().split())  # Normalize spaces
        return left.eval_bin(opr, right)

    def dot_expr(self, field: FieldAccess):
        return field.eval_una("bool")

    def fields(self, *fields):
        return list(fields)

    def orderby_fields(self, *fields):
        return list(fields)

    def model(self, names: Tuple[str]):
        model_name = '.'.join(names)
        self._init_model(model_name)
        return model_name

    def field(self, names: Tuple[str]):
        return FieldAccess(self.recs, names, self._meta)

    def field_as(self, field: Tuple[str], as_: Optional[Tuple[str]]):
        return FieldAccess(self.recs, field, self._meta, as_='.'.join(as_) if as_ else None)

    def orderby_field(self, name: str, dir_: str):
        return name, dir_ or "asc"

    def dot_names(self, *args):
        return args

    def string(self, value):
        return value

    def ESCAPED_STRING(self, value: str):
        return value[1:-1].replace("''", "'")

    def TRUE(self, value):
        return True

    def FALSE(self, value):
        return False

    def NULL(self, value):
        return None

    def array(self, *values):
        return values

    @classmethod
    def _type_check_bin(cls, left, opr, right, left_expr: str, right_expr: str):
        hint_expr = f"Expr: {left_expr} ({opr}) {right_expr}"
        if opr == ".":
            if not isinstance(left, models.AbstractModel):
                raise TypeError(f"Expect `{tn(models.AbstractModel)}` instance at left, got `{tn(left)}`. {hint_expr}")
            if isinstance(right, models.AbstractModel):
                if left._name != right._name:
                    raise TypeError(f"Left type `{tn(left)}` and right `{tn(right)}` are inconsistent. {hint_expr}")

    def __default_token__(self, token):
        return str(token)


class OqlReader:
    def __init__(self):
        fp = os.path.join(os.path.dirname(__file__), "oql.lark")
        self.lark = lark.Lark.open(fp, parser="lalr")
        self.parser = self.lark.parser

    def query(self, s: str, transformer: lark.Transformer):
        tree = self.parser.parse(s)
        try:
            result = transformer.transform(tree)
        except VisitError as ve:
            # Re-raise the original exception with its original traceback
            raise ve.orig_exc.with_traceback(ve.orig_exc.__traceback__)
        return result


reader = OqlReader()  # Global reader.
