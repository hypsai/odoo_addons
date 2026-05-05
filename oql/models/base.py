import logging

from odoo import models, api
from odoo.exceptions import UserError

from ..oql import reader, OqlTransformer, TermChipInfo

_logger = logging.getLogger(__name__)


class OqlBase(models.AbstractModel):
    _inherit = "base"

    @api.model
    def searcho(self, oql_where: str):
        """Search with OQL."""
        try:
            result = reader.query(oql_where, OqlTransformer(self.env, self._name))
            return result
        except Exception as e:
            _logger.debug(f"OQL query error: {e}", exc_info=True)
            raise UserError(str(e))

    @api.model
    def searcho_ids(self, oql_where: str):
        """Search with OQL and return record ids."""
        return self.searcho(oql_where).ids

    @api.model
    def hinto(self, field: str, query: str, cursor: int, limit=100):
        """
        Get OQL code completion hints. Typically used by frontends.
        :param field: The field in this model the query belongs to.
        :param query: The query to be completed.
        :param cursor: The cursor position in query to generate completion hints.
        :param limit: Count limit of hints.
        :return: List of hint.
        """
        pass

    def _valid_field_parameter(self, field, name):
        if name == "oql_model":
            return True
        return super()._valid_field_parameter(field, name)

    def __oql_bin__(self, term: TermChipInfo, opr: str, value, value_term: TermChipInfo):
        """
        Implement this method in subclasses.
        :return: `None` means `opr` not implemented.
        """
        pass
