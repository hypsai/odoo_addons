#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compatibility processor for Odoo module XML views.

Replaces deprecated ``<tree>`` tags with ``<list>`` tags in view definitions
for Odoo 18.0+.  Called by ``release.py`` during the per-branch release
pipeline so that each version branch contains the correct tag for its
target Odoo version.

Usage::

    python compat.py <module_path> <odoo_version>

Example::

    python compat.py oql 18.0
"""

import re
import sys
from pathlib import Path

# ── constants ────────────────────────────────────────────────────────────────

# Odoo 18 removed the ``<tree>`` view tag; only ``<list>`` is accepted.
_TREE_REPLACE_MIN_MAJOR = 18

# ``\b`` boundary ensures we don't accidentally replace "tree" inside
# attribute names like ``tree_view_ref`` or xml-ids like ``view_tree_foo``.
_TREE_OPEN_RE = re.compile(r'<tree\b')
_TREE_CLOSE_RE = re.compile(r'</tree>')

# Marker printed to stdout so the caller can detect whether files changed.
_CHANGED_MARKER = 'COMPAT_CHANGED'
_UNCHANGED_MARKER = 'COMPAT_UNCHANGED'


# ── public API ───────────────────────────────────────────────────────────────

def process_module(module_path, odoo_version):
    """Scan & rewrite XML view files, converting ``<tree>`` → ``<list>``.

    Args:
        module_path: Path to the module directory (relative or absolute).
        odoo_version: Odoo version string, e.g. ``'18.0'``.

    Returns:
        ``True`` if any files were modified.
    """
    major = int(odoo_version.split('.')[0])
    if major < _TREE_REPLACE_MIN_MAJOR:
        return False

    changed = False
    for xml_file in Path(module_path).rglob('*.xml'):
        content = xml_file.read_text(encoding='utf-8')
        if '<tree' not in content and '</tree>' not in content:
            continue

        new = _TREE_OPEN_RE.sub('<list', content)
        new = _TREE_CLOSE_RE.sub('</list>', new)

        if new != content:
            xml_file.write_text(new, encoding='utf-8')
            print(f'    tree→list: {xml_file}')
            changed = True

    return changed


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) != 3:
        print('Usage: python compat.py <module_path> <odoo_version>')
        print('Example: python compat.py oql 18.0')
        sys.exit(1)

    module_path = sys.argv[1]
    odoo_version = sys.argv[2]

    changed = process_module(module_path, odoo_version)
    if changed:
        print(_CHANGED_MARKER)
    else:
        print(_UNCHANGED_MARKER)


if __name__ == '__main__':
    main()
