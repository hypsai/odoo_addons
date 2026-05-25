# -*- coding: utf-8 -*-
# @Time         : 11:26 2025/10/17
# @Author       : Chris
# @Description  :
from typing import ClassVar, List, Iterable

from .compatible import normalize_domain, AND, OR


class Term(str):

    MISSING: ClassVar["Term"]

    @property
    def name(self) -> str:
        return str(self)

    def __bool__(self):
        return self is not self.MISSING


Term.MISSING = Term("<MISSING>")


class OqlDomain:
    """An object class that carries both model name and domain expression."""

    def __init__(self, name: str, model: str, domain: list, term: Term = Term.MISSING):
        """
        Attention: Must ensure `domain` is normalized.
            If you are not sure about format of the domain. Use `normalize` to instantiate.
        """
        self.term = term
        self.name = name
        self.model = model
        self.domain = domain

    @property
    def fullname(self):
        if self.term:
            return f"{self.term.name}@{self.name}"
        return self.name

    @classmethod
    def all(cls, model: str):
        return OqlDomain("ALL", model, [])

    @classmethod
    def normalize(cls, name: str, model: str, domain: list, term: Term):
        return cls(name, model, normalize_domain(domain), term)

    @classmethod
    def and_(cls, *term_domains: "OqlDomain"):
        """Create a new domain that `and` several domains together."""
        return cls._logic(term_domains, AND)

    @classmethod
    def or_(cls, *term_domains: "OqlDomain"):
        """Create a new domain that `or` several domains together."""
        return cls._logic(term_domains, OR)

    @classmethod
    def _logic(cls, term_domains: Iterable["OqlDomain"], opr: callable):
        models = set()
        names: List[str] = []
        domains: List[list] = []
        for td in term_domains:
            names.append(td.name)
            models.add(td.model)
            domains.append(td.domain)  # Gather domain in `&` logic.
        # Check.
        if len(models) == 0:
            raise Exception(f"Can't `{opr.__name__}` empty term domains.")
        elif len(models) > 1:
            raise Exception(f"Can't `{opr.__name__}` domains for different models: {models}")
        # Create new instance.
        model = next(iter(models))
        return OqlDomain(f"{opr.__name__}({', '.join(names)})", model, opr(domains))

    def __hash__(self):
        # Ignore domain when compute hash.
        return hash((
            self.term,
            self.name,
            self.model,
        ))

    def __str__(self):
        return f"{self.model}[{self.fullname}]"
