#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.container.contained import fixing_up
from zope.container.contained import _SENTINEL

from zope.container.contained import ContainedProxy
from zope.container.contained import notifyContainerModified

from zope.event import notify

from zope.lifecycleevent import ObjectAddedEvent
from zope.lifecycleevent import ObjectRemovedEvent

from zope.location.interfaces import ILocation
from zope.location.interfaces import IContained


def noOwnershipContainedEvent(obj, container, name=None):
    """
    see zope.container.contained.containedEvent
    """

    if not IContained.providedBy(obj):
        if ILocation.providedBy(obj):
            interface.alsoProvides(obj, IContained)
        else:
            obj = ContainedProxy(obj)

    oldparent = obj.__parent__
    oldname = obj.__name__

    if oldparent is container and oldname == name:
        # No events
        return obj, None

    # only set name
    obj.__name__ = name
    # pass container to get a connection
    event = ObjectAddedEvent(obj, container, name)
    return obj, event


def no_ownership_setitem(container, setitemf, name, obj):
    """
    see zope.container.contained.setitem
    """
    # Do basic name check:
    if isinstance(name, bytes):
        try:
            name = name.decode('ascii')
        except UnicodeError:
            raise TypeError("name not unicode or ascii string")
    elif not isinstance(name, unicode):
        raise TypeError("name not unicode or ascii string")

    if not name:
        raise ValueError("empty names are not allowed")

    old = container.get(name, _SENTINEL)
    if old is obj:
        return
    if old is not _SENTINEL:
        raise KeyError(name)

    obj, event = noOwnershipContainedEvent(obj, container, name)
    setitemf(name, obj)
    if event is not None:
        notify(event)
        notifyContainerModified(container)


def no_ownership_uncontained(obj, container, unused_name=None):
    """    
    see zope.container.contained.uncontained
    """
    try:
        oldname = obj.__name__
        oldparent = obj.__parent__
    except AttributeError:
        # The old object doesn't implements IContained
        # Maybe we're converting old data:
        if hasattr(obj, '__Broken_state__'):
            state = obj.__Broken_state__
            oldparent = state['__parent__']
            oldname = state['__name__']
        else:
            if not fixing_up:
                raise
            oldparent = None
            oldname = None

    event = ObjectRemovedEvent(obj, oldparent, oldname)
    notify(event)
    notifyContainerModified(container)
