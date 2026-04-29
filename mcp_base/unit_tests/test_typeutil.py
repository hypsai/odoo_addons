# -*- coding: utf-8 -*-
"""Unit tests for type conversion utilities."""
import sys
import unittest
from typing import List, Dict, Optional, Union, Tuple, Set, Any
from mcp_base.typeutil import python_type_to_json_type, docstring_type_to_json_type, resolve_method_metadata
from typeutil_test_classes import (
    _TestBaseClass,
    _TestChildClass,
    _TestBaseCustomer,
    _TestChildCustomer,
    _TestGrandparent,
    _TestParent,
    _TestChild
)


class TestTypeUtil(unittest.TestCase):
    """Test suite for type conversion utilities"""
    
    def test_python_type_to_json_basic(self):
        """Test basic Python type to JSON Schema conversion."""
        self.assertEqual(python_type_to_json_type(str), "string")
        self.assertEqual(python_type_to_json_type(int), "integer")
        self.assertEqual(python_type_to_json_type(float), "number")
        self.assertEqual(python_type_to_json_type(bool), "boolean")
        self.assertEqual(python_type_to_json_type(bytes), "string")
        self.assertEqual(python_type_to_json_type(type(None)), "null")


    def test_python_type_to_json_generics(self):
        """Test generic Python types to JSON Schema conversion."""
        # List[str]
        result1 = python_type_to_json_type(List[str])
        self.assertEqual(result1, {"type": "array", "items": {"type": "string"}})
        
        # List[int]
        result2 = python_type_to_json_type(List[int])
        self.assertEqual(result2, {"type": "array", "items": {"type": "integer"}})
        
        # Dict[str, int]
        result3 = python_type_to_json_type(Dict[str, int])
        self.assertEqual(result3, {"type": "object"})
        
        # Optional[str] - should extract inner type
        result4 = python_type_to_json_type(Optional[str])
        self.assertEqual(result4, 'string')
        
        # Union[int, str] - should return first non-None type
        result5 = python_type_to_json_type(Union[int, str])
        self.assertEqual(result5, 'integer')
        
        # Tuple[int, str]
        result6 = python_type_to_json_type(Tuple[int, str])
        self.assertEqual(result6["type"], "array")
        
        # Set[str]
        result7 = python_type_to_json_type(Set[str])
        self.assertEqual(result7["type"], "array")
        
        # Optional[List[str]] - nested generic
        result8 = python_type_to_json_type(Optional[List[str]])
        self.assertEqual(result8['type'], 'array')
        self.assertEqual(result8['items']['type'], 'string')


    def test_docstring_type_basic(self):
        """Test basic docstring type to JSON Schema conversion."""
        self.assertEqual(docstring_type_to_json_type('str'), 'string')
        self.assertEqual(docstring_type_to_json_type('int'), 'integer')
        self.assertEqual(docstring_type_to_json_type('float'), 'number')
        self.assertEqual(docstring_type_to_json_type('bool'), 'boolean')
        self.assertEqual(docstring_type_to_json_type('list'), 'array')
        self.assertEqual(docstring_type_to_json_type('dict'), 'object')


    def test_docstring_type_generics(self):
        """Test generic docstring types to JSON Schema conversion."""
        # List[str]
        result1 = docstring_type_to_json_type('List[str]')
        self.assertEqual(result1, {'type': 'array', 'items': {'type': 'string'}})
        
        # Dict[str, int]
        result2 = docstring_type_to_json_type('Dict[str, int]')
        self.assertEqual(result2, {'type': 'object'})
        
        # Optional[str]
        result3 = docstring_type_to_json_type('Optional[str]')
        self.assertEqual(result3, 'string')
        
        # Union[int, str]
        result4 = docstring_type_to_json_type('Union[int, str]')
        self.assertEqual(result4, 'integer')  # Takes first non-None type
        
        # List[Dict[str, Any]]
        result5 = docstring_type_to_json_type('List[Dict[str, Any]]')
        self.assertEqual(result5, {'type': 'array', 'items': {'type': 'object'}})
        
        # Sequence[str]
        result6 = docstring_type_to_json_type('Sequence[str]')
        self.assertEqual(result6, {'type': 'array', 'items': {'type': 'string'}})
        
        # Mapping[str, int]
        result7 = docstring_type_to_json_type('Mapping[str, int]')
        self.assertEqual(result7, {'type': 'object'})


    def test_docstring_type_edge_cases(self):
        """Test edge cases for docstring type conversion."""
        # Empty string
        result1 = docstring_type_to_json_type('')
        self.assertEqual(result1, 'string')
        
        # None/NoneType in Union
        result2 = docstring_type_to_json_type('Union[str, None]')
        self.assertEqual(result2, 'string')
        
        result3 = docstring_type_to_json_type('Union[None, int]')
        self.assertEqual(result3, 'integer')
        
        # Unknown type defaults to string
        result4 = docstring_type_to_json_type('CustomType')
        self.assertEqual(result4, 'string')
        
        # Case insensitivity
        result5 = docstring_type_to_json_type('STRING')
        self.assertEqual(result5, 'string')
        
        result6 = docstring_type_to_json_type('Int')
        self.assertEqual(result6, 'integer')


    def test_resolve_method_metadata_basic(self):
        """Test basic method metadata resolution."""
        meta = resolve_method_metadata(_TestBaseClass.search)
        
        # Check it's a MethodMeta object
        self.assertTrue(hasattr(meta, 'name'))
        self.assertTrue(hasattr(meta, 'description'))
        self.assertTrue(hasattr(meta, 'params'))
        
        self.assertEqual(meta.name, 'search')
        self.assertIsNotNone(meta.description)
        self.assertEqual(len(meta.params), 2)  # name and limit (excluding self)
        
        # Check parameters
        param_names = [p.name for p in meta.params]
        self.assertIn('name', param_names)
        self.assertIn('limit', param_names)
        
        # Find name parameter
        name_param = next(p for p in meta.params if p.name == 'name')
        self.assertEqual(name_param.json_type, 'string')
        
        # Find limit parameter
        limit_param = next(p for p in meta.params if p.name == 'limit')
        self.assertEqual(limit_param.json_type, 'integer')
        self.assertEqual(limit_param.default, 10)


    def test_resolve_method_metadata_inheritance(self):
        """Test metadata resolution with class inheritance."""
        meta = resolve_method_metadata(_TestChildClass.search)
        
        # Should inherit description from base
        self.assertIsNotNone(meta.description)
        self.assertIn('Search customers', meta.description)
        
        # Should inherit parameter types from base
        param_names = [p.name for p in meta.params]
        self.assertIn('name', param_names)
        self.assertIn('limit', param_names)
        
        name_param = next(p for p in meta.params if p.name == 'name')
        self.assertEqual(name_param.json_type, 'string')
        self.assertIn('Customer name', name_param.description)
        
        limit_param = next(p for p in meta.params if p.name == 'limit')
        self.assertEqual(limit_param.json_type, 'integer')
        self.assertEqual(limit_param.default, 10)


    def test_resolve_method_metadata_partial_override(self):
        """Test metadata resolution with partial override."""
        meta = resolve_method_metadata(_TestChildCustomer.create_customer)
        
        # Should use child's description
        self.assertIsNotNone(meta.description)
        self.assertIn('partial', meta.description.lower())
        
        # Should inherit parameter types from base
        param_names = [p.name for p in meta.params]
        self.assertIn('name', param_names)
        self.assertIn('email', param_names)
        
        name_param = next(p for p in meta.params if p.name == 'name')
        self.assertEqual(name_param.json_type, 'string')
        
        email_param = next(p for p in meta.params if p.name == 'email')
        self.assertEqual(email_param.json_type, 'string')


    def test_resolve_method_metadata_multi_level(self):
        """Test metadata resolution with multi-level inheritance."""
        meta = resolve_method_metadata(_TestChild.search)
        
        # Should inherit from grandparent through parent
        self.assertIsNotNone(meta.description)
        self.assertIn('Search customers', meta.description)
        
        param_names = [p.name for p in meta.params]
        self.assertIn('name', param_names)
        
        name_param = next(p for p in meta.params if p.name == 'name')
        self.assertEqual(name_param.json_type, 'string')
        self.assertIn('Customer name', name_param.description)


    def test_method_meta_structure(self):
        """Test MethodMeta and ParameterMeta structure."""
        meta = resolve_method_metadata(_TestBaseClass.search)
        
        # Check MethodMeta attributes
        self.assertIsInstance(meta.name, str)
        self.assertIsInstance(meta.description, str)
        self.assertIsInstance(meta.params, list)
        
        # Check ParameterMeta objects
        for param in meta.params:
            self.assertTrue(hasattr(param, 'name'))
            self.assertTrue(hasattr(param, 'json_type'))
            self.assertTrue(hasattr(param, 'description'))
            self.assertTrue(hasattr(param, 'default'))
            self.assertIsInstance(param.name, str)


if __name__ == '__main__':
    unittest.main()
