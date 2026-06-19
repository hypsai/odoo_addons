# @Time         : 12:05 2026/5/6
# @Author       : Chris
# @Description  :
import datetime
import json


def _json_default_serialize(o):
    # 1. Handle Datetime (Python Standard)
    if isinstance(o, (datetime.datetime, datetime.date)):
        return o.isoformat()


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, default=_json_default_serialize)
