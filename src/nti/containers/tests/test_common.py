#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import assert_that
from hamcrest import has_property

import unittest

from nti.containers.common import discard
from nti.containers.common import discard_p


class TestCommon(unittest.TestCase):

    def test_discard(self):
        s = {1, 2, 3}
        discard(s, 3)
        assert_that(s, is_({1, 2}))

        class FakeSet(object):

            def __init__(self):
                self.s = {1, 2, 3}

            def remove(self, e):
                self.s.remove(e)

        fs = FakeSet()
        discard(fs, 3)
        assert_that(fs,
                    has_property('s', is_({1, 2})))

        discard(fs, 4)

    def test_discard_p(self):

        class FakeSet(object):

            def __init__(self):
                self.s = {1, 2, 3}

            def remove(self, e):
                self.s.remove(e)

        fs = FakeSet()
        assert_that(discard_p(fs, 3), is_(True))
        assert_that(fs,
                    has_property('s', is_({1, 2})))

        assert_that(discard_p(fs, 4), is_(False))
