# -*- coding: utf-8 -*-
# @Time         : 11:54 2025/10/17
# @Author       : Chris
# @Description  :
import logging
from collections import defaultdict
from typing import Tuple, Any, Iterable
from dataclasses import dataclass

from .term import *

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecordSet:
    data: Any
    domain: TermDomain

    @property
    def ids(self):
        return self.data.ids

    @property
    def name(self):
        return self.data._name

    @property
    def env(self):
        return self.data.env

    def __bool__(self):
        return bool(self.data)

    def __str__(self):
        return f"RecordSet({self.name}[{len(self.data)}], {self.domain.fullname})"


class RecordSets(Tuple[RecordSet]):

    def flat(self):
        # Merge records of same model.
        env = None
        model2ids = defaultdict(set)
        for recs in self:
            model2ids[recs.name].update(recs.ids)
            env = recs.env
        # Check and return.
        if len(model2ids) == 0:
            return None
        elif len(model2ids) == 1:
            model, ids = next(iter(model2ids.items()))
            return env[model].browse(ids)
        else:
            raise Exception(f"Flat operation expect sets contains at most 1 set, got {len(self)}.")

    def __new__(cls, obj: Iterable[RecordSet]):
        # Reduce. Merge same set. Worth noting that emtpy set will be kept.
        env = None
        model2domain2ids = defaultdict(lambda: defaultdict(set))
        for recs in obj:
            if not isinstance(recs, RecordSet):
                raise ValueError(f"Failed create `{cls.__name__}`, expect a series of `{RecordSet.__name__}` object, "
                                 f"but got an unexpected `{type(recs).__name__}` object.")
            model2domain2ids[recs.name][recs.domain].update(recs.ids)
            env = recs.env
        instance = super().__new__(cls, (RecordSet(env[model].browse(ids), domain)
                                         for model, domain2ids in model2domain2ids.items()
                                         for domain, ids in domain2ids.items()))
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
            model2ids_domains = defaultdict(lambda: (set(), []))
            for rec_set in other:
                ids, domains = model2ids_domains[rec_set.name]
                ids.update(rec_set.ids)
                domains.append(rec_set.domain)
                env = rec_set.env
            for rec_set in self:
                ids, domains = model2ids_domains[rec_set.name]
                ids.intersection_update(rec_set.ids)
                domains.append(rec_set.domain)
                env = rec_set.env
            return RecordSets(RecordSet(env[model].browse(ids), TermDomain.and_(*domains))
                              for model, (ids, domains) in model2ids_domains.items())
        return bool(self) and other

    def __rand__(self, other):
        return self.__and__(other)

    def __str__(self):
        return f"RecordSets[{len(self)}]"
