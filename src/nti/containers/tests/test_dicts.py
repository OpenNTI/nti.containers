#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
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

        c['k'] = contained.Contained()

        assert_that(c.lastModified, 
                    is_(greater_than(0)),
                    "__setitem__ should change lastModified")
        # reset
        c.lastModified = 0
        assert_that(c.lastModified, is_(0))

        del c['k']

        assert_that(c.lastModified, 
                    is_(greater_than(0)),
                    "__delitem__ should change lastModified")

        # reset
        c.lastModified = 0
        assert_that(c.lastModified, is_(0))

        c['k'] = 1
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
        c['UPPER'] = child

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

        del c['upper']
        
    def test_minimal_list(self):
        d = dicts.MinimalList()
        d.append('ichigo')
        d.append('aizen')
        assert_that(d, has_length(2))
        assert_that(list(d), is_(['ichigo', 'aizen']))

        d.append('rukia')
        assert_that(d, has_length(3))
        
        d.remove('rukia')
        assert_that(d, has_length(2))
        
        with self.assertRaises(ValueError):
            d.remove('rukia')
        
        d.replace(['aizen', 'ichigo', 'zaraki'])
        assert_that(d, has_length(3))
        assert_that(list(d), is_(['aizen', 'ichigo', 'zaraki']))
        
        d.clear()
        assert_that(d, has_length(0))
        
        d.extend(('ichigo', 'urahara'))
        assert_that(d, has_length(2))

    def test_ordered_dict(self):
        d = dicts.OrderedDict()
        d['foo'] = 'bar'
        assert_that(d, has_length(1))
        d['bar'] = 'baz'
        assert_that(d, has_length(2))
        assert_that(d, has_entry('foo', is_('bar')))
        assert_that(d, has_entry('bar', is_('baz')))

        assert_that(list(d), is_(['foo', 'bar']))
        
        d.update({'bar': 'moo', 'ding': 'dong', 'beep': 'beep'})
        assert_that(d, has_length(4))
        
        assert_that(list(d), is_not(['bar', 'beep', 'ding', 'foo']))
        
        d.updateOrder(('bar', 'beep', 'ding', 'foo'))
        assert_that(list(d.keys()), is_(['bar', 'beep', 'ding', 'foo']))
  
        with self.assertRaises(ValueError):
            d.updateOrder(['bar', 'beep', 'ding'])
            
        with self.assertRaises(ValueError):
            d.updateOrder(['bar', 'beep', 'ding', 'sha', 'foo'])
            
        with self.assertRaises(ValueError):
            d.updateOrder(['bar', 'beep', 'ding', 'sha'])
            
        with self.assertRaises(ValueError):
            d.updateOrder(['bar', 'beep', 'ding', 'ding'])
        
        d.update([['sha', 'zam'], ['ka', 'pow']])
        assert_that(d, has_length(6))
        
        assert_that(d, has_entry('ka', is_('pow')))
        assert_that(list(d.keys()), 
                    is_( ['bar', 'beep', 'ding', 'foo', 'sha', 'ka']))

        d.update(left='hook', right='jab')
        assert_that(d, has_length(8))
        
        assert_that(d, has_entry('left', is_('hook')))
        
        assert_that(d.pop('sha'), is_('zam'))
        assert_that(d.pop('ka'), is_('pow'))
        assert_that(d.pop('left'), is_('hook'))
        assert_that(d.pop('right'), is_('jab'))
        
        assert_that(d, has_length(4))
        assert_that(list(d.keys()), 
                    is_(['bar', 'beep', 'ding', 'foo']))
        
        with self.assertRaises(KeyError):
            d.pop('nonexistent')

        assert_that(d.pop('nonexistent', 42), is_(42))
        assert_that(d, has_length(4))
         
        d.setdefault('newly created', 'value')
        assert_that(d, has_entry('newly created', is_('value')))
        assert_that(d, has_length(5))
        
        del d['newly created']
        
        assert_that(list(d.keys()), is_(['bar', 'beep', 'ding', 'foo']))
        assert_that(list(d.values()), is_(['moo', 'beep', 'dong', 'bar']))
        assert_that(list(d.items()), 
                    is_([('bar', 'moo'), ('beep', 'beep'), ('ding', 'dong'), ('foo', 'bar')]))
        
        i = iter(d)
        assert_that(i, is_not(none()))
        assert_that(d.iterkeys(), is_not(none()))
        assert_that(d.iteritems(), is_not(none()))
        assert_that(d.itervalues(), is_not(none()))

        assert_that(d, has_length(4))
        assert_that(d.popitem(), is_(('bar', 'moo')))

        c = d.copy()
        assert_that(d.items(), is_(c.items()))
        
        d.clear()
        assert_that(d, has_length(0))
        assert_that(list(d.keys()), is_([]))

        assert_that(c.has_key('beep'), is_(True))
        assert_that('BEEP', is_not(is_in(c)))
        
        assert_that(c.get('nonexistent', 'default'), is_('default'))
