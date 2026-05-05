import logging

from odoo import models, api
from odoo.addons.mcp_base import mcp_tool

_logger = logging.getLogger(__name__)


class OqlMcpBase(models.AbstractModel):
    _inherit = "base"

    @mcp_tool
    def oql_search(self, model: str, where=None, fields=None, offset=0, limit=None, order=None, **read_kwargs):
        """Search with OQL where clause and return given fields as dicts.

        :param model: Target model to query, such as 'res.partner'.
        :param where: Search where clause in OQL (Odoo Query Language) grammar.
            Defaults to an empty domain that will match all records.
            OQL grammar is similar to SQL. But in addition, It:
                - supports dot path for field access, e.g. company.name = 'MyCompany'
                - adds new concepts Term (preselected records from other model) and Alias (field path short name)
                  They can be both treated as virtual fields and used like normal fields.
            You can use `get_oql_hints` tool to find out available fields, terms, aliases, values at current cursor.
        :param fields: List of fields to read, see ``fields`` parameter in :meth:`read`.
            Defaults to all fields.
        :param int offset: Number of records to skip, see ``offset`` parameter in :meth:`search`.
            Defaults to 0.
        :param int limit: Maximum number of records to return, see ``limit`` parameter in :meth:`search`.
            Defaults to no limit.
        :param order: Columns to sort result, see ``order`` parameter in :meth:`search`.
            Defaults to no sort.
        :param read_kwargs: All read keywords arguments used to call read(..., **read_kwargs) method
            E.g. you can use search_read(..., load='') in order to avoid computing name_get
        :return: List of dictionaries containing the asked fields.
        :rtype: list(dict).
        """
        this = self.env[model]
        records = this.search(where or [], offset=offset, limit=limit, order=order)
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
    def get_oql_hints(self, field: str, query: str, cursor: int, limit=100):
        return super().get_oql_hints(field, query, cursor, limit)
