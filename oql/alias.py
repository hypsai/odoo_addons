# -*- coding: utf-8 -*-
# @Time         : 10:46 2025/10/17
# @Author       : Chris
# @Description  :
import json
import re
from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import List, Optional, Dict, Iterable

from odoo import models, fields
from odoo.models import BaseModel

from .recs import RecordSet
from .util import get_field_def, field_type2python_type, read_object, PathAwareFormatter


class AliasNode(ABC):
    _REGEX_EXPAND = re.compile(r"^\s*(?:(\w+(?:\.\w+)*)\s*=>\s*)?(.*)$", re.DOTALL)
    _REGEX_FIELD = re.compile(r"^\w+(\.\w+)*$")
    _REGEX_DOTPATH = re.compile(r"^\s*(\w+(?:\.\w+)*)\s*$")  # Looser restriction.

    def __init__(self, path: str, alias: str):
        self.path = self._validate_path(path, "field path")
        self.alias = self._validate_path(alias, "alias")  # Alias of current node.

    @property
    def is_complex(self):
        return True

    @property
    def expr(self):
        chips = []
        if self.path:
            chips.append(self.path)
            chips.append(" => ")
        chips.append(self._expr())
        return "".join(chips)

    @classmethod
    def parse(cls, text: str, alias: str, help_: str = None) -> "AliasNode":
        """
        Parse alias text into AliasNode. Supports three base formats, optionally prefixed with relational field expansion:

        Base formats:
        1. Dot path: `partner_id.company_id.name`
        2. String template: `"Partner: {partner_id.name}"`
        3. JSON mapping object (keys as aliases, values as paths):
           {
               "name": "partner_id.name",
               "addresses @ address_ids": {
                   "city": "city",
                   "country": "country_id.name"
               }
           }

        Optional expansion prefix (`field_path =>`):
        - Expands a relational field as data source for the base format
        - Examples:
          * `address_ids => country_id.name` (expand + dot path)
          * `address_ids => "Address: {city}"` (expand + string template)
          * `address_ids => {...}` (expand + JSON object)
        """
        root = cls._r_parse("", text, alias)
        root.help = help_
        return root

    def read(self, rec, _check=False):
        """
        Read data from a record.
        :param rec: Empty or single recordset.
        :param _check: Internal use only, use to check complex lias field existence.
        :return: Scalar or object.
        """
        path = self.path
        b_x2m = False
        if path:
            res = read_object(rec, path)
            if self.is_complex and not isinstance(res, models.Model):
                raise Exception(f"{self}: Result of complex alias must be records. Got `{type(res)}`")
            # Check whether path is x2m
            chips = path.split(".")
            p_rec = rec
            for chip in chips:
                f_meta: fields.Field = p_rec._fields[chip]
                if isinstance(f_meta, fields._RelationalMulti):
                    b_x2m = True
                    break
                p_rec = p_rec[chip]
        else:
            res = rec
        if b_x2m:
            if _check:
                return [self._format(res, _check)]
            return [self._format(x, _check) for x in res]
        if _check:
            return self._format(res, _check)
        return self._format(res, _check)

    @abstractmethod
    def _format(self, rec, _check: bool):
        pass

    @abstractmethod
    def _expr(self) -> str:
        """Get expr string, without expansion."""
        pass

    @classmethod
    def _r_parse(cls, path: str, obj, alias: str) -> "AliasNode":
        if isinstance(obj, str):
            # Format: xx.yy.zz
            match = cls._REGEX_DOTPATH.fullmatch(obj)
            if match:
                return AliasFieldPath("", alias, match.group(1))
            # Format: [xx.yy.zz] => ...
            match = cls._REGEX_EXPAND.fullmatch(obj)
            path_ex, body = match.groups()
            if path_ex:
                path = f"{path}.{path_ex}" if path else path_ex
            # Format [xx.yy.zz] => aa.bb
            match = cls._REGEX_DOTPATH.fullmatch(body)
            if match:
                return AliasFieldPath(path, alias, match.group(1))
            # Format [xx.yy.zz] => JSON
            try:
                obj = json.loads(body)
            except Exception as e:
                if not AliasString.is_valid_tmpl(body):
                    raise Exception(f"Invalid field path `{body}`. Expect: dot path, string template, JSON dict") from e
                obj = None
            if obj is not None:
                return cls._r_parse(path, obj, alias)
            # Format: [xx.yy.zz] => StringTemplate
            return AliasString(body, path, alias)
        elif isinstance(obj, dict):
            node = AliasDict(path, alias)
            alias2child = node.alias2child
            for key, value in obj.items():
                chips = key.split("@")
                if len(chips) == 1:
                    if not isinstance(value, str):
                        raise Exception(f"Value of simple alias mapping `{value}` must be `str`, got `{value}`.")
                    child_alias, child_path = chips[0].strip(), value.strip()
                    alias2child[child_alias] = cls._r_parse(child_path, value, child_alias)
                elif len(chips) == 2:
                    child_alias, child_path = chips[0].strip(), chips[1].strip()
                    alias2child[child_alias] = cls._r_parse(child_path, value, child_alias)
                else:
                    raise Exception(f"Invalid complex alias key `{key}`. Format: `alias @ path`")
            return node
        else:
            raise Exception(f"Invalid complex mapping node `{obj}`, expect `dict` or `str`. Path: `{path}`")

    @classmethod
    def _validate_path(cls, path: str, kind: str) -> str:
        if not path:  # Emtpy path means `self`
            return ""
        if not cls._REGEX_FIELD.fullmatch(path):
            raise Exception(f"Invalid {kind} `{path}`. Expect format: `xxx.yyy.zzz`")
        return path

    def __str__(self):
        return f"{type(self).__name__}[{self.alias or ''}]({self.expr})"
        
        
class AliasFieldPath(AliasNode):
    def __init__(self, path: str, alias: str, field: str):
        super().__init__(path, alias)
        self.field = field

    @property
    def is_complex(self):
        return bool(self.path)

    def _format(self, rec, _check: bool):
        return read_object(rec, self.field)

    def _expr(self) -> str:
        return self.field
    
    
class AliasSummary(AliasNode, ABC):
    def __init__(self, path: str, alias: str):
        super().__init__(path, alias)
        self.path: str = self._validate_path(path, "field path")

    @abstractmethod
    def get_children(self) -> Iterable["AliasNode"]:
        pass


class AliasDict(AliasSummary):
    def __init__(self, path: str, alias: str):
        super().__init__(path, alias)
        self.alias2child: Dict[str, AliasNode] = {}

    def get_children(self) -> Iterable["AliasNode"]:
        return self.alias2child.values()

    def _format(self, rec, _check: bool):
        return {k: v.read(rec) for k, v in self.alias2child.items()}

    def _expr(self) -> str:
        return json.dumps({
            f"{alias}@{node.path}" if node.path and isinstance(node, AliasDict) else alias: node._expr()
            for alias, node in self.alias2child.items()
        })

        
class AliasString(AliasSummary):
    """String template, format: 'Partner name is {partner_id.name}.'"""
    def __init__(self, tmpl: str, path: str, alias: str):
        super().__init__(path, alias)
        self.tmpl = tmpl
        self.path = path
        self._name2var: Dict[str, AliasNode] = {
            p: AliasFieldPath("", p, p) for _, p, _, _ in PathAwareFormatter().parse(tmpl) if p
        }

    def get_children(self) -> Iterable["AliasNode"]:
        return self._name2var.values()

    def _format(self, rec, _check: bool):
        kwargs = {k: v.read(rec, _check) for k, v in self._name2var.items()}
        string = PathAwareFormatter().vformat(self.tmpl, [], kwargs)
        return string

    def _expr(self) -> str:
        return self.tmpl

    @classmethod
    def is_valid_tmpl(cls, tmpl: str):
        try:
            PathAwareFormatter().parse(tmpl)
            return True
        except:
            return False


@dataclass(frozen=True)
class AliasRule:
    model: str
    lines: List["AliasRuleLine"]

    @classmethod
    def from_orm(cls, recs) -> List["AliasRule"]:
        env = recs.env
        rules = []
        for rec in recs:
            lines = []
            model = rec.model_id.model
            for rec_line in rec.line_ids:
                if not rec_line.enable_shorthand:
                    continue
                path = rec_line.path
                field_def = get_field_def(env[model], path)
                if field_def.relational:
                    value_model = field_def.comodel_name
                    value_type = None
                else:
                    value_model = None
                    value_type = field_type2python_type(field_def.type)
                lines.append(AliasRuleLine(model, value_model, value_type, path))
            rules.append(AliasRule(model, lines))
        return rules

    def get_path(self, operator: str, value, raises=True):
        matches = [x for x in self.lines if x.test(operator, value)]
        paths = set(x.path for x in matches)
        if len(paths) == 0:
            if raises:
                raise Exception(f"No field path rule found for operation `{self.model} ({operator}) {value}`.")
            return None
        elif len(paths) == 1:
            return matches[0].path
        else:
            raise Exception(f"Multiple incompatible field path rules found operation `{self.model} ({operator}) {value}`: {matches}")


@dataclass(frozen=True)
class AliasRuleLine:
    model: str
    value_model: Optional[str]
    value_type: Optional[type]
    path: str

    def test(self, operator: str, value):
        if self.value_model:
            if isinstance(value, RecordSet):
                if value.name == self.value_model:
                    return True
            elif isinstance(value, BaseModel):
                if value._name == self.value_model:
                    return True
        if self.value_type and type(value) is self.value_type:
            return True
        return False

    def __str__(self):
        return f"Alias({self.model}|{self.path})"
