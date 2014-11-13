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
import tempfile
import threading
import time
import unittest

from common_utils import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

WRITE_POLICY = ['write-back', 'write-through']

class TestInvalWraplogic(CBQAMixin, unittest.TestCase):

    """
    Test invalidation and wrap around logic
    """

    def setUp(self):
        super(TestInvalWraplogic, self).setUp()
        create_devices(ssdsz=20, pvolsz=200, bs=4096, oddsize=0, tc=self)
        self.rmax = 16
        self.rthreshold = 12

    def tearDown(self):
        super(TestInvalWraplogic, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_1(self):
        ssdsize = get_devsz(self.ssd_volume)
        for policy in WRITE_POLICY:
            for s in cbqaconfig['TEST_BSIZES']:
                bsize = 1 << s
                self.accelerate(bsize = bsize, write_policy = policy)
                drop_caches(tc=self)
                self.setpolicy()
                reclaimioctl(self.primary_volume, self.rmax, self.rthreshold)
                count = ssdsize / bsize 

                for i in range (1, 15):
                    r = dolmdd(inf = self.primary_volume, bs = bsize, count = str(10*count), skip = str(i*count))
                    self.assertEqual(r, 0)
                    drop_caches(tc=self)

                stats = getxstats(self.primary_volume)
                self.assertNotEqual(int(stats['cs_data_wrap_around']), 0)
                self.assertNotEqual(int(stats['cs_free_wrap_around']), 0)
                self.assertNotEqual(int(stats['cs_readdisk_flow']), 0)
                checkcorrectness(self.primary_volume, bsize, tc = self)
                self.deaccelerate()
                do_pass(self, "Test_reclaim %s for %s" % (bsize, policy))


class TestReclaim(CBQAMixin, unittest.TestCase):
    """
    Test reclaim ioctl to reclaim the EBS when the freespace falls
    below low watermark
    """

    def setUp(self):
        super(TestReclaim, self).setUp()
        create_devices(ssdsz=5, pvolsz=10, bs=4096, oddsize=0, tc=self)
        self.rmax = 2
        self.rthreshold = 3

    def tearDown(self):
        super(TestReclaim, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_1(self):
        for s in range(12,13):
            bsize = 1 << s
            self.accelerate(bsize = bsize)
            self.setpolicy()
            drop_caches(tc=self)

            count = (4 * self.ssdsize)/self.bsize

            r = dodd(inf = self.primary_volume, of = "/dev/null", bs = self.bsize, count = 1)
            do_pass(self, 'test_reclaim:%s' % bsize, r == 0)
            self.deaccelerate()


class ReclaimWithReads(CBQAMixin, unittest.TestCase):
    """
    Reclaim while Reads are ongoing.
    """

    def setUp(self):
        super(ReclaimWithReads, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(ReclaimWithReads, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_1(self):

        reclaim_with_read_loop(devtype='new', tc=self)
        do_pass(self, 'test_reclaim_with_read_loop', 1)

    def test_2(self):

        self.accelerate()
        self.setpolicy()

        threadB = threading.Thread(target = read_loop,
                                  kwargs = {'tc':self,
                                 'pv':self.primary_volume,
                                 'sv':self.ssd_volume})
        threadB.start()
        threadB.join()
        self.deaccelerate()


class ReclaimWithDirtyWrites(CBQAMixin, unittest.TestCase):
    """
    Reclaim with dirty RU.
    """

    def setUp(self):
        super(ReclaimWithDirtyWrites, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(ReclaimWithDirtyWrites, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_1(self):
        self.accelerate()
        self.setpolicy()

        # create a few dirty writes
        self.seq_write(count=1024)
        self.flush()
        self.assertTrue(self.getxstats()['cs_writecache_flow'] > 0)

        # try to reclaim the dirty RUs
        r = self.reclaim()
        self.assertEqual(r, 0)

        self.deaccelerate()

if __name__ == '__main__':
    unittest.main(argv=["reclaim.py"] + args)
