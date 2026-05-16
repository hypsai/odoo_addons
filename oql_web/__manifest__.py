{
    "name": "OQL Web",
    "version":"1.1.2",
    "author": "Chris",
    "website": "https://github.com/chrisking94/odoo_addons/tree/main/oql_web",
    "license": "LGPL-3",
    "category": "Productivity/Apps",
    "summary": "Odoo web components.",
    "depends": ["oql"],
    "images": ["static/description/banner.png"],

    "data": [
        "views/oql_workbench.xml",
    ],

    "assets": {
        "web.assets_backend": [
            "oql_web/static/lib/codemirror/lib/*",
            "oql_web/static/lib/codemirror/addon/**/*",
            "oql_web/static/lib/codemirror/mode/oql/oql.js",
            "oql_web/static/src/xml/*",
            "oql_web/static/src/css/*",
            "oql_web/static/src/js/*",
        ],
    },

    "installable": True,
}
