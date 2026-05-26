# -*- coding: utf-8 -*-
# @Time         : 19:16 2026/4/27
# @Author       : Chris
# @Description  :
from odoo.release import version_info

ODOO_VERSION = version_info[0]


def request_update_env(req, uid: int):
    if ODOO_VERSION >= 16:
        req.update_env(uid)
    else:
        req.uid = uid
        req._env = None
    # Inject user preferences (lang, tz, ...) that session-based auth
    # normally provides but non-session auth (API key) bypasses.
    context_overrides = req.env.user.context_get()
    if hasattr(req, 'update_context'):
        req.update_context(**context_overrides)
    else:
        req._env = req.env(
            context=dict(req.env.context, **context_overrides),
        )


def root_patch_get_request():
    # ---- Monkey Patch Start ----
    # Odoo Controller is strict to request type and endpoint type.
    # We need to make a monkey patch to loose this restriction for mcp endpoint.
    # This patch wrap all request to mcp endpoint as HTTPRequest, then controller will handle http request manually,
    # no matter it is http or json request.
    if 13 <= ODOO_VERSION <= 15:  # Patch V13~15
        from odoo.http import Root, HttpRequest

        _original_get_request = Root.get_request

        def _patched_get_request(self, httprequest):
            if httprequest.path == '/mcp':
                return HttpRequest(httprequest)
            return _original_get_request(self, httprequest)

        Root.get_request = _patched_get_request
    # ---- Monkey Patch End ---


def is_api_model(method):
    """Check whether `method` is decorated with `api.model` or `api.create_multi`"""
    if ODOO_VERSION >= 18:
        return getattr(method, "_api_model", False)
    else:
        odoo_api = getattr(method, "_api", None)
        return odoo_api == "model" or odoo_api == "model_create"
