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

    def _reconstruct(node):
        """Recursively build the path string (e.g., 'partner_id.name')."""
        if isinstance(node, nodes.Name):
            return node.name
        if isinstance(node, nodes.Getattr):
            base = _reconstruct(node.node)
            if base:
                return f"{base}.{node.attr}"
        return None

    # Find all attribute access and standalone names
    for node in ast.find_all((nodes.Getattr, nodes.Name)):
        path = _reconstruct(node)
        if path:
            # Clean up the path by removing internal wrapper prefixes
            # For example: 'record.partner_id.name' -> 'partner_id.name'
            parts = path.split('.')
            if parts[0] in ('record', 'rec', 'obj'):
                parts = parts[1:]

            if parts:
                found_paths.add(".".join(parts))

    return list(found_paths)
