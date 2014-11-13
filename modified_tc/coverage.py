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

import os
import random
import subprocess
import sys
import threading
import time
import unittest

from common_utils import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

class TestCoverage(CBQAMixin, unittest.TestCase):
    """
    Test whether the various code paths are being exercised.
    """

    def setUp(self):
        super(TestCoverage, self).setUp()

        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(TestCoverage, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)
        if is_mounted("%stest" % mountdir):
            do_unmount("%stest" % mountdir, self)


    def test_1(self):
        pv_ra = get_devra(self.primary_volume)
        sv_ra = get_devra(self.ssd_volume)
        set_devra(self.primary_volume, 0, tc=self)
        set_devra(self.ssd_volume, 0, tc=self)

        for s in cbqaconfig['TEST_BSIZES']:
            bsize = 1 << s
            resetcoverage(tc=self) 

            dev_blksz = get_devblksz(self.primary_volume)
            if bsize > dev_blksz:
                do_skip(self, "%s" % (bsize))
                continue

            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)
            # pass 1: populate the cache.
            accelerateregion(self, self.primary_volume, 0)
            flushadmitmap(self, self.primary_volume)

            count = int(dev_blksz)/bsize
            drop_caches(tc=self)
            r = dodd(inf = self.primary_volume, of = "/dev/null", bs = bsize, count = count)
            self.assertEqual(r, 0)
            stats = getxstats(self.primary_volume)

            self.assertEqual(stats['cs_readpopulate_flow'], count)
            self.assertEqual(stats['cs_readcache_flow'], 0)
            self.assertEqual(stats['cs_read_miss'], count)
            self.assertEqual(stats['cs_reads'], count)

            # pass 2: read again - this time forcing readcache flow.

            drop_caches(tc=self)
            r = dodd(inf = self.primary_volume, of = "/dev/null", bs = bsize, count = count)
            self.assertEqual(r, 0)
            stats = getxstats(self.primary_volume)

            self.assertEqual(stats['cs_readpopulate_flow'], count)
            self.assertEqual(stats['cs_readcache_flow'], count)
            self.assertEqual(stats['cs_read_hits'], count)
            self.assertEqual(stats['cs_read_miss'], count)
            self.assertEqual(stats['cs_reads'], 2*count)

            cover = getcoverage(tc=self)
            self.assertFalse('#cb_readpopulate1' in cover, "cb_readpopulate1 not covered") 
            self.assertFalse('#cb_readpopulate3' in cover, "cb_readpopulate3 not covered") 
            deaccelerate_dev(self.primary_volume, tc=self)
        set_devra(self.primary_volume, pv_ra, tc=self)
        set_devra(self.ssd_volume, sv_ra, tc=self)


    def test_2(self):
        for s in cbqaconfig['TEST_BSIZES']:
            bsize = 1 << s
            dev_blksz = get_devblksz(self.primary_volume)
            if bsize > dev_blksz:
                do_skip(self, '%s' % bsize)
                continue


            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)

            accelerateregion(self, self.primary_volume, 0)
            flushadmitmap(self, self.primary_volume)
            do_mkfs(self.primary_volume, bsize, tc=self)
            do_mkdir("%stest" % mountdir, tc=self)
            do_mount(self.primary_volume, "%stest/" % mountdir, tc=self)

            stats = getxstats(self.primary_volume)
            self.assertNotEqual(stats['cs_partialio'], 0)

            do_unmount("%stest/" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)

    def _test_3(self):
        # TBD: move these enospace tests to a different module, darn
        # thing takes forever to complete.
        rmax = 10
        rthreshold = 10 

        for s in cbqaconfig['TEST_BSIZES']:
            bsize = 1 << s
            dev_blksz = get_devblksz(self.primary_volume)
            if bsize > dev_blksz:
                do_skip(self, '%s' % bsize)
                continue

            resetcoverage(tc=self)
            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)
            drop_caches(tc=self)

            reclaimioctl(self.primary_volume, rmax, rthreshold)

            ssdsz= get_devsz(self.ssd_volume)
            count = (int(ssdsz)*512)/bsize


            drop_caches(tc=self)
            for i in range (1, 5):
               r = dolmdd(inf = self.primary_volume, bs = bsize, count = str(10*count), skip = str(i*count))
               self.assertEqual(r, 0)
               reclaimioctl(self.primary_volume, rmax, rthreshold)
               drop_caches(tc=self)

            stats = getxstats(self.primary_volume)
            self.assertNotEqual(int(stats['cs_readdisk_flow']), 0)
            self.assertNotEqual(int(stats['cs_enospace']), 0)

            cover = getcoverage(tc=self)
            self.assertFalse('#cb_readpopulate2' in cover) 
            self.assertTrue((stats.get('cs_readdisk_flow') != 0) or (cover.index('#cb_get_offset1') != -1)) 
            self.assertFalse('#cb_reclaim_flush1' in cover) 

            deaccelerate_dev(self.primary_volume, tc=self)

    def test_4(self):
        for s in cbqaconfig['TEST_BSIZES']:
            bsize = 1 << s
            dev_blksz = get_devblksz(self.primary_volume)
            if bsize > dev_blksz:
                do_skip(self, '%s' % bsize)
                continue
            resetcoverage(tc=self)
            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)

            drop_caches(tc=self)
            r = dodd(inf = self.primary_volume, of = "/dev/null", bs = bsize, count = "1")
            self.assertEqual(r, 0)
            cover = getcoverage(tc=self)
            if dev_blksz <= bsize:
                self.assertFalse('#cb__clone_and_map1' in cover, "cb__clone_and_map1 not covered") 
            else:
                self.assertFalse('#cb__clone_and_map3' in cover, "cb__clone_and_map1 not covered") 

            deaccelerate_dev(self.primary_volume, tc=self)


class TestNonBsizeBoundryIO(Pre_check, unittest.TestCase):
    """
    Test we are handling IOs falling on non bsize boundry properly. 
    """

    def setUp(self):
        super(TestNonBsizeBoundryIO, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(TestNonBsizeBoundryIO, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_1(self):
        for s in cbqaconfig['TEST_BSIZES']:
            bsize = 1 << s
            dev_blksz = get_devblksz(self.primary_volume)
            if bsize > dev_blksz:
                do_skip(self, '%s' % bsize)
                continue

            resetcoverage(tc=self) 
            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)
            do_mkfs(self.primary_volume, bsize, tc=self)
            do_mkdir("%stest" % mountdir, tc=self)
            do_mount(self.primary_volume, "%stest/" % mountdir, tc=self)

            stats = getxstats(self.primary_volume)
            self.assertNotEqual(int(stats['cs_partialio']), 0)
            cover = getcoverage(tc=self)
            self.assertFalse('#cb_non_bsize_boundry_io' in cover, "cb_non_bsize_boundry_io not covered") 
            cover = getcoverage(tc=self)
            self.assertFalse('#cb_zerosized_io' in cover, "cb_zerosized_io not covered") 
            do_unmount("%stest/" % mountdir, tc=self)

            deaccelerate_dev(self.primary_volume, tc=self)


if __name__ == '__main__':
    unittest.main(argv=["coverage.py"] + args)
