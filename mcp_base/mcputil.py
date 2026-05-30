# @Time         : 11:53 2026/4/29
# @Author       : Chris
# @Description  : MCP Utility Functions
import inspect

from .typeutil import resolve_method_metadata, OdooMro


def build_tool_info(mro: OdooMro, custom_desc: str = None, inherit_docs: bool = True):
    """Build complete tool information from a method.
    
    This function handles metadata resolution and JSON Schema generation.
    It's called by the controller at runtime when tools/list is requested.
    
    Args:
        mro: The method mro to analyze
        custom_desc: Custom description (overrides docstring)
        inherit_docs: Whether to inherit docs from parent classes
        
    Returns:
        dict: Tool information with name, description, and inputSchema
    """
    # Resolve metadata
    meta = resolve_method_metadata(mro, inherit=inherit_docs)
    
    # Use custom description if provided, otherwise use resolved description
    tool_description = custom_desc or meta.description or "Odoo Tool"
    
    # Build JSON Schema from resolved metadata
    properties = {}
    required = []
    
    for param in meta.params:
        # Skip *args/**kwargs in schema
        if param.name.startswith('*'):
            continue
        
        # Build property schema
        prop_schema = param.json_type if isinstance(param.json_type, dict) else {"type": param.json_type}
        
        # Add description if available
        if param.description:
            prop_schema["description"] = param.description
        
        # Add default value if present
        if param.default != inspect.Parameter.empty:
            prop_schema["default"] = param.default
        else:
            required.append(param.name)
        
        properties[param.name] = prop_schema
    
    schema = {
        "type": "object",
        "properties": properties,
        "required": required
    }
    
    return {
        "description": tool_description,
        "inputSchema": schema
    }
