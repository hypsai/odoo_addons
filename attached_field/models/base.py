# -*- coding: utf-8 -*-
# @Time         : 12:01 2026/2/23
# @Author       : Chris
# @Description  : Extends ``base`` so that attached fields are
#                 - installed during ``_setup_base`` (triggered by refresh_models)
#                 - injected into views via ``fields_view_get``.
import logging

from lxml import etree
from odoo import models, api

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dynamic compute / inverse helpers
# ---------------------------------------------------------------------------

def _create_attached_compute(invoker_model_name, original_compute, field_name):
    """Return a compute method that delegates to *original_compute* on the
    invoker model."""
    def _compute_attached_field(self):
        ctx = self._context.get('_attached_fields')
        if not ctx:
            for rec in self:
                rec[field_name] = False
            return

        invoker_ids = ctx.get('invoker_ids', [])
        if not invoker_ids:
            for rec in self:
                rec[field_name] = False
            return

        invoker = self.env[invoker_model_name].browse(invoker_ids)
        compute_fn = getattr(invoker, original_compute)
        result = compute_fn(self)

        if not isinstance(result, list):
            raise Exception(
                f"Compute method `{original_compute}` must return a list, "
                f"got `{type(result)}`."
            )
        if len(result) != len(self):
            raise Exception(
                f"Compute method `{original_compute}` result is not aligned "
                f"with target records, {len(result)}!={len(self)}."
            )
        for rec, val in zip(self, result):
            rec[field_name] = val

    return _compute_attached_field


def _create_attached_inverse(invoker_model_name, original_inverse):
    """Return an inverse method that delegates to *original_inverse* on the
    invoker model."""
    def _inverse_attached_field(self):
        ctx = self._context.get('_attached_fields')
        if not ctx:
            return
        invoker_ids = ctx.get('invoker_ids', [])
        if not invoker_ids:
            return
        invoker = self.env[invoker_model_name].browse(invoker_ids)
        inverse_fn = getattr(invoker, original_inverse)
        inverse_fn(self)

    return _inverse_attached_field


# ---------------------------------------------------------------------------
# View injection helpers
# ---------------------------------------------------------------------------

def _inject_form_fields(doc, res, fields_meta, model):
    """Inject attached fields into a form view as a floating container
    (upper-right corner)."""
    container = etree.Element('div', {'class': 'o_attached_field_container'})
    inner_box = etree.Element('div', {'class': 'o_attached_field_box'})

    for _user_fname, info in fields_meta.items():
        actual_fname = info['actual_fname']
        view_config = info.get('view_config') or {}

        # Ensure field metadata in response.
        if actual_fname not in res['fields']:
            res['fields'].update(model.fields_get([actual_fname]))

        fdef = model._fields.get(actual_fname)
        string = (fdef.string if fdef else actual_fname) if fdef else actual_fname

        label = etree.Element('label', {
            'for': actual_fname,
            'string': string,
            'class': 'o_attached_field_label',
        })
        field_attrs = {'name': actual_fname}
        field_attrs.update(view_config)
        field_el = etree.Element('field', field_attrs)

        inner_box.append(label)
        inner_box.append(field_el)

    container.append(inner_box)
    form_nodes = doc.xpath("/form")
    if form_nodes:
        form_nodes[0].insert(0, container)


def _inject_tree_fields(doc, res, fields_meta, model):
    """Append attached-field columns at the end of a tree view."""
    for _user_fname, info in fields_meta.items():
        actual_fname = info['actual_fname']
        view_config = info.get('view_config') or {}

        if actual_fname not in res['fields']:
            res['fields'].update(model.fields_get([actual_fname]))

        fdef = model._fields.get(actual_fname)
        field_attrs = {
            'name': actual_fname,
            'string': (fdef.string if fdef else actual_fname) if fdef else actual_fname,
        }
        field_attrs.update(view_config)
        doc.append(etree.Element('field', field_attrs))


# ---------------------------------------------------------------------------
# Model extension (inherits ``base`` → every model)
# ---------------------------------------------------------------------------

class AttachedFieldBase(models.AbstractModel):
    _inherit = "base"

    def _setup_base(self):
        super()._setup_base()

        from ..decorator import _PENDING_ATTACHED

        for (res_model, invoker_model, action_method), meta in list(
            _PENDING_ATTACHED.items()
        ):
            if res_model != self._name:
                continue
            if meta.get('_installed'):
                continue

            cls = type(self).__base__  # the concrete model class
            fields_meta = meta['fields_meta']

            for user_fname, info in fields_meta.items():
                actual_fname = info['actual_fname']
                field_def = info['field_def']

                if actual_fname in self._fields:
                    continue

                # -- Build a new Field instance for the target model --
                FieldClass = type(field_def)

                # Replicate common attributes from the original field definition.
                args = {}
                if hasattr(field_def, 'args') and isinstance(field_def.args, dict):
                    for key, val in field_def.args.items():
                        if key == 'view':
                            continue
                        # Skip callable defaults – they may belong to the invoker.
                        if callable(val):
                            continue
                        args[key] = val

                # Make sure 'string' is always present.
                if 'string' not in args and field_def.string:
                    args['string'] = field_def.string

                # Install delegated compute/inverse on the target model.
                if field_def.compute:
                    comp_method_name = f"_attached_compute_{actual_fname}"
                    compute_fn = _create_attached_compute(
                        invoker_model, field_def.compute, actual_fname
                    )
                    setattr(cls, comp_method_name, compute_fn)
                    args['compute'] = comp_method_name

                if field_def.inverse:
                    inv_method_name = f"_attached_inverse_{actual_fname}"
                    inverse_fn = _create_attached_inverse(
                        invoker_model, field_def.inverse
                    )
                    setattr(cls, inv_method_name, inverse_fn)
                    args['inverse'] = inv_method_name

                new_field = FieldClass(**args)
                self._add_field(actual_fname, new_field)
                _logger.debug(
                    "Attached field '%s' on model '%s' (invoker: %s.%s)",
                    actual_fname, self._name, invoker_model, action_method,
                )

            meta['_installed'] = True

    @api.model
    def fields_view_get(self, view_id=None, view_type='form',
                        toolbar=False, submenu=False):
        res = super().fields_view_get(
            view_id=view_id, view_type=view_type,
            toolbar=toolbar, submenu=submenu,
        )

        ctx = self._context.get('_attached_fields')
        if not ctx or not res.get('arch'):
            return res

        fields_meta = ctx.get('fields_meta', {})
        if not fields_meta:
            return res

        doc = etree.fromstring(res['arch'])

        if view_type == 'form':
            _inject_form_fields(doc, res, fields_meta, self)
        elif view_type in ('tree', 'list'):
            _inject_tree_fields(doc, res, fields_meta, self)

        res['arch'] = etree.tostring(doc, encoding='unicode')
        return res
