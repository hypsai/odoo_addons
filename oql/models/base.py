import logging
from typing import List, Optional, Union, override, Set

from odoo import models, api, _
from odoo.exceptions import UserError, AccessError

from ..oql import reader, OqlTransformer, OqlDomain

_logger = logging.getLogger(__name__)


class OqlBase(models.AbstractModel):
    _inherit = "base"

    @api.model
    @api.returns('self',
                 upgrade=lambda self, value, args, offset=0, limit=None, order=None, count=False: value if count else self.browse(value),
                 downgrade=lambda self, value, args, offset=0, limit=None, order=None, count=False: value if count else value.ids)
    def searcho(self, domain: Union[str, list], offset=0, limit=None, order=None, count=False):
        """OQL style `search_read`. Fully compatible with odoo built-in `search_read`.
        :param domain: Can be:
            1. OQL where clause
            2. Odoo domain
        :param offset:
        :param limit:
        :param order:
        :param count:
        """
        if isinstance(domain, str):
            try:
                recs = reader.search(self, domain, offset, limit, order, count)
            except Exception as e:
                _logger.debug(f"OQL query error: {e}", exc_info=True)
                raise UserError(str(e))
        else:
            recs = self.search(domain, offset, limit, order)
        return recs

    def reado(self, fields=None, load='_classic_read'):
        """OQL style `read` counterpart. `fields` could be like ["xxx.yyy as zzz", "cccc"]"""
        return reader.read(self, fields, load)

    @api.model
    def search_reado(self, domain=None, fields=None, offset=0, limit=None, order=None, **read_kwargs):
        """
        OQL style `search_read`. Fully compatible with odoo built-in `search_read`.
        :param domain: Can be:
            1. OQL where clause
            2. Odoo domain
        :param fields: Supports format `["xxx.yyy as zzz", "cccc"]`
        :param offset:
        :param limit:
        :param order:
        """
        recs = self.searcho(domain, offset, limit, order)
        return recs.reado(fields, **read_kwargs)

    @api.model
    def searcho_ids(self, domain: Union[str, list]):
        """Search with OQL and return record ids.
        :param domain: Can be:
            1. OQL where clause
            2. Odoo domain
        """
        return self.searcho(domain).ids

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

    @api.model
    def oql_hintx(self, hintable_oql: str):
        """
        Hint OQL at specified hint points.
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
        """
        raise NotImplementedError("Install `oql_pro` from odoo app store or implement with a custom addon.")

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
        :return: `None` means fall through to built-in logic for `opr`.
        """
        pass

    @api.model
    @override
    def check_field_access_rights(self, operation, fields) -> List[str]:
        """Align Odoo's native field access check with `oql.acl.field`.

        `oql.acl.field` becomes the single source of truth for field
        read/write, with precedence: oql override > field.groups > oql
        default. Native ORM operations (read, write, create, prefetch,
        fields_get...) and OQL queries then share the exact same per-field
        permission evaluation.
        """
        # 1 Special code path for oql `perm_fields`.
        if self.env.context.get("_oql_field_acl_escape", False):
            return super().check_field_access_rights(operation, fields)

        # 2 Superuser owns everything.
        if self.env.su:
            return fields or list(self._fields)  # noqa

        # 3 OQL access checker takes control.
        if operation != "read" and operation != "write":
            raise Exception(f"Unknown field operation `{operation}`.")
        allowed: Set[str] = self.env['oql.acl.field'].perm_fields(self._name, operation)
        if fields:
            denied = [x for x in fields if x not in allowed]
            if denied:
                self._odoo_access_raise(operation, denied)
            return fields
        return list(allowed)

    def _odoo_access_raise(self, operation, invalid_fields):
        """Code from this method is completely copied from odoo server's source code.
        !!! Do not modify it manually !!!
        """
        _logger.info('Access Denied by ACLs for operation: %s, uid: %s, model: %s, fields: %s',
                     operation, self._uid, self._name, ', '.join(invalid_fields))

        description = self.env['ir.model']._get(self._name).name
        if not self.env.user.has_group('base.group_no_one'):
            raise AccessError(
                _('You do not have enough rights to access the fields "%(fields)s" on %(document_kind)s (%(document_model)s). ' \
                  'Please contact your system administrator.\n\n(Operation: %(operation)s)') % {
                    'fields': ','.join(list(invalid_fields)),
                    'document_kind': description,
                    'document_model': self._name,
                    'operation': operation,
                })

        def format_groups(field):
            if field.groups == '.':
                return _("always forbidden")

            anyof = self.env['res.groups']
            noneof = self.env['res.groups']
            if field.groups:  # !!! This is a line added to bypass empty field groups issue specially in OQL integration.
                for g in field.groups.split(','):
                    if g.startswith('!'):
                        noneof |= self.env.ref(g[1:])
                    else:
                        anyof |= self.env.ref(g)
            strs = []
            if anyof:
                strs.append(_("allowed for groups %s") % ', '.join(
                    anyof.sorted(lambda g: g.id)
                    .mapped(lambda g: repr(g.display_name))
                ))
            if noneof:
                strs.append(_("forbidden for groups %s") % ', '.join(
                    noneof.sorted(lambda g: g.id)
                    .mapped(lambda g: repr(g.display_name))
                ))
            return '; '.join(strs)

        raise AccessError(_("""The requested operation can not be completed due to security restrictions.

        Document type: %(document_kind)s (%(document_model)s)
        Operation: %(operation)s
        User: %(user)s
        Fields:
        %(fields_list)s""") % {
            'document_model': self._name,
            'document_kind': description or self._name,
            'operation': operation,
            'user': self._uid,
            'fields_list': '\n'.join(
                '- %s (%s)' % (f, format_groups(self._fields[f]))
                for f in sorted(invalid_fields)
            )
        })
