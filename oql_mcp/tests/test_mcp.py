# -*- coding: utf-8 -*-
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestOqlMcp(TransactionCase):
    """Test OQL MCP integration."""

    def setUp(self):
        super().setUp()
        # Create test product for search_reado tests
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'default_code': 'TEST001',
            'list_price': 100.0,
        })

    def test_search_reado_basic(self):
        """Test basic search_reado functionality."""
        result = self.env['product.product'].search_reado(
            where="name = 'Test Product'",
            fields=['name', 'default_code']
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Test Product')
        self.assertEqual(result[0]['default_code'], 'TEST001')

    def test_search_reado_no_results(self):
        """Test search_reado with no matching records."""
        result = self.env['product.product'].search_reado(
            where="name = 'Nonexistent Product'",
            fields=['name']
        )
        self.assertEqual(result, [])

    def test_search_reado_with_limit(self):
        """Test search_reado with limit parameter."""
        # Create additional products
        for i in range(5):
            self.env['product.product'].create({
                'name': f'Product {i}',
            })
        
        result = self.env['product.product'].search_reado(
            where="1 = 1",  # Match all
            fields=['name'],
            limit=3
        )
        self.assertLessEqual(len(result), 3)

    def test_search_reado_with_order(self):
        """Test search_reado with order parameter."""
        result = self.env['product.product'].search_reado(
            where="1 = 1",
            fields=['name'],
            order='name asc',
            limit=5
        )
        # Verify results are ordered
        names = [r['name'] for r in result]
        self.assertEqual(names, sorted(names))

    def test_search_reado_id_only(self):
        """Test search_reado with only id field."""
        result = self.env['product.product'].search_reado(
            where="name = 'Test Product'",
            fields=['id']
        )
        self.assertEqual(len(result), 1)
        self.assertIn('id', result[0])
        self.assertEqual(list(result[0].keys()), ['id'])

    def test_get_oql_hints(self):
        """Test get_oql_hints method exists and is callable."""
        hints = self.env['product.product'].get_oql_hints(
            field='search',
            query='',
            cursor=0,
            limit=10
        )
        # Method should return a list (may be empty if no OQL config)
        self.assertIsInstance(hints, list)
