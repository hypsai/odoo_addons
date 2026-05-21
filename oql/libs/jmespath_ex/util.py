# -*- coding: utf-8 -*-
# @Time         : 14:46 2026/5/20
# @Author       : Chris
# @Description  :
from typing import List

from jmespath import visitor

__all__ = ["extract_fields"]


class FullPathExtractor(visitor.Visitor):
    def __init__(self):
        self.found_paths = set()
        self._prefix_stack = []  # Stack to track array/object prefixes
        self._in_projection_body = False  # Flag to indicate we're in projection body

    def visit(self, node, *args, **kwargs):
        """Visit AST node and extract field paths."""
        node_type = node['type']
        
        # Handle projection nodes (array projections like order_lines[].field)
        if node_type == 'projection':
            self._handle_projection(node)
            return self.found_paths
        
        # Handle key_val_pair nodes (inside multi_select_dict)
        elif node_type == 'key_val_pair':
            # In projection body, extract fields but don't let them be processed again
            for child in node.get('children', []):
                self.visit(child)
            return self.found_paths
        
        # Extract subexpression chains
        elif node_type == 'subexpression':
            path = self._resolve_chain(node)
            if path:
                self._add_with_prefix(path)
            # Don't recurse into children of subexpression to avoid duplicate partial paths
            return self.found_paths
        
        # Extract field names
        elif node_type == 'field':
            self._add_with_prefix(node['value'])

        # Recursively check children (only for non-subexpression nodes)
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
            elif flatten_child['type'] == 'subexpression':
                # For subexpression like rec.order_lines, get the full chain without 'rec' prefix
                chain = self._resolve_chain(flatten_child)
                if chain:
                    # Remove 'rec.' prefix if present (e.g., 'rec.order_lines' -> 'order_lines')
                    if chain.startswith('rec.'):
                        chain = chain[4:]
                    # Use the chain as prefix
                    self._prefix_stack.append(chain)
                    prefix_added = True
        
        # Visit the projection body (second child) with prefix context
        if len(node.get('children', [])) > 1:
            old_flag = self._in_projection_body
            self._in_projection_body = True
            self.visit(node['children'][1])
            self._in_projection_body = old_flag
        
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
    fields: List[str] = extractor.visit(jmespath.parsed)
    # Remove 'rec.' prefix from fields that start with it
    prefix = "rec."
    fields = [x[len(prefix):] if x.startswith(prefix) else x for x in fields]
    return fields
