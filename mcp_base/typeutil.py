# -*- coding: utf-8 -*-
# @Time         : 23:27 2026/4/25
# @Author       : Chris
# @Description  : Type conversion utilities for MCP framework.
import inspect
import re

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


def resolve_method_metadata(func, method_name=None, cls=None):
    """Recursively resolve method metadata from the method and its base classes.
    
    When a method overrides a base class method but lacks complete annotations or
    docstrings, this function recursively searches up the inheritance chain to
    gather missing information.
    
    For each parameter, if information (annotation or description) is missing in
    the current method, it searches parent classes until all information is found
    or there are no more base classes.
    
    Args:
        func: The method function to resolve metadata for
        method_name: Optional method name. If not provided, uses func.__name__
        cls: Optional class object. If not provided, tries to extract from func.
            Provide this when func is defined in a local scope (e.g., in tests).
        
    Returns:
        dict: Complete metadata including:
            - 'docstring': The best available docstring
            - 'annotations': Dict of parameter annotations
            - 'signature': The method signature
    
    Example:
        class Base:
            def search(self, name: str):
                '''Search by name.
                :param name: Customer name
                '''
                pass
        
        class Child(Base):
            def search(self):  # No annotation or docstring
                pass
        
        # resolve_method_metadata(Child.search) will find Base.search's metadata
        # Or explicitly: resolve_method_metadata(Child.search, cls=Child)
    """
    if method_name is None:
        method_name = func.__name__
    
    # Try to get the class from __objclass__ (for bound methods)
    if cls is None:
        cls = getattr(func, '__objclass__', None)
    
    if cls is None:
        # Not a bound method, try to find it via __qualname__
        qualname = getattr(func, '__qualname__', '')
        if '.' in qualname:
            # Try to extract class and module info
            parts = qualname.rsplit('.', 1)
            if len(parts) == 2:
                class_name = parts[0]
                # Try to get class from function's globals
                func_globals = getattr(func, '__globals__', {})
                cls = func_globals.get(class_name)
                
                # If not found in globals, try module
                if cls is None:
                    module = inspect.getmodule(func)
                    if module:
                        cls = getattr(module, class_name, None)
    
    if cls is not None:
        return _resolve_from_class_hierarchy(cls, method_name)
    else:
        # Fallback: just use the function as-is
        return {
            'docstring': inspect.getdoc(func),
            'annotations': getattr(func, '__annotations__', {}),
            'signature': inspect.signature(func)
        }


def _resolve_from_class_hierarchy(cls, method_name):
    """Resolve method metadata by walking up the class hierarchy.
    
    Args:
        cls: The class to start searching from
        method_name: Name of the method to find
        
    Returns:
        dict: Complete metadata with merged information from class hierarchy
    """
    # Collect all methods with this name from the class hierarchy
    methods_in_hierarchy = []
    for klass in cls.__mro__:  # Method Resolution Order includes the class itself
        if hasattr(klass, method_name):
            method = getattr(klass, method_name)
            if callable(method) and not isinstance(method, type):
                methods_in_hierarchy.append((klass, method))
    
    if not methods_in_hierarchy:
        # Method not found in hierarchy
        return {
            'docstring': '',
            'annotations': {},
            'signature': None
        }
    
    # Start with the first (most derived) method
    primary_cls, primary_method = methods_in_hierarchy[0]
    
    # Get initial metadata from the primary method
    best_docstring = inspect.getdoc(primary_method)
    best_annotations = dict(getattr(primary_method, '__annotations__', {}))
    
    # Merge annotations and docstrings from parent classes
    for klass, method in methods_in_hierarchy[1:]:
        # Merge annotations - only fill in missing ones
        parent_annotations = getattr(method, '__annotations__', {})
        for param_name, param_type in parent_annotations.items():
            if param_name not in best_annotations:
                best_annotations[param_name] = param_type
        
        # Use parent docstring if current one is missing
        if not best_docstring:
            parent_docstring = inspect.getdoc(method)
            if parent_docstring:
                best_docstring = parent_docstring
    
    # Get signature from the primary method
    try:
        signature = inspect.signature(primary_method)
    except (ValueError, TypeError):
        signature = None
    
    return {
        'docstring': best_docstring,
        'annotations': best_annotations,
        'signature': signature
    }
