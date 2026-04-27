{
    'name': 'Web Widget YAML',
    'summary': 'Adds a YAML code editor widget to form views using Ace Editor',
    'version': '15.0.1.0.0',
    'category': 'Web',
    'author': 'Chris',
    'website': 'https://github.com/chrisking94/odoo_addons/tree/main/web_widget_yaml',
    'license': 'LGPL-3',
    'depends': ['web'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'web_widget_yaml/static/src/js/yaml_editor.js',
        ],
    },
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'application': False,
    'description': """
    Web Widget YAML
    ===============
    This module extends the standard Odoo Ace Editor to provide a dedicated YAML 
    widget. 

    Key Improvement:
    ----------------
    Unlike the standard Ace implementation in Odoo 15, this widget allows 
    developers to pass Ace Editor configurations directly through the `options` 
    attribute in the XML view.

    Usage:
    ------
    .. code-block:: xml

        <field name="code_snippet" widget="yaml" options="{'fontSize': 14, 'theme': 'monokai', 'minLines': 15}"/>
        """,
}