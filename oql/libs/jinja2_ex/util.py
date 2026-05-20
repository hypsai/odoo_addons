# -*- coding: utf-8 -*-
# @Time         : 15:00 2026/5/20
# @Author       : Chris
# @Description  :
import jinja2
from jinja2 import nodes

__all__ = ["extract_fields"]

_ROOT_PREFIXES = frozenset(('record', 'rec', 'obj'))


def _strip_root(path):
    """Remove root object prefix from path."""
    parts = path.split('.')
    if parts and parts[0] in _ROOT_PREFIXES:
        return '.'.join(parts[1:])
    return path


def extract_fields(template_str):
    """
    Extract full dot-style field paths relative to the root object
    from a Jinja2 template string.
    """
    try:
        ast = jinja2.Environment().parse(template_str)
    except jinja2.TemplateSyntaxError:
        return []

    found_paths = set()
    loop_context = {}  # {loop_var: iterable_path}

    def _reconstruct(node):
        """Build path string from AST node."""
        if isinstance(node, nodes.Name):
            return loop_context.get(node.name, node.name)
        if isinstance(node, nodes.Getattr):
            base = _reconstruct(node.node)
            return f"{base}.{node.attr}" if base else None
        return None

    def _visit(node):
        """Recursively visit nodes and track loop contexts."""
        if isinstance(node, nodes.For):
            # Process for loop: {% for var in iterable %}
            iter_path = _reconstruct(node.iter)
            if iter_path:
                clean_path = _strip_root(iter_path)
                if clean_path:
                    old_ctx = loop_context.get(node.target.name)
                    loop_context[node.target.name] = clean_path
                    
                    for child in node.body:
                        _visit(child)
                    
                    # Restore context
                    if old_ctx is not None:
                        loop_context[node.target.name] = old_ctx
                    else:
                        del loop_context[node.target.name]
                    return
        
        # Extract field paths
        if isinstance(node, (nodes.Getattr, nodes.Name)):
            path = _reconstruct(node)
            if path:
                clean_path = _strip_root(path)
                if clean_path:
                    found_paths.add(clean_path)
        
        # Visit children
        for child in node.iter_child_nodes():
            _visit(child)

    _visit(ast)
    return list(found_paths)
