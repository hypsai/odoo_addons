import logging

from odoo import models, api
from odoo.addons.mcp_base import mcp_tool

_logger = logging.getLogger(__name__)


class OqlMcpBase(models.AbstractModel):
    _inherit = "base"

    @mcp_tool
    @api.model
    def oql_mcp_query(self, oql: str):
        """Execute OQL search and return records as dicts.

        OQL is a PostgreSQL-like query language for Odoo. It supports dot paths (e.g., `company.name`) and virtual fields (Terms/Aliases).
        Differences from SQL:
            1. FROM clause is placed at start of a query string.
            2. `id` field will be added to result automatically.
        OQL Example:
            FROM product.product
            SELECT name, default_code
            WHERE Brand = 'Danner' and Waterproof and list_price > 1000
        Use `oql_hint` only when you need auto-completion or are unsure of the syntax.

        :return: List of record dictionaries.
        """
        return self.oql(oql)

    @mcp_tool
    @api.model
    def oql_mcp_hint(self, partial_oql: str, cursor: int = None, limit=30):
        """Auto-complete INCOMPLETE OQL fragments. NOT for executing queries.

        Use when constructing a query to find valid fields or values matching the current input.
        Example: partial_oql="from res.partner select id where name = ma" -> returns ['Mary', 'JackMa'].

        :param partial_oql: The unfinished text typed so far. NEVER a complete statement.
        :param cursor: Typing position (zero-based). None means end of string.
        :param limit: Max candidates to return (default: 30).
        """
        return self.oql_hint(partial_oql, cursor, limit)
