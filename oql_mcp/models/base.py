import logging

from odoo import models, api
from odoo.addons.mcp_base import mcp_tool

_logger = logging.getLogger(__name__)


class OqlMcpBase(models.AbstractModel):
    _inherit = "base"

    @mcp_tool
    @api.model
    def oql_mcp_select(self, model: str, where: str, fields=None, offset=0, limit=None, order=None, **read_kwargs):
        """Execute OQL search and return records as dicts.

        OQL is a PostgreSQL-compatible query language for Odoo. It supports dot paths (e.g., `company.name`) and virtual fields (Terms/Aliases).
        Use `oql_hint` only when you need auto-completion or are unsure of the syntax.

        :param model: Target model (e.g., 'res.partner').
        :param where: Complete OQL WHERE clause. Must be a valid, executable statement.
        :param fields: List of fields to return. Defaults to all.
        :param offset: Records to skip (default: 0).
        :param limit: Max records to return (default: no limit).
        :param order: Sort columns (e.g., 'name desc').
        :param read_kwargs: Extra args for `read()` (e.g., load='' to skip name_get).
        :return: List of record dictionaries.
        """
        this = self.env[model]
        records = this.searcho(where)
        if not records:
            return []

        if fields and fields == ['id']:
            # shortcut read if we only want the ids
            return [{'id': record.id} for record in records]

        # read() ignores active_test, but it would forward it to any downstream search call
        # (e.g. for x2m or function fields), and this is not the desired behavior, the flag
        # was presumably only meant for the main search().
        # TODO: Move this to read() directly?
        if 'active_test' in this._context:
            context = dict(this._context)
            del context['active_test']
            records = records.with_context(context)

        result = records.read(fields, **read_kwargs)
        if len(result) <= 1:
            return result

        # reorder read
        index = {vals['id']: vals for vals in result}
        return [index[record.id] for record in records if record.id in index]

    @mcp_tool
    @api.model
    def oql_mcp_hint(self, model: str, partial_input: str, cursor: int = None, limit=30):
        """Auto-complete INCOMPLETE OQL fragments. NOT for executing queries.

        Use when constructing a query to find valid fields or values matching the current input.
        Example: partial_input="name = ma" -> returns ['Mary', 'JackMa'].

        :param model: Target model (e.g., 'res.partner').
        :param partial_input: The unfinished text typed so far. NEVER a complete statement.
        :param cursor: Typing position (zero-based). None means end of string.
        :param limit: Max candidates to return (default: 30).
        """
        return self.env[model].hinto(partial_input, cursor, limit)
