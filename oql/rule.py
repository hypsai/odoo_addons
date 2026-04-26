# -*- coding: utf-8 -*-
# @Time         : 10:46 2025/10/17
# @Author       : Chris
# @Description  :
from dataclasses import dataclass
from typing import List, Set, Optional
from odoo.models import BaseModel
from .util import parse_list, parse_type_list
from .recs import RecordSet


@dataclass(frozen=True)
class AliasRule:
    model: str
    lines: List["AliasRuleLine"]

    @classmethod
    def from_orm(cls, recs) -> List["AliasRule"]:
        rules = []
        for rec in recs:
            lines = []
            model = rec.model_id.model
            for rec_line in rec.line_ids:
                operators = set(parse_list(rec_line.operators))
                value_model = rec_line.value_model_id.model
                value_types = parse_type_list(rec_line.value_types, True)
                path = rec_line.path
                lines.append(AliasRuleLine(model, operators, value_model, set(value_types), path))
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
    operators: Set[str]
    value_model: Optional[str]
    value_types: Set[type]
    path: str

    def test(self, operator: str, value):
        if self.operators and operator not in self.operators:
            return False
        if self.value_model:
            if isinstance(value, RecordSet):
                if value.name == self.value_model:
                    return True
            if isinstance(value, BaseModel):
                if value._name == self.value_model:
                    return True
        if self.value_types and type(value) in self.value_types:
            return True
        return False

    def __str__(self):
        return f"Alias({self.model}|{self.path})"
