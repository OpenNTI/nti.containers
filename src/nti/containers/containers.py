#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementations of :mod:`zope.container` containers.

Subclassing a BTree is not recommended (and leads to conflicts), so this takes alternate approachs
to tracking modification date information and implementing case
insensitivity.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time
import numbers
import functools
from random import randint

from collections import Sized
from collections import Mapping
from collections import Iterable
from collections import Container

from UserDict import DictMixin

from repoze.lru import lru_cache

from slugify import slugify_url

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.annotation.interfaces import IAttributeAnnotatable

from zope.cachedescriptors.property import Lazy
from zope.cachedescriptors.property import CachedProperty

from zope.container.btree import BTreeContainer

from zope.container.contained import Contained
from zope.container.contained import NameChooser
from zope.container.contained import uncontained
from zope.container.contained import ContainedProxy
from zope.container.contained import notifyContainerModified

from zope.container.interfaces import INameChooser
from zope.container.interfaces import IBTreeContainer

from zope.container.constraints import checkObject

from zope.intid.interfaces import IIntIds

from zope.location.interfaces import ILocation
from zope.location.interfaces import IContained
from zope.location.interfaces import ISublocations

from zope.site.interfaces import IFolder

from zope.site.site import SiteManagerContainer

from ZODB.interfaces import IBroken

from ZODB import loglevels

from persistent import Persistent

import BTrees
from BTrees.Length import Length

from nti.containers.common import discard_p

from nti.dublincore.time_mixins import DCTimesLastModifiedMixin

from nti.externalization.representation import make_repr

from nti.ntiids import ntiids

from nti.zodb.containers import ZERO_64BIT_INT
from nti.zodb.containers import bit64_int_to_time
from nti.zodb.containers import time_to_64bit_int

from nti.zodb.minmax import NumericMaximum
from nti.zodb.minmax import NumericPropertyDefaultingToZero

from nti.zodb.persistentproperty import PersistentPropertyHolder

# BTree containers

_MAX_UNIQUEID_ATTEMPTS = 1000


class ExhaustedUniqueIdsError(Exception):
    pass


class _IdGenerationMixin(object):
    """
    Mix this in to a BTreeContainer to provide id generation.
    """

    #: The integer counter for generated ids.
    _v_nextid = 0

    def generateId(self, prefix='item', suffix='', 
                   rand_ceiling=999999999, _nextid=None):
        """
        Returns an (string) ID not used yet by this folder. Use this method directly
        if you have no client-supplied name to use as a base. (If you have a meaningful
        or client-supplied name to use as a base, use an :class:`.INameChooser`.)

        The ID is unlikely to collide with other threads and clients.
        The IDs are sequential to optimize access to objects
        that are likely to have some relation (i.e., so objects created in the same
        transaction are stored in the same BTree bucket)
        """
        # JAM: Based on code from Products.BTreeFolder2.BTreeFolder2
        tree = self._SampleContainer__data
        n = _nextid or self._v_nextid
        attempt = 0
        while True:
            if n % 4000 != 0 and n <= rand_ceiling:
                the_id = '%s%d%s' % (prefix, n, suffix)
                if the_id not in tree:
                    break
            n = randint(1, rand_ceiling)
            attempt = attempt + 1
            if attempt > _MAX_UNIQUEID_ATTEMPTS:
                # Prevent denial of service
                raise ExhaustedUniqueIdsError()
        self._v_nextid = n + 1
        return the_id

# Go ahead and mix this in to the base BTreeContainer
BTreeContainer.__bases__ = (_IdGenerationMixin,) + BTreeContainer.__bases__

# zope.container's NameChooser is registered on IWriteContainer, we override

@component.adapter(IBTreeContainer)
class IdGeneratorNameChooser(NameChooser):
    """
    A name chooser that uses the built-in ID generator to create a name.
    It also uses dots instead of dashes, as the superclass does.
    """

    def chooseName(self, name, obj):
        # Unfortunately, the superclass method is entirely
        # monolithic and we must replace it.

        container = self.context

        # convert to unicode and remove characters that checkName does not
        # allow
        if not name:
            # use __class__, not type(), to work with proxies
            name = unicode(obj.__class__.__name__)
        name = unicode(name)  # throw if conversion doesn't work
        name = name.strip()  # no whitespace
        # remove bad characters
        name = name.replace('/', '.').lstrip('+@')

        # If it's clean, go with it
        if name not in container:
            self.checkName(name, obj)
            return name

        # otherwise, generate

        # If the name looks like a filename, as in BASE.EXT, then keep the ext part
        # after the random part
        dot = name.rfind('.')
        if dot >= 0:
            # if name is 'foo.jpg', suffix is '.jpg' and name is 'foo.'.
            # that way we separate the random part with a ., as in foo.1.jpg
            suffix = name[dot:]
            name = name[:dot + 1]
        else:
            name = name + '.'
            suffix = ''

        if suffix == '.':
            suffix = ''

        # If the suffix is already an int, increment that
        try:
            extid = int(suffix[1:])
            nextid = extid + 1
        except ValueError:
            nextid = None
        else:
            suffix = ''

        name = container.generateId(name, suffix, _nextid=nextid)
        # Make sure the name is valid.    We may have started with something bad.
        self.checkName(name, obj)
        return name


@interface.implementer(INameChooser)
class AbstractNTIIDSafeNameChooser(object):
    """
    Handles NTIID-safe name choosing for objects in containers.
    Typically these objects are :class:`.ITitledContent`

    There must be some other name chooser that's next in line for the underlying
    container's interface; after we make the name NTIID safe we will lookup and call that
    chooser.
    """

    #: class attribute, subclasses must set.
    leaf_iface = None

    #: Set if the name should be passed through URL-safe
    #: sluggification if it is not safely a NTIID specific
    #: part already.
    slugify = True

    def __init__(self, context):
        self.context = context

    def __make_specific_safe(self, name):
        try:
            return ntiids.make_specific_safe(name)
        except ntiids.InvalidNTIIDError as e:
            if 'title' in self.leaf_iface:
                e.field = self.leaf_iface['title']
            else:
                e.field = self.leaf_iface['__name__']
            raise

    def _to_ntiid_safe(self, name):
        try:
            return self.__make_specific_safe(name)
        except ntiids.InvalidNTIIDError:
            if self.slugify:
                return self.__make_specific_safe(slugify_url(name))
            raise

    def chooseName(self, name, obj):
        # NTIID flatten
        name = self._to_ntiid_safe(name)

        # Now on to the next adapter (Note: this ignores class-based adapters)
        # First, get the "required" interface list (from the adapter's standpoint),
        # removing the think we just adapted out
        remaining = interface.providedBy(self.context) - self.leaf_iface
        # now perform a lookup. The first arg has to be a tuple for whatever
        # reason
        sm = component.getSiteManager()
        factory = sm.adapters.lookup((remaining,), INameChooser)
        return factory(self.context).chooseName(name, obj)


class _CheckObjectOnSetMixin(object):
    """
    Works only with the standard BTree container.
    """

    def _setitemf(self, key, value):
        checkObject(self, key, value)
        super(_CheckObjectOnSetMixin, self)._setitemf(key, value)

try:
    from Acquisition import aq_base
    from Acquisition.interfaces import IAcquirer

    class AcquireObjectsOnReadMixin(object):
        """
        Mix this in /before/ the container to support implicit
        acquisition.
        """

        def __setitem__(self, key, value):
            """
            Ensure that we do not put an acquisition wrapper
            as the __parent__ key (self).
            """
            self = aq_base(self)
            super(AcquireObjectsOnReadMixin, self).__setitem__(key, value)

        def __acquire(self, result):
            if IAcquirer.providedBy(result):
                # Make it __of__ this object. But if this object is itself
                # already acquired, and from its own parent, then
                # there's no good reason to acquire from the wrapper
                # that is this object.
                base_self = aq_base(self)
                base_self_parent = getattr(base_self, '__parent__', None)
                if     base_self is self \
                    or base_self_parent is getattr(self, '__parent__', None):
                    result = result.__of__(base_self)

            return result

        def __getitem__(self, key):
            result = super(AcquireObjectsOnReadMixin, self).__getitem__(key)
            return self.__acquire(result)

        def get(self, key, default=None):
            result = super(AcquireObjectsOnReadMixin, self).get(key,
                                                                default=default)
            # BTreeFolder doesn't wrap the default
            if result is not default:
                result = self.__acquire(result)
            return result

except ImportError:
    # Acquisition not installed
    class AcquireObjectsOnReadMixin(object):
        """
        No-op because Acquisition is not installed.
        """

# Last modified based containers


@interface.implementer(IAttributeAnnotatable)
class LastModifiedBTreeContainer(DCTimesLastModifiedMixin,
                                 BTreeContainer,
                                 PersistentPropertyHolder):

    """
    A BTreeContainer that provides storage for lastModified and created
    attributes (implements the :class:`interfaces.ILastModified` interface).

    Note that directly changing keys within this container does not actually
    change those dates; instead, we rely on event listeners to
    notice ObjectEvents and adjust the times appropriately.

    These objects are allowed to be annotated (see :mod:`zope.annotation`).
    """

    createdTime = 0
    lastModified = NumericPropertyDefaultingToZero(str('_lastModified'),
                                                   NumericMaximum,
                                                   as_number=True)

    def __init__(self):
        self.createdTime = time.time()
        super(LastModifiedBTreeContainer, self).__init__()

    def updateLastMod(self, t=None):
        if t is not None and t > self.lastModified:
            self.lastModified = t
        else:
            self.lastModified = time.time()
        return self.lastModified

    def updateLastModIfGreater(self, t):
        """
        Only if the given time is (not None and) greater than this object's
        is this object's time changed.
        """
        if t is not None and t > self.lastModified:
            self.lastModified = t
        return self.lastModified

    def clear(self):
        """
        Convenience method to clear the entire tree at one time.
        """
        if len(self) == 0:
            return
        for k in list(self.keys()):
            del self[k]

    def maxKey(self):
        return self._SampleContainer__data.maxKey()

    def minKey(self):
        return self._SampleContainer__data.minKey()

    def _delitemf(self, key, event=True):
        # make sure our lazy property gets set
        l = self._BTreeContainer__len
        item = self._SampleContainer__data[key]
        if event:
            # notify with orignal name
            lifecycleevent.removed(item, self, item.__name__)
        # remove
        del self._SampleContainer__data[key]
        l.change(-1)
        # clean containment
        if event and not IBroken.providedBy(item):
            item.__name__ = None
            item.__parent__ = None
        return item

    # We know that these methods are implemented as iterators.
    # This is not part of the IBTreeContainer interface, but it is
    # dict-like.
    # IBTreeContainer allows sending in exactly one min-key to
    # keys(), items() and values(), but the underlying BTree
    # supports a full range. We use that here.

    def itervalues(self, min=None, max=None, excludemin=False, excludemax=False):
        if max is None or min is None:
            return self.values(min)
        return self._SampleContainer__data.values(
            min, max, excludemin, excludemax)

    def iterkeys(self, min=None, max=None, excludemin=False, excludemax=False):
        if max is None or min is None:
            return self.keys(min)
        return self._SampleContainer__data.keys(min, max, excludemin, excludemax)

    def iteritems(self, min=None, max=None, excludemin=False, excludemax=False):
        if max is None or min is None:
            return self.items(min)
        return self._SampleContainer__data.items(min, max, excludemin, excludemax)

mapping_register = getattr(Mapping, 'register')
mapping_register(LastModifiedBTreeContainer)

ModDateTrackingBTreeContainer = LastModifiedBTreeContainer  # BWC


class CheckingLastModifiedBTreeContainer(_CheckObjectOnSetMixin,
                                         LastModifiedBTreeContainer):
    """
    A BTree container that validates constraints when items are added.
    """


@interface.implementer(IFolder)
class CheckingLastModifiedBTreeFolder(CheckingLastModifiedBTreeContainer,
                                      SiteManagerContainer):
    """
    Scalable :class:`IFolder` implementation.
    """


class EventlessLastModifiedBTreeContainer(LastModifiedBTreeContainer):
    """
    A BTreeContainer that doesn't actually broadcast any events, because
    it doesn't actually take ownership of the objects. The objects must
    have their ``__name__`` and ``__parent__`` set by a real container.
    """

    def _checkKey(self, key):
        # Containers don't allow None; keys must be unicode
        if isinstance(key, str):
            try:
                key = unicode(key)
            except UnicodeError:
                raise TypeError('Key could not be converted to unicode')
        elif not isinstance(key, unicode):
            raise TypeError("Key must be unicode")

    def _checkValue(self, value):
        if value is None:
            raise TypeError('Value must not be None')

    def _checkSame(self, key, value):
        old = self.get(key)
        if old is not None:
            if old is value:
                # no op
                return True
            raise KeyError(key)
        return False

    def __setitem__(self, key, value):
        __traceback_info__ = key, value

        self._checkKey(key)
        self._checkValue(value)
        if not self._checkSame(key, value):
            # Super's _setitemf changes the length, so only do this if
            # it's not here already. To comply with the containers interface,
            # we cannot add duplicates
            self._setitemf(key, value)
        # TODO: Should I enforce anything with the __parent__ and __name__ of
        # the value? For example, parent is not None and __name__ == key?
        # We're probably more generally useful without those constraints,
        # but more specifically useful in certain scenarios with those
        # constraints.

    def __delitem__(self, key):
        self._delitemf(key, event=False)

    def pop(self, key, default=None):
        try:
            result = self[key]
            del self[key]
        except KeyError:
            result = default
        return result


class NOOwnershipLastModifiedBTreeContainer(EventlessLastModifiedBTreeContainer):
    """
    A BTreeContainer that only broadcast added, removed and container modified events
    but does not take ownership of the objects
    """

    def clear(self, event=True):
        for k in list(self.keys()):
            if event:
                del self[k]
            else:
                self._delitemf(k, event=False)

    def _transform(self, value):
        if not IContained.providedBy(value):
            if ILocation.providedBy(value):
                interface.alsoProvides(value, IContained)
            else:
                value = ContainedProxy(value)
        return value

    def __setitem__(self, key, value):
        self._checkKey(key)
        self._checkValue(value)
        if not self._checkSame(key, value):
            value = self._transform(value)
            self._setitemf(key, value)
            # pass self as container so value object can get a connection if
            # available
            lifecycleevent.added(value, self, key)
            notifyContainerModified(self)

    def __delitem__(self, key):
        value = self[key]
        self._delitemf(key, event=False)
        lifecycleevent.removed(value, self, key)
        notifyContainerModified(self)


# Case insensitive containers


@functools.total_ordering
class _CaseInsensitiveKey(object):
    """
    This class implements a dictionary key that preserves case, but
    compares case-insensitively. It works with unicode keys only (BTrees do not
    work if 8-bit and unicode are mixed) by converting all keys to unicode.

    This is a bit of a heavyweight solution. It is nonetheless optimized for comparisons
    only with other objects of its same type. It must not be subclassed.
    """

    def __init__(self, key):
        if not isinstance(key, basestring):
            raise TypeError("Expected basestring instead of %s (%r)" %
                            (type(key), key))
        self.key = unicode(key)
        self._lower_key = self.key.lower()

    def __str__(self):  # pragma: no cover
        return self.key

    def __repr__(self):  # pragma: no cover
        return "%s('%s')" % (self.__class__, self.key)

    # These should only ever be compared to themselves

    def __eq__(self, other):
        try:
            return other is self or other._lower_key == self._lower_key
        except AttributeError:  # pragma: no cover
            return NotImplemented

    def __hash__(self):
        return hash(self._lower_key)

    def __lt__(self, other):
        try:
            return self._lower_key < other._lower_key
        except AttributeError:  # pragma: no cover
            return NotImplemented

    def __gt__(self, other):
        try:
            return self._lower_key > other._lower_key
        except AttributeError:  # pragma: no cover
            return NotImplemented

# These work best as plain functions so that the 'self'
# argument is not captured. The self argument is persistent
# and so that messes with caches


@lru_cache(10000)
def tx_key_insen(key):
    return _CaseInsensitiveKey(key) if key is not None else None
_tx_key_insen = tx_key_insen  # BWC

# As of BTrees 4.0.1, None is no longer allowed to be a key
# or even used in __contains__


@interface.implementer(ISublocations)
class CaseInsensitiveLastModifiedBTreeContainer(LastModifiedBTreeContainer):
    """
    A BTreeContainer that only works with string (unicode) keys, and treats
    them in a case-insensitive fashion. The original case of the key entered is
    preserved.
    """

    # For speed, we generally implement all these functions directly in terms of the
    # underlying data; we know that's what the superclass does.

    # Note that the IContainer contract specifies keys that are strings. None
    # is not allowed.

    def __contains__(self, key):
        return  key is not None \
            and _tx_key_insen(key) in self._SampleContainer__data

    def __iter__(self):
        # For purposes of evolving, when our parent container
        # class has changed from one that used to manually wrap keys to
        # one that depends on us, we trap attribute errors. This should only
        # happen during the initial migration.
        for k in self._SampleContainer__data:
            __traceback_info__ = self, k
            try:
                yield k.key
            except AttributeError:  # pragma: no cover
                if k == 'Last Modified':
                    continue
                yield k

    def __getitem__(self, key):
        return self._SampleContainer__data[_tx_key_insen(key)]

    def get(self, key, default=None):
        if key is None:
            return default
        return self._SampleContainer__data.get(_tx_key_insen(key), default)

    def _setitemf(self, key, value):
        LastModifiedBTreeContainer._setitemf(self, _tx_key_insen(key), value)

    def __delitem__(self, key):
        # deleting is somewhat complicated by the need to broadcast
        # events with the original case
        l = self._BTreeContainer__len
        item = self[key]
        uncontained(item, self, item.__name__)
        del self._SampleContainer__data[_tx_key_insen(key)]
        l.change(-1)

    def _delitemf(self, key, event=True):
        item = LastModifiedBTreeContainer._delitemf(self,
                                                    _tx_key_insen(key),
                                                    event)
        return item

    def items(self, key=None):
        if key is not None:
            key = _tx_key_insen(key)

        for k, v in self._SampleContainer__data.items(key):
            try:
                yield k.key, v
            except AttributeError:  # pragma: no cover
                if k == 'Last Modified':
                    continue
                yield k, v

    def keys(self, key=None):
        if key is not None:
            key = _tx_key_insen(key)
        return (k.key for k in self._SampleContainer__data.keys(key))

    def values(self, key=None):
        if key is not None:
            key = _tx_key_insen(key)
        return (v for v in self._SampleContainer__data.values(key))

    def iterkeys(self, min=None, max=None, excludemin=False, excludemax=False):
        if max is None or min is None:
            return self.keys(min)
        min = _tx_key_insen(min)
        max = _tx_key_insen(max)
        return (k.key for k in self._SampleContainer__data.keys(
            min, max, excludemin, excludemax))

    def sublocations(self):
        # We directly implement ISublocations instead of using the adapter for two reasons.
        # First, it's much more efficient as it saves the unwrapping
        # of all the keys only to rewrap them back up to access the data.
        # Second, during evolving, as with __iter__, we may be in an inconsistent state
        # that has keys of different types
        for v in self._SampleContainer__data.values():
            # For evolving, reject numbers (Last Modified key)
            if isinstance(v, numbers.Number):  # pragma: no cover
                continue
            yield v

# BWC
KeyPreservingCaseInsensitiveModDateTrackingBTreeContainer = CaseInsensitiveLastModifiedBTreeContainer


class CaseSensitiveLastModifiedBTreeFolder(CheckingLastModifiedBTreeFolder):
    """
    Scalable case-sensitive :class:`IFolder` implementation.
    """

    def sublocations(self):
        for v in self._SampleContainer__data.values():
            yield v


@interface.implementer(IFolder)
class CaseInsensitiveLastModifiedBTreeFolder(CaseInsensitiveLastModifiedBTreeContainer,
                                             SiteManagerContainer):
    """
    Scalable case-insensitive :class:`IFolder` implementation.
    """


class CaseInsensitiveCheckingLastModifiedBTreeFolder(_CheckObjectOnSetMixin,
                                                     CaseInsensitiveLastModifiedBTreeFolder):
    pass


class CaseInsensitiveCheckingLastModifiedBTreeContainer(_CheckObjectOnSetMixin,
                                                        CaseInsensitiveLastModifiedBTreeContainer):
    pass

# Containers specialized to work with intids.
# Make pylint not complain about "badly implemented container", "Abstract class not referenced"
# pylint: disable=R0924,R0921


@interface.implementer(ILocation)
class _AbstractIntidResolvingFacade(object):
    """
    Base class to support facades that resolve intids.
    """

    __parent__ = None
    __name__ = None
    _intids = None

    def __init__(self, context, allow_missing=False, 
                 parent=None, name=None, intids=None):
        """
        :keyword bool allow_missing: If False (the default) then errors will be
                raised for objects that are in the set but cannot be found by id. If
                ``True``, then they will be silently ignored.
        :keyword intids: If provided, this will be the intid utility we use. Otherwise, we
                will look one up at iteration time.
        """
        self.context = context
        self._allow_missing = allow_missing
        if parent is not None:
            self.__parent__ = parent
        if name is not None:
            self.__name__ = name
        if intids is not None:
            self._intids = intids

    def __reduce__(self):
        raise TypeError("Transient object; should not be pickled")


class IntidResolvingIterable(_AbstractIntidResolvingFacade,
                             Iterable,
                             Container, 
                             Sized):
    """
    An iterable that wraps another iterable, resolving intids as it
    goes. Typically this will be a :mod:`BTrees` IISet of some family.
    """

    def __iter__(self, allow_missing=None):
        allow_missing = allow_missing or self._allow_missing
        if self._intids is not None:
            intids = self._intids 
        else:
            intids = component.getUtility(IIntIds)
        for iid in self.context:
            __traceback_info__ = iid, self.__parent__, self.__name__
            try:
                yield intids.getObject(iid)
            except TypeError:
                # Raised when we send a string or something, which means we do not actually
                # have an IISet. This is a sign of an object missed during
                # migration
                if not allow_missing:
                    raise
                logger.log(loglevels.TRACE, 
                           "Incorrect key '%s' in %r of %r",
                           iid, self.__name__, self.__parent__)
            except KeyError:
                if not allow_missing:
                    raise
                logger.log(loglevels.TRACE, 
                           "Failed to resolve key '%s' in %r of %r",
                           iid, self.__name__, self.__parent__)

    def __len__(self):
        """
        This is only guaranteed to be accurate with `allow_missing` is ``False``.
        """
        return len(self.context)

    def __contains__(self, obj):
        """
        Is the given object in the container? This is implemented as a linear check.
        """
        for other in self.__iter__(allow_missing=True):
            if other == obj:
                return True


class IntidResolvingMappingFacade(_AbstractIntidResolvingFacade,
                                  DictMixin, 
                                  Mapping):
    """
    A read-only dict-like object wrapping another mapping (usually a :mod:`BTrees.family.OO.BTree`).
    The keys will typically be strings, and the values must be iterables of integers
    appropriate for use with the intid utility. (Usually they will be ``IISet`` objects.)
    """

    def _wrap(self, key, val):
        return IntidResolvingIterable(val, allow_missing=self._allow_missing,
                                      parent=self, name=key, intids=self._intids)

    def __getitem__(self, key):
        return self._wrap(key, self.context[key])

    def keys(self):
        return self.context.keys()

    def __contains__(self, key):
        return key in self.context

    def __iter__(self):
        return iter(self.context)

    def iteritems(self):
        return ((k, self._wrap(k, v)) for k, v in self.context.iteritems())

    def values(self):
        return (v for _, v in self.iteritems())

    def __len__(self):
        return len(self.context)

    __repr__ = make_repr(lambda self: '<%s %s/%s>' % (self.__class__.__name__,
                                                      self.__parent__,
                                                      self.__name__))

    def __setitem__(self, key, val):
        raise TypeError('Immutable Object')

    def __delitem__(self, key):
        raise TypeError('Immutable Object')


class _LengthIntidResolvingMappingFacade(IntidResolvingMappingFacade):

    def __init__(self, *args, **kwargs):
        self._len = kwargs.pop('_len')
        super(_LengthIntidResolvingMappingFacade, self).__init__(*args, **kwargs)

    def _wrap(self, key, val):
        wrapped = super(_LengthIntidResolvingMappingFacade, self)._wrap(key, val)
        wrapped.lastModified = self.__parent__._get_container_mod_time(key)
        return wrapped

    def __len__(self):
        return self._len()

_marker = object()


class IntidContainedStorage(Persistent, Contained, Iterable, Container, Sized):
    """
    An object that implements something like the interface of
    :class:`nti.dataserver.datastructures.ContainedStorage`, but in a
    simpler form using only intids, and assuming that we never need to
    look objects up by container/localID pairs.

    .. note:: This class and API is provisional.

    """

    family = BTrees.family64

    def __init__(self, family=None):
        super(IntidContainedStorage, self).__init__()
        if family is not None:
            self.family = family
        else:
            intids = component.queryUtility(IIntIds)
            if intids is not None:
                self.family = intids.family

        # Map from string container ids to self.family.II.TreeSet
        # { 'containerId': II.TreeSet() }
        # The values in the TreeSet are the intids of the shared
        # objects. Remember that len() of them is not efficient.
        self._containers = self.family.OO.BTree()

    def __iter__(self):
        return iter(self._containers)

    @Lazy
    def _IntidContainedStorage__len(self):
        l = Length()
        ol = len(self._containers)
        if ol > 0:
            l.change(ol)
        self._p_changed = True
        return l

    @Lazy
    def _IntidContainedStorage__moddates(self):
        """
        OF map from containerId to (int) date of last modification,
        since we cannot store them on the TreeSet itself
        """
        result = self.family.OI.BTree()
        self._p_changed = True
        return result

    def _get_container_mod_time(self, containerId):
        self._p_activate()
        if '_IntidContainedStorage__moddates' not in self.__dict__:
            return 0
        return bit64_int_to_time(
            self.__moddates.get(containerId, ZERO_64BIT_INT))

    def __len__(self):
        return self.__len()

    # TODO: Is this right? Are we sure that the volatile properties added will
    # go away when ghosted?
    @CachedProperty
    def containers(self):
        """
        Returns an object that has a `values` method that iterates
        the list-like (immutable) containers.

        .. note:: It is not efficient to get the length of the list-like
                containers; it is however, efficient, to test their boolean
                status (empty or not) and to get the length of the overall returned
                object.
        """
        return _LengthIntidResolvingMappingFacade(self._containers,
                                                  allow_missing=True,
                                                  parent=self,
                                                  name='SharedContainedObjectStorage',
                                                  _len=self.__len)

    def _check_contained_object_for_storage(self, contained):
        pass

    def _get_intid_for_object(self, contained, when_none=_marker):
        if contained is None and when_none is not _marker:
            return when_none

        return self._get_intid_for_object_from_utility(contained)

    def _get_intid_for_object_from_utility(self, contained):
        return component.getUtility(IIntIds).getId(contained)

    def addContainedObjectToContainer(self, contained, containerId=''):
        """
        Defaults to the unnamed container
        """
        self._check_contained_object_for_storage(contained)

        container_set = self._containers.get(containerId)
        if container_set is None:
            _len = self.__len
            container_set = self.family.II.TreeSet()
            self._containers[containerId] = container_set
            _len.change(1)
        container_set.add(self._get_intid_for_object(contained))
        self.__moddates[containerId] = time_to_64bit_int(time.time())
        return contained

    def deleteContainedObjectIdFromContainer(self, intid, containerId):
        container_set = self._containers.get(containerId)
        if container_set is not None:
            result = discard_p(container_set, intid)
            self.__moddates[containerId] = time_to_64bit_int(time.time())
            return result

    def deleteEqualContainedObjectFromContainer(self, contained, containerId=''):
        """
        Defaults to the unnamed container
        """
        self._check_contained_object_for_storage(contained)
        if self.deleteContainedObjectIdFromContainer(self._get_intid_for_object(contained),
                                                     containerId):
            return contained

    def addContainedObject(self, contained):
        """
        Fetches the containerId from the object.
        """
        return self.addContainedObjectToContainer(contained, 
                                                  contained.containerId)

    def deleteEqualContainedObject(self, contained, log_level=None):
        """
        Fetches the containerId from the object.
        """
        return self.deleteEqualContainedObjectFromContainer(contained, 
                                                            contained.containerId)

    def getContainer(self, containerId, defaultValue=None):
        return self.containers.get(containerId, default=defaultValue)

    def popContainer(self, containerId, default=_marker):
        try:
            _len = self.__len
            result = self._containers.pop(containerId)
            self.__moddates.pop(containerId)
            _len.change(-1)
            return result
        except KeyError:
            if default is not _marker:
                return default
            raise

    __repr__ = make_repr(lambda self: '<%s %s/%s>' % (self.__class__.__name__,
                                                      self.__parent__,
                                                      self.__name__))

    # Some dict-like conveniences
    __getitem__ = getContainer

    get = getContainer
    pop = popContainer

    def __contains__(self, key):
        return key in self._containers

    def keys(self):
        return self._containers.keys()

    def values(self):
        return self.containers.values()  # unwrapping

    def items(self):
        return self.containers.items()  # unwrapping
