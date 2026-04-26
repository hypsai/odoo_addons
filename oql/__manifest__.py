{
    "name": "OQL",
    "version": "15.0.1.0.0",
    "author": "Chris",
    "website": "https://github.com/chrisking94/odoo_addons/tree/main/oql",
    "license": "LGPL-3",
    "category": "Productivity/Apps",
    "summary": "Query ORM model with SQL-Style language.",
    'depends': ['base'],
    'images': ['static/description/banner.png'],
    'external_dependencies': {
        'python': ['lark'],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/oql_term_views.xml",
        "views/oql_alias_views.xml",
        "views/oql_menu.xml",
    ],

    "installable": True,
}
