# -*- coding: utf-8 -*-
# @Description  : Python-like chained select expression, e.g. `tag_ids[0].name`,
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple, Union

from odoo import _, models

from .alias import AliasNode
from .base import IRecsReader, AclUnit, UnitKind, FieldMode
from .meta import OqlMeta
from .util import tn, degrade_acl

OType = Union[models.Model, type, None]


class Step(ABC):
    """A single step of a chain, with a typed payload in each subclass."""

    __slots__ = ("is_agg", "input_type")

    input_type: OType
    """Statically resolved input type for this step. (Output of last step)"""

    def __init__(self, is_agg: bool = False):
        self.is_agg = bool(is_agg)

    @abstractmethod
    def chip(self) -> str:
        """Source fragment of this step, e.g. `.name`, `.name(...)`, `[0]`."""
        raise NotImplementedError()

    @abstractmethod
    def read(self, recs: models.Model, prev, load: str, expr: str):
        """Process the previous step's `value` (the base `recs` for the first
        step). Returns a column aligned with the records.
        :param recs: Initial recs for the chain.
        :param prev: Result of previous step.
        :param load: `load` parameter for odoo ORM's `read` method.
        :param expr: Literal expression of the chain, will be used for error report.
        """
        raise NotImplementedError()

    @abstractmethod
    def resolve(self) -> OType:
        """Static resolving, return the result type of this step."""
        raise NotImplementedError()

    @abstractmethod
    def gather_acl_units(self, res: List[AclUnit], mode):
        raise NotImplementedError()

    def __repr__(self):
        keys = [k for k in getattr(type(self), "__slots__", ()) if not k.startswith("_")]
        args = ", ".join("%s=%r" % (k, getattr(self, k)) for k in keys)
        return "%s(%s)" % (type(self).__name__, args)


class StepAttr(Step):
    """`.name` attribute navigation.

    Non-aggregate: read `name` from every element (for-in). Aggregate: fold the
    input into one value, i.e. the whole column as a single row (like `@field`).
    """

    __slots__ = ("name",)

    def __init__(self, name: str, is_agg: bool = False):
        super().__init__(is_agg)
        self.name = name

    def chip(self) -> str:
        return "." + self.name

    def read(self, recs, prev, load, expr):
        name = self.name
        if self.is_agg:
            return self._read(prev, name, expr)
        return [self._read(x, name, expr) for x in prev]

    def resolve(self) -> OType:
        return None

    def gather_acl_units(self, res: List[AclUnit], mode):
        pass

    @staticmethod
    def _read(value, name: str, expr: str):
        """Read `name` from one value: record / dict / object, like Python."""
        if isinstance(value, dict):
            if name in value:
                return value[name]
            raise Exception(_("OQL chain `%s`: key `%s` not found in dict `%s`.")
                            % (expr, name, value))
        try:
            return getattr(value, name)
        except AttributeError as e:
            raise Exception(_("OQL chain `%s`: `%s` has no attribute `%s`.")
                            % (expr, tn(value), name)) from e


class StepField(StepAttr):
    def __init__(self, model: models.Model, attr: StepAttr):
        super().__init__(attr.name, attr.is_agg)
        self.model = model

    def read(self, recs, prev, load, expr):
        if prev._name != self.model._name:  # noqa
            raise Exception(_("OQL chain `%s`: expected `%s` records, got `%s`.")
                            % (expr, self.model._name, prev._name))
        name = self.name
        prev.mapped(name)  # Prefetch
        if self.is_agg:
            return self._read(prev, name, expr)
        return [self._read(x, name, expr) for x in prev]

    def resolve(self) -> OType:
        return self.model[self.name]

    def gather_acl_units(self, res: List[AclUnit], mode):
        res.append(AclUnit(self.model, self.name, UnitKind.FIELD, mode))

    @staticmethod
    def _read(value, name: str, expr: str):
        try:
            return getattr(value, name)
        except Exception as e:
            raise Exception(_("OQL chain `%s`: failed reading `%s` on `%s`: %s")
                            % (expr, name, tn(value), e)) from e


class StepAlias(StepAttr):
    def __init__(self, model: models.Model, alias: AliasNode, attr: StepAttr):
        super().__init__(attr.name, attr.is_agg)
        self.alias = alias
        self.model = model

    def resolve(self) -> OType:
        alias = self.alias
        if alias.is_complex:
            return None
        return self.model.mapped(alias.path)

    def gather_acl_units(self, res: List[AclUnit], mode):
        res.append(AclUnit(self.model, self.name, UnitKind.ALIAS, mode))


class StepIndex(Step):
    """`[n]` subscript (`__getitem__`)."""

    __slots__ = ("index",)

    def __init__(self, index: int, is_agg: bool = False):
        super().__init__(is_agg)
        self.index = index

    def chip(self) -> str:
        return "[%s]" % self.index

    def read(self, recs, prev, load, expr):
        idx = self.index
        col = [self._item(el, idx, expr) for el in prev]
        return [col] if self.is_agg else col

    def resolve(self) -> OType:
        if self.input_type is models.Model:
            return self.input_type
        return None

    def gather_acl_units(self, res: List[AclUnit], mode):
        pass

    @staticmethod
    def _item(el, idx: int, expr: str):
        """`value[idx]` with a chain-aware error message."""
        if isinstance(el, models.Model):
            if idx >= len(el):
                return el.browse()  # Fail free
            return el[idx]
        elif isinstance(el, (list, tuple, str, bytes, dict)):
            try:
                return el[idx]
            except Exception as e:
                raise Exception(_("OQL chain `%s`: can't index `%s` with `%s`: %s")
                                % (expr, tn(el), idx, e)) from e
        if el is None or el is False:
            raise Exception(_("OQL chain `%s`: can't index empty value `%s` with `%s`.")
                            % (expr, el, idx))
        raise Exception(_("OQL chain `%s`: `%s` is not subscriptable with `%s`.")
                        % (expr, tn(el), idx))


class StepCall(Step):
    """`.name(...)` call, applied to the current value.

    Non-aggregate: invoke the method on every element of the input (for-in).
    Aggregate: invoke it once on the whole input and fold to a single value.
    """

    __slots__ = ("name", "args", "_g_func")

    def __init__(self, name: str, args: Tuple[Any], is_agg: Optional[bool] = None):
        super().__init__(is_agg)
        self.name = name
        self.args = args

    def chip(self) -> str:
        return ".%s(...)" % self.name

    def read(self, recs, prev, load, expr):
        prev = degrade_acl(prev)
        args = self.args
        if self.is_agg:
            args = [x.read(recs, load) if isinstance(x, IRecsReader) else x for x in args]
            return self._invoke(prev, args, expr)
        else:
            return [
                self._invoke(prev_val, [
                    x.read(x, load) if isinstance(x, IRecsReader) else x for x in args
                ], expr) for rec, prev_val in zip(recs, prev, strict=True)
            ]

    def resolve(self) -> OType:
        return None

    def gather_acl_units(self, res: List[AclUnit], mode: FieldMode):
        if self.input_type is models.Model:
            res.append(AclUnit(self.input_type, self.name, UnitKind.METHOD, "invoke"))
            for arg in self.args:
                if isinstance(arg, IRecsReader):
                    arg.gather_acl_units(res, mode)

    def _invoke(self, el, argv: List[Any], expr: str):
        method = getattr(el, self.name, None)
        if callable(method):
            return method(*argv)
        if method is not None:
            raise Exception(_("OQL chain `%s`: `%s.%s` is not callable.")
                            % (expr, tn(el), self.name))
        raise NotImplementedError(_(
            "OQL chain `%s`: function `%s(...)` not implemented for type `%s`.")
            % (expr, self.name, tn(el))
        )


class Chain(IRecsReader):
    """A chained select expression, folded left over its steps.

    The first step's input is the base `recs`; every following step processes
    the column the previous step produced, so `tag_ids[0].name`,
    `partner.mapped('name')` and `read(['id'])[0].id` all share one model.
    """

    def __init__(self, model: models.Model, meta, steps: tuple,
                 as_: Optional[str] = None):
        self.model = model
        self.meta = meta
        self.steps: Tuple[Step] = steps  # Preflight for chain text resolving.
        self.steps = self._resolve_steps(model, meta, steps)
        self._as = as_ or self.text

    # -- IRecsReader ------------------------------------------------
    @property
    def is_agg(self) -> bool:
        return any(step.is_agg for step in self.steps)

    @property
    def as_(self) -> str:
        return self._as

    @as_.setter
    def as_(self, value: str):
        self._as = value

    @property
    def text(self) -> str:
        """Approximate source text of the chain, e.g. `tag_ids[0].name`."""
        return ''.join(step.chip() for step in self.steps).lstrip('.')

    @property
    def path(self) -> str:
        return self.text

    def read(self, recs, load='_classic_read') -> list:
        if recs._name != self.model._name:  # noqa
            raise Exception(_("OQL chain `%s`: expected `%s` records, got `%s`.")
                            % (self.text, self.model._name, recs._name))  # noqa

        expr = self.text
        value = recs
        for step in self.steps:
            value = step.read(recs, value, load, expr)
        return value

    def gather_acl_units(self, res: List[AclUnit], mode):
        for step in self.steps:
            step.gather_acl_units(res, mode)

    def _resolve_steps(self, model: models.Model, meta: OqlMeta, steps):
        """Static resolving."""
        expr = self.text
        p_type = model
        resolved = []
        for step in steps:
            step.input_type = p_type
            if isinstance(step, StepAttr):
                if isinstance(p_type, models.Model):
                    # Model field or alias.
                    res_step = None
                    _fields = p_type._fields  # noqa
                    field = _fields.get(step.name)
                    if field:
                        res_step = StepField(p_type, step)
                    else:
                        alias = meta.get_alias(p_type._name, step.name)  # noqa
                        if alias:
                            res_step = StepAlias(p_type, alias, step)
                    if res_step is None:
                        raise AttributeError(_(
                            "OQL chain `%s`: model `%s` has no field or alias `%s`."
                        ) % (expr, p_type._name, step.name))
                else:
                    res_step = step
            else:
                res_step = step
            res_step.input_type = p_type
            resolved.append(res_step)
            p_type = res_step.resolve()
        return tuple(resolved)

    def __str__(self):
        return f"{type(self).__name__}({self.text})"

    def __repr__(self):
        return str(self)
