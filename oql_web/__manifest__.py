{
    "name": "OQL Web",
    "version":"1.5.1",
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
            "web/static/lib/jquery/jquery.js",
            "oql/static/lib/codemirror/lib/codemirror.css",
            "oql/static/lib/codemirror/addon/hint/show-hint.css",
            "oql/static/lib/codemirror/lib/codemirror.js",
            "oql/static/lib/codemirror/addon/hint/show-hint.js",
            "oql/static/src/css/oql_editor.css",
            "oql/static/src/js/oql_highlight.js",
            "oql/static/src/js/oql_editor.js",
            "oql_web/static/src/xml/*",
            "oql_web/static/src/css/oql_editor_widget.css",
            "oql_web/static/src/css/oql_search.css",
            "oql_web/static/src/js/oql_editor_widget.js",
            "oql_web/static/src/js/oql_search_bar.js",
        ],
    },

    "installable": True,
}
