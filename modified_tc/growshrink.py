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
import platform

from common_utils import *
from cblog import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)


VG = "lvm"
LV = "lvm_test"

real_device = None

WRITE_POLICY = ['write-back', 'write-around', 'write-through', 'read-around']

class GrowShrink_Utils(object):
    @staticmethod
    def islvm_accelerated(device):
         cmd = "cachebox -l | grep %s > /dev/null" % device
         r = os.system(cmd)
         return (1 if r == 0 else 0)


    @staticmethod
    def chk_lvm_inconfig(device):
        try:
            ss = os.readlink(device)
            return "True"
        except:
            device_detail = device.split('/')[-1]
            return os.path.exists("/sys/class/block/%s/dm" % device_detail)

    @staticmethod
    def do_dd(tc, input_dev, output_dev, bs, count, operation, debug=False):
        cmd = [
            "dd",
            "if=%s" % input_dev,
            "of=%s" % output_dev,
            "bs=%d" % bs,
            "count=%d" % count,
            "%s" % operation
            ]
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE)
        out, err = process_1.communicate()
        if debug:
            return process_1.returncode
        else:
            tc.assertEqual(process_1.returncode, 0)


islvm_accelerated = GrowShrink_Utils.islvm_accelerated
chk_lvm_inconfig = GrowShrink_Utils.chk_lvm_inconfig
do_dd = GrowShrink_Utils.do_dd


"""
Create a LVM volume, accelerate the LVM volume
Now extends the LVM volume
Do some writes on the extended volumes 
and check whether increased area are cached
and verify the cachebox output
"""
class GrowShrink_LVM(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(GrowShrink_LVM, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(GrowShrink_LVM, self).tearDown()
        global real_device
        if real_device is not None:
            if islvm_accelerated(real_device):
                deaccelerate_dev("/dev/%s" % (real_device), tc = self)
            self.flush()
            delete_lvmdevice("/dev/%s/%s" % (VG, LV), VG, 
                            self.primary_volume, tc = self)
        real_device = None


    """
    Accelerate LVM, Extend LVM, do writes on extended Volume
    Do reads on extended LVM volume
    Verifying the cachebox output
    """
    def test_1(self):
        global real_device
        if chk_lvm_inconfig(random.choice(PRIMARY_VOLUMES)):
            do_skip(self, 'Lvm volume is given for lvm testing')
            real_device = get_devicename(self.primary_volume, self)
        else:
            for policy in WRITE_POLICY:
                #size of LVM in GB
                size = 1
                create_lvmdevice(VG, LV, size, self.primary_volume, tc = self)
                volume = "/dev/%s/%s" % (VG, LV)
                real_device = get_devicename(volume, self)
                primary_volume = "/dev/%s" % (real_device)
                do_mkfs(primary_volume, "default", tc = self)
                accelerate_dev(primary_volume, self.ssd_volume, 4096, \
                                tc = self, write_policy = policy)
                #doing some IO on acclerated LVM
                do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
                do_dd(self, primary_volume, "/dev/zero", 4096, 10000, "skip=0")
                self.flush()
                first_stat = getxstats(primary_volume)
                real_device = get_devicename(primary_volume, self)
                #exteng LVM to 2GB
                extend_lvmdevice(volume, tc = self)
                """
                write some data beyond 1G
                Reading some data beyond 1G
                """
                do_dd(self, "/dev/zero", primary_volume, 4096, 1000, "seek=262144")
                do_dd(self, primary_volume, "/dev/zero", 4096, 1000, "skip=262144")
                self.flush()
                current_stat = getxstats(primary_volume)

                self.assertTrue(int(current_stat['cs_read_hits']) >= \
                                int(first_stat['cs_read_hits']))
                self.assertTrue(int(current_stat['cs_readcache_flow']) >= \
                                int(first_stat['cs_readcache_flow']))

                self.assertTrue(int(current_stat['cs_writecache_flow']) >= \
                                int(first_stat['cs_writecache_flow']) or
                                int(current_stat['cs_writearound_flow']) >= \
                                int(first_stat['cs_writearound_flow']) or
                                int(current_stat['cs_writethrough_flow']) >= \
                                int(first_stat['cs_writethrough_flow']))
                deaccelerate_dev(primary_volume, tc = self)
                self.flush()
                time.sleep(10)
                delete_lvmdevice("/dev/%s/%s" % (VG, LV), VG, 
                                self.primary_volume, tc = self)


    """
    Accelerate LVM, Reduce LVM, do writes and reads on shrinked Volume
    Verifying the cachebox output
    Try to write beyond LVM volume, IO's will not be done beyong shrink volume
    """
    def test_2(self):
        global real_device
        if chk_lvm_inconfig(random.choice(PRIMARY_VOLUMES)):
            do_skip(self, 'Lvm volume is given for lvm testing')
            real_device = get_devicename(self.primary_volume, self)
        else:
            for policy in WRITE_POLICY:
                #size of LVM in GB
                size = 1
                create_lvmdevice(VG, LV, size, self.primary_volume, tc = self)
                volume = "/dev/%s/%s" % (VG, LV)
                real_device = get_devicename(volume, self)
                primary_volume = "/dev/%s" % (real_device)
                do_mkfs(primary_volume, "default", tc = self)
                accelerate_dev(primary_volume, self.ssd_volume, 4096, \
                                tc = self, write_policy = policy)
                do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
                do_dd(self, primary_volume, "/dev/zero", 4096, 10000, "skip=0")
                self.flush()
                first_stat = getxstats(primary_volume)
                real_device = get_devicename(primary_volume, self)

                """
                reducing lvm from 1G to 524M
                try to write some data beyond 524M
                try to Read data till 524M, check cb_stats works
                """
                time.sleep(20)
                #shrink LVM volume by 500M
                shrink_lvmdevice(volume, tc = self)
                #try to write on the deleted lvm partition volume
                r1 = do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=134144", debug = True)
                self.assertNotEqual(r1, 0)
                #try to read from the accelerated device
                do_dd(self, primary_volume, "/dev/zero", 4096, 10000, "skip=0")
                self.flush()
                current_stat = getxstats(primary_volume)
                self.assertTrue(int(current_stat['cs_read_hits']) >= \
                                int(first_stat['cs_read_hits']))
                self.assertTrue(int(current_stat['cs_readcache_flow']) >= \
                                int(first_stat['cs_readcache_flow']))

                self.assertTrue(int(current_stat['cs_writecache_flow']) == \
                                int(first_stat['cs_writecache_flow']) or
                                int(current_stat['cs_writearound_flow']) == \
                                int(first_stat['cs_writearound_flow']) or
                                int(current_stat['cs_writethrough_flow']) == \
                                int(first_stat['cs_writethrough_flow']))
                deaccelerate_dev(primary_volume, tc = self)
                self.flush()
                time.sleep(10)
                delete_lvmdevice("/dev/%s/%s" % (VG, LV), VG, 
                                self.primary_volume, tc = self)



if __name__ == '__main__':
    unittest.main(argv=["growshrink.py"] + args)
