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
        # Handle projection nodes (array projections like order_lines[].field)
        if node['type'] == 'projection':
            # First child can be a field or flatten node
            array_child = node['children'][0]
            prefix_added = False
            
            # Extract the array field name
            if array_child['type'] == 'field':
                # Direct field reference
                self._prefix_stack.append(array_child['value'])
                prefix_added = True
            elif array_child['type'] == 'flatten':
                # Flatten node contains the actual field
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
            return self.found_paths
        
        # Handle key_val_pair nodes (inside multi_select_dict)
        # key_val_pair has structure: {type: 'key_val_pair', value: 'key_name', children: [expression_node]}
        # We need to visit the child expression to extract fields from it
        if node['type'] == 'key_val_pair':
            # Visit the child expression (the value part of key: value)
            for child in node.get('children', []):
                self.visit(child)
            return self.found_paths
        
        # A subexpression is a chain like 'partner_id.name'
        if node['type'] == 'subexpression':
            path = self._resolve_chain(node)
            if path:
                # Add current prefix if exists
                if self._prefix_stack:
                    full_path = ".".join(self._prefix_stack) + "." + path
                    self.found_paths.add(full_path)
                else:
                    self.found_paths.add(path)

        # A field is a standalone path like 'name'
        elif node['type'] == 'field':
            field_name = node['value']
            # Add current prefix if exists
            if self._prefix_stack:
                full_path = ".".join(self._prefix_stack) + "." + field_name
                self.found_paths.add(full_path)
            else:
                self.found_paths.add(field_name)

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
