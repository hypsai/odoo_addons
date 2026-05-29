# -*- coding: utf-8 -*-
"""Unit tests for the MCP tool ACL (``mcp.base.tool.acl``)."""
import logging

from odoo.tests import tagged, TransactionCase

_logger = logging.getLogger(__name__)


@tagged('mcp_base', 'post_install', '-at_install')
class TestMcpBaseAcl(TransactionCase):
    """Exercise the mcp.base.tool.acl model and ``perm_tools()`` SQL."""

    def setUp(self):
        super().setUp()
        self.Tool = self.env['mcp.base.tool']
        self.ToolAcl = self.env['mcp.base.tool.acl']
        self.ModelAccess = self.env['ir.model.access']

        # ── test model ──────────────────────────────────────────────────
        self.test_model = self.env['ir.model'].search(
            [('model', '=', 'test.mcp.base.tool')], limit=1,
        )
        self.assertTrue(self.test_model,
                        'test.mcp.base.tool must exist in ir.model')

        # post_init_hook already created code-first tools — grab them
        self.tools = self.Tool.search([
            ('model_id', '=', self.test_model.id),
            ('active', '=', True),
        ])
        _logger.info('ACL test tools: %s', {
            t.method_id.name: t.id for t in self.tools
        })

        # ── test user ───────────────────────────────────────────────────
        self.test_user = self.env['res.users'].create({
            'name': 'Test MCP ACL User',
            'login': 'test_mcp_acl_user',
            'email': 'test_mcp_acl@example.com',
            'groups_id': [
                (6, 0, [self.env.ref('base.group_user').id]),
            ],
        })

        # Grant model-level read on test.mcp.base.tool for group_user.
        self.test_mac = self.ModelAccess.create({
            'name': 'test.mcp.base.tool user access',
            'model_id': self.test_model.id,
            'group_id': self.env.ref('base.group_user').id,
            'perm_read': True,
            'perm_write': False,
            'perm_create': False,
            'perm_unlink': False,
            # default: perm_mcp_base_tool_default_read = True
        })

        # ── warm the registry method cache ──────────────────────────────
        for t in self.tools:
            _ = t.method_id.name  # noqa

    # ═════════════════════════════════════════════════════════════════
    # helpers
    # ═════════════════════════════════════════════════════════════════

    def _perm_tools_as(self, user):
        """Return tool-id set visible to *user* via ``perm_tools()``."""
        return self.ToolAcl.with_user(user).perm_tools()

    def _find_tool(self, method_name):
        """Return the active tool record for *method_name* on test model."""
        for t in self.tools:
            if t.method_id.name == method_name:
                return t
        self.fail(f'Tool {method_name} not found on test model')

    # ═════════════════════════════════════════════════════════════════
    # superuser
    # ═════════════════════════════════════════════════════════════════

    def test_perm_tools_superuser(self):
        """Superuser sees all active tools regardless of ACL settings."""
        # Turn off defaults to prove superuser bypasses them
        self.test_mac.perm_mcp_base_tool_default_read = False
        self.test_mac.perm_read = False

        permitted = self._perm_tools_as(self.env.user)  # admin is superuser
        all_tool_ids = set(self.Tool.search([('active', '=', True)]).ids)
        self.assertEqual(permitted, all_tool_ids,
                         'Superuser must see all active tools')

    # ═════════════════════════════════════════════════════════════════
    # default read = True
    # ═════════════════════════════════════════════════════════════════

    def test_perm_tools_default_read_true(self):
        """Non-admin user sees tools when default read access is True."""
        permitted = self._perm_tools_as(self.test_user)
        tool_ids = {t.id for t in self.tools}
        self.assertEqual(permitted, tool_ids,
                         'User with default read=True must see all tools')

    # ═════════════════════════════════════════════════════════════════
    # default read = False
    # ═════════════════════════════════════════════════════════════════

    def test_perm_tools_default_read_false(self):
        """Non-admin user sees NO tools when default read is disabled."""
        self.test_mac.perm_mcp_base_tool_default_read = False

        permitted = self._perm_tools_as(self.test_user)
        self.assertEqual(permitted, set(),
                         'No tools visible when default read=False')

    # ═════════════════════════════════════════════════════════════════
    # explicit allow overrides default=False
    # ═════════════════════════════════════════════════════════════════

    def test_perm_tools_explicit_allow(self):
        """Explicit ``perm_read=True`` on a tool overrides default=False."""
        self.test_mac.perm_mcp_base_tool_default_read = False
        allowed_tool = self._find_tool('get_customers')

        self.ToolAcl.create({
            'mac_id': self.test_mac.id,
            'tool_id': allowed_tool.id,
            'perm_read': True,
        })

        permitted = self._perm_tools_as(self.test_user)
        self.assertEqual(permitted, {allowed_tool.id},
                         'Explicit allow must override default=False')

    # ═════════════════════════════════════════════════════════════════
    # explicit deny when default=True
    # ═════════════════════════════════════════════════════════════════

    def test_perm_tools_explicit_deny(self):
        """Explicit ``perm_read=False`` on a tool hides it (default=True)."""
        denied_tool = self._find_tool('get_customers')
        other_ids = {t.id for t in self.tools if t.id != denied_tool.id}

        self.ToolAcl.create({
            'mac_id': self.test_mac.id,
            'tool_id': denied_tool.id,
            'perm_read': False,
        })

        permitted = self._perm_tools_as(self.test_user)
        self.assertEqual(permitted, other_ids,
                         'Explicit deny must hide that specific tool')

    # ═════════════════════════════════════════════════════════════════
    # no model access at all
    # ═════════════════════════════════════════════════════════════════

    def test_perm_tools_no_model_access(self):
        """User without any ir.model.access sees zero tools."""
        # Remove the test group from the user
        self.test_user.groups_id = [
            (3, self.env.ref('base.group_user').id),
        ]

        permitted = self._perm_tools_as(self.test_user)
        self.assertEqual(permitted, set(),
                         'User with no model access must see zero tools')

    def test_perm_tools_model_read_false(self):
        """Even with default=True, if model-level perm_read=False → no tools."""
        self.test_mac.perm_read = False

        permitted = self._perm_tools_as(self.test_user)
        self.assertEqual(permitted, set(),
                         'perm_read=False on model blocks all tools')

    # ═════════════════════════════════════════════════════════════════
    # inactive tools
    # ═════════════════════════════════════════════════════════════════

    def test_perm_tools_inactive_tool_excluded(self):
        """Inactive tools are excluded from ``perm_tools()``."""
        inactive = self._find_tool('get_customers')
        inactive.active = False

        permitted = self._perm_tools_as(self.test_user)
        self.assertNotIn(inactive.id, permitted,
                         'Inactive tools must be excluded')

    # ═════════════════════════════════════════════════════════════════
    # uniqueness constraint
    # ═════════════════════════════════════════════════════════════════

    def test_unique_mac_tool(self):
        """Duplicate (mac_id, tool_id) is rejected."""
        tool = self._find_tool('get_customers')
        self.ToolAcl.create({
            'mac_id': self.test_mac.id,
            'tool_id': tool.id,
            'perm_read': True,
        })
        with self.assertRaises(Exception):
            self.ToolAcl.create({
                'mac_id': self.test_mac.id,
                'tool_id': tool.id,
                'perm_read': False,
            })

    # ═════════════════════════════════════════════════════════════════
    # cascade delete
    # ═════════════════════════════════════════════════════════════════

    def test_cascade_delete_mac(self):
        """Deleting ir.model.access cascades to tool ACL records."""
        tool = self._find_tool('get_customers')
        acl = self.ToolAcl.create({
            'mac_id': self.test_mac.id,
            'tool_id': tool.id,
            'perm_read': True,
        })
        acl_id = acl.id
        self.test_mac.unlink()

        self.assertFalse(
            self.ToolAcl.search([('id', '=', acl_id)]),
            'Tool ACL must be deleted when ir.model.access is deleted',
        )

    # ═════════════════════════════════════════════════════════════════
    # One2many integrity
    # ═════════════════════════════════════════════════════════════════

    def test_mac_has_tac_ids(self):
        """``ir.model.access`` One2many ``mcp_base_tac_ids`` reflects ACL."""
        acl = self.ToolAcl.create({
            'mac_id': self.test_mac.id,
            'tool_id': self._find_tool('get_customers').id,
            'perm_read': True,
        })
        self.assertIn(acl.id, self.test_mac.mcp_base_tac_ids.ids)

    # ═════════════════════════════════════════════════════════════════
    # multiple groups / multiple mac
    # ═════════════════════════════════════════════════════════════════

    def test_multiple_groups_merge(self):
        """A user in two groups sees the union of permitted tools."""
        # Group 2 has default=False, except one tool explicitly allowed.
        group2 = self.env['res.groups'].create({
            'name': 'Test MCP ACL Group 2',
        })
        mac2 = self.ModelAccess.create({
            'name': 'test group2 access',
            'model_id': self.test_model.id,
            'group_id': group2.id,
            'perm_read': True,
            'perm_mcp_base_tool_default_read': False,
        })
        allowed_tool = self._find_tool('greet_customer')
        self.ToolAcl.create({
            'mac_id': mac2.id,
            'tool_id': allowed_tool.id,
            'perm_read': True,
        })

        # Add group2 to the test user
        self.test_user.groups_id = [(4, group2.id)]

        permitted = self._perm_tools_as(self.test_user)
        # From group_user: all tools (default=True)
        # From group2: only greet_customer (explicit allow)
        # Union should be all tools
        tool_ids = {t.id for t in self.tools}
        self.assertEqual(permitted, tool_ids,
                         'Union of two groups = all tools')

    def test_multiple_mac_restrictive_union(self):
        """When two groups both restrict → only tools ANY group allows pass."""
        # Remove default group and set up two restrictive groups
        self.test_user.groups_id = [(3, self.env.ref('base.group_user').id)]
        self.test_mac.unlink()

        customer_tool = self._find_tool('get_customers')
        greet_tool = self._find_tool('greet_customer')

        for gname, tool in [('Group A', customer_tool), ('Group B', greet_tool)]:
            g = self.env['res.groups'].create({'name': gname})
            mac = self.ModelAccess.create({
                'name': f'{gname} access',
                'model_id': self.test_model.id,
                'group_id': g.id,
                'perm_read': True,
                'perm_mcp_base_tool_default_read': False,
            })
            self.ToolAcl.create({
                'mac_id': mac.id,
                'tool_id': tool.id,
                'perm_read': True,
            })
            self.test_user.groups_id = [(4, g.id)]

        permitted = self._perm_tools_as(self.test_user)
        self.assertEqual(permitted, {customer_tool.id, greet_tool.id},
                         'Union of restrictive groups = allowed tools')
