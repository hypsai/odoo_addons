{
    "name": "OQL Web",
    "version":"1.4.2",
    "author": "Chris",
    "website": "https://github.com/chrisking94/odoo_addons/tree/main/oql_web",
    "license": "LGPL-3",
    "category": "Productivity/Apps",
    "summary": "Odoo web components.",
    "depends": ["oql"],
    "images": ["static/description/banner.png"],

    "data": [
        "security/ir.model.access.csv",
        "security/oql_workbench_security.xml",
        "views/oql_workbench.xml",
    ],

    "assets": {
        "web.assets_backend": [
            "oql_web/static/lib/codemirror/lib/*",
            "oql_web/static/lib/codemirror/addon/**/*",
            "oql_web/static/src/xml/*",
            "oql_web/static/src/css/oql_editor.css",
            "oql_web/static/src/css/oql_editor_widget.css",
            "oql_web/static/src/css/oql_search.css",
            "oql_web/static/src/css/oql_navbar_button.css",
            "oql_web/static/src/js/oql_highlight.js",
            "oql_web/static/src/js/oql_editor.js",
            "oql_web/static/src/js/oql_editor_widget.js",
            "oql_web/static/src/js/oql_search_bar.js",
            "oql_web/static/src/js/oql_navbar_button.js",
        ],
    },

    "installable": True,
}
