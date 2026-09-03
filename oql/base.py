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

    @abstractmethod
    def read(self, recs, load='_classic_read') -> List[Dict[str, Any]]:
        pass
