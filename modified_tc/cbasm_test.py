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
from common_utils import *
from cblog import *
from growshrink import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

do_dd = GrowShrink_Utils.do_dd

VG = "lvm"
LV = "lvm_test"
real_device = None
WRITE_POLICY = ['write-back', 'write-through', 'write-around', 'read-around']

def do_sp(cmd):
    r = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                stderr = subprocess.PIPE, shell=True)
    out, err = r.communicate()
    return (r.returncode, out, err)


class Cbasm_utils(object):

    #chk btd and and return pid related to that
    @staticmethod
    def chk_btd(device, uuid, tc):
        cmd = ("ps -aef | grep -i '/etc/cachebox/server/btd.py --device=%s --uuid=%s start'\
               | grep -v grep" % (device, uuid))
        logger.debug(cmd)
        r, out, err = do_sp(cmd)
        logger.debug(out)
        tc.assertEqual(r, 0)


    @staticmethod
    def get_pid(device, uuid, tc):
        cmd = ("ps -aef | grep -i '/etc/cachebox/server/btd.py --device=%s --uuid=%s start'\
               | grep -v grep" % (device, uuid))
        logger.debug(cmd)
        r, out, err = do_sp(cmd)
        out = out.strip('\n').split('\n')
        for i in out:
            a = i.split()
        pid = a[1]
        return pid

    #Return UUID of device and flag
    @staticmethod
    def get_uuid_flag(device):
        cmd = "cbasm --list | grep -i '%s' | grep -v grep" % device
        ss = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE)
        out = ss.communicate()[0].strip('\n').split('\n')
        for i in out:
            a = i.split()
        return[a[0], a[-3]]


    #Return count of admission bitmap
    @staticmethod
    def chk_bitmapcount(volume, tc):
        cmd = ("cachebox -a 15 -d %s | grep -i ' 1' | wc -l" % volume)
        r, out, err = do_sp(cmd)
        logger.debug("Admit map: %s" % out)
        return out


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


chk_btd = Cbasm_utils.chk_btd
chk_bitmapcount = Cbasm_utils.chk_bitmapcount
islvm_accelerated = Cbasm_utils.islvm_accelerated
chk_lvm_inconfig = Cbasm_utils.chk_lvm_inconfig
get_uuid_flag = Cbasm_utils.get_uuid_flag
get_pid = Cbasm_utils.get_pid


class CbasmTest(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(CbasmTest, self).setUp
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(CbasmTest, self).tearDown()
        volume = get_devicename(self.primary_volume, self)
        primary_volume = "/dev/%s" % volume
        if isdev_accelerated(primary_volume):
            deaccelerate_dev(primary_volume, tc = self)
        if is_mounted("%stest" % mountdir):
            do_unmount("%stest" % mountdir, self)


    '''
    Accelerate the device using cbasm and check btd and 
    cbasm --list flag are set
    '''
    def test_1(self):
        for policy in WRITE_POLICY:
            volume = get_devicename(self.primary_volume, self)
            primary_volume = "/dev/%s" % volume
            accelerate_dev(primary_volume, self.ssd_volume, 4096, self,  \
                            write_policy = policy, mode="monitor")
            uuid_flag = get_uuid_flag(primary_volume)
            self.assertEqual(uuid_flag[0], "*")
            chk_btd(volume, uuid_flag[1], self)
            deaccelerate_dev(primary_volume, self)


    '''
    Accelerate device, verify bitmap database and 
    and check initially admit map count is zero
    '''
    def test_2(self):
        for policy in WRITE_POLICY:
            volume = get_devicename(self.primary_volume, self)
            primary_volume = "/dev/%s" % volume
            accelerate_dev(primary_volume, self.ssd_volume, 4096, self, \
                            write_policy = policy, mode = 'monitor')
            uuid_flag = get_uuid_flag(primary_volume)
            chk_btd(volume, uuid_flag[1], self)
            count = chk_bitmapcount(primary_volume, tc = self)
            self.assertEqual(int(count), 0)
            deaccelerate_dev(primary_volume, self)


    '''
    Accelerate using cbasm and set policy as fulldisk
    do IO's and crosscheck cb_stats
    '''
    def test_3(self):
        for policy in WRITE_POLICY:
            volume = get_devicename(self.primary_volume, self)
            primary_volume = "/dev/%s" % volume
            do_mkfs(primary_volume, "default", tc = self)
            do_mount(primary_volume, "%stest" % mountdir, tc = self)
            accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                            write_policy = policy)
            lmddwritezerotofile("%stest/test_file" % mountdir, 4096, 1000, 1)
            self.flush()
            stats = getxstats(primary_volume)
            count = chk_bitmapcount(primary_volume, tc = self)
            self.assertTrue(int(count) > 0)
            self.assertTrue((stats['cs_writecache_flow'] > 0) or
            (stats['cs_writethrough_flow'] > 0) or 
            (stats['cs_writedisk_flow'] > 0))
            deaccelerate_dev(primary_volume, self)
            do_unmount("%stest" % mountdir, tc = self)


    '''
    Accelerate the device, kill the btd.py
    Check btd.py whether it starts automatically or not
    '''
    def test_4(self):
        for policy in WRITE_POLICY:
            volume = get_devicename(self.primary_volume, self)
            primary_volume = "/dev/%s" % volume
            uuid_flag = get_uuid_flag(primary_volume)
            accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                            write_policy = policy, mode = "monitor")
            chk_btd(volume, uuid_flag[1], self)
            pid = get_pid(volume, uuid_flag[1], self)
            cmd = "kill -9 %s" % pid
            logger.debug(cmd)
            r, out, err = do_sp(cmd)
            logger.debug(out)
            self.assertEqual(r, 0)
            lmddwritezero(primary_volume, 4096, 1000, 1)
            chk_btd(volume, uuid_flag[1], self)
            deaccelerate_dev(primary_volume, self)

    #
    # Test case to handle the change in write-policies among wt, wb, wa and ra modes.
    #
    def test_5(self):

        volume = get_devicename(self.primary_volume, self)
        primary_volume = "/dev/%s" % volume

        for policy in WRITE_POLICY:
            if isdev_accelerated(primary_volume):
                deaccelerate_dev(primary_volume, tc = self)

            accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                            write_policy = policy, mode = "monitor")
            
            for change_policy in WRITE_POLICY:
                if change_policy != policy:
                    change_write_policy(primary_volume, self.ssd_volume, \
                            change_policy, self)

                    deaccelerate_dev(primary_volume, self)

                    accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                            write_policy = policy, mode = "monitor")

            deaccelerate_dev(primary_volume, tc = self)

    #
    # Accelerate in write-back mode, perform writes
    # Change policy to write-through mode, perform writes
    # Write through flows should be incremented
    #
    def test_6(self):
        volume = get_devicename(self.primary_volume, self)
        primary_volume = "/dev/%s" % volume
        accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                         write_policy = "write-back")
        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        first_stats = getxstats(primary_volume)
        self.assertTrue(first_stats['cs_writecache_flow'] > 0)
        self.assertTrue(first_stats['cs_writedisk_flow'] == 0)

        change_write_policy(primary_volume, self.ssd_volume, \
                           "write-through", self)

        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_writethrough_flow'] > 0)

        deaccelerate_dev(primary_volume, tc = self)

    #
    # Accelerate in write-back mode, perform writes
    # Change policy to write-around mode, perform writes
    # Write invalidate flows should be incremented
    # Perform writes, write disk flows should be incremented
    # Perform reads, readpopulate flows should be incremented
    #
    def test_7(self):
        volume = get_devicename(self.primary_volume, self)
        primary_volume = "/dev/%s" % volume
        accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                         write_policy = "write-back")
        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        first_stats = getxstats(primary_volume)
        self.assertTrue(first_stats['cs_writecache_flow'] > 0)

        change_write_policy(primary_volume, self.ssd_volume, \
                           "write-around", self)

        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_writeinvalidate_flow'] > 0)

        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_writedisk_flow'] > 0)

        do_dd(self, primary_volume, "/dev/null", 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_readpopulate_flow'] > 0)

        deaccelerate_dev(primary_volume, tc = self)

    #
    # Accelerate in write-back mode, perform writes
    # Change policy to read-around mode, perform writes
    # Perform reads
    # read disk flows should be incremented
    # write cache flows should be incremented
    #
    def test_8(self):
        volume = get_devicename(self.primary_volume, self)
        primary_volume = "/dev/%s" % volume
        accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                         write_policy = "write-back")
        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        first_stats = getxstats(primary_volume)
        self.assertTrue(first_stats['cs_writecache_flow'] > 0)
        self.assertTrue(first_stats['cs_writedisk_flow'] == 0)

        change_write_policy(primary_volume, self.ssd_volume, \
                           "read-around", self)

        do_dd(self, primary_volume, "/dev/null", 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_readdisk_flow'] > 0)

        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_writecache_flow'] > first_stats['cs_writecache_flow'])

        deaccelerate_dev(primary_volume, tc = self)

    #
    # Accelerate in write-through mode, perform writes
    # Change policy to read-around mode, perform writes
    # write cache flows should be incremented
    # Perform reads
    # read cache flows should be incremented
    #
    def test_9(self):
        volume = get_devicename(self.primary_volume, self)
        primary_volume = "/dev/%s" % volume
        accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                         write_policy = "write-through")
        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        first_stats = getxstats(primary_volume)
        self.assertTrue(first_stats['cs_writethrough_flow'] > 0)

        change_write_policy(primary_volume, self.ssd_volume, \
                           "read-around", self)

        do_dd(self, primary_volume, "/dev/null", 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_readdisk_flow'] > 0)

        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_writecache_flow'] > 0)

        deaccelerate_dev(primary_volume, tc = self)

    #
    # Accelerate in write-through mode, perform writes
    # Change policy to write-around mode, perform reads
    # read cache flows should be incremented
    # Perform writes
    # write invalidate flows should be incremented
    # Perform writes
    # write disk flows should be incremented
    #
    def test_10(self):
        volume = get_devicename(self.primary_volume, self)
        primary_volume = "/dev/%s" % volume
        accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                         write_policy = "write-through")
        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        first_stats = getxstats(primary_volume)
        self.assertTrue(first_stats['cs_writethrough_flow'] > 0)

        change_write_policy(primary_volume, self.ssd_volume, \
                           "write-around", self)

        do_dd(self, primary_volume, "/dev/null", 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_readcache_flow'] > 0)
        self.assertTrue(stats['cs_readpopulate_flow'] > 0)

        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_writeinvalidate_flow'] > 0)

        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_writedisk_flow'] > 0)

        deaccelerate_dev(primary_volume, tc = self)

    #
    # Accelerate in write-through mode, perform writes
    # Change policy to write-back mode, perform reads
    # read cache flows should be incremented
    # Perform writes
    # write cache flows should be incremented
    #
    def test_11(self):
        volume = get_devicename(self.primary_volume, self)
        primary_volume = "/dev/%s" % volume
        accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                         write_policy = "write-through")
        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        first_stats = getxstats(primary_volume)
        self.assertTrue(first_stats['cs_writethrough_flow'] > 0)

        change_write_policy(primary_volume, self.ssd_volume, \
                           "write-back", self)

        do_dd(self, primary_volume, "/dev/null", 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_readpopulate_flow'] > 0)

        do_dd(self, "/dev/zero", primary_volume, 4096, 10000, "seek=0")
        self.flush()
        stats = getxstats(primary_volume)
        self.assertTrue(stats['cs_writecache_flow'] > 0)

        deaccelerate_dev(primary_volume, tc = self)
 


class CbasmLVMTest(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(CbasmLVMTest, self).setUp
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(CbasmLVMTest, self).tearDown()
        global real_device
        if real_device is not None:
            if islvm_accelerated(real_device):
                deaccelerate_dev("/dev/%s" % (real_device), tc = self)
            self.flush()
            if is_mounted("%stest" % mountdir):
                do_unmount("%stest" % mountdir, self)
            delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, 
                            self.primary_volume, tc = self)
        real_device = None


    '''
    Accelerate the device using cbasm and check btd and 
    cbasm --list flag are set in case of LVM
    '''
    def test_1(self):
        global real_device
        if chk_lvm_inconfig(self.primary_volume):
            do_skip(self, 'Simple Volume or Partition volume needed')
        else:
            #Size of lvm in GB
            size = 1
            create_lvmdevice(VG, LV, size, \
                                self.primary_volume, tc = self)
            volume = "/dev/mapper/%s-%s" % (VG, LV)
            real_device = get_devicename(volume, self)
            primary_volume = "/dev/%s" % real_device
            for policy in WRITE_POLICY:
                accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                             write_policy = policy, mode = "monitor")
                uuid_flag = get_uuid_flag(primary_volume)
                self.assertEqual(uuid_flag[0], "*")
                chk_btd(real_device, uuid_flag[1], self)
                deaccelerate_dev(primary_volume, self)
            self.flush()
            delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, 
                            self.primary_volume, tc = self)


    '''
    Accelerate using cbasm and set policy as fulldisk
    do IO's and crosscheck cachebox_stats in case of LVM
    '''
    def test_2(self):
        global real_device
        if chk_lvm_inconfig(self.primary_volume):
            do_skip(self, 'Simple Volume or Partition volume needed')
        else:
            #Size of lvm in GB
            size = 1
            create_lvmdevice(VG, LV, size, \
                                self.primary_volume, tc = self)
            volume = "/dev/mapper/%s-%s" % (VG, LV)
            real_device = get_devicename(volume, self)
            primary_volume = "/dev/%s" % real_device
            for policy in WRITE_POLICY:
                do_mkfs(primary_volume, "default", self)
                do_mkdir("%stest" % mountdir, self)
                do_mount(primary_volume, "%stest" % mountdir, self)
                accelerate_dev(primary_volume, self.ssd_volume, 4096 , self, \
                             write_policy = policy)
                lmddwritezerotofile("%stest/test_file" % mountdir, 4096, 1000, 1)
                self.flush()
                stats = getxstats(primary_volume)
                count = chk_bitmapcount(primary_volume, tc = self)
                self.assertTrue(int(count) > 0)
                self.assertTrue((stats['cs_writecache_flow'] > 0) or
                (stats['cs_writethrough_flow'] > 0) or
                (stats['cs_writedisk_flow'] > 0))
                deaccelerate_dev(primary_volume, self)
                do_unmount("%stest" % mountdir, self)
            self.flush()
            delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, 
                            self.primary_volume, tc = self)

    '''
    Test case for cbasm --list handling resize/deletion of a partition. 
    '''
    def test_3(self):
        global real_device
        if chk_lvm_inconfig(self.primary_volume):
            do_skip(self, 'Simple Volume or Partition volume needed')
        else:
            cmd = 'cbasm --volume --list'
            r, out, err = do_sp(cmd) 

            #Size of lvm in GB
            size = 1
            create_lvmdevice(VG, LV, size, \
                            self.primary_volume, tc = self)
            volume = "/dev/mapper/%s-%s" % (VG, LV)
            device = os.readlink(volume).split('/')[-1]
            real_device = get_devicename(volume, self)

            cmd = 'cbasm --volume --list | grep -w %s' % device
            r, out, err = do_sp(cmd)
            self.assertEqual(r, 0)

            size = 2
            cmd = "lvextend -L+1G %s" % volume
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                           stderr = subprocess.PIPE,shell=True)
            out, err = process_1.communicate()
            self.assertEqual(process_1.returncode, 0)

            cmd = 'cbasm --volume --list | grep -w %s' % device
            r, out, err = do_sp(cmd)
            self.assertEqual(r, 0)

            cmd = 'cbasm --volume --list | grep -w %s | awk \'{print($7)}\'' % device
            size_asm = os.popen(cmd).read().strip()
            cmd = 'cbasm --volume --list | grep -w %s | awk \'{print($8)}\'' % device
            unit = os.popen(cmd).read().strip()

            mult = 1
            if unit == 'MB' :
                mult = 1024

            if unit == 'GB' :
               mult = 1024 * 1024
            self.assertEqual(size * 1024 * 1024, int(size_asm) * mult)

            delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, 
                                self.primary_volume, tc = self)
            cmd = 'cbasm --volume --list | grep -w %s' % device
            r, out, err = do_sp(cmd) 
            self.assertNotEqual(r, 0)


class LVMWithPartitionDeviceTest(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(LVMWithPartitionDeviceTest, self).setUp
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        if len(SSD_VOLUMES[self.ssd_volume]) < 2:
            do_skip(self, 'Need at least 2 partitions  of  ssd device')
        self.ssd_part1 = SSD_VOLUMES[self.ssd_volume][0]
        self.ssd_part2 = SSD_VOLUMES[self.ssd_volume][1]

    def tearDown(self):
        super(LVMWithPartitionDeviceTest, self).tearDown()
        volume = "/dev/mapper/%s-%s" % (VG, LV)
        if os.path.exists(volume):
            delete_lvmdevice(volume, VG, self.ssd_part1, tc = self)

    '''
    Accelerate the one partition of device where another partition device has LVM.
    '''
    def test_1(self):
        #Size of lvm in GB
        size = 1
        create_lvmdevice(VG, LV, size, \
                            self.ssd_part1, tc = self)
        volume = "/dev/mapper/%s-%s" % (VG, LV)
        accelerate_dev(self.primary_volume, self.ssd_part2, 4096 , self, \
                         write_policy = "write-back")
        deaccelerate_dev(self.primary_volume, self)
        delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, 
                        self.ssd_part1, tc = self)
    '''
    Should not Accelerate the main device if one partition has LVM.
    '''
    def test_2(self):
       #Size of lvm in GB
        size = 1
        # lvm on ssd partition
        create_lvmdevice(VG, LV, size, \
                            self.ssd_part1, tc = self)
        volume = "/dev/mapper/%s-%s" % (VG, LV)
        ret = accelerate_dev(self.primary_volume, self.ssd_volume, 4096 , self, \
                         debug = True, write_policy = "write-back")
        self.assertNotEqual(ret, 0)
        delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, 
                        self.ssd_part1, tc = self)
        # lvm on primary device
        create_lvmdevice(VG, LV, size, \
                            self.primary_volume, tc = self)
        ret = accelerate_dev(self.primary_volume, self.ssd_volume, 4096 , self, \
                         debug = True, write_policy = "write-back")
        self.assertNotEqual(ret, 0)
        delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, 
                        self.primary_volume, tc = self)

    '''
    Accelerate the lvm device with another LVM.
    '''
    def test_3(self):
        #Size of lvm in GB
        size = 1
        create_lvmdevice(VG, LV, size, \
                            self.primary_volume, tc = self)
        create_lvmdevice("vg1", "test1", size, \
                            self.ssd_part1, tc = self)
        volume = "/dev/%s" % get_devicename("/dev/mapper/%s-%s" % (VG, LV), self)
        ssd = "/dev/%s" % get_devicename("/dev/mapper/%s-%s" % ("vg1", "test1"), self)
        accelerate_dev(volume, ssd, 4096 , self, \
                          write_policy = "write-back")
        deaccelerate_dev(volume, self)
        delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, 
                        self.primary_volume, tc = self)
        delete_lvmdevice("/dev/mapper/%s-%s" % ("vg1", "test1"), "vg1", 
                        self.ssd_part1, tc = self)

    '''
    Create LVM on device that parent device should not accelerate.
    '''
    def test_4(self):
        #Size of lvm in GB
        size = 1
        create_lvmdevice(VG, LV, size, \
                            self.primary_volume, tc = self)
        ret = accelerate_dev(self.primary_volume, self.ssd_volume, 4096 , self, \
                          debug = True, write_policy = "write-back")
        self.assertNotEqual(ret, 0)
        delete_lvmdevice("/dev/mapper/%s-%s" % (VG, LV), VG, 
                        self.ssd_part1, tc = self)
        #after delete lvm accelerate successfully
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096 , self, \
                        write_policy = "write-back")
        deaccelerate_dev(self.primary_volume, self)



if __name__  == '__main__':
    unittest.main(argv=["cbasm_test.py"] + args)
