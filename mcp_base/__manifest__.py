{
    'name': 'Odoo MCP Framework',
    'version':'2.0.0',
    'summary': 'Native Model Context Protocol (MCP) Server for Odoo - Connect AI Agents to Your ERP',
    'description': """
        Transform your Odoo into an AI-ready MCP Server with just one decorator!
        
        This addon implements the Model Context Protocol (MCP) specification, enabling
        seamless integration between Odoo and AI agents like Claude, ChatGPT, and Cursor.
        
        Key Features:
        - One-line @mcp_tool decorator to expose methods to AI
        - Automatic JSON schema generation from Python type hints
        - Streamable HTTP transport (MCP 2025-03-26)
        - Zero configuration required
        - Production-ready with error handling and logging
        
        Security:
        - Optional auth_api_key support for secure API authentication
        - Without auth_api_key: runs with admin privileges (development only)
        - With auth_api_key: uses API key-based user authentication (production recommended)
        
        Perfect for building AI-powered chatbots, automated workflows,
        intelligent assistants, and LLM integrations with your Odoo ERP.
    """,
    'category': 'Tools/AI',
    'author': 'Hypsai.ai',
    'website': 'https://github.com/chrisking94/odoo_addons/tree/main/mcp_base',
    'license': 'LGPL-3',
    'depends': ['base'],
    'images': ['static/description/banner.png'],
    'external_dependencies': {
        'python': [],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/ir_model_views.xml',
        'views/mcp_base_tool_views.xml',
        'views/ir_model_access_views.xml',
        'views/mcp_base_menu.xml',
    ],
    # Required for v13-v19 compatibility: explicitly declare controllers
    # so the routing map includes /mcp in test environments.
    'controllers': ['controllers/main.py'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': '_post_init_sync_tools',
}
