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
import mmap
import os
import random
import string
import subprocess
import sys
import threading
import time
import unittest

from common_utils import *
from cblog import *
from layout import *

MB_BUF_SIZE = (1 << 20)

ev = threading.Event()

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

class TestCopyBack(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestCopyBack, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.wfile = "%stest_wfile" % tmpdir
        self.rfile = "%stest_rfile" % tmpdir

    def tearDown(self):
        super(TestCopyBack, self).tearDown()
        self.copyback_enable()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_tmpfile(self.wfile, tc=self)
        del_tmpfile(self.rfile, tc=self)

    def get_buffer(self, size, sector):
        s = ('%0.16d%0.16d' % (size, sector)) * (size/32)
        buf = buffer(s, 0, size)
        return buf

    def copyback_disable(self):
        return cb_set_tunable("copyback_enable", 0)

    def copyback_enable(self):
        return cb_set_tunable("copyback_enable", 1)

    def copyback_set_threshold(self, dmax, dmin):
        cmd = "cachebox -d %s -g %s -e %s > /dev/null 2>&1" % (self.primary_volume, dmax, dmin)
        return os.system(cmd)

    def copyback_ioctl(self, cmax):
        cmd = "cachebox -d %s -k %s > /dev/null 2>&1" % (self.primary_volume, cmax)
        return os.system(cmd)

    def copyback_disk(self, start, end):
        cmd = "./cbcopyback -d %s -s %s -e %s > /dev/null 2>&1" % (self.primary_volume, start, end)
        return os.system(cmd)

    def read_super(self):
        drop_caches(self)
        f = os.open(self.ssd_volume, os.O_RDONLY)
        buf = readsuper(f)
        sb = cast(buf, POINTER(cb_superblock)).contents
        os.close(f)
        return sb

    def read_region_fmap(self, region):
        fct = []
        f = os.open(self.ssd_volume, os.O_RDONLY)
        buf = readsuper(f)
        sb = cast(buf, POINTER(cb_superblock)).contents
        fmap = readfmap(f, sb, region)
        buf = os.read(f, sb.csb_bsize)
        fmapp = cast(buf, POINTER(cb_fmapentry * sb.csb_blocksperregion))
        i = 0
        hddsector = (region * sb.csb_blocksperregion * sb.csb_bsize) >> 9
        for i in xrange(sb.csb_blocksperregion):
            fmape = fmapp.contents[i]
            if (fmape.cfm_flags & 0x0002):
                fct.append((hddsector, fmape.cfm_ssdsector))
            hddsector += ((sb.csb_bsize) >> 9)

        os.close(f)

        return fct

    def read_bypass_from_disk(self, sector, bypass = 1):
        cmd = [
               "./cbio",
               "-a 0",
               "-d",
               "%s" % self.primary_volume,
               "-s %s" % sector,
               "-t %d" % bypass
              ]

        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, err = r.communicate()
        self.assertEqual(r.returncode, 0)
        return output.rstrip('\n')

    def write_bypass_to_disk(self, sector, bypass, pfile):
        cmd = [
               "./cbio",
               "-a 1",
               "-d",
               "%s" % self.primary_volume,
               "-s %s" % sector,
               "-t %d" % bypass,
               "-p %s" % pfile
              ]

        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = r.communicate()[0].rstrip('\n')
        self.assertEqual(r.returncode,  0)
        return output

    def read_from_disk(self, disk, sector, size):
        fd = os.open(disk, os.O_RDONLY)
        os.lseek(fd, sector, os.SEEK_SET)
        buf = os.read(fd, size)
        os.close(fd)
        return buf

    def func_fill(self, fd, offset, buf, size):
        assert offset >= 0
        assert offset == (offset & ~(size - 1))
        os.lseek(fd, offset, os.SEEK_SET)
        os.write(fd, buf)

    def func_1(self, fd, offset):
        buf = ('%s'%(offset % 10))*4096
        self.func_fill(fd, offset, buf, 4096)

    def func_2(self, fd, offset):
        buf = ('%s'%('w'))*4096
        self.func_fill(fd, offset, buf, 4096)

    def func_3(self, fd, pattern, offset):
        buf = ('%s' % pattern)*4096
        self.func_fill(fd, offset, buf, 4096)

    def write_pattern(self, fd, pattern, offset):
        buf = ('%s' % pattern) * MB_BUF_SIZE
        self.func_fill(fd, offset, buf, MB_BUF_SIZE)

    def thread_copyback(self, ebcount, rep):
        ev.wait()
        time.sleep(0.1)
        for y in xrange(rep):
            r = self.copyback_disk(0, int(ebcount))
            if not r:
                break

    def thread_letgo(self):
        ev.wait()
        time.sleep(0.5)
        deaccelerate_dev(self.primary_volume, tc=self)

    def thread_readio(self, fd, N, rep):
        ev.wait()
        offset = 0
        for y in xrange(rep):
            for x in xrange(N):
                sect = offset >> 9
                self.read_from_disk(self.primary_volume, sect, 4096)
                offset += 4096

    def thread_writeio(self, fd, N, rep):
        offset = 0
        for y in xrange(rep):
            for x in xrange(N):
                self.func_2(fd, offset)
                if (x == N /2):
                    ev.set()
                offset += 4096

    def test_1(self):

      #
      # copy back should happen every 60 seconds. Copy back will 
      # only happen if reverse map has been flushed. This test
      # validates both. Required full disk acceleration
      #

      bsize = 4096
      count = 2000

      accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")
      self.copyback_set_threshold(1, 0)
      dodd(inf = "/dev/zero", of = self.primary_volume, bs = bsize, oflag = "direct")
      drop_caches(self)
      time.sleep(60)
      stats = getxstats(self.primary_volume)
      deaccelerate_dev(self.primary_volume, tc=self)
      do_pass(self, 'test_1 a', float(stats.get('dirty')) > 1)
      do_pass(self, 'test_1 b', stats.get('cs_copyback_flow') > 0)

    def test_2(self):

        #
        # copy back should happen every 60 seconds. Copy back will 
        # only happen if reverse map has been flushed. This test
        # validates both. Requires fulldisk acceleration
        #

        bsize = 4096
        size = 1048576

        dir_name = "%stest/" % mountdir
        do_mkdir(dir_name, tc=self)
        tmp_file = "%stest/tmp_01" % mountdir

        do_mkfs(self.primary_volume, bsize, tc=self)
        do_mount(self.primary_volume, dir_name, tc=self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self,
                       write_policy = "write-back")

        self.copyback_set_threshold(1, 0)

        for x in xrange(5):

            wbuf = self.get_buffer(size, x)

            d = open(self.wfile, "wb")
            d.write(wbuf)
            d.close()
            r = dodd(inf = self.wfile, of = tmp_file, bs = size, oflag = "direct")
            do_pass(self, 'test_2:a', r == 0)

        stats = getxstats(self.primary_volume)
        do_pass(self, 'test_2:b', stats.get('cs_writecache_flow') > 100)

        r = dodd(inf = tmp_file, of = self.rfile, bs = size, iflag = "direct")
        do_pass(self, 'test_2:c', r == 0)

        d = open(self.rfile, "r")
        rbuf = d.read(size)
        d.close()

        do_pass(self, 'test_2:d', str(wbuf) == rbuf)

        time.sleep(60)
        deaccelerate_dev(self.primary_volume, tc=self)

        r = dodd(inf = tmp_file, of = self.rfile, bs = size, iflag = "direct")
        do_pass(self, 'test_2:e', r == 0)

        d = open(self.rfile, "r")
        rbuf = d.read(size)
        d.close()

        do_pass(self, 'test_2:f', str(wbuf) == rbuf)

        del_tmpfile(tmp_file, tc=self)
        do_unmount("%stest" % mountdir, tc=self)

    def test_3(self):

        #
        # 1. initialize a HDD sector with content 'x'. sync. drop caches.
        # 2. accelerate HDD with SSD and setup whole disk acceleration.
        # 3. write HDD sector with content 'y'. sync. drop caches. assert a write back has happend.
        # 4. reclaim 1 RU, should fail because RU is dirty.    
        # 5. do 1 - 4 in a loop to fillup one RU
        # 6. issue copyback of RU.
        # 7. assert writecache count == copyback count
        # 8. de-accelerate the device
        #

        bsize = 4096
        N = 5

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.func_1(fd, offset)
            offset += 4096
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        import time

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")
        self.copyback_set_threshold(2, 0)

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.func_2(fd, offset)
            offset += 4096
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        self.copyback_disk(0, 1)
        stats = getxstats(self.primary_volume)        
        do_pass(self, 'test_3:a', stats.get('cs_writecache_flow') == N)
        do_pass(self, 'test_3:b', stats.get('cs_writecache_flow') == stats.get('cs_copyback_flow'))

        deaccelerate_dev(self.primary_volume, tc=self)

    def test_4(self):

        #
        # 1. Disable copyback by increasing the copyback_interval in proc.
        #    Increase the copyback max to decrease time taken for letgo.
        # 2. initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches. assert a write back has happend.
        # 5. read from HDD sector and assert that content is 'q' - this has to be done via an ioctl to bypass the cache.
        # 6. do 4 - 5 in a loop to fillup one RU
        # 8. issue copyback of RU.
        # 9. assert writecache count == copyback count
        # 10. read from HDD and assert that the content is now 'y' - this has to be done via an ioctl to bypass the cache.
        # 11. de-accelerate the device
        #

        self.copyback_disable()

        bsize = 4096
        N = 5

        init_buf = 'q' * 4096

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.func_3(fd, 'q', offset)
            offset += 4096
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")

        sb = self.read_super()
        csb_start_sect = sb.csb_start_sect
        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
                self.func_3(fd, 'y', offset)
                sect = offset >> 9
                buf = self.read_bypass_from_disk(sect + csb_start_sect)
                assert(buf == init_buf)
                offset += 4096
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)
        do_pass(self, 'test_4:a', buf == init_buf)

        self.copyback_disk(0, 1)

        stats = getxstats(self.primary_volume) 
        do_pass(self, 'test_4:b', stats.get('cs_writecache_flow') == N)
        do_pass(self, 'test_4:c', stats.get('cs_writecache_flow') == stats.get('cs_copyback_flow'))

        sect = 0
        tmp_buf = 'y' * 4096
        for x in xrange(N): 
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            sect += ((4096) >> 9)
            assert(tmp_buf == buf)

        do_pass(self, 'test_4:d', buf == tmp_buf)
        deaccelerate_dev(self.primary_volume, tc=self)
        self.copyback_enable()

    def test_5(self):

        #
        # 1. Disable copyback by increasing the copyback_interval in proc
        # 2. initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches. assert a write back has happend.
        # 5. read from HDD sector and assert that content is 'y' - this has to be done via an ioctl to bypass the cache.
        # 6. Read the fct map to get the SSD sectors correspoding to the HDD sectors 
        # 7. issue copyback of RU.
        # 8. assert writecache count == copyback count
        # 9. Read the correspoding SSD sector, assert HDD sector buf ==  SSD sector buf == 'y'
        # 10. de-accelerate the device
        #

        self.copyback_disable()

        bsize = 4096
        N = 5

        init_buf = 'q' * 4096

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.func_3(fd, 'q', offset)
            offset += bsize
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")

        sb = self.read_super()
        csb_start_sect = sb.csb_start_sect
        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.func_3(fd, 'y', offset)
            sect = offset >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == init_buf)
            offset += bsize
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        do_pass(self, 'test_5:a', buf == init_buf)

        flush_forward_maps(self.primary_volume, self)

        fct_map = self.read_region_fmap(0)

        self.copyback_disk(0, 1)

        stats = getxstats(self.primary_volume) 
        do_pass(self, 'test_5:b', stats.get('cs_writecache_flow') == N)
        do_pass(self, 'test_5:c', stats.get('cs_writecache_flow') == stats.get('cs_copyback_flow'))

        tmp_buf = 'y' * bsize
        hdd_buf = tmp_buf
        ssd_buf = tmp_buf
        for hdd, ssd in fct_map:
            hdd_buf = self.read_bypass_from_disk(hdd)
            ssd_buf = self.read_bypass_from_disk(ssd, bypass = 0)
            assert(tmp_buf == hdd_buf)
            assert(hdd_buf == ssd_buf)

        do_pass(self, 'test_5:d', (hdd_buf == ssd_buf) and (tmp_buf == hdd_buf))

        self.copyback_enable()
        deaccelerate_dev(self.primary_volume, tc=self)

    def test_6(self):

        #
        # 1. Disable copyback by increasing the copyback_interval in proc
        # 2. initialize a HDD sector with content 'x'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content pattern-i. sync. drop caches.
        # 5. issue copyback for the corresponding RU.
        # 6. read from HDD sector and assert that content is pattern-i - 
        #    this has to be done via an ioctl to bypass the cache.
        # 7. assert current copyback_flow >= old copyback_flow + 255
        # 8. repeat step 4 - 7 with different pattern. 
        # 9. de-accelerate the device
        #

        self.copyback_disable()

        bsize = 4096
        N = 5

        init_buf = 'q' * 4096

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.func_3(fd, 'q', offset)
            offset += bsize
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")

        sb = self.read_super()
        csb_start_sect = sb.csb_start_sect
        offset = 0
        tmp_buf = 'y' * bsize
        for x in xrange(N):
            fd = os.open(self.primary_volume, os.O_RDWR)
            self.func_3(fd, 'y', offset)
            sect = offset >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == init_buf)
            os.fsync(fd)
            os.close(fd)
            drop_caches(self)
            self.copyback_disk(0, 1)
            stats = getxstats(self.primary_volume) 
            assert(stats.get('cs_writecache_flow') == stats.get('cs_copyback_flow'))
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == tmp_buf)
            offset += bsize

        do_pass(self, 'test_6', buf == tmp_buf)

        self.copyback_enable()
        deaccelerate_dev(self.primary_volume, tc=self)

    def test_7(self):

        #
        # 1. Disable copyback by increasing the copyback_interval in proc
        # 2. initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches until we are out of cache space
        # 5. issue copyback for the corresponding RU.
        # 6. Write 'z' on first HDD sector
        # 7. issue copyback for the corresponding RU.
        # 8. bypass the cache and read from the HDD - assert that patterns starts with 'z' and ends with 'pattern-i'
        # 9. de-accelerate the device
        #

        self.copyback_disable()

        bsize = 4096
        N = (get_devsz(self.primary_volume) << 9)/ MB_BUF_SIZE

        init_buf = 'q' * 4096

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.write_pattern(fd, 'q', offset)
            offset += MB_BUF_SIZE
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")

        sb = self.read_super()
        csb_start_sect = sb.csb_start_sect
        attrs = getattrs(self.primary_volume)
        ebcount = attrs.get('ebcount')

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        tmp_buf = 'y' * bsize
        for x in xrange(N):
            self.write_pattern(fd, 'y', offset)
            sect = offset >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == init_buf)
            offset += MB_BUF_SIZE

        offset = 0
        for x in xrange(N):
            self.write_pattern(fd, 'y', offset)
            sect = offset >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == init_buf)
            offset += MB_BUF_SIZE
            stats = getxstats(self.primary_volume)
            if stats.get('cs_free_wrap_around') > 0:
                break

        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        do_pass(self, 'test_7a', buf == init_buf)

        stats = getxstats(self.primary_volume)
        assert(stats.get('cs_free_wrap_around') > 0)
        assert(stats.get('cs_copyback_flow') == 0)

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        self.write_pattern(fd, 'z', offset)
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        self.copyback_disk(0, int(ebcount))

        do_pass(self, 'test_7b', 1)

        tmp_buf = 'z' * bsize
        for x in xrange(MB_BUF_SIZE/ bsize):
            sect = offset >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == tmp_buf)
            offset += bsize

        do_pass(self, 'test_7c', buf == tmp_buf)

        self.copyback_enable()
        deaccelerate_dev(self.primary_volume, tc=self)

    def test_8(self):

        #
        # 1. Disable copyback by increasing the copyback_interval in proc
        # 2. initialize a HDD sector with content 'x'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content pattern-i. sync. drop caches. 
        #    assert a write back has happend. (first 255 4k blocks)
        # 5. read from HDD sector and assert that content is not pattern-i - 
        #    this has to be done via an ioctl to bypass the cache.
        # 6. repeat step 4 - 5 with different pattern from 'a' - 'z' on the same RU
        # 7. issue copyback for all the RU's 
        # 8. bypass the cache and read from the HDD - assert that pattern is 'z'
        # 9. de-accelerate the device
        #

        self.copyback_disable()

        bsize = 4096
        N = 5

        init_buf = '1' * 4096

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.func_3(fd, '1', offset)
            offset += bsize
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")

        sb = self.read_super()
        csb_start_sect = sb.csb_start_sect
        fd = os.open(self.primary_volume, os.O_RDWR)

        strlist = list(string.ascii_lowercase)

        for pattern in strlist:
            offset = 0
            for x in xrange(N):
                    self.func_3(fd, pattern, offset)
                    sect = offset >> 9
                    buf = self.read_bypass_from_disk(sect + csb_start_sect)
                    assert(buf == init_buf)
                    offset += bsize
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        do_pass(self, 'test_8:a', buf == init_buf)

        self.copyback_disk(0, 1)

        stats = getxstats(self.primary_volume) 
        do_pass(self, 'test_8:b', stats.get('cs_writecache_flow') == N)
        do_pass(self, 'test_8:c', stats.get('cs_writecache_flow') == stats.get('cs_copyback_flow'))

        tmp_buf = pattern * 4096
        offset = 0
        for x in xrange(N):
            sect = offset >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == tmp_buf)
            offset += bsize

        do_pass(self, 'test_8:d', 1)

        self.copyback_enable()
        deaccelerate_dev(self.primary_volume, tc=self)


    def test_9(self):

        #
        # 1. Disable copyback by increasing the copyback_interval in proc
        # 2. initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches.
        # 5. read from HDD sector and assert that content is not 'y' - this 
        #    has to be done via an ioctl to bypass the cache.
        # 6. issue copyback for alternate RU's
        # 7. read HDD for all RU's and assert they are y buf while other are 
        #    'q' buf - this has to be done via an ioctl to bypass the cache.
        # 8. de-accelerate the device
        #

        self.copyback_disable()

        bsize = 4096
        N = (get_devsz(self.primary_volume) << 9)/ MB_BUF_SIZE

        init_buf = 'q' * 4096

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.write_pattern(fd, 'q', offset)
            offset += MB_BUF_SIZE
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")

        sb = self.read_super()
        csb_start_sect = sb.csb_start_sect
        attrs = getattrs(self.primary_volume)
        ebcount = attrs.get('ebcount')

        #
        # To avoid reclaim, issue IO's till ebcount - 2 RU's, leaving
        # atleast 2 MB of space.
        #
        S = int(ebcount) - 2
        if S > N:
            S = N - 2

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        tmp_buf = 'y' * bsize
        for x in xrange(S):
            self.write_pattern(fd, 'y', offset)
            sect = offset >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == init_buf)
            offset += MB_BUF_SIZE

        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        stats = getxstats(self.primary_volume)
        assert(stats.get('cs_free_wrap_around') == 0)

        do_pass(self, 'test_9a', buf == init_buf)

        for x in xrange(S):
            if ((x % 2) == 0):
                self.copyback_disk(x, x + 1)

        do_pass(self, 'test_9b', 1)

        #
        # Read a random offset on HDD and verify if copyback
        # is done.
        #

        offset = 0
        for x in xrange(S):
            sect = (offset + (bsize * 10)) >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            if ((x % 2) == 0):
                assert(buf == tmp_buf)
            else:
                assert(buf == init_buf)
            offset += MB_BUF_SIZE

        do_pass(self, 'test_9', 1)

        self.copyback_enable()
        deaccelerate_dev(self.primary_volume, tc=self)

    def test_10(self):

        #
        # 1. Disable copyback by increasing the copyback_interval in proc
        # 2. initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches. assert a 
        #    write back has happend.
        # 5. read from HDD sector and assert that content is not 'y' - this
        #    has to be done via an ioctl to bypass the cache.
        # 6. copyback the same RU
        # 7. read from HDD sector and assert that content is 'y' - this has
        #    to be done via an ioctl to bypass the cache.
        # 8. repeat 4 - 7 for the same RU.
        # 9. de-accelerate the device
        #

        self.copyback_disable()

        bsize = 4096
        N = 5

        init_buf = '1' * 4096

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.func_3(fd, '1', offset)
            offset += bsize
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")

        sb = self.read_super()
        csb_start_sect = sb.csb_start_sect
        strlist = list(string.ascii_lowercase)

        tmp_buf = init_buf
        offset = 0
        for pattern in strlist:
            fd = os.open(self.primary_volume, os.O_RDWR)
            self.func_3(fd, pattern, offset)
            sect = offset >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == tmp_buf)
            os.fsync(fd)
            os.close(fd)
            drop_caches(self)
            tmp_buf = pattern * 4096
            self.copyback_disk(0, 1)
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == tmp_buf)
            stats = getxstats(self.primary_volume) 
            do_pass(self, 'test_10:%s' % pattern, stats.get('cs_writecache_flow') == stats.get('cs_copyback_flow'))

        self.copyback_enable()
        deaccelerate_dev(self.primary_volume, tc=self)

    def test_11(self):

        #
        # 1. Disable copyback by increasing the copyback_interval in proc
        # 2. initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches.
        # 5. read from HDD sector and assert that content is not 'y' - this
        #    has to be done via an ioctl to bypass the cache.
        # 6. copyback all RU's in one thread and another thread should perform letgo
        # 7. validate that the data is not corrupted
        #

        self.copyback_disable()

        bsize = 4096
        N = (get_devsz(self.primary_volume) << 9)/ MB_BUF_SIZE

        init_buf = '1' * 4096

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.write_pattern(fd, '1', offset)
            offset += MB_BUF_SIZE
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")

        sb = self.read_super()
        csb_start_sect = sb.csb_start_sect
        attrs = getattrs(self.primary_volume)
        ebcount = attrs.get('ebcount')

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        tmp_buf = 'y' * bsize
        for x in xrange(N):
            self.write_pattern(fd, 'y', offset)
            sect = offset >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == init_buf)
            offset += MB_BUF_SIZE

        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        do_pass(self, 'test_11a', 1)

        ev.clear()

        copyback_thread = threading.Thread(target=self.thread_copyback, args=(ebcount, 1, ))
        letgo_thread = threading.Thread(target=self.thread_letgo)

        copyback_thread.start()
        letgo_thread.start()

        time.sleep(1)

        ev.set()
 
        copyback_thread.join()
        letgo_thread.join()

        offset = 0
        tmp_buf = 'y' * MB_BUF_SIZE
        for x in xrange(N):
            sect = offset >> 9
            buf = self.read_from_disk(self.primary_volume, sect, MB_BUF_SIZE)
            assert(buf == tmp_buf)
            offset += MB_BUF_SIZE

        self.copyback_enable()
        do_pass(self, 'test_11', buf == tmp_buf)

    def test_12(self):

        #
        # 1. Disable copyback by increasing the copyback_interval in proc
        # 2. initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches.
        # 5. read from HDD sector and assert that content is not 'y' - this 
        #    has to be done via an ioctl to bypass the cache.
        # 6. keep doing read and write IO's along with copyback with seperate 
        #    threads and another thread should perform letgo
        # 7. validate that the data is not corrupted
        #

        self.copyback_disable()

        bsize = 4096
        N = (get_devsz(self.primary_volume) << 9)/ MB_BUF_SIZE

        init_buf = '1' * 4096

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.write_pattern(fd, '1', offset)
            offset += MB_BUF_SIZE
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")

        sb = self.read_super()
        csb_start_sect = sb.csb_start_sect
        attrs = getattrs(self.primary_volume)
        ebcount = attrs.get('ebcount')

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        tmp_buf = 'y' * bsize
        for x in xrange(N):
            self.write_pattern(fd, 'y', offset)
            sect = offset >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == init_buf)
            offset += MB_BUF_SIZE

        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        do_pass(self, 'test_12a', buf == init_buf)

        ev.clear()

        fd = os.open(self.primary_volume, os.O_RDWR)

        copyback_thread = threading.Thread(target=self.thread_copyback, args=(ebcount, 1, ))
        letgo_thread = threading.Thread(target=self.thread_letgo)
        readio_thread = threading.Thread(target=self.thread_readio, args=(fd, N, 1, ))
        writeio_thread = threading.Thread(target=self.thread_writeio, args=(fd, N, 1, ))

        writeio_thread.start()
        readio_thread.start()
        copyback_thread.start()
        letgo_thread.start()

        time.sleep(1)

        copyback_thread.join()
        letgo_thread.join()
        readio_thread.join()
        writeio_thread.join()

        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        offset = 0
        tmp_buf = 'w' * MB_BUF_SIZE
        for x in xrange(N):
            sect = offset >> 9
            buf = self.read_from_disk(self.primary_volume, sect, MB_BUF_SIZE)
            assert(buf == tmp_buf)
            offset += MB_BUF_SIZE

        self.copyback_enable()
        do_pass(self, 'test_12', buf == tmp_buf)

    def test_13(self):

        #
        # 1. Increase the copyback frequency and number of RUs it needs to process 
        # 2. Initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches.
        # 5. Again write HDD with content 'x'. sync. drop caches.
        # 6. letgo of the device.
        # 7. read from HDD and assert that the data is still 'x'
        #

        bsize = 4096
        N = (get_devsz(self.primary_volume) << 9)/ MB_BUF_SIZE

        init_buf = 'q' * 4096

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.write_pattern(fd, 'q', offset)
            offset += MB_BUF_SIZE
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        tmp_buf = 'y' * bsize
        for x in xrange(N):
            self.write_pattern(fd, 'y', offset)
            sect = offset >> 9
            offset += MB_BUF_SIZE

        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        tmp_buf = 'x' * bsize
        for x in xrange(N):
            self.write_pattern(fd, 'x', offset)
            sect = offset >> 9
            offset += MB_BUF_SIZE

        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        deaccelerate_dev(self.primary_volume, tc=self)

        offset = 0
        tmp_buf = 'x' * MB_BUF_SIZE
        for x in xrange(N):
            sect = offset >> 9
            buf = self.read_from_disk(self.primary_volume, sect, MB_BUF_SIZE)
            assert(buf == tmp_buf)
            offset += MB_BUF_SIZE

        do_pass(self, 'test_13', buf == tmp_buf)

    def test_14(self):

        #
        # 1. Disable copyback by increasing the copyback_interval in proc
        # 2. Initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches. 
        #    Bypass cache and validate that the content is still 'q'.
        # 5. copyback the RUs
        # 6. Bypass and read from HDD and assert that the data is 'y' 
        # 7. Issue partial IOs on the HDD with pattern 'z' and assert cs_partial_io > 0
        # 8. Bypass and read from HDD and assert that the data is 'y' 
        # 9. De-accelarte the volume
        # 10. Read from HDD and assert that the data is now 'z'
        #  

        self.copyback_disable()

        bsize = 4096
        N = 10

        init_buf = 'q' * bsize

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.func_3(fd, 'q', offset)
            offset += bsize
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self,
                       write_policy = "write-back")

        sb = self.read_super()
        csb_start_sect = sb.csb_start_sect
        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.func_3(fd, 'y', offset)
            sect = offset >> 9
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            assert(buf == init_buf)
            offset += bsize

        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        do_pass(self, 'test_14:a', buf == init_buf)

        self.copyback_disk(0, 1)

        stats = getxstats(self.primary_volume) 
        do_pass(self, 'test_14:b', stats.get('cs_writecache_flow') == N)
        do_pass(self, 'test_14:c', stats.get('cs_writecache_flow') == stats.get('cs_copyback_flow'))

        sect = 0
        tmp_buf = 'y' * bsize
        for x in xrange(N): 
            buf = self.read_bypass_from_disk(sect + csb_start_sect)
            sect += ((bsize) >> 9)
            assert(tmp_buf == buf)

        do_pass(self, 'test_14:d', buf == tmp_buf)

        psize = bsize / (bsize >> 9)
        N = N * (bsize >> 9)

        #
        # Do direct IO with 512 bs
        #
        fd = os.open(self.primary_volume, os.O_RDWR|os.O_DIRECT)
        offset = 0
        ptmp_buf = 'z' * (psize)
        m = mmap.mmap(-1, psize)
        m.write(ptmp_buf)

        for x in xrange(N):
            os.lseek(fd, offset, os.SEEK_SET)
            os.write(fd, m)
            sect = offset >> 9
            #
            # Leave the last 7 bytes as reading 4K may give older
            # HDD data, as it will go beyond the HDD sectors used
            # in this test case
            #
            if x <= (N - (bsize >> 9)):
                buf = self.read_bypass_from_disk(sect + csb_start_sect)
                assert(buf == tmp_buf)
            offset += psize

        m.close()
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        do_pass(self, 'test_14:e', buf == tmp_buf)

        stats = getxstats(self.primary_volume)
        do_pass(self, 'test_14:f', stats.get('cs_partialio') > 0)

        deaccelerate_dev(self.primary_volume, tc=self)

        N = N / (bsize >> 9)
        offset = 0
        tmp_buf = 'z' * bsize
        for x in xrange(N):
            sect = offset >> 9
            buf = self.read_from_disk(self.primary_volume, sect, bsize)
            assert(buf == tmp_buf)
            offset += bsize

        self.copyback_enable()
        do_pass(self, 'test_14', buf == tmp_buf)

    def test_15(self):

        #
        # 1. Disable the steady state copyback, but increase number of RUs it needs to process 
        # 2. Initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches.
        # 5. Again write HDD with content 'x'. sync. drop caches.
        # 6. letgo of the device.
        # 7. read from HDD and assert that the data is still 'x'
        #

        self.copyback_disable()

        bsize = 4096
        N = (get_devsz(self.primary_volume) << 9)/ MB_BUF_SIZE

        init_buf = 'q' * 4096

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        for x in xrange(N):
            self.write_pattern(fd, 'q', offset)
            offset += MB_BUF_SIZE
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self,
                       write_policy = "write-back")

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        tmp_buf = 'y' * bsize
        for x in xrange(N):
            self.write_pattern(fd, 'y', offset)
            sect = offset >> 9
            offset += MB_BUF_SIZE

        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        fd = os.open(self.primary_volume, os.O_RDWR)
        offset = 0
        tmp_buf = 'x' * bsize
        for x in xrange(N):
            self.write_pattern(fd, 'x', offset)
            sect = offset >> 9
            offset += MB_BUF_SIZE

        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        stats = getxstats(self.primary_volume)
        do_pass(self, 'test_15:a', stats.get('cs_copyback_flow') == 0)

        deaccelerate_dev(self.primary_volume, tc=self)

        offset = 0
        tmp_buf = 'x' * MB_BUF_SIZE
        for x in xrange(N):
            sect = offset >> 9
            buf = self.read_from_disk(self.primary_volume, sect, MB_BUF_SIZE)
            assert(buf == tmp_buf)
            offset += MB_BUF_SIZE

        self.copyback_enable()
        do_pass(self, 'test_15', buf == tmp_buf)

    def test_16(self):

        #
        # 1. Disable the steady state copyback, but increase number of RUs it needs to process 
        # 2. Initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches.
        # 5. Again write HDD with content 'x'. sync. drop caches.
        # 6. letgo of the device.
        # 7. read from HDD and assert that the data is still 'x'
        #

        self.copyback_disable()

        bsize = 4096

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self,
                       write_policy = "write-back")

        fd = os.open(self.primary_volume, os.O_RDWR)

        strlist = list(string.ascii_lowercase)

        for x in xrange(10000):
            for pattern in strlist:
                offset = 0
                for x in xrange(255):
                    self.func_3(fd, pattern, offset)
                    offset += bsize
        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        deaccelerate_dev(self.primary_volume, tc=self)
        self.copyback_enable()

        do_pass(self, 'test_16')

    def test_17(self):

        #
        # 1. Disable copyback by increasing the copyback_interval in proc
        # 2. initialize a HDD sector with content 'q'. sync. drop caches.
        # 3. accelerate HDD with SSD and setup whole disk acceleration.
        # 4. write HDD sector with content 'y'. sync. drop caches.
        # 5. read from HDD sector and assert that content is not 'y' - this 
        #    has to be done via an ioctl to bypass the cache.
        # 6. keep doing read and write IO's along with copyback with seperate 
        #    threads and another thread should perform letgo
        # 7. validate that the data is not corrupted
        #

        self.copyback_disable()

        bsize = 4096
        N = 255

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self,
                       write_policy = "write-back")

        ev.clear()

        fd = os.open(self.primary_volume, os.O_RDWR)

        copyback_thread = threading.Thread(target=self.thread_copyback, args=(2, 2000, ))
        readio_thread = threading.Thread(target=self.thread_readio, args=(fd, N, 1000, ))
        writeio_thread = threading.Thread(target=self.thread_writeio, args=(fd, N, 1000, ))

        writeio_thread.start()
        readio_thread.start()
        copyback_thread.start()

        time.sleep(1)

        copyback_thread.join()
        readio_thread.join()
        writeio_thread.join()

        os.fsync(fd)
        os.close(fd)
        drop_caches(self)

        deaccelerate_dev(self.primary_volume, tc=self)
        self.copyback_enable()

        do_pass(self, 'test_17', 1)

    def test_18(self):

        #
        # 1. Accelerate the device in monitoring mode. Verify that copyback
        #    is disabled by default
        # 2. Set all admit maps.
        # 3. Set copyback max threshold to 1 and min to 0
        # 4. write data on the accelerated volume
        # 5. sleep for 60 seconds and verify that there was no copyback 
        # 6. assert that dirty perc was greater than 1
        # 7. initiate copyback
        # 8. assert that dirty perc is now less than prev dirty perc
        # 9. assert that copyback flow is greater than 0
        # 10. de-accelerate the device.
        #
 
        bsize = 4096
        count = 20000

        accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back", mode = "monitor")
        setpolicy_dev("fulldisk", self.primary_volume, None, tc=self)
        self.copyback_set_threshold(1, 0)
        dodd(inf = "/dev/zero", of = self.primary_volume, bs = bsize, count = count, oflag = "direct")
        drop_caches(self)
        time.sleep(60)
        stats = getxstats(self.primary_volume)
        dirty = float(stats.get('dirty'))
        do_pass(self, 'test_18 a', dirty > 1)
        do_pass(self, 'test_18 b', int(stats.get('cs_copyback_flow')) == 0)
        self.copyback_ioctl(50)
        stats = getxstats(self.primary_volume)
        do_pass(self, 'test_18 c', dirty > float(stats.get('dirty')))
        do_pass(self, 'test_18 d', int(stats.get('cs_copyback_flow')) > 0)
        deaccelerate_dev(self.primary_volume, tc=self)

if __name__ == '__main__':
    unittest.main(argv=["copyback.py"] + args)
