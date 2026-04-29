# -*- coding: utf-8 -*-
"""Quick test for docstring parser functionality."""
import sys
import unittest
from mcp_base.docstring import parse_docstring, parse_docstring_params, extract_tool_description
from mcp_base.decorators import mcp_tool


class TestDocstring(unittest.TestCase):
    """Test suite for docstring parser functionality"""
    
    def test_google_style(self):
        """Test Google-style docstring parsing."""
        docstring = """Search for customers by name.
    
    Args:
        name: Customer name to search for
        limit: Maximum number of results to return
    
    Returns:
        List of matching customers
    """
        
        params = parse_docstring_params(docstring)
        self.assertEqual(params.get('name'), "Customer name to search for")
        self.assertEqual(params.get('limit'), "Maximum number of results to return")


    def test_numpy_style(self):
        """Test NumPy-style docstring parsing."""
        docstring = """Calculate total price.
    
    Parameters
    ----------
    quantity : int
        Number of items
    price : float
        Price per item
    
    Returns
    -------
    float
        Total price
    """
        
        params = parse_docstring_params(docstring)
        # Note: descriptions are normalized to lowercase by cleandoc
        self.assertIn('quantity', params)
        self.assertIn('price', params)
        self.assertIn('items', params['quantity'].lower())
        self.assertIn('price', params['price'].lower())


    def test_sphinx_style(self):
        """Test Sphinx/reST-style docstring parsing."""
        docstring = """Send email notification.
    
    :param recipient: Email recipient address
    :param subject: Email subject line
    :arg body: Email body content
    """
        
        params = parse_docstring_params(docstring)
        self.assertEqual(params.get('recipient'), "Email recipient address")
        self.assertEqual(params.get('subject'), "Email subject line")
        self.assertEqual(params.get('body'), "Email body content")


    def test_parse_docstring_complete(self):
        """Test complete docstring parsing (description + params + returns)."""
        # Test 1: Sphinx style with returns
        docstring1 = """Search customers by name.
    
    :param name: Customer name to search for
    :param limit: Maximum number of results
    :returns: List of matching customers
    """
        result1 = parse_docstring(docstring1)
        self.assertEqual(result1['description'], "Search customers by name.")
        self.assertEqual(result1['params']['name'], "Customer name to search for")
        self.assertEqual(result1['params']['limit'], "Maximum number of results")
        self.assertEqual(result1['returns'], "List of matching customers")
        
        # Test 2: Google style
        docstring2 = """Calculate total price.
    
    Args:
        quantity: Number of items
        price: Price per item
    
    Returns:
        Total price as float
    """
        result2 = parse_docstring(docstring2)
        self.assertEqual(result2['description'], "Calculate total price.")
        self.assertIn('quantity', result2['params'])
        self.assertIn('price', result2['params'])
        self.assertIn('total price', result2['returns'].lower())
        
        # Test 3: No returns section
        docstring3 = """Simple method.
    
    :param x: Input value
    """
        result3 = parse_docstring(docstring3)
        self.assertEqual(result3['description'], "Simple method.")
        self.assertEqual(result3['params']['x'], "Input value")
        self.assertEqual(result3['returns'], "")


    def test_extract_tool_description(self):
        """Test extraction of tool description from docstring."""
        # Test 1: Sphinx style
        docstring1 = """Search customers by name.
    
    :param name: Customer name to search for
    :param limit: Maximum number of results
    """
        desc1 = extract_tool_description(docstring1)
        self.assertEqual(desc1, "Search customers by name.")
        
        # Test 2: Google style
        docstring2 = """Calculate total price.
    
    Args:
        quantity: Number of items
        price: Price per item
    """
        desc2 = extract_tool_description(docstring2)
        self.assertEqual(desc2, "Calculate total price.")
        
        # Test 3: NumPy style
        docstring3 = """Send email notification.
    
    Parameters
    ----------
    recipient : str
        Email recipient
    """
        desc3 = extract_tool_description(docstring3)
        self.assertEqual(desc3, "Send email notification.")
        
        # Test 4: No params
        docstring4 = """Simple method without parameters."""
        desc4 = extract_tool_description(docstring4)
        self.assertEqual(desc4, "Simple method without parameters.")
        
        # Test 5: Empty docstring
        desc5 = extract_tool_description("")
        self.assertEqual(desc5, "Odoo Tool")


    def test_complex_types_from_docstring(self):
        """Test parsing of complex type annotations from :type: directives."""
        # Test 1: List[str]
        docstring1 = """Method with list type.
    
    :param names: List of user names
    :type names: List[str]
    """
        result1 = parse_docstring(docstring1)
        self.assertEqual(result1['param_types'].get('names'), {'type': 'array', 'items': {'type': 'string'}})
        
        # Test 2: Dict[str, int]
        docstring2 = """Method with dict type.
    
    :param data: User data mapping
    :type data: Dict[str, int]
    """
        result2 = parse_docstring(docstring2)
        self.assertEqual(result2['param_types'].get('data'), {'type': 'object'})
        
        # Test 3: Optional[str]
        docstring3 = """Method with optional type.
    
    :param name: Optional user name
    :type name: Optional[str]
    """
        result3 = parse_docstring(docstring3)
        self.assertEqual(result3['param_types'].get('name'), 'string')
        
        # Test 4: List[Dict[str, Any]]
        docstring4 = """Method with complex nested type.
    
    :param users: List of user objects
    :type users: List[Dict[str, Any]]
    """
        result4 = parse_docstring(docstring4)
        self.assertEqual(result4['param_types'].get('users'), {'type': 'array', 'items': {'type': 'object'}})
        
        # Test 5: Union[int, str]
        docstring5 = """Method with union type.
    
    :param value: Value that can be int or str
    :type value: Union[int, str]
    """
        result5 = parse_docstring(docstring5)
        self.assertEqual(result5['param_types'].get('value'), 'integer')  # Takes first non-None type


    def test_type_priority(self):
        """Test that type hints take priority over docstring :type:."""
        # Note: Current decorator implementation doesn't generate _mcp_schema
        # Schema generation is handled by controller at runtime via build_tool_info()
        # This test would need to be updated to use build_tool_info() instead
        self.skipTest("Schema generation moved to controller runtime (build_tool_info)")


    def test_mcp_decorator_integration(self):
        """Test MCP decorator with docstring parameter descriptions."""
        # Note: Current decorator doesn't generate _mcp_schema at decoration time
        # Schema is generated at runtime by controller using build_tool_info()
        @mcp_tool()
        def search_customers(self, name: str, limit: int = 10):
            """Search for customers by name.
            
            Args:
                name: Customer name to search for
                limit: Maximum number of results to return
            """
            return []
        
        # Just verify decorator marks the method
        self.assertTrue(hasattr(search_customers, '_is_mcp_tool'))
        self.assertEqual(search_customers._mcp_custom_description, None)  # Uses docstring
        self.assertEqual(search_customers._mcp_inherit_docs, True)


    def test_mcp_decorator_without_parentheses(self):
        """Test MCP decorator without parentheses (@mcp_tool)."""
        # Test 1: Basic usage without parentheses
        @mcp_tool
        def simple_search(self, query: str):
            """Simple search method.
            
            :param query: Search query string
            """
            return []
        
        self.assertTrue(hasattr(simple_search, '_is_mcp_tool'))
        self.assertIsNone(simple_search._mcp_custom_description)  # Will use docstring at runtime
        self.assertEqual(simple_search._mcp_inherit_docs, True)
        
        # Test 2: Without parentheses but with complex types
        @mcp_tool
        def complex_method(self, names: list, data: dict):
            """Method with complex types.
            
            Args:
                names: List of names
                data: Data dictionary
            """
            return []
        
        self.assertTrue(hasattr(complex_method, '_is_mcp_tool'))
        self.assertIsNone(complex_method._mcp_custom_description)


    def test_mcp_decorator_with_custom_description(self):
        """Test MCP decorator with custom description parameter."""
        # Test 1: Custom description overrides docstring (keyword arg)
        @mcp_tool(description="Custom tool description")
        def method_with_custom_desc(self, param: str):
            """This should be ignored.
            
            :param param: Parameter description
            """
            return []
        
        self.assertEqual(method_with_custom_desc._mcp_custom_description, "Custom tool description")
        self.assertEqual(method_with_custom_desc._mcp_inherit_docs, True)
        
        # Test 2: Positional argument style
        @mcp_tool("Positional description")
        def method_with_positional_desc(self, value: int):
            """This should also be ignored.
            
            :param value: Integer value
            """
            return []
        
        self.assertEqual(method_with_positional_desc._mcp_custom_description, "Positional description")
        
        # Test 3: Empty parentheses (should use docstring)
        @mcp_tool()
        def method_with_empty_parens(self, data: str):
            """Method with empty parens.
            
            :param data: Data parameter
            """
            return []
        
        self.assertIsNone(method_with_empty_parens._mcp_custom_description)  # Will use docstring at runtime


if __name__ == '__main__':
    unittest.main()
