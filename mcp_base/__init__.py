from odoo import api

from . import models
from . import controllers
from .decorators import mcp_tool


def _post_init_sync_tools(cr, registry):
    """Post-install hook: sync @mcp_tool methods into mcp.base.tool ORM records."""
    env = api.Environment(cr, 1, {})  # admin user
    env['mcp.base.tool']._sync_tools_from_registry()
