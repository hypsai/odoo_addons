# -*- coding: utf-8 -*-
import inspect

from mcp_base.decorators import mcp_tool
from mcp_base.typeutil import python_type_to_json_type


def test_mcp_tool_decorator_basic():
    """Test basic @mcp_tool decorator application"""
    
    @mcp_tool(description="Test tool")
    def test_method(self, name: str, age: int = 0):
        return {"name": name, "age": age}
    
    # Check decorator sets the flag
    assert hasattr(test_method, '_is_mcp_tool')
    assert test_method._is_mcp_tool == True
    
    # Check decorator stores parameters for controller
    assert hasattr(test_method, '_mcp_custom_description')
    assert test_method._mcp_custom_description == "Test tool"
    assert hasattr(test_method, '_mcp_inherit_docs')
    assert test_method._mcp_inherit_docs == True

def test_mcp_tool_decorator_with_positional_arg():
    """Test @mcp_tool with positional description argument"""
    
    @mcp_tool("Custom description")
    def test_method(self, param: str):
        return param
    
    assert test_method._mcp_custom_description == "Custom description"

def test_mcp_tool_decorator_without_parentheses():
    """Test @mcp_tool without parentheses"""
    
    @mcp_tool
    def test_method(self, param: str):
        return param
    
    assert test_method._is_mcp_tool
    # When used without parentheses, _func_or_desc is the function itself
    # So _mcp_custom_description will be set to the function
    assert callable(test_method._mcp_custom_description)

def test_mcp_tool_decorator_inherit_docs_false():
    """Test @mcp_tool with inherit_docs=False"""
    
    @mcp_tool(inherit_docs=False)
    def test_method(self, param: str):
        return param
    
    assert test_method._mcp_inherit_docs == False

def test_python_type_to_json_type_mapping():
    """Test Python to JSON type conversion"""
    
    assert python_type_to_json_type(str) == "string"
    assert python_type_to_json_type(int) == "integer"
    assert python_type_to_json_type(float) == "number"
    assert python_type_to_json_type(bool) == "boolean"
    assert python_type_to_json_type(bytes) == "string"

def test_python_type_to_json_type_list():
    """Test Python list type conversion"""
    from typing import List
    
    result = python_type_to_json_type(List[str])
    assert result['type'] == 'array'
    assert result['items']['type'] == 'string'

def test_python_type_to_json_type_empty_annotation():
    """Test type conversion with empty annotation"""
    
    result = python_type_to_json_type(inspect.Parameter.empty)
    assert result == "string"


if __name__ == '__main__':
    print("Running MCP decorator tests...")
    test_mcp_tool_decorator_basic()
    print("✓ test_mcp_tool_decorator_basic passed")
    
    test_mcp_tool_decorator_with_positional_arg()
    print("✓ test_mcp_tool_decorator_with_positional_arg passed")
    
    test_mcp_tool_decorator_without_parentheses()
    print("✓ test_mcp_tool_decorator_without_parentheses passed")
    
    test_mcp_tool_decorator_inherit_docs_false()
    print("✓ test_mcp_tool_decorator_inherit_docs_false passed")
    
    test_python_type_to_json_type_mapping()
    print("✓ test_python_type_to_json_type_mapping passed")
    
    test_python_type_to_json_type_list()
    print("✓ test_python_type_to_json_type_list passed")
    
    test_python_type_to_json_type_empty_annotation()
    print("✓ test_python_type_to_json_type_empty_annotation passed")
    
    print("\nAll MCP decorator tests passed! ✓")
