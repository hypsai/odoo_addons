# @Time         : 11:43 2026/9/3
# @Author       : Chris
# @Description  :
from collections import deque
from typing import List, Any, Dict, Tuple, Callable, Optional, Deque

from odoo import _, models, fields

from .base import IRecsReader
from .field import FieldAccess

_global: Dict[str, Tuple[Callable, bool]] = {}  # {name: (func, is_agg)}


def register(name: str, func, is_agg: bool = False, force: bool = False):
    if not force:
        registered = _global.get(name)
        if registered and func is not registered[0]:
            raise KeyError(f"Name `{name}` has already been registered as `{registered}`.")
    _global[name] = (func, is_agg)


class FuncCall(IRecsReader):
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

    args: List[Any]
    """Arguments. `FieldAccess` for field arguments, plain values for literals.
    `count(*)` and `count()` are both parsed as empty args."""

    def __init__(self, name: str, args: List[Any], is_agg: Optional[bool] = None):
        self.name = name
        self.args = args
        self._as = name
        self._is_agg = is_agg
        # Preload global func.
        t_func = _global.get(name)
        g_func = None
        if t_func:
            g_func, g_is_agg = t_func
            if is_agg is None:
                is_agg = g_is_agg
            elif g_is_agg ^ is_agg:
                g_func = None  # Global function is inconsistent with `is_agg` param, discard global func.
        is_agg = bool(is_agg)
        self._g_func: Optional[Callable] = g_func
        self._is_agg: bool = is_agg
        # Check args.
        bad_args = [x for x in args if isinstance(x, IRecsReader) and x.is_agg ^ is_agg]
        if bad_args:
            raise Exception(_("%s: %s function can't be called on %s args %s") % (
                self,
                _("Aggregate") if is_agg else _("Non-aggregate"),
                _("non-aggregate") if is_agg else _("aggregate"),
                bad_args,
            ))

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
              "Implement `FuncCall.eval_bin` to support it.") % self.name)

    def read(self, recs, load='_classic_read') -> list:
        # 0 Check permission
        if self.name.startswith('_'):
            if not recs.env.is_admin():
                raise PermissionError(f"Only administrators can invoke private model method. Method: `{self.name}`.")
        # 1 Prepare func
        func = getattr(type(recs), self.name, None)
        if not callable(func):
            func = self._g_func
        if not func:
            raise NotImplementedError(
                _("Function `%s(...)` not implemented. ") % self.name
            )
        func: Callable
        # 2 Invoke
        args = self.args
        if self.is_agg:
            # 2.1 Aggregate invoke
            arg_vals = [x.read(recs, load) if isinstance(x, IRecsReader) else x for x in self.args]
            return [func(recs, *arg_vals)]
        elif args:
            # 2.2 Non-aggregate and invoke with args
            arg_cols = []
            for arg in args:
                if isinstance(arg, IRecsReader):
                    arg_cols.append(arg.read(recs, load))
                else:
                    arg_cols.append([arg] * len(recs))
            return [func(rec, *args) for rec, args in zip(recs, zip(*arg_cols, strict=True), strict=True)]
        else:
            # 2.3 Non-aggregate and invoke without args.
            return [func(rec) for rec in recs]

    def get_fas(self) -> List[FieldAccess]:
        """Get `FieldAccess` objects recursively."""
        fas = []
        q: Deque[FuncCall] = deque()
        q.append(self)
        while len(q):
            node = q.popleft()
            for arg in node.args:
                if isinstance(arg, FieldAccess):
                    fas.append(arg)
                elif isinstance(arg, FuncCall):
                    q.append(arg)
        return fas

    def __str__(self):
        return f"{type(self).__name__}({self.name}, args[{len(self.args)}])"

    def __repr__(self):
        return str(self)


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


def _agg_column(self: models.Model, values):
    """Normalize an aggregate arg: a field-path literal or a read value column."""
    if isinstance(values, str):
        return self.mapped(values)
    return values or []


def _func_count(self: models.Model, field=None):
    if field:
        return len([x for x in self.mapped(field) if x])
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

# === Aggregate ===
_global["count"] = (_func_count, True)
_global["sum"] = (_func_sum, True)
_global["avg"] = (_func_avg, True)
_global["min"] = (_func_min, True)
_global["max"] = (_func_max, True)
