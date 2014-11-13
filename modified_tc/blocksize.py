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

WRITE_POLICY = ['write-back', 'write-through', 'write-around']

class TestBlockSize(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(TestBlockSize, self).setUp()

        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.devbsz = get_devblksz(self.primary_volume)
        do_mkfs(self.primary_volume, "default", tc = self)
        do_mkdir("%stest" % mountdir, tc = self)
        do_mount(self.primary_volume, "%stest/" % mountdir, tc = self)

        cmd = "cp /etc/passwd %stest" % mountdir
        r = os.system(cmd)
        self.assertEqual(r, 0)

        do_unmount("%stest/" % mountdir, tc=self)

    def tearDown(self):
        super(TestBlockSize, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)
        set_devblksz(self.primary_volume, self.devbsz, tc=self)


    def test_1(self):
        for policy in WRITE_POLICY: 
            for s in cbqaconfig['TEST_BSIZES']:
                bsize = 1 << s
                acceleratedev(self.primary_volume, self.ssd_volume, bsize, self, \
                        write_policy = policy)
                deaccelerate_dev(self.primary_volume, tc=self)


    def test_2(self):
        for policy in WRITE_POLICY: 
            for s in cbqaconfig['TEST_BSIZES']:
                bsize = 1 << s
                dev_blksz = get_devblksz(self.primary_volume)
                if bsize > dev_blksz:
                    do_skip(self, 'test_block_sizes:%s' % bsize)
                    continue 

                acceleratedev(self.primary_volume, self.ssd_volume, bsize, self, \
                        write_policy = policy)
                self.setpolicy()
                do_fsck(self.primary_volume, tc=self)
                do_mount(self.primary_volume, "%stest" % mountdir, tc=self)

                cmd = "diff /etc/passwd %stest/passwd" % mountdir
                logger.debug(cmd)
                r = os.system(cmd)
                self.assertEqual(r, 0)
                do_unmount("%stest" % mountdir, tc=self)

                self.deaccelerate()
                do_fsck(self.primary_volume, tc=self)


class TestSupportedBSize(CBQAMixin, unittest.TestCase):

    """
    Check that we are conforming to the block size supoorted by
    underlying device.
    """

    def setUp(self):
        super(TestSupportedBSize, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(TestSupportedBSize, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_1(self):
        for policy in WRITE_POLICY: 
            for s in cbqaconfig['TEST_BSIZES']:
                bsize = 1 << s
                acceleratedev(self.primary_volume, self.ssd_volume, bsize, self, \
                        write_policy = policy)
                attrs = getattrs(self.primary_volume) 
                dev_blksz = get_devblksz(self.primary_volume)
                if bsize > dev_blksz:
                    do_pass(self, 'test_supported_bsize:1a', attrs['bsize'] != dev_blksz)
                deaccelerate_dev(self.primary_volume, tc=self)


if __name__ == '__main__':
    unittest.main(argv=["blocksize.py"] + args)
