#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,too-many-function-args

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import greater_than
from hamcrest import same_instance
does_not = is_not

from nti.testing.matchers import is_true
from nti.testing.matchers import is_false
from nti.testing.matchers import validly_provides

import six
import time
import fudge
import unittest

import BTrees

from Acquisition import Implicit

from ExtensionClass import Base

from zope import interface
from zope import lifecycleevent

from zope.component.eventtesting import getEvents
from zope.component.eventtesting import clearEvents

from zope.container.contained import Contained as ZContained

from zope.container.interfaces import INameChooser

from zope.dottedname import resolve as dottedname

from zope.location.interfaces import ILocation
from zope.location.interfaces import IContained

from nti.base.interfaces import ILastModified

from nti.containers.containers import _IdGenerationMixin
from nti.containers.containers import _CaseInsensitiveKey
from nti.containers.containers import _CheckObjectOnSetMixin
from nti.containers.containers import IdGeneratorNameChooser
from nti.containers.containers import ExhaustedUniqueIdsError
from nti.containers.containers import AcquireObjectsOnReadMixin
from nti.containers.containers import LastModifiedBTreeContainer
from nti.containers.containers import AbstractNTIIDSafeNameChooser
from nti.containers.containers import EventlessLastModifiedBTreeContainer
from nti.containers.containers import CaseSensitiveLastModifiedBTreeFolder
from nti.containers.containers import NOOwnershipLastModifiedBTreeContainer
from nti.containers.containers import CaseInsensitiveLastModifiedBTreeContainer

from nti.dublincore.datastructures import CreatedModDateTrackingObject

from nti.ntiids.ntiids import ImpossibleToMakeSpecificPartSafe

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

        assert_that(name_chooser.chooseName(None, Contained()),
                    is_('Contained'))

        # initial names
        c['foo.jpg'] = Contained()
        c['baz'] = Contained()

        # bad chars are stripped, and the result is unicode
        name = name_chooser.chooseName(b'+@hah/bah', None)
        assert_that(name, is_(six.text_type))
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

        c.clear()
        assert_that(c, has_length(0))

    def test_exhausted(self):
        tree = fudge.Fake().provides('has_key').returns(True)
        container = _IdGenerationMixin()
        container._SampleContainer__data = tree
        with self.assertRaises(ExhaustedUniqueIdsError):
            container.generateId()

    def test_abstract_name_chooser(self):
        obj = Contained()
        container = LastModifiedBTreeContainer()
        chooser = AbstractNTIIDSafeNameChooser(container)
        chooser.leaf_iface = IContained
        assert_that(chooser.chooseName('x', obj), is_('x'))
        assert_that(chooser.chooseName(u'いちご', obj), is_('ichigo'))
        chooser.slugify = False
        with self.assertRaises(ImpossibleToMakeSpecificPartSafe):
            chooser.chooseName(u'いちご', obj)

        # pylint: disable=inherit-non-class
        class IFake(interface.Interface):
            title = interface.Attribute("fake")
        chooser.leaf_iface = IFake
        with self.assertRaises(ImpossibleToMakeSpecificPartSafe) as e:
            chooser.chooseName(u'いちご', obj)
        assert_that(e.exception,
                    has_property('field', is_(interface.Attribute)))

    def test_check_lm_container(self):
        class C(_CheckObjectOnSetMixin,
                LastModifiedBTreeContainer):
            pass
        c = C()
        c['ichigo'] = Contained()
        c['aizen'] = Contained()
        c.updateLastMod(time.time() + 100)
        assert_that(c.maxKey(), is_('ichigo'))
        assert_that(c.minKey(), is_('aizen'))
        # delete w/ event
        c._delitemf('aizen')
        assert_that(c, has_length(1))
        for func in (c.itervalues, c.iterkeys, c.iteritems):
            assert_that(list(func()), has_length(1))
            assert_that(list(func('zaraki', 'zaraki')), has_length(0))

        # clear
        c.clear()
        assert_that(c, has_length(0))
        # no effect
        c.clear()
        assert_that(c, has_length(0))

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
        assert_that(c.get(None), is_(none()))

        c['mykey'] = child
        assert_that(c._delitemf('mykey'), is_(child))
        assert_that(c, has_length(0))

        c.clear()
        c['mykey'] = child
        assert_that(list(c.iterkeys()), has_length(1))
        assert_that(list(c.iterkeys('a', 'a')), has_length(0))

        c['otherkey'] = 2
        assert_that(list(c.sublocations()), has_length(1))

        key = _CaseInsensitiveKey('UPPER')
        assert_that(hash(key), is_(hash('upper')))

        assert_that(key.__gt__(_CaseInsensitiveKey('z')),
                    is_(False))

    def test_case_insensitive_container_invalid_keys(self):
        c = CaseInsensitiveLastModifiedBTreeContainer()
        with self.assertRaises(TypeError):
            c.get({})
        with self.assertRaises(TypeError):
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
        with self.assertRaises(KeyError):
            c['key'] = value2

        # We cannot add None values or non-unicode keys
        with self.assertRaises(TypeError):
            c['key2'] = None

        with self.assertRaises(TypeError):
            c[None] = value

        with self.assertRaises(TypeError):
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

        c['key'] = value
        assert_that(c.pop('key', None), is_(value))
        assert_that(c.pop('key', None), is_(none()))

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
        with self.assertRaises(KeyError):
            c['key'] = value2

        with self.assertRaises(TypeError):
            c[None] = value

        with self.assertRaises(TypeError):
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

        @interface.implementer(ILocation)
        class Loc(object):
            __parent__ = None
            __name__ = None
        l = Loc()
        l.__parent__ = c
        l.__name__ = 'key2'
        c['key2'] = l
        c['key2'] = c['key2']

        with self.assertRaises(ValueError):
            c[''] = Loc()
        # clear container
        clearEvents()
        c.clear()
        assert_that(getEvents(), has_length(4))

        c['key'] = object()
        clearEvents()
        c.clear(False)
        assert_that(getEvents(), has_length(0))

        class Broken(object):
            def __init__(self, state=True):
                if state:
                    self.__Broken_state__ = {'__name__': 'key',
                                             '__parent__': c}

        c.clear()
        clearEvents()

        # test broke objs
        broken = Broken()
        c._setitemf('key', broken)
        del c['key']
        assert_that(getEvents(), has_length(2))
        assert_that(c, has_length(0))

        clearEvents()
        broken = Broken(False)
        c._setitemf('key', broken)
        with self.assertRaises(AttributeError):
            del c['key']

        clearEvents()
        c.clear()
        c._setitemf('key', broken)

        module = dottedname.resolve('nti.containers.contained')
        module.__dict__['fixing_up'] = True
        with self.assertRaises(AttributeError):
            del c['key']
        module.__dict__['fixing_up'] = False

    def test_case_sensitive_last_modified_btree_folder(self):
        c = CaseSensitiveLastModifiedBTreeFolder()
        c['key'] = Contained()
        c['KEY'] = Contained()
        assert_that(list(c.sublocations()), has_length(2))

    def test_aquire(self):
        class C(Implicit,
                AcquireObjectsOnReadMixin,
                CaseInsensitiveLastModifiedBTreeContainer):
            pass

        class I(Implicit):
            pass

        class P(Base,
                Contained):
            pass

        c_parent = P()
        
        c = C()
        c.__parent__ = c_parent

        c['key'] = I()
        
        assert_that(c.get('key'), is_(I))
        assert_that(c.__getitem__('key'), is_(I))

        assert_that(c.get('key').__parent__.__parent__, is_(c_parent))

        alternate_parent = P()
        c = c.__of__(alternate_parent)

        assert_that(c.get('key').__parent__.__parent__, is_(alternate_parent))
