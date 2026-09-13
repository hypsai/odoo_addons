# @Time         : 11:43 2026/9/3
# @Author       : Chris
# @Description  : Unbound static functions.
from typing import List, Any, Dict, Tuple, Callable, Optional

from odoo import models, fields

from .base import IRecsReader, AclUnit, FieldMode
from .util import degrade_acl
from odoo.tools.translate import _

_global: Dict[str, Tuple[Callable[[models.Model, ...], Any], bool]] = {}  # {name: (func, is_agg)}
"""models.Model is used for context accessing."""


def register(name: str, func: Callable[[models.Model, ...], Any], is_agg: bool = False, force: bool = False):
    if not force:
        registered = _global.get(name)
        if registered and func is not registered[0]:
            raise KeyError(f"Name `{name}` has already been registered as `{registered}`.")
    _global[name] = (func, is_agg)


def resolve_call(name: str, is_agg: Optional[bool], args) -> Tuple[Optional[Callable[[models.Model, ...], Any]], bool]:
    """Resolve a call's aggregate-ness and its registered global function.

    * `is_agg is None`: infer from the global registry.
    * explicit `is_agg` inconsistent with the registry: drop the global func.
    Also validates that every `IRecsReader` arg matches the call's aggregate-ness.
    """
    g_func = None
    t_func = _global.get(name)
    if t_func:
        g_func, g_is_agg = t_func
        if is_agg is None:
            is_agg = g_is_agg
        elif bool(g_is_agg) ^ bool(is_agg):
            g_func = None  # Registry disagrees with the explicit marker, discard it.
    is_agg = bool(is_agg)
    bad_args = [x for x in args if isinstance(x, IRecsReader) and x.is_agg ^ is_agg]
    if bad_args:
        raise Exception(_("Function `%s(...)`: %s function can't be called on %s args %s") % (
            name,
            _("Aggregate") if is_agg else _("Non-aggregate"),
            _("non-aggregate") if is_agg else _("aggregate"),
            bad_args,
        ))
    return g_func, is_agg


class UnboundFuncCall(IRecsReader):
    """Function call node in OQL. e.g. `lower(name)`, `count(tag_ids)`, `count(*)`.

    Note: Only the grammar and the parse-tree structure are defined for now.
    Evaluation is not implemented yet. Extension points:
    * `eval_bin`: Use the function result as the left operand of a binary
      expression. e.g. `where lower(name) = 'x'`.
    * `read`: Use the function result as a SELECT field. e.g.
      `select count(tag_ids) as cnt`.
    """

    name: str
    """Function name. e.g. `lower`, `count`."""

    args: Tuple[Any]
    """Arguments. `FieldAccess` for field arguments, plain values for literals.
    `count(*)` and `count()` are both parsed as empty args."""

    def __init__(self, name: str, args: Tuple[Any], is_agg: Optional[bool] = None):
        self.name = name
        self.args = args
        self._as = name
        # Resolve global func + aggregate-ness, and check arg consistency.
        self._g_func: Optional[Callable]
        self._is_agg: bool
        self._g_func, self._is_agg = resolve_call(name, is_agg, args)
        if not self._g_func:
            raise Exception(_("Function %s(...) not implemented") % name)

    @property
    def is_agg(self) -> bool:
        return self._is_agg

    @property
    def as_(self) -> str:
        """Result name in SELECT output. Defaults to the function name."""
        return self._as

    @as_.setter
    def as_(self, value: str):
        self._as = value

    @property
    def path(self) -> str:
        """Pseudo path, for `id` presence check in SELECT and debugging."""
        return self.name

    def eval_bin(self, opr: str, value):
        raise NotImplementedError(
            _("Function `%s(...)` in expressions is not implemented yet. "
              "Implement `UnboundFuncCall.eval_bin` to support it.") % self.name)

    def read(self, recs, load='_classic_read') -> list:
        # 1 Prepare func
        func = self._g_func
        recs = recs.sudo(False)  # recs are used for context accessing only.
        # 2 Invoke
        args = self.args
        if self.is_agg:
            # 2.1 Aggregate invoke
            arg_vals = [x.read(recs, load) if isinstance(x, IRecsReader) else x for x in self.args]
            return [func(recs, *degrade_acl(arg_vals))]
        elif args:
            # 2.2 Non-aggregate and invoke with args
            arg_cols = []
            for arg in args:
                if isinstance(arg, IRecsReader):
                    arg_cols.append(arg.read(recs, load))
                else:
                    arg_cols.append([arg] * len(recs))
            return [func(rec, *degrade_acl(args)) for rec, args in zip(recs, zip(*arg_cols, strict=True), strict=True)]
        else:
            # 2.3 Non-aggregate and invoke without args.
            return [func(rec) for rec in recs]

    def gather_acl_units(self, res: List[AclUnit], mode: FieldMode):
        for arg in self.args:
            if isinstance(arg, IRecsReader):
                arg.gather_acl_units(res, mode)

    def __str__(self):
        return f"{type(self).__name__}({self.name}, args[{len(self.args)}])"

    def __repr__(self):
        return str(self)


# =======================
# OQL Built-in Functions
# -----------------------

def _func_lower(self: models.Model, val):
    return val.lower() if isinstance(val, str) else val


def _func_upper(self: models.Model, val):
    return val.upper() if isinstance(val, str) else val


def _func_strip(self: models.Model, val):
    return val.strip() if isinstance(val, str) else val


def _func_replace(self: models.Model, val, old, new):
    return val.replace(old, new) if isinstance(val, str) else val


def _func_concat(self: models.Model, *args):
    return " ".join(str(x) for x in args if x is not None and x is not False and x != "")


def _func_len(self: models.Model, val):
    return len(val) if val else 0


def _func_abs(self: models.Model, val):
    return abs(val) if val else val


def _func_round(self: models.Model, val, digits=0):
    return round(val, digits) if val else val


def _func_int(self: models.Model, val):
    return int(val) if val else val


def _func_float(self: models.Model, val):
    return float(val) if val else val


def _func_str(self: models.Model, val):
    return "" if val is None or val is False else str(val)


def _func_year(self: models.Model, val):
    date = fields.Date.to_date(val)
    return date.year if date else None


def _func_month(self: models.Model, val):
    date = fields.Date.to_date(val)
    return date.month if date else None


def _func_day(self: models.Model, val):
    date = fields.Date.to_date(val)
    return date.day if date else None


def _func_today(self: models.Model):
    return fields.Date.context_today(self)


def _func_now(self: models.Model):
    return fields.Datetime.now()


def _func_ref(self: models.Model, name: str):
    return self.env.ref(name)


def _agg_column(self: models.Model, values):
    """Normalize an aggregate arg: a field-path literal or a read value column."""
    if isinstance(values, str):
        return self.mapped(values)
    return values or []


def _func_count(self: models.Model, field=None):
    if field:
        return len([x for x in self.mapped(field) if x is not False])
    return len(self)


def _func_sum(self: models.Model, values):
    return sum(v for v in _agg_column(self, values) if v)


def _func_avg(self: models.Model, values):
    vals = [v for v in _agg_column(self, values) if v]
    return sum(vals) / len(vals) if vals else None


def _func_min(self: models.Model, values):
    vals = [v for v in _agg_column(self, values) if v]
    return min(vals) if vals else None


def _func_max(self: models.Model, values):
    vals = [v for v in _agg_column(self, values) if v]
    return max(vals) if vals else None


# === Non-aggregate ===
_global["lower"] = (_func_lower, False)
_global["upper"] = (_func_upper, False)
_global["strip"] = (_func_strip, False)
_global["replace"] = (_func_replace, False)
_global["concat"] = (_func_concat, False)
_global["len"] = (_func_len, False)
_global["abs"] = (_func_abs, False)
_global["round"] = (_func_round, False)
_global["int"] = (_func_int, False)
_global["float"] = (_func_float, False)
_global["str"] = (_func_str, False)
_global["year"] = (_func_year, False)
_global["month"] = (_func_month, False)
_global["day"] = (_func_day, False)
_global["today"] = (_func_today, False)
_global["now"] = (_func_now, False)
_global["ref"] = (_func_ref, False)

# === Aggregate ===
_global["count"] = (_func_count, True)
_global["sum"] = (_func_sum, True)
_global["avg"] = (_func_avg, True)
_global["min"] = (_func_min, True)
_global["max"] = (_func_max, True)
