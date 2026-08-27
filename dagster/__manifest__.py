# -*- coding: utf-8 -*-
{
    'name': 'Dagster',
    "version":"1.0.1",

    'summary': 'Generic Dagster job/run management plugin, independent of any business module.',

    'description': """
    Dagster
    =======

    A generic plugin to manage Dagster jobs and their runs from Odoo.

    Models:

    * ``dagster.job``: a Dagster job defined by its key, with an optional
      ``run_config_tmpl`` (YAML template supporting variable substitution).
    * ``dagster.run``: a single Dagster run (run id) linked to a job.

    The ``run`` / ``call`` methods are extension points. Actual submission to a
    Dagster instance is delegated to ``get_dagster_client`` so each deployment
    can plug in its own client (default is a stub, no network calls).

    Data migration:
    ----------------
    Existing ``fishing.dagster.job`` / ``fishing.dagster.run`` records can be
    migrated to ``dagster.job`` / ``dagster.run`` by an external script. The
    field layouts are kept compatible on purpose.
    """,

    'author': 'Hypsai Tech',
    'website': 'https://github.com/hypsai/odoo_addons/tree/main/dagster',
    'license': 'LGPL-3',

    'category': 'Productivity',
    'version':'1.0.1',

    'depends': ['base', 'web', 'hypsai', 'web_widget_yaml'],

    'external_dependencies': {
        'python': ['yaml'],
    },

    'data': [
        'security/ir.model.access.csv',
        'views/dagster_job_views.xml',
        'views/dagster_menu.xml',
    ],

    'installable': True,
    'application': False,
}
