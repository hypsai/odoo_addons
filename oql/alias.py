# -*- coding: utf-8 -*-
# @Time         : 10:46 2025/10/17
# @Author       : Chris
# @Description  :
import re
from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import List, Optional, Dict, Iterable, Type

from odoo import fields, _
from odoo.models import BaseModel

from .libs import jmespath
from .recs import RecordSet
from .util import get_field_def, field_type2python_type, RecordDictAdapter


class AliasNode(ABC):
    _REGEX_EXPAND = re.compile(r"^\s*(?:(\w+(?:\.\w+)*)\s*=>\s*)?(.*)$", re.DOTALL)
    _REGEX_FIELD = re.compile(r"^\w+(\.\w+)*$")
    _REGEX_DOTPATH = re.compile(r"^\s*(\w+(?:\.\w+)*)\s*$")  # Looser restriction.
    _MODE2CLS: Dict[str, type] = {}

    def __init__(self, alias: str, path: str):
        self.alias = self._validate_path(alias, "alias")  # Alias of current node.
        self.path = path
        self.help = None

    @property
    def is_complex(self):
        return True

    @property
    @abstractmethod
    def fields(self) -> Iterable[str]:
        """The fields this alias node uses, in dot-style."""
        pass

    @classmethod
    def register(cls, mode: str, t: Type["AliasNode"]):
        existing_t = t
        if existing_t is not t:
            raise Exception(f"Mode `{mode}` has already been registered as `{existing_t}`.")
        cls._MODE2CLS[mode] = t

    @classmethod
    def parse(cls, alias: str, mode, path: str, help_: str = None) -> "AliasNode":
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
        return self._read(rec, _check)

    @abstractmethod
    def _read(self, rec, _check: bool):
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

    @property
    def fields(self) -> Iterable[str]:
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
                if isinstance(f_meta, fields._RelationalMulti):
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
        # Cache extracted fields
        self._cached_fields = None

    @property
    def fields(self) -> Iterable[str]:
        """
        Extract field names from JMESPath expression.
        
        Returns a list of dot-notation field paths that this JMESPath expression accesses.
        For example:
        - 'partner_id.name' -> ['partner_id.name']
        - '{name: partner_id.name, email: partner_id.email}' -> ['partner_id.name', 'partner_id.email']
        - 'order_lines[].product_id.name' -> ['order_lines.product_id.name']
        """
        if self._cached_fields is not None:
            return self._cached_fields
        
        try:
            # Parse JMESPath to AST
            ast_tree = jmespath.parser.Parser().parse(self.path)
            fields_set = set()
            self._extract_fields_from_ast(ast_tree, '', fields_set)
            self._cached_fields = list(fields_set)
            return self._cached_fields
        except Exception:
            # If parsing fails, return empty list (fallback)
            return []
    
    def _extract_fields_from_ast(self, node, prefix: str, fields_set: set):
        """
        Recursively extract field names from JMESPath AST nodes.
        
        :param node: JMESPath AST node
        :param prefix: Current field path prefix (from record root)
        :param fields_set: Set to collect complete field paths
        """
        if node is None:
            return
        
        node_type = type(node).__name__
        
        if node_type == 'Field':
            # Direct field reference - build complete path from root
            field_name = node.value
            full_path = f"{prefix}.{field_name}" if prefix else field_name
            fields_set.add(full_path)
        
        elif node_type == 'Subexpression':
            # Chained access like a.b.c
            # Left side builds the prefix, right side continues with that prefix
            self._extract_fields_from_ast(node.left, prefix, fields_set)
            # For right side, we need to get all fields from left and use them as prefix
            left_fields = set()
            self._collect_all_fields(node.left, '', left_fields)
            for left_field in left_fields:
                self._extract_fields_from_ast(node.right, left_field, fields_set)
        
        elif node_type == 'IndexExpression':
            # Array index access like items[0] - index doesn't change field path
            self._extract_fields_from_ast(node.children[0], prefix, fields_set)
        
        elif node_type in ('SliceExpression', 'Projection'):
            # Array projection like items[] - projection doesn't change field path
            self._extract_fields_from_ast(node.children[0], prefix, fields_set)
            if len(node.children) > 1:
                self._extract_fields_from_ast(node.children[1], prefix, fields_set)
        
        elif node_type == 'MultiSelectHash':
            # Object construction like {name: partner_id.name, email: partner_id.email}
            for pair in node.pairs:
                # Each expression is independent, starts from root
                self._extract_fields_from_ast(pair.expression, '', fields_set)
        
        elif node_type == 'MultiSelectList':
            # List selection like [partner_id.name, partner_id.email]
            for child in node.expressions:
                self._extract_fields_from_ast(child, '', fields_set)
        
        elif node_type == 'Comparator':
            # Comparison like partner_id.age > `18`
            self._extract_fields_from_ast(node.children[0], prefix, fields_set)
            self._extract_fields_from_ast(node.children[1], prefix, fields_set)
        
        elif node_type in ('AndExpression', 'OrExpression'):
            # Logical operations
            self._extract_fields_from_ast(node.children[0], prefix, fields_set)
            self._extract_fields_from_ast(node.children[1], prefix, fields_set)
        
        elif node_type == 'NotExpression':
            # Negation
            self._extract_fields_from_ast(node.children[0], prefix, fields_set)
        
        elif node_type == 'FunctionExpression':
            # Function calls like sort_by(order_lines, &price)
            for arg in node.arguments:
                self._extract_fields_from_ast(arg, prefix, fields_set)
        
        elif hasattr(node, 'children'):
            # Generic handling for nodes with children
            for child in node.children:
                self._extract_fields_from_ast(child, prefix, fields_set)
    
    def _collect_all_fields(self, node, prefix: str, fields_set: set):
        """
        Collect all complete field paths from a node.
        Used to get left-side fields for Subexpression handling.
        """
        if node is None:
            return
        
        node_type = type(node).__name__
        
        if node_type == 'Field':
            field_name = node.value
            full_path = f"{prefix}.{field_name}" if prefix else field_name
            fields_set.add(full_path)
        
        elif node_type == 'Subexpression':
            self._collect_all_fields(node.left, prefix, fields_set)
            left_fields = set()
            self._collect_all_fields(node.left, '', left_fields)
            for left_field in left_fields:
                self._collect_all_fields(node.right, left_field, fields_set)
        
        elif hasattr(node, 'children'):
            for child in node.children:
                self._collect_all_fields(child, prefix, fields_set)

    def _read(self, rec, _check: bool):
        if not rec:
            return None
        try:
            return self._jmespath.search(RecordDictAdapter(rec, _check))
        except Exception as e:
            raise Exception(f"JMESPath query failed for alias '{self.alias}': {str(e)}") from e


class AliasJinja2(AliasNode):

    @property
    def fields(self) -> Iterable[str]:
        return []

    def _read(self, rec, _check: bool):
        return self.path


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
