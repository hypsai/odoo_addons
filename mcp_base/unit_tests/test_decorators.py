import inspect
import unittest

from mcp_base.decorators import mcp_tool
from mcp_base.typeutil import python_type_to_json_type


class TestDecorators(unittest.TestCase):
    """Test suite for MCP decorators"""
    
    def test_mcp_tool_decorator_basic(self):
        """Test basic @mcp_tool decorator application"""
        
        @mcp_tool(description="Test tool")
        def test_method(self, name: str, age: int = 0):
            return {"name": name, "age": age}
        
        # Check decorator sets the flag
        self.assertTrue(hasattr(test_method, '_is_mcp_tool'))
        self.assertEqual(test_method._is_mcp_tool, True)
        
        # Check decorator stores parameters for controller
        self.assertTrue(hasattr(test_method, '_mcp_custom_description'))
        # When using @mcp_tool(description="..."), description parameter is used
        self.assertEqual(test_method._mcp_custom_description, "Test tool")
        self.assertTrue(hasattr(test_method, '_mcp_inherit_docs'))
        self.assertEqual(test_method._mcp_inherit_docs, True)

    def test_mcp_tool_decorator_with_positional_arg(self):
        """Test @mcp_tool with positional description argument"""
        
        @mcp_tool("Custom description")
        def test_method(self, param: str):
            return param
        
        # Positional arg becomes _func_or_desc, then assigned to description
        self.assertEqual(test_method._mcp_custom_description, "Custom description")

    def test_mcp_tool_decorator_without_parentheses(self):
        """Test @mcp_tool without parentheses"""
        
        @mcp_tool
        def test_method(self, param: str):
            return param
        
        self.assertTrue(test_method._is_mcp_tool)
        # When used without parentheses, description stays None
        self.assertIsNone(test_method._mcp_custom_description)

    def test_mcp_tool_decorator_inherit_docs_false(self):
        """Test @mcp_tool with inherit_docs=False"""
        
        @mcp_tool(inherit_docs=False)
        def test_method(self, param: str):
            return param
        
        self.assertEqual(test_method._mcp_inherit_docs, False)

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


if __name__ == '__main__':
    unittest.main()
