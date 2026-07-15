{
    "name": "Attached Field",
    "version": "15.0.1.0.0",
    "category": "Tools",
    "summary": "Dynamically attach fields to models from action methods.",
    "description": """
        Attached Field
        ==============
        Use the ``@attached`` decorator on action methods to dynamically add
        fields to the target model of a returned view action.  Compute and
        inverse methods are defined on the invoker model.

        Example::

            @attached(note=fields.Char(compute='_compute_note'))
            def action_open(self):
                return self.env['other.model'].search([])
    """,
    "author": "Your Company",
    "website": "https://www.yourcompany.com",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "demo": [
        "views/demo_views.xml",
        "data/demo_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "attached_field/static/src/css/attached.css",
        ],
        "web.qunit_suite_tests": [
        ],
    },
    "installable": True,
    "application": False,
    "license": "OPL-1",
}