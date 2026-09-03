# -*- coding: utf-8 -*-
# @Time         : 12:35 2026/9/3
# @Author       : Chris
# @Description  :
from abc import ABC, abstractmethod
from typing import List, Dict, Any


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
