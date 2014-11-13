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
import string
import subprocess
import sys
import time
import unittest

from common_utils import *
from layout import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

WRITE_POLICY = ['write-back', 'write-around', 'write-through', 'read-around']

class TestAdmitMap(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestAdmitMap, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.wfile = "%stest_wfile" % tmpdir
        self.rfile = "%stest_rfile" % tmpdir

    def tearDown(self):
        super(TestAdmitMap, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_tmpfile(self.wfile, tc=self)
        del_tmpfile(self.rfile, tc=self)

    def read_super(self, f):
        drop_caches(self)
        buf = readsuper(f)
        return buf

    def take_checkpoint(self):
        cmd = [
            "./cbtran",
            "-d",
            "%s" % self.primary_volume,
            "-c"
            ]
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = r.communicate()[0]
        assert(r.returncode == 0)

    def test_1(self):

        #
        # 1. Accelerate primary volume with ssd
        # 2. Mark 3rd region for acceleration
        # 3. Take a checkpoint
        # 4. Read the admitmap and assert that the region is 
        #    marked for caching
        # 5. letgo of the device
        #
        for policy in WRITE_POLICY:
            bsize = 4096
            region = 3

            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, self, \
                            write_policy = policy, mode="monitor")
            accelerateregion(self, self.primary_volume, 3)
            flushadmitmap(self, self.primary_volume)

            self.take_checkpoint()

            fd = os.open(self.ssd_volume, os.O_RDONLY)
            buf = self.read_super(fd)
            sb = cast(buf, POINTER(cb_superblock)).contents
            amap_buf = readadmitmap(fd, sb)
            n = roundup((sb.csb_numregions), 64) >> 6
            amaps = cast(amap_buf, POINTER(cb_admitmapentry * n)).contents

            index = region / 64
            r = region & 63
            self.assertEqual(amaps[index].cad_bits, cb_bmaplookup[r])

            os.close(fd)
            self.deaccelerate()

    def test_2(self):
        #
        # 1. Accelerate primary volume with ssd
        # 2. Mark multiple random regions for acceleration
        # 3. Take a checkpoint
        # 4. Read the admitmap and assert that the region is 
        #    marked for caching
        # 5. letgo of the device
        #
        for policy in WRITE_POLICY:
            bsize = 4096
            regions = []

            # for index 0
            amap_bits = range(63)

            for i in xrange(10):
                regions.append(str(random.choice(amap_bits)))

            # for index 2
            amap_bits = range(128, 191)

            for i in xrange(10):
                regions.append(str(random.choice(amap_bits)))

            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, self, \
                            write_policy = policy, mode="monitor")
            accelerateregion(self, self.primary_volume, ",".join(regions))
            flushadmitmap(self, self.primary_volume)

            self.take_checkpoint()

            fd = os.open(self.ssd_volume, os.O_RDONLY)
            buf = self.read_super(fd)
            sb = cast(buf, POINTER(cb_superblock)).contents
            amap_buf = readadmitmap(fd, sb)
            n = roundup((sb.csb_numregions), 64) >> 6
            amaps = cast(amap_buf, POINTER(cb_admitmapentry * n)).contents

            index = 0
            result = 0

            for reg in regions[:10]:
                r = int(reg) & 63
                result |= cb_bmaplookup[r]

            self.assertEqual(amaps[index].cad_bits, result)

            index = 2
            result = 0

            for reg in regions[10:]:
                r = int(reg) & 63
                result |= cb_bmaplookup[r]

            self.assertEqual(amaps[index].cad_bits, result)
            os.close(fd)
            self.deaccelerate()

if __name__ == '__main__':
    unittest.main(argv=["admap.py"] + args)
