# -*- coding: utf-8 -*-
# @Time         : 11:26 2025/10/17
# @Author       : Chris
# @Description  :
from dataclasses import dataclass
from typing import ClassVar


class Term(str):

    MISSING: ClassVar["Term"]

    @property
    def name(self) -> str:
        return str(self)


Term.MISSING = Term("<MISSING>")


@dataclass(frozen=True)
class TermDomain:

    MISSING: ClassVar["TermDomain"]

    term: Term
    name: str
    model: str
    domain: list

    @property
    def info(self):
        return TermChipInfo(self.term.name, self.name)

    @property
    def fullname(self):
        return f"{self.name}@{self.term.name}"

    @classmethod
    def and_(cls, *term_domains: "TermDomain"):
        """Create a domain that `and` several domains together."""
        terms = set()
        models = set()
        domain = []
        for td in term_domains:
            terms.add(td.term)
            models.add(td.model)
            domain.extend(td.domain)  # Gather domain in `&` logic.
        term = next(iter(terms)) if len(terms) == 1 else Term.MISSING
        model = next(iter(models)) if len(models) == 1 else ""
        domain = domain if model else []
        return TermDomain(term, "<AND>", model, domain)

    def __hash__(self):
        # Ignore domain when compute hash.
        return hash((
            self.term,
            self.name,
            self.model,
        ))

    def __str__(self):
        return f"{self.model}[{self.fullname}]"


TermDomain.MISSING = TermDomain(Term.MISSING, "<MISSING>", "", [])


@dataclass(frozen=True)
class TermChipInfo:
    name: str
    """Name of the term."""

    domain: str
    """Name of the term domain."""

    def __str__(self):
        return f"{self.domain}@{self.name}"
