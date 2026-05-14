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
        Attention: You must use LIMIT clause for any query. Use offset together with limit if you need paginated result.

        OQL is a PostgreSQL-like query language for Odoo. It supports dot paths (e.g., `company.name`) and virtual fields (Terms/Aliases).
        Differences from SQL:
            1. FROM clause is placed at start of a query string.
            2. It uses Odoo domain operators such as 'like', '=like', etc. Be careful about this!!!
            3. `id` field will be added to result automatically.
        OQL Example:
            FROM product.product
            SELECT name, default_code, tag_ids.name
            WHERE Brand = 'Danner' and Waterproof and list_price > 1000
            LIMIT 80
            OFFSET 160
        Use `oql_mcp_hint` to find out valid model and field you have access to, or valid candidate values for a field.

        :return: List of record dictionaries.
        """
        return self.oql(oql)

    @mcp_tool
    @api.model
    def oql_mcp_hint(self, partial_oql: str, cursor: int = None, limit=30, verbose=0):
        """Auto-complete INCOMPLETE OQL fragments. NOT for executing queries.

        Use to find out valid model or field or value candidates at given cursor position in `partial_oql`.
        Example: partial_oql="from res.partner select id where name = ma" -> returns ['Mary', 'JackMa'].
        The string before cursor can be an incomplete name or value, it will be used to filter and sort candidates by string similarity.

        * Note: Hint follows access control rules, so you can use this to find out models or fields that you have access to.
        Example:
            1. partial_oql="from res.p" will return a model list you have read access to, such as: ['res.partner', 'res.company']
            2. partial_oql="from res.partner select na" will return fields you have read access to, such as: ['name', 'display_name']
            3. partial_oql="from res.partner select id where name = ma", result example: ['Mary', 'Ema', ...]

        :param partial_oql: The unfinished text typed so far. NEVER a complete statement.
        :param cursor: Typing position (zero-based). None means end of string.
        :param limit: Max candidates to return (default: 30).
        :param verbose: Verbosity level of hints.
            - 0: list of candidate strings. e.g. ['name', ...]
            - 1: list of candidate dict with value, description. e.g. [{'value': 'name', 'desc': 'Product Name'}, ...]
            - 2: list of candidate dict with value, description, type. e.g. [{'value': 'name', 'desc': 'Product Name', 'type': 'field'}, ...]
        """
        hints = self.oql_hint(partial_oql, cursor, limit)
        if verbose == 0:
            return [x["value"] for x in hints]
        elif verbose == 1:
            return [{
                "value": x["value"],
                "desc": x["desc"],
            } for x in hints]
        else:
            return hints
