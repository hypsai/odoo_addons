{
    "name": "OQL MCP Integration",
    "version":"1.0.1",
    "author": "Hypsai Tech",
    "website": "https://github.com/hypsai/odoo_addons/tree/main/oql_mcp",
    "license": "LGPL-3",
    "category": "Tools/AI",
    "summary": "Expose OQL query capabilities to AI agents via Model Context Protocol (MCP).",
    "description": """
OQL MCP Integration exposes Odoo Query Language (OQL) methods to AI agents through the Model Context Protocol.

Key Features:
- Expose search_reado method with OQL support to AI agents via @mcp_tool
- Enable natural language queries on Odoo data through MCP-compatible clients
- Seamless integration with Claude, ChatGPT, Cursor and other AI assistants
- Business-focused query syntax instead of technical domain expressions

Example Usage by AI:
    - Search products: "Find waterproof Danner boots in size 40"
    - Query customers: "Show me active customers from Germany"
    - Filter records: "Get orders created last week with total > 1000"

Requirements:
- mcp_base module (for MCP framework)
- oql module (for OQL query engine)

This module extends base models with MCP-enabled OQL query methods.
    """,
    'depends': ['base', 'mcp_base', 'oql'],
    'images': ['static/description/banner.png'],
    'external_dependencies': {
        'python': [],
    },
    "data": [],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
