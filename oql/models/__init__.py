from . import base
from . import oql_term
from . import oql_term_domain
from . import oql_alias
from . import oql_alias_line

from odoo.tools import config

if config.get("test_enable"):
    from ..tests import test_model_defs
