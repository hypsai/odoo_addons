# -*- coding: utf-8 -*-
# @Time         : 14:46 2026/5/20
# @Author       : Chris
# @Description  :
from jmespath import visitor

__all__ = ["extract_fields"]


class FullPathExtractor(visitor.Visitor):
    def __init__(self):
        self.found_paths = set()

    def visit(self, node, *args, **kwargs):
        # A subexpression is a chain like 'partner_id.name'
        if node['type'] == 'subexpression':
            path = self._resolve_chain(node)
            if path:
                self.found_paths.add(path)

        # A field is a standalone path like 'name'
        elif node['type'] == 'field':
            self.found_paths.add(node['value'])

        # Recursively check children for other expressions (like inside {key: path})
        for child in node.get('children', []):
            self.visit(child)
        return self.found_paths

    def _resolve_chain(self, node):
        """Recursively reconstructs dot-notation from subexpression/field nodes."""
        parts = []
        for child in node.get('children', []):
            if child['type'] == 'field':
                parts.append(child['value'])
            elif child['type'] == 'subexpression':
                res = self._resolve_chain(child)
                if res: parts.append(res)
        return ".".join(parts) if parts else None


def extract_fields(jmespath):
    """Extract full dot-style field path relative to root object."""
    extractor = FullPathExtractor()
    paths = extractor.visit(jmespath.parsed)
    return paths
