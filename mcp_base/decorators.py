# -*- coding: utf-8 -*-
# @Time         : 10:26 2026/4/24
# @Author       : Chris
# @Description  : MCP Tool Decorator


def mcp_tool(_func_or_desc=None, description=None, inherit_docs=True):
    """Decorator to mark Odoo methods as MCP tools.
    
    Usage:
        @mcp_tool
        def search(self, name: str): ...
        
        @mcp_tool("Custom description")
        def search(self, name: str): ...
        
        @mcp_tool(description="Custom", inherit_docs=False)
        def search(self, name: str): ...
    
    Args:
        _func_or_desc: Function or custom description string
        description: Custom tool description (overrides docstring)
        inherit_docs: Inherit missing docs from parent classes (default: True)
    
    Note:
        Metadata resolution and schema generation are handled by the controller
        at runtime. This decorator only marks the method with _is_mcp_tool flag
        and stores configuration for later use.
    """
    # Detect usage style
    if callable(_func_or_desc):
        func = _func_or_desc
    else:  # str
        func = None
        description = _func_or_desc
    
    def decorator(f):
        f._is_mcp_tool = True
        f._mcp_custom_description = description
        f._mcp_inherit_docs = inherit_docs
        return f
    
    if func is not None:
        return decorator(func)
    else:
        return decorator
