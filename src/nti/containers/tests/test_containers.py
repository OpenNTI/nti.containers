#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import greater_than
from hamcrest import same_instance
does_not = is_not

from nose.tools import assert_raises

from nti.testing.matchers import is_true
from nti.testing.matchers import is_false
from nti.testing.matchers import validly_provides

import unittest

import BTrees

from zope import interface
from zope import lifecycleevent

from zope.component.eventtesting import getEvents
from zope.component.eventtesting import clearEvents

from zope.container.contained import Contained as ZContained

from zope.container.interfaces import INameChooser

from zope.location.interfaces import IContained

from nti.base.interfaces import ILastModified

from nti.containers.containers import IntidContainedStorage
from nti.containers.containers import IdGeneratorNameChooser
from nti.containers.containers import LastModifiedBTreeContainer
from nti.containers.containers import IntidResolvingMappingFacade
from nti.containers.containers import EventlessLastModifiedBTreeContainer
from nti.containers.containers import NOOwnershipLastModifiedBTreeContainer
from nti.containers.containers import CaseInsensitiveLastModifiedBTreeContainer

from nti.dublincore.datastructures import CreatedModDateTrackingObject

from nti.containers.tests import SharedConfiguringTestLayer

family64 = BTrees.family64


@interface.implementer(ILastModified)
class Contained(CreatedModDateTrackingObject, ZContained):
    pass


class TestContainers(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_name_chooser(self):
        c = LastModifiedBTreeContainer()

        name_chooser = INameChooser(c)
        assert_that(name_chooser, is_(IdGeneratorNameChooser))

        # initial names
        c['foo.jpg'] = Contained()
        c['baz'] = Contained()

        # bad chars are stripped, and the result is unicode
        name = name_chooser.chooseName(b'+@hah/bah', None)
        assert_that(name, is_(unicode))
        assert_that(name, is_('hah.bah'))

        # assign to the random id so we have deterministic results
        c._v_nextid = 1
        name = name_chooser.chooseName('foo.jpg', None)

        assert_that(name, is_('foo.1.jpg'))

        c._v_nextid = 1
        name = name_chooser.chooseName('baz', None)
        assert_that(name, is_('baz.1'))

        # trailing dots don't get doubled
        c._v_nextid = 1
        c['baz.'] = Contained()
        name = name_chooser.chooseName('baz.', None)
        assert_that(name, is_('baz.1'))

        # A final digit is incremented
        c['biz.1'] = Contained()
        c._v_nextid = 0
        name = name_chooser.chooseName('biz.1', None)
        assert_that(name, is_('biz.2'))

    def test_lastModified_container_event(self):

        c = LastModifiedBTreeContainer()

        assert_that(c.lastModified, is_(0))

        c['k'] = ZContained()

        assert_that(c.lastModified, is_(greater_than(0)),
                    "__setitem__ should change lastModified")
        # reset
        c.lastModified = 0
        assert_that(c.lastModified, is_(0))

        del c['k']

        assert_that(c.lastModified, is_(greater_than(0)),
                    "__delitem__ should change lastModified")

        # coverage
        c.updateLastModIfGreater(c.lastModified + 100)

    def test_lastModified_in_parent_event(self):
        c = LastModifiedBTreeContainer()

        child = Contained()
        assert_that(child, validly_provides(ILastModified))

        c['k'] = child
        # reset
        c.lastModified = 0
        assert_that(c.lastModified, is_(0))

        lifecycleevent.modified(child)

        assert_that(c.lastModified, is_(greater_than(0)),
                    "changing a child should change lastModified")

    def test_case_insensitive_container(self):
        c = CaseInsensitiveLastModifiedBTreeContainer()

        child = ZContained()
        c['UPPER'] = child
        assert_that(child, has_property('__name__', 'UPPER'))

        assert_that(c.__contains__(None), is_false())
        assert_that(c.__contains__('UPPER'), is_true())
        assert_that(c.__contains__('upper'), is_true())

        assert_that(c.__getitem__('UPPER'), is_(child))
        assert_that(c.__getitem__('upper'), is_(child))

        assert_that(list(iter(c)), is_(['UPPER']))
        assert_that(list(c.keys()), is_(['UPPER']))
        assert_that(list(c.keys('a')), is_(['UPPER']))
        assert_that(list(c.keys('A')), is_(['UPPER']))
        assert_that(list(c.iterkeys()), is_(['UPPER']))

        assert_that(list(c.items()), is_([('UPPER', child)]))
        assert_that(list(c.items('a')), is_([('UPPER', child)]))
        assert_that(list(c.items('A')), is_([('UPPER', child)]))
        assert_that(list(c.iteritems()), is_([('UPPER', child)]))

        assert_that(list(c.values()), is_([child]))
        assert_that(list(c.values('a')), is_([child]))
        assert_that(list(c.values('A')), is_([child]))
        assert_that(list(c.itervalues()), is_([child]))

        del c['upper']

    def test_case_insensitive_container_invalid_keys(self):

        c = CaseInsensitiveLastModifiedBTreeContainer()

        with assert_raises(TypeError):
            c.get({})

        with assert_raises(TypeError):
            c.get(1)

    def test_eventless_container(self):

        # The container doesn't proxy, fire events, or examine __parent__ or
        # __name__
        c = EventlessLastModifiedBTreeContainer()

        clearEvents()

        value = object()
        value2 = object()
        c['key'] = value
        assert_that(c['key'], is_(same_instance(value)))
        assert_that(getEvents(), has_length(0))
        assert_that(c, has_length(1))

        # We cannot add duplicates
        with assert_raises(KeyError):
            c['key'] = value2

        # We cannot add None values or non-unicode keys
        with assert_raises(TypeError):
            c['key2'] = None

        with assert_raises(TypeError):
            c[None] = value

        with assert_raises(TypeError):
            c[b'\xf0\x00\x00\x00'] = value

        assert_that(c._checkSame('key', value), is_(True))

        # After all that, nothing has changed
        assert_that(c['key'], is_(same_instance(value)))
        assert_that(getEvents(), has_length(0))
        assert_that(c, has_length(1))

        del c['key']
        assert_that(c.get('key'), is_(none()))
        assert_that(getEvents(), has_length(0))
        assert_that(c, has_length(0))

    def test_noownership_container(self):

        marker = object()

        @interface.implementer(IContained)
        class Foo(object):
            __parent__ = marker
            __name__ = None

        c = NOOwnershipLastModifiedBTreeContainer()
        clearEvents()

        value = Foo()
        value2 = Foo()
        c['key'] = value
        assert_that(c['key'], is_(same_instance(value)))
        assert_that(getEvents(), has_length(2))
        assert_that(c, has_length(1))
        assert_that(value, has_property('__parent__', is_(marker)))

        # We cannot add duplicates
        with assert_raises(KeyError):
            c['key'] = value2

        # We cannot add None values or non-unicode keys
        with assert_raises(TypeError):
            c['key2'] = None

        with assert_raises(TypeError):
            c[None] = value

        with assert_raises(TypeError):
            c[b'\xf0\x00\x00\x00'] = value

        # After all that, nothing has changed
        assert_that(c['key'], is_(same_instance(value)))
        assert_that(getEvents(), has_length(2))
        assert_that(c, has_length(1))

        clearEvents()
        c['key'] = value
        assert_that(getEvents(), has_length(0))
        assert_that(c, has_length(1))

        clearEvents()
        del c['key']
        assert_that(c.get('key'), is_(none()))
        assert_that(getEvents(), has_length(2))
        assert_that(c, has_length(0))

        clearEvents()
        c['key'] = object()
        assert_that(c.get('key'), is_not(none()))
        assert_that(getEvents(), has_length(2))
        assert_that(c, has_length(1))


class TestMappingFacade(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    class MockUtility(object):

        data = None

        def getObject(self, key):
            return self.data[key]

    def setUp(self):
        super(TestMappingFacade, self).setUp()
        self.utility = self.MockUtility()
        self.utility.data = {i: object() for i in range(10)}

        btree = family64.OO.BTree()
        btree['a'] = family64.II.TreeSet()
        btree['a'].add(1)
        btree['a'].add(2)
        btree['a'].add(3)
        btree['b'] = family64.II.TreeSet()
        btree['b'].add(4)
        self.btree = btree

        self.facade = IntidResolvingMappingFacade(btree, intids=self.utility)

    def test_keys(self):
        assert_that(list(self.facade), is_(['a', 'b']))
        assert_that(list(self.facade.keys()), is_(['a', 'b']))

        assert_that(self.facade, has_key('a'))
        assert_that(self.facade, does_not(has_key('c')))

        assert_that(self.facade, has_length(2))

    def test_get(self):
        facade = self.facade
        # iter unpack
        [obj] = facade['b']
        assert_that(obj, is_(self.utility.data[4]))

        [obj] = list(facade.values())[1]
        assert_that(obj, is_(self.utility.data[4]))

        assert_that(self.utility.data[4], is_in(facade['b']))


class TestIntidContainedStorage(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    class MockUtility(object):

        data = None

        def getObject(self, key):
            return self.data[key]

        def getId(self, obj):
            for k, v in self.data.items():
                if obj == v:
                    return k
            raise KeyError()

    class FixedUtilityIntidContainedStorage(IntidContainedStorage):
        utility = None

        def _get_intid_for_object_from_utility(self, contained):
            return self.utility.getId(contained)

    def setUp(self):
        super(TestIntidContainedStorage, self).setUp()
        self.utility = self.MockUtility()
        self.utility.data = {i: object() for i in range(10)}
        self.storage = self.FixedUtilityIntidContainedStorage()
        self.storage.utility = self.utility

    def test_len(self):
        storage = self.storage
        containers = self.storage  # the facade stays in sync

        def assert_len(i):
            assert_that(storage, has_length(i))
            assert_that(containers, has_length(i))

        assert_len(0)
        storage.addContainedObjectToContainer(self.utility.data[1])
        assert_len(1)
        storage.addContainedObjectToContainer(self.utility.data[2], 'b')
        assert_len(2)

        # As it is the length of the containers, removing from a container doesn't
        # change anything
        storage.deleteEqualContainedObjectFromContainer(self.utility.data[1])
        assert_len(2)

        storage.deleteEqualContainedObjectFromContainer(
            self.utility.data[2],
            'b')
        assert_len(2)

        storage.popContainer('')
        assert_len(1)

        storage.popContainer('b')
        assert_len(0)
