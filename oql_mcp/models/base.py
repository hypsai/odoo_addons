import logging

from odoo import models, api
from odoo.addons.mcp_base import mcp_tool

_logger = logging.getLogger(__name__)


class OqlMcpBase(models.AbstractModel):
    _inherit = "base"

    @mcp_tool
    @api.model
    def oql_mcp_query(self, oql: str):
        """Execute OQL statement and return records as dicts.

        OQL is a PostgreSQL-like query language over the Odoo ORM.

        Synopsis:
            [ WITH CONTEXT name = value [, ...] ] statement

            statement:
                FROM model SELECT [TRANSLATE] ( * | reader [ AS alias ] [, ...] )
                    [ WHERE [TRANSLATE] condition ]
                    [ ORDER BY field [ ASC | DESC ] [, ...] ]
                    [ LIMIT n ] [ OFFSET n ]
              | UPDATE model SET [TRANSLATE] field = value [, ...]
                    [ WHERE [TRANSLATE] condition ] [ LIMIT n ]
              | INSERT INTO model [TRANSLATE] ( field [, ...] )
                    VALUES ( value [, ...] ) [, ...]
              | DELETE FROM model [ WHERE [TRANSLATE] condition ] [ LIMIT n ]

            reader:     [ @agg ] path ( .method(args) | [index] )*  |  func(args)
                        e.g. tag_ids[0].name, @tag_ids.mapped('name'), lower(name), count(@tag_ids)
            condition:  condition AND/OR condition | NOT condition | ( condition ) | field
                        | field OP value | field[value] | field IS [NOT] NULL | _sizeof_ field
            OP:         = | != | <> | < | <= | > | >= | [NOT] LIKE | [NOT] ILIKE | [NOT] IN
                        | =LIKE | =ILIKE | =? | CHILD_OF | PARENT_OF
            value:      'text' ('' escapes a quote) | number | true | false | null
                        | ( value [, ...] )            -- id tuple, links x2many
                        | [ value | cmd , ... ]        -- JSON array, may hold ORM commands
                        | { field: value [, ...] }     -- JSON object
            cmd:        link n | unlink n | set [ n [, ...] ] | create object | update n object | delete n
            object:     { field: value [, ...] }    -- nested JSON-like object, keys unquoted,
                                                        values may nest objects/arrays/cmds

        Notes:
            1. SELECT must carry LIMIT (use OFFSET for paging).
            2. Fields are Odoo dot paths, e.g. company_id.name; Terms/Aliases (virtual fields) allowed.
            3. `id` is added to results automatically.
            4. LIKE/ILIKE match substrings (no `%`); use =LIKE/=ILIKE for `%` wildcard patterns.
            5. TRANSLATE reads/writes field values in the user's language.
        Use `oql_mcp_hint` to discover accessible models, fields, or candidate values for a field.

        :return: List of record dictionaries.
        """
        return self.oql(oql)

    @mcp_tool
    @api.model
    def oql_mcp_hint(self, hintable_oql: str, verbose: int = 0):
        """Hint OQL at specified hint points.
        :param hintable_oql: Partial OQL with hint points.
          Grammar: 'Partial OQL ?hint_options'
            hint_options: A JSON dict that contains keys:
              name: str. Name for the hint point. It will be used as key in hint result.
              keywords: List[str]. A list of keywords used search for possible candidates.
              limit: int. Max hint count.
              offset: Optional[int]. Used for paging when there are too many hint items.
          e.g.  'FROM product.product SELECT ?{"name": "sel_field", "keywords": ["code", "de"], "limit": 10}'
                'FROM product.?{"name": "model", "keywords": ["te"], "limit": 5}'
                'FROM product.product SELECT id where default_code like ?{"name": "default_code", "keywords": ["danner"], "limit": 40}'
          * Note: hint point can only be placed at the end of a partial OQL.
        :return: {hint_point_name: {hints: [{type: ..., value: ..., desc: ...}]}}
        :param verbose: Verbosity level of hints. Use lower level as priority.
            - 0: list of candidate strings. e.g. ['name', ...]
            - 1: list of candidate dict with value, description. e.g. [{'value': 'name', 'desc': 'Product Name'}, ...]
            - 2: list of candidate dict with value, description, type. e.g. [{'value': 'name', 'desc': 'Product Name', 'type': 'field'}, ...]
        """
        hintx = self.oql_hintx(hintable_oql)
        # Align hint verbosity with `verbose` parameter.
        for obj in hintx.values():
            hints = obj["hints"]
            if verbose == 0:
                hints = [x["value"] for x in hints]
            elif verbose == 1:
                hints = [{
                    "value": x["value"],
                    "desc": x["desc"],
                } for x in hints]
            obj["hints"] = hints
        return hintx
