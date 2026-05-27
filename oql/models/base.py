import logging
from typing import List, Optional

from odoo import models, api
from odoo.exceptions import UserError

from ..oql import reader, OqlTransformer, OqlDomain

_logger = logging.getLogger(__name__)


class OqlBase(models.AbstractModel):
    _inherit = "base"

    @api.model
    def searcho(self, oql_where: str):
        """Search with OQL."""
        prefix = f"FROM {self._name} SELECT id WHERE "
        try:
            result = self.oql(f"{prefix}{oql_where}")
            return self.browse([x["id"] for x in result])
        except Exception as e:
            _logger.debug(f"OQL query error: {e}", exc_info=True)
            raise UserError(str(e))

    @api.model
    def searcho_ids(self, oql_where: str):
        """Search with OQL and return record ids."""
        return self.searcho(oql_where).ids

    @api.model
    def hinto(self, partial_oql_where: str, cursor: int = None, limit=100, offset=0) -> dict:
        """
        Get OQL code completion hints.
        * Note: FROM clause is defaulted to `self._name`.
        :param partial_oql_where: A complete or incomplete OQL where clause criteria.
        :param cursor: The cursor position in query to generate completion hints.
        :param limit: Count limit of hints.
        :param offset: Hint item index offset.
        :return: List of hint.
        """
        prefix = f"FROM {self._name} SELECT id WHERE "
        oql = f"{prefix}{partial_oql_where}"
        cursor = None if cursor is None else len(prefix)+cursor
        return self.oql_hint(oql, cursor, limit, offset)

    @api.model
    def oql(self, oql: str) -> List[dict]:
        """
        Execute an OQL query.
        """
        return reader.query(oql, OqlTransformer(self.env))

    @api.model
    def oql_hint(self, partial_oql: str, cursor: int = None, limit=100, offset=0) -> dict:
        """
        Hint an OQL query at given `cursor`.
        * Note: This method is implemented in `oql_pro`, a professional addon for oql.
            You can find it in Odoo App Store. Link: https://apps.odoo.com/apps/modules/15.0/oql_pro
        :param partial_oql: A complete or incomplete OQL query string.
        :param cursor: The cursor position in query to generate completion hints.
        :param limit: Count limit of hints.
        :param offset: Offset of full hint list, used to paginate.
        :return: A page of hints.
        {
            "hints": [{'type': 'xxx', 'value': 'yyy', 'desc': 'zzz'}, ...],  // Hints in page.
            "total: 1099,  // Total number of full hint list.
        }
        """
        pass

    def _valid_field_parameter(self, field, name):
        if name == "oql_model":
            return True
        return super()._valid_field_parameter(field, name)

    def __oql_bin__(self,
                    domain: Optional[OqlDomain],
                    field: Optional[str],
                    opr: str,
                    value,
                    value_domain: Optional[OqlDomain]):
        """
        Implement this method in subclasses.
        :param self: Records pre-selected with `domain`. It will be emtpy recordset when `domain` is None.
        :param domain: Domain for left operand `self`.
        :param field: dot-style field path for the binary expression. `None` means evaluate on the recordset itself.
        :param opr: Odoo operator.
        :param value: Right operand, could be scalar or list or RecordSet or RecordSets.
        :param value_domain: Domain of the right operand, available only when right operand is RecordSet.
        :return: `None` means `opr` not implemented.
        """
        pass
