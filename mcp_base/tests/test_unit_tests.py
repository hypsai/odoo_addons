# -*- coding: utf-8 -*-
# @Time         : 12:33 2026/4/29
# @Author       : Chris
# @Description  : Run unit tests within Odoo test framework
import sys
import os
import unittest
from odoo.tests import common, tagged


@tagged("mcp_base", "post_install", "-at_install")
class TestUnitTests(common.SingleTransactionCase):
    """Run standalone unit tests within Odoo test framework.
    
    This test class discovers and runs all tests in the unit_tests directory,
    allowing them to be executed as part of Odoo's test suite.
    
    Note: Using SingleTransactionCase to avoid cursor closure issues when
    running unittest.TestLoader which may trigger module imports after
    the main test method completes.
    """
    
    def test_run_unit_tests(self):
        """Discover and run all unit tests from unit_tests directory."""
        # Get the path to unit_tests directory
        module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        unit_tests_dir = os.path.join(module_dir, 'unit_tests')
        
        # Add unit_tests directory to sys.path for relative imports within test files
        if unit_tests_dir not in sys.path:
            sys.path.insert(0, unit_tests_dir)
        
        # Manually load test files since unit_tests is not a package (no __init__.py)
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # Find all test_*.py files in unit_tests directory
        for filename in sorted(os.listdir(unit_tests_dir)):  # Sort for consistent order
            if filename.startswith('test_') and filename.endswith('.py'):
                # Import the test module
                module_name = filename[:-3]  # Remove .py extension
                # Import module from file path using absolute path
                import importlib.util
                test_file = os.path.join(unit_tests_dir, filename)
                
                # Use a unique module name that won't conflict with odoo.addons
                full_module_name = f"mcp_base_unit_tests_{module_name}"
                
                spec = importlib.util.spec_from_file_location(
                    full_module_name,
                    test_file
                )
                test_module = importlib.util.module_from_spec(spec)
                
                # Add parent module to sys.modules so relative imports work
                # But don't trigger mcp_base.__init__.py
                if 'mcp_base' not in sys.modules:
                    # Create a minimal mcp_base module placeholder
                    import types
                    mcp_base_placeholder = types.ModuleType('mcp_base')
                    mcp_base_placeholder.__path__ = [module_dir]
                    sys.modules['mcp_base'] = mcp_base_placeholder
                
                # Add to sys.modules before exec
                sys.modules[full_module_name] = test_module
                spec.loader.exec_module(test_module)
                
                # Load tests from this module
                module_suite = loader.loadTestsFromModule(test_module)
                suite.addTests(module_suite)
        
        # Run the tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Assert that all tests passed
        self.assertTrue(
            result.wasSuccessful(),
            f"Unit tests failed: {len(result.failures)} failures, {len(result.errors)} errors"
        )
