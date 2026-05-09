# -*- coding: utf-8 -*-
# @Time         : 11:38 2026/5/6
# @Author       : Chris
# @Description  :
from typing import Dict, Union, List, Set, Literal

from .util import KeyPassingDefaultDict


class OqlAcl:
    """Access control checker for the user bound to a given `env`."""

    def __init__(self, env):
        self.env = env
        self._model2acl: Dict[str, OqlModelAcl] = KeyPassingDefaultDict(self._load_model)

    def __getitem__(self, model_name: str) -> "OqlModelAcl":
        return self._model2acl[model_name]

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
        self._perm_read = None
        self._perm_write = None

    @property
    def perm_read(self):
        if self._perm_read is None:
            self._perm_read = self.name in self._mac.perm_fields("read")
        return self._perm_read

    @property
    def perm_write(self):
        if self._perm_write is None:
            self._perm_write = self.name in self._mac.perm_fields("write")
        return self._perm_write
