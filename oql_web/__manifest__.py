{
    "name": "Advanced Search",
    "version":"1.5.3",
    "author": "Hypsai Tech",
    "website": "https://github.com/hypsai/odoo_addons/tree/main/oql_web",
    "license": "LGPL-3",
    "category": "Productivity/Apps",
    "summary": "Text-based search bar with syntax highlighting and autocomplete.",
    "depends": ["oql"],
    "images": ["static/description/banner.png"],

    "data": [
    ],

    "assets": {
        "web.assets_backend": [
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
