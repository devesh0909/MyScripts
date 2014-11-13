import paramiko
import os
import fcntl
import random
import shutil
import sys
import time
import unittest

from common_remote_utils import *
from cblog import *
from layout import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)


LOG_SIZE = (1 << 20)

class LogReplay(Pre_check_remote, CBQAMixin, unittest.TestCase):
    def setUp(self):
        self.startTime = time.time()


        self.pvn1 = random.choice(PRIMARY_VOLUMES)
        self.svn1 = random.choice(SSD_VOLUMES.keys())
        self.host1 = random.choice(TEST_HOSTS.keys())
        self.proto1 = random.choice(TEST_PROTO.keys())
        self.host1 = TestHost(host=self.host1,proto=self.proto1)

        super(LogReplay, self).setUp()

        # Check if the devices in config.py are already existing
        checkdev(devname=self.pvn1, tc=self)
        checkdev(devname=self.svn1, tc=self)

        logger.debug( "\n\nSTART: %s" % self.id())
        logger.debug( "testing with %s and %s on %s" % (self.pvn1, self.svn1, self.host1))

    def tearDown(self):
        logger.debug( "\n\nEnd: %s" % self.id())
        if isdev_accelerated(self.pvn1,tc=self):
            deaccelerate_dev(self.pvn1, tc=self)

            self.config_backup_delete()
        do_unmount("/mnt/temp_test", self, debug = True)

    def test_01(self):

        #
        # Basic log replay test case
        # 1. Accelerate the remote device and set fulldisk acceleration
        # 2. Move the original config file into another file to avoid acceleration 
        #    during reboot.
        # 3. Perform IOs on the accelerated device
        # 4. Reboot the machine and wait until it comes up
        # 5. Restore the config file
        # 6. Call cbreplay in test mode and assert that we have a valid checkpoint
        # 7. If valid, call cbreplay and re-accelerate the device
        # 8. De-accelerate the device and cleanup
        #

        self.host1.cmd_exec("hostname")

        #Accelerate the device and set policy to write-back
        accelerate_dev(self.pvn1, self.svn1, tc=self, write_policy="write-back")

        xstats = getxstats(self.pvn1, self)
        accelerate_allregions(self.pvn1, xstats.get('cs_numregions'), self)

        #Move the config file
        self.config_backup()
 
        #Do some wirte io
        dd(tc = self, ipf = "/dev/zero", of = self.pvn1, bs = 4096, count = 102400)

        # sleep untill checkpoint is taken
        logger.debug("sleep for 70 secs")
        time.sleep(70)

        #Reboot the machine
        self.host1.reboot(force = True)

        #Restore the config file
        self.config_restore()

        #After reboot replay the log
        out = self.cbreplay(test = True)

        clsn = int(out[0].split(":")[-1])
        coffset = int(out[1].split(":")[-1])
        rlsn = int(out[1].split(":")[-1])

        self.assertTrue(clsn > 0)
        self.assertTrue(coffset > 0)
        self.assertTrue(rlsn > 0)

        self.cbreplay()

        # Re-accelerate the device
        self.reaccelerate()

        #cleanup
        deaccelerate_dev(self.pvn1, tc=self)
        self.config_backup_delete()

        do_pass(self, 'test_logreplay_base')

    def test_02(self):

        #
        # Basic log replay test case with FS
        # 1. Accelerate the remote device and set fulldisk acceleration
        # 2. Create a FS on the accelerated volume and mount it
        # 3. Move the original config file into another file to avoid acceleration 
        #    during reboot.
        # 4. Create and write data into the a file on the mounted volume
        # 5. Store the checksum of the file
        # 6. Reboot the machine and wait until it comes up
        # 7. Restore the config file
        # 8. Call cbreplay in test mode and assert that we have a valid checkpoint
        # 9. If valid, call cbreplay and re-accelerate the device
        # 10. Remount the filesystem
        # 11. Take checkusm after reboot and assert that checksum is same as old checksum
        # 12. De-accelerate the device and cleanup
        #

        self.host1.cmd_exec("hostname")

        accelerate_dev(self.pvn1, self.svn1, tc=self, write_policy="write-back")
        xstats = getxstats(self.pvn1, self)
        accelerate_allregions(self.pvn1, xstats.get('cs_numregions'), self)

        do_mkfs(self.pvn1, 4096, self)

        #
        #Creating directory for mounting
        #
        do_mkdir("/mnt/temp_test", tc=self)
        do_mount(self.pvn1, "/mnt/temp_test", tc=self)

        self.config_backup()

        dd(tc=self, ipf="/dev/urandom", of="/mnt/temp_test/a", bs=4096, count=102400)

        cksumold = get_checksum('/mnt/temp_test/a', self)

        # sleep untill checkpoint is taken
        logger.debug("sleep for 70 secs")
        time.sleep(70)

        self.host1.reboot(force = True)

        self.config_restore()

        out = self.cbreplay(test = True)

        clsn = int(out[0].split(":")[-1])
        coffset = int(out[1].split(":")[-1])
        rlsn = int(out[1].split(":")[-1])

        self.assertTrue(clsn > 0)
        self.assertTrue(coffset > 0)
        self.assertTrue(rlsn > 0)

        self.cbreplay()

        self.reaccelerate()

        do_mount(self.pvn1, "/mnt/temp_test", tc=self)

        cksumnew = get_checksum('/mnt/temp_test/a', self)

        logger.debug("checksum new=%s checksumold=%s" % (cksumnew, cksumold))
        self.assertEqual(cksumnew, cksumold)

        deaccelerate_dev(self.pvn1, tc=self)
        self.config_backup_delete()

        cksumnew = get_checksum('/mnt/temp_test/a', self)

        logger.debug("checksum new=%s checksumold=%s" % (cksumnew, cksumold))
        self.assertEqual(cksumnew, cksumold)

        do_unmount("/mnt/temp_test", self)

        do_pass(self, 'test_logreplay_file')

    def test_03(self):

        #
        # Basic log replay test case with FS with aggressive copyback
        # 1. Accelerate the remote device and set fulldisk acceleration
        # 2. Create a FS on the accelerated volume and mount it
        # 3. Move the original config file into another file to avoid acceleration 
        #    during reboot.
        # 4. Create and write data into the a file on the mounted volume
        # 5. Store the checksum of the file
        # 6. Reboot the machine and wait until it comes up
        # 7. Restore the config file
        # 8. Call cbreplay in test mode and assert that we have a valid checkpoint
        # 9. If valid, call cbreplay and re-accelerate the device
        # 10. Remount the filesystem
        # 11. Take checkusm after reboot and assert that checksum is same as old checksum
        # 12. De-accelerate the device and cleanup
        #

        self.host1.cmd_exec("hostname")

        accelerate_dev(self.pvn1, self.svn1, tc=self, write_policy="write-back")
        xstats = getxstats(self.pvn1, self)
        accelerate_allregions(self.pvn1, xstats.get('cs_numregions'), self)
        self.copyback_set_threshold(1, 0);

        do_mkfs(self.pvn1, 4096, self)

        #
        #Creating directory for mounting
        #
        do_mkdir("/mnt/temp_test", tc=self)
        do_mount(self.pvn1, "/mnt/temp_test", tc=self)

        self.config_backup()

        dd(tc=self, ipf="/dev/urandom", of="/mnt/temp_test/a", bs=4096, count=102400)

        drop_cache_and_sync(self)
        drop_cache_and_sync(self)

        cksumold = get_checksum('/mnt/temp_test/a', self)

        # sleep untill checkpoint is taken
        logger.debug("sleep for 70 secs")
        time.sleep(70)

        self.host1.reboot(force = True)

        self.config_restore()

        out = self.cbreplay(test = True)

        clsn = int(out[0].split(":")[-1])
        coffset = int(out[1].split(":")[-1])
        rlsn = int(out[1].split(":")[-1])

        self.assertTrue(clsn > 0)
        self.assertTrue(coffset > 0)
        self.assertTrue(rlsn > 0)

        self.cbreplay()

        self.reaccelerate()

        do_mount(self.pvn1, "/mnt/temp_test", tc=self)

        cksumnew = get_checksum('/mnt/temp_test/a', self)

        logger.debug("checksum new=%s checksumold=%s" % (cksumnew, cksumold))
        self.assertEqual(cksumnew, cksumold)

        deaccelerate_dev(self.pvn1, tc=self)
        self.config_backup_delete()

        cksumnew = get_checksum('/mnt/temp_test/a', self)

        logger.debug("checksum new=%s checksumold=%s" % (cksumnew, cksumold))
        self.assertEqual(cksumnew, cksumold)

        do_unmount("/mnt/temp_test", self)

        do_pass(self, 'test_logreplay_file_with_aggressive_copyback')

    def test_04(self):

        #
        # Basic log replay test case with FS
        # 1. Accelerate the remote device.
        # 2. Move the original config file into another file to avoid acceleration 
        #    during reboot.
        # 3. De-accelerate the volume.
        # 4. Format the SSD for 3 Log RU as transaction log size, and re-accelerate
        # 5. set fulldisk acceleration
        # 6. Perform IOs on the accelerated device, Assert log wrap around happens. 
        #    Combination of copyback and IO required.
        # 7. Reboot the machine and wait until it comes up
        # 8. Restore the config file
        # 9. Call cbreplay in test mode and assert that we have a valid checkpoint
        # 10. If valid, call cbreplay and re-accelerate the device
        # 11. De-accelerate the device and cleanup
        #

        self.host1.cmd_exec("hostname")

        accelerate_dev(self.pvn1, self.svn1, tc=self, write_policy="write-back")
        disk_id, ssd_id = self.get_device_ids()

        self.config_backup()
        self.cadb_backup()

        self.ca_deaccelerate()

        self.format_logru(3, disk_id, ssd_id)
        self.reaccelerate()

        self.cadb_restore()
        xstats = getxstats(self.pvn1, self)
        accelerate_allregions(self.pvn1, xstats.get('cs_numregions'), self)

        do_mkfs(self.pvn1, 4096, self)

        #
        #Creating directory for mounting
        #
        do_mkdir("/mnt/temp_test", tc=self)
        do_mount(self.pvn1, "/mnt/temp_test", tc=self)

        self.config_backup()

        dd(tc=self, ipf="/dev/urandom", of="/mnt/temp_test/a", bs=4096, count=102400)

        cksumold = get_checksum('/mnt/temp_test/a', self)

        # sleep untill checkpoint is taken
        logger.debug("sleep for 70 secs")
        time.sleep(70)

        self.host1.reboot(force = True)

        self.config_restore()

        out = self.cbreplay(test = True)

        clsn = int(out[0].split(":")[-1])
        coffset = int(out[1].split(":")[-1])
        rlsn = int(out[1].split(":")[-1])

        self.assertTrue(clsn > 0)
        self.assertTrue(coffset > 0)
        self.assertTrue(rlsn > 0)

        self.cbreplay()

        self.reaccelerate()

        do_mount(self.pvn1, "/mnt/temp_test", tc=self)

        cksumnew = get_checksum('/mnt/temp_test/a', self)

        logger.debug("checksum new=%s checksumold=%s" % (cksumnew, cksumold))
        self.assertEqual(cksumnew, cksumold)

        deaccelerate_dev(self.pvn1, tc=self)
        self.config_backup_delete()

        cksumnew = get_checksum('/mnt/temp_test/a', self)

        logger.debug("checksum new=%s checksumold=%s" % (cksumnew, cksumold))
        self.assertEqual(cksumnew, cksumold)

        do_unmount("/mnt/temp_test", self)

        do_pass(self, 'test_wrap_logreplay_file')

    def test_05(self):

        #
        # Basic log replay test with dynamic policy by comparing admit map count
        # 1. Accelerate the remote device.
        # 2. Move the original config file into another file to avoid acceleration 
        #    during reboot.
        # 3. Mark regions for acceleration.
        # 4. Get the count of admit map that have been marked for caching 
        # 5. Reboot the machine and wait until it comes up
        # 6. Restore the config file
        # 7. Call cbreplay in test mode and assert that we have a valid checkpoint
        # 8. If valid, call cbreplay and re-accelerate the device
        # 9. Again Take the cached admit map count and assert the count is still the same.
        # 10. De-accelerate the device and cleanup
        #

        self.host1.cmd_exec("hostname")

        accelerate_dev(self.pvn1, self.svn1, tc=self, write_policy="write-back")

        self.config_backup()

        #
        # Mark regions for acceleration
        #
        for i in xrange(1024):
            accelerateregion(self, self.pvn1, i)

        logger.debug("sleep for 70 secs")
        time.sleep(70)

        o_amap_cnt = get_admitmap_count(self, self.pvn1)

        self.host1.reboot(force = True)

        self.config_restore()

        out = self.cbreplay(test = True)

        clsn = int(out[0].split(":")[-1])
        coffset = int(out[1].split(":")[-1])
        rlsn = int(out[1].split(":")[-1])

        self.assertTrue(clsn > 0)
        self.assertTrue(coffset > 0)
        self.assertTrue(rlsn > 0)

        self.cbreplay()

        self.reaccelerate()

        n_amap_cnt = get_admitmap_count(self, self.pvn1)

        logger.debug("admit map count old=%s new=%s" % (o_amap_cnt, n_amap_cnt))
        self.assertEqual(o_amap_cnt, n_amap_cnt)

        deaccelerate_dev(self.pvn1, tc=self)
        self.config_backup_delete()

        do_pass(self, 'test_dynamic_amap_cnt')


    def test_06(self):

        #
        # Basic log replay test case
        # 1. Accelerate the remote device and set fulldisk acceleration
        #    during reboot.
        # 2. Perform IOs on the accelerated device
        # 3. Reboot the machine and wait until it comes up
        # 4. Assert that the device is accelerated once the system is up
        # 5. De-accelerate the device and cleanup
        #

        self.host1.cmd_exec("hostname")

        #Accelerate the device and set policy to write-back
        accelerate_dev(self.pvn1, self.svn1, tc=self, write_policy="write-back")
        xstats = getxstats(self.pvn1, self)
        accelerate_allregions(self.pvn1, xstats.get('cs_numregions'), self)

        #Do some wirte io
        dd(tc = self, ipf = "/dev/zero", of = self.pvn1, bs = 4096, count = 102400)

        # sleep untill checkpoint is taken
        logger.debug("sleep for 70 secs")
        time.sleep(70)

        #Reboot the machine
        self.host1.reboot(force = True)

        self.assertTrue(isdev_accelerated(self.pvn1, self))

        #cleanup
        deaccelerate_dev(self.pvn1, tc=self)
        self.config_backup_delete()

        do_pass(self, 'test_logreplay_base_2')

    def test_07(self):

        #
        # Basic log replay test case with FS with multiple log replay
        # 1. Accelerate the remote device and set fulldisk acceleration
        # 2. Create a FS on the accelerated volume and mount it
        # 3. Move the original config file into another file to avoid acceleration 
        #    during reboot.
        # 4. Create and write data into the a file on the mounted volume
        # 5. Store the checksum of the file
        # 6. Reboot the machine and wait until it comes up
        # 7. Restore the config file
        # 8. Call cbreplay in test mode and assert that we have a valid checkpoint
        # 9. If valid, call cbreplay and re-accelerate the device
        # 10. Remount the filesystem
        # 11. Take checkusm after reboot and assert that checksum is same as old checksum
        # 12. Create and write data into the another file on the mounted volume
        # 13. Store the checksum of the file
        # 14. Reboot the machine and wait until it comes up
        # 15. Restore the config file
        # 16. Call cbreplay in test mode and assert that we have a valid checkpoint
        # 17. If valid, call cbreplay and re-accelerate the device
        # 18. Remount the filesystem
        # 19. Take checkusm after reboot and assert that checksum is same as old checksum
        # 20. De-accelerate the device and cleanup
        #

        self.host1.cmd_exec("hostname")

        accelerate_dev(self.pvn1, self.svn1, tc=self, write_policy="write-back")
        xstats = getxstats(self.pvn1, self)
        accelerate_allregions(self.pvn1, xstats.get('cs_numregions'), self)

        do_mkfs(self.pvn1, 4096, self)

        #
        #Creating directory for mounting
        #
        do_mkdir("/mnt/temp_test", tc=self)
        do_mount(self.pvn1, "/mnt/temp_test", tc=self)

        self.config_backup()

        dd(tc=self, ipf="/dev/urandom", of="/mnt/temp_test/a", bs=4096, count=102400)

        drop_cache_and_sync(self)
        drop_cache_and_sync(self)

        cksumold = get_checksum('/mnt/temp_test/a', self)

        # sleep untill checkpoint is taken
        logger.debug("sleep for 70 secs")
        time.sleep(70)

        self.host1.reboot(force = True)

        self.config_restore()

        out = self.cbreplay(test = True)

        clsn = int(out[0].split(":")[-1])
        coffset = int(out[1].split(":")[-1])
        rlsn = int(out[1].split(":")[-1])

        self.assertTrue(clsn > 0)
        self.assertTrue(coffset > 0)
        self.assertTrue(rlsn > 0)

        self.cbreplay()

        self.reaccelerate()

        do_mount(self.pvn1, "/mnt/temp_test", tc=self)

        cksumnew = get_checksum('/mnt/temp_test/a', self)

        logger.debug("checksum new=%s checksumold=%s" % (cksumnew, cksumold))
        self.assertEqual(cksumnew, cksumold)

        self.config_backup()

        dd(tc=self, ipf="/dev/urandom", of="/mnt/temp_test/b", bs=4096, count=10240)

        drop_cache_and_sync(self)
        drop_cache_and_sync(self)

        cksumold = get_checksum('/mnt/temp_test/b', self)

        # sleep untill checkpoint is taken
        logger.debug("sleep for 70 secs")
        time.sleep(70)

        self.host1.reboot(force = True)

        self.config_restore()

        out = self.cbreplay(test = True)

        clsn = int(out[0].split(":")[-1])
        coffset = int(out[1].split(":")[-1])
        rlsn = int(out[1].split(":")[-1])

        self.assertTrue(clsn > 0)
        self.assertTrue(coffset > 0)
        self.assertTrue(rlsn > 0)

        self.cbreplay()

        self.reaccelerate()

        self.copyback_set_threshold(1, 0)

        do_mount(self.pvn1, "/mnt/temp_test", tc=self)

        cksumnew = get_checksum('/mnt/temp_test/b', self)

        logger.debug("checksum new=%s checksumold=%s" % (cksumnew, cksumold))
        self.assertEqual(cksumnew, cksumold)

        deaccelerate_dev(self.pvn1, tc=self)
        self.config_backup_delete()

        cksumnew = get_checksum('/mnt/temp_test/b', self)

        logger.debug("checksum new=%s checksumold=%s" % (cksumnew, cksumold))
        self.assertEqual(cksumnew, cksumold)

        do_unmount("/mnt/temp_test", self)

        do_pass(self, 'test_multiple_logreplay')

    def test_08(self):

        #
        # Basic log replay test case with FS with aggressive copyback
        # 1. Accelerate the remote device and set fulldisk acceleration
        # 2. Move the original config file into another file to avoid acceleration 
        #    during reboot.
        # 3. Run fio on the device
        # 4. Reboot the machine and wait until it comes up
        # 5. Restore the config file
        # 6. Call cbreplay in test mode and assert that we have a valid checkpoint
        # 7. If valid, call cbreplay and re-accelerate the device
        # 8. De-accelerate the device and cleanup
        #

        self.host1.cmd_exec("hostname")

        accelerate_dev(self.pvn1, self.svn1, tc=self, write_policy="write-back")
        xstats = getxstats(self.pvn1, self)
        accelerate_allregions(self.pvn1, xstats.get('cs_numregions'), self)
        self.copyback_set_threshold(1, 0);

        self.config_backup()

        self.run_fio()
        self.run_fio()

        drop_cache_and_sync(self)
        drop_cache_and_sync(self)
        self.run_fio()

        # sleep untill checkpoint is taken
        logger.debug("sleep for 10 secs")
        time.sleep(70)

        self.host1.reboot(force = True)

        self.config_restore()

        out = self.cbreplay(test = True)

        clsn = int(out[0].split(":")[-1])
        coffset = int(out[1].split(":")[-1])
        rlsn = int(out[1].split(":")[-1])

        self.assertTrue(clsn > 0)
        self.assertTrue(coffset > 0)
        self.assertTrue(rlsn > 0)

        self.cbreplay()

        self.reaccelerate()

        deaccelerate_dev(self.pvn1, tc=self)
        self.config_backup_delete()

        do_pass(self, 'test_logreplay_file_with_aggressive_copyback_and_fio')

class LogReplayCode(Pre_check_remote, CBQAMixin, unittest.TestCase):
    def setUp(self):
        self.startTime = time.time()


        self.pvn1 = random.choice(PRIMARY_VOLUMES)
        self.svn1 = random.choice(SSD_VOLUMES.keys())
        self.host1 = random.choice(TEST_HOSTS.keys())
        self.proto1 = random.choice(TEST_PROTO.keys())
        self.host1 = TestHost(host=self.host1,proto=self.proto1)

        super(LogReplayCode, self).setUp()

        # Check if the devices in config.py are already existing
        checkdev(devname=self.pvn1, tc=self)
        checkdev(devname=self.svn1, tc=self)

        logger.debug( "\n\nSTART: %s" % self.id())
        logger.debug( "testing with %s and %s on %s" % (self.pvn1, self.svn1, self.host1))

    def tearDown(self):
        logger.debug( "\n\nEnd: %s" % self.id())
        if isdev_accelerated(self.pvn1,tc=self):
            deaccelerate_dev(self.pvn1, tc=self)

        self.config_backup_delete()
        self.unset_restart()
        do_unmount("/mnt/temp_test", self, debug = True)

    def test_01(self):

        #
        # CB_ACCBEGIN_RESTART - trigger restart before acceleration is done
        #

        self.host1.cmd_exec("hostname")
        self.config_cleanup()

        self.trigger_restart(0x00000001)

        try:
            accelerate_dev(self.pvn1, self.svn1, tc=self, write_policy="write-back", wait = False)
        except:
            pass
        time.sleep(2)
        self.host1.wait()
        self.trigger_restart(0)
        do_pass(self, 'test_CB_ACCBEGIN_RESTART', isdev_accelerated(self.pvn1, tc=self) == 0)

    def test_02(self):

        #
        # CB_LETGOEND_RESTART - Restart the system once letgo is done
        #

        self.host1.cmd_exec("hostname")
        self.config_cleanup()

        self.trigger_restart(0x80000000)

        accelerate_dev(self.pvn1, self.svn1, tc=self, write_policy="write-back")
        xstats = getxstats(self.pvn1, self)
        self.config_backup()

        accelerate_allregions(self.pvn1, xstats.get('cs_numregions'), self)
        self.copyback_set_threshold(1, 0);

        try:
            dd(tc = self, ipf = self.pvn1, of = "/dev/null", bs = 4096)
            time.sleep(2)
            deaccelerate_dev(self.pvn1, tc=self, wait = False)
            time.sleep(30)
        except:
            pass

        self.host1.wait()
        self.trigger_restart(0)

        do_pass(self, 'test_CB_LETGOEND_RESTART', isdev_accelerated(self.pvn1, tc=self) == 0)

    def test_03(self):

        #
        # REBOOT_TRIGGER_CODE are invoked and system is restarted as per
        # the code.
        #

        self.config_cleanup()

        for code in REBOOT_TRIGGER_CODE.keys():
            self.host1.cmd_exec("hostname")
            mode = "write-back"
            if code == 'CB_WTHRUFLOW_RESTART' or code == 'CB_WTHRUDONE_RESTART':
                mode = "write-through"
            if code == 'CB_ACCEND_RESTART':
                self.trigger_restart(REBOOT_TRIGGER_CODE.get(code))
            try:
                accelerate_dev(self.pvn1, self.svn1, tc=self, write_policy=mode, wait = False)
                time.sleep(10)
                self.config_backup()
                accelerate_allregions(self.pvn1, 1024, self)
                self.copyback_set_threshold(1, 0);
                self.run_fio()
                self.trigger_restart(REBOOT_TRIGGER_CODE.get(code))

                if code in ['CB_LETGOBEGIN_RESTART', 'CB_CMODEEND_RESTART', 'CB_CMODEBEGIN_RESTART']:
                    deaccelerate_dev(self.pvn1, tc=self, wait = False)
                    time.sleep(30)
                    raise Exception('done')
                 
                self.run_fio(wait = False)
                time.sleep(2)
                drop_cache_and_sync(tc = self, wait = False)
                time.sleep(2)
                drop_cache_and_sync(tc = self, wait = False)
                time.sleep(2)
                if code in ['CB_RDISKFLOW_RESTART', 'CB_RDISKDONE_RESTART']:
                    dd(tc = self, ipf = self.pvn1, of = "/dev/null", bs = 4096, \
                       count = None, wait = False, flags="iflag=direct")
                    time.sleep(60)
                if code in ['CB_WDISKFLOW_RESTART', 'CB_WDISKDONE_RESTART']:
                    dd(tc = self, ipf = "/dev/zero", of = self.pvn1, bs = 4096, \
                       count = None, wait = False, flags="oflag=direct")
                    time.sleep(60)
                self.run_fio(wait = False)
                time.sleep(2)
                dd(tc = self, ipf = "/dev/zero", of = self.pvn1, bs = 4096, \
                   count = None, wait = False, flags="oflag=direct")
                time.sleep(60)
                dd(tc = self, ipf = self.pvn1, of = "/dev/null", bs = 4096, \
                   count = None, wait = False, flags="iflag=direct")
                time.sleep(60)
                time.sleep(60)
            except:
                pass

            try:
                if isdev_accelerated(self.pvn1, tc=self):
                    # it can so happen that some cases are not triggered,
                    # handling this with force reboot
                    self.host1.reboot(force = True)
                else:
                    self.host1.wait()
            except:
                self.host1.wait()

            self.config_restore()

            out = self.cbreplay(test = True)

            clsn = int(out[0].split(":")[-1])
            coffset = int(out[1].split(":")[-1])
            rlsn = int(out[1].split(":")[-1])

            self.assertTrue(clsn > 0)
            self.assertTrue(coffset > 0)
            self.assertTrue(rlsn > 0)

            self.cbreplay()

            self.reaccelerate()
            if self.is_in_cachebox_list():
                deaccelerate_dev(self.pvn1, tc=self)
            else:
                self.ca_deaccelerate()

            self.config_backup_delete()
            self.trigger_restart(0)
            do_pass(self, 'test_%s' % code)

if __name__ == '__main__':
    unittest.main(argv=["logreplay_reboot.py"] + args)
