# -*- coding: utf-8 -*-
# @Time         : 15:41 2026/2/24
# @Author       : Chris
# @Description  :
from odoo import http
from odoo.http import request
import os


class FileController(http.Controller):
    @http.route('/web/static/lib/ace/mode-yaml.js', type='http', auth='none')
    def get_ace_model_yaml(self):
        # Path to your file in the custom addon
        addon_path = os.path.join(os.path.dirname(__file__), '../static/src/js/lib/ace/mode-yaml.js')

        if os.path.exists(addon_path):
            with open(addon_path, 'rb') as f:
                return request.make_response(
                    f.read(),
                    headers=[('Content-Type', 'application/javascript')]
                )
        return request.not_found()
