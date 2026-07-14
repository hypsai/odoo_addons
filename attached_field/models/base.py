# -*- coding: utf-8 -*-
# @Time         : 12:01 2026/2/23
# @Author       : Chris
# @Description  :
import logging

from lxml import etree
from odoo import models, api, fields, _

_logger = logging.getLogger(__name__)


class RecordPickerBase(models.AbstractModel):
    _inherit = "base"

    _is_record_picked = fields.Boolean("Is Picked",
                                       compute="_compute__is_record_picked",
                                       inverse="_inverse__is_record_picked",
                                       help="Indicate whether to record is picked.")

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if not self._context.get("_record_picker") or not res.get("arch"):
            return res

        doc = etree.fromstring(res["arch"])
        if "_is_record_picked" not in res["fields"]:
            res["fields"].update(self.fields_get(["_is_record_picked"]))

        if view_type == 'form':
            # Create the structured HTML using classes defined in your CSS file
            container = etree.Element('div', {'class': 'o_record_picker_container'})
            inner_box = etree.Element('div', {'class': 'o_record_picker_box'})

            label = etree.Element('label', {
                'for': '_is_record_picked',
                'string': _('Picked'),
                'class': 'o_record_picker_label'
            })
            field = etree.Element('field', {
                'name': "_is_record_picked",
                'widget': 'boolean_toggle'
            })

            inner_box.append(label)
            inner_box.append(field)
            container.append(inner_box)

            form_nodes = doc.xpath("/form")
            if form_nodes:
                form_nodes[0].insert(0, container)

        elif view_type == 'tree':
            doc.append(etree.Element('field', {
                'name': '_is_record_picked',
                'widget': 'boolean_toggle',
                'string': _('Picked'),
            }))

        res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    def _compute__is_record_picked(self):
        if not self._context.get("_record_picker"):
            self._is_record_picked = False
            return  # Only compute in picker mode.
        compute_picked = self._get_record_picker_invokers_method("compute_picked")
        res = compute_picked(self)
        # Check result.
        if not isinstance(res, list):
            raise Exception(f"`{compute_picked}` must return a list, got `{type(res)}`.")
        if len(res) != len(self):
            raise Exception(f"`{compute_picked}` result is not aligned with input records, {len(res)}!={len(self)}.")
        for rec, val in zip(self, res):
            rec._is_record_picked = val

    def _inverse__is_record_picked(self):
        if not self._context.get("_record_picker"):
            return
        inverse_picked = self._get_record_picker_invokers_method("inverse_picked")
        picked_rec_ids, unpicked_rec_ids = [], []
        for rec in self:
            if rec._is_record_picked:
                picked_rec_ids.append(rec.id)
            else:
                unpicked_rec_ids.append(rec.id)
        inverse_picked(self.browse(picked_rec_ids), self.browse(unpicked_rec_ids))

    def _get_record_picker_invokers_method(self, method_key: str):
        meta = self._context.get("_record_picker")
        invoker_model = meta["invoker_model"]
        invoker_ids = meta["invoker_ids"]
        invoker_recs = self.env[invoker_model].browse(invoker_ids)
        method_name = meta.get(method_key)
        if not hasattr(invoker_recs, method_name):
            raise Exception(f"Model `{invoker_recs._name}` does not have method `{method_name}`.")
        method = getattr(invoker_recs, method_name)
        return method
