#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,too-many-function-args
# pylint: disable=unsubscriptable-object,attribute-defined-outside-init

from hamcrest import is_
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

import fudge
import pickle
import unittest

from zope import component
from zope import interface

from zope.container.contained import Contained as ZContained

from zope.intid.interfaces import IIntIds

import BTrees

from nti.base.interfaces import ILastModified

from nti.containers.datastructures import IntidContainedStorage
from nti.containers.datastructures import IntidResolvingIterable
from nti.containers.datastructures import IntidResolvingMappingFacade
from nti.containers.datastructures import _LengthIntidResolvingMappingFacade

from nti.dublincore.datastructures import CreatedModDateTrackingObject

from nti.containers.tests import SharedConfiguringTestLayer

family64 = BTrees.family64


@interface.implementer(ILastModified)
class Contained(CreatedModDateTrackingObject, ZContained):
    pass


class TestIntidResolvingIterable(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_iter(self):
        intids = fudge.Fake()
        component.getGlobalSiteManager().registerUtility(intids, IIntIds)
        intids.provides('getObject').raises(TypeError())
        iterable = IntidResolvingIterable((1, 2))
        with self.assertRaises(TypeError):
            list(iterable.__iter__())
        assert_that(list(iterable.__iter__(True)), is_([]))
        component.getGlobalSiteManager().unregisterUtility(intids, IIntIds)

        assert_that(iterable, has_length(2))

        intids = fudge.Fake().provides('getObject').raises(KeyError())
        iterable = IntidResolvingIterable((1, 2))
        iterable._intids = intids
        with self.assertRaises(KeyError):
            list(iterable.__iter__())
        assert_that(list(iterable.__iter__(True)), is_([]))

        with self.assertRaises(TypeError):
            pickle.dumps(iterable)


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
        repr(self.facade)

        assert_that('a', is_in(self.facade))

    def test_get(self):
        facade = self.facade
        # iter unpack
        [obj] = facade['b']
        assert_that(obj, is_(self.utility.data[4]))

        [obj] = list(facade.values())[1]
        assert_that(obj, is_(self.utility.data[4]))

        assert_that(self.utility.data[4], is_in(facade['b']))

    def test_immutable(self):
        with self.assertRaises(TypeError):
            self.facade['k'] = family64.II.TreeSet()

        with self.assertRaises(TypeError):
            del self.facade['b']

    def test_length_resolving_facade(self):
        btree = family64.OO.BTree()
        btree['a'] = family64.II.TreeSet()
        facade = _LengthIntidResolvingMappingFacade(btree, intids=self.utility,
                                                    _len=lambda: 1)
        facade.__parent__ = fudge.Fake().provides('_get_container_mod_time').returns(0)
        facade._wrap('b', 'c')
        assert_that(facade, has_length(1))


class TestIntidContainedStorage(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    class MockUtility(object):

        data = None

        def getId(self, obj):
            for k, v in self.data.items():
                if obj == v:
                    return k

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

    def test_ctor(self):
        storage = IntidContainedStorage(family64)
        assert_that(storage, has_property('family', is_(family64)))
        
        intids = fudge.Fake().has_attr(family=family64)
        component.getGlobalSiteManager().registerUtility(intids, IIntIds)

        storage = IntidContainedStorage()
        assert_that(storage, has_property('family', is_(family64)))

        component.getGlobalSiteManager().unregisterUtility(intids, IIntIds)
    
    def test_len(self):
        storage = IntidContainedStorage(family64)
        storage._containers['cid'] = 100
        assert_that(storage, has_length(1))

    def test_storage(self):
        storage = self.storage
        containers = self.storage  # the facade stays in sync
        assert_that(storage._get_container_mod_time('b'), is_(0))

        def assert_len(i):
            assert_that(storage, has_length(i))
            assert_that(containers, has_length(i))

        assert_len(0)
        storage.addContainedObjectToContainer(self.utility.data[1])
        assert_len(1)
        storage.addContainedObjectToContainer(self.utility.data[2], 'b')
        assert_len(2)
        assert_that(list(storage), has_length(2))

        assert_that(storage._get_intid_for_object_from_utility(self.utility.data[2]),
                    is_(2))

        assert_that(storage._get_container_mod_time('b'), is_not(0))

        assert_that(storage.containers,
                    is_(_LengthIntidResolvingMappingFacade))

        # As it is the length of the containers, removing from a container doesn't
        # change anything
        storage.deleteEqualContainedObjectFromContainer(self.utility.data[1])
        assert_len(2)

        storage.deleteEqualContainedObjectFromContainer(self.utility.data[2],
                                                        'b')
        assert_len(2)

        storage.popContainer('')
        assert_len(1)

        c = Contained()
        c.containerId = 'b'
        # pylint: disable=unsupported-assignment-operation
        self.utility.data[100] = c
        storage.addContainedObject(c)
        container = storage.getContainer('b')
        assert_that(container, has_length(1))
        storage.deleteEqualContainedObject(c)
        assert_that(container, has_length(0))

        for func in (storage.keys, storage.values, storage.items):
            assert_that(list(func()), has_length(1))
        assert_that('b', is_in(storage))

        storage.popContainer('b')
        assert_len(0)

        assert_that(storage.popContainer('b', ()), is_(()))
        with self.assertRaises(KeyError):
            storage.popContainer('b')

        whence = object()
        assert_that(storage._get_intid_for_object(None, whence), is_(whence))
        
    def test_coverage(self):
        intids = fudge.Fake().provides('getId').returns(10)
        component.getGlobalSiteManager().registerUtility(intids, IIntIds)

        storage = IntidContainedStorage(family64)  
        assert_that(storage._get_intid_for_object_from_utility(object()),
                    is_(10))

        component.getGlobalSiteManager().unregisterUtility(intids, IIntIds)
