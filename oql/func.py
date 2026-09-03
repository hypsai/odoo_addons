# -*- coding: utf-8 -*-
# @Time         : 11:43 2026/9/3
# @Author       : Chris
# @Description  :
from typing import List, Any

from odoo import _


class FuncCall:
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

    def __init__(self, name: str, args: List[Any], as_: str = None):
        self.name = name
        self.args = args
        self._as = as_ or name

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
        raise NotImplementedError(
            _("Function `%s(...)` in SELECT fields is not implemented yet. "
              "Implement `FuncCall.read` to support it.") % self.name)

    def __str__(self):
        return f"{type(self).__name__}({self.name}, args[{len(self.args)}])"

    def __repr__(self):
        return str(self)
