# -*- coding: utf-8 -*-
# @Time         : 15:00 2026/5/20
# @Author       : Chris
# @Description  :
import jinja2
from jinja2 import nodes

__all__ = ["extract_fields"]


def extract_fields(template_str):
    """
    Extract full dot-style field paths relative to the root object
    from a Jinja2 template string.
    """
    env = jinja2.Environment()
    try:
        ast = env.parse(template_str)
    except jinja2.TemplateSyntaxError:
        return []

    found_paths = set()
    loop_context = {}  # Track loop variables: {loop_var: iterable_path}

    def _reconstruct(node):
        """Recursively build the path string (e.g., 'partner_id.name')."""
        if isinstance(node, nodes.Name):
            name = node.name
            # Check if this is a loop variable
            if name in loop_context:
                return loop_context[name]
            return name
        if isinstance(node, nodes.Getattr):
            base = _reconstruct(node.node)
            if base:
                return f"{base}.{node.attr}"
        return None

    def _extract_iterable_path(node):
        """Extract the path from the iterable expression in a for loop."""
        if isinstance(node, nodes.Getattr):
            return _reconstruct(node)
        elif isinstance(node, nodes.Name):
            return node.name
        return None

    def _visit_node(node):
        """Recursively visit nodes and track loop contexts."""
        # Handle For loops
        if isinstance(node, nodes.For):
            # Extract the iterable path (e.g., 'rec.order_lines')
            iterable_path = _extract_iterable_path(node.iter)
            
            if iterable_path:
                # Clean up root prefix
                parts = iterable_path.split('.')
                if parts[0] in ('record', 'rec', 'obj'):
                    parts = parts[1:]
                
                if parts:
                    # Store the loop variable context
                    old_value = loop_context.get(node.target.name)
                    loop_context[node.target.name] = ".".join(parts)
                    
                    # Visit the loop body
                    for child in node.body:
                        _visit_node(child)
                    
                    # Restore old context
                    if old_value is not None:
                        loop_context[node.target.name] = old_value
                    else:
                        del loop_context[node.target.name]
                    return
        
        # Handle attribute access and names
        if isinstance(node, (nodes.Getattr, nodes.Name)):
            path = _reconstruct(node)
            if path:
                # Clean up the path by removing internal wrapper prefixes
                parts = path.split('.')
                if parts[0] in ('record', 'rec', 'obj'):
                    parts = parts[1:]
                
                if parts:
                    found_paths.add(".".join(parts))
        
        # Recursively visit children
        for child_node in node.iter_child_nodes():
            _visit_node(child_node)

    _visit_node(ast)
    return list(found_paths)
