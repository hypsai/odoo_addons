# -*- coding: utf-8 -*-
# @Time         : 11:38 2026/5/6
# @Author       : Chris
# @Description  :
from typing import Dict, Union, List
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
    def __init__(self, env, model_name: str):
        self.env = env
        self.model_name = model_name
        self._field2acl: Dict[str, OqlFieldAcl] = KeyPassingDefaultDict(self._load_field)
        self._perm_cache: Dict[str, bool] = {}

    def __getitem__(self, field_name: Union[str, List[str]]) -> Union["OqlFieldAcl", Dict[str, "OqlFieldAcl"]]:
        if isinstance(field_name, list):
            return {f: self._field2acl[f] for f in field_name}
        return self._field2acl[field_name]

    def _load_field(self, field_name: str) -> "OqlFieldAcl":
        perm = self._get_model_perm()
        return OqlFieldAcl(perm_read=perm.get('perm_read', False))

    def _get_model_perm(self) -> dict:
        if 'perm' not in self._perm_cache:
            IrModelAccess = self.env['ir.model.access']
            perm = IrModelAccess.check(self.model_name, raise_exception=False)
            # check returns True/False for general access, we need detailed perms
            # Using search to get the most permissive rule for the current user's groups
            domain = [('model_id.model', '=', self.model_name)]
            rules = IrModelAccess.search(domain)
            
            max_perm = {'perm_read': False, 'perm_write': False, 'perm_create': False, 'perm_unlink': False}
            for rule in rules:
                if rule.active:
                    for key in max_perm:
                        max_perm[key] = max_perm[key] or getattr(rule, key, False)
            self._perm_cache['perm'] = max_perm
        return self._perm_cache['perm']


class OqlFieldAcl:
    def __init__(self, perm_read: bool = False):
        self.perm_read = perm_read
