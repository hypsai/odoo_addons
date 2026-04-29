# -*- coding: utf-8 -*-
# @Time         : 23:27 2026/4/25
# @Author       : Chris
# @Description  : Type conversion utilities for MCP framework.
import inspect
import re
from typing import List, Dict, Any

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
        if origin in (list, tuple, set):
            args = get_args(py_type)
            if args:
                item_type = python_type_to_json_type(args[0])
                return {"type": "array", "items": {"type": item_type}}
            return {"type": "array", "items": {"type": "string"}}
        elif origin is dict:
            return {"type": "object"}
        elif origin.__name__ == 'Literal':
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


class ParameterMeta:
    """Metadata for a single parameter."""
    def __init__(self, name: str, json_type: Any, description: str = '', default: Any = None):
        self.name = name
        self.json_type = json_type  # Can be string or dict for complex types
        self.description = description
        self.default = default


class MethodMeta:
    """Complete metadata for a method."""
    def __init__(self, name: str, description: str = '', params: List[ParameterMeta] = None):
        self.name = name
        self.description = description
        self.params = params or []


def resolve_method_metadata(func, inherit=True) -> MethodMeta:
    """Resolve complete method metadata with intelligent inheritance.
    
    This function recursively searches up the class hierarchy to gather
    complete metadata for a method and all its parameters. It merges
    information from parent classes when child classes have incomplete
    annotations or docstrings.
    
    For methods with *args/**kwargs, it drills down to find the actual
    parameters from parent methods while preserving **kwargs in the final
    signature (since code may use kwargs.get('xxx')).
    
    Args:
        func: The method function to resolve metadata for.
        inherit: If True, search parent classes for missing info. Default True.
        
    Returns:
        dict: Complete metadata including:
            - 'docstring': Best available method docstring
            - 'annotations': Merged parameter type annotations
            - 'signature': Method signature (may include **kwargs)
            - 'param_descriptions': Parameter descriptions from docstring
    """
    # Try to get the class from __objclass__ (for bound methods)
    cls = getattr(func, '__objclass__', None)
    
    # If not a bound method, try to extract class from __qualname__
    if cls is None:
        qualname = getattr(func, '__qualname__', '')
        if '.' in qualname:
            parts = qualname.rsplit('.', 1)
            if len(parts) == 2:
                class_name = parts[0]
                # Try to get class from function's globals
                func_globals = getattr(func, '__globals__', {})
                cls = func_globals.get(class_name)
                
                # If not found in globals, try module
                if cls is None:
                    try:
                        module = inspect.getmodule(func)
                        if module:
                            cls = getattr(module, class_name, None)
                    except (AttributeError, ValueError):
                        cls = None
    
    # Resolve metadata
    if cls is not None and inherit:
        # Class is available - resolve from hierarchy
        method_name = func.__name__
        return _resolve_from_class_hierarchy(cls, method_name)
    else:
        # No inheritance or class not available - use function's own metadata
        return _build_method_meta_from_func(func)


def _build_method_meta_from_func(func) -> MethodMeta:
    """Build MethodMeta from a single function without inheritance."""
    from .docstring import parse_docstring
    
    docstring = inspect.getdoc(func) or ''
    parsed = parse_docstring(docstring)
    description = parsed.get('description', '')
    param_descriptions = parsed.get('params', {})
    param_types_from_docstring = parsed.get('param_types', {})
    annotations = getattr(func, '__annotations__', {})
    
    try:
        signature = inspect.signature(func)
    except (ValueError, TypeError):
        signature = None
    
    params = []
    if signature:
        for name, param in signature.parameters.items():
            if name == 'self':
                continue
            
            # Determine type
            if param.annotation != inspect.Parameter.empty:
                json_type = python_type_to_json_type(param.annotation)
            elif name in annotations:
                json_type = python_type_to_json_type(annotations[name])
            elif name in param_types_from_docstring:
                json_type = param_types_from_docstring[name]
            else:
                json_type = 'string'
            
            # Get description
            desc = param_descriptions.get(name, '')
            
            # Get default
            default = param.default if param.default != inspect.Parameter.empty else None
            
            params.append(ParameterMeta(
                name=name,
                json_type=json_type,
                description=desc,
                default=default
            ))
    
    return MethodMeta(
        name=func.__name__,
        description=description,
        params=params
    )


def _resolve_from_class_hierarchy(cls, method_name) -> MethodMeta:
    """Resolve method metadata by intelligently walking up the class hierarchy.
    
    For each parameter, searches up the inheritance chain until all information
    is found (type from annotations, description from docstring). Handles *args/**kwargs
    by drilling down to find actual parameters while preserving **kwargs in signature.
    
    Args:
        cls: The class to start searching from
        method_name: Name of the method to find
        
    Returns:
        MethodMeta: Complete method metadata object
    """
    # Collect all methods with this name from the class hierarchy
    methods_in_hierarchy = []
    for klass in cls.__mro__:
        if hasattr(klass, method_name):
            method = getattr(klass, method_name)
            if callable(method) and not isinstance(method, type):
                methods_in_hierarchy.append((klass, method))
    
    if not methods_in_hierarchy:
        return MethodMeta(name=method_name)
    
    # Start with the first (most derived) method
    primary_cls, primary_method = methods_in_hierarchy[0]
    
    # Get primary method's signature
    try:
        primary_sig = inspect.signature(primary_method)
    except (ValueError, TypeError):
        primary_sig = None
    
    # Check if primary method uses *args/**kwargs
    has_var_keyword = False
    if primary_sig:
        for param in primary_sig.parameters.values():
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                has_var_keyword = True
                break
    
    # If primary method has **kwargs, find the most specific parent signature
    effective_sig = primary_sig
    if has_var_keyword:
        # Look for parent method with concrete parameters
        for klass, method in methods_in_hierarchy[1:]:
            try:
                sig = inspect.signature(method)
                # Check if this parent has concrete parameters
                has_concrete_params = any(
                    p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                    for p in sig.parameters.values()
                    if p.name != 'self'
                )
                if has_concrete_params:
                    effective_sig = sig
                    break
            except (ValueError, TypeError):
                continue
    
    # Merge annotations from all levels
    best_annotations = {}
    for klass, method in methods_in_hierarchy:
        parent_annotations = getattr(method, '__annotations__', {})
        for param_name, param_type in parent_annotations.items():
            if param_name not in best_annotations:
                best_annotations[param_name] = param_type
    
    # Merge docstrings - use first available non-empty docstring
    best_docstring = ''
    for klass, method in methods_in_hierarchy:
        docstring = inspect.getdoc(method)
        if docstring:
            best_docstring = docstring
            break
    
    # Parse docstring to extract descriptions
    from .docstring import parse_docstring
    parsed = parse_docstring(best_docstring)
    description = parsed.get('description', '')
    param_descriptions = parsed.get('params', {})
    param_types_from_docstring = parsed.get('param_types', {})
    
    # Merge parameter descriptions from parent docstrings
    if not param_descriptions:
        for klass, method in methods_in_hierarchy[1:]:
            docstring = inspect.getdoc(method)
            if docstring:
                parsed_parent = parse_docstring(docstring)
                parent_descs = parsed_parent.get('params', {})
                for param_name, desc in parent_descs.items():
                    if param_name not in param_descriptions:
                        param_descriptions[param_name] = desc
    
    # Build final signature: use effective_sig but preserve **kwargs if present
    final_sig = effective_sig
    if has_var_keyword and effective_sig and effective_sig != primary_sig:
        params_list = list(effective_sig.parameters.values())
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params_list)
        if not has_kwargs:
            for param in primary_sig.parameters.values():
                if param.kind == inspect.Parameter.VAR_KEYWORD:
                    params_list.append(param)
                    break
            final_sig = primary_sig.replace(parameters=params_list)
    
    # Build ParameterMeta objects
    params = []
    if final_sig:
        for name, param in final_sig.parameters.items():
            if name == 'self':
                continue
            
            # Determine type with priority
            if param.annotation != inspect.Parameter.empty:
                json_type = python_type_to_json_type(param.annotation)
            elif name in best_annotations:
                json_type = python_type_to_json_type(best_annotations[name])
            elif name in param_types_from_docstring:
                json_type = param_types_from_docstring[name]
            else:
                json_type = 'string'
            
            # Get description
            desc = param_descriptions.get(name, '')
            
            # Get default
            default = param.default if param.default != inspect.Parameter.empty else None
            
            params.append(ParameterMeta(
                name=name,
                json_type=json_type,
                description=desc,
                default=default
            ))
    
    return MethodMeta(
        name=method_name,
        description=description,
        params=params
    )

