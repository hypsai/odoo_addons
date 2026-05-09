# -*- coding: utf-8 -*-
# @Time         : 17:50 2025/10/15
# @Author       : Chris
# @Description  :
import os.path
from typing import List, Dict, Optional

import lark
from odoo import models, _
from odoo.tools.safe_eval import safe_eval

from .alias import AliasRule
from .recs import *
from .util import KeyPassingDefaultDict, tn

_logger = logging.getLogger(__name__)


class OqlMeta:
    def __init__(self, env):
        self.env = env
        self._term_fields = self._load_term_fields()
        self._term2domains: Dict[Term, List[TermDomain]] = KeyPassingDefaultDict(self._load_domains)  # Lazy loading.
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

    def get_term2domains(self) -> Dict[Term, List[TermDomain]]:
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
        fields = env['ir.model.fields'].sudo().search([
            '|', ('ttype', '=', 'many2one'), ('ttype', '=', 'many2many'),
            ('relation', '=', "oql.term"),
            ('model', '!=', 'oql.term.domain'),
        ])
        return fields

    def _load_domains(self, term: str) -> List[TermDomain]:
        if self._all_terms_loaded:
            return []  # No need to query anymore.
        term2domains = self._load_terms([term])
        return next(iter(term2domains.values()))

    def _load_terms(self, terms: List[str]) -> Dict[Term, List[TermDomain]]:
        """
        Load a term or all terms.
        :param terms: Name of the terms to be loaded. Input empty list to load all terms.
        :return: {term1: [term_domain1, ...], ...}
        """
        term2domains: Dict[Term, List[TermDomain]] = defaultdict(list)
        env = self.env
        # 1 Search all Many2One and Many2Many fields that refer to 'oql.term'
        fields = self._term_fields
        # 2 Load terms.
        term2model2name2domains = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        # 2.1 Reference
        model2field2term2ids = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        term_criteria = [("name", "in", terms)] if terms else []
        term_recs = self.env["oql.term"].search(term_criteria)
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
                model = domain_rec.model_id.model
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
                    d_domains.append(TermDomain(d_term, name, model, merged))
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
        return alias2path


class FieldAccess:
    def __init__(self, recs, names, meta: OqlMeta, domain=TermDomain.MISSING):
        self.meta = meta
        # Parse
        names = list(names)
        env = recs.env
        plain_names = []
        p_recs = recs
        next_ = []
        i = 0
        while i < len(names):
            name = names[i]
            # Model Field
            if hasattr(p_recs, name):
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
                    child_recs = env[child_domain.model].search(child_domain.domain)
                    next_.append(FieldAccess(child_recs, remains, meta, child_domain))
                break
            prefix = ".".join([tn(recs), *plain_names])
            raise RuntimeError(_(f"Neither `%s(.%s)` is a field nor an alias nor a term.") % (prefix, name))
        self.recs = recs
        self.names = plain_names
        self.domain: TermDomain = domain
        self.next: List[FieldAccess] = next_

    def eval_bin(self, opr: str, value):
        return self._eval(False, opr, value)

    def eval_una(self, opr: str):
        return self._eval(True, opr, None)

    def get_rear_recs(self) -> List[Tuple[RecordSet, Optional[str]]]:
        """Get (RecordSet, field) at the rear of this field access."""
        if self.next:
            return [y for x in self.next for y in x.get_rear_recs()]
        else:
            rear_recs = self.recs
            rear_field = None
            p = self.recs
            for name in self.names:
                p = p[name]
                if isinstance(p, models.BaseModel):
                    rear_recs = p
                else:
                    rear_field = name
            return [(RecordSet(rear_recs, self.domain), rear_field)]

    def _eval(self, una: bool, opr: str, value):
        """
        Core eval function.
        :param una: True: Unary, False: Binary
        :param opr: Unary or binary operator
        :param value: Could be None in unary model
        :return: Evaluation result
        """
        recs = self.recs
        if self.next:  # Branch node
            meta = self.meta
            list_rec_set_y = []
            for child in self.next:
                rec_sets = child._eval(una, opr, value)
                for rec_set in rec_sets:
                    path = meta.get_path(recs._name, ".", rec_set)
                    fullpath = ".".join([*self.names, path])
                    res = recs.search([(fullpath, "in", rec_set.ids)], order="id")
                    list_rec_set_y.append(RecordSet(res, rec_set.domain))
            return RecordSets(list_rec_set_y)
        elif una:
            if opr == "bool":
                return RecordSets([RecordSet(self.recs, self.domain)])
            else:
                raise NotImplementedError(f"Unary operator `{opr}({tn(self.recs)})` not implemented.")
        else:
            value_domain = TermDomain.MISSING
            if isinstance(value, RecordSet):
                value_domain = value.domain
                value = value.data
            res = recs.__oql_bin__(self.domain.info, opr, value, value_domain.info)
            if res is None:
                raise NotImplementedError(f"Operation `{tn(recs)} {opr} {value}` not implemented yet. "
                                          f"Please implement it in `{tn(recs)}.__oql_bin__`.")
            return RecordSets([RecordSet(res, self.domain)])


@lark.v_args(inline=True)
class OqlTransformer(lark.Transformer):

    CNAME = str
    INT = int
    FLOAT = float

    def __init__(self, env, model: str):
        super().__init__(True)
        self.env = env
        self.recs = env[model]
        self._meta = OqlMeta(env)

    def root(self, value):
        assert isinstance(value, RecordSets), "System Error, invalid root result."
        result = value.flat()
        if result is None:
            return self.recs  # Empty set.
        return result

    def or_expr(self, left, right):
        if isinstance(left, RecordSets) or isinstance(right, RecordSets):
            return left | right
        return left or right

    def and_expr(self, left, right):
        if isinstance(left, RecordSets) or isinstance(right, RecordSets):
            return left & right
        return left and right

    def bin_expr(self, left, opr, right):
        left: FieldAccess
        if left.next:  # Contains term.
            return left.eval_bin(opr, right)
        else:
            fullpath = ".".join(left.names)
            result = left.recs.search([(fullpath, opr, right)])
            return RecordSets([RecordSet(result, TermDomain.MISSING)])

    def dot_expr(self, field):
        field: FieldAccess
        if field.next:  # Contains term.
            return field.eval_una("bool")
        else:
            fullpath = ".".join(field.names)
            result = field.recs.search([(fullpath, "!=", False)])
            return RecordSets([RecordSet(result, TermDomain.MISSING)])

    def field(self, *args: str):
        return FieldAccess(self.recs, args, self._meta)

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
        result = transformer.transform(tree)
        return result


reader = OqlReader()  # Global reader.
