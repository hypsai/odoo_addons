# @Time         : 11:41 2026/4/28
# @Author       : Chris
# @Description  :
from . import ir_model
from . import ir_model_access
from . import mcp_base_method
from . import mcp_base_tool
from . import mcp_base_acl_tool

from odoo.tools import config
if config.get("test_enable"):
    from ..tests import test_model_defs
