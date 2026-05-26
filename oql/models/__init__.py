from . import base
from . import oql_term
from . import oql_term_domain
from . import oql_alias
from . import oql_alias_line
from . import oql_acl_field
from . import oql_acl_alias
from . import ir_model_access
from . import oql_workbench_state

from odoo.tools import config

if config.get("test_enable"):
    from ..tests import test_model_defs
