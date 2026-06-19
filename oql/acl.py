# @Time         : 11:38 2026/5/6
# @Author       : Chris
# @Description  :
import logging
from collections import defaultdict
from typing import Dict, Union, List, Set, Literal, Iterable, Tuple

from odoo import models, _, fields
from odoo.exceptions import AccessError

from .compatible import AND
from .alias import AliasNode
from .util import KeyPassingDefaultDict

_logger = logging.getLogger(__name__)


class OqlAcl:
    """Access control checker for the user bound to a given `env`."""

    def __init__(self, env):
        self.env = env
        self._model2acl: Dict[str, OqlModelAcl] = KeyPassingDefaultDict(self._load_model)
        self._mode2models: Dict[str, Set[str]] = KeyPassingDefaultDict(env["ir.model.access"].perm_models)

    def __getitem__(self, model_name: str) -> "OqlModelAcl":
        return self._model2acl[model_name]

    def check_field(self, recs: models.Model, field: str, mode: Literal["read", "write"]):
        model = recs._name
        if not self[model][field].check(mode):
            document_kind = self.env['ir.model']._get(model).name or model
            raise AccessError(_("You are not allowed to %s field '%s' of '%s' (%s) records.",
                                mode, field, document_kind, model))

    def perm_models(self, mode: Literal["read", "write"]) -> Set[str]:
        return self._mode2models[mode]

    def perm_paths(self, model: str, paths: Iterable[str], mode: Literal["read", "write"]) -> Set[str]:
        """Find out dot-style paths on `model` that current user has access to."""
        env = self.env

        # BFS check, layer by model.
        model2stack_chips: Dict[str, List[Tuple[str, List[str]]]] = {
            model: [(x, list(reversed(x.split('.')))) for x in paths]
        }
        ok_paths = set()
        while model2stack_chips:
            new_model2stack_chips: Dict[str, List[Tuple[str, List[str]]]] = defaultdict(list)
            for comodel, stack_chips in model2stack_chips.items():
                recs = env[comodel]
                model_acl = self[comodel]
                _fields = recs._fields
                for path, chips in stack_chips:
                    chip = chips.pop()
                    f_meta: fields.Field = _fields.get(chip)
                    if not f_meta:
                        _logger.warning(_(f"Path `%s` is invalid on model `%s`, field `%s` not found from `%s`"),
                                        path, model, chip, comodel)
                        continue
                    if not model_acl[chip].check(mode):
                        # No access right to this field, skip.
                        continue
                    if len(chips) == 0:
                        # This is a rear chip, path access completed.
                        ok_paths.add(path)
                        continue
                    if not f_meta.relational:
                        _logger.warning(_(f"Path `%s` is invalid on model `%s`, field `%s`.`%s` is not relational field."),
                                        path, model, comodel, chip)
                        continue
                    new_model2stack_chips[f_meta.comodel_name].append((path, chips))
            # Move to next layer.
            model2stack_chips = new_model2stack_chips

        return ok_paths

    def _load_model(self, model_name: str) -> "OqlModelAcl":
        return OqlModelAcl(self, model_name)


class OqlModelAcl:
    """Model level ACL."""

    def __init__(self, acl: "OqlAcl", model_name: str):
        self.acl = acl
        self.env = acl.env
        self.model_name = model_name
        self._mode2fields: Dict[str, set] = KeyPassingDefaultDict(self._perm_fields)
        self._mode2aliases: Dict[str, set] = KeyPassingDefaultDict(self._perm_aliases)

    @property
    def perm_read(self):
        return self.check("read")

    def __getitem__(self, field_name: Union[str, List[str]]) -> Union["OqlFieldAcl", List["OqlFieldAcl"]]:
        """Get field or fields ACL."""
        if isinstance(field_name, list):
            return [OqlFieldAcl(x, self) for x in field_name]
        return OqlFieldAcl(field_name, self)

    def check(self, mode: Literal["read", "write"], raises: bool = False):
        """Check access right of current model."""
        return self.env["ir.model.access"].check(self.model_name, mode, raises)

    def check_path(self, path: str, mode: Literal["read", "write"]) -> bool:
        return path in self.perm_paths([path], mode)

    def perm_fields(self, mode: Literal["read", "write"]) -> Set["str"]:
        """Return fields that have the specified `mode` access."""
        ok_fields = self._mode2fields[mode]
        # Check access rights for related fields.
        acl = self.acl
        for f_meta in self.env[self.model_name]._fields.values():
            f_meta: fields.Field
            rf_meta: fields.Field = f_meta.related_field
            if f_meta.name in ok_fields or not rf_meta:
                continue
            if rf_meta.name in acl[rf_meta.model_name]._mode2fields[mode]:
                ok_fields.add(f_meta.name)
        return ok_fields

    def perm_aliases(self, mode: Literal["read", "write"]) -> Set[str]:
        """Return aliases that have the specified `mode` access."""
        # Check direct access rights configured for aliases on current model.
        ok_aliases = self._mode2aliases[mode]

        # Check access rights for referencing fields to determine alias access right.
        alias_recs = self.env["oql.alias.line"].sudo().search(
            [("model_id.name", "=", self.model_name), ("alias", "not in", list(ok_aliases))])
        for alias_rec in alias_recs:
            node = AliasNode.parse(alias_recs.alias, alias_rec.mode, alias_rec.path)
            paths = set(node.fields)
            if not paths:  # For safety reason, decline access right inheritance if node doesn't provide paths.
                continue
            perm_paths = self.perm_paths(paths, mode)
            if len(paths) == len(perm_paths):  # All paths are allowed to be accessed.
                ok_aliases.add(alias_rec.alias)

        return ok_aliases

    def perm_paths(self, paths: Iterable[str], mode: Literal["read", "write"]) -> Set[str]:
        return self.acl.perm_paths(self.model_name, paths, mode)

    def perm_records(self, domain, mode: Literal["read", "write"]) -> list:
        """Return domain."""
        perm_domain = self.env['ir.rule']._compute_domain(self.model_name, mode=mode)
        if perm_domain:
            domain = AND([domain, perm_domain])
        return domain

    def _perm_fields(self, mode: str) -> Set[str]:
        return self.env["oql.acl.field"].perm_fields(self.model_name, mode)

    def _perm_aliases(self, mode: str) -> Set[str]:
        return self.env["oql.acl.alias"].perm_aliases(self.model_name, mode)


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
