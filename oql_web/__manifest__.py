{
    "name": "OQL Web",
    "version": "15.0.1.0.0",
    "author": "Chris",
    "website": "https://github.com/chrisking94/odoo_addons/tree/main/oql_web",
    "license": "LGPL-3",
    "category": "Productivity/Apps",
    "summary": "Odoo web components.",
    "depends": ["oql"],

    'assets': {
        'web.assets_backend': [
            "oql/static/lib/codemirror/lib/*",
            "oql/static/lib/codemirror/addon/**/*",
            "oql/static/src/xml/*",
            "oql/static/src/css/*",
            "oql/static/src/js/*",
        ],
    },

    "installable": True,
}
