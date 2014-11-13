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


class TestWriteInvalidateFlow(CBQAMixin, unittest.TestCase):

    """
    Test Write Invalidate Flow
    """

    def setUp(self):
        super(TestWriteInvalidateFlow, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.pv_ra = get_devra(self.primary_volume)
        self.sv_ra = get_devra(self.ssd_volume)
        set_devra(self.primary_volume, 0, tc=self)
        set_devra(self.ssd_volume, 0, tc=self)


    def tearDown(self):
        super(TestWriteInvalidateFlow, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)
        set_devra(self.primary_volume, self.pv_ra, tc=self)
        set_devra(self.ssd_volume, self.sv_ra, tc=self)

    def call_writeinvalidate(self):
	  self.skipTest("write invalidate test needs to be rewritten")  
          cmd = "echo 90 > /proc/sys/kernel/cachebox/reclaim_flush_interval"
          r = os.system(cmd)
          self.assertEqual(r, 0, "could not set reclaim flush interval")
          accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self)
          attrs = getattrs(self.primary_volume)
          numregions = int(attrs['numregions'])
          regionsize = int(attrs['regionsize'])
          sbattrs = getsb(self.ssd_volume)
          cachesize = int(sbattrs['ssdcachesize'])
          if self.testcovwritethrough1:
            testregioncnt = (cachesize / regionsize)
          else:
            testregioncnt = (cachesize / regionsize) >> 1
          if  testregioncnt > numregions:
            testregioncnt = numregions
          count = regionsize * testregioncnt / 4096
          drop_caches(tc=self)
          rc = lmddwrite(self.primary_volume, 4096, count, 0)
          self.assertEqual(rc, 0) 
          for region in xrange(0, testregioncnt):
            accelerateregion(self, self.primary_volume, region)

          drop_caches(tc=self)
          rc = lmdd_checkpattern(self.primary_volume, 4096, count, 0)
          self.assertEqual(rc, 0) 
          stats = getxstats(self.primary_volume)
          self.assertTrue(stats.get('cs_readpopulate_flow') == count)

          drop_caches(tc=self)
          rc = lmdd_checkpattern(self.primary_volume, 4096, count, 0)
          self.assertEqual(rc, 0) 
          stats = getxstats(self.primary_volume)
          self.assertTrue(stats.get('cs_readcache_flow') == count)

          flush_forward_maps(self.primary_volume, tc=self)
          drop_caches(tc=self)
          rc = lmddwritezero(self.primary_volume, 4096, count, 0)
          self.assertEqual(rc, 0) 
          drop_caches(tc=self)
          stats = getxstats(self.primary_volume)
          self.assertTrue(stats.get('cs_writeinvalidate_flow') >= (count-1))
          self.assertTrue(stats.get('cs_writethrough_flow') >= (count-1))
          cover = getcoverage(tc=self)
          if self.testcovwritethrough1:
            self.assertFalse('#cb_writethrough1' in cover, "cb_writethrough1 not covered") 
          else:
            self.assertFalse('#cb_writethrough2' in cover, "cb_writethrough2 not covered") 
          flush_forward_maps(self.primary_volume, tc=self)
          drop_caches(tc=self)
          if self.event_flush_invalidate:
            cover = getcoverage(tc=self)
            self.assertFalse('#cb_pop_waitfmap' in cover, "cb_pop_waitfmap not covered") 
            cmd = "cat /proc/sys/kernel/cachebox/event_flush_invalidate"
            rc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            val = int(rc.communicate()[0].rstrip('\n'))
            self.assertEqual(val, 0)

          deaccelerate_dev(self.primary_volume, tc=self)
          accelerate_existingdev(self.primary_volume, self.ssd_volume, self)
          rc = lmddcheckzero(self.primary_volume, 4096, count, 0)
          self.assertEqual(rc, 0) 
          drop_caches(tc=self)
          stats = getxstats(self.primary_volume)
          deaccelerate_dev(self.primary_volume, tc=self)


    def test_writeinvalidate(self):
	 do_skip(self, 'test_writeinvalidate')

if __name__ == '__main__':
    unittest.main(argv=["invalidateflow.py"] + args)
