#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.container.interfaces import IContainerModifiedEvent

def update_container_modified_time(container, event):
	"""
	Register this handler to update modification times when a container is
	modified through addition or removal of children.
	"""
	try:
		container.updateLastMod()
	except AttributeError:
		pass

def update_parent_modified_time(modified_object, event):
	"""
	If an object is modified and it is contained inside a container
	that wants to track modifications, we want to update its parent too...
	but only if the object itself is not already a container and we are
	responding to a IContainerModifiedEvent (that leads to things bubbling
	up surprisingly far).
	"""
	# IContainerModifiedEvent extends IObjectModifiedEvent
	if IContainerModifiedEvent.providedBy(event):
		return

	try:
		modified_object.__parent__.updateLastModIfGreater(modified_object.lastModified)
	except AttributeError:
		pass

def update_object_modified_time(modified_object, event):
	"""
	Register this handler to update modification times when an object
	itself is modified.
	"""
	try:
		modified_object.updateLastMod()
	except AttributeError:
		# this is optional API
		pass
