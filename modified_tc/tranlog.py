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

import mmap
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
from layout import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

LOG_SIZE = (1 << 20)
CONFIG_PATH = "/etc/cachebox/cachebox_txt.conf"

LR_TRAN_POPULATE_TRANSLATION = "LR_TRAN_POPULATE_TRANSLATION"
LR_TRAN_DIRTY_TRANSLATION = "LR_TRAN_DIRTY_TRANSLATION"
LR_TRAN_INVALIDATE_TRANSLATION = "LR_TRAN_INVALIDATE_TRANSLATION"
LR_TRAN_CLEAN_TRANSLATION = "LR_TRAN_CLEAN_TRANSLATION"

LR_REGION_INIT = "CB_TRAN_REGIONINIT"
LR_TRAN_RUUPDATE = "CB_TRAN_RUUPDATE"

LR_TRAN_ACCELERATE_REGION = "CB_TRAN_ACCELERATE_REGION"

class TestTranLog(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestTranLog, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.devbsz = get_devblksz(self.primary_volume)
        logger.debug("testing with %s and %s" % (self.primary_volume, self.ssd_volume))

    def tearDown(self):
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, self)

        super(TestTranLog, self).tearDown()

    def flush_logs(self):
        cmd = [
               "./cbtran",
               "-d",
               "%s" % self.primary_volume,
               "-f"
            ]
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        assert(r.returncode == 0)

    def read_log_record(self):
        cmd = [
            "cbck",
            "-s",
            "%s" % self.ssd_volume,
            "-d"
            ]

        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        self.assertEqual(r.returncode, 0)
        output = output.rstrip("\n").split("\n")
        output = filter(None, output)
        logs = {
            'read_populate': 0,
            'write_cache': 0,
            'write_invalidate': 0,
            'copy_back': 0,
            'tran_buffer': 0,
            'ru_update': 0,
            'acc_region': 0
            }

        for o in output:
            if o.strip().startswith(LR_TRAN_POPULATE_TRANSLATION):
                logs['read_populate'] += 1
            elif o.strip().startswith(LR_TRAN_DIRTY_TRANSLATION):
                logs['write_cache'] += 1
            elif o.strip().startswith(LR_TRAN_INVALIDATE_TRANSLATION):
                logs['write_invalidate'] += 1
            elif o.strip().startswith(LR_TRAN_CLEAN_TRANSLATION):
                logs['copy_back'] += 1
            elif o.strip().startswith(LR_REGION_INIT):
                logs['tran_buffer'] += 1
            elif o.strip().startswith(LR_TRAN_RUUPDATE):
                logs['ru_update'] += 1
            elif o.strip().startswith(LR_TRAN_ACCELERATE_REGION):
                logs['acc_region'] += 1

        logger.debug(logs)
        return logs

    def format_logsize(self, logsize, disk_id, ssd_id):
        cmd = "cbfmt -d %s -s %s -l %s -i %s -j %s -m full-disk" % \
                      (self.primary_volume, self.ssd_volume, logsize, disk_id, ssd_id)
        r = os.system(cmd)
        assert(r == 0)

    def direct_write(self, size, count):
        buf = 'z' * size
        m = mmap.mmap(-1, size)
        m.write(buf)
        fd = os.open(self.primary_volume, os.O_RDWR|os.O_DIRECT)
        offset = 0
        for i in xrange(count):
            os.lseek(fd, offset, os.SEEK_SET)
            os.write(fd, m)
            offset += size
            m.close()
        os.fsync(fd)
        os.close(fd)

    def read_logs(self, lunit):
        f = os.open(self.ssd_volume, os.O_RDONLY)
        buf = readsuper(f)
        sb = cast(buf, POINTER(cb_superblock)).contents
        logs = readtranlog(f, sb, lunit)
        os.close(f)
        return logs

    def read_super(self):
        f = os.open(self.ssd_volume, os.O_RDONLY)
        buf = readsuper(f)
        sb = cast(buf, POINTER(cb_superblock)).contents
        return sb

    def get_device_ids(self):
        f = open(CONFIG_PATH)
        output = f.read()
        f.close()
        output = output.split("\n")[0].strip().split("|")
        logger.debug(output)
        disk_id = output[3]
        ssd_id = output[5]
        return (disk_id, ssd_id)

    def ca_deaccelerate(self):
        cmd = "cachebox -a 17 -d %s " % self.primary_volume
        r = os.system(cmd)
        assert(r == 0)
        cmd = "cachebox -a 1 -d %s " % self.primary_volume
        r = os.system(cmd)
        assert(r == 0)

    def test_1(self):

        #
        # Basic test case to check if log wrap around
        # 1. Format the SSD with 1 MB log size
        # 2. Accelerate the volume with the SSD
        # 3. Accelerate all regions
        # 4. Keep on doing IO onto the disk untill log wrap
        #    around count is more than 5
        # 5. deaccelerate the device.
        #

        bsize = 4096

        self.accelerate()
        disk_id, ssd_id = self.get_device_ids()
        self.ca_deaccelerate()
        self.format_logsize(LOG_SIZE, disk_id, ssd_id)
        accelerate_existingdev(self.primary_volume, self.ssd_volume, self)
        accelerate_allregions(self.primary_volume, self)
        stats = getxstats(self.primary_volume)
        wrap_around = int(stats.get('cs_log_wrap_around'))
        while (wrap_around < 5):
            dodd(inf = "/dev/zero", of = self.primary_volume, bs = bsize, count = "1000")
            drop_caches(self)
            stats = getxstats(self.primary_volume)
            wrap_around = int(stats.get('cs_log_wrap_around'))
            if (wrap_around >= 5):
                break
            self.copyback()
            stats = getxstats(self.primary_volume)
            wrap_around = int(stats.get('cs_log_wrap_around'))

        self.assertTrue(wrap_around >= 5)
        deaccelerate_dev(self.primary_volume, tc=self)
        do_pass(self, 'test_1')


    def test_2(self):

        #
        # Basic test case for log flushing
        # 1. for count in range [1, 10, 100, 1000, 10000]
        # 2. Accelerate the primary solume with full disk acceleration
        # 3. Do direct writes over the accelerated volume which issues
        #    fsync at the very end.
        # 4. Gather the stats and read the logs using cbck utility
        # 5. assert that the write cahe, read populate counts match with
        #    with the stats
        # 6. de-accelerate the primary volume
        #

        bsize = 4096

        for count in [1, 10, 100, 1000, 10000]:
            self.accelerate()
            accelerate_allregions(self.primary_volume, self)
            self.direct_write(bsize, count)
            stats = getxstats(self.primary_volume)
            self.flush_logs()
            logs = self.read_log_record()
            assert (logs['read_populate'] >= int(stats.get('cs_readpopulate_flow')))
            assert (logs['write_cache'] >= int(stats.get('cs_writecache_flow')))
            assert (logs['write_invalidate'] >= int(stats.get('cs_writeinvalidate_flow')))
            assert (logs['copy_back'] >= int(stats.get('cs_copyback_flow')))
            assert (logs['tran_buffer'] >= int(stats.get('cs_translation_buffers')))
            deaccelerate_dev(self.primary_volume, tc=self)
            do_pass(self, 'test_2 count %d' % count)


    def test_3(self):

        #
        # Basic test case to check the log offets.
        # 1. Accelerate the primary volume with full disk acceleration
        # 2. Do direct writes over the accelerated volume which issues
        #    fsync at the very end.
        # 3. Flush the logs onto the SSD
        # 4. de-accelerate the primary volume
        # 5. Read the first log buffer and assert that the current
        #    LSN is always == prev_lsn + length of last log record
        #

        bsize = 4096

        self.accelerate()
        accelerate_allregions(self.primary_volume, self)
        self.direct_write(bsize, 1000)
        self.flush_logs()
        drop_caches(self)
        deaccelerate_dev(self.primary_volume, tc=self)
        drop_caches(self)
        self.flush()
        logs = self.read_logs(0)
        n = (4096 / 64)
        rec = cast(logs, POINTER(cb_log_record_header * n)).contents
        j = 1
        while j < n:
            if rec[j].lrh_length != 0:
                if j > 2:
                    assert (prev_lsn + last_length == rec[j].lrh_lsn.lsn_64)
                prev_lsn = rec[j].lrh_lsn.lsn_64
                last_length = rec[j].lrh_length
            j += 1

        do_pass(self, 'test_3')

    def test_4(self):

        #
        # Basic test case to check if log wrap around
        # 1. Format the SSD with 1 MB log size
        # 2. Accelerate the volume with the SSD
        # 3. Accelerate all regions
        # 4. Keep on doing IO onto the disk untill log wrap
        #    around count is more than 5
        # 5. With each wrap read the starting log and assert that the
        #    lsn is greater than transaction log end and on modulo
        #    should be present in the first log buffer entry.
        # 6. deaccelerate the device.
        #

        bsize = 4096

        self.accelerate()
        disk_id, ssd_id = self.get_device_ids()
        self.ca_deaccelerate()
        self.format_logsize(LOG_SIZE, disk_id, ssd_id)
        accelerate_existingdev(self.primary_volume, self.ssd_volume, self)
        accelerate_allregions(self.primary_volume, self)

        stats = getxstats(self.primary_volume)
        old_wrap_around = int(stats.get('cs_log_wrap_around'))
        sb = self.read_super()
        log_end = int(sb.csb_tranlogstart) + int(sb.csb_tranlogsize)
        log_end = log_end >> 9
        log_start = sb.csb_tranlogstart >> 9
        i = 1
        while (old_wrap_around < 5):
            dodd(inf = "/dev/zero", of = self.primary_volume, bs = bsize, count = "1000", oflag = "direct")
            drop_caches(self)
            stats = getxstats(self.primary_volume)
            cur_wrap_around = int(stats.get('cs_log_wrap_around'))
            if (old_wrap_around != cur_wrap_around):
                self.flush_logs()
                logs = self.read_logs(0)
                rec = cast(logs, POINTER(cb_log_record_header))
                do_pass (self, "test 4.a.%s" % i, int(rec[0].lrh_lsn.lsn_64) >= log_end)
                old_wrap_around = cur_wrap_around
                i += 1
            self.copyback()

        self.assertTrue(old_wrap_around >= 5)
        deaccelerate_dev(self.primary_volume, tc=self)

    def test_5(self):

        #
        # Check log wraparound for 1024
        # 1. Format the SSD with 1 MB log size
        # 2. Accelerate the volume with the SSD
        # 3. Accelerate all regions
        # 4. Keep on doing IO onto the disk untill log wrap
        #    around count is more than 1024
        # 5. deaccelerate the device.
        #

        bsize = 4096

        self.accelerate()
        disk_id, ssd_id = self.get_device_ids()
        self.ca_deaccelerate()
        self.format_logsize(LOG_SIZE, disk_id, ssd_id)
        accelerate_existingdev(self.primary_volume, self.ssd_volume, self)
        accelerate_allregions(self.primary_volume, self)
        stats = getxstats(self.primary_volume)
        wrap_around = int(stats.get('cs_log_wrap_around'))
        while (wrap_around < 1024):
            dodd(inf = "/dev/zero", of = self.primary_volume, bs = bsize, count = 1000000)
            stats = getxstats(self.primary_volume)
            wrap_around = int(stats.get('cs_log_wrap_around'))
            if (wrap_around >= 1024):
                break
            self.copyback()
            stats = getxstats(self.primary_volume)
            wrap_around = int(stats.get('cs_log_wrap_around'))

        self.assertTrue(wrap_around >= 1024)
        deaccelerate_dev(self.primary_volume, tc=self)
        do_pass(self, 'test_5')


    def test_6(self):

        #
        # Check log wraparound for various block sizes
        # 1. Format the SSD with 1 MB log size
        # 2. Accelerate the volume with the SSD
        # 3. Accelerate all regions
        # 4. Do IOs with varying blocksize
        # 5. deaccelerate the device.
        #

        bsize = 4096

        self.accelerate()
        disk_id, ssd_id = self.get_device_ids()
        self.ca_deaccelerate()
        self.format_logsize(LOG_SIZE, disk_id, ssd_id)
        accelerate_existingdev(self.primary_volume, self.ssd_volume, self)
        accelerate_allregions(self.primary_volume, self)
        stats = getxstats(self.primary_volume)
        wrap_around = int(stats.get('cs_log_wrap_around'))
        bs=[512, 1025, 2048, 4096, 8192]
        for bsize in bs:
            dodd(inf = "/dev/zero", of = self.primary_volume, bs = bsize, count = 10000)
            drop_caches(self)
            stats = getxstats(self.primary_volume)
            wrap_around = int(stats.get('cs_log_wrap_around'))
            self.copyback()
            stats = getxstats(self.primary_volume)
            wrap_around = int(stats.get('cs_log_wrap_around'))


        self.assertTrue(wrap_around >= 1)
        deaccelerate_dev(self.primary_volume, tc=self)
        do_pass(self, 'test_6')


    def test_7(self):

        #
        # Check for data consistency
        # 1. Format the SSD with 1 MB log size
        # 2. Accelerate the volume with the SSD
        # 3. Accelerate all regions
        # 4. Do IO using lmdd
        # 5. deaccelerate the device.
        # 6. Check for consistency
        #

        bsize = 4096

        self.accelerate()
        disk_id, ssd_id = self.get_device_ids()
        self.ca_deaccelerate()
        self.format_logsize(LOG_SIZE, disk_id, ssd_id)
        accelerate_existingdev(self.primary_volume, self.ssd_volume, self)
        accelerate_allregions(self.primary_volume, self)
        stats = getxstats(self.primary_volume)
        wrap_around = int(stats.get('cs_log_wrap_around'))
        ssdsize = get_devsz(self.ssd_volume)
        count = ssdsize / bsize

        for i in range (1, 5):
            r = dolmdd(inf = self.primary_volume, bs = "4k", count = str(10*count), skip = str(i*count))
            self.assertEqual(r, 0)
            drop_caches(tc=self)
            stats = getxstats(self.primary_volume)
            wrap_around = int(stats.get('cs_log_wrap_around'))

        deaccelerate_dev(self.primary_volume, tc=self)
        checkcorrectness(self.primary_volume, bsize, tc = self)

        do_pass(self, 'test_7')


if __name__ == '__main__':
  unittest.main(argv=["tranlog.py"] + args)
