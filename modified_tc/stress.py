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
import tempfile
import unittest

from common_utils import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
	if not member_name.startswith("__"):
		globals()[member_name] = getattr(config, member_name)

callInvalidateioc = Common_Utils.callInvalidateioc
create_devices = Common_Utils.create_devices
resetcoverage = Common_Utils.resetcoverage
checkdev = Common_Utils.checkdev
getxstats = Common_Utils.getxstats
getattrs = Common_Utils.getattrs
accelerateregion = Common_Utils.accelerateregion
accelerate_allregions = Common_Utils.accelerate_allregions
deaccelerate_allregions = Common_Utils.deaccelerate_allregions
deaccelerateregion = Common_Utils.deaccelerateregion
isdev_accelerated = Common_Utils.isdev_accelerated
lmdd_checkpattern = Common_Utils.lmdd_checkpattern
get_devsz = Common_Utils.get_devsz

del_loopdev = Common_Utils.del_loopdev
accelerate_dev = Common_Utils.accelerate_dev
deaccelerate_dev = Common_Utils.deaccelerate_dev
getcoverage = Common_Utils.getcoverage
do_mkfs = Common_Utils.do_mkfs
do_mkdir = Common_Utils.do_mkdir
do_mount = Common_Utils.do_mount
do_unmount = Common_Utils.do_unmount
do_fsck = Common_Utils.do_fsck
del_tmpfile = Common_Utils.del_tmpfile
drop_caches = Common_Utils.drop_caches
get_devblksz = Common_Utils.get_devblksz
set_devblksz = Common_Utils.set_devblksz

accelerate_slowdown = Common_Utils.accelerate_slowdown
mount_unmount = Common_Utils.mount_unmount


class Utils(object):

    @staticmethod
    def checkcorrectness(pvol, bs, tc):

        do_mkfs(pvol, bs, tc)
        do_mkdir("/mnt/test/", tc)
        do_mount(pvol, "/mnt/test/", tc)

        devsz = get_devsz(pvol)
        count = ((int(devsz)*512)/bs)/10
        for i in range(1, 6):
            cmd = "lmdd of=/mnt/test/file%d opat=1 bs=%d count=%d > /dev/null 2>&1" % (i, bs, count)
            r = os.system(cmd)
            tc.assertEqual(r, 0)

        do_unmount("/mnt/test/", tc)
        do_mount(pvol, "/mnt/test/", tc)

        for i in range(1, 6):
            dev = "/mnt/test/trial/file%d" % i
            r = lmdd_checkpattern(dev, bs, count, 0)
            tc.assertEqual(r, 0)

        do_unmount("/mnt/test/", tc)

    @staticmethod
    def read_hdd(devname, bs, tc):
        cmd = "lmdd ipat=1 if=%s bs=%d > /dev/null 2>&1" % (devname, bs)
        r = os.system(cmd)
        tc.assertEqual(r, 0)

    @staticmethod
    def do_ioctl(*args, **kwargs):
        pv = kwargs.get('pv')
        sv = kwargs.get('sv')
        tc = kwargs.get('tc')
        for j in range(1, 15):
            for i in range(0, 9):
                if i not in (0, 1, 2, 3):
                    cmd = "cachebox -a %d -d %s -s %s>/dev/null 2>&1" % (i, pv, sv)
                    r = os.system(cmd)
         
    @staticmethod
    def read_device(*args, **kwargs):
        pv = kwargs.get('pv')
        tc = kwargs.get('tc')
        devsz = get_devsz(tc.primary_volume)
        tc.count = devsz >> 4
        cmd = "lmdd opat=1 of=%s bs=4096 count=%s > /dev/null 2>&1" % (pv, tc.count)
        r = os.system(cmd)
        tc.assertEqual(r, 0)

        for i in xrange(1, 6):
            r = lmdd_checkpattern(pv, 4096, tc.count, 0)
            tc.assertEqual(r, 0)
            drop_caches(tc)


    @staticmethod
    def loop_readwrite_hdd(pvol, bs, tc):
        for i in xrange(1, 10):
            devsz = get_devsz(pvol)
            count = ((int(devsz)*512)/bs)/10
            cmd = "lmdd opat=1 of=%s bs=%d count=%d skip=%d > /dev/null 2>&1" % (pvol,
                     bs, count, i*count)
            r = os.system(cmd)

            cmd = "lmdd ipat=1 if=%s bs=%d count=%d skip=%d > /dev/null 2>&1" % (pvol,
                     bs, count, i*count)
            r = os.system(cmd)
            drop_caches(tc)

    @staticmethod
    def issue_reclaim(devname, rmax, rthreshold):
        callInvalidateioc(devname, rmax, rthreshold)

    @staticmethod
    def accelerate_deaccelerate_bmflip(*args, **kwargs):
        pv = kwargs.get('pv')
        count = kwargs.get('count')
        tc = kwargs.get('tc')
        for i in xrange(1, count):
            cmd = "cachebox -a 7 -d %s" % (pv)
            r = os.system(cmd)
            tc.assertEqual(r, 0)

	    # deacceleration is not supported
            # cmd = "cachebox -a 9 -d %s" % (pv)
            # r = os.system(cmd)
            # tc.assertEqual(r, 0)

            if tc.stopthread:
              break


checkcorrectness = Utils.checkcorrectness
read_hdd = Utils.read_hdd
issue_reclaim = Utils.issue_reclaim
loop_readwrite_hdd = Utils.loop_readwrite_hdd
read_device = Utils.read_device
do_ioctl = Utils.do_ioctl
accelerate_deaccelerate_bmflip = Utils.accelerate_deaccelerate_bmflip


class ThreadsReadDevice(Pre_check, unittest.TestCase):
    """
    Test read/write using multiple threads parallely 
    """

    def setUp(self):
        super(ThreadsReadDevice, self).setUp()

        self.startTime = time.time()

        # The ssd and hdd sizes are specified in MB and bs in bytes
        create_devices(ssdsz=20, pvolsz=200, bs=4096, oddsize=0, tc=self)

    def tearDown(self):
        super(ThreadsReadDevice, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        t = time.time() - self.startTime
        time.sleep(2)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_block_sizes(self):
        for s in range(12,13):
            bsize = 1 << s
            
            cmd = "lmdd opat=1 of=%s bs=%d > /dev/null 2>&1" % (self.primary_volume,
                      self.bsize)
            r = os.system(cmd)
            self.assertEqual(r, 0)

            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)

            accelerate_allregions(self.primary_volume, tc=self)
            drop_caches(tc=self)

            thread1 = threading.Thread(target = read_hdd, args = (self.primary_volume, bsize, self)) 
            thread2 = threading.Thread(target = read_hdd, args = (self.primary_volume, bsize, self)) 
            thread3 = threading.Thread(target = read_hdd, args = (self.primary_volume, bsize, self)) 
            thread4 = threading.Thread(target = read_hdd, args = (self.primary_volume, bsize, self)) 
            thread5 = threading.Thread(target = read_hdd, args = (self.primary_volume, bsize, self)) 
            thread6 = threading.Thread(target = read_hdd, args = (self.primary_volume, bsize, self)) 

            thread1.start()
            thread2.start()
            thread3.start()
            thread4.start()
            thread5.start()
            thread6.start()

            thread1.join()
            thread2.join()
            thread3.join()
            thread4.join()
            thread5.join()
            thread6.join()

            deaccelerate_dev(self.primary_volume, tc=self)

class ThreadRead_Write_loop(Pre_check, unittest.TestCase):
    """
    Test read/write using two threads in loop
    """

    def setUp(self):
        super(ThreadRead_Write_loop, self).setUp()

        self.startTime = time.time()

        # The ssd and hdd sizes are specified in MB and bs in bytes
        create_devices(ssdsz=20, pvolsz=200, bs=4096, oddsize=0, tc=self)
        self.rmax = 15
        self.rthreshold =	8 

    def tearDown(self):
        super(ThreadRead_Write_loop, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        t = time.time() - self.startTime
        time.sleep(2)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_block_sizes(self):
        for s in range(12,13):
            bsize = 1 << s
            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)

            accelerate_allregions(self.primary_volume, tc=self)

            drop_caches(tc=self)

            threadA = threading.Thread(target = loop_readwrite_hdd, args = (self.primary_volume, bsize, self))

            threadA.start()
            while threadA.isAlive():
                threadB = threading.Timer(2, issue_reclaim, [self.primary_volume, self.rmax, self.rthreshold])
                threadB.start()
                threadB.join()

            threadA.join()

            deaccelerate_dev(self.primary_volume, tc=self)

class TestWithSysbench(Pre_check, unittest.TestCase):
    """
    Test read/write using two threads in loop
    """

    def setUp(self):
        super(TestWithSysbench, self).setUp()

        self.startTime = time.time()

        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        #Check if the devices in config.py are already existing
        checkdev(devname=self.primary_volume, tc=self)
        checkdev(devname=self.ssd_volume, tc=self)

        self.devbsz = get_devblksz(self.primary_volume)

    def tearDown(self):
        super(TestWithSysbench, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        t = time.time() - self.startTime
        time.sleep(2)
        set_devblksz(self.primary_volume, self.devbsz, tc=self)

    def test_sysbench_directio(self):
        for s in range(10, 17):
            bsize = 1 << s
            dev_blksz = get_devblksz(self.primary_volume)
            if bsize > dev_blksz:
                continue
            do_mkfs(self.primary_volume, bsize, tc=self)
            do_mkdir("/mnt/test", tc=self)
            do_mount(self.primary_volume, "/mnt/test/", tc=self)
            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)
            accelerate_allregions(self.primary_volume, tc=self)

            cmd = "bash ./sb.sh direct > /dev/null 2>&1"
            r = os.system(cmd)
            self.assertEqual(r, 0)
            stats = getxstats(self.primary_volume)
            do_unmount("/mnt/test", tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_sysbench(self):
        for s in range(10, 17):
            bsize = 1 << s
            dev_blksz = get_devblksz(self.primary_volume)
            if bsize > dev_blksz:
                continue
            do_mkfs(self.primary_volume, bsize, tc=self)
            do_mkdir("/mnt/test", tc=self)
            do_mount(self.primary_volume, "/mnt/test/", tc=self)
            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)
            accelerate_allregions(self.primary_volume, tc=self)

            cmd = "bash ./sb.sh > /dev/null 2>&1"
            r = os.system(cmd)
            self.assertEqual(r, 0)
            stats = getxstats(self.primary_volume)
            do_unmount("/mnt/test", tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)


class AccelerateSlowdown(Pre_check, unittest.TestCase):
    """
    Accelerate and slowdown while IOs are ongoing.
    """

    def setUp(self):
        super(AccelerateSlowdown, self).setUp()
        self.startTime = time.time()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        #Check if the devices in config.py are already existing
        checkdev(self.primary_volume, tc=self)
        checkdev(self.ssd_volume, tc=self)

        self.devbsz = get_devblksz(self.primary_volume)


    def tearDown(self):
        super(AccelerateSlowdown, self).tearDown()
        time.sleep(2)
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)
        t = time.time() - self.startTime
        set_devblksz(self.primary_volume, self.devbsz, tc=self)

    def test_accelerate_slowdown_with_io_loop(self):

        self.stopthread = 0
        threadA = threading.Thread(target = read_device, kwargs = {'tc':self, 'pv':self.primary_volume})
        threadB = threading.Thread(target = accelerate_slowdown, kwargs = {'tc':self, 'pv':self.primary_volume, 'sv':self.ssd_volume, 'count':500, 'assertval':"use"})

        threadB.start()
        threadA.start()

        threadA.join()
        if not threadA.isAlive():
           self.stopthread = 1
           threadB.join(0)

    def test_accelerate_slowdown_with_ioctl_loop(self):

        self.stopthread = 0
        threadA = threading.Thread(target = do_ioctl, kwargs = {'tc':self, 'pv':self.primary_volume, 'sv':self.ssd_volume})
        threadB = threading.Thread(target = accelerate_slowdown, kwargs = {'tc':self, 'pv':self.primary_volume, 'sv':self.ssd_volume, 'count':100, 'assertval':"ignore"})

        threadB.start()
        threadA.start()
        
        threadA.join()
        if not threadA.isAlive():
           self.stopthread = 1
           threadB.join(0)
 
    def multithreaded_sysbench(*args, **kwargs):
          bsize = 4096
          pv = kwargs.get('pv')
          tc = kwargs.get('tc')
          do_mkfs(pv, "default", tc)
          do_mkdir("/mnt/test", tc)
          do_mount(pv, "/mnt/test/", tc)

          cmd = "bash ./sb.sh direct > /dev/null 2>&1"
          r = os.system(cmd)
          tc.assertEqual(r, 0)
          do_unmount("/mnt/test", tc)

    def test_accelerate_slowdown_with_multithreaded_sysbench(self):

        self.stopthread = 0
#        resetcoverage(tc=self)
        threadA = threading.Thread(target = self.multithreaded_sysbench, kwargs = {'tc':self, 'pv':self.primary_volume})
        threadB = threading.Thread(target = accelerate_slowdown, kwargs = {'tc':self, 'pv':self.primary_volume, 'sv':self.ssd_volume, 'count':500, 'assertval':"use"})

        threadB.start()
        threadA.start()
        threadA.join()
        if not threadA.isAlive():
           self.stopthread = 1
           threadB.join(0)
 
#        cover = getcoverage(tc=self)
#        self.assertFalse('#cb_io_during_disable' in cover, "cb_io_during_disable not covered") 

    def test_accelerate_deacc_with_multithreaded_sysbench(self):

        self.stopthread = 0
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self)
        threadA = threading.Thread(target = self.multithreaded_sysbench, kwargs = {'tc':self, 'pv':self.primary_volume})
        threadB = threading.Thread(target = accelerate_deaccelerate_bmflip, kwargs = {'tc':self, 'pv':self.primary_volume, 'count':500})

        threadB.start()
        threadA.start()
        threadA.join()
        if not threadA.isAlive():
           self.stopthread = 1
           threadB.join(0)

        deaccelerate_dev(self.primary_volume, tc=self)


if __name__ == '__main__':
	unittest.main(argv=["stress.py"] + args)
