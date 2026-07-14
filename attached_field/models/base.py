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
# Record wrapper – makes user-defined field names work on target records.
# ---------------------------------------------------------------------------

class _AttachedFieldRecWrapper:
    """Wraps a single target-model record, routing user-defined field names
    (e.g. ``picked``) to their auto-generated counterparts
    (e.g. ``attached_field_demo_set_action_view_entities_picked``).
    """
    __slots__ = ('_rec', '_map')

    def __init__(self, record, user2actual):
        object.__setattr__(self, '_rec', record)
        object.__setattr__(self, '_map', user2actual)

    def __getattr__(self, name):
        _map = object.__getattribute__(self, '_map')
        if name in _map:
            return object.__getattribute__(self, '_rec')[_map[name]]
        return getattr(object.__getattribute__(self, '_rec'), name)

    def __setattr__(self, name, value):
        _map = object.__getattribute__(self, '_map')
        if name in _map:
            object.__getattribute__(self, '_rec')[_map[name]] = value
        else:
            setattr(object.__getattribute__(self, '_rec'), name, value)

    # -- common record pass-throughs --
    @property
    def id(self):
        return object.__getattribute__(self, '_rec').id

    @property
    def ids(self):
        return object.__getattribute__(self, '_rec').ids

    @property
    def _name(self):
        return object.__getattribute__(self, '_rec')._name

    def __hash__(self):
        return hash(object.__getattribute__(self, '_rec'))

    def __eq__(self, other):
        if isinstance(other, _AttachedFieldRecWrapper):
            other = object.__getattribute__(other, '_rec')
        return object.__getattribute__(self, '_rec') == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __getitem__(self, key):
        return object.__getattribute__(self, '_rec')[key]

    def __setitem__(self, key, value):
        object.__getattribute__(self, '_rec')[key] = value


class _AttachedFieldRecSetWrapper:
    """Wraps a target-model recordset so iteration yields
    :class:`_AttachedFieldRecWrapper` instances.
    """
    def __init__(self, records, user2actual):
        self._records = records
        self._map = user2actual

    def __iter__(self):
        for rec in self._records:
            yield _AttachedFieldRecWrapper(rec, self._map)

    def __getattr__(self, name):
        return getattr(self._records, name)

    def __len__(self):
        return len(self._records)

    def __bool__(self):
        return bool(self._records)


# ---------------------------------------------------------------------------
# Dynamic compute / inverse helpers
# ---------------------------------------------------------------------------

def _create_attached_compute(invoker_model_name, original_compute, user2actual):
    """Return a compute method that delegates to *original_compute* on the
    invoker model.  The invoker's compute receives wrapped target records
    so that it can use user-defined field names naturally
    (e.g. ``res_rec.picked = True``)."""
    def _compute_attached_field(self):
        ctx = self._context.get('_attached_fields')
        if not ctx:
            for rec in self:
                for actual_name in user2actual.values():
                    rec[actual_name] = False
            return

        invoker_ids = ctx.get('invoker_ids', [])
        if not invoker_ids:
            for rec in self:
                for actual_name in user2actual.values():
                    rec[actual_name] = False
            return

        invoker = self.env[invoker_model_name].browse(invoker_ids)
        compute_fn = getattr(invoker, original_compute)

        wrapped = _AttachedFieldRecSetWrapper(self, user2actual)
        compute_fn(wrapped)
        # The invoker's compute writes values via the wrapper, which
        # routes them to the actual field names on *self*.

    return _compute_attached_field


def _create_attached_inverse(invoker_model_name, original_inverse, user2actual):
    """Return an inverse method that delegates to *original_inverse* on the
    invoker model.  The invoker's inverse receives wrapped target records."""
    def _inverse_attached_field(self):
        ctx = self._context.get('_attached_fields')
        if not ctx:
            return
        invoker_ids = ctx.get('invoker_ids', [])
        if not invoker_ids:
            return
        invoker = self.env[invoker_model_name].browse(invoker_ids)
        inverse_fn = getattr(invoker, original_inverse)

        wrapped = _AttachedFieldRecSetWrapper(self, user2actual)
        inverse_fn(wrapped)
        # Inverse writes via wrapper → routed to actual fields on *self*.

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

            # Build user-name → actual-name mapping for the proxy wrapper.
            user2actual = {
                uf: info['actual_fname']
                for uf, info in fields_meta.items()
            }

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
                        invoker_model, field_def.compute, user2actual
                    )
                    setattr(cls, comp_method_name, compute_fn)
                    args['compute'] = comp_method_name

                if field_def.inverse:
                    inv_method_name = f"_attached_inverse_{actual_fname}"
                    inverse_fn = _create_attached_inverse(
                        invoker_model, field_def.inverse, user2actual
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
