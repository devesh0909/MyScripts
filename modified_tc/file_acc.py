import common_utils
import fcntl
import getopt
import os.path
import random
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from common_utils import *
from cblog import *
from layout import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)


path = os.getcwd()+"/../tools"
os.environ['PATH'] = "%s:%s" % (os.getenv('PATH'), path)

WRITE_POLICY = ['write-back', 'write-through', 'write-around', 'read-around']

class FileAcceleration(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(FileAcceleration, self).setUp()
        self.pvn1 = random.choice(PRIMARY_VOLUMES)
        self.svn1 = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(FileAcceleration, self).tearDown()
        if isdev_accelerated(self.pvn1):
            deaccelerate_dev(self.pvn1, tc = self)
        if is_mounted("%stest" % mountdir):
            do_unmount("%stest" % mountdir, tc = self)


    def test_1(self):
        for policies in WRITE_POLICY:
            do_mkfs(self.pvn1, "default", self)
            do_mkdir("%stest" % mountdir, tc = self)
            do_mount(self.pvn1, "%stest" % mountdir, tc = self)
            lmddwritezerotofile("%stest/filetmp" % mountdir, 4096, 10000, 0)
            acceleratedev(self.pvn1, self.svn1, 4096, self, write_policy = policies)
            deaccelerate_dev(self.pvn1, tc = self)
            acceleratedev(self.pvn1, self.svn1, 4096, self, \
                            write_policy = policies, mode = "monitor")
            acceleratedir(self, self.pvn1, "%stest/filetmp" % mountdir)
            self.flush()
            for j in range(0, 5):
                if policies == 'read-around':
                    break
                lmddreadfromfile("%stest/filetmp" % mountdir, 4096, 1000, j) 
                self.flush()
                stat = getxstats(self.pvn1)
                self.assertNotEqual(int(stat['cs_readpopulate_flow']), 0)
            deaccelerate_dev(self.pvn1, tc = self)
            do_unmount("%stest" % mountdir, self)
            del_tmpfile("%stest/filetmp" % mountdir, self)
            shutil.rmtree("%stest" % mountdir)


    def test_2(self):
        for policies in WRITE_POLICY:
            do_mkfs(self.pvn1, "default", self)
            do_mkdir("%stest" % mountdir, tc = self)
            do_mount(self.pvn1, "%stest" % mountdir, tc = self)
            dodd(inf = "/dev/urandom", of = "%stest/file_fr_link" % mountdir, bs = "4k", count = "1000")
            create_symbolic_link('%stest/file_fr_link' % mountdir, \
                          '%stest/sym_link' % mountdir)
            acceleratedev(self.pvn1, self.svn1, 4096, self, \
                        write_policy = policies, mode = "monitor")
            acceleratedir(self, self.pvn1, "%stest/sym_link" % mountdir)
            first_stat = getxstats(self.pvn1)
            self.flush()
            for j in range(0, 5):
                if policies == 'read-around':
                    break
                lmddreadfromfile("%stest/sym_link" % mountdir, 4096, 1000, j) 
                stat = getxstats(self.pvn1)
                self.assertEqual(int(stat['cs_readpopulate_flow']), \
                                int(first_stat['cs_readpopulate_flow']))

            deaccelerate_dev(self.pvn1, tc = self)
            remove_symbolic_link("%stest/sym_link" % mountdir)
            do_unmount('%stest' % mountdir, self)
            del_tmpfile("%stest/sym_link" % mountdir, self)
            shutil.rmtree("%stest" % mountdir)


    def test_3(self):
        for policies in WRITE_POLICY:
            do_mkfs(self.pvn1, 1024, self)
            do_mkdir("%stest" % mountdir, tc = self)
            do_mount(self.pvn1, "%stest" % mountdir, tc = self)
            for s in cbqaconfig['TEST_BSIZES']:
                bsize = 1 << s
                dev_blksz = get_devblksz(self.pvn1)
                if bsize > dev_blksz:
                    continue
                dodd(inf = "/dev/urandom", of = "%stest/filetmp" % mountdir, bs = bsize, count = "1000")

                acceleratedev(self.pvn1, self.svn1, bsize, self, write_policy = policies)
                deaccelerate_dev(self.pvn1, tc = self)
                acceleratedev(self.pvn1, self.svn1, bsize, self, \
                            write_policy = policies, mode = "monitor")
                acceleratedir(self, self.pvn1, "%stest/filetmp" % mountdir)
                self.flush()
                first_stat = getxstats(self.pvn1)
                for j in range(0, 5):
                    if policies == 'read-around':
                        break
                    lmddreadfromfile("%stest/filetmp" % mountdir, bsize, 1000, j) 
                    self.flush()
                    stat = getxstats(self.pvn1)
                    self.assertTrue(int(stat['cs_readpopulate_flow']) > \
                                    int(first_stat['cs_readpopulate_flow']))
                deaccelerate_dev(self.pvn1, tc = self)
            do_unmount("%stest" % mountdir, self)
            del_tmpfile("%stest/filetmp" % mountdir, self)
            shutil.rmtree("%stest" % mountdir)


    def test_4(self):
        for policies in WRITE_POLICY:
            do_mkfs(self.pvn1, 2048, self)
            do_mkdir("%stest" % mountdir, tc = self)
            do_mount(self.pvn1, "%stest" % mountdir, tc = self)
            for s in cbqaconfig['TEST_BSIZES']:
                bsize = 1 << s
                dev_blksz = get_devblksz(self.pvn1)
                if bsize > dev_blksz:
                    continue
                lmddwritezerotofile("%stest/filetmp" % mountdir, bsize, 10000, 0)
                acceleratedev(self.pvn1, self.svn1, bsize, self, write_policy = policies)
                deaccelerate_dev(self.pvn1, self)
                acceleratedev(self.pvn1, self.svn1, bsize, self, \
                            write_policy = policies, mode = "monitor")
                acceleratedir(self, self.pvn1, "%stest/filetmp" % mountdir)
                self.flush()
                first_stat = getxstats(self.pvn1)
                for j in range(0, 10):
                    if policies == 'read-around':
                        break
                    lmddreadfromfile("%stest/filetmp" % mountdir, bsize, 1000, j)
                    self.flush()
                    stat = getxstats(self.pvn1)
                    self.assertTrue(int(stat['cs_readpopulate_flow']) > \
                                    int(first_stat['cs_readpopulate_flow']))
                deaccelerate_dev(self.pvn1, self)
            do_unmount("%stest" % mountdir, self)
            del_tmpfile("%stest/filetmp" % mountdir, self)
            shutil.rmtree("%stest" % mountdir)


    def test_5(self):
        for policies in WRITE_POLICY:
            do_mkfs(self.pvn1, 4096, self)
            do_mkdir("%stest" % mountdir, tc = self)
            do_mount(self.pvn1, "%stest" % mountdir, tc = self)
            for s in cbqaconfig['TEST_BSIZES']:
                bsize = 1 << s
                dev_blksz = get_devblksz(self.pvn1)
                if bsize > dev_blksz:
                    continue
                lmddwritezerotofile("%stest/filetmp" % mountdir, bsize, 10000, 0)
                acceleratedev(self.pvn1, self.svn1, bsize, self, write_policy = policies)
                deaccelerate_dev(self.pvn1, self)
                acceleratedev(self.pvn1, self.svn1, bsize, self, \
                            write_policy = policies, mode = "monitor")
                acceleratedir(self, self.pvn1, "%stest/filetmp" % mountdir)
                self.flush()
                first_stat = getxstats(self.pvn1)
                for j in range(0, 5):
                    if policies == 'read-around':
                        break
                    lmddreadfromfile("%stest/filetmp" % mountdir, bsize, 1000, j)
                    self.flush()
                    stat = getxstats(self.pvn1)
                    self.assertTrue(int(stat['cs_readpopulate_flow']) > \
                                    int(first_stat['cs_readpopulate_flow']))
                deaccelerate_dev(self.pvn1, self)
            do_unmount("%stest" % mountdir, self)
            del_tmpfile("%stest/filetmp" % mountdir, self)
            shutil.rmtree("%stest" % mountdir)


    def test_6(self):
        for policies in WRITE_POLICY:
            do_mkfs(self.pvn1, "default", self)
            do_mkdir("%stest" % mountdir, tc = self)
            do_mount(self.pvn1, "%stest" % mountdir, tc = self)
            # Create a 1GB file	
            self.flush()
            lmddwritezerotofile("%stest/filetmp" % mountdir, 262144, 4096, 0)
            self.flush()
            acceleratedev(self.pvn1, self.svn1, 4096, self, \
                        write_policy = policies, mode = "monitor")
            '''
            cbfacc on regions of a file. Ranges we are accelerating
            right now is : 0-100MB, 100-110MB, 900MB-1024MB which is
            equal to 410 regions Test can be improved later after
            selecting the random starting offset and length (as well
            as by choosing non region aligned lengths)
            '''
            cmd = (
                "cbfacc",
                "-d",
                "%s" % self.pvn1,
                "-o",
                "file=%s,offset=%s,length=%s" % ("%stest/filetmp" % mountdir, 104857600, 10485760),
                "file=%s,offset=%s,length=%s" % ("%stest/filetmp" % mountdir, 0, 104857600),
                "file=%s,offset=%s,length=%s" % ("%s_test/filetmp" % mountdir, 943718400, 104857600)
                )

            process1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
            out, err = process1.communicate()
            self.assertEqual(process1.returncode, 0)

            # Get the number of accelerated regions. This count may be
            # greater because we map the offset+length to a fs extent
            # and accelerate the whole extent.

            os.system("cachebox -a 10 -d %s" % (self.pvn1))
            process_2 = subprocess.Popen(("cachebox -a 15 -d %s | grep \" 1\" | wc -l" %
                                (self.pvn1)), shell=True, stdout = subprocess.PIPE)
            out = process_2.communicate()[0].strip(",")
            self.assertTrue(int(out) >= 256)
            deaccelerate_dev(self.pvn1, tc = self)
            del_tmpfile("%stest/filetmp" % mountdir, self)
            do_unmount("%stest" % mountdir, self)
            shutil.rmtree("%stest" % mountdir)


    def test_7(self):
        for policies in WRITE_POLICY:
            do_mkfs(self.pvn1, "default", self)
            do_mkdir("%stest" % mountdir, tc = self)
            do_mount(self.pvn1, "%stest" % mountdir, tc = self)

            # Create a 1GB file
            lmddwritezerotofile("%stest/filetmp" % mountdir, 1048576, 1024, 0)
            acceleratedev(self.pvn1, self.svn1, 4096, self, \
                        write_policy = policies, mode = "monitor")
            # Read the regions of the whole file

            cmd="cbfacc -n -d %s -o file=%s,offset=%s,length=%s" % \
                (self.pvn1, "%stest/filetmp" % mountdir, 0, 1073741824)
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                        stderr = subprocess.PIPE, shell = True)
            output = process_1.communicate()[0].strip(",")

            # count the number of regions displayed, discount an 
            # extra , coming at the last of the output
            cmd="echo %s | sed \"s/,/\\n/g\"| wc -l" %(output)
            logger.debug(cmd)
            process_2 = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE, \
                                    stderr = subprocess.PIPE)
            out = process_2.communicate()[0].split(',')
            self.assertTrue(int(out[0]) == 2048)
            deaccelerate_dev(self.pvn1, tc = self)
            del_tmpfile("%stest/filetmp" % mountdir, self)
            do_unmount("%stest" % mountdir, self)
            shutil.rmtree("%stest" % mountdir)


    def test_8(self):
        for policies in WRITE_POLICY:
            do_mkfs(self.pvn1, "default", self)
            do_mkdir("%stest" % mountdir, tc = self)
            do_mount(self.pvn1, "%stest" % mountdir, tc = self)
            '''
            Create a 1GB file with largest default 
            extent size supported 
            '''
            cmd="fallocate -l 1G %stest/filetmp" % mountdir
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, shell=True, \
                        stdout = subprocess.PIPE, stderr =subprocess.PIPE)
            out, err = process_1.communicate()

            # Accelerate the device with default block and region size
            acceleratedev(self.pvn1, self.svn1, 4096, self, \
                        write_policy = policies, mode = "monitor")
            #
            # Read region corresponding to first 1K of the file. This 1K 
            # offset can at most span across 2 different regions (1K is 
            # divided in two different regions, starting from one and 
            # ending to other). We should get the region count as 1 or 2.
            #
            cmd="cbfacc -n -d %s -o file=%s,offset=%s,length=%s" % \
                (self.pvn1, "%stest/filetmp" % mountdir, 0, 1024)
            logger.debug(cmd)
            process_2 = subprocess.Popen(cmd, shell=True, \
                        stdout = subprocess.PIPE, stderr = subprocess.PIPE)
            # Count the number of regions displayed 
            cmd="echo %s | sed \"s/,/\\n/g\"| wc -l" %(out)
            logger.debug(cmd)
            process_2 = subprocess.Popen(cmd, shell=True, \
                        stdout = subprocess.PIPE, stderr = subprocess.PIPE)
            out, err = process_2.communicate()
            self.assertTrue(int(out) == 1 or int(out) == 2)
            deaccelerate_dev(self.pvn1, tc = self)
            del_tmpfile("%stest/filetmp" % mountdir, self)
            do_unmount("%stest" % mountdir, self)
            shutil.rmtree("%stest" % mountdir)


class TestCbfaccOnFileExtent(CBQAMixin, unittest.TestCase):
    """
    Test cbfacc for after file extent if greater than 1024 then should be start from zero.
    """
    def setUp(self):
        super(TestCbfaccOnFileExtent, self).setUp()
        self.count = 1000
        self.bsize = 1024


    def tearDown(self):
        super(TestCbfaccOnFileExtent, self).tearDown()
        if is_mounted("%stest" % mountdir):
            do_unmount("%stest" % mountdir, tc = self)
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)


    def test_1(self):
        for policies in WRITE_POLICY:
            do_mkdir("%stest" % mountdir, tc=self)
            filename = "%stest/testfile" % mountdir
            self.primary_volume = random.choice(PRIMARY_VOLUMES)
            self.ssd_volume = random.choice(SSD_VOLUMES.keys())
            do_mkfs(self.primary_volume, self.bsize, tc=self)
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, \
                            write_policy = policies, mode = "monitor")
            do_mount(self.primary_volume, "%stest" % mountdir, tc=self)
            lmddwritezerotofile(filename, 4096, self.count, 0)
            do_mkfs(filename, self.bsize, tc=self)
            logger.debug("resize2fs -f %s 90G" % filename)
            cmd = [ "resize2fs",
                    "-f",
                    filename,
                    "90G" ]
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = r.communicate()
            self.assertEqual(r.returncode, 0)
            cmd = [ "cbfacc",
                    "-d", 
                    self.primary_volume,
                    "-o file=%s",
                    filename ]
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = r.communicate()
            logger.debug(out)
            logger.debug(err)
            self.assertEqual(r.returncode, 0)
            deaccelerate_dev(self.primary_volume, tc=self)
            do_unmount("%stest" % mountdir, tc = self)
            shutil.rmtree("%stest" % mountdir)


class TestAccelerateDirectory(CBQAMixin, unittest.TestCase):
    """
    Test the acceleration of a directory on a mounted 
    accelerated device.
    """
    def setUp(self):
        super(TestAccelerateDirectory, self).setUp()
        self.count = 1000
        do_mkdir("%stest" % mountdir, tc=self)
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())


    def tearDown(self):
        super(TestAccelerateDirectory, self).tearDown()
        if is_mounted("%stest" % mountdir):
            try:
                shutil.rmtree("%stest/deep_dir") % mountdir
            except:
                pass
            try:
                remove_symbolic_link("%stest/tmp") % mountdir
            except:
                pass
            do_unmount("%stest" % mountdir, tc=self)
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)


    def test_1(self):
        for policies in WRITE_POLICY:
            do_mkfs(self.primary_volume, "default", tc = self)
            do_mount(self.primary_volume, "%stest" % mountdir, tc=self)
            # Create directory for acceleration
            dir_name = "%stest/tmp_01" % mountdir
            do_mkdir(dir_name, tc=self)
            # Write 4MB to tmp files on the directories
            filename_1 = "%s/tmp_test_01" % dir_name
            lmddwritezerotofile(filename_1, 4096, self.count, 0)
            # Accelerate one of the directory on the primary volume
            r = acceleratedir(self, self.primary_volume, dir_name, debug = True)
            self.assertNotEqual(r, 0)
            del_tmpfile(filename_1, tc=self)
            shutil.rmtree(dir_name)
            do_unmount("%stest" % mountdir, tc=self)


    def test_2(self):
        for policies in WRITE_POLICY:
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self, \
                            write_policy = policies, mode = "monitor")
            do_mkfs(self.primary_volume, "default", tc = self)
            do_mount(self.primary_volume, "%stest" % mountdir, tc=self)
            dir_name = "%stest/tmp_01" % tmpdir
            do_mkdir(dir_name, tc=self)
            filename_1 = "%s/tmp_test_01" % dir_name
            lmddwritezerotofile(filename_1, 4096, self.count, 0)
            r = acceleratedir(self, self.primary_volume, dir_name, debug = True)
            self.assertEqual(r, 0)
            del_tmpfile(filename_1, tc=self)
            shutil.rmtree(dir_name)
            do_unmount("%stest" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)


    def test_3(self):
        for policies in WRITE_POLICY:
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self, \
                           write_policy = policies, mode = "monitor")
            do_mkfs(self.primary_volume, "default", tc = self)
            do_mount(self.primary_volume, "%stest" % mountdir, tc = self) 
            # Create two directory for acceleration
            dir_name_1 = "%stest/tmp_01" % mountdir
            do_mkdir(dir_name_1, tc=self)

            dir_name_2 = "%stest/tmp_01" % mountdir
            do_mkdir(dir_name_2, tc=self)
            # Write 4MB to tmp files on the directories
            filename_1 = "%s/tmp_test_01" % dir_name_1

            filename_2 = "%s/tmp_test_01" % dir_name_2
            lmddwritezerotofile(filename_1, 4096, self.count, 0)
            lmddwritezerotofile(filename_2, 4096, self.count, 0)

            fd = os.open(filename_1, os.O_EXCL|os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX)

            fd_2 = os.open(filename_2, os.O_EXCL|os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX)

            # Accelerate one of the directory on the primary volume
            acceleratedir(self, self.primary_volume, dir_name_1)

            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

            fcntl.flock(fd_2, fcntl.LOCK_UN)
            os.close(fd_2)

            del_tmpfile(filename_1, tc=self)
            del_tmpfile(filename_2, tc=self)
            shutil.rmtree(dir_name_1)
            do_unmount("%stest" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)


    def test_4(self):
        for policies in WRITE_POLICY:
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self, \
                            write_policy = policies, mode = "monitor")
            # Mount the primary volume on a mount point
            do_mkfs(self.primary_volume, "default", tc = self)
            do_mount(self.primary_volume, "%stest" % mountdir, tc = self) 
            dir_name = "%stest/tmp_01" % mountdir
            do_mkdir(dir_name, tc=self)
            # Write 2GB to tmp files on the directories
            filename = "%s/tmp_test_large_01" % dir_name
            lmddwritezerotofile(filename, 4096, 262144, 0)
            # Accelerate one of the directory on the primary volume
            acceleratedir(self, self.primary_volume, dir_name)
            del_tmpfile(filename, tc=self)
            shutil.rmtree(dir_name)
            do_unmount("%stest" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)


    def test_5(self):
        for policies in WRITE_POLICY:
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self, \
                            write_policy = policies, mode = "monitor")
            # Mount the primary volume on a mount point
            do_mkfs(self.primary_volume, "default", tc = self)
            do_mount(self.primary_volume, "%stest" % mountdir, tc = self) 
            # Write 4MB to tmp files on the directories
            filename = "%stmp_test_01" % tmpdir
            lmddwritezerotofile(filename, 4096, self.count, 0)
            dir_name = "%stest/tmp" % mountdir
            create_symbolic_link("%s" % tmpdir, dir_name)
            acceleratedir(self, self.primary_volume, dir_name)
            # Start reading from the accelerated directory
            drop_caches(tc=self)
            lmddreadfromfile(filename, 4096, self.count, 0)
            stats = getxstats(self.primary_volume)
            self.assertEqual(int(stats['cs_readpopulate_flow']), 0)
            drop_caches(tc=self)
            lmddreadfromfile(filename, 4096, self.count, 0)
            stats = getxstats(self.primary_volume)
            self.assertEqual(int(stats['cs_read_hits']), 0)
            remove_symbolic_link(dir_name)
            del_tmpfile(filename, tc=self)
            do_unmount("%stest" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)


    def test_6(self):
        for policies in WRITE_POLICY:
            # Mount the primary volume on a mount point
            do_mkfs(self.primary_volume, "default", tc = self)
            do_mount(self.primary_volume, "%stest" % mountdir, tc=self)
            dir_name_1 = "%stest/tmp_04" % mountdir
            do_mkdir(dir_name_1, tc=self)
            dir_name = "%stest/tmp_08" % mountdir
            filename_1 = "%s/tmp_test_08" % dir_name_1
            lmddwritezerotofile(filename_1, 4096, self.count, 0)
            create_symbolic_link(dir_name_1, dir_name)
            filename = "%s/tmp_test_08" % dir_name
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, \
                            tc=self, write_policy = policies, mode = "monitor")
            # Accelerate symbolic link directory on the primary volume
            acceleratedir(self, self.primary_volume, dir_name)
            # Start reading from the accelerated directory
            drop_caches(tc=self)
            lmddreadfromfile(filename, 4096, self.count, 0)
            stats = getxstats(self.primary_volume)
            self.assertEqual(int(stats['cs_readpopulate_flow']), 0)
            drop_caches(tc=self)
            lmddreadfromfile(filename, 4096, self.count, 0)
            stats = getxstats(self.primary_volume)
            self.assertEqual(int(stats['cs_read_hits']), 0)
            remove_symbolic_link(dir_name)
            del_tmpfile(filename_1, tc=self)
            shutil.rmtree(dir_name_1)
            do_unmount("%stest" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)


    def test_7(self):
        for policies in WRITE_POLICY:
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, \
                        tc=self, write_policy = policies, mode = "monitor")
            # Mount the primary volume on a mount point
            do_mkfs(self.primary_volume, "default", tc = self)
            do_mount(self.primary_volume, "%stest" % mountdir, tc=self)
            # Create a directory for acceleration
            dir_name = "%stest/deep_dir" % mountdir
            do_mkdir(dir_name, tc=self)
            # In a loop create 10 directory and around 200 files
            # in each dir
            tmp = ''
            for d in xrange(10):
                tmp += "/dir_%s" % d
                d_name = "%stest/deep_dir%s" % (mountdir, tmp)
                do_mkdir(d_name, tc=self)
                for f in xrange(200):
                    # Write 400k to tmp files on the directories
                    filename = "%s/tmp_f_%s" % (d_name, f)
                    lmddwritezerotofile(filename, 4096, 100, 0)

            acceleratedir(self, self.primary_volume, filename)
            # Assert Nothing has been cached
            drop_caches(tc=self)
            stats = getxstats(self.primary_volume)
            self.assertEqual(int(stats['cs_readpopulate_flow']), 0)
            self.assertEqual(int(stats['cs_read_hits']), 0)
            # Start reading from the accelerated directory
            lmddreadfromfile(filename, 4096, 100, 0)
            drop_caches(tc=self)
            stats = getxstats(self.primary_volume)
            pp_2 = subprocess.Popen(("cachebox -a 15 -d %s | grep \" 1\" | \
                                    awk '{print($1)}' | head -1" % \
                  (self.primary_volume)), shell=True, stdout = subprocess.PIPE)
            out = pp_2.communicate()[0]
            if policies == "read-around":
                break
            self.assertTrue(int(stats['cs_readpopulate_flow']) >= 100)
            lmddreadfromfile(filename, 4096, 10000, 0)
            drop_caches(tc=self)
            stats = getxstats(self.primary_volume)
            self.assertTrue(int(stats['cs_read_hits']) >= 100)
            shutil.rmtree(dir_name)
            do_unmount("%stest" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)


    def test_8(self):
        for policies in WRITE_POLICY:
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, \
                        tc=self, write_policy = policies, mode = "monitor")
            # Mount the primary volume on a mount point
            do_mkfs(self.primary_volume, "default", tc = self)
            do_mount(self.primary_volume, "%stest" % mountdir, tc=self)
            dir_name = "%stest/tmp_01" % mountdir
            do_mkdir(dir_name, tc=self)
            filename = "%s/tmp_test_layout_file_01" % dir_name
            lmddwritezerotofile(filename, 4096, self.count, 0)
            acceleratedir(self, self.primary_volume, filename)
            # Write 4MB to tmp files on the directory
            drop_caches(tc=self)
            pp_1 = subprocess.Popen(("cachebox -a 15 -d %s | grep \" 1\" | \
                   wc -l" % (self.primary_volume)), shell=True, stdout = subprocess.PIPE)
            out = pp_1.communicate()[0]
            #No. of regions accelerated * 128 = no. of blocks marked caching
            self.assertTrue((out * 128) >= self.count)
            # convert sectors into 4k block and use dd to validate
            pp_2 = subprocess.Popen(("cachebox -a 15 -d %s | grep \" 1\" | \
                                    awk '{print($1)}' | head -1" % \
                  (self.primary_volume)), shell=True, stdout = subprocess.PIPE)
            out = pp_2.communicate()[0]
            skip_block = int(out) * 128
            rc = ddcheckfile(self.primary_volume, 4096, self.count, skip_block, filename)
            self.assertEqual(rc, 0)

            shutil.rmtree(dir_name)
            do_unmount("%stest" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)


    def test_9(self):
        for policies in WRITE_POLICY:
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, \
                        tc=self, write_policy = policies, mode = "monitor")
            do_mkfs(self.primary_volume, "default", tc = self)
            do_mount(self.primary_volume, "%stest" % mountdir, tc=self)
            dir_name_1 = "%stest/tmp_01" % mountdir
            do_mkdir(dir_name_1, tc=self)
            dir_name_2 = "%stest/tmp_02" % mountdir
            do_mkdir(dir_name_2, tc=self)
            filename_1 = "%s/tmp_test_12" % dir_name_1
            lmddwritezerotofile(filename_1, 4096, self.count, 0)

            filename_2 = "%s/tmp_test_12" % dir_name_2
            lmddwritezerotofile(filename_2, 4096, self.count, 0)
            drop_caches(tc=self)
            # Accelerate one of the directory on the primary volume
            acceleratedir(self, self.primary_volume, filename_1)
            # Start reading from the accelerated directory
            drop_caches(tc=self)
            lmddreadfromfile(filename_1, 4096, self.count, 0)
            stats = getxstats(self.primary_volume)
            if policies == 'read-around':
                break
            self.assertEqual(int(stats['cs_readpopulate_flow']), self.count)

            drop_caches(tc=self)
            lmddreadfromfile(filename_1, 4096, self.count, 0)
            stats = getxstats(self.primary_volume)
            self.assertEqual(int(stats['cs_read_hits']), self.count)
            drop_caches(tc=self)
            '''
            Start reading from the not accelerated directory
            There should be no change in the stats, as this
            directory has not been accelerated.
            '''
            lmddreadfromfile(filename_2, 4096, self.count, 0)
            stats = getxstats(self.primary_volume)
            self.assertEqual(int(stats['cs_readpopulate_flow']), self.count)

            drop_caches(tc=self)
            lmddreadfromfile(filename_2, 4096, self.count, 0)
            stats = getxstats(self.primary_volume)
            self.assertEqual(int(stats['cs_read_hits']), self.count)

            shutil.rmtree(dir_name_1)
            shutil.rmtree(dir_name_2)
            do_unmount("%stest" % mountdir, tc=self)
            deaccelerate_dev(self.primary_volume, tc=self)


if __name__ == '__main__':
    unittest.main(argv=["file_acc.py"] + args)
