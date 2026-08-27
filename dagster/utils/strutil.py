# -*- coding: utf-8 -*-
# String utilities (copied from futil.strutil).
import dataclasses
import io
from typing import Protocol, Optional, Callable, List


class IGet(Protocol):
    def get(self, key) -> Optional:
        ...


_ID_CHARS = [False] * 256
for _ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_":
    _ID_CHARS[ord(_ch)] = True
_WC2PRIORITY = {' ': 1, '\t': 2, '\r': 3, '\n': 4}  # White char : priority.


@dataclasses.dataclass(frozen=True)
class Var:
    name: str
    """Var name."""

    refs: List["VarRef"]
    """Refs to this var."""

    @property
    def required(self):
        return all(x.default is None for x in self.refs)

    def __repr__(self):
        str_refs = ', '.join(f'{x.row}:{x.col}{("" if x.default is None else f"={x.default}")}' for x in self.refs)
        return f"{self.name}({str_refs})"


class VarRef:
    name: str
    """Var name."""

    row: int
    """Line number of the var ref text."""

    col: int
    """Char number of the `$` char in line."""

    default: Optional[str]
    """Default value of the var ref."""


def _process_template(template: str, build: bool, kw_vars: IGet = None, var_escape: Callable[[str], str] = None, partial=False):
    """
    Unified engine for template processing.
    :param template: Source string with ${var} or ${var?default} placeholders.
    :param build: If True, substitute and return a string. If False, parse and return List[Var].
    :param kw_vars: Var value source (required if build=True).
    :param var_escape: Optional escape function for substituted values.
    :param partial: Missing var refs are kept untouched when True.
    :return: Union[str, List[Var]] depending on 'build'.
    """
    sb = io.StringIO()
    vn_sb = io.StringIO()  # Variable Name
    def_sb = io.StringIO()  # Default Value
    found_vars = {}  # type: dict[str, List[VarRef]]

    stage, row, col = 0, 1, 0
    start_row, start_col = 1, 0

    for c in template:
        col += 1
        if stage == 0:  # Hunt for '$' or '\'.
            if c == '$':
                start_row, start_col = row, col
                stage = 1
            elif build:
                sb.write(c)
        elif stage == 1:  # Hunt for '{'.
            if c == '{':
                stage = 2
                vn_sb = io.StringIO()
            else:
                stage = 0
                if build:
                    sb.write('$')
                    if c != '$':  # Escape '$'.
                        sb.write(c)
        elif stage == 2:  # Devour var name, hunt for '}' or '?'.
            if c == '}' or c == '?':
                var_name = vn_sb.getvalue()

                if not build:
                    ref = VarRef()
                    ref.name, ref.row, ref.col, ref.default = var_name, start_row, start_col, None
                    found_vars.setdefault(var_name, []).append(ref)

                var_value = kw_vars.get(var_name) if build else None
                if var_value is None or var_value == '':
                    if c == "?":
                        stage = 3
                        def_sb = io.StringIO()
                    elif not build or (kw_vars is not None and var_name in kw_vars):
                        stage = 0
                    elif partial:
                        if build:
                            sb.write(f"${{{var_name}}}")
                        stage = 0
                    else:
                        raise KeyError(f"Value of variable '{var_name}' is not provided for template '{template}'.",
                                       var_name, template)
                else:
                    if build:
                        var_value = str(var_value)
                        if var_escape:
                            var_value = var_escape(var_value)
                        sb.write(var_value)

                    if c == "?":
                        stage = 4
                    else:
                        stage = 0
            else:
                vn_sb.write(c)
                c_ord = ord(c)
                if c_ord > 255 or not _ID_CHARS[c_ord]:  # Invalid var name char.
                    if build:
                        sb.write("${")
                        sb.write(vn_sb.getvalue())
                    vn_sb = io.StringIO()
                    stage = 0
        elif stage == 3:  # Devour default value, hunt for '}' or '\'.
            if c == '}':
                var_name = vn_sb.getvalue()
                default_val = def_sb.getvalue()

                if not build:
                    found_vars[var_name][-1].default = default_val
                elif partial and (kw_vars.get(var_name) is None and var_name not in kw_vars):
                    sb.write(f"${{{var_name}?{default_val}}}")
                else:
                    sb.write(default_val)
                stage = 0
            else:
                def_sb.write(c)
        elif stage == 4:  # Ignore default value, hunt for '}'.
            if c == '}':
                stage = 0

        if c == '\n':
            row += 1
            col = 0

    return sb.getvalue() if build else [Var(name=n, refs=r) for n, r in found_vars.items()]


def substitute(template: str, kw_vars: IGet, var_escape: Callable[[str], str] = None, partial=False):
    """
    Substitute ${var_name} placeholders with values from kw_vars.
    Placeholder must be strict '${\\w+}' or '${...}' is treated as plain text.
    """
    return _process_template(template, True, kw_vars, var_escape, partial)


def parse_vars(s: str) -> List[Var]:
    """Parse ${...} format vars in the string."""
    return _process_template(s, False)


def escape(s: str):
    """
    Escape special chars in string.
    Escapes: \b (backspace), \r (carriage return), \\ (raw backslash), \n (newline).
    """
    if not s:
        return s
    sb = io.StringIO()
    stage = 0
    for c in s:
        if stage == 0:
            if c == '\\':
                stage = 1
            else:
                sb.write(c)
        elif stage == 1:
            if c == 'b':  # Backspace
                sb.seek(max(sb.tell() - 1, 0))
            elif c == 'r':
                j = 0
                for i in range(sb.tell() - 1, -1, -1):
                    sb.seek(i)
                    c = sb.read(1)
                    if c == '\n':
                        j = i + 1
                        break
                sb.seek(j)
            elif c == '\\':
                sb.write('\\')
            elif c == 'n':
                sb.write('\n')
            else:
                raise ValueError(f"Invalid escape char '{c}' in string '{s}'")
            stage = 0
    sb.truncate(sb.tell())
    return sb.getvalue()


def split_camel(s: str):
    """Split camel string into words. NOT TESTED."""
    sb = io.StringIO()
    mode = 0  # 0: hunt for upper, 1: hunt for lower
    for i in range(len(s)):
        c = s[i]
        if mode == 0:
            if c.isupper():
                mode = 1
                sb.write(' ')
        else:
            if c.islower():
                mode = 0
        sb.write(c)
    return sb.getvalue()


def compact(s: str):
    """
    Remove redundant white chars.
    1. Several white chars together -> keep highest priority one (_WC2PRIORITY).
    2. Strip white chars at start/end.
    """
    sb = io.StringIO()
    master_wc = ''
    master_p = 999  # Master priority.
    for c in s:
        priority = _WC2PRIORITY.get(c)
        if priority is None:  # Non-white char.
            if master_wc is not None:
                sb.write(master_wc)
                master_wc = None
                master_p = 0
            sb.write(c)
        else:  # White char.
            if priority > master_p:
                master_wc = c
                master_p = priority
    return sb.getvalue()


def remove_prefix(text: str, prefix: str) -> str:
    if text.startswith(prefix):
        return text[len(prefix):]
    return text
