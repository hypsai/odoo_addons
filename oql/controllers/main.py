# -*- coding: utf-8 -*-
# @Time         : 10:00 2026/5/16
# @Author       : Chris
# @Description  :
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class McpController(http.Controller):

    @http.route('/oql/query', type='json', auth='user', csrf=False)
    def oql_query(self, query):
        """Execute OQL query and return result as list of dict."""
        _logger.debug(f"OQL query from user {request.env.user.name} (ID {request.env.uid}): {query}")
        res = request.env["base"].oql(query)
        return res
