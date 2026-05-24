# -*- coding: utf-8 -*-
# @Time         : 10:46 2025/10/17
# @Author       : Chris
# @Description  :
import logging
import re
from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import List, Optional, Dict, Iterable, Type

import jinja2
import jinja2.meta
import jmespath
from odoo import fields, _
from odoo.models import BaseModel

from .libs import jmespath_ex, jinja2_ex
from .recs import RecordSet
from .util import get_field_def, field_type2python_type, RecordDictAdapter

_logger = logging.getLogger(__name__)


class AliasNode(ABC):
    _REGEX_EXPAND = re.compile(r"^\s*(?:(\w+(?:\.\w+)*)\s*=>\s*)?(.*)$", re.DOTALL)
    _REGEX_FIELD = re.compile(r"^\w+(\.\w+)*$")
    _REGEX_DOTPATH = re.compile(r"^\s*(\w+(?:\.\w+)*)\s*$")  # Looser restriction.
    _MODE2CLS: Dict[str, type] = {}

    def __init__(self, alias: str, path: str):
        self.alias = self._validate_path(alias, "alias")  # Alias of current node.
        self.path = path
        self.help = None
        self._fields = None

    @property
    def is_complex(self):
        return True

    @property
    def fields(self) -> Iterable[str]:
        if self._fields is None:
            self._fields = self._parse_fields()
        return self._fields

    @classmethod
    def register(cls, mode: str, t: Type["AliasNode"]):
        existing_t = t
        if existing_t is not t:
            raise Exception(f"Mode `{mode}` has already been registered as `{existing_t}`.")
        cls._MODE2CLS[mode] = t

    @classmethod
    def parse(cls, alias: str, mode, path: str, help_: str = None) -> "AliasNode":
        """
        Parse alias text into AliasNode. Supports three modes:

        1. Field mode: Simple dot notation path
           Example: `partner_id.company_id.name`

        2. JMESPath mode: JSON query expression for complex data transformation
           Example: `{name: partner_id.name, email: partner_id.email}`

        3. Jinja2 mode: Template string for formatted output
           Example: `Name is {{ rec.partner_id.name }}`
        
        All modes support accessing record fields through the `rec` context variable in templates.
        """
        t = cls._MODE2CLS.get(mode)
        if not t:
            raise KeyError(_("Alias mode `%s` not registered.") % (mode, ))
        root: AliasNode = t(alias, path)
        root.help = help_
        return root

    def read(self, rec, _check=False):
        """
        Read data from a record.
        :param rec: Empty or single recordset.
        :param _check: Internal use only, use to check complex lias field existence.
        :return: Scalar or object.
        """
        try:
            return self._read(rec, _check)
        except Exception as e:
            raise Exception(f"{type(self).__name__} query failed for alias '{self.alias}': {str(e)}") from e

    @abstractmethod
    def _read(self, rec, _check: bool):
        pass

    @abstractmethod
    def _parse_fields(self) -> Iterable[str]:
        pass

    @classmethod
    def _validate_path(cls, path: str, kind: str) -> str:
        if not path:  # Emtpy path means `self`
            return ""
        if not cls._REGEX_FIELD.fullmatch(path):
            raise Exception(f"Invalid {kind} `{path}`. Expect format: `xxx.yyy.zzz`")
        return path

    def __str__(self):
        return f"{type(self).__name__}[{self.alias or ''}]({self.path})"
        
        
class AliasField(AliasNode):
    def __init__(self, alias: str, path: str):
        super().__init__(alias, path)

    @property
    def is_complex(self):
        return False

    def _parse_fields(self) -> Iterable[str]:
        return [self.path]

    def _read(self, rec, _check=False):
        """
        Read data from a record.
        :param rec: Empty or single recordset.
        :param _check: Internal use only, use to check complex lias field existence.
        :return: Scalar or object.
        """
        path = self.path
        b_x2m = False
        if path:
            # Check whether path is x2m
            chips = path.split(".")
            p_rec = rec
            for chip in chips:
                f_meta: fields.Field = p_rec._fields[chip]
                if f_meta.type in ('one2many', 'many2many'):
                    b_x2m = True
                    break
                p_rec = p_rec[chip]
            res = rec.mapped(path)
        else:
            res = rec.name_get()
        if b_x2m:
            return res
        return res[0] if res else None


class AliasJMESPath(AliasNode):
    def __init__(self, alias: str, path: str):
        super().__init__(alias, path)
        self._jmespath = jmespath.compile(path)

    def _parse_fields(self) -> Iterable[str]:
        return jmespath_ex.extract_fields(self._jmespath)

    def _read(self, rec, _check: bool):
        if not rec:
            return None
        obj = RecordDictAdapter(rec, _check)
        return self._jmespath.search({
            "rec": obj,
        })


class AliasJinja2(AliasNode):
    def __init__(self, alias: str, path: str):
        super().__init__(alias, path)
        self._template = jinja2.Template(self.path)

    def _parse_fields(self) -> Iterable[str]:
        return jinja2_ex.extract_fields(self.path)

    def _read(self, rec, _check: bool):
        if not rec:
            return None
        obj = RecordDictAdapter(rec, _check)
        return self._template.render(rec=obj)


AliasNode.register("field", AliasField)
AliasNode.register("jmespath", AliasJMESPath)
AliasNode.register("jinja2", AliasJinja2)


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
