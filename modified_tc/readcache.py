#!/usr/bin/python

#
#  Copyright 2012 Cachebox, Inc. All rights reserved. This software
#  is property of Cachebox, Inc and contains trade secrects,
#  confidential & proprietary information. Use, disclosure or copying
#  this without explicit written permission from Cachebox, Inc is
#  prohibited.
#
#  Author: Cachebox, Inc (sales@cachebox.com)
#

import datetime
import os
import random
import subprocess
import sys
import threading
import time
import unittest

from common_utils import *
from cblog import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)


class TestReadCachePassthrough(CBQAMixin, unittest.TestCase):

    """
    Test read from cache when the disk is pass-through.
    """

    def setUp(self):
        super(TestReadCachePassthrough, self).setUp()

        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)
        super(TestReadCachePassthrough, self).tearDown()

    def test_block_sizes(self):
        for s in cbqaconfig['TEST_BSIZES']:
            bsize = 1 << s
            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)
            sbattrs = getsb(self.ssd_volume)
            cachesize = int(sbattrs['ssdcachesize'])
            count = cachesize / bsize
            r = dolmdd(of = self.primary_volume, bs = bsize, count = count, opat = "1")
            do_pass(self, 'test_block_sizes:1a:%s' % bsize, r == 0)
            drop_caches(tc=self)
            accelerate_allregions(self.primary_volume, tc=self)

            r = lmdd_checkpattern(self.primary_volume, bsize, count, 0)
            do_pass(self, 'test_block_sizes:1b:%s' % bsize, r == 0)
            stats = getxstats(self.primary_volume)
            do_pass(self, 'test_block_sizes:1c:%s' % bsize, stats.get('cs_readpopulate_flow') >= (count))

            drop_caches(tc=self)
            r = lmdd_checkpattern(self.primary_volume, bsize, count, 0)
            do_pass(self, 'test_block_sizes:1d:%s' % bsize, r == 0)

            stats = getxstats(self.primary_volume)
            do_pass(self, 'test_block_sizes:1e:%s' % bsize, stats.get('cs_readcache_flow') >= (count))
            deaccelerate_dev(self.primary_volume, tc=self)

if __name__ == '__main__':
    unittest.main(argv=["readcache.py"] + args)
