OQL MCP Integration
===================

Expose OQL query capabilities to AI agents via Model Context Protocol (MCP).

Overview
--------

This module integrates OQL (Odoo Query Language) with the MCP framework, allowing AI agents to query Odoo data using natural language through business-focused syntax.

Key Features
~~~~~~~~~~~~

- **@mcp_tool decorated methods**: Expose ``search_reado`` and ``get_oql_hints`` to AI agents
- **Natural language queries**: AI can use OQL syntax like "Waterproof and Size = '40'"
- **Seamless integration**: Works with Claude, ChatGPT, Cursor and other MCP-compatible clients
- **Business terminology**: Use terms and aliases instead of technical field paths

Quick Start
-----------

**1. Install Dependencies**

Ensure you have these modules installed:

- ``mcp_base`` - MCP framework for Odoo
- ``oql`` - OQL query engine

**2. Install oql_mcp**

Install the module in your Odoo instance.

**3. Configure OQL (Optional)**

Set up Terms and Aliases in OQL for better query experience:

- Navigate to **Settings > Technical > OQL > Terms**
- Navigate to **Settings > Technical > OQL > Aliases**

**4. Connect AI Client**

Configure your MCP client to connect to Odoo:

.. code-block:: json

   {
     "mcpServers": {
       "odoo": {
         "url": "http://localhost:8069/mcp",
         "headers": {
           "X-API-Key": "your-api-key"
         }
       }
     }
   }

Usage Examples
--------------

AI agents can now use these MCP tools:

**search_reado**

Search and read records using OQL:

.. code-block:: python

   # AI asks: "Find waterproof Danner boots in size 40"
   result = env['product.product'].search_reado(
       where="CatgS = 'Boot' and Brand = 'Danner' and EuShoeSize = '40' and Waterproof",
       fields=['name', 'default_code', 'list_price']
   )

**get_oql_hints**

Get autocomplete suggestions for OQL queries:

.. code-block:: python

   hints = env['product.product'].get_oql_hints(
       field='search',
       query="Waterproof and ",
       cursor=15
   )

How It Works
------------

The module extends the base model with two MCP-enabled methods:

1. **search_reado**: Combines search and read operations with OQL support
   - Accepts OQL where clause instead of domain
   - Returns list of dictionaries with requested fields
   - Supports all standard search parameters (offset, limit, order)

2. **get_oql_hints**: Provides query completion hints
   - Returns available fields, terms, and aliases
   - Helps AI construct valid OQL queries
   - Context-aware suggestions based on cursor position

Example Queries
---------------

.. code-block:: python

   # Simple equality
   products = env['product.product'].search_reado(
       where="name = 'Cold Boot'",
       fields=['name', 'price']
   )

   # Complex conditions
   orders = env['sale.order'].search_reado(
       where="state = 'sale' and amount_total > 1000 and partner_id.country = 'Germany'",
       fields=['name', 'amount_total', 'partner_id']
   )

   # Using IN operator
   customers = env['res.partner'].search_reado(
       where="country in ('US', 'CA', 'MX') and active = true",
       fields=['name', 'email']
   )

Requirements
------------

- Odoo 13.0 or higher
- Python packages: lark (via oql dependency)
- Modules: mcp_base, oql

Best Practices
--------------

**For AI Agents:**

- Use ``get_oql_hints`` to discover available fields and terms
- Start with simple queries, then add complexity
- Leverage configured Terms for business-friendly queries
- Use Aliases to shorten field paths

**For Developers:**

- Configure meaningful Term names (e.g., "Waterproof" not "tag_123")
- Create short Aliases for common field paths
- Test OQL queries before exposing to AI
- Monitor query performance for complex conditions

Troubleshooting
---------------

**No tools found in MCP client**

1. Verify ``mcp_base`` is installed and working
2. Check that ``oql_mcp`` module is installed
3. Ensure methods are properly decorated with ``@mcp_tool``

**OQL query errors**

1. Verify ``oql`` module is installed
2. Check Term and Alias configurations
3. Review OQL syntax in query string

Support
-------

For issues or contributions, visit:
https://github.com/chrisking94/odoo_addons/tree/main/oql_mcp

License
-------

LGPL-3
