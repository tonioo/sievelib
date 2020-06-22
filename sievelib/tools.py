"""Some tools."""


def to_list(stringlist, unquote=True):
    """Convert a string representing a list to real list."""
    stringlist = stringlist[1:-1]
    return [
        string.strip('"') if unquote else string
        for string in stringlist.split(",")
    ]
