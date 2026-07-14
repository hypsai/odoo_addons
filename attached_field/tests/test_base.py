# -*- coding: utf-8 -*-
# @Time         : 15:18 2026/2/25
# @Author       : Chris
# @Description  :
import os

from odoo import fields, models
from odoo.tests import TransactionCase, HttpCase
from odoo.tools import convert_file


class ConfidenceTestAge(models.Model):
    _name = 'confidence.test.age'
    _description = 'Simple Age Confidence Test'
    _confidence = True

    name = fields.Char("Name")
    age = fields.Integer("Age", confidence=True)


class TestBase(HttpCase):

    def setUp(self):
        super().setUp()

        # 1 Register temporary models.
        for Model in [ConfidenceTestAge]:
            model_name = Model._name
            self.registry.models[model_name] = Model._build_model(
                self.registry, self.cr
            )
            self.registry.setup_models(self.cr)
            self.registry.init_models(
                self.cr, [model_name], {"module": "test"}, install=True
            )
            self.env['ir.model.access'].create({
                'name': 'access_confidence_test_age',
                'model_id': self.env['ir.model']._get_id('confidence.test.age'),
                'group_id': self.env.ref('base.group_user').id,
                'perm_read': True,
                'perm_write': True,
                'perm_create': True,
                'perm_unlink': True,
            })

        # 2 Load temporary views.
        # TODO: No working yet, the views is not viable on ui.
        for view_name in ['test_views.xml']:
            file_path = os.path.join(os.path.dirname(__file__), view_name)

            # Manually parse and load the file into the database
            # Use 'init' mode to treat it as a fresh installation
            convert_file(
                self.cr,
                'attached_field',  # The module name to associate with XMLIDs
                file_path,
                {},  # idref (usually empty for new files)
                mode='init',
                noupdate=False,
                kind='xml'
            )

        # 3 Clear cache.
        # 3.1 Clear the ORM cache (important for menus)
        self.env['ir.ui.menu'].clear_caches()
        # 3.2 Re-initialize the environment to pick up the new records
        self.env.registry.clear_caches()
        self.env.registry.signal_changes()
