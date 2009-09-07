# -*- coding: utf-8 -*-
"""
A pure-Python implementation of Tokyo Tyrant protocol.
Python 2.4+ is required.

More information about Tokyo Cabinet:
    http://tokyocabinet.sourceforge.net/

More information about Tokyo Tyrant:
    http://tokyocabinet.sourceforge.net/tyrantdoc/

Usage example (note the automatically managed support for table database)::

    >>> import pyrant
    >>> t = pyrant.Tyrant(host='127.0.0.1', port=1983)    # default port is 1978
    >>> if t.dbtype != pyrant.DBTYPETABLE:
    ...     t['key'] = 'foo'
    ...     print t['key']
    ... else:
    ...     t['key'] = {'name': 'foo'}
    ...     print t['key']['name']
    foo
    >>> del t['key']
    >>> print t['key']
    Traceback (most recent call last):
        ...
    KeyError: 'key'

"""

import copy
import itertools as _itertools
from protocol import TyrantProtocol, TyrantError


__version__ = '0.1.0'
__all__ = ['Tyrant', 'TyrantError', 'TyrantProtocol', 'Q']


# Constants
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 1978
MAX_RESULTS = 1000

# Table Types
DBTYPEBTREE = 'B+ tree'
DBTYPETABLE = 'table'
DBTYPEMEMORY = 'on-memory hash'
DBTYPEHASH = 'hash'


def _parse_elem(elem, dbtype, sep=None):
    if dbtype == DBTYPETABLE:
        # Split element by \x00 which is the column separator
        elems = elem.split('\x00')
        if not elems[0]:
            return None

        return dict((elems[i], elems[i + 1]) \
                        for i in xrange(0, len(elems), 2))
    elif sep and sep in elem:
        return elem.split(sep)

    return elem


class Tyrant(dict):
    """A Python dictionary API for Tokyo Tyrant.

    :param host: Tyrant host address
    :param port: Tyrant port number
    :param separator: if set, will be used to get/put lists as values
    :param literal: if set, returned data is not encoded to Unicode
    """

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, separator=None,
                 literal=False):
        """
        Acts like a python dictionary.
        """
        # We want to make protocol public just in case anyone need any
        # specific option
        self.proto = TyrantProtocol(host, port)
        self.dbtype = self.get_stats()['type']
        self.separator = separator
        self.literal = literal

    def __contains__(self, key):
        try:
            self.proto.vsiz(key)
        except TyrantError:
            return False
        else:
            return True

    def __delitem__(self, key):
        try:
            return self.proto.out(key)
        except TyrantError:
            raise KeyError(key)

    def __getitem__(self, key):
        try:
            return _parse_elem(self.proto.get(key, self.literal), self.dbtype,
                               self.separator)
        except TyrantError:
            raise KeyError(key)

    def get(self, key, default=None):
        """Returns value for `key`. If no record is found, returns `default`."""
        try:
            return self[key]
        except KeyError:
            return default

    def __len__(self):
        return self.proto.rnum()

    def __repr__(self):
        return object.__repr__(self)

    def __setitem__(self, key, value):
        if isinstance(value, dict):
            flat = _itertools.chain([key], *value.iteritems())
            self.proto.misc('put', list(flat))

        elif isinstance(value, (list, tuple)):
            assert self.separator, "Separator is not set"

            flat = self.separator.join(value)
            self.proto.put(key, flat)

        else:
            self.proto.put(key, value)


    def call_func(self, func, key, value, record_locking=False,
                  global_locking=False):
        """Calls specific function."""
        # TODO: write better documentation *OR* move this method to lower level
        opts = ((record_locking and TyrantProtocol.RDBXOLCKREC) |
                (global_locking and TyrantProtocol.RDBXOLCKGLB))
        return self.proto.ext(func, opts, key, value)

    def clear(self):
        """Removes all records from the remote database."""
        self.proto.vanish()

    def concat(self, key, value, width=None):
        """Concatenates columns of the existing record."""
        # TODO: write better documentation, provide example code
        if width is None:
            self.proto.putcat(key, value)
        else:
            self.proto.putshl(key, value, width)

    def get_size(self, key):
        """Returns the size of the value for `key`."""
        try:
            return self.proto.vsiz(key)
        except TyrantError:
            raise KeyError(key)

    def get_stats(self):
        """Returns the status message of the database as dictionary."""
        return dict(l.split('\t', 1) \
                        for l in self.proto.stat().splitlines() if l)

    def iterkeys(self):
        """Iterates keys using remote operations."""
        self.proto.iterinit()
        try:
            while True:
                yield self.proto.iternext()
        except TyrantError:
            pass

    def keys(self):
        """Returns the list of keys in the database."""
        return list(self.iterkeys())

    def update(self, other, **kwargs):
        """Updates/s given objects into the database."""
        # TODO: write better documentation, provide example code
        self.multi_set(other.iteritems())
        if kwargs:
            self.update(kwargs)

    def multi_del(self, keys, no_update_log=False):
        """Removes given records from the database."""
        # TODO: write better documentation: why would user need the no_update_log param?
        opts = (no_update_log and TyrantProtocol.RDBMONOULOG or 0)
        if not isinstance(keys, (list, tuple)):
            keys = list(keys)

        self.proto.misc("outlist", keys, opts)

    def multi_get(self, keys, no_update_log=False):
        """Returns a list of records that match given keys."""
        opts = (no_update_log and TyrantProtocol.RDBMONOULOG or 0)
        if not isinstance(keys, (list, tuple)):
            keys = list(keys)

        rval = self.proto.misc("getlist", keys, opts)

        if len(rval) <= len(keys):
            # 1.1.10 protocol, may return invalid results
            if len(rval) < len(keys):
                raise KeyError("Missing a result, unusable response in 1.1.10")

            return rval

        # 1.1.11 protocol returns interleaved key, value list
        d = dict((rval[i], _parse_elem(rval[i + 1], self.dbtype,
                                       self.separator)) \
                    for i in xrange(0, len(rval), 2))
        return d

    def multi_set(self, items, no_update_log=False):
        """Stores given records in the database."""
        opts = (no_update_log and TyrantProtocol.RDBMONOULOG or 0)
        lst = []
        for k, v in items.iteritems():
            if isinstance(v, (list, tuple)):
                assert self.separator, "Separator is not set"

                v = self.separator.join(v)
            lst.extend((k, v))

        self.proto.misc("putlist", lst, opts)

    def prefix_keys(self, prefix, maxkeys=None):
        """Get forward matching keys in a database.
        The return value is a list object of the corresponding keys.
        """
        # TODO: write better documentation: describe purpose, provide example code
        if maxkeys is None:
            maxkeys = len(self)

        return self.proto.fwmkeys(prefix, maxkeys)

    def sync(self):
        """Synchronizes updated content with the database."""
        # TODO: write better documentation: when would user need this?
        self.proto.sync()

    @property
    def query(self):
        """Returns a :class:`~pyrant.Query` object for the database."""
        return Query(self.proto, self.dbtype, self.literal)


class Q(object):
    """Condition object. You can | this type to ORs conditions,
    but you cannot use operand "&", to do this just add more Q to your filter.
    """
    # TODO: write better documentation: provide example code

    def __init__(self, **kwargs):
        assert kwargs, "You need to specify at least one condition"

        for kw, val in kwargs.iteritems():
            nameop = kw.split('__')
            self._op = 's' if isinstance(val, (str, unicode)) else 'n'
            self._op += nameop[1] if len(nameop) > 1 else 'eq'
            self.name = nameop[0]
            self.expr = val

        self.negate = False

    def __or__(self, q):
        assert isinstance(q, Q), "Unsupported operand type(s) for |"

        op = '%s_or' % q._op
        if q._op == self._op and op in TyrantProtocol.conditionsmap:
            qcopy = q._clone()
            qcopy._op = op
            qcopy.expr = "%s,%s" % (q.expr , self.expr)

            return qcopy
        else:
            raise TypeError("Unsoported operand for |. You can only do this "\
                            "on contains or eq")

    @property
    def op(self):
        op = TyrantProtocol.conditionsmap[self._op]
        return op | TyrantProtocol.RDBQCNEGATE if self.negate else op

    def __repr__(self):
        return "%s [%s] %s" % (self.name, self.op, self.expr)

    def _clone(self):
        return copy.copy(self)


class Query(object):
    """Query table operations. This is a lazy object
    that abstract all queries for tyrant protocol.
    """

    def __init__(self, proto, dbtype, literal=False, conditions=None):
        if conditions:
            assert isinstance(conditions, list) and \
                   all(isinstance(c,Q) for c in conditions), \
                   'Expected a list of Q instances, got %s' % conditions
        self._conditions = conditions or []
        self._order = None
        self._order_t = 0
        self._cache = {}
        self._proto = proto
        self._dbtype = dbtype
        self.literal = literal

    def _clone(self):
        conditions = [q._clone() for q in self._conditions]
        query = Query(self._proto, self._dbtype, literal=self.literal,
                      conditions=conditions)
        return query

    @staticmethod
    def _decorate(k, v):
        return (k, v)

    def order(self, name):
        """Defines order in which results should be retrieved.

        :param name: the column name. If prefixed with ``-``, direction is changed
            from ascending (default) to descending.
            If prefixed with ``#``, values are treated as numbers.

        Examples::

            q.order('name')       # ascending
            q.order('-name')      # descending
            q.order('-#ranking')  # descending, numeric

        """
        if name.startswith('-'):
            if name.startswith('-#'):
                order, order_t = name[2:], TyrantProtocol.RDBQONUMDESC
            else:
                order, order_t = name[1:], TyrantProtocol.RDBQOSTRDESC
        elif name.startswith('#'):
            order, order_t = name[1:], TyrantProtocol.RDBQONUMASC
        else:
            order, order_t = name, TyrantProtocol.RDBQOSTRASC

        query = self._clone()

        if self._order == order and self._order_t == order_t:
            # provide link to existing cache
            query._cache = self._cache
        query._order = order
        query._order_t = order_t

        return query

    def exclude(self, *args, **kwargs):
        """Antipode of :meth:`~pyrant.Query.filter`."""
        return self._filter(True, args, kwargs)

    def filter(self, *args, **kwargs):    # TODO: provide full list of lookups
        """Returns a clone of the Query object with given conditions applied.

        Conditions can be specified as Q objects and/or keyword arguments.

        Supported keyword lookups are:

            * __eq: Equals (default) to expression
            * __lt: Less than expression
            * __le: Less or equal to expression
            * __gt: Greater than expression
            * __ge: Greater or equal to expression

        Usage:

            connect to a remote table database:

            >>> t = Tyrant()
            >>> t.get_stats()['type']
            u'table'

            stuff some data into the storage:

            >>> t['a'] = {'name': 'Foo', 'price': 1}
            >>> t['b'] = {'name': 'Bar', 'price': 2}
            >>> t['c'] = {'name': 'Foo', 'price': 3}

            find everything with price > 1:

            >>> [x[0] for x in t.query.filter(price__gt=1)]
            ['b', 'c']

            find everything with name "Foo":

            >>> [x[0] for x in t.query.filter(name='Foo')]
            ['a', 'c']

            chain queries:

            >>> cheap_items = t.query.filter(price__lt=3)
            >>> cheap_bars = cheap_items.filter(name='Bar')
            >>> [x[0] for x in cheap_items]
            ['a', 'b']
            >>> [x[0] for x in cheap_bars]
            ['b']

        """
        return self._filter(False, args, kwargs)

    def _filter(self, negate, args, kwargs):
        query = self._clone()

        # Iterate arguments. Should be instances of Q
        for cond in args:
            assert isinstance(cond, Q), "Arguments must be instances of Q"
            q = cond._clone()
            q.negate = q.negate ^ negate
            query._conditions.append(q)

        # Generate Q with arguments as needed
        for name, expr in kwargs.iteritems():
            q = Q(**{name: expr})
            q.negate = negate
            query._conditions.append(q)

        return query

    def values(self, key):
        "Returns a list of unique values for given key."
        collected = {}
        for _, data in self[:]:
            for k,v in data.iteritems():
                if k == key and v not in collected:
                    collected[v] = 1
        return collected.keys()

    def stat(self):
        "Returns statistics on key usage."
        collected = {}
        for _, data in self[:]:
            for k in data:
                collected[k] = collected.setdefault(k, 0) + 1
        return collected

    def __len__(self):
        return len(self[:])

    def __repr__(self):
        # Do the query using getitem
        return str(self[:])

    def __getitem__(self, k):
        # Retrieve an item or slice from the set of results.
        if not isinstance(k, (slice, int, long)):
            raise TypeError("ResultSet indices must be integers")

        # Check slice integrity
        assert (not isinstance(k, slice) and (k >= 0)) \
            or (isinstance(k, slice) and (k.start is None or k.start >= 0) \
            and (k.stop is None or k.stop >= 0)), \
            "Negative indexing is not supported."

        if isinstance(k, slice):
            offset = k.start or 0
            limit = (k.stop - offset) if k.stop is not None else MAX_RESULTS
        else:
            offset = k
            limit = 1

        cache_key = "%s_%s" % (offset, limit)
        if cache_key in self._cache:
            return self._cache[cache_key]

        conditions = [(c.name, c.op, c.expr) for c in self._conditions]

        # Do the search.
        keys = self._proto.search(conditions, limit, offset,
                                  order_type=self._order_t,
                                  order_field=self._order)

        # Since results are keys, we need to query for actual values
        if isinstance(k, slice):
            ret = [self._decorate(key, _parse_elem(self._proto.get(key, self.literal),
                                                   self._dbtype))
                   for key in keys]
        else:
            ret = self._decorate(keys[0], _parse_elem(self._proto.get(keys[0], self.literal),
                                                      self._dbtype))

        self._cache[cache_key] = ret

        return ret
