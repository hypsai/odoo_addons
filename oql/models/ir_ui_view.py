# @Time         : 2026/9/4
# @Author       : Chris
# @Description  : Align ir.ui.view field visibility with oql.acl.field.

from odoo import models

from odoo.addons.base.models.ir_ui_view import NameManager


class _OqlField:
    """Field proxy whose ``groups`` serves the OQL read verdict.

    Readable -> ``''``, so the native postprocessor keeps the node; denied ->
    ``'.'``, a group nobody has, so ``user_has_groups('.')`` is False and the
    native removal logic triggers. Everything else delegates to the field.
    """

    __slots__ = ('_oql_acl_field', '_oql_acl_groups')

    def __init__(self, field, groups):
        object.__setattr__(self, '_oql_acl_field', field)
        object.__setattr__(self, '_oql_acl_groups', groups)

    @property
    def groups(self):
        return self._oql_acl_groups

    def __getattr__(self, name):
        return getattr(self._oql_acl_field, name)


class _OqlFields:
    """Read-only mapping view over ``model._fields`` with one field swapped.

    ``model._fields`` is a shared class attribute that cannot be patched, and
    copying it per node costs O(field count). Only ``get``/``__getitem__`` sit
    on the native hot path, so they are O(1) shims; the rest of the dict
    protocol delegates to the underlying mapping for drop-in safety.
    """

    __slots__ = ('_oql_acl_fields', '_oql_acl_field_name', '_oql_acl_field_proxy')

    def __init__(self, fields, field_name, field_proxy):
        object.__setattr__(self, '_oql_acl_fields', fields)
        object.__setattr__(self, '_oql_acl_field_name', field_name)
        object.__setattr__(self, '_oql_acl_field_proxy', field_proxy)

    def __getitem__(self, name):
        if name == self._oql_acl_field_name:
            return self._oql_acl_field_proxy
        return self._oql_acl_fields[name]

    def get(self, name, default=None):
        if name == self._oql_acl_field_name:
            return self._oql_acl_field_proxy
        return self._oql_acl_fields.get(name, default)

    def __contains__(self, name):
        return name in self._oql_acl_fields

    def __iter__(self):
        return iter(self._oql_acl_fields)

    def __len__(self):
        return len(self._oql_acl_fields)

    def keys(self):
        return self._oql_acl_fields.keys()

    def values(self):
        return [self._oql_acl_field_proxy if name == self._oql_acl_field_name else field
                for name, field in self._oql_acl_fields.items()]

    def items(self):
        return [(name, self._oql_acl_field_proxy if name == self._oql_acl_field_name else field)
                for name, field in self._oql_acl_fields.items()]


class _OqlModel:
    """Model proxy swapping one field for its OQL-aware proxy.

    ``model._fields`` is served as a ``_OqlFields`` view; everything else
    delegates to the real model. ``_fields`` keeps its plain name because the
    native chain reads it, while the back-reference to the model lives under
    ``_oql_acl_model``.
    """

    __slots__ = ('_oql_acl_model', '_fields')

    def __init__(self, model, field_name, acl):
        object.__setattr__(self, '_oql_acl_model', model)
        readable = field_name in acl.perm_fields(model._name, 'read')
        object.__setattr__(self, '_fields', _OqlFields(
            model._fields, field_name,
            _OqlField(model._fields[field_name], '' if readable else '.'),
        ))

    def __getattr__(self, name):
        return getattr(self._oql_acl_model, name)


class _OqlNameManager(NameManager):
    """NameManager serving the OQL-aware model proxy to the native chain.

    Passes isinstance checks; the whole instance state is copied by reference
    from the real manager, so ``has_field()`` etc. keep accumulating on it.
    Only ``model`` (a contractual name the native chain reads) is swapped for
    the proxy, and ``field_info`` is delegated to the real manager so
    ``fields_get()`` is computed once, not per node.
    """

    def __init__(self, name_manager, field_name, acl):  # noqa
        self.__dict__.update(name_manager.__dict__)
        self._oql_acl_name_manager = name_manager
        self.model = _OqlModel(name_manager.model, field_name, acl)

    @property
    def field_info(self):
        return self._oql_acl_name_manager.field_info


class OqlIrUiView(models.Model):
    """Align view field visibility with oql.acl.field.

    Patch with wrapped `NameManager`.
    """

    _inherit = "ir.ui.view"

    def _oql_acl(self):
        """Return the `oql.acl.field` accessor bound to the real user.

        Postprocessing may run on a sudo-ed view (e.g. `fields_view_get`
        browses the view with `sudo()`), while `perm_fields` short-circuits
        to "all fields" under `su`. The visibility verdict must always be
        computed as the real user -- the same spirit as the native
        `user_has_groups`, which ignores `su` too -- so rebind the env with
        `su=False`. For the true superuser (uid == SUPERUSER_ID) the env
        forces `su` back to True, keeping the "superuser sees everything"
        behavior.
        """
        env = self.env
        if env.su:
            env = env(user=env.uid, su=False)
        return env['oql.acl.field']

    def _postprocess_tag_field(self, node, name_manager, node_info):
        fname = node.get('name')
        if fname and fname in name_manager.model._fields:  # noqa
            name_manager = _OqlNameManager(name_manager, fname, self._oql_acl())
        return super()._postprocess_tag_field(node, name_manager, node_info)  # noqa

    def _postprocess_tag_label(self, node, name_manager, node_info):
        fname = node.get('for')
        if fname and fname in name_manager.model._fields:  # noqa
            name_manager = _OqlNameManager(name_manager, fname, self._oql_acl())
        return super()._postprocess_tag_label(node, name_manager, node_info)  # noqa
