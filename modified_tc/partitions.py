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

class TestMisalignedPartition(CBQAMixin, unittest.TestCase):
    """
    Test Misaligned Partition of disk and ssd.
    """
    #
    # To run this test case you need to make two partitions of ssd one
    # is misaligned and other is aligned.  and write that partitions
    # name on config.py ssd array in sequence where first one aligned
    # and second one is misaligned.
    #

    def test_misaligned_partition(self):

        self.pv1 = random.choice(PRIMARY_VOLUMES)
        self.sv1 = random.choice(SSD_VOLUMES.keys())

        if len(SSD_VOLUMES[self.sv1]) < 2:
            do_skip(self, "need atleast two ssds")
            return

        self.primary_volume = [self.pv1, SSD_VOLUMES[self.sv1][1], self.pv1]
        self.ssd_volume = [SSD_VOLUMES[self.sv1][1], self.pv1, SSD_VOLUMES[self.sv1][0]]

        #
        # If ssd partition is misaligned then return 1
        #

        cmd = [
            "cbfmt",
            "-d",
            "%s" % self.primary_volume[0],
            "-s",
            "%s" % self.ssd_volume[0]
        ]
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, err = r.communicate()
        do_pass(self, 'test_misaligned_partition:1a', r.returncode == 0)

        #
        # If disk partition is misaligned then return 1
        #

        cmd = [
            "cbfmt",
            "-d",
            "%s" % self.primary_volume[1],
            "-s",
            "%s" % self.ssd_volume[1]
        ]
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, err = r.communicate()

        #
        # If disk partition and ssd partition both are aligned then
        # only return 0
        #

        do_pass(self, 'test_misaligned_partition:1b', r.returncode == 0)
        cmd = [
            "cbfmt",
            "-d",
            "%s" % self.primary_volume[2],
            "-s",
            "%s" % self.ssd_volume[2]
        ]
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, err = r.communicate()
        do_pass(self, 'test_misaligned_partition:1c', r.returncode == 0)


class TestOddSizedHDDSSD(CBQAMixin, unittest.TestCase):
    """
    Test HDD and SSD whose sizes are not multiple of cachebox region
    size.
    """

    def setUp(self):
        super(TestOddSizedHDDSSD, self).setUp()
        # The ssd and hdd sizes are specified in MB and bs in bytes
        # oddsize attributes to ssd and hdd sizes not multiple of 
        # region size (64K)
        create_devices(ssdsz=110, pvolsz=200, bs=4096, oddsize=1, tc=self)

    def tearDown(self):
        super(TestOddSizedHDDSSD, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)


    def test_block_sizes(self):
        for s in range(12,13):
            bsize = 1 << s
            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)
            dolmdd(of = self.primary_volume, bs = "4k", opat = "1")
            drop_caches(tc=self)
            r = lmdd_checkpattern(self.primary_volume, 4096, 0, 0)
            do_pass(self, 'test_block_sizes:%s' % bsize, r == 0)

            stats = getxstats(self.primary_volume)

            deaccelerate_dev(self.primary_volume, tc=self)

if __name__ == '__main__':
    unittest.main(argv=["partitions.py"] + args)
