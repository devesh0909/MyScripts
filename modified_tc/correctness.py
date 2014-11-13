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


class TestCorrectness(CBQAMixin, unittest.TestCase):
    """
    Test there is no corruption with cb driver in picture.
    """

    def setUp(self):
        super(TestCorrectness, self).setUp()
        create_devices(ssdsz=110, pvolsz=200, bs=4096, oddsize=0, tc=self)
        self.devbsz = get_devblksz(self.primary_volume)
        path=os.getcwd()+"/../tools"
        os.environ['PATH']="%s:%s" % (os.getenv('PATH'), path)

    def tearDown(self):
        super(TestCorrectness, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        set_devblksz(self.primary_volume, self.devbsz, tc=self)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_1(self):
        for s in range(12,13):
            bsize = 1 << s

            do_mkfs(self.primary_volume, bsize, tc=self)
            do_mount(self.primary_volume, "%stest/" % mountdir, tc=self)
            do_mkdir("%stest/trial/" % mountdir, tc=self)

            devsz = get_devsz(self.primary_volume) 

            # Keeping some 110M(225280 sectors) size aside for FS and
            # using remaining size for creating files.

            count = (((devsz - 225280)*512)/bsize)/5
            for i in range(1, 5):
                r = dolmdd(of = "%stest/trial/file%d" % (mountdir, i), bs=bsize, count = count, opat = "1")
                do_pass(self, 'test_block_sizes_correctness:%s' % bsize, r == 0)

            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)

            do_unmount("%stest/" % mountdir, tc=self)
            drop_caches(tc=self)
            do_mount(self.primary_volume, "%stest/" % mountdir, tc=self)


            for i in range(1, 5):
                dev = "%stest/trial/file%d" % (mountdir, i)
                drop_caches(tc=self)
                r = lmdd_checkpattern(dev, bsize, count, 0)
                do_pass(self, 'test_block_sizes_correctness:%s' % bsize, r == 0)

            do_unmount("%stest/" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)

    # The only difference between previous test and this one is the
    # time when we put the device under cachebox.

    def test_2(self):
        for s in range(12,13):
            bsize = 1 << s

            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)

            do_mkfs(self.primary_volume, bsize, tc=self)
            do_mount(self.primary_volume, "%stest/" % mountdir, tc=self)
            do_mkdir("%stest/trial/" % mountdir, tc=self)


            devsz = get_devsz(self.primary_volume) 
            # Keeping some 110M(225280 sectors) size aside for FS and
            # using remaining size for creating files.

            count = (((devsz - 225280)*512)/bsize)/5
            for i in range(1, 5):
                cmd = ["lmdd",
                       "of=%stest/trial/file%d" % (mountdir, i),
                       "opat=1",
                       "bs=%d" % bsize,
                       "count=%d" % count
                       ]
                r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output = r.communicate()[0].rstrip('\n')
                do_pass(self, 'test_block_sizes_correctness2:%s' % bsize, r.returncode == 0)

            drop_caches(tc=self)

            do_unmount("%stest/" % mountdir, tc=self)
            do_mount(self.primary_volume, "%stest/" % mountdir, tc=self)

            for i in range(1, 5):
                dev = "%stest/trial/file%d" % (mountdir, i)
                r = lmdd_checkpattern(dev, bsize, count, 0)
                do_pass(self, 'test_block_sizes_correctness2:%s' % bsize, r == 0)

            do_unmount("%stest/" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)


class TestCorruption(CBQAMixin, unittest.TestCase):
    """
    Test the cb caching to see if there are no corruptions
    """

    def setUp(self):
        super(TestCorruption, self).setUp()

        cmd = "du -m /bin/"
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = r.communicate()[0].rstrip('\n').split('\t')
        binsz = int(output[0])

        cmd = "du -m /sbin/"
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = r.communicate()[0].rstrip('\n').split('\t')
        sbinsz = int(output[0])

        pvolsz = binsz + sbinsz + 520
        bs = 4096
        ssdsz = pvolsz / 5
        create_devices(ssdsz, pvolsz, bs, oddsize=0, tc=self)
        self.devbsz = get_devblksz(self.primary_volume)

    def tearDown(self):
        super(TestCorruption, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)
        if is_mounted("%stest/" % mountdir):
            do_unmount("%stest/" % mountdir, tc=self)
        set_devblksz(self.primary_volume, self.devbsz, tc=self)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_1(self):
        for s in range(12, 13):
            bsize = 1 << s
            dev_blksz = get_devblksz(self.primary_volume)
            if bsize > dev_blksz:
                do_skip(self, 'test_corruption: %s' % bsize)    
                continue

            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)
            do_mkfs(self.primary_volume, bsize, tc=self)
            do_mkdir("%stest" % mountdir, tc=self)
            do_mount(self.primary_volume, "%stest/" % mountdir, tc=self)

            cmd = "cp -r /bin/ %stest/bin/" % mountdir
            r = os.system(cmd)
            do_pass(self, 'test_corruption:0', r == 0)
            cmd = "cp -r /sbin/ %stest/sbin/" % mountdir
            r = os.system(cmd)
            do_unmount("%stest/" % mountdir, tc=self)

            do_mount(self.primary_volume, "%stest/" % mountdir, tc=self)

            for i in range(1, 5):
                drop_caches(tc=self)

            # Avoid symbolic links which can have the relative
            # paths as target

            cmd = "for f in `find /bin/* -type f`;do diff $f %stest${f}; echo %stest${f} ; done" % (mountdir, mountdir)
            r = os.system("%s >/dev/null 2>&1" % cmd)
            do_pass(self, 'test_corruption:1a', r == 0)

            cmd = "for f in `find /sbin/* -type f`;do diff $f %stest${f} ; echo %stest${f}; done" % (mountdir, mountdir)
            r = os.system("%s > /dev/null 2>&1" % cmd)
            do_pass(self, 'test_corruption:1b', r == 0)

            stats = getxstats(self.primary_volume)

            do_unmount("%stest/" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)
            return
            accelerate_existingdev(self.primary_volume, self.ssd_volume, tc=self)
            do_mount(self.primary_volume, "%test/" % mountdir, tc=self)

            for i in range(1, 5):
                drop_caches(tc=self)
            cmd = "for f in `find /bin/* -type f`;do diff $f %stest${f}; echo %stest${f} ; done" % (mountdir, mountdir)
            r = os.system("%s > /dev/null 2>&1" % cmd)
            do_pass(self, 'test_corruption:2a', r == 0)

            cmd = "for f in `find /sbin/* -type f`;do diff $f %stest${f} ; echo %stest${f}; done" % (mountdir, mountdir)
            r = os.system("%s > /dev/null 2>&1" % cmd)
            do_pass(self, 'test_corruption:2b', r == 0)

            stats = getxstats(self.primary_volume)

            do_unmount("%stest/" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)


if __name__ == '__main__':
    unittest.main(argv=["correctness.py"] + args)
