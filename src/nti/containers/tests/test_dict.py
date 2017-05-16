#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that
from hamcrest import greater_than

from nose.tools import assert_raises

from nti.testing.matchers import is_true
from nti.testing.matchers import is_false

import unittest

from zope.container import contained

from nti.containers import dicts

from nti.containers.tests import SharedConfiguringTestLayer


class TestDict(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_lastModified_dict(self):

        c = dicts.LastModifiedDict()

        assert_that(c.lastModified, is_(0))

        c[u'k'] = contained.Contained()

        assert_that(c.lastModified, 
					is_(greater_than(0)),
    				"__setitem__ should change lastModified")
        # reset
        c.lastModified = 0
        assert_that(c.lastModified, is_(0))

        del c[u'k']

        assert_that(c.lastModified, 
					is_(greater_than(0)),
                    "__delitem__ should change lastModified")

        # reset
        c.lastModified = 0
        assert_that(c.lastModified, is_(0))

        c[u'k'] = 1
        c.lastModified = 0
        c.pop('missing key', None)
        assert_that(c.lastModified, is_(0))
        c.pop('k')

        assert_that(c.lastModified, 
					is_(greater_than(0)),
                    "__delitem__ should change lastModified")

        with assert_raises(KeyError):
            c.pop('k')

        c.lastModified = 0
        assert_that(c.lastModified, is_(0))

        c.clear()
        assert_that(c.lastModified, is_(0))

        c[u'k'] = 1
        c.lastModified = 0
        c.clear()
        assert_that(c.lastModified, 
					is_(greater_than(0)),
                    "full clear should change lastModified")

        # coverage
        c.updateLastModIfGreater(c.lastModified + 100)

    def test_case_insensitive_dict(self):
        c = dicts.CaseInsensitiveLastModifiedDict()

        child = contained.Contained()
        c[u'UPPER'] = child

        assert_that(c.__contains__(None), is_false())
        assert_that(c.__contains__('UPPER'), is_true())
        assert_that(c.__contains__('upper'), is_true())

        assert_that(c.__getitem__('UPPER'), is_(child))
        assert_that(c.__getitem__('upper'), is_(child))

        assert_that(c.get('UPPER'), is_(child))
        assert_that(c.get('upper'), is_(child))

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

        del c[u'upper']
