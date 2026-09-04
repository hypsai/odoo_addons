# -*- coding: utf-8 -*-
# @Time         : 12:35 2026/9/3
# @Author       : Chris
# @Description  :
from abc import ABC, abstractmethod
from enum import IntEnum
from typing import List, Dict, Any

from odoo import models


class UnitKind(IntEnum):
    FIELD = 1
    ALIAS = 2


class AclUnit:
    def __init__(self, model: models.Model, name: str, kind: UnitKind):
        self.model = model
        self.name = name
        self.kind = kind

    @property
    def key(self):
        return self.model._name, self.name, self.kind


class IRecsReader(ABC):

    @property
    @abstractmethod
    def is_agg(self) -> bool:
        """Whether this is an aggregate reader."""
        pass

    @property
    @abstractmethod
    def as_(self) -> str:
        """Alias name that will be used as key in reading result."""
        pass

    @abstractmethod
    def read(self, recs, load='_classic_read') -> List[Dict[str, Any]]:
        pass
