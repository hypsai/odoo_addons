# -*- coding: utf-8 -*-
# @Time         : 11:10 2026/4/28
# @Author       : Chris
# @Description  :
from odoo import models, api

from ..decorators import mcp_tool


class TestMcpBaseTool(models.Model):
    _name = "test.mcp.base.tool"
    _description = "MCP Tool Test"

    @mcp_tool
    @api.model
    def get_customers(self):
        """Get all customers."""
        return [{"name": "Mary"}, {"name": "Lily"}, {"name": "Tom"}]

    @mcp_tool
    def get_customer_detail(self, name: str):
        """Get detailed information about a specific customer.
        
        :param name: Customer name to look up (e.g., 'Mary', 'Lily', 'Tom')
        :return: Dictionary with customer details including name, email, and status
        """
        customers = {
            "Mary": {
                "name": "Mary",
                "email": "mary@example.com",
                "status": "active",
                "orders_count": 5
            },
            "Lily": {
                "name": "Lily",
                "email": "lily@example.com",
                "status": "active",
                "orders_count": 3
            },
            "Tom": {
                "name": "Tom",
                "email": "tom@example.com",
                "status": "inactive",
                "orders_count": 0
            }
        }
        return customers.get(name, {"error": f"Customer '{name}' not found"})


class TestMcpBaseToolInherited(models.Model):
    _inherit = "test.mcp.base.tool"

    @mcp_tool(description="Get enhanced customer details with additional information")
    def get_customer_detail(self, name: str):
        """Override to provide enhanced customer details.
        
        :param name: Customer name to look up
        :return: Enhanced customer information with premium status
        """
        # Call parent method
        result = super().get_customer_detail(name)
        if "error" not in result:
            # Add enhanced information
            result["premium"] = result.get("orders_count", 0) > 2
            result["vip_level"] = "Gold" if result.get("orders_count", 0) > 4 else "Silver"
        return result

    @mcp_tool
    def greet_customer(self, name: str, greeting: str = "Hello"):
        """Send a personalized greeting to a customer.
        
        :param name: Customer name to greet
        :param greeting: Greeting message template (default: 'Hello')
        :return: Personalized greeting message
        """
        return f"{greeting}, {name}! Welcome back."


# ── Delegation inheritance pair for testing @api.model vs recordset
#     filtering on name_search and _sync_tools_from_registry ─────────

class TestMcpBaseToolParent(models.Model):
    _name = "test.mcp.base.tool.parent"
    _description = "MCP Tool Parent Test"

    @mcp_tool
    @api.model
    def parent_api_model_method(self):
        """An @api.model method defined on the parent — must NOT appear
        on child models via delegation inheritance."""
        return "parent api model"

    @mcp_tool
    def parent_recordset_method(self, name: str):
        """A recordset method on the parent — MAY appear on child models."""
        return f"Parent: {name}"


class TestMcpBaseToolChild(models.Model):
    _name = "test.mcp.base.tool.child"
    _inherit = "test.mcp.base.tool.parent"
    _description = "MCP Tool Child Test"

    @mcp_tool
    def child_method(self, value: int):
        """A recordset method defined on the child model."""
        return value * 2


def ensure_model_meta(env, model_names):
    """
    Insert model meta into `ir.model` manually.
    """
    for model_name in model_names:
        # Search for existing model record
        meta = env["ir.model"].search([("model", "=", model_name)], limit=1)

        if not meta:
            model_class = env.registry.get(model_name)
            description = getattr(model_class, '_description', '') if model_class else ''
            is_abstract = getattr(model_class, '_abstract', False) if model_class else False
            is_transient = getattr(model_class, '_transient', False) if model_class else False

            # Create complete model metadata with all required fields
            env["ir.model"].create({
                'model': model_name,
                'name': description or model_name.replace('.', ' ').title(),
                'state': 'base',
                'info': description,
                'transient': is_transient,
                'order': 'id',  # Default ordering
            })


def ensure_tool_records(env, model_names=None):
    """Create or update ``mcp.base.tool`` records for all ``@mcp_tool`` methods.

    This mirrors what the future auto-sync mechanism will do at module
    install/upgrade time, so that controller tests see the same ORM-based
    tool definitions that a real instance would produce.
    """
    for model_name, model_cls in env.registry.models.items():
        if model_names and model_name not in model_names:
            continue

        ir_model = env['ir.model'].search([('model', '=', model_name)], limit=1)
        if not ir_model:
            continue

        for attr_name in dir(model_cls):
            if attr_name.startswith('_'):
                continue
            method = getattr(model_cls, attr_name, None)
            if not callable(method) or not getattr(method, '_is_mcp_tool', False):
                continue

            docstring = method.__doc__ or ''

            # find or create mcp.base.method
            method_ref = env['mcp.base.method'].search([
                ('name', '=', attr_name),
                ('model_id', '=', ir_model.id),
            ], limit=1)
            if not method_ref:
                method_ref = env['mcp.base.method'].create({
                    'name': attr_name,
                    'model_id': ir_model.id,
                })

            existing = env['mcp.base.tool'].search([
                ('model_id', '=', ir_model.id),
                ('method_id', '=', method_ref.id),
            ], limit=1)

            if existing:
                existing.write({
                    'name': f"{model_name}:{attr_name}",
                    'docstring': docstring,
                    'is_code_first': True,
                    'active': True,
                })
            else:
                env['mcp.base.tool'].create({
                    'name': f"{model_name}:{attr_name}",
                    'model_id': ir_model.id,
                    'method_id': method_ref.id,
                    'docstring': docstring,
                    'is_code_first': True,
                })
