# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from ..decorators import mcp_tool, python_type_to_json_type
from typing import List, Dict, Optional
import inspect


@tagged("mcp_base")
class TestMCPDecorator(common.TransactionCase):
    """Test MCP decorator functionality"""

    def test_mcp_tool_decorator_basic(self):
        """Test basic @mcp_tool decorator application"""
        
        @mcp_tool(description="Test tool")
        def test_method(self, name: str, age: int = 0):
            return {"name": name, "age": age}
        
        # Check decorator attributes
        self.assertTrue(hasattr(test_method, '_is_mcp_tool'))
        self.assertEqual(test_method._is_mcp_tool, True)
        self.assertEqual(test_method._mcp_desc, "Test tool")
    
    def test_mcp_tool_decorator_auto_description(self):
        """Test auto description from docstring"""
        
        @mcp_tool()
        def test_method_with_doc(self, param: str):
            """This is a test method"""
            return param
        
        self.assertEqual(test_method_with_doc._mcp_desc, "This is a test method")
    
    def test_mcp_tool_schema_generation_string(self):
        """Test schema generation for string parameter"""
        
        @mcp_tool()
        def test_method(self, name: str):
            return name
        
        schema = test_method._mcp_schema
        self.assertEqual(schema['type'], 'object')
        self.assertIn('properties', schema)
        self.assertIn('name', schema['properties'])
        self.assertEqual(schema['properties']['name']['type'], 'string')
        self.assertIn('name', schema['required'])
    
    def test_mcp_tool_schema_generation_integer(self):
        """Test schema generation for integer parameter"""
        
        @mcp_tool()
        def test_method(self, count: int):
            return count
        
        schema = test_method._mcp_schema
        self.assertEqual(schema['properties']['count']['type'], 'integer')
    
    def test_mcp_tool_schema_generation_float(self):
        """Test schema generation for float parameter"""
        
        @mcp_tool()
        def test_method(self, price: float):
            return price
        
        schema = test_method._mcp_schema
        self.assertEqual(schema['properties']['price']['type'], 'number')
    
    def test_mcp_tool_schema_generation_boolean(self):
        """Test schema generation for boolean parameter"""
        
        @mcp_tool()
        def test_method(self, active: bool):
            return active
        
        schema = test_method._mcp_schema
        self.assertEqual(schema['properties']['active']['type'], 'boolean')
    
    def test_mcp_tool_schema_generation_list(self):
        """Test schema generation for list parameter"""
        
        @mcp_tool()
        def test_method(self, items: List[str]):
            return items
        
        schema = test_method._mcp_schema
        prop = schema['properties']['items']
        self.assertEqual(prop['type'], 'array')
        self.assertEqual(prop['items']['type'], 'string')
    
    def test_mcp_tool_schema_generation_dict(self):
        """Test schema generation for dict parameter"""
        
        @mcp_tool()
        def test_method(self, data: Dict):
            return data
        
        schema = test_method._mcp_schema
        self.assertEqual(schema['properties']['data']['type'], 'object')
    
    def test_mcp_tool_schema_optional_parameter(self):
        """Test schema generation for optional parameter with default"""
        
        @mcp_tool()
        def test_method(self, name: str, age: int = 0):
            return {"name": name, "age": age}
        
        schema = test_method._mcp_schema
        self.assertIn('name', schema['required'])
        self.assertNotIn('age', schema['required'])
        self.assertEqual(schema['properties']['age']['default'], 0)
    
    def test_mcp_tool_schema_multiple_parameters(self):
        """Test schema generation with multiple parameters"""
        
        @mcp_tool()
        def test_method(self, name: str, age: int, active: bool = True):
            return {"name": name, "age": age, "active": active}
        
        schema = test_method._mcp_schema
        self.assertEqual(len(schema['properties']), 3)
        self.assertIn('name', schema['required'])
        self.assertIn('age', schema['required'])
        self.assertNotIn('active', schema['required'])
    
    def test_python_type_to_json_type_mapping(self):
        """Test Python to JSON type conversion"""
        
        self.assertEqual(python_type_to_json_type(str), "string")
        self.assertEqual(python_type_to_json_type(int), "integer")
        self.assertEqual(python_type_to_json_type(float), "number")
        self.assertEqual(python_type_to_json_type(bool), "boolean")
        self.assertEqual(python_type_to_json_type(bytes), "string")
    
    def test_python_type_to_json_type_list(self):
        """Test Python list type conversion"""
        from typing import List
        
        result = python_type_to_json_type(List[str])
        self.assertEqual(result['type'], 'array')
        self.assertEqual(result['items']['type'], 'string')
    
    def test_python_type_to_json_type_empty_annotation(self):
        """Test type conversion with empty annotation"""
        
        result = python_type_to_json_type(inspect.Parameter.empty)
        self.assertEqual(result, "string")
