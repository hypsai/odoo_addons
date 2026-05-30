# @Time         : 11:54 2025/10/17
# @Author       : Chris
# @Description  :
import logging
from collections import defaultdict
from typing import Tuple, Dict

from odoo import fields
from odoo.models import Model

from .term import *
from odoo.fields import Domain

_logger = logging.getLogger(__name__)


class RecordSet:
    def __init__(self, model: Model, domain: OqlDomain):
        """
        `None` domain means empty records.
        """
        if domain.model != model._name:
            raise Exception(f"Domain `{domain}` is incompatible with model `{model._name}`")
        self._model = model.browse()
        self.domain = domain
        self._recs = None

    @classmethod
    def from_recs(cls, recs: Model):
        return RecordSet(recs, OqlDomain("from_recs", recs._name, [("id", "in", recs.ids)]))

    @property
    def model(self):
        return self._model

    @property
    def name(self) -> str:
        """Odoo ORM model name"""
        return self._model._name

    @property
    def fields(self) -> Dict[str, fields.Field]:
        return self._model._fields

    @property
    def table(self) -> str:
        """Database table name."""
        return self._model._table

    @property
    def env(self):
        return self._model.env

    def get_recs(self, limit: int = None, offset: int = 0):
        return self._model.search(self.domain.domain, offset, limit, order="id")

    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **read_kwargs):
        """Search on current record set."""
        domain = Domain.AND([self.domain.domain, domain or []])
        return self._model.search_read(domain, fields, offset, limit, order, **read_kwargs)

    def __bool__(self):
        return len(self) > 0

    def __len__(self):
        return self._model.search_count(self.domain.domain)

    def __str__(self):
        return f"RecordSet({self.name}[{len(self)}], {self.domain.fullname})"


class RecordSets(Tuple[RecordSet]):
    def __new__(cls, obj: Iterable[RecordSet]):
        # Reduce. Merge same set. Worth noting that emtpy set will be kept.
        env = None
        model2domains: Dict[str, List[OqlDomain]] = defaultdict(list)
        for recs in obj:
            if not isinstance(recs, RecordSet):
                raise ValueError(f"Failed create `{cls.__name__}`, expect a series of `{RecordSet.__name__}` object, "
                                 f"but got an unexpected `{type(recs).__name__}` object.")
            model2domains[recs.name].append(recs.domain)
            env = recs.env
        instance = super().__new__(cls, (RecordSet(env[model], OqlDomain.or_(*domains))
                                         for model, domains in model2domains.items()))
        return instance

    def __or__(self, other):
        if isinstance(other, RecordSets):
            return RecordSets(self+other)
        return bool(self) or other

    def __ror__(self, other):
        return self.__or__(other)

    def __and__(self, other):
        if isinstance(other, RecordSets):
            env = None
            model2domains: Dict[str, List[OqlDomain]] = defaultdict(list)
            for rec_sets in (other, self):
                for rec_set in rec_sets:
                    model2domains[rec_set.name].append(rec_set.domain)
                    env = rec_set.env
            return RecordSets(RecordSet(env[model], OqlDomain.and_(*domains))
                              for model, domains in model2domains.items())
        return bool(self) and other

    def __rand__(self, other):
        return self.__and__(other)

    def __str__(self):
        return f"RecordSets[{len(self)}]"
