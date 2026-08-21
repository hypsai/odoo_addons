# -*- coding: utf-8 -*-
# @Time         : 11:10 2026/4/28
# @Author       : Chris
# @Description  : Test model definitions for OQL testing
from odoo import models, fields, api
from odoo.tests import tagged


def post_test(*tags):
    """Method-level tag decorator that always includes "-at_install" and
    "post_install", avoiding Odoo's "tests should be either at_install or
    post_install" warning when using @tagged on individual methods."""
    return tagged("-at_install", "post_install", *tags)


MODEL_NAMES = ['test.oql.template', 'test.oql.product', 'test.oql.attribute', 'test.oql.attribute.value',
               'test.oql.tag', 'test.oql.supplierinfo', 'test.oql.category']


def ensure_model_meta(env):
    """
    Insert model meta into `ir.model` manually.

    Note: This only creates `ir.model` records. It does NOT touch
    `ir.model.access`. Use `ensure_model_access` separately to grant access.
    """
    for model_name in MODEL_NAMES:
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


def ensure_model_access(env, groups=('base.group_system',),
                        perm_read=True, perm_write=True, perm_create=True, perm_unlink=True):
    """
    Insert full `ir.model.access` records for all test models, for the given
    groups only.

    Why not demo data / security CSV: the test models live under `tests/`, so
    they are only loaded while running tests. Their ACL must therefore be
    created at runtime.

    Why admin only by default: the test environment runs as `admin`, which
    belongs to `base.group_system`. Granting access to `base.group_system`
    allows the setUp fixtures to create/write records.

    IMPORTANT: do NOT grant access to `base.group_user` here. ACL-denial tests
    (in `test_acl.py`) create a `test_user` in `base.group_user` and rely on it
    having NO access, then grant/deny access precisely per test. Giving
    `base.group_user` access here would leak permissions (field-level ACL uses
    `BOOL_OR` over groups, so an extra permissive row would make "denied"
    fields readable).

    :param groups: Groups to grant full access to. Defaults to admin only.
    """
    if isinstance(groups, str):
        groups = (groups,)
    group_ids = [env.ref(g).id if isinstance(g, str) else g.id for g in groups]
    for model_name in MODEL_NAMES:
        meta = env["ir.model"].search([("model", "=", model_name)], limit=1)
        if not meta:
            continue
        for group_id in group_ids:
            existing = env["ir.model.access"].search([
                ("model_id", "=", meta.id), ("group_id", "=", group_id)], limit=1)
            if existing:
                continue
            env["ir.model.access"].create({
                "name": f"test access {model_name}",
                "model_id": meta.id,
                "group_id": group_id,
                "perm_read": perm_read,
                "perm_write": perm_write,
                "perm_create": perm_create,
                "perm_unlink": perm_unlink,
            })


class TestOqlCategory(models.Model):
    _name = "test.oql.category"
    _description = "Test OQL Category"

    name = fields.Char("Name")
    parent_id = fields.Many2one("test.oql.category", "Parent Category")
    child_ids = fields.One2many("test.oql.category", "parent_id", "Child Categories")


class TestOqlTemplate(models.Model):
    _name = "test.oql.template"
    _description = "Test OQL Product Template"

    name = fields.Char("Name", translate=True)
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

    name = fields.Char("Name", compute="_compute_name", store=True)
    name_no_store = fields.Char("Name No Store", compute="_compute_name_no_store")
    spu_name = fields.Char(related="tmpl_id.name", string="Template Name", readonly=False)
    tmpl_id = fields.Many2one("test.oql.template", "Template",
                              delegate=True, required=True, ondelete="cascade")
    attribute_value_ids = fields.One2many("test.oql.attribute.value", "product_id")
    active = fields.Boolean("Active", default=True)

    @api.depends("tmpl_id.name", "attribute_value_ids.name")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.tmpl_id.name}({', '.join(rec.attribute_value_ids.mapped('name'))})"

    def _compute_name_no_store(self):
        for rec in self:
            rec.name_no_store = rec.name


class TestOqlAttribute(models.Model):
    _name = "test.oql.attribute"
    _description = "Test Oql Attribute"

    name = fields.Char("Name")
    value_ids = fields.One2many("test.oql.attribute.value", "attribute_id", "Values")
    term_ids = fields.Many2many("oql.term", string="Terms")

    def __oql_bin__(self, domain, field, opr, value, value_domain):
        if domain.name == "self.term_ids":
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


class TestOqlSupplierinfo(models.Model):
    _name = "test.oql.supplierinfo"
    _description = "Test OQL Supplier Information"

    name = fields.Char("Name")
    product_id = fields.Many2one("test.oql.product", "Product")
