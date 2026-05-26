{
    "name": "OQL Web",
    "version":"1.5.0",
    "author": "Chris",
    "website": "https://github.com/chrisking94/odoo_addons/tree/main/oql_web",
    "license": "LGPL-3",
    "category": "Productivity/Apps",
    "summary": "Odoo web components.",
    "depends": ["oql"],
    "images": ["static/description/banner.png"],

    "data": [
    ],

    "assets": {
        "web.assets_backend": [
            "oql_web/static/src/xml/*",
            "oql_web/static/src/css/oql_editor_widget.css",
            "oql_web/static/src/css/oql_search.css",
            "oql_web/static/src/js/oql_editor_widget.js",
            "oql_web/static/src/js/oql_search_bar.js",
        ],
    },

    "installable": True,
}
