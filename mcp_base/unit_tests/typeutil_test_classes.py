# -*- coding: utf-8 -*-
"""Test classes for typeutil tests - defined at module level to avoid circular imports."""


class _TestBaseClass:
    """Base class for metadata resolution tests."""
    def search(self, name: str, limit: int = 10):
        """Search customers by name.
        
        :param name: Customer name to search for
        :param limit: Maximum number of results to return
        """
        pass


class _TestChildClass(_TestBaseClass):
    """Child class that overrides without annotations."""
    def search(self, name, limit=10):
        # No annotation, no docstring - should inherit from base
        pass


class _TestBaseCustomer:
    """Base class for customer tests."""
    def create_customer(self, name: str, email: str, phone: str = None):
        """Create a new customer record.
        
        :param name: Customer's full name
        :param email: Customer's email address
        :param phone: Customer's phone number (optional)
        """
        pass


class _TestChildCustomer(_TestBaseCustomer):
    """Child class with partial override."""
    def create_customer(self, name, email, phone=None):
        """Override with partial docstring but no type hints."""
        # Only description, no param docs or types
        pass


class _TestGrandparent:
    """Grandparent class for multi-level inheritance test."""
    def search(self, name: str, limit: int = 10):
        """Search customers by name.
        
        :param name: Customer name to search for
        :param limit: Maximum number of results to return
        """
        pass


class _TestParent(_TestGrandparent):
    """Parent class (middle of hierarchy)."""
    def search(self, name, limit=10):
        # No annotation, no docstring
        pass


class _TestChild(_TestParent):
    """Child class for multi-level inheritance test."""
    def search(self, *args, **kwargs):
        # Completely empty override
        pass
