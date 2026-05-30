{
    "name": "OQL - Odoo Query Language",
    "version":"1.9.8",
    "author": "Chris",
    "website": "https://github.com/chrisking94/odoo_addons/tree/main/oql",
    "license": "LGPL-3",
    "category": "Technical Settings",
    "summary": "Query Odoo models with intuitive, business-focused syntax instead of complex technical domains.",
    "description": """
OQL (Odoo Query Language) transforms how you query data in Odoo.

Key Features:
- Write queries in business language (e.g., "Waterproof and Size = '40'")
- Configure Terms and Aliases through the UI - no coding required
- SQL-like syntax with AND, OR, IN operators
- Perfect for complex product searches and user-facing filters

Example:
    products = env['product.product'].searcho(
        "CatgS = 'Boot' and Brand = 'Danner' and EuShoeSize in ('40', '40.5') and Waterproof"
    )

Menu: Settings > Technical > OQL
    """,
    'depends': ['base'],
    'images': ['static/description/banner.png'],
    "data": [
        "security/ir.model.access.csv",
        "security/oql_workbench_security.xml",
        "views/oql_term_views.xml",
        "views/oql_alias_views.xml",
        "views/ir_model_access_views.xml",
        "views/oql_menu.xml",
        "views/oql_workbench.xml",
    ],

    "assets": {
        "web.assets_backend": [
            "web/static/lib/jquery/jquery.js",
            "oql/static/lib/codemirror/lib/codemirror.css",
            "oql/static/lib/codemirror/addon/hint/show-hint.css",
            "oql/static/lib/codemirror/lib/codemirror.js",
            "oql/static/lib/codemirror/addon/hint/show-hint.js",
            "oql/static/src/css/oql_editor.css",
            "oql/static/src/js/oql_highlight.js",
            "oql/static/src/js/oql_editor.js",
            "oql/static/src/css/oql_navbar_button.css",
            "oql/static/src/js/oql_navbar_button.js",
        ],
    },

    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
