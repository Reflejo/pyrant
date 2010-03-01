# -*- coding: utf-8 -*-

from pyrant.protocol import DB_TABLE, TABLE_COLUMN_SEP


def from_python(value):
    """
    Returns value prepared for storage. This is required for search because
    some Python types cannot be converted to string and back without changes
    in semantics, e.g. True-->"True"-->True and False-->"False"-->True.

    Note that we don't convert the value to bytes here, it's done by
    pyrant.protocol._pack.
    """
    if isinstance(value, bool):
        return 1 if value else ''
    return value

def to_python(elem, dbtype, sep=None):
    """
    Returns pythonic representation of a database record.
    """
    if dbtype == DB_TABLE:
        # Split element by \x00 which is the column separator
        elems = elem.split(TABLE_COLUMN_SEP)
        if elems[0]:
            return dict((elems[i], elems[i+1]) for i in xrange(0, len(elems), 2))
        else:
            return

    if sep and sep in elem:
        return elem.split(sep)

    return elem

def csv_to_dict(lines):
    return dict(line.split('\t', 1) for line in lines.splitlines() if line)