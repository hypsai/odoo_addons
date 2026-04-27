# -*- coding: utf-8 -*-
# @Time         : 19:16 2026/4/27
# @Author       : Chris
# @Description  :
from odoo.release import version_info

ODOO_MAJOR_VERSION = version_info[0]


def request_update_env(req, uid: int):
    if ODOO_MAJOR_VERSION >= 16:
        req.update_env(uid)
    else:
        req.uid = uid
        req._env = None


def registry_clear_cache(registry):
    if ODOO_MAJOR_VERSION >= 17:
        registry.clear_cache()
    else:
        registry.clear_caches()


def root_patch_get_request():
    # ---- Monkey Patch Start ----
    # Odoo Controller is strict to request type and endpoint type.
    # We need to make a monkey patch to loose this restriction for mcp endpoint.
    # This patch wrap all request to mcp endpoint as HTTPRequest, then controller will handle http request manually,
    # no matter it is http or json request.
    if ODOO_MAJOR_VERSION == 12:
        pass
    elif 13 <= ODOO_MAJOR_VERSION <= 15:  # Patch V13~15
        from odoo.http import Root, HttpRequest

        _original_get_request = Root.get_request

        def _patched_get_request(self, httprequest):
            if httprequest.path == '/mcp':
                return HttpRequest(httprequest)
            return _original_get_request(self, httprequest)

        Root.get_request = _patched_get_request
    # ---- Monkey Patch End ---


def registry_register_temp_model(registry, cr, Model):
    """Register a temporary model in the registry (Odoo 12-19 compatible)
    
    Args:
        registry: The Odoo registry
        cr: Database cursor
        Model: The model class to register
    
    Returns:
        str: The model name
    """
    model_name = Model._name
    
    if ODOO_MAJOR_VERSION >= 19:
        # Odoo 19+ uses registry.load()
        registry.load(cr, [Model])
    else:
        # Odoo 12-18 uses Model._build_model()
        registry.models[model_name] = Model._build_model(registry, cr)
    
    return model_name
