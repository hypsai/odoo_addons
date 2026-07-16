# -*- coding: utf-8 -*-
# @Time         : 13:00 2026/7/16
# @Author       : Chris
# @Description  :
import collections
import importlib
import json


def get_class(fullname: str):
    """Import a Field subclass from its dotted path."""
    module_path, class_name = fullname.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def groupby(iterable, key, convert_item=None, returns_dict=False):
    """
    Similar to 'itertools.groupby', but this function can work on unsorted data.
    * 'itertools.groupby' works only on ordered data.
    """
    if convert_item is None:
        def convert_item(x):
            return x
    res_dict = collections.defaultdict(list)
    for item in iterable:
        res_dict[key(item)].append(convert_item(item))
    return res_dict if returns_dict else res_dict.items()


class RawAttachedField:
    def __init__(self, name: str, field_class: type, field_args: dict, invoker_model: str, action_method: str, name_user: str):
        self.name = name
        self.clazz = field_class
        self.args = field_args
        self.invoker_model = invoker_model
        self.action_method = action_method
        self.name_user = name_user

    @classmethod
    def from_row(cls, field_name: str, field_type: str, field_args: str, invoker_model: str, user_field_name: str, action_method: str):
        clazz = get_class(field_type)
        args = json.loads(field_args)
        return RawAttachedField(field_name, clazz, args, invoker_model, action_method, user_field_name)
