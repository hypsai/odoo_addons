# -*- coding: utf-8 -*-
# @Time         : 12:01 2026/2/23
# @Author       : Chris
# @Description  : Extends ``base`` so that attached fields are
#                 - installed during ``_setup_base`` (triggered by refresh_models)
#                 - injected into views via ``fields_view_get``.
import logging
from typing import Dict, Iterable

from lxml import etree
from odoo import models, api, fields

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Record wrapper – makes user-defined field names work on target records.
# ---------------------------------------------------------------------------

def _map(self):
    return object.__getattribute__(self, '_map')


def _recs(self):
    return object.__getattribute__(self, '_recs')


def _actual_name(self, name: str):
    _map = object.__getattribute__(self, '_map')
    return _map.get(name) or name


class _AttachedFieldRecSetWrapper:
    """Wraps odoo ORM records, routing user-defined field names
    (e.g. ``picked``) to their auto-generated counterparts
    (e.g. ``attached_field_demo_set_action_view_entities_picked``).
    """
    __slots__ = ('_recs', '_map')

    def __init__(self, record, user2actual):
        object.__setattr__(self, '_recs', record)
        object.__setattr__(self, '_map', user2actual)

    def __getattr__(self, name):
        return getattr(_recs(self), _actual_name(self, name))

    def __setattr__(self, name, value):
        setattr(_recs(self), _actual_name(self, name), value)

    def __hash__(self):
        return hash(_recs(self))

    def __eq__(self, other):
        if isinstance(other, _AttachedFieldRecSetWrapper):
            other = _recs(other)
        return _recs(self) == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __getitem__(self, key):
        return _recs(self)[_actual_name(self, key)]

    def __setitem__(self, key, value):
        _recs(self)[_actual_name(self, key)] = value

    def __iter__(self):
        for rec in _recs(self):
            yield _AttachedFieldRecSetWrapper(rec, _map(self))

    def __len__(self):
        return len(_recs(self))

    def __bool__(self):
        return bool(_recs(self))


# ---------------------------------------------------------------------------
# Dynamic compute / inverse helpers
# ---------------------------------------------------------------------------

def _create_attached_compute(invoker_model_name: str, original_compute: str, fname: str, user2actual):
    """Return a compute method that delegates to *original_compute* on the
    invoker model.  The invoker's compute receives wrapped target records
    so that it can use user-defined field names naturally
    (e.g. ``res_rec.picked = True``)."""
    def _compute_attached_field(self):
        ctx = self._context.get('_attached_fields')
        if not ctx:
            for rec in self:
                rec[fname] = False
            return

        invoker_ids = ctx.get('invoker_ids', [])
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
        invoker_ids = ctx.get('invoker_ids')
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

def _inject_form_fields(doc, res: dict, field_names: Iterable[str], model: models.Model):
    """Inject attached fields into a form view as a floating container
    (upper-right corner)."""
    container = etree.Element('div', {'class': 'o_attached_field_container'})
    inner_box = etree.Element('div', {'class': 'o_attached_field_box'})
    _fields = model._fields  # noqa
    res_fields = res.get("fields") or {}
    if not res_fields:
        res["fields"] = res_fields

    for fname in field_names:
        # Ensure field metadata in response.
        if fname not in res_fields:
            res_fields.update(model.fields_get([fname]))

        fdef = _fields.get(fname)
        if not fdef:
            _logger.warning(f"Attached field `{fname}` is missing from `{model}`, injection ignored.")
            continue
        view_config = (getattr(fdef, "view", None) or {}).copy()
        view_config.update(getattr(fdef, "view_form", {}))
        string = (fdef.string if fdef else fname) if fdef else fname

        row = etree.Element('div', {'class': 'o_attached_field_row'})
        label = etree.Element('label', {
            'for': fname,
            'string': string,
            'class': 'o_attached_field_label',
        })
        field_attrs = {'name': fname}
        field_attrs.update(view_config)
        field_el = etree.Element('field', field_attrs)
        value_div = etree.Element('div', {'class': 'o_attached_field_value'})
        value_div.append(field_el)

        row.append(label)
        row.append(value_div)
        inner_box.append(row)

    container.append(inner_box)
    form_nodes = doc.xpath("/form")
    if form_nodes:
        form_nodes[0].insert(0, container)


def _inject_tree_fields(doc, res: dict, field_names: Iterable[str], model: models.Model):
    """Append attached-field columns at the end of a tree view."""
    _fields: Dict[str, fields.Field] = model._fields  # noqa
    res_fields = res.get("fields") or {}
    if not res_fields:
        res["fields"] = res_fields

    for fname in field_names:
        if fname not in res_fields:
            res_fields.update(model.fields_get([fname]))

        fdef = _fields.get(fname)
        if not fdef:
            _logger.warning(f"Attached field `{fname}` is missing from `{model}`, injection ignored.")
            continue
        view_config = (getattr(fdef, "view", None) or {}).copy()
        view_config.update(getattr(fdef, "view_tree", {}))
        field_attrs = {
            'name': fname,
            'string': fdef.string or fname,
        }
        field_attrs.update(view_config)
        doc.append(etree.Element('field', field_attrs))


class AttachedFieldBase(models.AbstractModel):
    _inherit = "base"

    def _setup_base(self):
        super()._setup_base()

        # Try load attached meta from context.
        ctx: dict = self.env.context.get("_attached_fields")
        if not ctx:
            return
        invoker_model = ctx.get("invoker_model")
        action_method = ctx.get("action_method")
        fields_meta: Dict[str, fields.Field] = ctx.get("fields_meta")
        user2actual = {f.args["name_user"]: actual for actual, f in fields_meta.items()}

        # Install attached field to this model.
        cls = type(self).__base__  # the concrete model class
        _fields = self._fields  # noqa
        for fname, fdef in fields_meta.items():
            if fname in _fields:
                continue  # Has already been installed.

            # -- Build a new Field instance for the target model --
            FieldClass = type(fdef)

            # Replicate attributes from the original field definition.
            args = fdef.args.copy()

            # Install delegated compute/inverse on the target model.
            original_compute = args.get("compute")
            original_inverse = args.get("inverse")
            if not original_compute and not original_inverse:
                raise Exception(f"Attached field `{fname}` must define either one of compute/inverse method.")
            if original_compute:
                comp_method_name = f"_attached_compute_{fname}"
                compute_fn = _create_attached_compute(invoker_model, original_compute, fname, user2actual)
                setattr(cls, comp_method_name, compute_fn)
                args['compute'] = comp_method_name
            if original_inverse:
                inv_method_name = f"_attached_inverse_{fname}"
                inverse_fn = _create_attached_inverse(invoker_model, original_inverse, user2actual)
                setattr(cls, inv_method_name, inverse_fn)
                args['inverse'] = inv_method_name

            new_field = FieldClass(**args)
            self._add_field(fname, new_field)
            _logger.debug(
                "Attached field '%s' on model '%s' (invoker: %s.%s)",
                fname, self._name, invoker_model, action_method,
            )

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        ctx = self.env.context.get('_attached_fields')
        if not ctx or not res.get('arch'):
            return res

        fields_meta: Dict[str, fields.Field] = ctx.get('fields_meta', {})
        if not fields_meta:
            return res

        doc = etree.fromstring(res['arch'])

        if view_type == 'form':
            _inject_form_fields(doc, res, fields_meta, self)
        elif view_type in ('tree', 'list'):
            _inject_tree_fields(doc, res, fields_meta, self)

        res['arch'] = etree.tostring(doc, encoding='unicode')

        return res
