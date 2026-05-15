# -*- coding: utf-8 -*-
# @Time         : 17:50 2025/10/15
# @Author       : Chris
# @Description  :
import os.path
from typing import Optional

import lark
from lark.exceptions import VisitError
from odoo import models, _
from odoo.fields import _RelationalMulti
from odoo.tools.safe_eval import safe_eval

from .acl import OqlAcl
from .alias import AliasRule
from .recs import *
from .util import KeyPassingDefaultDict, tn

_logger = logging.getLogger(__name__)


class OqlMeta:
    def __init__(self, env):
        self.env = env
        self.acl = OqlAcl(env)
        self._term_fields = self._load_term_fields()
        self._term2domains: Dict[Term, List[OqlDomain]] = KeyPassingDefaultDict(self._load_domains)  # Lazy loading.
        self._model2rule: Dict[str, AliasRule] = KeyPassingDefaultDict(self._load_rule)  # Lazy loading.
        self._model2alias2path: Dict[str, Dict[str, str]] = KeyPassingDefaultDict(self._load_alias)  # Lazy loading.
        self._all_terms_loaded = False

    def get_domains(self, term: str):
        domains = self._term2domains[Term(term)]
        return domains

    def get_path(self, model: str, opr: str, value, raises=True):
        rule = self._model2rule[model]
        if rule is None:
            if raises:
                raise Exception(f"No field path rule found for operation `{model} ({opr}) {value}`.")
            return None
        return rule.get_path(opr, value, raises)

    def get_path_by_alias(self, model: str, alias: str) -> Optional[str]:
        alias2path = self._model2alias2path[model]
        return alias2path.get(alias)

    def get_term2domains(self) -> Dict[Term, List[OqlDomain]]:
        if not self._all_terms_loaded:
            term2domains = self._load_terms([])
            self._term2domains.update(term2domains)
            self._all_terms_loaded = True
        return self._term2domains

    def get_alias2path(self, model: str) -> Dict[str, str]:
        return self._model2alias2path[model]

    def _load_term_fields(self):
        """Load fields that have a relation to `oql.term`."""
        env = self.env
        perm_models = self.acl.perm_models("read")
        fields = env['ir.model.fields'].sudo().search([
            '|', ('ttype', '=', 'many2one'), ('ttype', '=', 'many2many'),
            ('relation', '=', "oql.term"),
            ('model', 'in', list(perm_models)),
        ])
        return fields

    def _load_domains(self, term: str) -> List[OqlDomain]:
        if self._all_terms_loaded:
            return []  # No need to query anymore.
        term2domains = self._load_terms([term])
        return next(iter(term2domains.values())) if term2domains else []

    def _load_terms(self, terms: List[str]) -> Dict[Term, List[OqlDomain]]:
        """
        Load a term or all terms.
        :param terms: Name of the terms to be loaded. Input empty list to load all terms.
        :return: {term1: [term_domain1, ...], ...}
        """
        term2domains: Dict[Term, List[OqlDomain]] = defaultdict(list)
        env = self.env
        acl = self.acl
        perm_models = acl.perm_models("read")
        # 1 Search all Many2One and Many2Many fields that refer to 'oql.term'
        fields = self._term_fields
        # 2 Load terms.
        term2model2name2domains = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        # 2.1 Reference
        model2field2term2ids = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        term_criteria = [("name", "in", terms)] if terms else []
        term_recs = self.env["oql.term"].sudo().search(term_criteria)
        for field in fields:
            model = field.model
            field_name = field.name
            term2ids = model2field2term2ids[model][field_name]
            recs = env.get(model)
            if recs is None:
                continue  # Simply ignore terms of missing model.
            referring_recs = recs.sudo().search([(field_name, "in", term_recs.ids)], order="id")
            for rec in referring_recs:
                ref_term_recs = rec[field_name]
                for term_rec in ref_term_recs:
                    term2ids[term_rec.name].add(rec.id)
        for model, field2term2ids in model2field2term2ids.items():
            for field, term2ids in field2term2ids.items():
                for term, ids in term2ids.items():
                    term2model2name2domains[term][model][f"self.{field}"].append([("id", "in", list(ids))])
        # 2.2 Domain defined on term records.
        for term_rec in term_recs:
            term = term_rec.name
            for domain_rec in term_rec.domain_ids:
                model: str = domain_rec.model_id.model
                if model not in perm_models:
                    continue  # Omit domain that has no read access to bound model.
                domain_name = domain_rec.name
                str_domain = domain_rec.domain
                try:
                    domain = safe_eval(str_domain)
                    term2model2name2domains[term][model][domain_name].append(domain)
                except Exception as e:
                    _logger.warning(f"Invalid domain `{domain_name}` for term `{term}`: {str_domain} has been ignored. "
                                    f"Error: {type(e).__name__}({e})")
        # 3 Merge domains.
        for term, model2name2domains in term2model2name2domains.items():
            d_term = Term(term)
            d_domains = []
            for model, name2domains in model2name2domains.items():
                for name, domains in name2domains.items():
                    merged = [y for x in domains for y in x]  # Merge domains with '&' logic.
                    d_domains.append(OqlDomain.normalize(name, model, merged, d_term))
            term2domains[d_term] = d_domains
        return term2domains

    def _load_rule(self, model: str) -> Optional[AliasRule]:
        recs = self.env["oql.alias"].sudo().search([("model_id.model", "=", model)], limit=1)
        if not recs:
            return None
        return AliasRule.from_orm(recs)[0]

    def _load_alias(self, model: str) -> Dict[str, str]:
        recs = self.env["oql.alias.line"].sudo().search([("rule_id.model_id.model", "=", model)])
        alias2path = {x.alias: x.path for x in recs}
        ok_paths = self.acl.perm_paths(model, alias2path.values(), "read")
        alias2path = {k: v for k, v in alias2path.items() if v in ok_paths}
        return alias2path


class FieldAccess:

    model: models.Model
    """Accessing target model."""

    x2m: bool
    """Whether there is any X2Many field on the access path."""

    pre_domain: OqlDomain
    """Pre-selector domain, select some records for further filtering."""

    def __init__(self, model: models.Model, names: Iterable[str], meta: OqlMeta, pre_domain: OqlDomain = None):
        self.meta = meta
        model = model.browse()  # Make model data-inconscient.
        env = model.env
        acl = meta.acl
        # Parse
        names = list(names)
        plain_names = []
        p_recs = model
        pp_recs = None  # The recs right before p_recs in path.
        next_ = []
        b_x2m = False
        non_searchable_fields = []
        i = 0
        while i < len(names):
            name = names[i]
            # Model Field
            if hasattr(p_recs, name):
                acl.check_field(p_recs, name, "read")
                f_meta = p_recs._fields[name]
                # Check X2Many
                if not b_x2m:
                    if isinstance(f_meta, _RelationalMulti):
                        b_x2m = True
                # Check availability in search criteria.
                if not f_meta._description_searchable:
                    non_searchable_fields.append(name)
                pp_recs = p_recs
                p_recs = p_recs[name]
                plain_names.append(name)
                i += 1
                continue
            # Alias
            aliased = meta.get_path_by_alias(p_recs._name, name)
            if aliased:
                chips = aliased.split('.')
                i += 1
                names[i:i] = chips
                continue
            # Term
            domains = meta.get_domains(name)
            if domains:
                remains = names[i+1:]
                for child_domain in domains:
                    next_.append(FieldAccess(env[child_domain.model], remains, meta, child_domain))
                break
            prefix = ".".join([tn(model), *plain_names])
            raise RuntimeError(_(f"Neither `%s(.%s)` is a field nor an alias nor a term.") % (prefix, name))
        # Validate (.) term statement.
        rear = p_recs
        if next_ and not isinstance(rear, Model):
            rear_field_name = plain_names[-1]
            rear_field: fields.Field = pp_recs._fields[rear_field_name]
            raise Exception(_(f"Invalid field path `{model._name}` -> `{'.'.join(names[:i])}` (.) `{names[i]}`. "
                              f"Expect relational field before (.), got `{rear_field.type}`."))
        # Initialize instance.
        self.root = RecordSet(model, pre_domain or OqlDomain.all(model._name))
        self.model = model
        self._rear_model: Optional[Model] = rear if isinstance(rear, Model) else None
        self.names = plain_names
        self.pre_domain = pre_domain
        self.x2m = b_x2m
        self.next: List[FieldAccess] = next_
        self._non_searchable_fields = non_searchable_fields

    @property
    def as_(self):
        return '.'.join(self.names)

    @property
    def path(self):
        return '.'.join(self.names)

    @property
    def expr(self) -> str:
        chips = []
        if self.pre_domain and self.pre_domain.term:
            chips.append(self.pre_domain.term.name)
        if self.path:
            chips.append(self.path)
        if self.next:
            chips.append(self.next[0].expr)
        return '.'.join(chips)

    def eval_bin(self, opr: str, value):
        return self._eval(False, opr, value)

    def eval_una(self, opr: str):
        return self._eval(True, opr, None)

    def read(self, recs) -> list:
        """Read value from recs. Result is aligned with `recs`.
        Note: If there is any X2Many field on the field path, the result item will be list type."""
        # Check
        if recs._name != self.root.name:
            raise Exception(f"Expect `{self.root.name}` records, got `{recs._name}`.")
        # Read
        path = '.'.join(self.names)
        recs.mapped(path)  # Prefetch.
        res = [x.mapped(path) for x in recs]
        if not self.x2m:
            res = [x[0] if x else None for x in res]
        return res

    def _eval(self, una: bool, opr: str, value):
        """
        Core eval function.
        :param una: True: Unary, False: Binary
        :param opr: Unary or binary operator
        :param value: Could be None in unary model
        :return: Evaluation result
        """
        # Check
        if self._non_searchable_fields:
            raise Exception(_("Can't search with expression `%s %s %s`, "
                              "some fields in expression are not searchable: %s. "
                              "Please contact administrator for help or use a difference field.") %
                            (self.expr, opr, value, self._non_searchable_fields))
        # Eval
        root = self.root
        model = self.model
        names = self.names
        pre_domain = self.pre_domain
        if self.next:  # Branch node
            meta = self.meta
            rear_model = self._rear_model
            list_rec_set_y = []
            for child in self.next:
                rec_sets = child._eval(una, opr, value)
                for rec_set in rec_sets:
                    path = meta.get_path(rear_model._name, ".", rec_set)
                    fullpath = ".".join([*self.names, path])
                    domain = OqlDomain(f"{fullpath} in {rec_set.domain}",
                                       root.name,
                                       [(fullpath, "in", rec_set.get_recs().ids)])
                    list_rec_set_y.append(RecordSet(model, domain))
            return RecordSets(list_rec_set_y)
        elif una:
            if opr == "bool":
                if names:
                    # e.g. WHERE product_id.active
                    fullpath = ".".join(names)
                    domain = OqlDomain(f"{opr}({fullpath})",
                                       root.name,
                                       [(fullpath, "!=", False)])
                    if pre_domain:
                        domain = OqlDomain.and_(pre_domain, domain)
                    return RecordSets([RecordSet(model, domain)])
                else:
                    # e.g. WHERE Waterproof.
                    return RecordSets([RecordSet(model, pre_domain)])
            else:
                raise NotImplementedError(f"Unary operator `{opr}({tn(self.model)})` not implemented.")
        else:
            value_domain = None  # Only RecordSet value has domain info.
            if isinstance(value, RecordSet):
                value_domain = value.domain
                value = value.get_recs()
            if names:
                # Traditional Odoo domain field path.
                fullpath = ".".join(names)
                domain = OqlDomain(f"{fullpath} {opr} {value}",
                                   root.name,
                                   [(fullpath, opr, value)])
                if pre_domain:
                    domain = OqlDomain.and_(pre_domain, domain)
                return RecordSets([RecordSet(root.model, domain)])
            else:
                # Term expression: models.Model (opr) value
                if pre_domain:
                    model = self.model.search(self.pre_domain.domain)  # Apply on pre-selected subset.
                res = model.__oql_bin__(self.pre_domain, opr, value, value_domain)
                if res is None:
                    raise NotImplementedError(f"Operation `{tn(model)} {opr} {value}` not implemented yet. "
                                              f"Please implement it in `{tn(model)}.__oql_bin__`.")
                if not isinstance(res, models.Model):
                    raise Exception(f"`{model._name}.__oql_bin__` returns `{type(res)}` data, expect records.")
                return RecordSets(
                    [RecordSet(res.browse(), OqlDomain("__oql_bin__", res._name, [("id", "in", res.ids)]))])

    def __str__(self):
        return f"{type(self).__name__}({self.path}, next[{len(self.next)}])"


@lark.v_args(inline=True)
class OqlTransformer(lark.Transformer):

    CNAME = str
    INT = int
    FLOAT = float

    def __init__(self, env):
        super().__init__(True)
        self.env = env
        self.model_name = None
        self.recs = None
        self._meta = OqlMeta(env)

    def query(self, from_, select: List[FieldAccess], where: RecordSets, orderby, limit, offset):
        # 1 Categorize field access into plain and dot fields.
        dot_fas: List[FieldAccess] = []
        plain_fields: List[str] = []
        for fa in select:
            if len(fa.names) == 1:
                plain_fields.append(fa.names[0])
            else:
                dot_fas.append(fa)
        # 2 Read data.
        rec_set = where[0]
        recs = rec_set.model.search(rec_set.domain.domain, offset, limit, orderby)
        # 2.1 Read plain fields.
        if not plain_fields:
            plain_fields.append("id")
        rows = recs.read(plain_fields)
        # 2.2 Read dot-style fields.
        for fa in dot_fas:
            for row, val in zip(rows, fa.read(recs), strict=True):
                row[fa.as_] = val
        return rows

    def from_clause(self, model: str):
        acl = self._meta.acl
        acl[model].check("read", True)
        self.model_name = model
        self.recs = self.env[model].sudo()  # OQL ACL is fully controlled by OQL, so use sudo() here to pass Odoo ACL.

    def select_clause(self, fields="*"):
        if fields == "*":
            fields = self._meta.acl[self.model_name].perm_fields("read")
            fields = [FieldAccess(self.recs, [x], self._meta) for x in fields]
        return fields

    def where_clause(self, expr):
        return expr

    def orderby_clause(self, fields):
        return ','.join(f"{t[0]} {t[1]}" for t in fields)

    def offset_clause(self, num: int):
        return num

    def limit_clause(self, num: int):
        return num

    def or_expr(self, left, right):
        if isinstance(left, RecordSets) or isinstance(right, RecordSets):
            return left | right
        return left or right

    def and_expr(self, left, right):
        if isinstance(left, RecordSets) or isinstance(right, RecordSets):
            return left & right
        return left and right

    def bin_expr(self, left: FieldAccess, opr: str, right):
        opr = opr.lower()
        return left.eval_bin(opr, right)

    def dot_expr(self, field: FieldAccess):
        return field.eval_una("bool")

    def fields(self, *fields):
        return fields

    def orderby_fields(self, *fields):
        return fields

    def model(self, *args):
        return '.'.join(args)

    def field(self, *args: str):
        return FieldAccess(self.recs, args, self._meta)

    def orderby_field(self, name: str, dir_: str):
        return name, dir_ or "asc"

    def string(self, value):
        return value[1:-1]

    def TRUE(self, value):
        return True

    def FALSE(self, value):
        return False

    def NULL(self, value):
        return None

    def array(self, *values):
        return values

    @classmethod
    def _type_check_bin(cls, left, opr, right, left_expr: str, right_expr: str):
        hint_expr = f"Expr: {left_expr} ({opr}) {right_expr}"
        if opr == ".":
            if not isinstance(left, models.AbstractModel):
                raise TypeError(f"Expect `{tn(models.AbstractModel)}` instance at left, got `{tn(left)}`. {hint_expr}")
            if isinstance(right, models.AbstractModel):
                if left._name != right._name:
                    raise TypeError(f"Left type `{tn(left)}` and right `{tn(right)}` are inconsistent. {hint_expr}")

    def __default_token__(self, token):
        return str(token)


class OqlReader:
    def __init__(self):
        fp = os.path.join(os.path.dirname(__file__), "oql.lark")
        self.lark = lark.Lark.open(fp, parser="lalr")
        self.parser = self.lark.parser

    def query(self, s: str, transformer: lark.Transformer):
        tree = self.parser.parse(s)
        try:
            result = transformer.transform(tree)
        except VisitError as ve:
            # Re-raise the original exception with its original traceback
            raise ve.orig_exc.with_traceback(ve.orig_exc.__traceback__)
        return result


reader = OqlReader()  # Global reader.
