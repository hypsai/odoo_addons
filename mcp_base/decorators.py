# -*- coding: utf-8 -*-
# @Time         : 10:26 2026/4/24
# @Author       : Chris
# @Description  :
import inspect
from .typeutil import python_type_to_json_type, resolve_method_metadata
from .docstring import parse_docstring


def mcp_tool(_func_or_desc=None, description=None):
    """Decorator to expose Odoo methods as MCP tools.
    
    Supports multiple usage styles:
    - @mcp_tool (without parentheses)
    - @mcp_tool() (with empty parentheses)
    - @mcp_tool("Custom description") (positional argument)
    - @mcp_tool(description="Custom description") (keyword argument)
    
    Automatically generates JSON Schema from Python type hints and docstrings.
    Parameter descriptions are extracted from docstrings, while types come from
    type annotations. This minimizes developer effort - you only need to write
    parameter descriptions in docstrings, types are inferred automatically.
    
    Tool description priority:
    1. Explicit description parameter (for overriding complex docstrings)
    2. Extracted from docstring (removes param sections, token-efficient)
    3. Default "Odoo Tool"
    
    Examples:
        # Style 1: Without parentheses (most common)
        @mcp_tool
        def search(self, name: str, limit: int = 10):
            '''Search by name.
            
            :param name: Customer name to search
            :param limit: Maximum results (optional)
            '''
            pass
        
        # Style 2: With positional argument
        @mcp_tool("Advanced customer search")
        def advanced_search(self, query: str):
            '''Advanced search with filters.
            
            :param query: Search query string
            '''
            pass
        
        # Style 3: With keyword argument
        @mcp_tool(description="Another custom description")
        def another_method(self, data: str):
            '''Method with keyword arg.
            
            :param data: Data parameter
            '''
            pass
    
    Args:
        _func_or_desc: Internal parameter - can be either a function (when used
                      as @mcp_tool) or a description string (when used as
                      @mcp_tool("desc")). Don't use directly.
        description: Optional tool description. Can also be passed as first
                    positional argument. If not provided, intelligently extracts
                    description from docstring.
    """
    # Detect usage style and normalize parameters
    if callable(_func_or_desc):
        # Called as @mcp_tool (without parentheses)
        func = _func_or_desc
        custom_description = description
    else:
        # Called as @mcp_tool() or @mcp_tool("desc") or @mcp_tool(description="desc")
        func = None
        # Priority: keyword arg > positional arg
        custom_description = description if description is not None else _func_or_desc
    
    def decorator(func):
        func._is_mcp_tool = True

        # Resolve method metadata recursively from class hierarchy
        metadata = resolve_method_metadata(func)
        
        # Use resolved docstring and annotations
        docstring = metadata['docstring']
        resolved_annotations = metadata['annotations']
        
        # Parse docstring and extract metadata
        parsed = parse_docstring(docstring)

        # Set tool description with priority: custom > docstring > default
        func._mcp_desc = custom_description or parsed.get('description') or "Odoo Tool"

        # Build JSON Schema from signature and docstring
        sig = metadata['signature'] or inspect.signature(func)
        param_descriptions = parsed['params']
        param_types_from_docstring = parsed.get('param_types', {})
        
        properties = {}
        required = []

        for name, param in sig.parameters.items():
            if name == 'self':
                continue

            # Determine parameter type with priority: type hint > resolved annotation > docstring :type: > default
            if param.annotation != inspect.Parameter.empty:
                json_type = python_type_to_json_type(param.annotation)
            elif name in resolved_annotations:
                json_type = python_type_to_json_type(resolved_annotations[name])
            elif name in param_types_from_docstring:
                json_type = param_types_from_docstring[name]
            else:
                json_type = 'string'
            
            # Build property schema
            prop_schema = json_type if isinstance(json_type, dict) else {"type": json_type}
            
            # Add description if available
            if name in param_descriptions:
                prop_schema["description"] = param_descriptions[name]
            
            # Add default value if present
            if param.default != inspect.Parameter.empty:
                prop_schema["default"] = param.default
            else:
                required.append(name)
            
            properties[name] = prop_schema

        func._mcp_schema = {
            "type": "object",
            "properties": properties,
            "required": required
        }
        return func
    
    # If func is already detected (called as @mcp_tool), apply decorator immediately
    if func is not None:
        return decorator(func)
    else:
        # Otherwise return the decorator for later application
        return decorator
