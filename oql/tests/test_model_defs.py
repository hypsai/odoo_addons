# -*- coding: utf-8 -*-
# @Time         : 11:10 2026/4/28
# @Author       : Chris
# @Description  : Test model definitions for OQL testing
from odoo import models, fields


def ensure_model_meta(env, model_names):
    """
    Insert model meta into `ir.model` manually.
    """
    for model_name in model_names:
        # Search for existing model record
        meta = env["ir.model"].search([("model", "=", model_name)], limit=1)

        if not meta:
            model_class = env.registry.get(model_name)
            description = getattr(model_class, '_description', '') if model_class else ''
            is_abstract = getattr(model_class, '_abstract', False) if model_class else False
            is_transient = getattr(model_class, '_transient', False) if model_class else False
            
            # Create complete model metadata with all required fields
            env["ir.model"].create({
                'model': model_name,
                'name': description or model_name.replace('.', ' ').title(),
                'state': 'base',
                'info': description,
                'transient': is_transient,
                'order': 'id',  # Default ordering
            })


class TestOqlA(models.Model):
    _name = 'test.oql.a'
    _description = 'Test OQL Model A'

    name = fields.Char()
    b_ids = fields.One2many("test.oql.b", "a_id")
    attr_value_ids = fields.Many2many("test.oql.c")


class TestOqlB(models.Model):
    _name = "test.oql.b"
    _description = 'Test OQL Model B'

    name = fields.Char()
    a_id = fields.Many2one("test.oql.a")
    c_ids = fields.Many2many("test.oql.c")
    term_ids = fields.Many2many("oql.term")

    def __oql_bin__(self, term, opr, value, value_term):
        if term.domain == "self.term_ids":
            return self.c_ids.search([("id", "in", self.c_ids.ids), ("name", opr, value)])
        raise NotImplementedError()

    def __oql_hnt__(self, opr: str):
        if opr == "?":
            return self.c_ids
        else:
            return self.c_ids.mapped("name")


class TestOqlC(models.Model):
    _name = "test.oql.c"
    _description = 'Test OQL Model C'

    name = fields.Char()
    age = fields.Integer()
    gender = fields.Selection([("male", "Male"), ("female", "Female")])
    height = fields.Float()
    enrolled = fields.Boolean()
