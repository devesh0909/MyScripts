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


SSD_SIZE = [4 << 24, 4 << 25, 5 << 25, 7 << 30]
HDD_SIZE = [1 << 30, 4 << 31, 5 << 33]
MODE = ['full-disk', 'monitor']

HDD_SSD_COMBINATION = {HDD_SIZE[0]: [SSD_SIZE[0], SSD_SIZE[1]], \
                       HDD_SIZE[1]: [SSD_SIZE[1], SSD_SIZE[2]], \
                       HDD_SIZE[2]: [SSD_SIZE[2], SSD_SIZE[3]], \
                       }

"""
This function is used create virtual drives
"""
def create_drive(size, drive, nature, name, tc):
    size = size / 512
    cmd = """dmsetup create %s << -EOD
0 %d zero
-EOD""" % (nature, size)
    logger.debug(cmd)
    returncode = os.system(cmd)
    cmd = "dd if=/dev/zero of=%s count=10000 bs=4K" % (drive)
    process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                stderr = subprocess.PIPE, shell = True)
    output = process_1.communicate()

    cmd = """dmsetup create %s << -EOD
0 %s snapshot /dev/mapper/%s  %s P 16
-EOD""" % (name, size, nature, drive)
    logger.debug(cmd)
    returncode = os.system(cmd)


"""
Delete the virtual hdd and  ssd volume
"""
def delete_drive(nature, name, tc):
    cmd = ("dmsetup remove /dev/mapper/%s" % name)
    logger.debug(cmd)
    process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                stderr = subprocess.PIPE, shell = True)
    output = process_1.communicate()

    cmd = ("dmsetup remove /dev/mapper/%s" % nature)
    logger.debug(cmd)
    process_2 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                stderr = subprocess.PIPE, shell = True)
    output = process_2.communicate()


def do_acceleration(pv, sv):
    bsize = 4096
    cmd = ["cbfmt",
           "-d",
           "%s" % pv,
           "-s",
           "%s" % sv,
           "-b",
           "%s" % bsize
           ]
    logger.debug(cmd)
    process_1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = process_1.communicate()

    cmd = ["cachebox",
           "-a 3",
           "-d",
           "%s" % pv,
           "-s",
           "%s" % sv,
           "-b",
           "%s" % bsize
           ]
    logger.debug(cmd)
    process_2 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = process_2.communicate()

    output = [process_1.returncode, process_2.returncode]
    return output


"""
Get the virtual drive name
"""
def get_devicename(device):
    ss = os.readlink(device)
    return ss.split('/')[-1]


"""
deaccelerate the device
"""
def deaccelerate(devname, tc):
    cmd = "cachebox -a 17 -d %s" % devname
    logger.debug(cmd)
    r = os.system(cmd)
    tc.assertEqual(r, 0)

    cmd = "cachebox -a 1 -d %s" % devname
    logger.debug(cmd)
    r = os.system(cmd)
    tc.assertEqual(r, 0)
    cmd = "sync"


class TestSmallCache(CBQAMixin, unittest.TestCase):

    """
    Check that we are handling too small cache size properly
    Creating Different Sizes of HDD and SSD and check whether 
    it handle small SSD
    HDD                   SSD
    ===========================
    1G                    64M
    8G                    128M
    40G                   160M
                          7G
    """
    def setUp(self):
        super(TestSmallCache, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.hdd_size = HDD_SSD_COMBINATION.keys()


    def tearDown(self):
        super(TestSmallCache, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate(self.primary_volume, tc=self)
        delete_drive("SSD", "ssd_test", tc = self)
        delete_drive("HDD", "hdd_test", tc = self)


    def test_1(self):
        for i in range(0, 3):
            self.ssd_size =  HDD_SSD_COMBINATION[self.hdd_size[i]]
            create_drive(self.hdd_size[i], self.primary_volume, "HDD", "hdd_test", tc = self)
            primary_volume = "/dev/%s" % get_devicename("/dev/mapper/hdd_test")
            for j in range(0, 2):
                create_drive(self.ssd_size[j], self.ssd_volume, "SSD", "ssd_test", tc = self)
                ssd_volume = "/dev/%s" % get_devicename("/dev/mapper/ssd_test")
                output = do_acceleration(primary_volume, ssd_volume)
                if j == 0:
                    self.assertNotEqual(output[0], 0)
                    self.assertNotEqual(output[1], 0)
                else:
                    self.assertEqual(output[0], 0)
                    self.assertEqual(output[1], 0)
                if isdev_accelerated(primary_volume):
                    deaccelerate(primary_volume, tc=self)
                delete_drive("SSD", "ssd_test", tc = self)
            delete_drive("HDD", "hdd_test", tc = self)


class TestSSDDevice(CBQAMixin, unittest.TestCase):
    """
    Test that two disks cannot be accelerated using same SSD.
    """

    def setUp(self):
        super(TestSSDDevice, self).setUp()
        self.startTime = time.time()
        create_devices(ssdsz=150, pvolsz=300, bs=4096, oddsize=0, tc=self)
        self.pv = random.choice(PRIMARY_VOLUMES)


    def tearDown(self):
        super(TestSSDDevice, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)
        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_1(self):
        for mode in MODE:
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self, mode = mode)
            cmd = "cachebox -a 3 -d %s -s %s > /dev/null 2>&1" % (self.pv, self.ssd_volume) 
            r = os.system(cmd)
            do_pass(self, 'test_ssddevbusy:1a', r != 0)
            deaccelerate_dev(self.primary_volume, tc=self)

if __name__ == '__main__':
    unittest.main(argv=["cachedev.py"] + args)
