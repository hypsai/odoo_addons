{
    "name": "OQL Web",
    "version":"1.1.0",
    "author": "Chris",
    "website": "https://github.com/chrisking94/odoo_addons/tree/main/oql_web",
    "license": "LGPL-3",
    "category": "Productivity/Apps",
    "summary": "Odoo web components.",
    "depends": ["oql"],
    "images": ["static/description/banner.png"],

    "assets": {
        "web.assets_backend": [
            "oql_web/static/lib/codemirror/lib/*",
            "oql_web/static/lib/codemirror/addon/**/*",
            "oql_web/static/src/xml/*",
            "oql_web/static/src/css/*",
            "oql_web/static/src/js/*",
        ],
    },

    "installable": True,
}
