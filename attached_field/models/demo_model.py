from odoo import fields, models, Command
from ..decorator import attached


class AttachedFieldDemoSet(models.Model):
    _name = 'attached.field.demo.set'

    name = fields.Char("Name", required=True)
    model_id = fields.Many2one("ir.model")
    entity_ids = fields.One2many("attached.field.demo.entity", "department_id")

    @attached(picked=fields.Boolean("Picked", compute="_entity_compute_picked", inverse="_entity_inverse_picked"),
              kind=fields.Selection([("customer", "Customer"), ("supplier", "Supplier")], "Kind",
                                    view={"widget": "radio", "options": "{'horizontal': true}"},
                                    compute="_entity_compute_kind", inverse="_entity_inverse_kind"))
    def action_pick_records(self):
        return {
            'name': "Entities",
            'type': 'ir.actions.act_window',
            'res_model': self.model_id.model,
            'view_mode': 'tree,form',
            'target': 'current',
            'context': self.env.context,
        }

    def _entity_compute_picked(self, res_recs):
        picked_ids = set(self.entity_ids.mapped("res_id"))
        for res_rec in res_recs:
            res_rec.picked = res_rec.id in picked_ids

    def _entity_inverse_picked(self, res_recs):
        res_id2entity = {x.res_id: x for x in self.entity_ids}
        for res_rec in res_recs:
            entity = res_id2entity.get(res_rec.id)
            if res_rec.picked:
                if not entity:
                    self.entity_ids = [Command.create({"res_id": res_rec.id})]
            else:
                if entity:
                    entity.unlink()

    def _entity_compute_kind(self, res_recs):
        res_id2entity = {x.res_id: x for x in self.entity_ids}
        for res_rec in res_recs:
            entity = res_id2entity.get(res_rec.id)
            res_rec.kind = entity.kind if entity else False

    def _entity_inverse_kind(self, res_recs):
        res_id2entity = {x.res_id: x for x in self.entity_ids}
        for res_rec in res_recs:
            entity = res_id2entity.get(res_rec.id)
            if entity:
                entity.kind = res_rec.kind


class AttachedFieldDemoEntity(models.Model):
    _name = 'attached.field.demo.entity'

    department_id = fields.Many2one("attached.field.demo.set", "Demo Set")
    res_id = fields.Integer("ResRecord", required=True)
    kind = fields.Selection([("customer", "Customer"), ("supplier", "Supplier")], "Kind")
