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


class TestWritePolicyFlow(CBQAMixin, unittest.TestCase):
    """
    Test Write Cache Policy Flow
    """

    def setUp(self):
        super(TestWritePolicyFlow, self).setUp()

        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.pv_ra = get_devra(self.primary_volume)
        self.sv_ra = get_devra(self.ssd_volume)
        set_devra(self.primary_volume, 0, tc=self)
        set_devra(self.ssd_volume, 0, tc=self)


    def tearDown(self):
        super(TestWritePolicyFlow, self).tearDown()
        set_devra(self.primary_volume, self.pv_ra, tc=self)
        set_devra(self.ssd_volume, self.sv_ra, tc=self)

    def call_writearound(self):
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self, \
                    write_policy='write-around', mode = "monitor")
        attrs = getattrs(self.primary_volume)
        numregions = int(attrs['numregions'])
        regionsize = int(attrs['regionsize'])
        sbattrs = getsb(self.ssd_volume)
        cachesize = int(sbattrs['ssdcachesize'])
        testregioncnt = (cachesize / regionsize) >> 1
        if testregioncnt > numregions:
            testregioncnt = numregions
        count = regionsize * testregioncnt / 4096
        drop_caches(tc=self)

        for region in xrange(0, testregioncnt):
            accelerateregion(self, self.primary_volume, region)
            getadmissionbitmap(self.primary_volume)
        #
        # As the regions won't be valid, we should see only 
        # write disk flow 
        #
        rc = lmddwrite(self.primary_volume, 4096, count, 0)
        self.assertEqual(rc, 0)
        #
        # As the writes are asynchronous, try atleast 5 times till
        # the stats gets updated, else raise exception
        #
        for i in xrange(1, 7):
            try:
                self.flush()
                stats = getxstats(self.primary_volume)
                self.assertTrue(stats.get('cs_writedisk_flow') > 0)
                break
            except:
                if i > 5:
                    raise
                else:
                    time.sleep(i)
                    continue

        drop_caches(tc=self)
        #
        # Disk read will lead to read populate and hence marking the  
        # regions as valid.
        #
        rc = lmdd_checkpattern(self.primary_volume, 4096, count, 0)
        self.flush()
        self.assertEqual(rc, 0)
        stats = getxstats(self.primary_volume)
        logger.debug( 'cs_readpopulate_flow=%s, cs_partialio=%d' % (
                stats.get('cs_readpopulate_flow'),
                stats.get('cs_partialio')))
        self.assertTrue(stats.get('cs_readpopulate_flow') >= (count))

        drop_caches(tc=self)
        #
        # Disk read will now lead to read cache flow.
        #
        rc = lmdd_checkpattern(self.primary_volume, 4096, count, 0)
        self.assertEqual(rc, 0)
        self.flush()
        stats = getxstats(self.primary_volume)
        logger.debug( 'cs_readcache_flow=%s, cs_partialio=%d' % (
                stats.get('cs_readcache_flow'),
                stats.get('cs_partialio')))
        self.assertTrue(stats.get('cs_readcache_flow') > 0)
        #
        # Now writing on disk will cause write around flow as the
        # regions are now marked valid. 
        #
        rc = lmddwrite(self.primary_volume, 4096, count, 0)
        self.assertEqual(rc, 0)
        #
        # As the writes are asynchronous, try atleast 5 times till
        # the stats gets updated, else raise exception
        #
        for i in xrange(1, 7):
            try:
                stats = getxstats(self.primary_volume)
                logger.debug( 'cs_writethrough_flow=%s, cs_partialio=%d' % (
                        stats.get('cs_writethrough_flow'),
                        stats.get('cs_partialio')))
                self.assertTrue(stats.get('cs_writethrough_flow') > 0)
                break
            except:
                if i > 5:
                    raise
                else:
                    time.sleep(i)
                    continue
        #
        # Now reading from disk will cause read cache flow as the
        # regions have been updated during write around flow.
        #
        rc = lmdd_checkpattern(self.primary_volume, 4096, count, 0)
        self.assertEqual(rc, 0)
        stats = getxstats(self.primary_volume)
        logger.debug( 'cs_readcache_flow=%s, cs_partialio=%d cs_readpopulate_low=%d' % (
                stats.get('cs_readcache_flow'),
                stats.get('cs_partialio'),
                stats.get('cs_readpopulate_flow')))
        self.assertTrue(stats.get('cs_readcache_flow') >= count)
        self.assertTrue(stats.get('cs_readpopulate_flow') < (2 * count))

        deaccelerate_dev(self.primary_volume, tc=self)


    def call_changepolicy(self):
          accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self, \
                        write_policy='write-around', mode = "monitor")
          attrs = getattrs(self.primary_volume)
          logger.debug(attrs)
          numregions = int(attrs['numregions'])
          regionsize = int(attrs['regionsize'])
          sbattrs = getsb(self.ssd_volume)
          cachesize = int(sbattrs['ssdcachesize'])
          logger.debug( "ssdcachesize=%s regionsize=%s numregions=%s" %(
            cachesize, regionsize, numregions))
          testregioncnt = (cachesize / regionsize) >> 1
          if  testregioncnt > numregions:
              testregioncnt = numregions
          logger.debug( "testregioncnt = %s" %(testregioncnt))
          count = regionsize * testregioncnt / 4096
          logger.debug( "count = %s" %(count))
          drop_caches(tc=self)
          for region in xrange(0, testregioncnt):
              accelerateregion(self, self.primary_volume, region)
          #
          # As the regions won't be valid, we should see only 
          # write disk flow 
          #
          rc = lmddwrite(self.primary_volume, 4096, count, 0)
          self.assertEqual(rc, 0)
          drop_caches(tc=self)
          #
          # As the writes are asynchronous, try atleast 5 times till
          # the stats gets updated, else raise exception
          #
          for i in xrange(1, 7):
            try:
                stats = getxstats(self.primary_volume)
                logger.debug( 'cs_writedisk_flow=%s, cs_writethrough_flow=%d, cs_partialio=%s, cs_writearound_flow=%s' % (
                        stats.get('cs_writedisk_flow'),
                        stats.get('cs_writethrough_flow'),
                        stats.get('cs_partialio'),
                        stats.get('cs_writearound_flow')))
                self.assertTrue(stats.get('cs_writedisk_flow') > 0)
                self.assertTrue(stats.get('cs_writearound_flow') > 0)
                self.assertTrue(stats.get('cs_writethrough_flow') == 0)
                break
            except:
                if i > 5:
                    raise
                else:
                    time.sleep(i)
                    continue

          drop_caches(tc=self)
          #
          # Disk read will lead to read populate and hence marking the  
          # regions as valid.
          #
          rc = lmdd_checkpattern(self.primary_volume, 4096, count, 0)
          self.assertEqual(rc, 0)
          stats = getxstats(self.primary_volume)
          logger.debug( 'cs_readpopulate_flow=%s, cs_partialio=%d' % (
                    stats.get('cs_readpopulate_flow'),
                    stats.get('cs_partialio')))
          self.assertTrue(stats.get('cs_readpopulate_flow') >= (count))

          drop_caches(tc=self)
          #
          # Now writing on disk will cause write around flow as the
          # regions are now marked valid. 
          #
          rc = lmddwrite(self.primary_volume, 4096, count, 0)
          self.assertEqual(rc, 0)
          #
          # As the writes are asynchronous, try atleast 5 times till
          # the stats gets updated, else raise exception
          #
          for i in xrange(1, 7):
            try:
                stats = getxstats(self.primary_volume)
                logger.debug( 'cs_writearound_flow=%s, cs_writethrough_flow=%d' % (
                        stats.get('cs_writearound_flow'),
                        stats.get('cs_writethrough_flow')))
                self.assertTrue(stats.get('cs_writethrough_flow') > 0)
                break
            except:
                if i > 5:
                    raise
                else:
                    time.sleep(i)
                    continue

          rc = change_write_policy(self.primary_volume, "write-through")
          self.assertEqual(rc, 0)

          drop_caches(tc=self)
          #
          # After the policy change writing on disk will cause only
          # write through flow as the regions are now marked valid and
          #
          #
          rc = lmddwrite(self.primary_volume, 4096, count, 0)
          self.assertEqual(rc, 0)
          #
          # As the writes are asynchronous, try atleast 5 times till
          # the stats gets updated, else raise exception
          #
          for i in xrange(1, 7):
            try:
                stats = getxstats(self.primary_volume)
                logger.debug( 'cs_writearound_flow=%s, cs_writethrough_flow=%d' % (
                        stats.get('cs_writearound_flow'),
                        stats.get('cs_writethrough_flow')))
                self.assertTrue(stats.get('cs_writethrough_flow') > 0)
                break
            except:
                if i > 5:
                    raise
                else:
                    time.sleep(i)
                    continue

          deaccelerate_dev(self.primary_volume, tc=self)

    def test_1(self):
         self.call_writearound()
         do_pass(self, 'test_writearound', 1)

    def test_2(self):
        do_skip(self, "policy change is not supported")
        do_pass(self, 'test_policychange', 1)

if __name__ == '__main__':
    unittest.main(argv=["writepolicy.py"] + args)
