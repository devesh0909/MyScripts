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
import time
import unittest
import datetime

from common_utils import *
from cblog import *
from multiprocessing import Process

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)


real_device = None
WRITE_POLICY = ['write-back', 'write-through', 'write-around', 'read-around']

class Utils(object):

    """
    This method is used to check partition file is given in config
    """
    @staticmethod
    def chk_partition_inconfig(device):
        device_detail = device.split('/')[-1]
        return os.path.exists("/sys/class/block/%s/device" % device_detail)


    """
    This method is used to check lvm file is given in config
    """
    @staticmethod
    def chk_lvm_inconfig(device):
        try:
            ss = os.readlink(device)
            return "True"
        except:
            device_detail = device.split('/')[-1]
            return os.path.exists("/sys/class/block/%s/dm" % device_detail)


    @staticmethod
    def islvm_accelerated(device):
        cmd = "cachebox -l | grep %s > /dev/null" % device
        r = os.system(cmd)
        return (1 if r == 0 else 0)


chk_partition_inconfig = Utils.chk_partition_inconfig
chk_lvm_inconfig = Utils.chk_lvm_inconfig
islvm_accelerated = Utils.islvm_accelerated


"""
Accelerate the partition, delete the partition during acceleration
Recreate the partition with the same details
It Will not allow the acceleration on the newly created volume
"""
class AccelerationOnDeletedpartition(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(AccelerationOnDeletedpartition, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.device = self.primary_volume
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        checkdev(devname=self.primary_volume, tc=self)
        checkdev(devname=self.ssd_volume, tc=self)


    def tearDown(self):
        super(AccelerationOnDeletedpartition, self).tearDown()
        global real_device
        if real_device is not None:
            if isdev_accelerated(self.primary_volume):
                deaccelerate_dev(self.primary_volume, tc=self)
                self.flush()
            delete_partition(self.device, tc = self)
            alter_table(self.device, tc = self)
            real_device = None


    def do_acc(self, policies, primary_volume):
        '''
        accelerate the partitions and set the fulldisk policies on it
        '''
        accelerate_dev(primary_volume, self.ssd_volume, 4096, \
                      self, write_policy = policies)
        delete_partition(self.device, tc = self)
        create_partition(self.device, tc = self)
        output = accelerate_dev(primary_volume, self.ssd_volume, \
                 4096, self, debug = True, write_policy = policies)
        self.assertNotEqual(output, 0)


    def test_1(self):
        global real_device
        if not chk_partition_inconfig(self.primary_volume):
            do_skip(self, 'Partition or lvm volume is given for testing')
        else:
            for policy in WRITE_POLICY:
                real_device = get_devicename(self.primary_volume, self)
                self.primary_volume = self.device+"1"
                create_partition(self.device, tc = self)
                self.do_acc(policy, self.primary_volume)
                deaccelerate_dev(self.primary_volume, tc = self)
                delete_partition(self.device, tc = self)
                alter_table(self.device, tc = self)


"""
Create a partition of HDD
Accelerate the partition and delete the partition when \
acceleration is in progress. 
The Partition should not be Deleted
"""
class DeletePartitionduringacceleration(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(DeletePartitionduringacceleration, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.device = self.primary_volume
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        checkdev(devname=self.primary_volume, tc=self)
        checkdev(devname=self.ssd_volume, tc=self)


    def tearDown(self):
        super(DeletePartitionduringacceleration, self).tearDown()
        global real_device
        if real_device is not None:
            if isdev_accelerated(self.primary_volume):
                deaccelerate_dev(self.primary_volume, tc=self)
                self.flush()
            delete_partition(self.device, tc = self)
            alter_table(self.device, tc = self)
            real_device = None


    """
    This method parrallely accelerate and try to delete the partition
    """
    def do_accelerate(self, primary_volume, *args):
        policy = "".join(args)
        accelerate_dev(primary_volume, self.ssd_volume, 4096, \
                      tc = self, write_policy = policy)


    """
    This method is used to delete the partition of primary volume
    """
    def delete_partition_volume(self):
        time.sleep(16)
        cmd = [
            "fdisk",
            "%s" % self.device
            ]
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdin = subprocess.PIPE, \
                    stdout = subprocess.PIPE, stderr = subprocess.PIPE)

        process_1.stdin.write("d\n")
        process_1.stdin.write("\n")
        process_1.stdin.write("\n")
        process_1.stdin.write("w\n")

        out, err = process_1.communicate()
        logger.debug("partition deleted %s %s" % (out, err))
        self.assertNotEqual(process_1.returncode, 0)


    def test_1(self):
        global real_device
        if not chk_partition_inconfig(self.primary_volume):
            do_skip(self, 'Partition or lvm volume is given for testing')
        else:
            for policy in WRITE_POLICY:
                self.primary_volume = self.device+"1"
                create_partition(self.device, tc = self)
                #Calling two process at a single time using multi processing
                process_1 = Process(target = self.do_accelerate, args = (self.primary_volume, policy))
                process_1.start()
                process_2 = Process(target = self.delete_partition_volume)
                process_2.start()
                process_1.join()
                process_2.join()
                deaccelerate_dev(self.primary_volume, tc = self)
                delete_partition(self.device, tc = self)
                alter_table(self.device, tc = self)


"""
Create an LVM,
Accelerate LVM, delete LVM when Acceleration is in progress
"""
class DeleteLVMduringacceleration(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(DeleteLVMduringacceleration, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        #size of LVM in GB
        self.size = 1
        #Check if the devices in config.py are already existing
        checkdev(devname=self.primary_volume, tc=self)
        checkdev(devname=self.ssd_volume, tc=self)


    def tearDown(self):
        super(DeleteLVMduringacceleration, self).tearDown()
        global real_device
        if real_device is not None:
            if islvm_accelerated(real_device):
                deaccelerate_dev(self.primary_volume, tc=self)
                self.flush()
            delete_lvmdevice("vol_grp1", "logical_vol1", self.primary_volume, tc = self)
            real_device = None


    def do_test(self, *args):
        policy = "".join(args)
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, \
                        tc = self, write_policy = policy)

    """
    Remove logical volume
    """
    def remove_logical_volume(self):
        self.flush()
        time.sleep(20)
        cmd = [
            "lvremove",
            "-f",
            "/dev/vol_grp1/logical_vol1"
            ]
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE)
        out, err = process_1.communicate()
        logger.debug("%s %s" % (out, err))
        self.assertNotEqual(process_1.returncode, 0)


    def test_1(self):
        global real_device
        if chk_lvm_inconfig(self.primary_volume):
            do_skip(self, 'Lvm volume is given for lvm testing')
        else:
            for policies in WRITE_POLICY:
                create_lvmdevice("vol_grp1", "logical_vol1", self.size, \
                        self.primary_volume, tc = self)
                volume = "/dev/vol_grp1/logical_vol1"
                real_device = get_devicename(volume, self)
                self.primary_volume = "/dev/%s" % (real_device)
                #Calling two process at a single time using multi processing
                process_1 = Process(target = self.do_test, args = policies)
                process_1.start()
                process_2 = Process(target = self.remove_logical_volume)
                process_2.start()
                process_1.join()
                process_2.join()
                deaccelerate_dev(self.primary_volume, tc=self)
                delete_lvmdevice("vol_grp1", "logical_vol1", self.primary_volume, tc = self)


"""
create a RAID volume, accelerate the RAID volume
and delete the RAID volume during acceleration
"""
class Delete_RAIDduringacceleration(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(Delete_RAIDduringacceleration, self).setUp()
        if len(PRIMARY_VOLUMES) < 2 :
            self.skipTest("need to have two primary_volume to run this test")
        self.primary_volume = PRIMARY_VOLUMES[0]
        self.primary_volume_2 = PRIMARY_VOLUMES[1]
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        #Check if the devices in config.py are already existing
        checkdev(devname=self.primary_volume, tc=self)
        checkdev(devname=self.ssd_volume, tc=self)


    def tearDown(self):
        super(Delete_RAIDduringacceleration, self).tearDown()
        if isdev_accelerated("/dev/md0"):
            deaccelerate_dev("/dev/md0", tc=self)

        delete_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)
        net_time = time.time() - self.startTime
        logger.debug("\nDONE: %s: %.3f" % (self.id(), net_time))


    """
    It stop the RAID volume
    then remove the RAID volume and delete the superblock 
    from all drives in the array
    """
    def delete_RAID(self):
        time.sleep(10)
        cmd = ("mdadm --stop /dev/md0")
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE, shell = True)
        out, err = process_1.communicate()
        logger.debug("%s %s", (out, err))
        self.assertNotEqual(process_1.returncode, 0)


        cmd2 = ("mdadm --remove /dev/md0")
        logger.debug(cmd2)
        process_2 = subprocess.Popen(cmd2, stdout = subprocess.PIPE, shell=True, \
                    stderr = subprocess.PIPE)

        cmd3 = ("mdadm --zero-superblock %s %s" % (self.primary_volume, self.primary_volume_2))
        logger.debug(cmd3)
        process_3 = subprocess.Popen(cmd3, stdout = subprocess.PIPE, shell=True, \
                    stderr = subprocess.PIPE)
        out, err = process_3.communicate()
        self.assertNotEqual(process_3.returncode, 0)


    def accelerate(self, *args):
        create_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)
        policy = "".join(args)
        accelerate_dev("/dev/md0", self.ssd_volume, 4096, tc = self, \
                        write_policy = policy)


    def test_1(self):
        for policy in WRITE_POLICY:
            process_1 = Process(target=self.accelerate, args=(policy))
            process_1.start()
            process_2 = Process(target=self.delete_RAID)
            process_2.start()
            process_1.join()
            process_2.join()
            deaccelerate_dev("/dev/md0", tc = self)
            delete_raiddevice(self.primary_volume, self.primary_volume_2, tc = self)


"""
Accelerating the Primary volume and 
checking whether read or write is going on SSD
"""
class ExternIOonSSD(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(ExternIOonSSD, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(ExternIOonSSD, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    """
    Accelerating the HDD volume with SSD
    Doing Reading and writing from SSD
    """
    def test_1(self):
        for policies in WRITE_POLICY:
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, \
                           tc=self, write_policy = policies)
            #Writing into SSD
            r = dodd(inf = "/dev/zero", of = self.ssd_volume, bs = "4k", count = 4000)
            self.assertNotEqual(r, 0)

            #reading from SSD
            r = dodd(inf = self.ssd_volume, of = "/dev/null", bs = "4k", count = 4000)
            self.assertNotEqual(r, 0)
            deaccelerate_dev(self.primary_volume, tc = self)



"""
Accelerating the Primary volume and 
checking whether read or write is going on HDD
"""
class ExternIOonHDD(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(ExternIOonHDD, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(ExternIOonHDD, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    """
    Accelerating the HDD volume with SSD
    Doing Reading and writing from HDD
    """
    def test_1(self):
        for policies in WRITE_POLICY:
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, \
                          tc=self, write_policy = policies)            
            #Writing into HDD
            r = dodd(inf = "/dev/zero", of = self.primary_volume, bs = "4k", count = 4000)
            self.assertEqual(r, 0)

            #reading from HDD
            r = dodd(inf = self.primary_volume, of = "/dev/null", bs = "4k", count = 4000)
            self.assertEqual(r, 0)
            deaccelerate_dev(self.primary_volume, tc = self)


"""
Testing for Fileacc
Create a filesystem for HDD mount a file ar diirectory 
accelerate HDD volume and parllaly delete the directory
"""
class DeleteDirduringfileacc(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(DeleteDirduringfileacc, self).setUp()
        self.dir_name = "%stest" % mountdir
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        #Check if the devices in config.py are already existing
        checkdev(devname=self.primary_volume, tc = self)
        checkdev(devname=self.ssd_volume, tc = self)


    def tearDown(self):
        super(DeleteDirduringfileacc, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc = self)
        if is_mounted("%stest" % mountdir):
            do_unmount("%stest" % mountdir, self)


    """
    Accelerating the HDD volume with SSD
    Setting policy as fileacc
    """
    def accelerate_dir(self, *args):
        do_mkdir(self.dir_name, tc = self)
        do_mkfs(self.primary_volume, "default", tc = self)
        do_mount(self.primary_volume, self.dir_name, tc = self)
        policy = "".join(args)
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, \
                      tc=self, write_policy = policy, mode = "monitor")
        acceleratedir(self, self.primary_volume, "%stest" % mountdir)

    def delete_dir(self):
        time.sleep(10)
        cmd = "rm -rf %s" % self.dir_name
        process_1 = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE)
        out, err = process_1.communicate()
        logger.debug("%s %s"% (out, err))
        self.assertNotEqual(process_1.returncode, 0)


    def test_call_methods(self):
        for policies in WRITE_POLICY:
            process_1 = Process(target=self.accelerate_dir, args=(policies))
            process_1.start()
            process_2 = Process(target=self.delete_dir)
            process_2.start()
            process_1.join()
            process_2.join()
            deaccelerate_dev(self.primary_volume, tc = self)
            do_unmount(self.dir_name, tc = self)


if __name__ == '__main__':
    unittest.main(argv=["negative_test.py"] + args)
