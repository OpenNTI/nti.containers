#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementations of persistent dicts with various qualities.

.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import copy
import time
import collections

import BTrees

from persistent import Persistent

from zope import interface

from zc.queue import CompositeQueue

from zc.blist import BList

from nti.base.interfaces import ILastModified

from nti.containers.containers import _tx_key_insen

from nti.zodb.minmax import NumericMaximum
from nti.zodb.minmax import NumericPropertyDefaultingToZero

from nti.zodb.persistentproperty import PersistentPropertyHolder


class Dict(Persistent):
    """
    A BTree-based dict-like persistent object that can be safely
    inherited from.
    """

    def __init__(self, *args, **kwargs):
        self._data = BTrees.OOBTree.OOBTree()
        self._len = BTrees.Length.Length()
        if args or kwargs:
            self.update(*args, **kwargs)

    def __setitem__(self, key, value):
        delta = 1
        if key in self._data:
            delta = 0
        self._data[key] = value
        if delta:
            self._len.change(delta)

    def __delitem__(self, key):
        self.pop(key)

    def update(self, *args, **kwargs):
        if args:
            if len(args) > 1:
                raise TypeError(
                    'update expected at most 1 arguments, got %d' %
                    (len(args),))
            if getattr(args[0], 'keys', None):
                for k in args[0].keys():
                    self[k] = args[0][k]
            else:
                for k, v in args[0]:
                    self[k] = v
        for k, v in kwargs.items():
            self[k] = v

    def setdefault(self, key, failobj=None):
        # we can't use BTree's setdefault because then we don't know to
        # increment _len
        try:
            res = self._data[key]
        except KeyError:
            res = failobj
            self[key] = res
        return res

    def pop(self, key, *args):
        try:
            res = self._data.pop(key)
        except KeyError:
            if args:
                res = args[0]
            else:
                raise
        else:
            self._len.change(-1)
        return res

    def clear(self):
        self._data.clear()
        self._len.set(0)

    def __len__(self):
        return self._len()

    def keys(self):
        return list(self._data.keys())

    def values(self):
        return list(self._data.values())

    def items(self):
        return list(self._data.items())

    def copy(self):
        if self.__class__ is Dict:
            return Dict(self._data)
        data = self._data
        try:
            self._data = BTrees.OOBTree.OOBTree()
            c = copy.copy(self)
        finally:
            self._data = data
        c.update(self._data)
        return c

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def iteritems(self):
        return self._data.iteritems()

    def iterkeys(self):
        return self._data.iterkeys()

    def itervalues(self):
        return self._data.itervalues()

    def has_key(self, key):
        return bool(self._data.has_key(key))

    def get(self, key, failobj=None):
        return self._data.get(key, failobj)

    def __contains__(self, key):
        return self._data.__contains__(key)

    def popitem(self):
        try:
            key = self._data.minKey()
        except ValueError:
            raise KeyError('container is empty')
        return (key, self.pop(key))
ZC_Dict = Dict  # BWC


class MinimalList(CompositeQueue):
    
    def clear(self):
        self._data = ()
        
    def append(self, item):
        return CompositeQueue.put(self, item)
    
    def replace(self, items=()):
        self.clear()
        for item in items or ():
            self.append(item)
    
    def remove(self, item):
        index = -1
        for pivot, v in enumerate(self):
            if item == v:
                index = pivot
        if index != -1:
            return self.pull(index)
        raise ValueError('not in list')


def list_type():
    return BList()


class OrderedDict(Dict):
    """
    An ordered BTree-based dict-like persistent object that can be safely
    inherited from.
    """

    def __init__(self, *args, **kwargs):
        self._order = list_type()
        super(OrderedDict, self).__init__(*args, **kwargs)

    def keys(self):
        return list(self._order)

    def __iter__(self):
        return iter(self._order)

    def values(self):
        return [self._data[key] for key in self._order]

    def items(self):
        return [(key, self._data[key]) for key in self._order]

    def __setitem__(self, key, value):
        if key not in self._data:
            self._order.append(key)
            self._len.change(1)
        self._data[key] = value

    def updateOrder(self, order):
        order = list(order)

        if len(order) != len(self._order):
            raise ValueError("Incompatible key set.")

        order_set = set(order)

        if len(order) != len(order_set):
            raise ValueError("Duplicate keys in order.")

        if order_set.difference(self._order):
            raise ValueError("Incompatible key set.")

        if hasattr(self._order, "replace"):
            self._order.replace(order)
        else:
            self._order[:] = order

    def clear(self):
        super(OrderedDict, self).clear()
        if hasattr(self._order, "clear"):
            self._order.clear()
        else:
            del self._order[:]

    def copy(self):
        if self.__class__ is OrderedDict:
            return OrderedDict(self)
        data = self._data
        order = self._order
        try:
            self._order = list_type()
            self._data = BTrees.OOBTree.OOBTree()
            c = copy.copy(self)
        finally:
            self._data = data
            self._order = order
        c.update(self)
        return c

    def iteritems(self):
        return ((key, self._data[key]) for key in self._order)

    def iterkeys(self):
        return iter(self._order)

    def itervalues(self):
        return (self._data[key] for key in self._order)

    def pop(self, key, *args):
        try:
            res = self._data.pop(key)
        except KeyError:
            if args:
                res = args[0]
            else:
                raise
        else:
            self._len.change(-1)
            self._order.remove(key)
        return res


@interface.implementer(ILastModified)
class LastModifiedDict(PersistentPropertyHolder,
                       ZC_Dict):
    """
    A BTree-based persistent dictionary that maintains the
    data required by :class:`interfaces.ILastModified`. Since this is not a
    :class:`zope.container.interfaces.IContainer`, this is done when this object is modified.
    """

    lastModified = NumericPropertyDefaultingToZero('_lastModified',
                                                   NumericMaximum,
                                                   as_number=True)

    def __init__(self, *args, **kwargs):
        self.createdTime = time.time()
        super(LastModifiedDict, self).__init__(*args, **kwargs)

    def updateLastMod(self, t=None):
        self.lastModified = t if t is not None and t > self.lastModified else time.time()
        return self.lastModified

    def updateLastModIfGreater(self, t):
        """
        Only if the given time is (not None and) greater than this object's 
        is this object's time changed.
        """
        if t is not None and t > self.lastModified:
            self.lastModified = t
        return self.lastModified

    def pop(self, key, *args):
        try:
            result = super(LastModifiedDict, self).pop(key)
            self.updateLastMod()
            return result
        except KeyError:
            if args:
                return args[0]
            raise

    def clear(self):
        len_ = self._len()
        if len_:
            super(LastModifiedDict, self).clear()
            self.updateLastMod()

    def __setitem__(self, key, value):
        super(LastModifiedDict, self).__setitem__(key, value)
        self.updateLastMod()

    def __delitem__(self, key):
        super(LastModifiedDict, self).__delitem__(key)
        self.updateLastMod()

register = getattr(collections.Mapping, "register")
register(ZC_Dict)


class CaseInsensitiveLastModifiedDict(LastModifiedDict):
    """
    Preserves the case of keys but compares them case-insensitively.
    """

    # First the documented mutation methods
    def pop(self, key, *args):
        LastModifiedDict.pop(self, _tx_key_insen(key), *args)

    def __setitem__(self, key, value):
        LastModifiedDict.__setitem__(self, _tx_key_insen(key), value)

    def __delitem__(self, key):
        LastModifiedDict.__delitem__(self, key)

    # Now the informational. Since these don't mutate, it's simplest
    # to go directly to the data member

    def __contains__(self, key):
        return key is not None and self._data.__contains__(_tx_key_insen(key))

    def __iter__(self):
        return iter((k.key for k in self._data))

    def __getitem__(self, key):
        return self._data[_tx_key_insen(key)]

    def get(self, key, default=None):
        if key is None:
            return default
        return self._data.get(_tx_key_insen(key), default)

    def items(self, key=None):
        if key is not None:
            key = _tx_key_insen(key)
        return ((k.key, v) for k, v in self._data.items(key))

    def keys(self, key=None):
        if key is not None:
            key = _tx_key_insen(key)
        return (k.key for k in self._data.keys(key))

    def values(self, key=None):
        if key is not None:
            key = _tx_key_insen(key)
        return (v for v in self._data.values(key))

    iterkeys = keys
    iteritems = items
    itervalues = values
    has_key = __contains__
