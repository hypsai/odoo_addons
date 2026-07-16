# -*- coding: utf-8 -*-
# @Time         : 12:01 2026/07/16
# @Author       : Chris
# @Description  : Persist attached field meta.
import json
import logging
from typing import Dict, List

from odoo import models, fields, api
from odoo.tools import table_exists

from ..util import RawAttachedField

_logger = logging.getLogger(__name__)

# Per-database cache: {dbname: bool} — avoids information_schema check on every model.
_table_exists_cache = {}


class AttachedFieldRegistry(models.Model):
    _name = 'attached.field.registry'
    _description = 'Persistent store for @attached fields (multi-worker safe)'

    model_name = fields.Char(required=True, index=True)
    field_name = fields.Char(required=True)
    field_type = fields.Char(required=True, help="e.g. 'odoo.fields.Char'")
    field_args = fields.Text(required=True)           # JSON string of field kwargs
    invoker_model = fields.Char(required=True)
    action_method = fields.Char(required=True)
    user_field_name = fields.Char(required=True)

    _sql_constraints = [
        ('unique_field_per_model', 'UNIQUE(model_name, field_name)',
         'Field name must be unique per model.'),
    ]

    @api.model
    def register(self, model_name: str, fields_meta: Dict[str, fields.Field], invoker_model: str, action_method: str):
        """Save field defs to DB so other workers can pick them up on registry reload."""
        self = self.sudo()
        field2rec = {x.field_name: x for x in self.search([("model_name", "=", model_name), ("field_name", "in", list(fields_meta.keys()))])}

        to_create = []
        for fname, fdef in fields_meta.items():
            FieldClass = type(fdef)
            field_type_path = f"{FieldClass.__module__}.{FieldClass.__name__}"
            user_fname = fdef.args.get("name_user", "")

            # Keep original compute/inverse names; wrapped names are regenerated per-process.
            clean_args = {}
            for k, v in fdef.args.items():
                if k == "name_user":
                    continue
                if isinstance(v, (str, int, float, bool, list, dict, type(None))):
                    clean_args[k] = v
                else:
                    clean_args[k] = str(v)

            existing_rec = field2rec.get(fname)

            vals = {
                'model_name': model_name,
                'field_name': fname,
                'field_type': field_type_path,
                'field_args': json.dumps(clean_args),
                'invoker_model': invoker_model,
                'action_method': action_method,
                'user_field_name': user_fname,
            }

            if existing_rec:
                existing_rec.write(vals)
            else:
                to_create.append(vals)

        self.create(to_create)

    @api.model
    def table_exists(self):
        """Check whether `self._table` exists in database."""
        global _table_exists_cache
        cr = self.env.cr
        dbname = cr.dbname
        exists = _table_exists_cache.get(dbname)
        if exists is None:
            _table_exists_cache[dbname] = exists = table_exists(cr, self._table)
        return exists

    @api.model
    def load_fields(self, model_name) -> List[RawAttachedField]:
        """Restore persisted attached fields onto *model_name* during registry init.

        Called from ``_setup_base`` (Path B).  Uses raw SQL to avoid
        ORM-dependency loops during early registry loading.
        """
        cr = self.env.cr
        if not self.table_exists():
            return []

        cr.execute("""
            SELECT field_name, field_type, field_args, invoker_model, user_field_name, action_method
            FROM attached_field_registry
            WHERE model_name = %s
        """, [model_name])
        rows = cr.fetchall()
        if not rows:
            return []

        return [RawAttachedField.from_row(*t) for t in rows]
