# -*- coding: utf-8 -*-
from typing import List, Dict

from mcp_base.decorators import mcp_tool
from mcp_base.mcputil import build_tool_info


def test_build_tool_info_basic():
    """Test build_tool_info with basic method"""
    
    @mcp_tool(description="Test method")
    def test_method(self, name: str, age: int = 0):
        """Test method docstring"""
        return {"name": name, "age": age}
    
    # Need to pass custom_desc because mcputil doesn't auto-read from method
    tool_info = build_tool_info(test_method, custom_desc="Test method")
    
    assert 'description' in tool_info
    assert 'inputSchema' in tool_info
    assert tool_info['description'] == "Test method"

def test_build_tool_info_auto_description():
    """Test build_tool_info extracts description from docstring"""
    
    @mcp_tool()
    def test_method(self, param: str):
        """Auto extracted description"""
        return param
    
    tool_info = build_tool_info(test_method)
    assert tool_info['description'] == "Auto extracted description"

def test_build_tool_info_schema_string():
    """Test schema generation for string parameter"""
    
    @mcp_tool()
    def test_method(self, name: str):
        return name
    
    tool_info = build_tool_info(test_method)
    schema = tool_info['inputSchema']
    
    assert schema['type'] == 'object'
    assert 'name' in schema['properties']
    assert schema['properties']['name']['type'] == 'string'
    assert 'name' in schema['required']

def test_build_tool_info_schema_integer():
    """Test schema generation for integer parameter"""
    
    @mcp_tool()
    def test_method(self, count: int):
        return count
    
    tool_info = build_tool_info(test_method)
    assert tool_info['inputSchema']['properties']['count']['type'] == 'integer'

def test_build_tool_info_schema_float():
    """Test schema generation for float parameter"""
    
    @mcp_tool()
    def test_method(self, price: float):
        return price
    
    tool_info = build_tool_info(test_method)
    assert tool_info['inputSchema']['properties']['price']['type'] == 'number'

def test_build_tool_info_schema_boolean():
    """Test schema generation for boolean parameter"""
    
    @mcp_tool()
    def test_method(self, active: bool):
        return active
    
    tool_info = build_tool_info(test_method)
    assert tool_info['inputSchema']['properties']['active']['type'] == 'boolean'

def test_build_tool_info_schema_list():
    """Test schema generation for list parameter"""
    
    @mcp_tool()
    def test_method(self, items: List[str]):
        return items
    
    tool_info = build_tool_info(test_method)
    prop = tool_info['inputSchema']['properties']['items']
    assert prop['type'] == 'array'
    assert prop['items']['type'] == 'string'

def test_build_tool_info_schema_dict():
    """Test schema generation for dict parameter"""
    
    @mcp_tool()
    def test_method(self, data: Dict):
        return data
    
    tool_info = build_tool_info(test_method)
    assert tool_info['inputSchema']['properties']['data']['type'] == 'object'

def test_build_tool_info_optional_parameter():
    """Test schema generation for optional parameter with default"""
    
    @mcp_tool()
    def test_method(self, name: str, age: int = 0):
        return {"name": name, "age": age}
    
    tool_info = build_tool_info(test_method)
    schema = tool_info['inputSchema']
    
    assert 'name' in schema['required']
    assert 'age' not in schema['required']
    assert schema['properties']['age']['default'] == 0

def test_build_tool_info_multiple_parameters():
    """Test schema generation with multiple parameters"""
    
    @mcp_tool()
    def test_method(self, name: str, age: int, active: bool = True):
        return {"name": name, "age": age, "active": active}
    
    tool_info = build_tool_info(test_method)
    schema = tool_info['inputSchema']
    
    assert len(schema['properties']) == 3
    assert 'name' in schema['required']
    assert 'age' in schema['required']
    assert 'active' not in schema['required']

def test_build_tool_info_with_custom_description():
    """Test build_tool_info uses custom description"""
    
    @mcp_tool()
    def test_method(self, param: str):
        """Docstring description"""
        return param
    
    # Override with custom description
    tool_info = build_tool_info(test_method, custom_desc="Custom override")
    assert tool_info['description'] == "Custom override"

def test_build_tool_info_inherit_docs_false():
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
    
    child_instance = ChildClass()
    tool_info = build_tool_info(child_instance.child_method, inherit_docs=False)
    
    # Should use child's docstring, not inherit from base
    assert tool_info['description'] == "Child docstring"


if __name__ == '__main__':
    print("Running MCP util tests...")
    
    test_build_tool_info_basic()
    print("✓ test_build_tool_info_basic passed")
    
    test_build_tool_info_auto_description()
    print("✓ test_build_tool_info_auto_description passed")
    
    test_build_tool_info_schema_string()
    print("✓ test_build_tool_info_schema_string passed")
    
    test_build_tool_info_schema_integer()
    print("✓ test_build_tool_info_schema_integer passed")
    
    test_build_tool_info_schema_float()
    print("✓ test_build_tool_info_schema_float passed")
    
    test_build_tool_info_schema_boolean()
    print("✓ test_build_tool_info_schema_boolean passed")
    
    test_build_tool_info_schema_list()
    print("✓ test_build_tool_info_schema_list passed")
    
    test_build_tool_info_schema_dict()
    print("✓ test_build_tool_info_schema_dict passed")
    
    test_build_tool_info_optional_parameter()
    print("✓ test_build_tool_info_optional_parameter passed")
    
    test_build_tool_info_multiple_parameters()
    print("✓ test_build_tool_info_multiple_parameters passed")
    
    test_build_tool_info_with_custom_description()
    print("✓ test_build_tool_info_with_custom_description passed")
    
    test_build_tool_info_inherit_docs_false()
    print("✓ test_build_tool_info_inherit_docs_false passed")
    
    print("\nAll MCP util tests passed! ✓")
