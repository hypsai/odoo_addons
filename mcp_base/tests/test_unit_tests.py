# -*- coding: utf-8 -*-
# @Time         : 12:33 2026/4/29
# @Author       : Chris
# @Description  : Run unit tests within Odoo test framework
import sys
import os
import unittest
from odoo.tests import common, tagged


@tagged("mcp_base", "post_install", "-at_install")
class TestUnitTests(common.TransactionCase):
    """Run standalone unit tests within Odoo test framework.
    
    This test class discovers and runs all tests in the unit_tests directory,
    allowing them to be executed as part of Odoo's test suite.
    """
    
    def test_run_unit_tests(self):
        """Discover and run all unit tests from unit_tests directory."""
        # Get the path to unit_tests directory
        module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        unit_tests_dir = os.path.join(module_dir, 'unit_tests')
        
        # Add module directory to sys.path for imports
        if module_dir not in sys.path:
            sys.path.insert(0, module_dir)
        
        # Discover all test files in unit_tests directory
        loader = unittest.TestLoader()
        suite = loader.discover(
            start_dir=unit_tests_dir,
            pattern='test_*.py',
            top_level_dir=module_dir
        )
        
        # Run the tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Assert that all tests passed
        self.assertTrue(
            result.wasSuccessful(),
            f"Unit tests failed: {len(result.failures)} failures, {len(result.errors)} errors"
        )
