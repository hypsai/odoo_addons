# -*- coding: utf-8 -*-
# @Time         : 11:54 2025/10/17
# @Author       : Chris
# @Description  :
import logging
from collections import defaultdict
from typing import Tuple, Dict

from odoo.models import Model

from .term import *

_logger = logging.getLogger(__name__)


class RecordSet:
    def __init__(self, model: Model, domain: OqlDomain):
        if domain.model != model._name:
            raise Exception(f"Domain `{domain}` is incompatible with model `{model._name}`")
        self._model = model
        self.domain = domain
        self._recs = None

    @property
    def model(self):
        return self._model

    @property
    def name(self) -> str:
        """Odoo ORM model name"""
        return self._model._name

    @property
    def env(self):
        return self._model.env

    def get_recs(self):
        if self._recs is None:
            self._recs = self._model.search(self.domain.domain, order="id")
        return self._recs

    def __bool__(self):
        return len(self) > 0

    def __len__(self):
        return self._model.search_count(self.domain.domain)

    def __str__(self):
        return f"RecordSet({self.name}[{len(self)}], {self.domain.name})"


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
        instance = super().__new__(cls, (RecordSet(env[model], OqlDomain.or_(domains))
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
            return RecordSets(RecordSet(env[model], OqlDomain.and_(domains))
                              for model, domains in model2domains.items())
        return bool(self) and other

    def __rand__(self, other):
        return self.__and__(other)

    def __str__(self):
        return f"RecordSets[{len(self)}]"
