# -*- coding: utf-8 -*-
# @Time         : 12:35 2026/9/3
# @Author       : Chris
# @Description  :
import copy
from abc import ABC, abstractmethod
from enum import IntEnum
from typing import List, Dict, Any, Literal, Callable

from odoo import models

ModelMode = Literal["read", "write", "create", "unlink"]
FieldMode = Literal["read", "write"]


class UnitKind(IntEnum):
    MODEL = 1
    FIELD = 2
    ALIAS = 3
    TERM = 4
    METHOD = 5


class AclUnit:

    loose: Callable[[], bool]
    """A callback used to loose access range, return `True` if loosing succeeded, else `False`.
    * Attention: `loose` method is not idempotent."""

    def __init__(self, model: models.Model, name: str, kind: UnitKind, mode=None, loose: Callable[[], bool] = None):
        self.model = model
        self.name = name
        self.kind = kind
        self.mode = mode
        self.loose = loose

    @property
    def model_name(self):
        return self.model._name  # noqa

    @property
    def key(self):
        return self.model_name, self.name, self.kind, self.mode, self.loose

    def as_mode(self, mode):
        obj = copy.copy(self)
        obj.mode = mode
        return obj


class IAcl(ABC):

    @abstractmethod
    def gather_acl_units(self, res: List[AclUnit]):
        pass


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

    @as_.setter
    @abstractmethod
    def as_(self, value):
        pass

    @abstractmethod
    def read(self, recs, load='_classic_read') -> list:
        pass

    @abstractmethod
    def gather_acl_units(self, res: List[AclUnit], mode: FieldMode):
        pass
