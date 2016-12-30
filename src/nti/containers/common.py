#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

def discard_p(the_set, the_value):
	"""
	A version of :meth:`set.discard` that functions as a predicate by returning
	whether or not the object was removed from the set. In addition to working on :class:`set` objects,
	it also works on :class:`BTrees.OOBTree.OOTreeSet` (and the smaller :class:`BTrees.OOBTree.OOSet`,
	plus the sets in other families). (It incidentally works on lists, though not efficiently.)

	:param set the_set: The :class:`set` or set-like thing.
	:param the_value: The object to remove from `the_set`. If the object isn't
		present in the set, no exception will be raised.
	:return: A true value if `the_value` was present in the set and has now
		been removed; a false value if `the_value` was not present in the set.
	"""
	try:
		# Both set and OOSet support remove with the same semantics
		the_set.remove(the_value)
		return True  # TODO: Is there a more useful value to return? If so document it
	except KeyError:
		return False
