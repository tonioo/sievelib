"""Some tools."""

import re
from typing import List, Union

QUOTED_STRING_RE = re.compile(r'"([^"\\]|\\.)*"', re.DOTALL)


def is_quoted(value: str) -> bool:
    """Tell if value is a valid sieve quoted string."""
    return QUOTED_STRING_RE.fullmatch(value) is not None


def quote(value: str) -> str:
    """Convert value to a sieve quoted string (RFC 5228, section 2.4.2)."""
    return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')


def unquote(value: str) -> str:
    """Return the content of a sieve quoted string.

    A value which is not a quoted string is returned unchanged.
    """
    if not is_quoted(value):
        return value
    return re.sub(r"\\(.)", r"\1", value[1:-1], flags=re.DOTALL)


def to_list(stringlist: str, unquote: bool = True) -> List[str]:
    """Convert a string representing a list to real list."""
    stringlist = stringlist[1:-1]
    return [
        string.strip('"') if unquote else string for string in stringlist.split(",")
    ]


def unquote_arg(value: Union[str, List[str]]) -> Union[str, List[str]]:
    """Unquote a string or a string list argument.

    A string list can be either a real list or its string representation.
    """
    if isinstance(value, list):
        return [unquote(item) for item in value]
    if value.startswith("["):
        return to_list(value)
    return unquote(value)
