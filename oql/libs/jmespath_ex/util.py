# @Time         : 14:46 2026/5/20
# @Author       : Chris
# @Description  :
from typing import List

from ..jmespath import visitor

__all__ = ["extract_fields"]


class FullPathExtractor(visitor.Visitor):
    def __init__(self):
        self.found_paths = set()
        self._prefix_stack = []  # Stack to track array/object prefixes

    def visit(self, node, *args, **kwargs):
        """Visit AST node and extract field paths."""
        node_type = node['type']
        
        if node_type == 'projection':
            self._handle_projection(node)
        elif node_type == 'key_val_pair':
            for child in node.get('children', []):
                self.visit(child)
        elif node_type == 'subexpression':
            path = self._resolve_chain(node)
            if path:
                self._add_with_prefix(path)
        elif node_type == 'field':
            self._add_with_prefix(node['value'])
        else:
            # Recursively check children for other node types
            for child in node.get('children', []):
                self.visit(child)
        
        return self.found_paths
    
    def _handle_projection(self, node):
        """Handle projection node with prefix tracking."""
        array_child = node['children'][0]
        prefix = None
        
        # Extract the array field name from field or flatten node
        if array_child['type'] == 'field':
            prefix = array_child['value']
        elif array_child['type'] == 'flatten' and array_child['children']:
            flatten_child = array_child['children'][0]
            if flatten_child['type'] == 'field':
                prefix = flatten_child['value']
            elif flatten_child['type'] == 'subexpression':
                # For subexpression like rec.order_lines, use the full chain as prefix
                chain = self._resolve_chain(flatten_child)
                if chain:
                    # Only use as prefix if it starts with 'rec.'
                    if chain.startswith('rec.'):
                        prefix = chain
        
        if prefix:
            self._prefix_stack.append(prefix)
        
        # Visit the projection body (second child) with prefix context
        if len(node.get('children', [])) > 1:
            self.visit(node['children'][1])
        
        if prefix:
            self._prefix_stack.pop()
    
    def _add_with_prefix(self, path):
        """Add path with current prefix stack."""
        full_path = ".".join(self._prefix_stack + [path]) if self._prefix_stack else path
        self.found_paths.add(full_path)

    def _resolve_chain(self, node):
        """Reconstruct dot-notation from subexpression/field nodes."""
        parts = []
        for child in node.get('children', []):
            if child['type'] == 'field':
                parts.append(child['value'])
            elif child['type'] == 'subexpression':
                res = self._resolve_chain(child)
                if res:
                    parts.append(res)
        return ".".join(parts) if parts else None


def extract_fields(jmespath):
    """Extract full dot-style field path relative to root object."""
    extractor = FullPathExtractor()
    fields = extractor.visit(jmespath.parsed)
    # Only keep fields that start with 'rec.' and remove the prefix
    return [f[4:] for f in fields if f.startswith('rec.')]
