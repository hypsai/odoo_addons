# -*- coding: utf-8 -*-
# @Time         : 11:01 2025/10/17
# @Author       : Chris
# @Description  :
from collections import defaultdict
from typing import List, Callable, Any

from odoo import models


def parse_list(s: str) -> List[str]:
    """Parse comma-delimited string into list of strings."""
    if not s:
        return []
    return [x.strip() for x in s.split(',')]


def parse_type_list(s: str, ignore_errors=False) -> List[type]:
    """Parse comma-delimited string to list of types."""
    s_types = parse_list(s)
    types = []
    for s_type in s_types:
        try:
            types.append(eval(s_type))
        except Exception as e:
            if ignore_errors:
                continue
            raise ValueError(f"Invalid type name '{s_type}'.") from e
    return types


def fullname(klass: type):
    """Get full qualified name of a type."""
    module = klass.__module__
    if module == 'builtins':
        return klass.__qualname__
    return f"{module}.{klass.__qualname__}"


def tn(obj):
    """Get OQL style type name for object."""
    if isinstance(obj, models.AbstractModel):
        return f"Odoo[{obj._name}]"
    if isinstance(obj, type):
        return fullname(obj)
    return fullname(type(obj))


def read_object(obj, path: str):
    """
    Read object field with dot style path.
    """
    chips = path.split('.')
    p = obj
    for chip in chips:
        if hasattr(p, chip):
            p = getattr(p, chip)
        else:
            raise KeyError(f"`{type(obj)}.{path}` not exist, missing field `{type(p)}.{chip}`.")
    return p


class KeyPassingDefaultDict(defaultdict):
    def __init__(self, factory: Callable[[Any], Any]):
        super().__init__(factory)

    def __missing__(self, key):
        # Call the default_factory with the missing key
        if self.default_factory:
            value = self.default_factory(key)
        else:
            # If no default_factory is set, behave like a regular defaultdict
            # or raise a KeyError if desired.
            raise KeyError(key)

        self[key] = value  # Store the newly created value
        return value
