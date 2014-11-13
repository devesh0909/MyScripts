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

class TestRUH(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestRUH, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.wfile = "%stest_wfile" % tmpdir
        self.rfile = "%stest_rfile" % tmpdir

    def tearDown(self):
        super(TestRUH, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_tmpfile(self.wfile, tc=self)
        del_tmpfile(self.rfile, tc=self)

    def read_super(self, f):
        drop_caches(self)
        buf = readsuper(f)
        return buf

    def read_ruh(self, f, sb, ruindex):
        drop_caches(self)
        buf = readruheader(f, sb, ruindex)
        return buf

    def read_from_disk(self, offset, size = 4096):
        fd = os.open(self.primary_volume, os.O_RDONLY)
        os.lseek(fd, offset, os.SEEK_SET)
        buf = os.read(fd, size)
        os.close(fd)
        return buf

    def func_fill(self, fd, offset, buf, size):
        assert offset >= 0
        assert offset == (offset & ~(size - 1))
        os.lseek(fd, offset, os.SEEK_SET)
        os.write(fd, buf)

    def write_pattern(self, pattern, offset, size = 4096):
        fd =  os.open(self.primary_volume, os.O_RDWR)
        buf = ('%s' % pattern) * size
        self.func_fill(fd, offset, buf, size)
        os.fsync(fd)
        os.close(fd)

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
        # 2. Mark first region for acceleration
        # 3. Write data on HDD offset zero
        # 4. Read next three 4k buffers
        # 5. Again write next 2 4k buffers onto the HDD
        # 6. Take a checkpoint - this will flush the ru buffer 
        #    onto the SSD
        # 7. Read the ru header and assert that the HDD sector to
        #    SSD sector is valid
        # 8. Assert that there are holes or zeroed ssd and hdd sectors
        # 9. letgo of the device
        #

        bsize = 4096

        self.accelerate(mode = "monitor")
        accelerateregion(self, self.primary_volume, 0)
        flushadmitmap(self, self.primary_volume)

        # write
        offset = 0
        self.write_pattern('a', offset)

        # read
        offset += bsize
        self.read_from_disk(offset)
        offset += bsize
        self.read_from_disk(offset)

        # write
        offset += bsize
        self.write_pattern('a', offset)
        offset += bsize
        self.write_pattern('a', offset)
        offset += bsize
        self.write_pattern('a', offset)
        drop_caches(self)

        xstats = self.getxstats()

        self.assertEqual(int(xstats.get('cs_writecache_flow')), 4)

        self.take_checkpoint()

        fd = os.open(self.ssd_volume, os.O_RDONLY)
        buf = self.read_super(fd)
        sb = cast(buf, POINTER(cb_superblock)).contents
        ruheader = self.read_ruh(fd, sb, 0)
        n = sb.csb_blocksperebs
        ruh = cast(ruheader, POINTER(cb_ruheader)).contents
        rmaps = cast(ruheader, POINTER(cb_rmapping * n)).contents

        self.assertEqual(sb.csb_generation, ruh.ruh_generation)

        # write
        offset = 0
        self.assertNotEqual(rmaps[1].rm_ssd, 0)
        self.assertEqual(rmaps[1].rm_hdd, offset >> 9)

        # read
        offset += bsize
        self.assertEqual(rmaps[2].rm_ssd, 0)
        self.assertEqual(rmaps[2].rm_hdd, 0)

        offset += bsize
        self.assertEqual(rmaps[3].rm_ssd, 0)
        self.assertEqual(rmaps[3].rm_hdd, 0)

        # write
        offset += bsize
        self.assertNotEqual(rmaps[4].rm_ssd, 0)
        self.assertEqual(rmaps[4].rm_hdd, offset >> 9)

        offset += bsize
        self.assertNotEqual(rmaps[5].rm_ssd, 0)
        self.assertEqual(rmaps[5].rm_hdd, offset >> 9)

        offset += bsize
        self.assertNotEqual(rmaps[6].rm_ssd, 0)
        self.assertEqual(rmaps[6].rm_hdd, offset >> 9)

        # no write here after
        for i in xrange(7, n):
            self.assertEqual(rmaps[i].rm_ssd, 0)
            self.assertEqual(rmaps[i].rm_hdd, 0)

        os.close(fd)
        self.deaccelerate()

    def test_2(self):

        #
        # 1. Accelerate primary volume with ssd
        # 2. Mark first region for acceleration
        # 3. Write muliple times on the same offset
        # 4. Take a checkpoint - this will flush the ru buffer 
        #    onto the SSD
        # 5. Read the ru header and assert that the HDD sector to
        #    SSD sector is valid. 
        # 6. assert that there are no duplicate hdd offsets (inplace)
        # 6. Assert that there are holes or zeroed ssd and hdd sectors
        # 7. letgo of the device
        #

        bsize = 4096

        self.accelerate(mode = "monitor")
        accelerateregion(self, self.primary_volume, 0)
        flushadmitmap(self, self.primary_volume)

        offset = 0
        self.read_from_disk(offset)

        # write
        offset += bsize

        strlist = list(string.ascii_lowercase)
        for pattern in strlist:
            self.write_pattern(pattern, offset)

        xstats = self.getxstats()
        self.assertEqual(int(xstats.get('cs_writecache_flow')), len(strlist))

        self.take_checkpoint()

        fd = os.open(self.ssd_volume, os.O_RDONLY)
        buf = self.read_super(fd)
        sb = cast(buf, POINTER(cb_superblock)).contents
        ruheader = self.read_ruh(fd, sb, 0)
        n = sb.csb_blocksperebs
        ruh = cast(ruheader, POINTER(cb_ruheader)).contents
        rmaps = cast(ruheader, POINTER(cb_rmapping * n)).contents

        self.assertEqual(sb.csb_generation, ruh.ruh_generation)

        # write
        self.assertNotEqual(rmaps[2].rm_ssd, 0)
        self.assertNotEqual(rmaps[2].rm_hdd, 0)
        self.assertEqual(rmaps[2].rm_hdd, offset >> 9)

        for i in xrange(3, n):
            self.assertEqual(rmaps[i].rm_ssd, 0)
            self.assertEqual(rmaps[i].rm_hdd, 0)

        os.close(fd)
        self.deaccelerate()

    def test_3(self):

        #
        # 1. Accelerate primary volume with ssd
        # 2. Mark first two regions for acceleration
        # 3. Read and write data on alternate offsets
        # 4. Take a checkpoint - this will flush the ru buffer 
        #    onto the SSD
        # 5. Read the ru header and assert that the HDD sector to
        #    SSD sector is valid
        # 6. Assert that there are holes or zeroed ssd and hdd sectors
        # 7. letgo of the device
        #

        bsize = 4096

        self.accelerate(mode = "monitor")
        accelerateregion(self, self.primary_volume, "0,1")
        flushadmitmap(self, self.primary_volume)

        fd = os.open(self.ssd_volume, os.O_RDONLY)
        buf = self.read_super(fd)
        sb = cast(buf, POINTER(cb_superblock)).contents

        offset = 0
        for i in xrange(sb.csb_blocksperebs):
            if i % 2 == 0:
                self.write_pattern('a', offset)
            else:
                self.read_from_disk(offset)
            offset += bsize

        xstats = self.getxstats()
        self.assertEqual(int(xstats.get('cs_writecache_flow')), sb.csb_blocksperebs/ 2)

        self.take_checkpoint()

        ruheader = self.read_ruh(fd, sb, 0)
        n = sb.csb_blocksperebs
        ruh = cast(ruheader, POINTER(cb_ruheader)).contents
        rmaps = cast(ruheader, POINTER(cb_rmapping * n)).contents

        self.assertEqual(sb.csb_generation, ruh.ruh_generation)
        rmaps = rmaps[1:]

        offset = 0
        for i in xrange(len(rmaps)):
            if i % 2 == 0:
                self.assertNotEqual(rmaps[i].rm_ssd, 0)
                self.assertEqual(rmaps[i].rm_hdd, offset >> 9)
            else:
                self.assertEqual(rmaps[i].rm_ssd, 0)
                self.assertEqual(rmaps[i].rm_hdd, 0)
            offset += bsize

        os.close(fd)
        self.deaccelerate()

if __name__ == '__main__':
    unittest.main(argv=["ruh.py"] + args)
