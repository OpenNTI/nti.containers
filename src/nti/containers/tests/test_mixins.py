#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that

from nti.testing.matchers import is_true
from nti.testing.matchers import is_false

import unittest

from zope.container.contained import Contained

from nti.containers.mixins import DictMixin


class TestMixins(unittest.TestCase):

    def test_dict_mixin(self):

        class Mappable(DictMixin):
            def __init__(self):
                self.store = dict()

            def __setitem__(self, key, value):
                self.store[key] = value

            def __delitem__(self, key):
                del self.store[key]

            def __getitem__(self, key):
                return self.store[key]

            def keys(self):
                return list(self.store.keys())

        c = Mappable()

        child = Contained()
        c['key'] = child
        assert_that(c.__contains__(None), is_false())
        assert_that(c.__contains__('key'), is_true())

        assert_that(c.__getitem__('key'), is_(child))
        assert_that(c.get('key'), is_(child))
        assert_that(c.get('key2'), is_(none()))

        assert_that(list(iter(c)), is_(['key']))
        assert_that(list(c.iterkeys()), is_(['key']))

        assert_that(list(c.items()), is_([('key', child)]))
        assert_that(list(c.iteritems()), is_([('key', child)]))

        assert_that(list(c.values()), is_([child]))
        assert_that(list(c.itervalues()), is_([child]))

        assert_that(c.has_key('key'), is_(True))
        assert_that(c.has_key('key2'), is_(False))
        del c['key']

        c['key2'] = child
        assert_that(c, has_length(1))
        c['key3'] = child
        assert_that(c, has_length(2))
        c.clear()
        assert_that(c, has_length(0))

        c['key4'] = child
        with self.assertRaises(TypeError):
            c.pop('bar', 'beep', 'ding')
        assert_that(c.pop('key4', None), is_(child))
        assert_that(c.pop('key4', 1), is_(1))
        with self.assertRaises(KeyError):
            c.pop('key4')

        c.setdefault('key5', [])
        assert_that(c, has_entry('key5', is_([])))
        del c['key5']

        c['key6'] = 1
        assert_that(c.popitem(), is_(('key6', 1)))
        with self.assertRaises(KeyError):
            c.popitem()

        c.update(None)
        c.update({'1': '2'})
        c.update(c)
        assert_that(repr(c), is_("{'1': '2'}"))
        c.update((('1','2'),('3','4')), five='6')

