# -*- coding: utf-8 -*-
# @Time         : 11:10 2026/4/28
# @Author       : Chris
# @Description  : Test model definitions for OQL testing
from odoo import models, fields


def ensure_model_meta(env):
    """
    Insert model meta into `ir.model` manually.
    """
    model_names = ['test.oql.template', 'test.oql.product', 'test.oql.attribute', 'test.oql.attribute.value', 'test.oql.tag']
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


class TestOqlTemplate(models.Model):
    _name = "test.oql.template"
    _description = "Test OQL Product Template"

    tag_ids = fields.One2many("test.oql.tag", "tmpl_id")


class TestOqlTag(models.Model):
    _name = "test.oql.tag"
    _description = 'Test OQL Tag'

    name = fields.Char("Name")
    tmpl_id = fields.Many2one("test.oql.template", "Template")
    term_ids = fields.Many2many("oql.term", string="Terms")


class TestOqlProduct(models.Model):
    _name = 'test.oql.product'
    _description = 'Test OQL Product'
    _inherits = {"test.oql.template": "tmpl_id"}

    name = fields.Char("Name")
    tmpl_id = fields.Many2one("test.oql.template", "Template", delegate=True)
    attribute_value_ids = fields.One2many("test.oql.attribute.value", "product_id")
    active = fields.Boolean("Active", default=True)


class TestOqlAttribute(models.Model):
    _name = "test.oql.attribute"
    _description = "Test Oql Attribute"

    name = fields.Char("Name")
    value_ids = fields.One2many("test.oql.attribute.value", "attribute_id", "Values")
    term_ids = fields.Many2many("oql.term", string="Terms")

    def __oql_bin__(self, term, opr, value, value_term):
        if term.domain == "self.term_ids":
            return self.value_ids.search([("id", "in", self.value_ids.ids), ("name", opr, value)])
        raise NotImplementedError()

    def __oql_hnt__(self, opr: str):
        if opr == "?":
            return self.value_ids
        else:
            return self.value_ids.mapped("name")


class TestOqlAttributeValue(models.Model):
    _name = "test.oql.attribute.value"
    _description = 'Test OQL Attribute Value'

    name = fields.Char("Name")
    product_id = fields.Many2one("test.oql.product", "Product")
    attribute_id = fields.Many2one("test.oql.attribute", "Attribute")
