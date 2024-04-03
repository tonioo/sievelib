"""Some tools."""

from typing import List


def to_list(stringlist: str, unquote: bool = True) -> List[str]:
    """Convert a string representing a list to real list."""
    stringlist = stringlist[1:-1]
    return [
        string.strip('"') if unquote else string for string in stringlist.split(",")
    ]
