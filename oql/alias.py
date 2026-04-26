# -*- coding: utf-8 -*-
# @Time         : 10:46 2025/10/17
# @Author       : Chris
# @Description  :
from dataclasses import dataclass
from typing import List, Optional

from odoo.models import BaseModel

from .models.oql_alias_line import OqlAliasLine
from .recs import RecordSet
from .util import get_field_def, field_type2python_type


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
                rec_line: OqlAliasLine
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
