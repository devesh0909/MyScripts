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


class TestWriteThroughFlow(CBQAMixin, unittest.TestCase):

    """
    Test WriteThrough Flow
    """

    def setUp(self):
        super(TestWriteThroughFlow, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.pv_ra = get_devra(self.primary_volume)
        self.sv_ra = get_devra(self.ssd_volume)
        set_devra(self.primary_volume, 0, tc=self)
        set_devra(self.ssd_volume, 0, tc=self)

    def tearDown(self):
        super(TestWriteThroughFlow, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)
        set_devra(self.primary_volume, self.pv_ra, tc=self)
        set_devra(self.ssd_volume, self.sv_ra, tc=self)

    def call_writethrough(self):
          self.skipTest("call_writethrough test needs to be rewritten")
          r = cb_set_tunable("reclaim_flush_interval", 90)
          self.assertEqual(r, 0, "could not set reclaim flush interval")
          accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self)
          attrs = getattrs(self.primary_volume)
          numregions = int(attrs['numregions'])
          regionsize = int(attrs['regionsize'])
          sbattrs = getsb(self.ssd_volume)
          cachesize = int(sbattrs['ssdcachesize'])
          testregioncnt = (cachesize / regionsize) >> 1
          if  testregioncnt > numregions:
              testregioncnt = numregions
          count = regionsize * testregioncnt / 4096
          drop_caches(tc=self)
          for region in xrange(0, testregioncnt):
              accelerateregion(self, self.primary_volume, region)
          rc = lmddwrite(self.primary_volume, 4096, count, 0)
          self.assertEqual(rc, 0)
          #
          # As the writes are asynchronous, try atleast 5 times till
          # the stats gets updated, else raise exception
          #
          for i in xrange(1, 7):
            try:
                stats = getxstats(self.primary_volume)
                self.assertTrue(stats.get('cs_writethrough_flow') == count)
                break
            except:
                if i > 5:
                    raise
                else:
                    time.sleep(i)
                    continue

          if self.event_writethrough_nospace:
            cover = getcoverage(tc=self)
            self.assertFalse('#cb_writethrough1' in cover, "cb_writethrough1 not covered")
            val = cb_get_tunable("event_writethrough_nospace")
            self.assertEqual(val, 0)
          else:
            cover = getcoverage(tc=self)
            self.assertFalse('#cb_writethrough2' in cover, "cb_writethrough2 not covered") 


          drop_caches(tc=self)
          rc = lmdd_checkpattern(self.primary_volume, 4096, count, 0)
          self.assertEqual(rc, 0) 
          stats = getxstats(self.primary_volume)
          if self.event_writethrough_nospace:
              self.assertTrue(stats.get('cs_readcache_flow') >= (count-1))
          else:
              self.assertTrue(stats.get('cs_readcache_flow') >= (count))
          deaccelerate_dev(self.primary_volume, tc=self)

    def test_writethrough(self):
         do_skip(self, 'test_writethrough')

if __name__ == '__main__':
    unittest.main(argv=["writethrough.py"] + args)
