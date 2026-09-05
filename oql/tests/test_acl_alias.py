# @Time         : 09:30 2026/9/4
# @Author       : Chris
# @Description  : Test OQL alias ACL (oql.acl.alias).
#
# Two classes, two environments:
#   * `TestOqlAclAlias`          -- `self.env` is switched to a plain internal
#                                   user, so every assertion resolves permissions
#                                   as that user. Fixtures and ACL configuration
#                                   run on `self.env_admin`.
#   * `TestOqlAclAliasSuperuser` -- `self.env` stays the superuser env coming
#                                   from TransactionCase.
#
# The alias ACL differs from the field ACL (`oql.acl.field`), which stacks
# three layers. Here every (user group -> ir.model.access) path produces one
# verdict and the paths are OR-ed together:
#
#   BOOL_OR( b.perm_<mode>
#            AND COALESCE(e.perm_<mode>, b.perm_oql_aac_default_<mode>, FALSE) )
#
# where `e` is the `oql.acl.alias` row for that (access, alias) pair, if any.
# Hence:
#   * an explicit row wins over the model default (it both relaxes and tightens);
#   * model-level <mode> permission is a hard prerequisite;
#   * explicit denials are NOT sticky across groups -- BOOL_OR means any
#     granting path wins (the opposite of the field ACL's layer 1).
#
# Unlike the field ACL, alias access does NOT depend on whether the fields an
# alias references are themselves accessible. The verdict comes purely from
# `oql.acl.alias` (explicit row OR the model default), evaluated in SQL.
from odoo import SUPERUSER_ID
from odoo.tests import tagged, TransactionCase

from .test_model_defs import ensure_model_meta, ensure_model_access, post_test
from ..acl import OqlAcl
from ..compatible import res_users_data

# Aliases declared on `test.oql.product`.
ALIAS_SPU = "spu"                # field    -> spu_name
ALIAS_TAG_NAMES = "tag_names"    # field    -> tag_ids.name
ALIAS_INFO = "product_info"      # jmespath -> {name: rec.spu_name, active: rec.active}

ALL_ALIASES = {ALIAS_SPU, ALIAS_TAG_NAMES, ALIAS_INFO}


class OqlAclAliasCase(TransactionCase):
    """Shared fixtures: an alias rule on `test.oql.product` plus a restricted user.

    `self.env_admin` is the superuser env handed over by TransactionCase. It is
    used for fixtures and for ACL configuration (both are admin operations);
    subclasses decide what `self.env` itself is.
    """

    def setUp(self):
        super().setUp()
        self.env_admin = self.env
        env = self.env_admin
        ensure_model_meta(env)
        # Admin-only access so fixtures can be created; the test user's access
        # is granted per test.
        ensure_model_access(env)

        self.metaProduct = env["ir.model"].search(
            [("model", "=", "test.oql.product")], limit=1)

        self.prod_cold = env["test.oql.product"].create({"spu_name": "Cold Boot"})
        env["test.oql.tag"].create(
            {"name": "Waterproof:GTX", "tmpl_id": self.prod_cold.tmpl_id.id})

        # Alias rule on the product model.
        self.rule = env["oql.alias"].create({"model_id": self.metaProduct.id})
        self.alias_spu = env["oql.alias.line"].create({
            "rule_id": self.rule.id, "alias": ALIAS_SPU, "mode": "field", "path": "spu_name"})
        self.alias_tags = env["oql.alias.line"].create({
            "rule_id": self.rule.id, "alias": ALIAS_TAG_NAMES, "mode": "field", "path": "tag_ids.name"})
        self.alias_info = env["oql.alias.line"].create({
            "rule_id": self.rule.id, "alias": ALIAS_INFO, "mode": "jmespath",
            "path": "{name: rec.spu_name, active: rec.active}"})

        self.test_user = env['res.users'].create(res_users_data({
            'name': 'Alias ACL User',
            'login': 'alias_acl_user',
            'email': 'alias_acl@example.com',
            'groups_id': [(6, 0, [env.ref('base.group_user').id])],  # Internal User only
        }))
        self.user_group = env.ref('base.group_user')

    # ---- ACL configuration (admin operations) -----------------------------

    def _grant_product(self, perm_read=True, perm_write=False,
                       default_read=True, default_write=False, group=None):
        """Create an ir.model.access row for the test user's group."""
        return self.env_admin["ir.model.access"].create({
            'name': 'Alias ACL Access',
            'model_id': self.metaProduct.id,
            'group_id': (group or self.user_group).id,
            'perm_read': perm_read,
            'perm_write': perm_write,
            'perm_create': False,
            'perm_unlink': False,
            'perm_oql_aac_default_read': default_read,
            'perm_oql_aac_default_write': default_write,
            'perm_oql_fac_default_read': True,
            'perm_oql_fac_default_write': default_write,
        })

    def _grant_alias(self, alias_line, perm_read=None, perm_write=None, mac=None):
        """Create an oql.acl.alias override row for `alias_line`.

        Only the given permissions are written; the others keep their default
        (False), because an explicit row governs the alias on its own.
        """
        access = mac or self.env_admin["ir.model.access"].search([
            ('model_id', '=', self.metaProduct.id),
            ('group_id', '=', self.user_group.id)], limit=1)
        vals = {'mac_id': access.id, 'alias_id': alias_line.id}
        if perm_read is not None:
            vals['perm_read'] = perm_read
        if perm_write is not None:
            vals['perm_write'] = perm_write
        return self.env_admin["oql.acl.alias"].create(vals)


@tagged("oql_acl_alias", "-at_install", "post_install")
class TestOqlAclAlias(OqlAclAliasCase):
    """Alias ACL resolved as a plain internal user.

    `self.env` IS the restricted user's env (out of superuser mode), so every
    assertion below resolves permissions as `self.test_user` -- no per-call
    env switching, and no way for a permission check to silently run as
    superuser.
    """

    def setUp(self):
        super().setUp()
        # Switch the whole env to the restricted user.
        #
        # !! `env(user=...)` already resets `su` on Odoo 15
        # (`su = (user is None and self.su) if su is None else su`), so this is
        # non-su. `su=False` is passed to state the intent explicitly.
        # !! `Environment.__new__` forces `su=True` for uid == SUPERUSER_ID, so a
        # test user resolving to the superuser is rejected right here.
        self.env = self.env_admin(user=self.test_user, su=False)
        self.assertFalse(self.env.su)
        self.assertNotEqual(self.env.uid, SUPERUSER_ID)

    # ---- helpers ----------------------------------------------------------

    def _aliases(self, mode="read"):
        """Aliases granted by the alias ACL, as seen through `self.env`."""
        acl = OqlAcl(self.env)
        return acl["test.oql.product"].perm_aliases(mode)

    # ---- sanity -----------------------------------------------------------

    @post_test("aac.sanity")
    def test_env_is_the_test_user(self):
        """Guard: `self.env` must be the restricted user, out of superuser mode,
        otherwise this whole class would assert nothing."""
        self.assertFalse(self.env.su)
        self.assertEqual(self.test_user.id, self.env.uid)
        # Canary: with no access row at all a restricted user gets nothing...
        self.assertEqual(set(), self._aliases("read"))
        # ...while the superuser gets everything.
        self.assertEqual(
            ALL_ALIASES,
            set(self.env_admin["oql.acl.alias"].perm_aliases("test.oql.product", "read")))

    # ---- default: perm_oql_aac_default_* ---------------------------------

    @post_test("aac.default")
    def test_default_read_true(self):
        """default_read=True grants every alias of the model."""
        self._grant_product(default_read=True)
        self.assertEqual(ALL_ALIASES, set(self._aliases("read")))

    @post_test("aac.default")
    def test_default_read_false(self):
        """default_read=False denies every alias, model read alone is not enough."""
        self._grant_product(perm_read=True, default_read=False)
        self.assertEqual(set(), self._aliases("read"))

    @post_test("aac.default")
    def test_no_access_row_denies_all(self):
        """Without any ir.model.access row the user gets no alias at all."""
        self.assertEqual(set(), self._aliases("read"))

    # ---- override: oql.acl.alias -----------------------------------------

    @post_test("aac.override")
    def test_explicit_grant_relaxes(self):
        """An explicit allow row grants an alias even when the default denies."""
        self._grant_product(default_read=False)
        self._grant_alias(self.alias_spu, perm_read=True)
        self.assertEqual({ALIAS_SPU}, set(self._aliases("read")))

    @post_test("aac.override")
    def test_explicit_deny_tightens(self):
        """An explicit deny row withholds an alias even when the default grants."""
        self._grant_product(default_read=True)
        self._grant_alias(self.alias_spu, perm_read=False)
        self.assertEqual({ALIAS_TAG_NAMES, ALIAS_INFO}, set(self._aliases("read")))

    @post_test("aac.override")
    def test_override_takes_effect_immediately(self):
        """Creating an override row invalidates the ormcache, so a later read
        in the same transaction already sees it (regression: `oql.acl.alias`
        used to have no cache invalidation hooks)."""
        self._grant_product(default_read=True)
        # Everything granted before...
        self.assertIn(ALIAS_SPU, self._aliases("read"))
        # ...and withheld right after the deny row is created.
        self._grant_alias(self.alias_spu, perm_read=False)
        self.assertNotIn(ALIAS_SPU, self._aliases("read"))

    # ---- model level permission is a prerequisite ------------------------

    @post_test("aac.model_perm")
    def test_model_read_required(self):
        """Model-level read gates everything: without it no alias is granted,
        not even one with an explicit allow row."""
        self._grant_product(perm_read=False, default_read=True)
        self._grant_alias(self.alias_spu, perm_read=True)
        self.assertEqual(set(), self._aliases("read"))

    # ---- write mode ------------------------------------------------------

    @post_test("aac.write")
    def test_write_mode(self):
        """The write mode is evaluated against perm_write / the write default,
        independently from the read mode."""
        self._grant_product(perm_read=True, perm_write=True,
                            default_read=True, default_write=False)
        # Write default False -> nothing writable.
        self.assertEqual(set(), self._aliases("write"))
        # An explicit allow row -> only that alias becomes writable.
        self._grant_alias(self.alias_spu, perm_write=True)
        self.assertEqual({ALIAS_SPU}, set(self._aliases("write")))
        # The same row carries perm_read=False, which also withholds the alias
        # on the read side (an explicit row governs the alias on its own).
        self.assertEqual({ALIAS_TAG_NAMES, ALIAS_INFO}, set(self._aliases("read")))

    # ---- multiple groups -------------------------------------------------

    @post_test("aac.multi_group")
    def test_explicit_deny_is_not_sticky(self):
        """BOOL_OR over the user's paths: an explicit deny on one path does not
        block another path that grants (unlike the field ACL's layer 1)."""
        env = self.env_admin
        extra_group = env['res.groups'].create({
            'name': 'Alias ACL Extra',
            'category_id': env.ref('base.module_category_hidden').id})
        self.test_user.write({'groups_id': [(4, extra_group.id)]})

        # group_user path: default deny + explicit deny row on `spu`.
        self._grant_product(default_read=False)
        self._grant_alias(self.alias_spu, perm_read=False)
        # extra group path: default allow, no override row.
        self._grant_product(default_read=True, group=extra_group)

        self.assertIn(ALIAS_SPU, self._aliases("read"))

    # ---- scope -----------------------------------------------------------

    @post_test("aac.scope")
    def test_aliases_are_scoped_to_model(self):
        """Aliases belonging to another model are never returned."""
        self._grant_product(default_read=True)
        env = self.env_admin
        metaTag = env["ir.model"].search([("model", "=", "test.oql.tag")], limit=1)
        rule = env["oql.alias"].create({"model_id": metaTag.id})
        env["oql.alias.line"].create({
            "rule_id": rule.id, "alias": "tag_name", "mode": "field", "path": "name"})

        aliases = self._aliases("read")
        self.assertNotIn("tag_name", aliases)
        self.assertIn(ALIAS_SPU, aliases)

    # ---- alias access is independent of field-path accessibility ----------

    @post_test("aac.path_independent")
    def test_alias_access_ignores_field_path(self):
        """An alias is granted by the alias ACL even when the fields it
        references are denied at the field level -- and denied even when those
        fields are allowed. Field-path accessibility must NOT affect the verdict."""
        access = self._grant_product(perm_read=True, default_read=False)
        # Deny `active` and `spu_name` at the field level, allow `name`.
        for fname in ("active", "spu_name"):
            f = self.env_admin["ir.model.fields"].search([
                ('model_id', '=', self.metaProduct.id), ('name', '=', fname)], limit=1)
            self.env_admin["oql.acl.field"].create({
                'mac_id': access.id, 'field_id': f.id, 'perm_read': False})

        # Default read is False -> NO alias is granted, regardless of paths.
        self.assertEqual(set(), set(self._aliases("read")))
        # Now flip the default to True -> ALL aliases granted, even `product_info`
        # (which references the denied `active`) and `spu` (which references the
        # denied `spu_name`). Field-path denial does not block them.
        access.perm_oql_aac_default_read = True
        self.env["oql.acl.alias"].clear_caches()
        self.assertEqual(ALL_ALIASES, set(self._aliases("read")))


@tagged("oql_acl_alias_su", "-at_install", "post_install")
class TestOqlAclAliasSuperuser(OqlAclAliasCase):
    """Alias ACL under a superuser env.

    `self.env` stays the superuser env handed over by TransactionCase, so
    `perm_aliases` short-circuits to "every alias of the model" and no
    ir.model.access / oql.acl.alias record can restrict it.
    """

    def setUp(self):
        super().setUp()
        self.assertTrue(self.env.su, "This class must run on the superuser env.")

    def _aliases(self, mode="read"):
        """Aliases granted by the alias ACL, as seen through the su env."""
        return self.env["oql.acl.alias"].perm_aliases("test.oql.product", mode)

    @post_test("aac.su")
    def test_superuser_gets_all_aliases(self):
        """Superuser gets every alias without any access configuration."""
        self.assertEqual(ALL_ALIASES, set(self._aliases("read")))
        self.assertEqual(ALL_ALIASES, set(self._aliases("write")))

    @post_test("aac.su")
    def test_superuser_ignores_explicit_deny(self):
        """Explicit deny rows configured for the user's group do not restrict
        the superuser."""
        self._grant_product(perm_read=False, default_read=False)
        for alias_line in (self.alias_spu, self.alias_tags, self.alias_info):
            self._grant_alias(alias_line, perm_read=False, perm_write=False)

        self.assertEqual(ALL_ALIASES, set(self._aliases("read")))
        self.assertEqual(ALL_ALIASES, set(self._aliases("write")))

    @post_test("aac.su")
    def test_superuser_ignores_restricted_user(self):
        """The same query is unrestricted for su while the restricted user gets
        nothing, proving the outcome really depends on the env."""
        self._grant_product(perm_read=True, default_read=False)

        # Restricted user: the alias default denies everything.
        user_aliases = self.env_admin(user=self.test_user, su=False)[
            "oql.acl.alias"].perm_aliases("test.oql.product", "read")
        self.assertEqual(set(), set(user_aliases))
        # Superuser: everything.
        self.assertEqual(ALL_ALIASES, set(self._aliases("read")))
