# -*- coding: utf-8 -*-
# @Time         : 17:50 2025/10/15
# @Author       : Chris
# @Description  :
import copy
import os.path
from typing import Optional, Any, Set

import odoo.fields
from odoo import models, _, Command
from odoo.exceptions import AccessError

from .acl import ModelMode, FieldMode
from .base import UnitKind, AclUnit, IAcl, IRecsReader
from .chain import Chain, StepAttr, StepCall, StepIndex, Step
from .clause import SelectClause, SetClause, WhereClause, OrderbyClause
from .field import FieldAccess
from .func import UnboundFuncCall
from .expr import UnaExpr, BinExpr, AndExpr, OrExpr, Expr
from .libs import lark
from .libs.lark.exceptions import VisitError
from .meta import OqlMeta
from .recs import *
from .stmt import Statement, SelectStmt, UpdateStmt, CreateStmt, DeleteStmt
from .util import tn, groupby

_logger = logging.getLogger(__name__)


@lark.v_args(inline=True)
class OqlTransformer(lark.Transformer):
    """Note that transformer only generate statement or clause, it won't execute query."""

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

    @property
    def meta(self):
        return self._meta

    def query(self, ctx_clause: Optional[Any], stmt: Statement):
        stmt.meta = self._meta
        return stmt

    def init_model(self, model_name: str, mode: ModelMode = "read"):
        """Initialize model for non-SELECT statements."""
        self.model_name = model_name
        self.recs = self.env[model_name].sudo()  # SUDO-REMARK: ACL check will be performed at stage 2.

    def update_stmt(self, model: models.Model, set_clause: SetClause,
                    where: Optional[WhereClause] = None, limit=None):
        return UpdateStmt(model, set_clause, where, limit)

    def insert_stmt(self, model: models.Model, set_clause: SetClause):
        return CreateStmt(model, set_clause)

    def delete_stmt(self, model: models.Model, where: Optional[WhereClause] = None, limit=None):
        return DeleteStmt(model, where, limit)

    def ctx_clause(self, *assignments: Tuple[str, Any]):
        env = self.env
        context = dict(env.context)
        context.update(assignments)
        env = env(context=context)
        self.env = env

    def from_clause(self, model: str):
        self.init_model(model, "read")
        return self.recs

    def select_clause(self, translate: Optional[str], fields="*"):
        if fields == "*":
            fields = self._meta.acl[self.model_name].perm_fields("read")
            fields = [FieldAccess(self.recs, [x], self._meta) for x in fields]
        return SelectClause(bool(translate), fields)

    def update_clause(self, model: str):
        self.init_model(model, "write")
        return self.recs

    def insert_clause(self, model: str):
        self.init_model(model, "create")
        return self.recs

    def delete_clause(self, model: str):
        self.init_model(model, "unlink")
        return self.recs

    def set_clause(self, translate: Optional[str], *assignments):
        return SetClause(bool(translate), assignments, self.env)

    def where_clause(self, translate: Optional[str], expr: Expr):
        return WhereClause(bool(translate), expr, self.recs)

    def orderby_clause(self, __, fields):
        return OrderbyClause(self.recs, fields)

    def offset_clause(self, num: int):
        return num

    def limit_clause(self, num: int):
        return num

    def or_expr(self, left, right):
        return OrExpr(left, right)

    def and_expr(self, left, right):
        return AndExpr(left, right)

    def bin_expr(self, left: FieldAccess, opr: str, right):
        return BinExpr(left, opr, right)

    def dot_expr(self, field: FieldAccess):
        return UnaExpr("bool", field)

    def ubd_func(self, agg, name: str, *args):
        return UnboundFuncCall(name, args, agg)

    def attr_step(self, agg, name: str):
        return StepAttr(name, is_agg=bool(agg))

    def call_step(self, agg, name: str, *args):
        return StepCall(name, args, bool(agg) if agg is not None else None)

    def index_step(self, num: int):
        return StepIndex(num)

    def sel_chain(self, head: Step, *steps: Step):
        """Fold a select chain (left-associative): a pure dotted path becomes a
        `FieldAccess`, everything else (attrs / calls / subscripts) a `Chain`.
        The first step's input is the base `recs`; each step's `@` marks it
        aggregate — fold the whole input instead of for-in over every row.
        """
        path = (head, *steps)
        if all(isinstance(s, StepAttr) for s in path):
            # Optimize performance for pure field path access.
            names = [s.name for s in path]
            return FieldAccess(self.recs, names, self._meta,
                               is_agg=any(s.is_agg for s in path))
        return Chain(self.recs, self._meta, path)

    def assignment(self, fa: FieldAccess, opr, value):
        if opr != "=":
            raise Exception(f"Assignment operator must be `=`, got `{opr}`")
        return fa, value

    def assignment_simple(self, key: str, value):
        return key, value

    def fields(self, *fields):
        return list(fields)

    def orderby_fields(self, *fields):
        return list(fields)

    def model(self, names: Tuple[str]):
        return '.'.join(names)

    def field(self, agg, names: Tuple[str]):
        fa = FieldAccess(self.recs, names, self._meta, is_agg=agg)
        return fa

    def field_assi(self, names: Tuple[str]):
        """Field assignment."""
        fa = FieldAccess(self.recs, names, self._meta)
        return fa

    def field_as(self, field: IRecsReader, as_: Optional[Tuple[str]]):
        """Select item (`FieldAccess` / `Chain`), with optional alias."""
        if as_:
            field.as_ = '.'.join(as_)
        return field

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

    def set(self, *values):
        return values

    def array(self, *items):
        return list(items)

    def array_int(self, *values):
        return list(values)

    def object(self, *members):
        return dict(members)

    def member(self, key: str, value):
        return key, value

    def cmd(self, cmd):
        return cmd

    def cmd_link(self, _id: int):
        return Command.link(_id)

    def cmd_unlink(self, _id: int):
        return Command.unlink(_id)

    def cmd_delete(self, _id: int):
        return Command.delete(_id)

    def cmd_create(self, values: dict):
        return Command.create(values)

    def cmd_update(self, _id: int, values: dict):
        return Command.update(_id, values)

    def cmd_set(self, ids: list):
        return Command.set(ids)

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
    """
    3 stages query convention:
        Stage 1: Parse query string into statement or clause
        Stage 2: Check permission (This must be enforced or there will be security leak)
        Stage 3: Execute queries
    """

    START_RULES = ["start", "select_clause", "where_clause"]
    """Name of the rules that can be use as AST root."""

    def __init__(self):
        fp = os.path.join(os.path.dirname(__file__), "oql.lark")
        self.lark = lark.Lark.open(fp, parser="lalr", start=self.START_RULES)
        self.parser = self.lark.parser

    def parse(self, s: str, transformer: lark.Transformer, start: Optional[str] = None):
        """Parse `s` with an optional start rule and transform with `transformer`."""
        tree = self.parser.parse(s, start)
        try:
            result = transformer.transform(tree)
        except VisitError as ve:
            # Re-raise the original exception with its original traceback
            raise ve.orig_exc.with_traceback(ve.orig_exc.__traceback__)
        return result

    def query(self, s: str, env: odoo.api.Environment):
        """Full OQL query."""
        transformer = OqlTransformer(env)
        stmt: Statement = self.parse(s, transformer, start="start")
        self._check_perms(transformer.meta, stmt)
        return stmt.execute()

    def search(self, recs: models.Model, oql_where: str, offset=0, limit=None, order=None, count=False):
        transformer = OqlTransformer(recs.env)
        transformer.init_model(recs._name)
        where: WhereClause = self.parse(f"WHERE TRANSLATE {oql_where}", transformer, start="where_clause")
        self._check_perms(transformer.meta, where)
        return where.execute(recs.sudo(), transformer.meta, offset, limit, order, count)

    def read(self, recs: models.Model, fields: List[str] = None, load='_classic_read') -> List[Dict[str, Any]]:
        """
        Read OQL fields from `recs`.
        :param recs: Target records.
        :param fields: OQL style fields. Can be:
            1. None: meas all fields.
            2. Field list: ["xxx.yyy as zzz", "ccc"]
        :param load: Counterpart of odoo `read`'s `load` parameter.
        """
        # 1 Normalize `fields` to a comma-joined select list.
        fields_s = ", ".join(fields) if fields else "*"

        # 2 Parse the field list into a `SelectClause` by treating `select_clause` as the root.
        transformer = OqlTransformer(recs.env)
        transformer.init_model(recs._name)
        select: SelectClause = self.parse(f"SELECT TRANSLATE {fields_s}", transformer, start="select_clause")
        self._check_perms(transformer.meta, select)

        # 3 Read fields aligned with `recs` (mirrors `SelectStmt.execute` step 3).
        return select.execute(recs.sudo(), transformer.meta, load)

    def _check_perms(self, meta: OqlMeta, obj: IAcl):
        acl = meta.acl
        units: List[AclUnit] = []
        obj.gather_acl_units(units)
        units = self._unique_acl_units(units)
        errs = []
        model_units, member_units = [], []
        for unit in units:
            if unit.kind == UnitKind.MODEL or unit.kind == UnitKind.TERM:
                model_units.append(unit)
            else:
                member_units.append(unit)
        # 1. Check models, terms.
        for kind, units_kind in groupby(model_units, lambda x: x.kind):
            for mode, units_mode in groupby(units_kind, lambda x: x.mode):
                allowed = acl.perm_models(mode)
                self._extend_model_acl_errs(errs, mode, kind, units_mode, allowed)
        # 2. Check fields, aliases, methods.
        for model, units_model in groupby(member_units, lambda x: x.model_name):
            model: str
            mac = acl[model]
            for kind, units_kind in groupby(units_model, lambda x: x.kind):
                for mode, units_mode in groupby(units_kind, lambda x: x.mode):
                    units_mode: List[AclUnit]
                    if kind == UnitKind.FIELD:
                        self._extend_member_acl_errs(errs, mode, model, kind, units_mode, mac.perm_fields(mode))
                    elif kind == UnitKind.ALIAS:
                        self._extend_member_acl_errs(errs, mode, model, kind, units_mode, mac.perm_aliases(mode))
                    elif kind == UnitKind.METHOD:
                        self._extend_member_acl_errs(errs, mode, model, kind, units_mode, mac.perm_methods(mode, [x.name for x in units_mode]))
                    else:
                        raise NotImplementedError(f"ACL unit kind `{kind}`")
        # 3. Report.
        if errs:
            raise AccessError(_("Permissions denied:\n%s") % ('\n'.join(errs), ))

    @classmethod
    def _unique_acl_units(cls, units: List[AclUnit]) -> List[AclUnit]:
        key2unit: Dict[Tuple[str, str, UnitKind], AclUnit] = {}
        for unit in units:
            key = unit.key
            old = key2unit.get(key)
            if old:
                pass  # TODO: Merge
            else:
                key2unit[key] = copy.copy(unit)
        return list(key2unit.values())

    @classmethod
    def _extend_model_acl_errs(cls, errs: List[str], mode: FieldMode, kind: UnitKind,
                               units: List[AclUnit], allowed: Set[str]):
        denied_units = [x for x in units if x.model_name not in allowed]
        denied_units = [x for x in denied_units if not x.loose or not x.loose()]
        if denied_units:
            errs.append(_("%s %s: %s") % (
                mode,
                kind.name,
                ", ".join(x.name for x in denied_units),
            ))

    @classmethod
    def _extend_member_acl_errs(cls, errs: List[str], mode: FieldMode, model: str, kind: UnitKind,
                                units: List[AclUnit], allowed: Set[str]):
        denied_units = [x for x in units if x.name not in allowed]
        if denied_units:
            errs.append(_("%s `%s` %s: %s") % (
                mode,
                model,
                kind.name,
                ", ".join(x.name for x in denied_units),
            ))


reader = OqlReader()  # Global reader.
