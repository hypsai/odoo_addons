.. |tool_logo| image:: /mcp_base/static/description/icon.png
   :alt: Odoo MCP Framework Logo
   :align: center
   :width: 200px

.. |license_badge| image:: https://img.shields.io/badge/license-%20%20GNU%20LGPLv3%20-green?style=plastic&logo=gnu
   :target: https://www.gnu.org/licenses/lgpl-3.0.txt
   :alt: License: LGPL-3

.. |github_badge| image:: https://img.shields.io/badge/github-repo-blue?logo=github
   :target: https://github.com/chrisking94/odoo_addons/tree/main/mcp_base
   :alt: Github Repo

.. |chatwise_auth_basic| image:: /mcp_base/static/description/chatwise_auth_basic.png
   :alt: ChatWise config with X-User/X-Password
   :align: center
   :width: 500px

.. |chatwise_auth_api_key| image:: /mcp_base/static/description/chatwise_auth_api_key.png
   :alt: ChatWise config with API Key
   :align: center
   :width: 500px

.. |mcp_tools_list| image:: /mcp_base/static/description/mcp_tools_list.png
   :alt: MCP Tools list view in Odoo
   :align: center
   :width: 500px

.. |mcp_tool_form| image:: /mcp_base/static/description/mcp_tool_form.png
   :alt: MCP Tool form view in Odoo
   :align: center
   :width: 500px

=================
Odoo MCP Framework
=================

|tool_logo|

|license_badge| |github_badge|

**Connect Odoo to AI Agents — with a decorator or a few clicks.**

Transform your Odoo into an **MCP (Model Context Protocol) Server** and expose any model method to AI agents like Claude, ChatGPT, and Cursor.

Pick the approach that fits your workflow: add ``@mcp_tool`` in Python code, or define tools
through the Odoo UI with a docstring — no code required.

.. contents:: Table of Contents
   :depth: 2
   :local:

Why This Module?
================

**Code-First** — one decorator, instant MCP tool:

.. code-block:: python

    @mcp_tool
    def search_customers(self, name: str):
        """Search customers by name."""
        return self.search([('name', 'ilike', name)])

**Config-First** — fill in a form in the Odoo UI, write a docstring, and it just works:

.. code-block::

   Model: res.partner
   Method: action_archive
   Docstring:
       Archive the selected customers.

       :param force: Set to True to skip the unlink check

That's it.  No complex configuration, no manual schema definition.

Key Features
============

* **Two flexible approaches** — ``@mcp_tool`` decorator for developers, UI-based docstring for admins
* **Automatic JSON Schema generation** — from Python type hints **or** docstring formats
* **Smart docstring parsing** — supports Google, NumPy, and Sphinx/reST styles
* **Modern protocol** — MCP Streamable HTTP (2025-03-26)
* **Production ready** — error handling, logging, CORS support built-in
* **Secure authentication** — plain text headers, HTTP Basic Auth, and optional API keys via ``auth_api_key``

Quick Start
===========

1. Install the module in your Odoo instance
2. Choose your approach (see below)
3. Connect your MCP client to ``http://your-odoo:8069/mcp``

.. important::
   The MCP server requires authentication.  Use plain text ``X-User`` / ``X-Password`` headers,
   HTTP Basic Auth, or — for enhanced security — install ``auth_api_key`` to use API keys.
   See the `Security & Authentication`_ section for details.

Two Approaches to Define Tools
==============================

The framework supports both **Code-First** and **Config-First** workflows.
You can mix both approaches — they live side-by-side in the same ``mcp.base.tool`` model.

Code-First — ``@mcp_tool`` Decorator
-------------------------------------

Tag any model method with ``@mcp_tool`` and the framework handles the rest:

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
                'email': p.email,
            } for p in partners]

**What happens automatically:**

* Type hints → JSON Schema types (``str`` → ``string``, ``int`` → ``integer``)
* Docstring → tool description + parameter descriptions
* Default values → optional parameters in the schema
* No defaults → required parameters

**``@mcp_tool`` decorator styles:**

.. code-block:: python

    # Style 1: Bare decorator (recommended for most cases)
    @mcp_tool
    def method1(self, param: str):
        """Simple tool."""

    # Style 2: Custom description string
    @mcp_tool("Advanced search with filters")
    def method2(self, query: str):
        """Complex implementation..."""

    # Style 3: Keyword arguments
    @mcp_tool(description="Another custom description", inherit_docs=False)
    def method3(self, data: str):
        """Method with keyword arg."""

**Smart MRO inheritance** — when you override a parent's ``@mcp_tool`` method, missing type
hints and docstrings are automatically inherited from the parent class.  You don't need
to repeat annotations.  See `Smart Inheritance Support`_ below.

.. important::
   ``@mcp_tool`` only applies to methods defined directly in the current class.
   Methods decorated in parent classes are **not** inherited as MCP tools.
   If you need a tool in a child model, re-decorate it there.
   This is by design — you explicitly control which methods are exposed.

Config-First — UI-Based (No Code)
-----------------------------------

Define a tool entirely through the Odoo web interface by filling in a form.
No Python decorator, no restarts — just pick a model, pick a method, and write a docstring.

**Steps:**

1. Go to **MCP Tools** via the app menu, or open **Settings → Technical → Models → [a model] → MCP Tools** tab.
2. Click **Create**, then fill in:

   * **Tool Name** — a display name (e.g. "Archive Customers")
   * **Model** — the Odoo model the tool operates on
   * **Method** — a Python method from that model (auto-populated dropdown)
   * **Docstring** — write a docstring in Google, NumPy, or Sphinx style to define parameters

3. Save.  The framework parses your docstring and generates the tool's description and
   JSON input schema automatically.

**Supported docstring styles:**

+-----------------+-------------------------------------------------------+--------------------------------------------+
| Style           | Parameter syntax                                      | Type annotation                            |
+=================+=======================================================+============================================+
| **Sphinx/reST** | ``:param name: description``                          | ``:type name: str``                        |
+-----------------+-------------------------------------------------------+--------------------------------------------+
| **Google**      | ``name (str): description`` or ``name: description``  | Inline in parentheses, e.g. ``(str)``      |
+-----------------+-------------------------------------------------------+--------------------------------------------+
| **NumPy**       | ``name : str`` followed by indented description       | After colon, e.g. ``name : int``           |
+-----------------+-------------------------------------------------------+--------------------------------------------+

**Example — Sphinx-style docstring:**

.. code-block:: rst

    Archive customers by force or with a confirmation check.

    :param force: Set to True to skip the unlink safety check
    :type force: bool

This generates:

.. code-block:: json

    {
      "description": "Archive customers by force or with a confirmation check.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "force": { "type": "boolean", "description": "Set to True to skip the unlink safety check" }
        },
        "required": ["force"]
      }
    }

**Example — Google-style docstring:**

.. code-block:: rst

    Search for partners by name.

    Args:
        name (str): The partner name to search for
        limit (int, optional): Maximum results, defaults to 10

.. note::
   In config-first mode, all declared parameters are treated as **required**.
   For optional parameters with defaults, use the **code-first** approach instead.

**UI management:**

* Toggle tools on/off with the **Active** checkbox — inactive tools are hidden from MCP clients.
* Edit the docstring at any time to adjust parameters or descriptions.
* Use the search view to filter by model, method name, or active status.

Approach Comparison
-------------------

+---------------------------+-------------------------------------------------+-----------------------------------------------+
| Aspect                    | Code-First (``@mcp_tool``)                       | Config-First (UI docstring)                   |
+===========================+=================================================+===============================================+
| **Trigger**               | Python decorator on method                      | Manual form entry in Odoo UI                  |
+---------------------------+-------------------------------------------------+-----------------------------------------------+
| **Source of truth**       | Python type hints + ``__doc__``                  | User-written docstring on the tool record     |
+---------------------------+-------------------------------------------------+-----------------------------------------------+
| **Type information**      | Python annotations (``name: str``)              | Docstring type directives (``:type:``, etc.)  |
+---------------------------+-------------------------------------------------+-----------------------------------------------+
| **Optional parameters**   | Parameters with default values are optional     | All declared params are required              |
+---------------------------+-------------------------------------------------+-----------------------------------------------+
| **Inheritance**           | Automatically walks MRO for types + docs        | Not applicable (single docstring)             |
+---------------------------+-------------------------------------------------+-----------------------------------------------+
| **Custom description**    | ``@mcp_tool("Custom desc")``                    | First paragraph of docstring                  |
+---------------------------+-------------------------------------------------+-----------------------------------------------+
| **UI editability**        | Read-only (locked to code)                      | Editable (change docstring anytime)          |
+---------------------------+-------------------------------------------------+-----------------------------------------------+
| **Sync**                  | Auto-refreshed on module upgrade                | Instant on save                               |
+---------------------------+-------------------------------------------------+-----------------------------------------------+

Smart Inheritance Support
=========================

When overriding ``@mcp_tool`` methods in child classes, you don't need to repeat
type hints or docstrings:

.. code-block:: python

    class BaseClass(models.Model):
        _name = 'base.model'

        @mcp_tool
        def search_records(self, name: str, limit: int = 10):
            """Search records by name.

            :param name: Record name to search
            :param limit: Maximum results
            """

    class ChildClass(BaseClass):
        _inherit = 'base.model'

        @mcp_tool
        def search_records(self, name, limit=10):
            # No need to repeat type hints or docstring!
            # Automatically inherited from parent class
            return super().search_records(name, limit)

**How it works:**

* Missing type hints → inherited from parent method
* Missing docstring → inherited from parent method
* Partial override → merges child and parent info
* Multi-level inheritance → searches the entire class hierarchy

This saves you from duplicating documentation while keeping AI agents fully informed.

**Built-in ``_search_`` parameter**

Every MCP tool (both code-first and config-first) automatically includes an optional
``_search_`` object parameter **unless the method is decorated with ``@api.model``**.
This allows AI agents to filter records before method execution:

.. code-block:: json

    {
      "_search_": {
        "args": [["active", "=", true], ["country_id.code", "=", "US"]],
        "limit": 10,
        "order": "name asc"
      }
    }

How It Works
============

The framework automatically builds a complete JSON Schema from your code or docstring:

.. code-block:: python

    @mcp_tool
    def search_customers(self, name: str, limit: int = 10):
        """Search customers by name.

        :param name: Customer name to search for
        :param limit: Maximum number of results
        """

**Generated Schema:**

.. code-block:: json

    {
      "type": "object",
      "properties": {
        "name": {
          "type": "string",
          "description": "Customer name to search for"
        },
        "limit": {
          "type": "integer",
          "description": "Maximum number of results",
          "default": 10
        }
      },
      "required": ["name"]
    }

**Zero Duplication:**

* Types from type hints — no need to repeat in docstrings
* Descriptions from docstrings — AI-friendly documentation
* Defaults from parameters — automatic schema defaults
* Any docstring format — Sphinx, Google, or NumPy style

Client Configuration
====================

Your MCP endpoint: ``http://your-odoo-server:8069/mcp``

ChatWise
--------

1. Settings → MCP Servers → Add new server
2. Select "Streamable HTTP"
3. Enter URL: ``http://localhost:8069/mcp``

Cursor
------

1. Settings → MCP → Add Server
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

Plain Text Headers (Simplest)
-------------------------------

Add two headers with your Odoo credentials — no encoding needed:

.. code-block:: text

    X-User: admin
    X-Password: your-password

|chatwise_auth_basic|

**Claude Desktop example:**

.. code-block:: json

    {
      "mcpServers": {
        "odoo": {
          "url": "http://localhost:8069/mcp",
          "transport": "streamable-http",
          "headers": {
            "X-User": "admin",
            "X-Password": "your-password"
          }
        }
      }
    }

HTTP Basic Auth (Alternative)
-----------------------------

Standard ``Authorization: Basic <base64-credentials>`` is also supported:

.. code-block:: json

    {
      "mcpServers": {
        "odoo": {
          "url": "http://localhost:8069/mcp",
          "transport": "streamable-http",
          "headers": {
            "Authorization": "Basic <base64(username:password)>"
          }
        }
      }
    }

API Key Authentication (Recommended for Production)
----------------------------------------------------

Install ``auth_api_key`` for key-based authentication — no passwords exposed:

**Step 1: Install auth_api_key**

Download from the `Odoo App Store <https://apps.odoo.com/apps/modules/browse?search=auth_api_key>`_.

**Step 2: Create an API Key**

1. Settings → Technical → API Keys → Create
2. Set name and choose target user
3. Copy the generated API key

**Step 3: Configure Your Client**

Add header: ``Api-Key: your-api-key-here``

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

|chatwise_auth_api_key|

.. note::
   When ``auth_api_key`` is installed, API key authentication takes priority
   and all other methods are disabled.

Architecture
============

Streamable HTTP Transport
-------------------------

Implements MCP protocol (2025-03-26):

* **GET /mcp** — SSE stream for server notifications
* **POST /mcp** — JSON-RPC 2.0 requests from clients

Protocol Flow
-------------

1. Client connects via GET → establishes SSE stream
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

1. **Descriptive names** — method name should indicate purpose
2. **Type hints** — enable automatic schema generation (code-first)
3. **Clear descriptions** — help AI agents understand usage
4. **Simple returns** — dicts and lists serialize best
5. **Error handling** — return meaningful error messages

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

1. Ensure the module with ``@mcp_tool`` methods is installed
2. Verify you have created tool records (code-first: run module upgrade; config-first: create in UI)
3. Check methods are on Odoo models (not regular Python classes)
4. Verify methods don't start with underscore
5. Enable debug logging to see scanning results

Connection errors
-----------------

If clients can't connect:

1. Verify Odoo is running and accessible
2. Check firewall allows the configured port (default 8069)
3. Ensure URL format: ``http://host:port/mcp``

Protocol errors
---------------

If you see JSON-RPC errors:

1. Check Odoo logs for details
2. Verify client supports Streamable HTTP transport
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
