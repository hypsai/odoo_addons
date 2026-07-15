# -*- coding: utf-8 -*-
# @Time         : 17:17 2026/5/29
# @Author       : Chris
# @Description  : Hot-reload utility – refresh models to pick up dynamically
#                 added fields and sync the DB schema without a module upgrade.
import logging
from collections import defaultdict

from odoo.release import version_info

ODOO_VERSION = version_info[0]
_logger = logging.getLogger(__name__)


def refresh_models(env, model_names):
    """Re-setup and sync DB schema for the given models without module upgrade.

    Performs the same three steps that Odoo runs during a module upgrade:

    1. **Re-setup** – ``_setup_base`` → ``_setup_fields`` → ``_setup_complete``
       so that dynamically-added fields and their ``@api.depends`` are
       registered in ``registry.field_depends``.
    2. **Sync DB schema** – ``init_models`` to create missing columns and indexes.
    3. **Signal** – notify the registry so other processes see the changes.

    :param env: Odoo Environment
    :param model_names: iterable of model names (e.g. ``['sale.order']``)
    """
    registry = env.registry
    cr = env.cr
    model_names = list(model_names)
    if not model_names:
        return

    # ---- 1. Re-setup target models ----
    for model_name in model_names:
        if model_name in registry:
            cls = registry[model_name]
            cls._setup_done = False

    for model_name in model_names:
        if model_name in registry:
            model = env[model_name]
            model._setup_base()

    registry._m2m = defaultdict(list)
    try:
        for model_name in model_names:
            if model_name in registry:
                model = env[model_name]
                model._setup_fields()
    finally:
        del registry._m2m

    for model_name in model_names:
        if model_name in registry:
            model = env[model_name]
            model._setup_complete()

    # ---- 2. Re-collect field_depends ----
    for model_name in model_names:
        if model_name in registry:
            model = env[model_name]
            for field in model._fields.values():
                depends, depends_context = field.get_depends(model)
                registry.field_depends[field] = tuple(depends)
                registry.field_depends_context[field] = tuple(depends_context)

    # ---- 3. Invalidate lazy_property caches ----
    from odoo.tools.func import lazy_property
    registry_dict = vars(registry)
    for attr_name in list(registry_dict):
        if isinstance(getattr(type(registry), attr_name, None), lazy_property):
            registry_dict.pop(attr_name, None)

    # ---- 4. Sync DB schema ----
    registry.init_models(cr, model_names, {'update_custom_fields': True})

    # ---- 5. Signal registry change ----
    registry.registry_invalidated = True
    registry.cache_invalidated = True
    try:
        registry.signal_changes()
    except Exception:
        _logger.debug("signal_changes failed (non-critical)", exc_info=True)
