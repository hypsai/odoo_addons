# -*- coding: utf-8 -*-
# @Time         : 16:23 2026/6/23
# @Author       : Chris
# @Description  :
from .field import FieldAccess
from .recs import *


class SelectClause:
    def __init__(self, translate: bool, fas: List[FieldAccess]):
        self.translate = translate
        self.fas = fas


class WhereClause:
    def __init__(self, translate: bool, rec_sets: RecordSets):
        self.translate = translate
        self.rec_set = rec_sets[0]
