# -*- coding: utf-8 -*-
# @Time         : 14:46 2026/5/20
# @Author       : Chris
# @Description  :
from jmespath import visitor

__all__ = ["extract_fields"]


class FullPathExtractor(visitor.Visitor):
    def __init__(self):
        self.found_paths = set()
        self._prefix_stack = []  # Stack to track array/object prefixes

    def visit(self, node, *args, **kwargs):
        """Visit AST node and extract field paths."""
        node_type = node['type']
        
        # Handle projection nodes (array projections like order_lines[].field)
        if node_type == 'projection':
            self._handle_projection(node)
            return self.found_paths
        
        # Handle key_val_pair nodes (inside multi_select_dict)
        if node_type == 'key_val_pair':
            for child in node.get('children', []):
                self.visit(child)
            return self.found_paths
        
        # Extract subexpression chains
        if node_type == 'subexpression':
            path = self._resolve_chain(node)
            if path:
                self._add_with_prefix(path)
        
        # Extract field names
        elif node_type == 'field':
            self._add_with_prefix(node['value'])

        # Recursively check children
        for child in node.get('children', []):
            self.visit(child)
        return self.found_paths
    
    def _handle_projection(self, node):
        """Handle projection node with prefix tracking."""
        array_child = node['children'][0]
        prefix_added = False
        
        # Extract the array field name from field or flatten node
        if array_child['type'] == 'field':
            self._prefix_stack.append(array_child['value'])
            prefix_added = True
        elif array_child['type'] == 'flatten' and array_child['children']:
            flatten_child = array_child['children'][0]
            if flatten_child['type'] == 'field':
                self._prefix_stack.append(flatten_child['value'])
                prefix_added = True
        
        # Visit all children with the prefix context
        for child in node.get('children', []):
            self.visit(child)
        
        # Pop the prefix after processing
        if prefix_added:
            self._prefix_stack.pop()
    
    def _add_with_prefix(self, path):
        """Add path with current prefix stack."""
        if self._prefix_stack:
            full_path = ".".join(self._prefix_stack) + "." + path
            self.found_paths.add(full_path)
        else:
            self.found_paths.add(path)

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
    return extractor.visit(jmespath.parsed)
