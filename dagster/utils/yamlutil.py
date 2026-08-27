# -*- coding: utf-8 -*-
# YAML utilities (copied from futil.yamlutil).
import yaml


def escape_dump(v):
    # common_args prevents PyYAML from adding --- or ... markers
    common_args = {
        'explicit_start': False,
        'explicit_end': False,
        'allow_unicode': True  # Prevents escaping non-ASCII characters like emojis
    }

    if isinstance(v, str):
        # default_style='"' forces double quotes, bypassing the 1024-char
        # "simple key" limit and converting newlines to \n (single line).
        return yaml.safe_dump(v, default_style='"', **common_args).strip().rstrip('.')

    # default_flow_style=True keeps lists/dicts on one line.
    return yaml.safe_dump(v, default_flow_style=True, **common_args).strip().rstrip('.')
