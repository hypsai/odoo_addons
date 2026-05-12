# -*- coding: utf-8 -*-
# @Time         : 11:01 2025/10/17
# @Author       : Chris
# @Description  :
from collections import defaultdict
from typing import List, Callable, Any, Union

from odoo import models, fields


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


_FIELD_TYPE_MAPPING = {
    'char': str,
    'text': str,
    'html': str,
    'integer': int,
    'float': float,
    'monetary': float,
    'boolean': bool,
    'date': str,
    'datetime': str,
    'binary': bytes,
    'selection': str,
    'many2one': int,
    'one2many': list,
    'many2many': list,
    'properties': dict,
    'json': dict,
}


def field_type2python_type(o_type: str) -> type:
    """
    Convert Odoo field type string to Python type.

    :param o_type: Odoo field type (e.g., 'char', 'integer', 'float', 'boolean', 'many2one', etc.)
    :return: Corresponding Python type
    """
    p_type = _FIELD_TYPE_MAPPING.get(o_type)
    if p_type is None:
        raise NotImplementedError(f"Don't know counterpart python type for odoo field type `{o_type}`.")
    return p_type


def get_field_def(recs: models.Model, path: str) -> fields.Field:
    """
    Get field definition by dot style path.
    """
    chips = path.split('.')
    p = recs
    for i in range(len(chips)-1):
        chip = chips[i]
        if not hasattr(p, chip):
            raise KeyError(f"Failed getting field definition on `{path}` of `{recs}`, "
                           f"`{'.'.join(chips[:i+1])}` -> `{p}` does not have field `{chip}`.")
        p = p[chip]
        if not isinstance(p, models.Model):
            raise ValueError(f"Failed getting field definition on `{path}` of `{recs}`, "
                             f"`{'.'.join(chips[:i+1])}` is not a relational field.")
    field_def = p._fields.get(chips[-1])
    if field_def is None:
        raise KeyError(f"Failed getting field definition on `{path}` of `{recs}`, "
                       f"`{'.'.join(chips[:-1])}` -> `{p}` does not have field `{chips[-1]}`.")
    return field_def


def get_field_type(field_def: fields.Field) -> Union[type, str]:
    if field_def.relational:
        return f"Records[{field_def.comodel_name}]"
    return field_type2python_type(field_def.type)


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


def groupby(iterable, key, convert_item=None, returns_dict=False):
    """
    Similar to 'itertools.groupby', but this function can work on unsorted data.
    * 'itertools.groupby' works only on ordered data.
    """
    if convert_item is None:
        def convert_item(x):
            return x
    res_dict = defaultdict(list)
    for item in iterable:
        res_dict[key(item)].append(convert_item(item))
    return res_dict if returns_dict else res_dict.items()


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
