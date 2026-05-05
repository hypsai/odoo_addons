# -*- coding: utf-8 -*-
import unittest
from typing import List, Dict

from mcp_base.decorators import mcp_tool
from mcp_base.mcputil import build_tool_info
from mcp_base.typeutil import OdooMro


class TestMcputil(unittest.TestCase):
    """Test suite for MCP utility functions"""
    
    def test_build_tool_info_basic(self):
        """Test build_tool_info with basic method"""
        
        class TestClass:
            @mcp_tool(description="Test method")
            def test_method(self, name: str, age: int = 0):
                """Test method docstring"""
                return {"name": name, "age": age}
        
        # Need to pass custom_desc because mcputil doesn't auto-read from method
        mro = OdooMro(method='test_method', classes=[TestClass])
        tool_info = build_tool_info(mro, custom_desc="Test method")
        
        self.assertIn('description', tool_info)
        self.assertIn('inputSchema', tool_info)
        self.assertEqual(tool_info['description'], "Test method")

    def test_build_tool_info_auto_description(self):
        """Test build_tool_info extracts description from docstring"""
        
        class TestClass:
            @mcp_tool()
            def test_method(self, param: str):
                """Auto extracted description"""
                return param
        
        mro = OdooMro(method='test_method', classes=[TestClass])
        tool_info = build_tool_info(mro)
        self.assertEqual(tool_info['description'], "Auto extracted description")

    def test_build_tool_info_schema_string(self):
        """Test schema generation for string parameter"""
        
        class TestClass:
            @mcp_tool()
            def test_method(self, name: str):
                return name
        
        mro = OdooMro(method='test_method', classes=[TestClass])
        tool_info = build_tool_info(mro)
        schema = tool_info['inputSchema']
        
        self.assertEqual(schema['type'], 'object')
        self.assertIn('name', schema['properties'])
        self.assertEqual(schema['properties']['name']['type'], 'string')
        self.assertIn('name', schema['required'])

    def test_build_tool_info_schema_integer(self):
        """Test schema generation for integer parameter"""
        
        class TestClass:
            @mcp_tool()
            def test_method(self, count: int):
                return count
        
        mro = OdooMro(method='test_method', classes=[TestClass])
        tool_info = build_tool_info(mro)
        self.assertEqual(tool_info['inputSchema']['properties']['count']['type'], 'integer')

    def test_build_tool_info_schema_float(self):
        """Test schema generation for float parameter"""
        
        class TestClass:
            @mcp_tool()
            def test_method(self, price: float):
                return price
        
        mro = OdooMro(method='test_method', classes=[TestClass])
        tool_info = build_tool_info(mro)
        self.assertEqual(tool_info['inputSchema']['properties']['price']['type'], 'number')

    def test_build_tool_info_schema_boolean(self):
        """Test schema generation for boolean parameter"""
        
        class TestClass:
            @mcp_tool()
            def test_method(self, active: bool):
                return active
        
        mro = OdooMro(method='test_method', classes=[TestClass])
        tool_info = build_tool_info(mro)
        self.assertEqual(tool_info['inputSchema']['properties']['active']['type'], 'boolean')

    def test_build_tool_info_schema_list(self):
        """Test schema generation for list parameter"""
        
        class TestClass:
            @mcp_tool()
            def test_method(self, items: List[str]):
                return items
        
        mro = OdooMro(method='test_method', classes=[TestClass])
        tool_info = build_tool_info(mro)
        prop = tool_info['inputSchema']['properties']['items']
        self.assertEqual(prop['type'], 'array')
        self.assertEqual(prop['items']['type'], 'string')

    def test_build_tool_info_schema_dict(self):
        """Test schema generation for dict parameter"""
        
        class TestClass:
            @mcp_tool()
            def test_method(self, data: Dict):
                return data
        
        mro = OdooMro(method='test_method', classes=[TestClass])
        tool_info = build_tool_info(mro)
        self.assertEqual(tool_info['inputSchema']['properties']['data']['type'], 'object')

    def test_build_tool_info_optional_parameter(self):
        """Test schema generation for optional parameter with default"""
        
        class TestClass:
            @mcp_tool()
            def test_method(self, name: str, age: int = 0):
                return {"name": name, "age": age}
        
        mro = OdooMro(method='test_method', classes=[TestClass])
        tool_info = build_tool_info(mro)
        schema = tool_info['inputSchema']
        
        self.assertIn('name', schema['required'])
        self.assertNotIn('age', schema['required'])
        self.assertEqual(schema['properties']['age']['default'], 0)

    def test_build_tool_info_multiple_parameters(self):
        """Test schema generation with multiple parameters"""
        
        class TestClass:
            @mcp_tool()
            def test_method(self, name: str, age: int, active: bool = True):
                return {"name": name, "age": age, "active": active}
        
        mro = OdooMro(method='test_method', classes=[TestClass])
        tool_info = build_tool_info(mro)
        schema = tool_info['inputSchema']
        
        self.assertEqual(len(schema['properties']), 3)
        self.assertIn('name', schema['required'])
        self.assertIn('age', schema['required'])
        self.assertNotIn('active', schema['required'])

    def test_build_tool_info_with_custom_description(self):
        """Test build_tool_info uses custom description"""
        
        class TestClass:
            @mcp_tool()
            def test_method(self, param: str):
                """Docstring description"""
                return param
        
        mro = OdooMro(method='test_method', classes=[TestClass])
        # Override with custom description
        tool_info = build_tool_info(mro, custom_desc="Custom override")
        self.assertEqual(tool_info['description'], "Custom override")

    def test_build_tool_info_inherit_docs_false(self):
        """Test build_tool_info with inherit_docs=False"""
        
        class BaseClass:
            def base_method(self, param: str):
                """Base docstring"""
                pass
        
        class ChildClass(BaseClass):
            @mcp_tool(inherit_docs=False)
            def child_method(self, param: str):
                """Child docstring"""
                pass
        
        mro = OdooMro(method='child_method', classes=[ChildClass])
        tool_info = build_tool_info(mro, inherit_docs=False)
        
        # Should use child's docstring, not inherit from base
        self.assertEqual(tool_info['description'], "Child docstring")


if __name__ == '__main__':
    unittest.main()
