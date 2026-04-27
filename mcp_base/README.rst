=================
Odoo MCP Framework
=================

.. image:: /mcp_base/static/description/icon.png
   :alt: Odoo MCP Framework Logo
   :align: center
   :width: 200px

.. image:: https://img.shields.io/badge/license-%20%20GNU%20LGPLv3%20-green?style=plastic&logo=gnu
   :target: https://www.gnu.org/licenses/lgpl-3.0.txt
   :alt: License: LGPL-3

.. image:: https://img.shields.io/badge/github-repo-blue?logo=github
   :target: https://github.com/chrisking94/odoo_addons/tree/main/mcp_base
   :alt: Github Repo

**Connect Odoo to AI Agents with One Decorator**

Transform your Odoo into an **MCP (Model Context Protocol) Server** and expose any method to AI agents like Claude, ChatGPT, and Cursor - with just ``@mcp_tool``.

Why This Module?
================

**The Simplest Way to Integrate Odoo with AI:**

.. code-block:: python

    @mcp_tool
    def search_customers(self, name: str):
        """Search customers by name."""
        return self.search([('name', 'ilike', name)])

That's it. No complex configuration, no manual schema definition. Just add the decorator and go.

Key Features
============

* **One-Line Setup**: ``@mcp_tool`` decorator instantly exposes methods to AI
* **Zero Configuration**: Automatic JSON schema generation from type hints
* **Smart Documentation**: Extracts parameter descriptions from docstrings
* **Modern Protocol**: Implements MCP Streamable HTTP (2025-03-26)
* **Production Ready**: Error handling, logging, CORS support built-in
* **Secure Authentication**: Optional API key support via ``auth_api_key``

Quick Start
===========

1. Install the module in your Odoo instance
2. Add ``@mcp_tool`` to any model method
3. Connect your MCP client to ``http://your-odoo:8069/mcp``

.. important::
   **Security Notice**: By default, the MCP server runs with administrator privileges for development convenience.
   For production use, we **strongly recommend** installing the ``auth_api_key`` module to enable secure API key authentication.
   See the Security & Authentication section below for details.

Usage Examples
==============

Basic Usage - The Simplest Way
-------------------------------

Just add the decorator. That's all you need:

.. code-block:: python

    from odoo.addons.mcp_base import mcp_tool
    from odoo import models

    class ResPartner(models.Model):
        _inherit = 'res.partner'
        
        @mcp_tool
        def search_customers(self, name: str, limit: int = 10):
            """Search customers by name.
            
            :param name: Customer name to search for
            :param limit: Maximum number of results
            """
            partners = self.search([('name', 'ilike', name)], limit=limit)
            return [{
                'id': p.id,
                'name': p.name,
                'email': p.email
            } for p in partners]

**What Happens Automatically:**

✅ Type hints -> JSON Schema types (``str`` -> ``string``, ``int`` -> ``integer``)  
✅ Docstring -> Tool description + parameter descriptions  
✅ Default values -> Schema defaults  
✅ Method signature -> Required parameters list

.. important::
   **Inheritance Note**: The ``@mcp_tool`` decorator only works on methods defined directly in the current class.
   Methods decorated in parent classes are NOT inherited as MCP tools. If you need a tool in a child model,
   you must re-decorate it in that model. This is by design to ensure explicit control over which methods
   are exposed to AI agents.

Flexible Decorator Styles
--------------------------

The decorator supports multiple usage styles for maximum convenience:

.. code-block:: python

    # Style 1: No parentheses (recommended for most cases)
    @mcp_tool
    def method1(self, param: str):
        """Simple tool."""
        pass
    
    # Style 2: Custom description (override docstring)
    @mcp_tool("Advanced search with filters")
    def method2(self, query: str):
        """Complex implementation..."""
        pass
    
    # Style 3: Keyword argument
    @mcp_tool(description="Another custom description")
    def method3(self, data: str):
        """Method with keyword arg."""
        pass

Choose the style that fits your needs. Most of the time, ``@mcp_tool`` (Style 1) is all you need.

How It Works
------------

The decorator automatically builds a complete JSON Schema from your code:

.. code-block:: python

    @mcp_tool
    def search_customers(self, name: str, limit: int = 10):
        """Search customers by name.
        
        :param name: Customer name to search for
        :param limit: Maximum number of results
        """
        # Type hints provide types automatically!
        # Only write descriptions in docstring

**Generated Schema:**

.. code-block:: json

    {
      "type": "object",
      "properties": {
        "name": {
          "type": "string",              // From type hint
          "description": "Customer name to search for"  // From docstring
        },
        "limit": {
          "type": "integer",             // From type hint
          "description": "Maximum number of results",  // From docstring
          "default": 10                  // From default value
        }
      },
      "required": ["name"]
    }

**Zero Duplication:**

* ✅ Types from type hints -> No need to repeat in docstrings
* ✅ Descriptions from docstrings -> AI-friendly documentation
* ✅ Defaults from parameters -> Automatic schema defaults
* ✅ Any docstring format -> Sphinx, Google, or NumPy style

Client Configuration
====================

Your MCP endpoint: ``http://your-odoo-server:8069/mcp``

ChatWise
--------

1. Settings -> MCP Servers -> Add new server
2. Select "Streamable HTTP"
3. Enter URL: ``http://localhost:8069/mcp``

Cursor
------

1. Settings -> MCP -> Add Server
2. Choose Streamable HTTP transport
3. Configure endpoint URL

Claude Desktop
--------------

Edit ``config.json``:

.. code-block:: json

    {
      "mcpServers": {
        "odoo": {
          "url": "http://localhost:8069/mcp",
          "transport": "streamable-http"
        }
      }
    }

Security & Authentication
=========================

Development Mode (Default)
---------------------------

Without ``auth_api_key``, the MCP server runs with administrator privileges. Convenient for testing, but **NOT for production**.

You'll see a warning in logs:

.. code-block:: text

    WARNING: MCP Security Warning: Running with sudo() privileges. 
    For production use, please install 'auth_api_key' module.

Production Mode (Recommended)
------------------------------

Install ``auth_api_key`` module for secure API key authentication:

**Step 1: Install auth_api_key**

Download from `Odoo App Store <https://apps.odoo.com/apps/modules/browse?search=auth_api_key>`_.

**Step 2: Create an API Key**

1. Settings -> Technical -> API Keys -> Create
2. Set name and select user account
3. Copy the generated API key

**Step 3: Configure Your Client**

Add header: ``Api-Key: your-api-key-here``

**Claude Desktop example:**

.. code-block:: json

    {
      "mcpServers": {
        "odoo": {
          "url": "http://localhost:8069/mcp",
          "transport": "streamable-http",
          "headers": {
            "Api-Key": "your-api-key-here"
          }
        }
      }
    }

.. warning::
   **Never run MCP server without auth_api_key in production!** Without authentication, anyone can access your Odoo with full admin privileges.

Architecture
============

Streamable HTTP Transport
-------------------------

Implements MCP protocol (2025-03-26):

* **GET /mcp**: SSE stream for server notifications
* **POST /mcp**: JSON-RPC 2.0 requests from clients

Protocol Flow
-------------

1. Client connects via GET -> establishes SSE stream
2. Client sends ``initialize`` via POST
3. Server responds with capabilities
4. Client confirms with ``notifications/initialized``
5. Ready to call ``tools/list`` and ``tools/call``

For Developers
==============

Debugging
---------

Enable debug logging:

.. code-block:: bash

    odoo-bin --log-handler=odoo.addons.mcp_base.controllers.main:DEBUG

Logs show:
* Received MCP methods and parameters
* Found tools during scanning
* Tool execution errors with tracebacks

Best Practices
--------------

1. **Descriptive names**: Method name should indicate purpose
2. **Type hints**: Enable automatic schema generation
3. **Clear descriptions**: Help AI agents understand usage
4. **Simple returns**: Dicts and lists serialize best
5. **Error handling**: Return meaningful error messages

Example:

.. code-block:: python

    @mcp_tool(description="Calculate product profit margin")
    def calculate_margin(self, product_id: int, cost: float):
        """Calculate profit margin for a product."""
        try:
            product = self.env['product.product'].browse(product_id)
            if not product.exists():
                return {'error': f'Product {product_id} not found'}
            
            revenue = product.list_price
            margin = ((revenue - cost) / revenue) * 100 if revenue else 0
            
            return {
                'product': product.name,
                'revenue': revenue,
                'cost': cost,
                'margin_percent': round(margin, 2)
            }
        except Exception as e:
            return {'error': str(e)}


Troubleshooting
===============

No tools found
--------------

If ``tools/list`` returns empty:

1. Ensure module with ``@mcp_tool`` is installed
2. Check methods are on models (not regular classes)
3. Verify methods don't start with underscore
4. Enable debug logging to see scanning results

Connection errors
-----------------

If clients can't connect:

1. Verify Odoo is running and accessible
2. Check firewall allows port 8069
3. Ensure URL format: ``http://host:port/mcp``

Protocol errors
---------------

If you see JSON-RPC errors:

1. Check Odoo logs for details
2. Verify client supports Streamable HTTP
3. Ensure MCP protocol version 2025-03-26 compatibility

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/chrisking94/odoo_addons/issues>`_.

Maintainer
==========

.. image:: https://avatars.githubusercontent.com/u/29966935
   :alt: Chris King Github Home
   :target: https://github.com/chrisking94
   :width: 80px

This module is maintained by **Chris**.
