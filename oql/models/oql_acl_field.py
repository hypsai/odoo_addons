# -*- coding: utf-8 -*-
# @Time         : 20:33 2026/5/9
# @Author       : Chris
# @Description  :
from typing import Literal, Set

from odoo import fields, models, api, tools

from ..compatible import model_flush


class OqlAclField(models.Model):
    """
    OQL field-level access control, aligned into Odoo's native field ACL.

    For a field of a model, the effective permission for a given mode is
    decided by the FIRST matching layer of the following precedence
    (highest first):

    1. oql read/write -- an explicit ``oql_acl_field`` row
       (``mac_id`` x ``field_id``) reachable through one of the user's
       ``ir.model.access`` rows. The row alone decides: it can **relax**
       (grant read/write even when ``field.groups`` / the default would deny)
       and it can **tighten** (deny even when ``field.groups`` would allow).
    2. odoo groups -- fields without an override row fall back to the
       ``groups`` attribute defined on the ORM field in code.
    3. oql default -- fields with neither an override row nor a ``groups``
       restriction fall back to the ``ir.model.access`` defaults
       ``perm_oql_fac_default_read`` / ``perm_oql_fac_default_write``.

    Related fields: Odoo copies the target field's ``groups`` onto the related
    field (``_related_groups`` is collected into ``related_attrs`` by
    ``setup_related``), so by default a related field is as restricted as the
    field it points to. An explicit ``oql_acl_field`` row for the related
    field breaks that inheritance (layer 1): the related field stays
    accessible regardless of whether the field it points to is accessible.
    """

    _name = "oql.acl.field"
    _description = "OQL Field Level Access Control"
    _rec_name = "field_id"

    mac_id = fields.Many2one("ir.model.access", "Model Access", required=True, ondelete="cascade")
    field_id = fields.Many2one("ir.model.fields", "Field", required=True, ondelete="cascade",
                               domain="[('model_id', '=', model_id)]")
    perm_read = fields.Boolean("Read Access")
    perm_write = fields.Boolean("Write Access")

    # Aux
    model_id = fields.Many2one(related="mac_id.model_id")

    _sql_constraints = [("mac_field_unique", "unique(mac_id, field_id)",
                         "Field must be unique in a model's field access collection.")]

    @api.model
    def perm_fields(self, model: str, mode: Literal["read", "write"]) -> Set[str]:
        """Check field access rights of the given model,
        and return all the fields that have given `mode` access right."""
        if self.env.su:
            # User root have all accesses
            return set(self.env[model]._fields)  # noqa
        return set(self._perm_fields(model, mode))

    @api.model
    @tools.ormcache('frozenset(self.env.user.groups_id.ids)', 'model', 'mode')
    def _perm_fields(self, model, mode):
        """Evaluate per-field access with precedence: oql override > field.groups > oql default.

        * Cached per user *group set*.
        * This method is strictly aligned with `base.check_field_access_rights`, they share
          identical access check logic.
        :type model: str
        :type mode: FieldMode
        :rtype: Set[str]
        """
        model_flush(self.env["ir.model.access"])
        model_flush(self, self._fields)  # noqa

        sql = f"""
        SELECT b.name,
            BOOL_OR(e.id IS NOT NULL)                                AS has_override,
            BOOL_OR(e.id IS NOT NULL AND d.perm_{mode} AND e.perm_{mode}) AS override_allowed,
            COALESCE(BOOL_OR(e.id IS NULL AND d.perm_{mode} AND d.perm_oql_fac_default_{mode}), FALSE) AS default_allowed
        FROM ir_model a
            JOIN ir_model_fields b ON a.id = b.model_id
             LEFT JOIN res_groups_users_rel c ON c.uid = %s
            LEFT JOIN ir_model_access d ON (a.id = d.model_id AND c.gid = d.group_id AND d.active)
            LEFT JOIN oql_acl_field e ON (d.id = e.mac_id AND b.id = e.field_id)
        WHERE a.model = %s
        GROUP BY b.id
        """
        self.env.cr.execute(sql, (self.env.uid, model))
        rows = self.env.cr.fetchall()
        # The three flags are aggregated over every (group, model access) path
        # of the user; a single True path wins for that flag.
        #
        # Multi-group semantics: layer 1 is "any explicit True path wins"
        # (relax); but once at least one explicit row exists for the field,
        # a field whose rows are all False is denied even if another group's
        # path has no row and would default to True. Tightening is therefore
        # sticky -- conservative by design, documented to avoid surprises.
        odoo_allowed = set(
            self.env[model].with_context(_oql_field_acl_escape=True)
            .check_field_access_rights(mode, None))
        _fields = self.env[model]._fields  # noqa
        field_names = set()
        for name, has_override, override_allowed, default_allowed in rows:
            # Layer 1: an explicit row governs alone.
            # * Note: It can relax past an inherited `field.groups` (related field)
            # or past the default, and it can also tighten below either of them.
            if has_override:
                if override_allowed:
                    field_names.add(name)
                continue
            # Layer 2: a code-level `groups` restriction decides on its own --
            # the oql default must not grant past it, only an override row can.
            # * Note: core access compute is performed by odoo's
            #   `check_field_access_rights` method.
            field = _fields.get(name)
            if field and field.groups:
                if name in odoo_allowed:
                    field_names.add(name)
                continue
            # Layer 3: neither override nor groups -> OQL model level default field access.
            if default_allowed:
                field_names.add(name)

        if mode == "read" and "id" not in field_names:
            field_names.add("id")  # ID is always readable.
        return field_names

    # ---- Cache invalidation ----
    # Odoo 15: clear_caches() clears the shared registry cache (see the note
    # in res_users.py "clear_caches methods pretty much just end up calling
    # Registry._clear_cache"). The result of `_perm_fields` depends on this
    # table and on `ir.model.access`, so invalidate on any write here and on
    # any change of `ir.model.access` (handled in ir_model_access.py).

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.clear_caches()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.clear_caches()
        return result

    def unlink(self):
        result = super().unlink()
        self.clear_caches()
        return result
