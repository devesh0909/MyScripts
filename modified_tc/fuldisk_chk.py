import sys
import getopt
import os
import random
import subprocess
import tempfile
import unittest
import time
import common_utils

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

WRITE_POLICY = ['write-back', 'write-through', 'write-around']

class Fuldisk_utils(object):

    @staticmethod
    def do_dd(*args):
        primary_volume = "".join(args)
        dodd(inf = primary_volume, of = "/dev/zero", bs = "4096", count = 30000)

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

do_dd = Fuldisk_utils.do_dd
deaccel_duringIO = Fuldisk_utils.deaccel_duringIO
islvm_accelerated = Fuldisk_utils.islvm_accelerated
chk_lvm_inconfig = Fuldisk_utils.chk_lvm_inconfig


"""
Accelerating a device using different block size and 
Doing reads without doing mkfs and cross checking CB stats 
"""
class FullDiskCheck(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(FullDiskCheck, self).setUp()
        self.startTime = time.time()
        self.pvn1 = random.choice(PRIMARY_VOLUMES)
        self.svn1 = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(FullDiskCheck, self).tearDown()
        if isdev_accelerated(self.pvn1):
            deaccelerate_dev(self.pvn1, tc=self)


    def test_1(self):
        for policy in WRITE_POLICY:
            for s in cbqaconfig['TEST_BSIZES']:
                bsize = 1 << s
                dev_blksz = get_devblksz(self.pvn1)
                if bsize > dev_blksz:
                    continue
                acceleratedev(self.pvn1, self.svn1, bsize, self, \
                            write_policy = policy)
                first_stat = getxstats(self.pvn1)
                for j in range(0, 5):
                    lmddreadfromdev(self.pvn1, bsize, 30000, j)
                    self.flush()
                    stat = getxstats(self.pvn1)
                    self.assertTrue((stat['cs_readpopulate_flow']) >
                                    (first_stat['cs_readpopulate_flow']))
                deaccelerate_dev(self.pvn1, tc = self)
            do_pass(self, 'test_fulldisk_%s' %bsize)


    '''
    Deaccelerate the device when io is going on the device
    '''
    def test_2(self):
        for policy in WRITE_POLICY:
            for x in range(0, 2):
                for s in cbqaconfig['TEST_BSIZES']:
                    bsize = 1 << s
                    acceleratedev(self.pvn1, self.svn1, bsize, self, \
                                       write_policy = policy)
                    deaccel_duringIO(self, self.pvn1)
            if isdev_accelerated(self.pvn1):
                deaccelerate_dev(self.pvn1, tc=self)


"""
Creating a filsystem on HDD volume
Accelearting a device using different block size and 
Doing reads on device and Cross checking CB stats
"""
class FDWithMkfs(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(FDWithMkfs, self).setUp()
        self.startTime = time.time()
        self.pvn1 = random.choice(PRIMARY_VOLUMES)
        self.svn1 = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(FDWithMkfs, self).tearDown()
        if isdev_accelerated(self.pvn1):
            deaccelerate_dev(self.pvn1, tc=self)
        if is_mounted("%stest" % mountdir):
            do_unmount("%stest" % mountdir, self)


    def test_1(self):
        for policy in WRITE_POLICY:
            for s in cbqaconfig['TEST_BSIZES']:
                bsize = 1 << s
                dev_blksz = get_devblksz(self.pvn1)
                if bsize > dev_blksz:
                    continue
                if bsize != 512:
                    do_mkfs(self.pvn1, bsize, self)
                else:
                    do_mkfs(self.pvn1, "default", self)
                do_mkdir("%stest" % mountdir, self)
                do_mount(self.pvn1, "%stest" % mountdir, self)

                acceleratedev(self.pvn1, self.svn1, bsize, self, \
                            write_policy = policy)

                first_stat = getxstats(self.pvn1)
                for j in range(0, 5):
                    lmddreadfromdev(self.pvn1, bsize, 30000, j)
                    self.flush()
                    stat = getxstats(self.pvn1)
                    self.assertTrue((stat['cs_readpopulate_flow']) >
                                    (first_stat['cs_readpopulate_flow']))
                deaccelerate_dev(self.pvn1, tc = self)
                do_unmount("%stest" % mountdir, self)
            do_pass(self, 'test_fulldisk_%sbs' % bsize)


    '''
    Deaccelerate the device when io is going on the device with all the three mode
    '''
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
                                       write_policy = policy)
                    deaccel_duringIO(self, self.pvn1)
                    do_unmount("%stest" % mountdir, self)
            if isdev_accelerated(self.pvn1):
                deaccelerate_dev(self.pvn1, tc=self)
            if is_mounted("%stest" % mountdir):
                do_unmount("%stest" % mountdir, self)


"""
Accelearting LVM volume using different block size and 
Doing reads on the volume and Cross checking CB stats
"""
class LVMAcceleration(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(LVMAcceleration, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(LVMAcceleration, self).tearDown()
        global real_device
        if real_device is not None:
            if islvm_accelerated(real_device):
                deaccelerate_dev("/dev/%s" % (real_device), tc = self)
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
            do_skip(self, 'Lvm volume is given for lvm testing')
        else:
            size = 1
            create_lvmdevice(VG, LV, size,
                             self.primary_volume, tc = self)
            volume = "/dev/mapper/%s-%s" % (VG, LV)
            real_device = get_devicename(volume, self)
            primary_volume = "/dev/%s" % (real_device)
            for policy in WRITE_POLICY:
                for s in cbqaconfig['TEST_BSIZES']:
                    bsize = 1 << s
                    dev_blksz = get_devblksz(self.primary_volume)
                    if bsize > dev_blksz:
                        continue
                    acceleratedev(primary_volume, self.ssd_volume, bsize,
                                  self, write_policy = policy)

                    first_stat = getxstats(primary_volume)

                    for j in range(0, 5):
                        lmddreadfromdev(primary_volume, bsize, 30000, j)
                        self.flush()
                        stat = getxstats(primary_volume)

                        self.assertTrue((stat['cs_readpopulate_flow']) >
                                        (first_stat['cs_readpopulate_flow']))

                    deaccelerate_dev(primary_volume, tc = self)
                    self.flush()
                    time.sleep(10)


    '''
    Deaccelerate the device when io is going on the device with all the three mode
    '''
    def test_2(self):
        global real_device
        if chk_lvm_inconfig(random.choice(PRIMARY_VOLUMES)):
            do_skip(self, 'Lvm volume is given for lvm testing')
        else:
            for policy in WRITE_POLICY:
                size = 1
                create_lvmdevice(VG, LV, size,
                                 self.primary_volume, tc = self)
                volume = "/dev/mapper/%s-%s" % (VG, LV)
                real_device = get_devicename(volume, self)
                primary_volume = "/dev/%s" % real_device
                for x in range(0, 2):
                    for s in cbqaconfig['TEST_BSIZES']:
                        bsize = 1 << s
                        acceleratedev(primary_volume, self.ssd_volume, bsize, self, \
                                    write_policy = policy)
                        deaccel_duringIO(self, primary_volume)
                    if islvm_accelerated(real_device):
                        deaccelerate_dev(primary_volume, tc = self)
                self.flush()
                time.sleep(10)
                delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, \
                        self.primary_volume, tc = self)


"""
creating an LVM volume making a filesystem
Accelearting LVM volume using different block size and 
Doing reads on the volume and Cross checking CB stats
"""
class LVMWithMKFS(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(LVMWithMKFS, self).setUp()
        self.startTime = time.time()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(LVMWithMKFS, self).tearDown()
        global real_device
        if real_device is not None:
            if islvm_accelerated(real_device):
                deaccelerate_dev("/dev/%s" % (real_device), tc = self)
            if is_mounted("%stest" % mountdir):
                do_unmount("%stest" % mountdir, self)
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
                    dev_blksz = get_devblksz(self.primary_volume)
                    if bsize > dev_blksz:
                        continue

                    size = 1
                    create_lvmdevice(VG, LV, size,
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
                                write_policy = policy)

                    first_stat = getxstats(primary_volume)

                    for j in range(0, 5):
                        lmddreadfromdev(primary_volume, bsize, 30000, j)
                        self.flush()
                        stat = getxstats(primary_volume)
                        self.assertTrue((stat['cs_readpopulate_flow'])
                                        > (first_stat['cs_readpopulate_flow']))
                    deaccelerate_dev(primary_volume, tc = self)
                    self.flush()
                    time.sleep(10)
                    do_unmount("%stest" % mountdir, self)
                    delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV),
                                     VG, self.primary_volume, tc = self)


    '''
    Deaccelerate the device when io is going on the device with all the three mode
    '''
    def test_2(self):
        global real_device
        if chk_lvm_inconfig(self.primary_volume):
            do_skip(self, 'Simple Volume or Partition volume needed')
        else:
            for policy in WRITE_POLICY:
                size = 1
                create_lvmdevice(VG, LV, size, \
                                self.primary_volume, tc = self)
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
                        acceleratedev(primary_volume, self.ssd_volume, bsize, \
                                    self, write_policy = policy)
                        deaccel_duringIO(self, primary_volume)

                    if islvm_accelerated(real_device):
                        deaccelerate_dev(primary_volume, tc=self)
                    self.flush()
                    time.sleep(10)
                    if is_mounted("%stest" % mountdir):
                        do_unmount("%stest" % mountdir, self)
                self.flush()
                time.sleep(10)
                delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, \
                            self.primary_volume, tc = self)


"""
Creating RAID1 volume using MDADM command
Accelearting volume using different block size and 
Doing reads on the volume and Cross checking CB stats
"""
class RAIDAcceleration(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(RAIDAcceleration, self).setUp()
        if len(PRIMARY_VOLUMES) < 2:
            logger.info("nedd two primary volume to run the test")
        else:
            self.primary_volume = PRIMARY_VOLUMES[0]
            self.primary_volume_2 = PRIMARY_VOLUMES[1]
            self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(RAIDAcceleration, self).tearDown()
        global real_device
        if real_device is not None:
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

                    acceleratedev(primary_volume, self.ssd_volume, bsize, self,
                                  write_policy = policy)

                    first_stat = getxstats(primary_volume)

                    for j in range(0, 5):
                        lmddreadfromdev(primary_volume, bsize, 30000, j)
                        self.flush()
                        stat = getxstats(primary_volume)

                        self.assertTrue((stat['cs_readpopulate_flow']) >
                                        (first_stat['cs_readpopulate_flow']))
                    deaccelerate_dev(primary_volume, tc = self)
                    self.flush()
                    time.sleep(10)


    '''
    Deaccelerate the device when io is going on the device with all the three mode
    '''
    def test_2(self):
        global real_device
        if os.system('which mdadm > /dev/null') != 0:
            do_skip(self, 'RAIN run requires mdadm to be installed. skipping.')
        elif len(PRIMARY_VOLUMES) < 2:
            do_skip(self, 'need to have two primary_volume to run this test')
        else:
            for policy in WRITE_POLICY:
                create_raiddevice(self.primary_volume, self.primary_volume_2, tc=self)
                primary_volume = "/dev/md0"
                real_device = get_devicename(primary_volume, self)
                for x in range(0, 2):
                    for s in cbqaconfig['TEST_BSIZES']:
                        bsize = 1 << s
                        acceleratedev(primary_volume, self.ssd_volume, bsize, \
                                    self, write_policy = policy)
                        deaccel_duringIO(self, primary_volume)
                    if isdev_accelerated(primary_volume):
                        deaccelerate_dev(primary_volume, tc=self)
                self.flush()
                time.sleep(10)
                delete_raiddevice(self.primary_volume, self.primary_volume_2, \
                        tc = self)


"""
creating an RAID volume making a filesystem
Accelearting RAID volume using different block size and 
Doing reads on the volume and Cross checking CB stats
"""
class RAIDWithMKFS(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(RAIDWithMKFS, self).setUp()
        if len(PRIMARY_VOLUMES) < 2:
            logger.info("nedd two primary volume to run the test")
        else:
            self.primary_volume = PRIMARY_VOLUMES[0]
            self.primary_volume_2 = PRIMARY_VOLUMES[1]
            self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(RAIDWithMKFS, self).tearDown()
        global real_device
        if real_device is not None:
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
                    create_raiddevice(self.primary_volume, self.primary_volume_2, \
                                    tc = self)
                    primary_volume = "/dev/md0"
                    real_device = get_devicename(primary_volume, self)
                    if bsize != 512:
                        do_mkfs(primary_volume, bsize, self)
                    else:
                        do_mkfs(primary_volume, "default", self)

                    do_mkdir("%stest" % mountdir, self)
                    do_mount(primary_volume, "%stest" % mountdir, self)

                    acceleratedev(primary_volume, self.ssd_volume, bsize,
                                  self, write_policy = policy)

                    first_stat = getxstats(primary_volume)
                    for j in range(0, 5):
                        lmddreadfromdev(primary_volume, bsize, 30000, j)
                        self.flush()
                        stat = getxstats(primary_volume)
                        self.assertTrue((stat['cs_readpopulate_flow']) > \
                                        (first_stat['cs_readpopulate_flow']))

                    deaccelerate_dev(primary_volume, tc = self)
                    do_unmount("%stest" % mountdir, self)
                    self.flush()
                    time.sleep(10)
                    delete_raiddevice(self.primary_volume, self.primary_volume_2, \
                                        tc = self)


    '''
    Deaccelerate the device when io is going on the device with all the three mode
    '''
    def test_2(self):
        global real_device
        if os.system('which mdadm > /dev/null') != 0:
            do_skip(self, 'RAID run requires mdadm to be installed. skipping.')
        elif len(PRIMARY_VOLUMES) < 2:
            do_skip(self, 'need to have two primary_volume to run this test')
        else:
            for policy in WRITE_POLICY:
                create_raiddevice(self.primary_volume, self.primary_volume_2, \
                                tc = self)
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
                                    write_policy = policy)
                        deaccel_duringIO(self, primary_volume)
                        if is_mounted("%stest" % mountdir):
                            do_unmount("%stest" % mountdir, self)
                    if isdev_accelerated(primary_volume):
                        deaccelerate_dev(primary_volume, tc=self)
                    if is_mounted("%stest" % mountdir):
                        do_unmount("%stest" % mountdir, self)
                self.flush()
                time.sleep(10)
                delete_raiddevice(self.primary_volume, self.primary_volume_2, \
                            tc = self)


if __name__ == '__main__':
    unittest.main(argv=["fuldisk_chk.py"] + args)

