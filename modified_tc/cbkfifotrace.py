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
import datetime

from common_utils import *
from cblog import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)


class TestKfifo(CBQAMixin, unittest.TestCase):
    """
    Test Region Fault Endio
    """

    def setUp(self):
        super(TestKfifo, self).setUp()

        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(TestKfifo, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_kfifo(self):

	# TBD : Turn off the read ahead and restore it back at the end
	# 4K blocks IO count

	# Corresponding to 1MB of data
	blksize=4096
	count=256 

	# Get the start of the primary device 

	start = 0
	dev_name =  self.primary_volume.split('/') [-1]

	# TBD: Need to improve this code for LVM partition lookup
	cmd = "find /sys -name \"start\" | grep -w \"%s/start\" | xargs cat" %(dev_name)
        process_1 = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE)
        out = process_1.communicate()[0]
      	if len(out) != 0:
	   start = int(out)

        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self)
        r = dodd(inf = "/dev/zero", of = self.primary_volume, bs= blksize, count = count, oflag = "direct")
        self.assertEqual(r, 0)

	# Read entries from kernel FIFO
        cmd = "cachebox -t 256 -d %s" % (self.primary_volume)
        process_1 = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE)
        out = process_1.communicate()[0]
        sector_no=0
	for ln in out.split('\n'):
	    if len(ln) == 0:
            	break
            entries = ln.split(',')
            sector = int(entries[0])
            size = int(entries[1])
            flag = int(entries[2])
	    self.assertEqual((start + sector_no * 8), sector) 
	    self.assertEqual(size, blksize)
	    # Flag 17 implies write IO, in centos 
	    # flag value is 65
	    self.assertTrue(int(flag) == 17 or int(flag) == 65)
	    sector_no = sector_no + 1

        # On break, sector count should be equal 
	# to the IO count
        self.assertEqual(sector_no, count)

	# Repeat the test for read operation.
	# Re-accelerate the device to vanish any 
	# residual entries in kfifo
	deaccelerate_dev(self.primary_volume, tc=self)
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self)

	# Read 1MB of data
        r = dodd(inf = self.primary_volume, of = "/dev/null", bs = blksize, count = count, iflag = "direct")
        self.assertEqual(r, 0)

	# Get entries from Kernel FIFO
        cmd = "cachebox -t 256 -d %s" % (self.primary_volume)
        process_1 = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE)
        out = process_1.communicate()[0]
        sector_no=0

	for ln in out.split('\n'):
	    if len(ln) == 0:
            	break
            entries = ln.split(',')
            sector = int(entries[0])
            size = int(entries[1])
            flag = int(entries[2])
	    self.assertEqual((start + sector_no * 8), sector) 
	    self.assertEqual(size, blksize)
	    # Flag 0 implies read IO	
	    self.assertEqual(flag, 0)
	    sector_no = sector_no + 1

        # Sector count should be equal to the IO count
        self.assertEqual(sector_no, count)

        drop_caches(tc=self)
        do_pass(self, 'test_kfifo')

if __name__ == '__main__':
       unittest.main(argv=["cbkfifotrace.py"] + args)
