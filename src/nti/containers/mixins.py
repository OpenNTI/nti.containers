#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

logger = __import__('logging').getLogger(__name__)

try:
    from UserDict import DictMixin
    DictMixin = DictMixin  # pylint
except ImportError:  # pragma: no cover
    class DictMixin(object):
        # Code taken from python2  UserDict.DictMixin
        def __iter__(self):
            for k in self.keys():
                yield k

        def has_key(self, key):
            try:
                self[key]
            except KeyError:
                return False
            return True

        def __contains__(self, key):
            return self.has_key(key)

        # third level takes advantage of second level definitions
        def iteritems(self):
            for k in self:
                yield (k, self[k])

        def iterkeys(self):
            return self.__iter__()

        # fourth level uses definitions from lower levels
        def itervalues(self):
            for _, v in self.iteritems():
                yield v

        def values(self):
            return [v for _, v in self.iteritems()]

        def items(self):
            return list(self.iteritems())

        def clear(self):
            for key in list(self.iterkeys()):
                del self[key]

        def setdefault(self, key, default=None):
            try:
                return self[key]
            except KeyError:
                self[key] = default
            return default

        def pop(self, key, *args):
            if len(args) > 1:
                raise TypeError("pop expected at most 2 arguments, got " +
                                repr(1 + len(args)))
            try:
                value = self[key]
            except KeyError:
                if args:
                    return args[0]
                raise
            del self[key]
            return value

        def popitem(self):
            try:
                k, v = next(self.iteritems())
            except StopIteration:
                raise KeyError('container is empty')
            del self[k]
            return (k, v)

        def update(self, other=None, **kwargs):
            # Make progressively weaker assumptions about "other"
            if other is None:
                pass
            elif hasattr(other, 'iteritems'):  # iteritems saves memory and lookups
                for k, v in other.iteritems():
                    self[k] = v
            elif hasattr(other, 'keys'):
                for k in other.keys():
                    self[k] = other[k]
            else:
                for k, v in other:
                    self[k] = v
            if kwargs:
                self.update(kwargs)

        def get(self, key, default=None):
            try:
                return self[key]
            except KeyError:
                return default

        def __repr__(self):
            return repr(dict(self.iteritems()))

        def __len__(self):
            return len(self.keys())
