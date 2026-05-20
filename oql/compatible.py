# -*- coding: utf-8 -*-
# @Time         : 19:16 2026/4/27
# @Author       : Chris
# @Description  :
import sys
from odoo.release import version_info

ODOO_VERSION = version_info[0]
PYTHON_VERSION = sys.version_info[:2]  # (major, minor)

__all__ = ["model_flush", "zip_c"]


def model_flush(model, fields=None):
    if ODOO_VERSION >= 16:
        model._flush(fields)
    else:
        model.flush(fields)


# Check if Python version supports zip with strict parameter (3.10+)
_HAS_ZIP_STRICT = PYTHON_VERSION >= (3, 10)
_SENTINEL = object()  # Sentinel object for detecting end of iterator


def zip_c(*args, **kwargs):
    """
    Compatible zip function that works across Python versions.
    
    For Python 3.10+: Uses built-in zip() with strict parameter
    For Python <3.10: Provides custom implementation with strict support
    
    Returns an iterator (like native zip), not a list.
    """
    if _HAS_ZIP_STRICT:
        # Use native zip for Python 3.10+ (returns iterator)
        return zip(*args, **kwargs)
    else:
        # Custom implementation for older Python versions
        strict = kwargs.pop('strict', False)
        
        if strict:
            # Check all iterables have the same length
            iterators = [iter(arg) for arg in args]
            
            while True:
                items = []
                counts = []
                
                for it in iterators:
                    item = next(it, _SENTINEL)
                    if item is _SENTINEL:
                        counts.append(0)
                    else:
                        items.append(item)
                        counts.append(1)
                
                # If we got no items, we're done
                if sum(counts) == 0:
                    break
                
                # If lengths don't match, raise error
                if len(items) != len(iterators):
                    raise ValueError("zip() argument of differing length in strict mode")
                
                yield tuple(items)
        else:
            # Normal zip behavior (returns iterator)
            return zip(*args)
