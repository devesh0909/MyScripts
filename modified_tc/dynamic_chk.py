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
import sys
import getopt
import os
import random
import subprocess
import tempfile
import unittest
import time
import common_utils
import threading
import platform

from common_utils import *
from cblog import *


config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

VG = "lvm"
LV = "lvm_test"

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

real_device = None

WRITE_POLICY = ['write-back', 'write-through', 'write-around', 'read-around']


class DynamicUtils(object):

    #Return UUID of device and flag
    @staticmethod
    def get_uuid_flag(device):
        cmd = "cbasm --list | grep -iw '%s' | grep -v grep" % device
        ss = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE)
        out = ss.communicate()[0].strip('\n').split('\n')
        for i in out:
            a = i.split()
        return[a[0], a[-3]]


    @staticmethod
    def chk_btd(device, uuid, tc):
        cmd = ("ps -aef | grep -i '/etc/cachebox/server/btd.py --device=%s --uuid=%s start' \
                | grep -v grep" % (device, uuid))
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, shell = True, \
                       stderr = subprocess.PIPE)
        out, err = process_1.communicate()
        logger.debug(out)
        tc.assertEqual(process_1.returncode, 0)


    @staticmethod
    def do_dd(*args):
        primary_volume = "".join(args)
        dodd(inf = primary_volume, of = "/dev/zero", bs = "4096", count = "30000")


    @staticmethod
    def deaccel_duringIO(this, volume):
        thread_1 = threading.Thread(target = do_dd, args = (volume))
        thread_1.start()
        thread_2 = threading.Thread(target = deaccelerate_dev, args = (volume, this))
        time.sleep(1)
        thread_2.start()
        thread_1.join()
        thread_2.join()


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


    #Return count of admission bitmap
    @staticmethod
    def chk_bitmapcount(volume):
        os.system("cachebox -a 10 -d %s" % volume)
        cmd = ("cachebox -a 15 -d %s | grep -i ' 1' | wc -l" % volume)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                stderr = subprocess.PIPE, shell = True)
        out = process_1.communicate()[0]
        logger.debug("Admit map: %s" % out)
        return out


chk_btd = DynamicUtils.chk_btd
chk_lvm_inconfig = DynamicUtils.chk_lvm_inconfig
do_dd = DynamicUtils.do_dd
deaccel_duringIO = DynamicUtils.deaccel_duringIO
get_uuid_flag = DynamicUtils.get_uuid_flag
islvm_accelerated = DynamicUtils.islvm_accelerated
chk_bitmapcount = DynamicUtils.chk_bitmapcount

"""
Accelerating a device using different block size and 
Doing reads without doing mkfs and cross checking CB stats 
"""
class DDCheck(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(DDCheck, self).setUp()
        self.startTime = time.time()
        self.pvn1 = random.choice(PRIMARY_VOLUMES)
        self.svn1 = random.choice(SSD_VOLUMES.keys())
        global real_device
        real_device = get_devicename(self.pvn1, self)
        self.pvn1 = "/dev/%s" % real_device


    def tearDown(self):
        super(DDCheck, self).tearDown()
        global real_device
        if isdev_accelerated(self.pvn1):
            deaccelerate_dev(self.pvn1, tc = self)
            real_device = None


    def test_1(self):
        for policy in WRITE_POLICY:
            for s in cbqaconfig['TEST_BSIZES']:
                bsize = 1 << s
                dev_blksz = get_devblksz(self.pvn1)
                if bsize > dev_blksz:
                    continue
                acceleratedev(self.pvn1, self.svn1, bsize, self, \
                                write_policy = policy, mode = "monitor")
                uuid_flag = get_uuid_flag(self.pvn1)
                self.assertEqual(uuid_flag[0], "*")
                chk_btd(real_device, uuid_flag[1], self)
                first_stat = getxstats(self.pvn1)
                accelerateregion(self, self.pvn1, 1)
                count = chk_bitmapcount(self.pvn1)
                self.assertEqual(int(count), 1)
                for j in range(1, 5):
                    lmddreadfromdev(self.pvn1, bsize, 30000, j)
                    self.flush()
                    stat = getxstats(self.pvn1)
                    if policy == "read-around":
                        break
                    self.assertTrue((stat['cs_readpopulate_flow']) > \
                                    (first_stat['cs_readpopulate_flow']))
                deaccelerate_dev(self.pvn1, tc = self)


    """
    Deaccelerate the device when io is going on the device
    """
    def test_2(self):
        for policy in WRITE_POLICY:
            for x in range(0, 2):
                for s in cbqaconfig['TEST_BSIZES']:
                    bsize = 1 << s
                    acceleratedev(self.pvn1, self.svn1, bsize, self, \
                                  write_policy = policy, mode = "monitor")
                    uuid_flag = get_uuid_flag(self.pvn1)
                    self.assertEqual(uuid_flag[0], "*")
                    chk_btd(real_device, uuid_flag[1], self)
                    deaccel_duringIO(self, self.pvn1)
            if isdev_accelerated(self.pvn1):
                deaccelerate_dev(self.pvn1, tc = self)


"""
Creating a filsystem on HDD
Accelearting a device using different block size and 
Doing reads on device and Cross checking CB stats
"""
class DDWithMkfs(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(DDWithMkfs, self).setUp()
        self.startTime = time.time()
        self.pvn1 = random.choice(PRIMARY_VOLUMES)
        self.svn1 = random.choice(SSD_VOLUMES.keys())
        global real_device
        real_device = get_devicename(self.pvn1, self)
        self.pvn1 = "/dev/%s" % real_device


    def tearDown(self):
        super(DDWithMkfs, self).tearDown()
        global real_device
        if isdev_accelerated(self.pvn1):
            deaccelerate_dev(self.pvn1, tc=self)
        if is_mounted("%stest" % mountdir):
            do_unmount("%stest" % mountdir, self)
        real_device = None


    def test_1(self):
        for policy in WRITE_POLICY:
            for s in cbqaconfig['TEST_BSIZES']:
                bsize = 1 << s
                if bsize != 512:
                    do_mkfs(self.pvn1, bsize, self)
                else:
                    do_mkfs(self.pvn1, "default", self)
                do_mkdir("%stest" % mountdir, self)
                do_mount(self.pvn1, "%stest" % mountdir, self)
                acceleratedev(self.pvn1, self.svn1, bsize, self, \
                                write_policy = policy, mode = "monitor")
                uuid_flag = get_uuid_flag(self.pvn1)
                self.assertEqual(uuid_flag[0], "*")
                chk_btd(real_device, uuid_flag[1], self)
                first_stat = getxstats(self.pvn1)
                accelerateregion(self, self.pvn1, 1)
                count = chk_bitmapcount(self.pvn1)
                self.assertEqual(int(count), 1)
                first_stat = getxstats(self.pvn1)
                for j in range(0, 5):
                    lmddreadfromdev(self.pvn1, bsize, 30000, j)
                    self.flush()
                    stat = getxstats(self.pvn1)
                    if policy == "read-around":
                        break
                    self.assertTrue((stat['cs_readpopulate_flow']) > \
                                    (first_stat['cs_readpopulate_flow']))
                deaccelerate_dev(self.pvn1, tc = self)
                do_unmount("%stest" % mountdir, self)


    def test_2(self):
        for policy in WRITE_POLICY:
            for x in range(0, 2):
                for s in cbqaconfig['TEST_BSIZES']:
                    bsize = 1 << s
                    if bsize != 512:
                        do_mkfs(self.pvn1, bsize, self)
                    else:
                        do_mkfs(self.pvn1, "default", self)
                    do_mkdir("%stest" % mountdir, self)
                    do_mount(self.pvn1, "%stest" % mountdir, self)
                    acceleratedev(self.pvn1, self.svn1, bsize, self, \
                                       write_policy = policy, mode = "monitor")
                    uuid_flag = get_uuid_flag(self.pvn1)
                    self.assertEqual(uuid_flag[0], "*")
                    chk_btd(real_device, uuid_flag[1], self)
                    deaccel_duringIO(self, self.pvn1)
                    do_unmount("%stest" % mountdir, self)
            if isdev_accelerated(self.pvn1):
                deaccelerate_dev(self.pvn1, tc = self)


"""
Accelearting VG using different block size and 
Doing reads on the volume and Cross checking CB stats
"""
class LVMChk(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(LVMChk, self).setUp()
        self.startTime = time.time()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(LVMChk, self).tearDown()
        global real_device
        if real_device is not None:
            if islvm_accelerated(real_device):
                deaccelerate_dev("/dev/%s" % real_device, tc = self)
            self.flush()
            delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, 
                            self.primary_volume, tc = self)
            real_device = None


    def test_1(self):
        """
        Create LVM volume from given Primary volume
        size of LVM in GB
        """
        global real_device
        if chk_lvm_inconfig(random.choice(PRIMARY_VOLUMES)):
            real_device = None
            do_skip(self, 'Lvm volume is given for lvm testing')
        else:
            size = 1
            create_lvmdevice(VG, LV, size, 
                            self.primary_volume, tc = self)
            volume = "/dev/mapper/%s-%s" % (VG, LV)
            real_device = get_devicename(volume, self)
            primary_volume = "/dev/%s" % real_device

            for policy in WRITE_POLICY:
                for s in cbqaconfig['TEST_BSIZES']:
                    bsize = 1 << s
                    dev_blksz = get_devblksz(self.primary_volume)
                    if bsize > dev_blksz:
                        continue
                    acceleratedev(primary_volume, self.ssd_volume, \
                        bsize, self, write_policy = policy, mode = "monitor")
                    uuid_flag = get_uuid_flag(primary_volume)
                    self.assertEqual(uuid_flag[0], "*")
                    chk_btd(real_device, uuid_flag[1], self)
                    accelerateregion(self, primary_volume, 1)
                    count = chk_bitmapcount(primary_volume)
                    self.assertEqual(int(count), 1)
                    first_stat = getxstats(primary_volume)
                    for j in range(0, 5):
                        lmddreadfromdev(primary_volume, bsize, 30000, j)
                        self.flush()
                        stat = getxstats(primary_volume)
                        if policy == "read-around":
                            break
                        self.assertTrue((stat['cs_readpopulate_flow']) > \
                                        (first_stat['cs_readpopulate_flow']))
                    deaccelerate_dev(primary_volume, tc = self)
                if islvm_accelerated(real_device):
                    deaccelerate_dev("/dev/%s" % real_device, tc = self)


    def test_2(self):
        global real_device
        if chk_lvm_inconfig(random.choice(PRIMARY_VOLUMES)):
            do_skip(self, 'Lvm volume is given for lvm testing')
        else:
            for policy in WRITE_POLICY:
                size = 1
                create_lvmdevice(VG, LV, size, self.primary_volume, tc = self)
                volume = "/dev/mapper/%s-%s" % (VG, LV)
                real_device = get_devicename(volume, self)
                primary_volume = "/dev/%s" % real_device
                for x in range(0, 2):
                    for s in cbqaconfig['TEST_BSIZES']:
                        bsize = 1 << s
                        acceleratedev(primary_volume, self.ssd_volume, bsize, self, \
                                    write_policy = policy, mode = "monitor")
                        accelerateregion(self, primary_volume, 1)
                        count = chk_bitmapcount(primary_volume)
                        self.assertEqual(int(count), 1)
                        deaccel_duringIO(self, primary_volume)
                if islvm_accelerated(real_device):
                    deaccelerate_dev(primary_volume, tc=self)
                self.flush()
                time.sleep(10)
                delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, \
                            self.primary_volume, tc = self)



"""
creating an LVM volume making a filesystem
Accelearting LVM volume using different block size and 
Doing reads on the volume and Cross checking CB stats
"""
class LVM_WithMKFS(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(LVM_WithMKFS, self).setUp()
        self.startTime = time.time()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(LVM_WithMKFS, self).tearDown()
        global real_device
        if real_device != None:
            if islvm_accelerated(real_device):
                deaccelerate_dev("/dev/%s" % real_device, tc = self)
            if is_mounted("%stest" % mountdir):
                do_unmount("%stest" % mountdir, self)
            self.flush()
            delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, \
                        self.primary_volume, tc = self)
            real_device = None


    def test_1(self):
        """
        Create LVM volume from given Primary volume
        size of LVM in GB
        """
        global real_device
        if chk_lvm_inconfig(self.primary_volume):
            do_skip(self, 'Simple Volume or Partition volume needed')
        else:
            for policy in WRITE_POLICY:
                for s in cbqaconfig['TEST_BSIZES']:
                    bsize = 1 << s
                    size = 1
                    create_lvmdevice(VG, LV, size, \
                                        self.primary_volume, tc = self)
                    volume = "/dev/mapper/%s-%s" % (VG, LV)
                    real_device = get_devicename(volume, self)
                    primary_volume = "/dev/%s" % real_device
                    if bsize != 512:
                        do_mkfs(primary_volume, bsize, self)
                    else:
                        do_mkfs(primary_volume, "default", self)

                    do_mkdir("%stest" % mountdir, self)
                    do_mount(primary_volume, "%stest" % mountdir, self)
                    acceleratedev(primary_volume, self.ssd_volume, bsize, self, \
                                    write_policy = policy, mode = "monitor")
                    uuid_flag = get_uuid_flag(primary_volume)
                    self.assertEqual(uuid_flag[0], "*")
                    chk_btd(real_device, uuid_flag[1], self)
                    accelerateregion(self, primary_volume, 1)
                    count = chk_bitmapcount(primary_volume)
                    self.assertEqual(int(count), 1)
                    first_stat = getxstats(primary_volume)
                    for j in range(0, 5):
                        lmddreadfromdev(primary_volume, bsize, 30000, j)
                        self.flush()
                        stat = getxstats(primary_volume)
                        if policy == "read-around":
                            break
                        self.assertTrue((stat['cs_readpopulate_flow']) > \
                                        (first_stat['cs_readpopulate_flow']))
                    deaccelerate_dev(primary_volume, tc = self)
                    self.flush()
                    time.sleep(10)
                    if is_mounted("%stest" % mountdir):
                        do_unmount("%stest" % mountdir, self)
                    delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, \
                                 self.primary_volume, tc = self)



    def test_2(self):
        global real_device
        if chk_lvm_inconfig(self.primary_volume):
            do_skip(self, 'Simple Volume or Partition volume needed')
        else:
            for policy in WRITE_POLICY:
                size = 1
                create_lvmdevice(VG, LV, size, self.primary_volume, tc = self)
                volume = "/dev/mapper/%s-%s" % (VG, LV)
                real_device = get_devicename(volume, self)
                primary_volume = "/dev/%s" % real_device
                for x in range(0, 2):
                    for s in cbqaconfig['TEST_BSIZES']:
                        bsize = 1 << s
                        if bsize != 512:
                            do_mkfs(primary_volume, bsize, self)
                        else:
                            do_mkfs(primary_volume, "default", self)
                        do_mkdir("%stest" % mountdir, self)
                        do_mount(primary_volume, "%stest" % mountdir, self)
                        acceleratedev(primary_volume, self.ssd_volume, bsize, self, \
                                    write_policy = policy, mode = "monitor")
                        accelerateregion(self, primary_volume, 1)
                        count = chk_bitmapcount(primary_volume)
                        self.assertEqual(int(count), 1)
                        deaccel_duringIO(self, primary_volume)
                    if islvm_accelerated(real_device):
                        deaccelerate_dev(primary_volume, tc=self)
                    self.flush()
                    if is_mounted("%stest" % mountdir):
                        do_unmount("%stest" % mountdir, self)
                if islvm_accelerated(real_device):
                    deaccelerate_dev(primary_volume, tc=self)
                self.flush()
                time.sleep(10)
                if is_mounted("%stest" % mountdir):
                    do_unmount("%stest" % mountdir, self)
                delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, \
                       self.primary_volume, tc = self)



"""
Creating RAID1 volume using MDADM command
Accelearting volume using different block size and 
Doing reads on the volume and Cross checking CB stats
"""
class RAIDchk(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(RAIDchk, self).setUp()
        if len(PRIMARY_VOLUMES) < 2:
            logger.info("nedd two primary volume to run the test")
        else:
            self.primary_volume = PRIMARY_VOLUMES[0]
            self.primary_volume_2 = PRIMARY_VOLUMES[1]
            self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(RAIDchk, self).tearDown()
        global real_device
        if real_device != None:
            if isdev_accelerated("/dev/md0"):
                deaccelerate_dev("/dev/md0", tc=self)
            delete_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)
            real_device = None


    def test_1(self):
        global real_device
        if os.system('which mdadm > /dev/null') != 0:
            do_skip(self, 'RAIN run requires mdadm to be installed. skipping.')
        elif len(PRIMARY_VOLUMES) < 2:
            do_skip(self, 'need to have two primary_volume to run this test')
        else:
            create_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)
            primary_volume = "/dev/md0"
            real_device = get_devicename(primary_volume, self)
            for policy in WRITE_POLICY:
                for s in cbqaconfig['TEST_BSIZES']:
                    bsize = 1 << s
                    dev_blksz = get_devblksz(self.primary_volume)
                    if bsize > dev_blksz:
                        continue
                    acceleratedev(primary_volume, self.ssd_volume, bsize, self, \
                                write_policy = policy, mode = "monitor")
                    uuid_flag = get_uuid_flag(primary_volume)
                    self.assertEqual(uuid_flag[0], "*")
                    chk_btd(real_device, uuid_flag[1], self)
                    accelerateregion(self, primary_volume, 1)
                    count = chk_bitmapcount(primary_volume)
                    self.assertEqual(int(count), 1)
                    first_stat = getxstats(primary_volume)
                    for j in range(0, 5):
                        lmddreadfromdev(primary_volume, bsize, 30000, j)
                        self.flush()
                        stat = getxstats(primary_volume)
                        if policy == 'read-around':
                            break
                        self.assertTrue((stat['cs_readpopulate_flow']) > \
                                        (first_stat['cs_readpopulate_flow']))
                    deaccelerate_dev(primary_volume, tc = self)
                    if isdev_accelerated(primary_volume):
                        deaccelerate_dev(primary_volume, tc=self)
                    time.sleep(10)


    def test_2(self):
        global real_device
        if os.system('which mdadm > /dev/null') != 0:
            do_skip(self, 'RAIN run requires mdadm to be installed. skipping.')
        elif len(PRIMARY_VOLUMES) < 2:
            do_skip(self, 'need to have two primary_volume to run this test')
        else:
            for policy in WRITE_POLICY:
                create_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)
                primary_volume = "/dev/md0"
                real_device = get_devicename(primary_volume, self)
                for x in range(0, 2):
                    for s in cbqaconfig['TEST_BSIZES']:
                        bsize = 1 << s
                        acceleratedev(primary_volume, self.ssd_volume, bsize, self, \
                                    write_policy = policy, mode = "monitor")
                        accelerateregion(self, primary_volume, 1)
                        count = chk_bitmapcount(primary_volume)
                        self.assertEqual(int(count), 1)
                        deaccel_duringIO(self, primary_volume)
                    if isdev_accelerated(primary_volume):
                        deaccelerate_dev(primary_volume, tc=self)
                    time.sleep(10)
                delete_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)



"""
creating an RAID volume making a filesystem
Accelearting RAID volume using different block size and 
Doing reads on the volume and Cross checking CB stats
"""
class RAID_WithMKFS(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(RAID_WithMKFS, self).setUp()
        if len(PRIMARY_VOLUMES) < 2:
            logger.info("nedd two primary volume to run the test")
        else:
            self.primary_volume = PRIMARY_VOLUMES[0]
            self.primary_volume_2 = PRIMARY_VOLUMES[1]
            self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(RAID_WithMKFS, self).tearDown()
        global real_device
        if real_device != None:
            if isdev_accelerated("/dev/md0"):
                deaccelerate_dev("/dev/md0", tc=self)
            if is_mounted("%stest" % mountdir):
                do_unmount("%stest" % mountdir, self)
            delete_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)
        real_device = None


    def test_1(self):
        global real_device
        if os.system('which mdadm > /dev/null') != 0:
            do_skip(self, 'RAID run requires mdadm to be installed. skipping.')
        elif len(PRIMARY_VOLUMES) < 2:
            do_skip(self, 'need to have two primary_volume to run this test')
        else:
            for policy in WRITE_POLICY:
                for s in cbqaconfig['TEST_BSIZES']:
                    bsize = 1 << s
                    dev_blksz = get_devblksz(self.primary_volume)
                    if bsize > dev_blksz:
                        continue
                    create_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)
                    primary_volume = "/dev/md0"
                    real_device = get_devicename(primary_volume, self)
                    if bsize != 512:
                        do_mkfs(primary_volume, bsize, self)
                    else:
                        do_mkfs(primary_volume, "default", self)
                    do_mkdir("%stest" % mountdir, self)
                    do_mount(primary_volume, "%stest" % mountdir, self)
                    acceleratedev(primary_volume, self.ssd_volume, bsize, self, \
                                write_policy = policy, mode = "monitor")
                    uuid_flag = get_uuid_flag(primary_volume)
                    self.assertEqual(uuid_flag[0], "*")
                    chk_btd(real_device, uuid_flag[1], self)
                    accelerateregion(self, primary_volume, 1)
                    count = chk_bitmapcount(primary_volume)
                    self.assertEqual(int(count), 1)
                    first_stat = getxstats(primary_volume)
                    for j in range(0, 5):
                        lmddreadfromdev(primary_volume, bsize, 30000, j)
                        self.flush()
                        stat = getxstats(primary_volume)
                        if policy == "read-around":
                            break
                        self.assertTrue((stat['cs_readpopulate_flow']) > \
                                        (first_stat['cs_readpopulate_flow']))
                    deaccelerate_dev(primary_volume, tc = self)
                    if isdev_accelerated("/dev/md0"):
                        deaccelerate_dev("/dev/md0", tc=self)
                    time.sleep(10)
                    if is_mounted("%stest" % mountdir):
                        do_unmount("%stest" % mountdir, self)
                    delete_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)


    def test_2(self):
        global real_device
        if os.system('which mdadm > /dev/null') != 0:
            do_skip(self, 'RAID run requires mdadm to be installed. skipping.')
        elif len(PRIMARY_VOLUMES) < 2:
            do_skip(self, 'need to have two primary_volume to run this test')
        else:
            for policy in WRITE_POLICY:
                create_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)
                primary_volume = "/dev/md0"
                real_device = get_devicename(primary_volume, self)
                for x in range(0, 2):
                    for s in cbqaconfig['TEST_BSIZES']:
                        bsize = 1 << s
                        if bsize != 512:
                            do_mkfs(primary_volume, bsize, self)
                        else:
                            do_mkfs(primary_volume, "default", self)
                        do_mkdir("%stest" % mountdir, self)
                        do_mount(primary_volume, "%stest" % mountdir, self)
                        acceleratedev(primary_volume, self.ssd_volume, bsize, self, \
                                        write_policy = policy, mode = "monitor")
                        accelerateregion(self, primary_volume, 1)
                        count = chk_bitmapcount(primary_volume)
                        self.assertEqual(int(count), 1)
                        deaccel_duringIO(self, primary_volume)
                    if isdev_accelerated(primary_volume):
                        deaccelerate_dev(primary_volume, tc=self)
                    if is_mounted("%stest" % mountdir):
                        do_unmount("%stest" % mountdir, self)
                if isdev_accelerated(primary_volume):
                    deaccelerate_dev(primary_volume, tc=self)
                time.sleep(10)
                if is_mounted("%stest" % mountdir):
                    do_unmount("%stest" % mountdir, self)
                delete_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)


if __name__ == '__main__':
     unittest.main(argv=["dynamic_chk.py"] + args)



