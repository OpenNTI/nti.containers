#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,too-many-function-args

from hamcrest import is_not
does_not = is_not

import unittest

from zope import interface
from zope import lifecycleevent

from zope.container.btree import BTreeContainer

from zope.container.contained import Contained as ZContained

from nti.base.interfaces import ILastModified

from nti.dublincore.datastructures import CreatedModDateTrackingObject

from nti.containers.tests import SharedConfiguringTestLayer


@interface.implementer(ILastModified)
class Contained(CreatedModDateTrackingObject, ZContained):
    pass


class TestSubscribers(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_events(self):
        container = BTreeContainer()
        interface.alsoProvides(container, ILastModified)
        obj = Contained()
        container['foo'] = obj
        lifecycleevent.modified(obj)
