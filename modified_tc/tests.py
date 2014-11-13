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

sys.path.append("../../webconsole/console/cgi-bin")
from util import validate_ip

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

WRITE_POLICY = ['write-back', 'write-through', 'write-around', 'read-around']

class Testcacheboxlistoption(CBQAMixin, unittest.TestCase):
    """
    Test the cachebox -l option to list all the devices accelerated by
    CB.
    """

    def setUp(self):
        super(Testcacheboxlistoption, self).setUp()

        create_devices(ssdsz=5, pvolsz=10, bs=4096, oddsize=0, tc=self)

    def tearDown(self):
        super(Testcacheboxlistoption, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_list_option(self):

        self.pv1 = random.choice(PRIMARY_VOLUMES)
        self.sv1 = random.choice(SSD_VOLUMES.keys())

        #Check if the devices in config.py are already existing
        checkdev(devname=self.pv1, tc=self)
        checkdev(devname=self.sv1, tc=self)
				
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self)
        accelerate_dev(self.pv1, self.sv1, 4096, tc=self)

        cmd = ["cachebox", "-l" ]
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = r.communicate()[0].rstrip('\n')
	do_pass(self, 'test_list_option', r.returncode == 0)

        cmd = ["cachebox",
               "-l",
               "-d",
               "%s" % self.primary_volume
               ]
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
	do_pass(self, 'test_list_option', r.returncode == 0)
        deaccelerate_dev(self.primary_volume, tc=self)
        deaccelerate_dev(self.pv1, tc=self)



class TestAccelerateExisting(CBQAMixin, unittest.TestCase):
    """
    Test the cb caching to see if there are no corruptions    
    """

    def setUp(self):
        super(TestAccelerateExisting, self).setUp()


        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        #Check if the devices in config.py are already existing
        checkdev(devname=self.primary_volume, tc=self)
        checkdev(devname=self.ssd_volume, tc=self)
      

    def tearDown(self):
        super(TestAccelerateExisting, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_existing_dev_accelerate(self):
        do_skip(self, "Skipping the Testcase as Acceleration of excisting \
device is not supported")
        return
        for s in cbqaconfig['TEST_BSIZES']:
            bsize = 1 << s
            dev_blksz = get_devblksz(self.primary_volume)
            if bsize > dev_blksz:
	     	do_skip(self, "test_existing_dev_accelerate:%s" % bsize)
                continue

            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)
            attrs = getattrs(self.primary_volume)
            deaccelerate_dev(self.primary_volume, tc=self)
            accelerate_existingdev(self.primary_volume, self.ssd_volume, tc=self)
            attrs_new = getattrs(self.primary_volume)

            do_pass(self, "test_existing_dev_accelerate:1", int(attrs['disk_size']) == int(attrs_new['disk_size']))
            do_pass(self, "test_existing_dev_accelerate:2", int(attrs['ssd_size']) == int(attrs_new['ssd_size']))
            do_pass(self, "test_existing_dev_accelerate:3", int(attrs['bsize']) == int(attrs_new['bsize']))
            do_pass(self, "test_existing_dev_accelerate:4", int(attrs['regionsize']) == int(attrs_new['regionsize']))
            do_pass(self, "test_existing_dev_accelerate:5", int(attrs['numregions']) == int(attrs_new['numregions']))
            do_pass(self, "test_existing_dev_accelerate:6", int(attrs['ebsize']) == int(attrs_new['ebsize']))
            do_pass(self, "test_existing_dev_accelerate:7", int(attrs['ebcount']) == int(attrs_new['ebcount']))

            deaccelerate_dev(self.primary_volume, tc=self)
            reclaim_with_read_loop(devtype='exist', tc=self)

class TestPerDiskMemioctl(CBQAMixin, unittest.TestCase):
    """
    Test the ioctl to set the memory cap. 
    """

    def setUp(self):
        super(TestPerDiskMemioctl, self).setUp()
        create_devices(ssdsz=10, pvolsz=50, bs=4096, oddsize=0, tc=self)

    def tearDown(self):
        super(TestPerDiskMemioctl, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_memcap(self):
	do_skip(self, 'test_memcap: deprecated functionality')
	return


class TestCorrectnessWithExist(CBQAMixin, unittest.TestCase):
    """
    Test there is no corruption with cb driver in picture.
    """

    def setUp(self):
        super(TestCorrectnessWithExist, self).setUp()

        # The ssd and hdd sizes are specified in MB and bs in bytes
        create_devices(ssdsz=12, pvolsz=50, bs=4096, oddsize=0, tc=self)
        self.devbsz = get_devblksz(self.primary_volume)

    def tearDown(self):
        super(TestCorrectnessWithExist, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_block_sizes_correctness1(self):
        for s in cbqaconfig['TEST_BSIZES']:
            bsize = 1 << s

            do_mkfs(self.primary_volume, bsize, tc=self)
            do_mount(self.primary_volume, "%stest/" % mountdir, tc=self)
            do_mkdir("%stest/trial/" % mountdir, tc=self)

            devsz = get_devsz(self.ssd_volume)

            # Keeping some 1M(2048 sectors) size aside for FS and
            # using remaining size for creating file.

            count = (((devsz - 2048)*512)/bsize)/2
            r = dolmdd(of = "%stest/trial/file1" % mountdir, bs = bsize, count = count, opat = "")
            do_pass(self, 'test_block_sizes_correctness1:1a', r == 0)

            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self)
            accelerate_allregions(self.primary_volume, tc=self)

            dev = "%stest/trial/file1" % mountdir
            drop_caches(tc=self)
            r = lmdd_checkpattern(dev, bsize, count, 0)
    	    do_pass(self, 'test_block_sizes_correctness1:1b', r == 0)
            stats = getxstats(self.primary_volume)
            do_pass(self, 'test_block_sizes_correctness1:1c',
	    (stats.get('cs_readpopulate_flow') > 0) or (stats.get('cs_writethrough_flow') > 0))

            do_unmount("%stest/" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)

            do_mount(self.primary_volume, "%stest/" % mountdir, tc=self)
            accelerate_existingdev(self.primary_volume, self.ssd_volume, tc=self)
            do_unmount("%stest/" % mountdir, tc=self)
            return
            drop_caches(tc=self)

            dev = "%stest/trial/file1" % mountdir
            drop_caches(tc=self)
            r = lmdd_checkpattern(dev, bsize, count, 0)
            do_pass(self, 'test_block_sizes_correctness1:1d', r == 0)

            stats = getxstats(self.primary_volume)
            do_pass(self, 'test_block_sizes_correctness1:1d', int(stats['cs_readcache_flow']) != 0)

            do_unmount("%stest/" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)

class TestCrash(CBQAMixin, unittest.TestCase):
    """
    Test crash during i)reclaim ii)forward map flush iii)both
    """

    def setUp(self):
        super(TestCrash, self).setUp()

        # Note: DO NOT CHANGE THE SIZES(size < CBFLUSHCNT*ebssize)

	# Note: DO NOT CHANGE THE SIZES(size < CBFLUSHCNT*ebssize)
        # The ssd and hdd sizes are specified in MB and bs in bytes
        create_devices(ssdsz=9, pvolsz=6, bs=4096, oddsize=0, tc=self)
        self.rmax = 6
        self.rthreshold = 4
        set_devra(self.primary_volume, 0, tc=self)
        r = cb_set_tunable("reclaim_flush_interval", 60)
        self.assertEqual(r, 0, "could not set reclaim flush interval")
        self.pv_ra = get_devra(self.primary_volume)
        self.sv_ra = get_devra(self.ssd_volume)
        set_devra(self.primary_volume, 0, tc=self)
        set_devra(self.ssd_volume, 0, tc=self)

    def tearDown(self):
        super(TestCrash, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        set_devra(self.primary_volume, self.pv_ra, tc=self)
        set_devra(self.ssd_volume, self.sv_ra, tc=self)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_reclaim_crash(self):
	do_skip(self, 'test_reclaim_crash: to be rewritten') 

    def test_flush_fmap_crash(self):
	do_skip(self, 'test_flush_fmap_crash: to be rewritten')

class TestAccelerationTime(CBQAMixin, unittest.TestCase):
    """
    Test acceleration time of the primary volume with the ssd volume   
    """

    def setUp(self):
        super(TestAccelerationTime, self).setUp()

        #
        # create different disk size partition of primary volume
        #
        self.dslist = [20 << 31, 15 << 31, 10 << 31, 5 << 31, 2 << 31, 1 << 31, 500 << 21]
        self.disklist = []
        count = 1

        for bs in self.dslist:
            ttbs=bs
            cmd = """dmsetup create fhdd%s << -EOD 
0 %d zero
-EOD""" %(count, ttbs)
            r = os.system(cmd)
            self.assertEqual(r, 0)
            self.disklist.append("%s%s" %("/dev/mapper/fhdd", count))
            count = count + 1
        #
        #create snapshot volume
        #
        self.ssize = (2 << 31)
        cmd = """dmsetup create test << -EOD
0  %d zero
-EOD""" % (self.ssize)
        r=os.system(cmd)
        self.assertEqual(r, 0)
        #
        #create ssd volume using backing store and snapshot
        #
        sdev= random.choice(SSD_VOLUMES.keys())
        dodd(inf = "/dev/zero", of = sdev)
        cmd = """dmsetup create snap  << -EOD
0 %d snapshot /dev/mapper/test %s  P 16
-EOD""" % (self.ssize, sdev)
        r=os.system(cmd)
        self.assertEqual(r, 0)

    def tearDown(self):
        super(TestAccelerationTime, self).tearDown()
        for ds in self.disklist:
            os.system("dmsetup remove %s" % ds)
        os.system("dmsetup remove snap")
        os.system("dmsetup remove test")

    def test_acceleration_time(self):
        for s in cbqaconfig['TEST_BSIZES']:
            bsizelist = 1 << s
        sdev = "/dev/mapper/snap"
        count = 0 
        #
        #check time required to accelerate primary device with ssd device with different block sizes
        #
        str = "Primary volume,SSD volume,Block size,Time\n"
        for pdev in self.disklist :
            for bs in bsizelist :
                cmd = ["time",
                       "cbasm",
                       "--accelerate",
                       "--device=%s" % (pdev),
                       "--ssd=%s" % (sdev),
                       "--write-policy=write-back"
                      ]

                r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output, err = r.communicate()
                logger.debug(cmd)
                self.assertEqual(r.returncode, 0)
                result = err.split('\n')[1].split()[2].strip("elapsed")
                time = result.split(':')[1]
                time = float(time)
                # 
                #check time is less than 30 sec or not
                #
                assert time < 30
                str += "%s,%s,%s,%s\n" % (self.dslist[count], self.ssize, bs, result)
                #
                # deaccelerate primary volume 
                #
                deaccelerate_dev(pdev, self)
            count = count + 1
        #
        # create file which contain the details of required acceleration time of primary devices 
        #
        now = datetime.datetime.now()
        now=now.strftime("%d_%m_%y_%H:%M")
        filename="time_accelerate_%s.csv" % (now)
        f=open(filename, "w")
        f.write(str)
        f.close()

class TestRegionFaultEndio(CBQAMixin, unittest.TestCase):
    """
    Test Region Fault Endio
    """

    def setUp(self):
        super(TestRegionFaultEndio, self).setUp()

        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        #Check if the devices in config.py are already existing
        checkdev(devname=self.primary_volume, tc=self)
        checkdev(devname=self.ssd_volume, tc=self)

    def tearDown(self):
        super(TestRegionFaultEndio, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_fault_endio(self):

        #
        # set memory cap for 17 translations for region size 512k
        #
        memory_cap = 4096
        count = 5120
        r = cb_set_tunable("memory_cap_perdisk", memory_cap)
        self.assertEqual(r, 0, "could not set memory cap perdisk")
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self)
        setpolicy_dev("fulldisk", self.primary_volume, None, tc=self)
        attrs = getattrs(self.primary_volume)
        logger.debug(attrs)
        r = dodd(inf = "/dev/zero", of = self.primary_volume, bs = "4k", count = count, oflag = "direct")
        self.assertEqual(r, 0)
        drop_caches(tc=self)
        stats = getxstats(self.primary_volume)
        logger.debug(stats)
        self.assertTrue(stats.get('cs_translation_buffers') > 20)
        r = dodd(inf = "/dev/zero", of = self.primary_volume, bs = "4k", count = count, oflag = "direct")
        self.assertEqual(r, 0)
        drop_caches(tc=self)
        do_pass(self, 'test_fault_endio')

class TestIPAddress(unittest.TestCase):

    # Test all IP addresses ranging from 0.0.0.0 to 255.255.255.255

    def setUp(self):
        self.startTime = time.time()
        self.start_ip = 0
        self.end_ip = 300

    def tearDown(self):
        super(TestIPAddress, self).tearDown()
        t = time.time() - self.startTime
        logger.debug( "\nDONE: %s: %.3f" % (self.id(), t))

    def ip_test(self):
        for first_oct  in range(self.start_ip,  self.end_ip):
            for second_oct  in range(self.start_ip,  self.end_ip):
                for third_oct in range(self.start_ip,  self.end_ip):
                    for fourth_oct in range(self.start_ip,  self.end_ip):
                        ip = ".".join([str(first_oct), str(second_oct), str(third_oct), str(fourth_oct)])
                        regex_match = validate_ip(ip)
                        return_code = 0
                        if not regex_match:
                            return_code = 1
                        if first_oct == 255 and second_oct == 255 and third_oct == 255 and fourth_oct == 255:
                            print "Invalid IP %s" % ip
                            self.assertNotEqual(return_code, 0)
                        if first_oct > 255 or second_oct > 255 or third_oct > 255 or fourth_oct > 255:
                            print "Invalid IP %s" % ip
                            self.assertNotEqual(return_code, 0)
                        elif first_oct <= 0 or second_oct < 0 or third_oct < 0 or fourth_oct < 0:
                            print "Invalid IP %s" % ip
                            self.assertNotEqual(return_code, 0)
                        else:
                            print "Valid IP %s" % ip
                            self.assertEqual(return_code, 0)

class TestUniqueWriteIO(CBQAMixin, unittest.TestCase):
    """
    Test Unique write IO's on SSD
    """

    def setUp(self):
        super(TestUniqueWriteIO, self).setUp()

        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        #Check if the devices in config.py are already existing
        checkdev(devname=self.primary_volume, tc=self)
        checkdev(devname=self.ssd_volume, tc=self)

    def tearDown(self):
        super(TestUniqueWriteIO, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_01(self):
        #
        # For write policies WRITE-BACK and WRITE-THROUGH verify
        # if unique write count is correct
        # 1. Accelerate primary volume with one of the policy
        # 2. Accelerate all regions
        # 3. Write on the disk - this should increment cs_unique_write
        # 4. Again write on the same disk offset - cs_unique_write should
        #    not change
        # 5. De-accelerate the volume
        #
        for policy in WRITE_POLICY:
            self.accelerate(write_policy = policy)
            self.setpolicy()
            self.seq_write(count=1000)
            self.flush()
            self.flush()
            xstats = self.getxstats()
            unique_writes = int(xstats.get('cs_unique_writes'))
            self.assertEqual(unique_writes, 1000)
            self.seq_write(count=1000)
            self.flush()
            xstats = self.getxstats()
            self.assertEqual(unique_writes, int(xstats.get('cs_unique_writes')))
            self.deaccelerate()

    def test_02(self):
        #
        # For write policies WRITE-BACK and WRITE-THROUGH verify
        # if unique write count is correct
        # 1. Accelerate primary volume with one of the policy
        # 2. Accelerate all regions
        # 3. Read from disk - cs_unique_write shoudl be 0 and cs_readpopulate
        #    count should increment
        # 4. Again write on the same disk offset - cs_unique_write should
        #    not change and should still be 0
        # 5. De-accelerate the volume
        #
        for policy in WRITE_POLICY:
            self.accelerate(write_policy = policy)
            self.setpolicy()
            self.seq_read(count=1000)
            self.flush()
            xstats = self.getxstats()
            unique_writes = int(xstats.get('cs_unique_writes'))
            self.assertEqual(unique_writes, 0)
            self.seq_write(count=1000)
            self.flush()
            xstats = self.getxstats()
            self.assertEqual(unique_writes, int(xstats.get('cs_unique_writes')))
            self.deaccelerate()

    def test_03(self):
        #
        # For write policies WRITE-BACK and WRITE-THROUGH verify
        # if unique write count is correct
        # 1. Accelerate primary volume with one of the policy
        # 2. Accelerate all regions
        # 3. Write on the disk - this should increment cs_unique_write
        # 4. Issue copyback
        # 4. Again write on the same disk offset - cs_unique_write should
        #    not change
        # 5. De-accelerate the volume
        #
        for policy in WRITE_POLICY:
            self.accelerate(write_policy = policy)
            self.setpolicy()
            self.seq_write(count=1000)
            self.flush()
            self.flush()
            xstats = self.getxstats()
            unique_writes = int(xstats.get('cs_unique_writes'))
            self.assertEqual(unique_writes, 1000)
            self.copyback()
            self.flush()
            self.seq_write(count=1000)
            self.flush()
            xstats = self.getxstats()
            self.assertEqual(unique_writes, int(xstats.get('cs_unique_writes')))
            self.deaccelerate()

class TestCleanAccelerationFailureHandling(CBQAMixin, unittest.TestCase):
    """
    Test there is no corruption with cb driver in picture.
    """

    def setUp(self):
        super(TestCleanAccelerationFailureHandling, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.ssd1 = None
        self.ssd2 = None

        #Check if the devices in config.py are already existing
        checkdev(devname=self.primary_volume, tc=self)
        checkdev(devname=self.ssd_volume, tc=self)


    def tearDown(self):
        super(TestCleanAccelerationFailureHandling, self).tearDown()
        VG = "test"
        if self.ssd1 is not None:
            LV = "test_01"
            delete_lvmdevice("/dev/%s/%s" % (VG, LV), VG, 
                            self.ssd_volume, tc = self)
        if self.ssd2 is not None:
            LV = "test_02"
            delete_lvmdevice("/dev/%s/%s" % (VG, LV), VG, 
                            self.ssd_volume, tc = self)


    def test_01(self):
        #
        # Checks if the cleanup on failed acceleration is leak free and clean
        # 1. Create two 1GB SSD volumes out of a given SSD
        # 2. Format both the SSD with primary volume
        # 3. Accelerate one SSD. This should pass
        # 4. Accelerate another SSD with same primary volume. This should fail
        # 5. de-accelerate the device
        # 6. rmmod cachebox should work without any issues
        # 7. modprobe cachebox should work awithout any issues
        # 8. delete the SSD volumes
        # 

        VG = "test"
        LV = "test_01"
        size = 1
        create_lvmdevice(VG, LV, size, self.ssd_volume, self)
        volume = "/dev/%s/%s" % (VG, LV)
        real_device = self.get_devicename(volume, self)
        self.ssd1 = "/dev/%s" % (real_device)

        LV = "test_02"
        create_logical_device(VG, LV, size, self)
        volume = "/dev/%s/%s" % (VG, LV)
        real_device = self.get_devicename(volume, self)
        self.ssd2 = "/dev/%s" % (real_device)

        format_dev(self.primary_volume, self.ssd1, self)
        format_dev(self.primary_volume, self.ssd2, self)

        accelerate_existingdev(self.primary_volume, self.ssd1, self)
        r = accelerate_existingdev(self.primary_volume, self.ssd2, self, debug = True)
        self.assertNotEqual(r, 0)

        cmd = (
            "cachebox",
            "-a",
            "17",
            "-d",
            "%s" % self.primary_volume
        )

        r, o, e = do_cmd(cmd)
        self.assertEqual(r, 0)

        cmd = (
            "cachebox",
            "-a",
            "1",
            "-d",
            "%s" % self.primary_volume
        )

        r, o, e = do_cmd(cmd)
        self.assertEqual(r, 0)

        cmd = (
            "rmmod",
            "cachebox"
        )

        r, o, e = do_cmd(cmd)
        self.assertEqual(r, 0)

        cmd = (
            "modprobe",
            "cachebox"
        )

        r, o, e = do_cmd(cmd)
        self.assertEqual(r, 0)

        delete_logical_device("/dev/test/test_01", self)

        delete_lvmdevice("/dev/%s/%s" % (VG, LV), VG, 
                            self.ssd_volume, tc = self)

if __name__ == '__main__':
       unittest.main(argv=["tests.py"] + args)
