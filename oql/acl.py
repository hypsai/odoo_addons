# -*- coding: utf-8 -*-
# @Time         : 11:38 2026/5/6
# @Author       : Chris
# @Description  :
from typing import Dict, Union, List, Set, Literal

from odoo import models, _
from odoo.exceptions import AccessError

from .util import KeyPassingDefaultDict


class OqlAcl:
    """Access control checker for the user bound to a given `env`."""

    def __init__(self, env):
        self.env = env
        self._model2acl: Dict[str, OqlModelAcl] = KeyPassingDefaultDict(self._load_model)

    def __getitem__(self, model_name: str) -> "OqlModelAcl":
        return self._model2acl[model_name]

    def check_field(self, recs: models.Model, field: str, mode: Literal["read", "write"]):
        model = recs._name
        if not self[model][field].check(mode):
            document_kind = self.env['ir.model']._get(model).name or model
            raise AccessError(_("You are not allowed to %s field '%s' of '%s' (%s) records.",
                                mode, field, document_kind, model))

    def _load_model(self, model_name: str) -> "OqlModelAcl":
        return OqlModelAcl(self.env, model_name)


class OqlModelAcl:
    """Model level ACL."""

    def __init__(self, env, model_name: str):
        self.env = env
        self.model_name = model_name
        self._mode2fields: Dict[str, set] = KeyPassingDefaultDict(self._check_fields)

    def __getitem__(self, field_name: Union[str, List[str]]) -> Union["OqlFieldAcl", List["OqlFieldAcl"]]:
        """Get field or fields ACL."""
        if isinstance(field_name, list):
            return [OqlFieldAcl(x, self) for x in field_name]
        return OqlFieldAcl(field_name, self)

    def perm_fields(self, mode: Literal["read", "write"]) -> Set["str"]:
        """Return fields that have the specified `mode` access."""
        return self._mode2fields[mode]

    def _check_fields(self, mode: str):
        return set(self.env["oql.acl.field"].check_fields(self.model_name, mode))


class OqlFieldAcl:
    """Lazy loading field ACL."""

    def __init__(self, name: str, mac: OqlModelAcl):
        self.name = name
        self._mac = mac

    @property
    def perm_read(self):
        return self.check("read")

    @property
    def perm_write(self):
        return self.check("write")

    def check(self, mode: Literal["read", "write"]):
        return self.name in self._mac.perm_fields(mode)
