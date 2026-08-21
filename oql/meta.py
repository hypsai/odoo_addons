# @Time         : 16:19 2026/6/23
# @Author       : Chris
# @Description  :
from typing import Optional

from odoo.tools.safe_eval import safe_eval

from .acl import OqlAcl
from .alias import AliasRule, AliasNode
from .recs import *
from .util import KeyPassingDefaultDict
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class OqlMeta:
    def __init__(self, env):
        self.env = env
        self.acl = OqlAcl(env)
        self._term_fields = self._load_term_fields()
        self._term2domains: Dict[Term, List[OqlDomain]] = KeyPassingDefaultDict(self._load_domains)  # Lazy loading.
        self._model2rule: Dict[str, AliasRule] = KeyPassingDefaultDict(self._load_rule)  # Lazy loading.
        self._model2alias2node: Dict[str, Dict[str, AliasNode]] = KeyPassingDefaultDict(self._load_alias2node)  # Lazy loading.
        self._model2alias2path: Dict[str, Dict[str, str]] = KeyPassingDefaultDict(self._load_alias2path)  # Lazy loading.
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

    def get_alias(self, model: str, alias: str) -> Optional[AliasNode]:
        return self._model2alias2node[model].get(alias)

    def get_term2domains(self) -> Dict[Term, List[OqlDomain]]:
        if not self._all_terms_loaded:
            term2domains = self._load_terms([])
            self._term2domains.update(term2domains)
            self._all_terms_loaded = True
        return self._term2domains

    def get_alias2path(self, model: str) -> Dict[str, str]:
        return self._model2alias2path[model]

    def get_aliases(self, model: str) -> Iterable[AliasNode]:
        return self._model2alias2node[model].values()

    def _load_term_fields(self):
        """Load fields that have a relation to `oql.term`."""
        env = self.env
        perm_models = self.acl.perm_models("read")
        perm_models.discard("oql.term.domain")
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
            referring_recs = recs.sudo().search(acl[model].perm_records([(field_name, "in", term_recs.ids)], "read"), order="id")
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
                    domain = acl[model].perm_records(domain, "read")
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

    def _load_alias2path(self, model: str) -> Dict[str, str]:
        alias2node = self._model2alias2node[model]
        return {k: v.path for k, v in alias2node.items() if not v.is_complex}

    def _load_alias2node(self, model: str) -> Dict[str, AliasNode]:
        recs = self.env["oql.alias.line"].sudo().search([("rule_id.model_id.model", "=", model)])
        perm_aliases = self.acl[model].perm_aliases("read")
        alias2node = {x.alias: AliasNode.parse(x.alias, x.mode, x.path, x.help) for x in recs if x.alias in perm_aliases}
        return alias2node
