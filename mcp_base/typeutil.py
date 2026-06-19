# @Time         : 23:27 2026/4/25
# @Author       : Chris
# @Description  : Type conversion utilities for MCP framework.
import inspect
import logging
import re
from typing import List, Dict, Any

_logger = logging.getLogger(__name__)


# Basic type mapping shared by both converters
BASIC_TYPE_MAP = {
    'str': 'string',
    'string': 'string',
    'unicode': 'string',
    'int': 'integer',
    'integer': 'integer',
    'long': 'integer',
    'float': 'number',
    'double': 'number',
    'number': 'number',
    'bool': 'boolean',
    'boolean': 'boolean',
    'list': 'array',
    'dict': 'object',
    'object': 'object',
    'any': 'string',
}


def get_origin(tp):
    """Get the origin of a generic type (compatible with Python 3.5+)."""
    return getattr(tp, '__origin__', None)


def get_args(tp):
    """Get the type arguments of a generic type."""
    return getattr(tp, '__args__', ())


def python_type_to_json_type(py_type):
    """Convert Python type annotations to JSON Schema types.
    
    Handles Python typing module types like List[str], Dict[str, int], Optional[T], etc.
    
    Args:
        py_type: Python type annotation (from function signature)
        
    Returns:
        str or dict: JSON Schema type string or object
            - Basic types: 'string', 'integer', 'number', 'boolean', 'null'
            - Complex types: {'type': 'array', 'items': {...}}, {'type': 'object'}
    
    Examples:
        >>> python_type_to_json_type(str)
        'string'
        >>> python_type_to_json_type(List[int])
        {'type': 'array', 'items': {'type': 'integer'}}
        >>> python_type_to_json_type(Dict[str, Any])
        {'type': 'object'}
    """
    if py_type == inspect.Parameter.empty:
        return "string"

    origin = get_origin(py_type)

    if origin is not None:
        # Handle Union/Optional types (Optional[X] is Union[X, None])
        # In Python 3.7-3.9, Union's origin may be typing._SpecialForm without __name__
        origin_name = getattr(origin, '__name__', None)
        if origin_name in ('Union', '_SpecialForm') or str(origin).startswith('typing.Union'):
            args = get_args(py_type)
            if args:
                # Filter out NoneType and return the first non-None type
                for arg in args:
                    if arg is not type(None):
                        return python_type_to_json_type(arg)
                # If all are None, return null
                return "null"
        elif origin in (list, tuple, set):
            args = get_args(py_type)
            if args:
                item_type = python_type_to_json_type(args[0])
                return {"type": "array", "items": {"type": item_type}}
            return {"type": "array", "items": {"type": "string"}}
        elif origin is dict:
            return {"type": "object"}
        elif origin_name == 'Literal':
            return {"type": "string"}

    # Handle bare list/dict/tuple/set types (Python 3.9+)
    type_mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        bytes: "string",
        type(None): "null",
        list: {"type": "array", "items": {"type": "string"}},
        dict: {"type": "object"},
        tuple: {"type": "array"},
        set: {"type": "array", "items": {"type": "string"}},
    }

    result = type_mapping.get(py_type, "string")
    return result if isinstance(result, dict) else result


def docstring_type_to_json_type(type_str):
    """Convert docstring type annotation string to JSON Schema type.
    
    Handles type strings from Sphinx/reST :type: directives like 'List[str]', 'Dict[str, int]'.
    
    Supports:
    - Basic types: str, int, float, bool, list, dict
    - Generic types: List[str], Dict[str, int], Optional[str]
    - Complex types: List[Dict[str, Any]], Union[int, str], etc.
    
    Args:
        type_str: Type string from docstring :type: directive
        
    Returns:
        str or dict: JSON Schema type (e.g., 'string', 'integer', or {'type': 'array', 'items': {...}})
    
    Examples:
        >>> docstring_type_to_json_type('str')
        'string'
        >>> docstring_type_to_json_type('List[int]')
        {'type': 'array', 'items': {'type': 'integer'}}
        >>> docstring_type_to_json_type('Optional[str]')
        'string'
    """
    if not type_str:
        return 'string'
    
    type_str = type_str.strip()
    
    # Handle Optional/Union types
    if type_str.startswith('Optional[') or type_str.startswith('Union['):
        match = re.match(r'(?:Optional|Union)\[(.+)\]', type_str)
        if match:
            inner_types = match.group(1).split(',')
            for t in inner_types:
                t = t.strip()
                if t.lower() not in ('none', 'nonetype'):
                    return docstring_type_to_json_type(t)
    
    # Handle List/Sequence types
    if type_str.startswith('List[') or type_str.startswith('Sequence['):
        match = re.match(r'(?:List|Sequence)\[(.+)\]', type_str)
        if match:
            item_type = docstring_type_to_json_type(match.group(1))
            items_schema = item_type if isinstance(item_type, dict) else {'type': item_type}
            return {'type': 'array', 'items': items_schema}
        return {'type': 'array', 'items': {'type': 'string'}}
    
    # Handle Dict/Mapping types
    if type_str.startswith('Dict[') or type_str.startswith('Mapping['):
        return {'type': 'object'}
    
    # Handle Tuple/Set types
    if type_str.startswith(('Tuple[', 'Set[')):
        return {'type': 'array'}
    
    # Basic type mapping
    basic_types = {
        'str': 'string',
        'string': 'string',
        'unicode': 'string',
        'int': 'integer',
        'integer': 'integer',
        'long': 'integer',
        'float': 'number',
        'double': 'number',
        'number': 'number',
        'bool': 'boolean',
        'boolean': 'boolean',
        'list': 'array',
        'dict': 'object',
        'object': 'object',
        'any': 'string',
    }
    
    return basic_types.get(type_str.lower(), 'string')


class OdooMro:
    def __init__(self, method: str, classes: List[type]):
        self.method = method
        self.classes = classes


class ParameterMeta:
    """Metadata for a single parameter."""
    json_type: str = None
    description: str = None

    def __init__(self, name: str, default):
        self.name = name
        self.default = default

    @property
    def closed(self):
        return self.json_type is not None and self.description is not None


class MethodMeta:
    """Complete metadata for a method."""
    def __init__(self, name: str, description: str = '', params: List[ParameterMeta] = None):
        self.name = name
        self.description = description
        self.params = params or []


def resolve_method_metadata(mro: OdooMro, inherit=True) -> MethodMeta:
    from .docstring import parse_docstring

    # Resolve in MRO order
    b_method_found = False
    method_desc = ""
    b_param_list_closed = False
    name2p_meta: Dict[str, ParameterMeta] = {}
    for cls in mro.classes:
        func = getattr(cls, mro.method, None)
        if not func:
            continue

        # Parse func
        signature = inspect.signature(func)
        params_iter = iter(signature.parameters.values())
        first_param = next(params_iter) if signature.parameters else None
        if first_param is None or first_param.name != "self":
            _logger.warning(f"{cls}.{mro.method} is not an instance method, ignored.")
            continue

        b_method_found = True

        # Parse param annotation.
        b_var_args = False
        for param in params_iter:
            if b_param_list_closed and param.name not in name2p_meta:
                continue  # Stop adding new params.
            if param.kind == inspect.Parameter.VAR_POSITIONAL or param.kind == inspect.Parameter.VAR_KEYWORD:
                b_var_args = True
                continue
            p_meta = name2p_meta.get(param.name)
            if p_meta is None:
                name2p_meta[param.name] = p_meta = ParameterMeta(param.name, param.default)
            if p_meta.json_type is None and param.annotation != inspect.Parameter.empty:
                p_meta.json_type = python_type_to_json_type(param.annotation)
        if not b_var_args:
            b_param_list_closed = True

        # Parse docstring.
        docstring = (func.__doc__ or "").strip()
        if docstring:
            doc_meta = parse_docstring(docstring)
            method_desc = (method_desc or doc_meta["description"] or "").strip()
            doc_name2param_desc = doc_meta["params"]
            doc_name2param_type = doc_meta["param_types"]
            for p_meta in name2p_meta.values():
                if p_meta.closed:
                    continue
                p_meta.json_type = p_meta.json_type or doc_name2param_type.get(p_meta.name)
                p_meta.description = p_meta.description or doc_name2param_desc.get(p_meta.name)

        # Break directly when inherit is turned off.
        if not inherit:
            break

        # Check close state to determine early return.
        if (method_desc and
                b_param_list_closed and
                (not name2p_meta or all(x.closed for x in name2p_meta.values()))
        ):
            break

    # Format and return.
    if not b_method_found:
        raise KeyError(f"Method `{mro.method}` not found on any of `{mro.classes}`.")
    return MethodMeta(mro.method,
                      method_desc,
                      list(name2p_meta.values()))
