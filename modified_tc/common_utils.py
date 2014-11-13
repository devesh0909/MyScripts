import getopt
import inspect
import os
import random
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import platform

from cblog import *
from config import *


path=os.getcwd()+"/../tools"
os.environ['PATH']="%s:%s:." % (os.getenv('PATH'), path)


RECLAIM_INTERVAL = (
    5,
)

MEMORY_CAP_PERDISK = (
    102400,
)


if platform.system() == 'Linux':
    OS = 'Linux'
elif platform.system() == 'Windows':
    OS = 'Windows'


tmpdir = "/tmp/"
mountdir = "/mnt/"

try:
    os.system("echo kbd > /sys/module/kgdboc/parameters/kgdboc")
except:
    pass

def get_config_file(argv):

    config_file = "config"

    try:
        opts, args = getopt.getopt(argv[1:], 'c:', [])
    except getopt.GetoptError:
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-c',):
            config_file = arg.split(".")[0]

    return (config_file, args)

def do_pass(tc, func, cond = 1):
    if cond:
        logger.info('%-60s %s' % (tc.__class__.__name__[:16]+'.'+ func[:24], 'pass'))
    else:
        logger.info('%-60s %s' % (tc.__class__.__name__[:16]+'.'+ func[:24], 'fail'))

def do_skip(tc, func):
    logger.info('%-60s %s' % (tc.__class__.__name__+':'+ func, 'skip'))


class AdmissionBitmap(object):
    def __init__(self, bitmap):
        self.bitmap = bitmap

    def isAccelerated(self, r):
        return(self.bitmap[r])

    def dump(self, r):
        logger.debug('index=%s bmap=%s' % (r, self.bitmap[r]))


class Pre_check(unittest.TestCase):
    def setUp(self):
        #Check if cachebox module is loaded
        cmd = "lsmod | grep cachebox > /dev/null 2>&1"
        r = os.system(cmd)
        self.assertEqual(r, 0, "cachebox module NOT loaded")

        #Check if cachebox is included in PATH
        cmd = "which cachebox > /dev/null 2>&1"
        r = os.system(cmd)
        self.assertEqual(r, 0, "cachebox NOT in $PATH")

        #clear all tmpfiles in /tmp that may be left out by previous tests
        cmd = "/bin/rm -rf %stmp*" % tmpdir
        r = os.system(cmd)


    def tearDown(self):
        pass

def do_cmd(cmd):
    r = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    out, err = r.communicate()
    return (r.returncode, out, err)


class Common_Utils_Cross(object):
    @staticmethod
    def accelerate_dev(pdevname, ssddev, bs, tc, debug = False, write_policy = DEFAULT_WRITE_POLICY, mode = DEFAULT_MODE):
       cmd = "cbasm --accelerate --device=%s --ssd=%s --write-policy=%s --mode=%s > /dev/null 2>&1" % (pdevname, ssddev, write_policy, mode)
       logger.debug(cmd)
       r = os.system(cmd)
       if debug:
           return r
       else:
           tc.assertEqual(r, 0)


    @staticmethod
    def deaccelerate_dev(devname, tc, debug=False):
       cmd = "cbasm --letgo --device=%s > /dev/null 2>&1" % devname 
       logger.debug(cmd)
       r = os.system(cmd)
       if debug:
           return r
       tc.assertEqual(r, 0)
       cmd = "sync" 
       logger.debug( cmd)
       r = os.system(cmd)
       tc.assertEqual(r, 0)


    @staticmethod
    def setpolicy_dev(spol, pdevname, pval, tc):
        cmd = (
            "cachebox",
            "-a",
            "7",
            "-d",
            "%s" % pdevname
            )

        r, o, e = do_cmd(cmd)
        tc.assertEqual(r, 0)

        cmd = (
            "cachebox",
            "-a",
            "10",
            "-d",
            "%s" % pdevname
            )

        r, o, e = do_cmd(cmd)
        tc.assertEqual(r, 0)

        return


    @staticmethod
    def getxstats(devname):
        cmd = "cachebox -x -d %s" % (devname)
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        lines = r.communicate()[0].strip('\n').split('\n')
        output = []
        for x in lines:
            k, v = x.split()
            try:
                v = int(v)
            except ValueError:
                v = float(v)
            except:
                pass
            output.append((k, v))
        return dict(output)


    @staticmethod
    def getattrs(devname):
        cmd = "cachebox -l -d %s" % (devname)
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = r.communicate()[0].strip('\n').split('\n')
        return dict(map(lambda x: (x.split()[0], x.split()[1]), output))


    @staticmethod
    def getsb(devname):
        cmd = "python layout.py -s %s --print-super" % (devname)
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = r.communicate()[0].strip('\n').split('\n')
        return dict(map(lambda x: (x.split()[0], x.split()[1]), output))


    @staticmethod
    def getadmissionbitmap(devname):
        #
        # returns the admission bitmap as a byte buffer. same as in
        # kernel.
        #
        os.system("cachebox -a 10 -d %s" % (devname))
        cmd = "cachebox -a 15 -d %s" % (devname)
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = r.communicate()[0].strip('\n').split('\n')
        return AdmissionBitmap(dict(map(lambda x: (int(x.split()[0]), int(x.split()[1], 16)), output)))


    @staticmethod
    def accelerateregion(tc, device, region, debug = False):
        cmd = "cachebox -a 4 -m %s -d %s > /dev/null 2>&1" % (region, device)
        r = os.system(cmd)
        if not debug:
            tc.assertEqual(r, 0)
        return r


    @staticmethod
    def flushadmitmap(tc, device, debug = False):
        cmd = "cachebox -a 10 -d %s > /dev/null 2>&1" % (device)
        r = os.system(cmd)
        if not debug:
            tc.assertEqual(r, 0)
        return r


    @staticmethod
    def acceleratedir(tc, device, path, debug = False):
        cmd = "cbfacc -d %s -o file=%s > /dev/null 2>&1" % (device, path)
        logger.debug( cmd)
        r = os.system(cmd)
        if debug:
            return r
        else:
            tc.assertEqual(r, 0)


    @staticmethod
    def getcoverage(tc):
        return ''


    @staticmethod
    def resetcoverage(tc):
        return


    @staticmethod
    def reclaimioctl(devname, rmax, rthreshold):
        cmd = "cachebox -d %s -M %s -T %s" % (devname, rmax, rthreshold)
        return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)


    @staticmethod
    def format_dev(devname, ssd, tc, debug = False):
        cmd = "cbfmt -d %s -s %s" % (devname, ssd)
        logger.debug(cmd)
        r = os.system(cmd)
        if debug:
            return r
        tc.assertEqual(r, 0)


    @staticmethod
    def accelerate_existingdev(devname, ssd, tc, debug = False):
        cmd = "cachebox -a 3 -d %s -s %s" % (devname, ssd)
        logger.debug(cmd)
        r = os.system(cmd)
        if debug:
            return r
        tc.assertEqual(r, 0)


    @staticmethod
    def accelerate_allregions(devname, tc):
        cmd = ["cachebox",
               "-a",
               "7",
               "-d",
               "%s" % devname
              ]
        logger.debug(cmd)
        r = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        output = r.communicate()[0]

        cmd = ["cachebox",
               "-a",
               "10",
               "-d",
               "%s" % devname
              ]
        logger.debug(cmd)
        r = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        output = r.communicate()[0]


    @staticmethod
    def flush_forward_maps(devname, tc):
        cmd = 'cachebox -a 8 -d %s' % devname
        logger.debug( cmd)
        r = os.system(cmd)
        tc.assertEqual(r, 0)


    @staticmethod
    def isdev_accelerated(devname):
        output = get_basenameofdevice(devname)

        cmd = "cachebox -l | grep %s > /dev/null" % output 
        r = os.system(cmd)
        return (1 if r == 0 else 0)


    @staticmethod
    def dolmdd(inf = "", of = "", bs = "", count = "", ipat = "", opat = "", mismatch = "", skip = "", seek = "", sync = ""):
        if inf == "":
            dinf = ""
        else:
            dinf = "if=%s" % inf
        if of == "":
            dof = ""
        else:
            dof = "of=%s" % of
        if bs == "":
            dbs = ""
        else:
            dbs = "bs=%s" % bs
        if count ==  "":
            dcount = ""
        else:
            dcount="count=%s" % count
        if ipat == "":
            dipat = ""
        else:
            dipat = "ipat=%s" % ipat
        if opat == "":
            dopat = ""
        else:
            dopat = "opat=%s" % opat
        if mismatch == "":
            dmismatch = ""
        else:
            dmismatch = "mismatch=%s" % mismatch
        if skip ==  "":
            dskip = ""
        else:
            dskip="skip=%s" % skip
        if seek ==  "":
            dseek = ""
        else:
            dseek="seek=%s" % seek
        if sync ==  "":
            dsync=""
        else:
            dsync = "sync=%s" % sync
        cmd = "lmdd %s %s %s %s %s %s %s %s %s %s" %(dinf, dof, dbs, dcount, dipat, dopat, dmismatch, dskip, dseek, dsync)
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        r.communicate()[0]
        return r.returncode


    @staticmethod
    def dodd(inf, of, bs = "", count = "", skip = "", seek = "", iflag = "", oflag = ""):
        if bs ==  "":
            sbs=""
        else:
            sbs="bs=%s"%bs
        if count ==  "":
            scount=""
        else:
            scount="count=%s"%count
        if skip ==  "":
            sskip=""
        else:
            sskip="skip=%s"%skip
        if seek ==  "":
            sseek=""
        else:
            sseek="seek=%s"%seek
        if iflag ==  "":
            siflag=""
        else:
            siflag="iflag=%s"%iflag
        if oflag ==  "":
            soflag=""
        else:
            soflag="oflag=%s"%oflag

        cmd = "dd if=%s of=%s %s %s %s %s %s %s"%(inf,of,sbs,scount,sskip,sseek,siflag,soflag)
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=True)
        r.communicate()[0]
        return r.returncode


    @staticmethod
    def cb_set_tunable(tunable, value):
        cmd="echo %s > /proc/sys/kernel/cachebox/%s" % (value, tunable)
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        r.communicate()[0]
        return r.returncode


    @staticmethod
    def cb_get_tunable(tunable):
        cmd="cat /proc/sys/kernel/cachebox/%s" % tunable
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        val = int(r.communicate()[0].rstrip('\n'))
        return val


    @staticmethod
    def accelerate_slowdown(*args, **kwargs):
        pv = kwargs.get('pv')
        sv = kwargs.get('sv')
        count = kwargs.get('count')
        assertval = kwargs.get('assert')
        write_pol = kwargs.get('write_policy')
        tc = kwargs.get('tc')
        bsize = 1 << 12
        for i in xrange(1, count):
            cmd = (
            "cbasm",
            "--accelerate",
            "--device=%s" % pv,
            "--ssd=%s" % sv,
            "--write-policy=%s" % write_pol,
            "--mode=full-disk"
            )
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()

            cmd = "cbasm --letgo --device=%s" % (pv)
            r = os.system(cmd)
            if assertval != 'ignore':
              tc.assertEqual(r, 0)
            drop_caches(tc)

            if tc.stopthread:
              logger.debug( "thread itself stopping accelerate slowdown")
              break


    @staticmethod
    def deaccelerateregion(devname, region, tc):
        # this ioctl is not supported
        return


    @staticmethod
    def deaccelerate_allregions(devname, tc):
        # this ioctl is not supported
        return


    @staticmethod
    def change_write_policy(pdevname, ssddev, write_policy, tc, debug = False):
       cmd = "cbasm --change-writepolicy --device=%s --ssd=%s --write-policy=%s > /dev/null 2>&1" % (pdevname, ssddev, write_policy)
       logger.debug(cmd)
       r = os.system(cmd)
       if debug:
           return r
       else:
           tc.assertEqual(r, 0)


    @staticmethod
    def list_accelerated_device():
        cmd = (
               "cbasm",
               "--list"
               "--accelerated"
               )
        logger.debug( cmd)
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()

        return (r.returncode, output)


if OS == 'Linux':
    class Common_Utils(Common_Utils_Cross):
        @staticmethod
        def create_devices(ssdsz, pvolsz, bs, oddsize, tc):
            ssdsz = ssdsz*1024*1024
            pvolsz = pvolsz*1024*1024

            ssdcount = ssdsz/bs
            pvolcount = pvolsz/bs

            # If the hdd and ssd are to be created Odd sizes i.e. not multiple
            # of cb region size (64K) add 1 blocks(4K) to the count
            if oddsize:
                ssdcount = ssdcount + 1
                pvolcount = pvolcount + 1

            (fd, tc.ssdtmpfile) = tempfile.mkstemp ()
            (fd, tc.hddtmpfile) = tempfile.mkstemp ()
            tc.ssdsize = ssdsz
            tc.bsize = bs
            r = dodd(inf = "/dev/zero", of = tc.ssdtmpfile, bs = bs, count = ssdcount)
            tc.assertEqual(r, 0)

            r = dodd(inf = "/dev/zero", of = tc.hddtmpfile, bs = bs, count = pvolcount)
            tc.assertEqual(r, 0)

            cmd = "losetup -f %s --show" % (tc.ssdtmpfile)
            logger.debug( cmd)
            r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            tc.ssd_volume = r.communicate()[0].rstrip('\n')
            logger.debug( "SSD device is %s" %( tc.ssd_volume))
            tc.assertEqual(r.returncode, 0)

            cmd = "losetup -f %s --show" % (tc.hddtmpfile)
            logger.debug( cmd)
            r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            tc.primary_volume= r.communicate()[0].rstrip('\n')
            logger.debug( "HDD device is %s" %( tc.primary_volume))
            tc.assertEqual(r.returncode, 0)
            time.sleep(1)


        """
        This method is used to alter the partition table without reboot
        """
        @staticmethod
        def alter_table(primary_volume, tc):
            cmd = [
                "partprobe",
                "%s" % primary_volume
                ]
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                                         stderr = subprocess.PIPE)
            out, err = process_1.communicate()


        """
        This method is used to create a partition of parimary volume
        It create 1 partitions of 1GB
        """
        @staticmethod
        def create_partition(primary_volume, tc, formats = "ntfs", size = 1):
            cmd = [
                "fdisk",
                "%s" % primary_volume
                  ]
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdin = subprocess.PIPE, \
                        stdout = subprocess.PIPE, stderr = subprocess.PIPE)
            process_1.stdin.write("n\n")
            process_1.stdin.write("p\n")
            process_1.stdin.write("\n")
            process_1.stdin.write("\n")
            process_1.stdin.write("+%sG\n" % size)
            process_1.stdin.write("w\n")
            out, err = process_1.communicate()
            logger.debug("partition creates %s %s" % (out, err))
            if process_1.returncode == 0:
                alter_table(primary_volume, tc)
                tc.assertEqual(process_1.returncode, 0)


        """
        This method is used to delete the partition of primary volume
        """
        @staticmethod
        def delete_partition(primary_volume, tc):
            cmd = [
                 "fdisk",
                 "%s" % primary_volume
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
            if process_1.returncode == 0:
                alter_table(primary_volume, tc)
                tc.assertEqual(process_1.returncode, 0)


        @staticmethod
        def create_logical_device(volume_name, logicalvol_name, size, tc):
            cmd = ("lvcreate", 
               "-L", 
               "%dG" % size, 
               "-n",
               "%s" % logicalvol_name,
               "%s" % volume_name
               )
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout = subprocess.PIPE, 
                     stderr = subprocess.PIPE)
            output, error = r.communicate()
            logger.debug("%s %s" % (output, error))
            tc.assertEqual(r.returncode, 0)


        @staticmethod
        def create_lvmdevice(volume_name ,logicalvol_name, size, device, tc):
            cmd = ("pvcreate", "%s" % (device))
            r = subprocess.Popen(cmd, stdout = subprocess.PIPE,
                 stderr = subprocess.PIPE)
            output, error = r.communicate()
            logger.debug("%s %s" % (output, error))

            cmd = ("vgcreate", "%s" % volume_name, "%s" % device)
            r = subprocess.Popen(cmd, stdout = subprocess.PIPE,
                                 stderr = subprocess.PIPE)
            output, error = r.communicate()
            logger.debug("%s %s" % (output, error))

            create_logical_device(volume_name, logicalvol_name, size, tc)


        @staticmethod
        def delete_logical_device(logicalvol_name, tc):
            cmd = "lvremove -f %s" % logicalvol_name
            logger.debug(cmd)
            r = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE, \
                                stderr = subprocess.PIPE)
            output, error = r.communicate()


        @staticmethod
        def delete_lvmdevice(logicalvol_name, volume_name, primary_volume, tc):
            delete_logical_device(logicalvol_name, tc)

            cmd = "vgremove %s" % volume_name
            logger.debug(cmd)
            r = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE, \
                                stderr = subprocess.PIPE)
            output, error = r.communicate()
            logger.debug("%s %s" % (output, error))

            cmd = "pvremove %s" % primary_volume
            logger.debug(cmd)
            r = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE, \
                                stderr = subprocess.PIPE)
            output, error = r.communicate()
            logger.debug("%s %s" % (output, error))


        #This method is used to create extend LVM in LINUX and Simple Volume in Windows
        @staticmethod
        def extend_lvmdevice(volume, tc, size = 1):
            cmd = "lvextend -L+%sG %s" % (size, volume)
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                        stderr = subprocess.PIPE,shell=True)
            out, err = process_1.communicate()
            logger.debug("%s %s" % (out, err))
            tc.assertEqual(process_1.returncode, 0)


        #size in MB
        @staticmethod
        def shrink_lvmdevice(volume, tc, size = 500):
            cmd = "lvreduce -f -L-500M %s" % volume
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                                   stderr = subprocess.PIPE,shell=True)
            out, err = process_1.communicate()
            logger.debug("%s %s" % (out, err))
            tc.assertEqual(process_1.returncode, 0)


        """
        It creates a RAID volume from two HDD disks
        """
        @staticmethod
        def create_raiddevice(device, device_2, tc):
            cmd = ("echo 'y' | mdadm -C --create /dev/md0 --level=mirror --raid-devices=2 %s %s" % (device, device_2))
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, shell=True, \
                       stderr = subprocess.PIPE)
            out, err = process_1.communicate()
            logger.debug("%s %s" % (out, err))
            tc.assertEqual(process_1.returncode, 0)


        """
        It stop the RAID volume
        then remove the RAID volume and delete the superblock.
        from all drives in the array
        """
        @staticmethod
        def delete_raiddevice(device, device_2, tc):
            cmd = ("mdadm --stop /dev/md0")
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                         stderr = subprocess.PIPE, shell = True)
            out, err = process_1.communicate()

            cmd = ("mdadm --remove /dev/md0")
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, shell=True, \
            stderr = subprocess.PIPE)

            cmd = ("mdadm --zero-superblock %s %s" % (device, device_2))
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, shell=True, \
                                       stderr = subprocess.PIPE)
            out, err = process_1.communicate()
            ss = os.system("partprobe %s %s" % (device, device_2))


        @staticmethod
        def create_dmsetup(size, volname, tc):
            cmd = """dmsetup create Test << -EOD
0 %d zero
-EOD""" % (size)
            logger.debug(cmd)
            returncode = os.system(cmd)
            tc.assertEqual(returncode, 0)
            dodd(inf = "/dev/zero", of = volname, bs = "4k", count = "10000")

            cmd = """dmsetup create test << -EOD
0 %s snapshot /dev/mapper/Test %s P 16
-EOD""" % (size, volname)
            logger.debug(cmd)
            returncode = os.system(cmd)
            tc.assertEqual(returncode, 0)


        @staticmethod
        def delete_dmsetup(tc):
            cmd = ("dmsetup remove /dev/mapper/test")
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                        stderr = subprocess.PIPE, shell = True)
            output = process_1.communicate()
            tc.assertEqual(process_1.returncode, 0)

            cmd = ("dmsetup remove /dev/mapper/Test")
            logger.debug(cmd)
            process_2 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                        stderr = subprocess.PIPE, shell = True)
            output = process_2.communicate()
            tc.assertEqual(process_2.returncode, 0)


        @staticmethod
        def get_devsz(devname):
            cmd = "blockdev --getsz %s" % devname
            r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            output = r.communicate()[0].strip('\n')
            return int(output)


        @staticmethod
        def get_devra(devname):
            cmd = "blockdev --getra %s" % devname
            r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            output = r.communicate()[0].strip('\n')
            return int(output)


        @staticmethod
        def get_devblksz(devname):
            cmd = "blockdev --getbsz %s" % devname 
            r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            output = r.communicate()[0].rstrip('\n')
            return int(output)


        @staticmethod
        def set_devra(devname, racount, tc):
            cmd = "blockdev --setra %s %s" % (racount, devname)
            r = os.system(cmd)
            tc.assertEqual(r, 0)


        @staticmethod
        def checkdev(devname, tc):
            devsz = Common_Utils.get_devsz(devname)
            tc.assertNotEqual(devsz, 0)


        @staticmethod
        def do_mkfs(devname, bsize, tc, formats = "ntfs"):
            if bsize == "default":
                cmd = [
                    "mkfs.ext4", 
                    "-F",
                    devname
                    ]
            else:
                cmd = ["mkfs.ext4", "-F" ,"-b", "%s" % bsize, devname]
            logger.debug( cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr = subprocess.PIPE)
            output = r.communicate()[0]
            logger.debug(output)
            tc.assertEqual(r.returncode, 0)


        @staticmethod
        def do_df(devname, tc):
            cmd = ["df", "-k", devname]
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            tc.assertEqual(r.returncode, 0)
            logger.debug(output)


        @staticmethod
        def do_fsckformount(devname, tc):
            r = os.system("fsck -n %s > /dev/null 2>&1" % devname)
            tc.assertEqual(r, 0)
            return r


        @staticmethod
        def do_mount(devname, dirname, tc):
            output = do_fsckformount(devname, tc)
            if output != 0:
                logger.info('filesystem %s corrupted. sleeping.' % devname)
                time.sleep(100000)
            cmd = "mount %s %s" % (devname, dirname) 
            r = os.system(cmd)
            tc.assertEqual(r, 0)


        @staticmethod
        def do_unmount(dirname, tc):
            cmd = "umount %s" % dirname
            logger.debug( cmd)
            r = os.system(cmd)
            tc.assertEqual(r, 0)


        @staticmethod
        def is_mounted(dirname):
            return os.path.ismount(dirname)


        @staticmethod
        def do_fsck(devname, tc):
            cmd = "fsck -nf %s > /dev/null 2>&1" % devname 
            logger.debug( cmd)
            r = os.system(cmd)
            tc.assertEqual(r, 0)


        @staticmethod
        def del_loopdev(devname, tc):
            cmd = "losetup -d %s" % devname
            r = os.system(cmd)
            tc.assertEqual(r, 0)


        @staticmethod
        def del_tmpfile(tmpfilename, tc):
            cmd = "/bin/rm -f %s" % tmpfilename
            logger.debug( cmd)
            r = os.system(cmd)
            tc.assertEqual(r, 0)


        @staticmethod
        def drop_caches(tc):
            cmd = "sync && echo 3 > /proc/sys/vm/drop_caches"
            r = os.system(cmd)


        @staticmethod
        def create_symbolic_link(src, dest):
            cmd = "ln -s %s %s > /dev/null 2>&1" % (src, dest)
            logger.debug( cmd)
            r = os.system(cmd)
            return r


        @staticmethod
        def remove_symbolic_link(path):
            cmd = "unlink %s > /dev/null 2>&1" % path
            logger.debug( cmd)
            r = os.system(cmd)
            return r


        @staticmethod
        def disable_varand(tc):
            cmd = "echo 0 > /proc/sys/kernel/randomize_va_space"
            logger.debug(cmd)
            r = os.system(cmd)
            tc.assertEqual(r, 0)


        @staticmethod
        def get_basenameofdevice(devname):
            cmd = "basename %s" % devname
            r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            output = r.communicate()[0].rstrip('\n')
            return output


        @staticmethod
        def do_filebench(cfgfile, ff):
            cmd = [
                "filebench",
                "-f",
                cfgfile
                ]

            cmd1 = [
                    "tee",
                    ff
                   ]

            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            r1 = subprocess.Popen(cmd1, stdin=r.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r1.communicate()

            return (r1.returncode, output, error)


        @staticmethod
        def lmdd_checkpattern(pv, bsize, count, skip):
            if count == 0:
                cmd = ["lmdd",
                       "if=%s" % pv,
                       "ipat=1",
                       "bs=%s" % bsize,
                       "mismatch=1",
                       "sync=1"
                     ]
            else:
                cmd = ["lmdd",
                       "if=%s" % pv,
                       "ipat=1",
                       "bs=%s" % bsize,
                       "count=%s" % count,
                       "mismatch=1",
                       "sync=1",
                       "skip=%s" % skip,
                       ]
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()

            if error is not None and 'want=' in error:
                return 1

            return 0


        @staticmethod
        def lmddwrite(pv, bsize, count, skip):
            r = dolmdd(of = pv, bs = bsize, count = count, opat = 1, skip = skip, sync = 1)
            return r


        @staticmethod
        def lmddwritezero(pv, bsize, count, skip):
            r = dolmdd(inf = "/dev/zero", of = pv, bs = bsize, count = count, skip = skip, sync = 1)
            return r


        @staticmethod
        def lmddcheckzero(pv, bsize, count, skip):
            _, tmp_file1 = tempfile.mkstemp ()
            _, tmp_file2 = tempfile.mkstemp ()
            dolmdd(inf = pv, of = tmp_file1, bs = bsize, count = count, skip = 1, sync = 1)

            dolmdd(inf = "/dev/zero", of = tmp_file2, bs = bsize, count = count, skip = 1, sync = 1)

            cmd = ["diff",
                   "-q",
                   tmp_file1, 
                   tmp_file2
                   ]
            logger.debug( cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()

            os.remove(tmp_file1)
            os.remove(tmp_file2)
            return r.returncode


        @staticmethod
        def lmddwritezerotofile(filename, bsize, count, skip):
            r = dolmdd(inf = "/dev/zero", of = filename, bs = bsize, count = count, skip = skip, sync = 1)
            return r


        @staticmethod
        def lmddreadfromfile(filename, bsize, count, skip):
            r = dolmdd(inf = filename, of = "/dev/null", bs = bsize, count = count, skip = skip, sync = 1)
            return r


        @staticmethod
        def lmddreadfromdev(devname, bsize, count, skip):
            r = dolmdd(inf = devname, of = "/dev/null", bs = bsize, count = count, skip = skip, sync = 1)
            return r


        @staticmethod
        def ddcheckfile(pv, bsize, count, skip, filename):
            tmp_file1 = "%sssd_test" % tmpdir
            dodd(inf = pv, of = tmp_file1, bs = bsize, count = count, skip = skip)
            cmd = ["diff",
                   "-q",
                   tmp_file1, 
                   filename
                   ]
            logger.debug( cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()

            os.remove(tmp_file1)
            return r.returncode


        @staticmethod
        def set_devblksz(devname, bsz, tc):
            cmd = "blockdev --setbsz %s %s" % (bsz, devname) 
            r = os.system(cmd)
            tc.assertEqual(r, 0)


        @staticmethod
        def mount_unmount(*args, **kwargs):
            pv = kwargs.get('pv')
            tc = kwargs.get('tc')

            cmd = "tune2fs -c 128 %s > /dev/null 2>&1" % pv
            r = os.system(cmd)
            tc.assertEqual(r, 0)

            for i in xrange(1, 10):
                cmd = "mount %s %stest" % (pv, mountdir)
                r = os.system(cmd)
                tc.assertEqual(r, 0)

                cmd = "sleep 10"
                r = os.system(cmd)

                cmd = "umount %stest" % (mountdir)
                r = os.system(cmd)
                tc.assertEqual(r, 0)
                drop_caches(tc)


        @staticmethod
        def get_devicename(device, tc):
            try:
                ss = os.readlink(device)
                return ss.split('/')[-1]
            except:
                device_detail = device.split('/')[-1]
                return device_detail



        @staticmethod
        def checkcorrectness(pvol, bs, tc):

            if bs != 512:
                do_mkfs(pvol, bs, tc)
            else:
                do_mkfs(pvol, "default", tc)

            do_mkdir("%stest/" % mountdir, tc)
            do_mount(pvol, "%stest/" % mountdir, tc)

            devsz = get_devsz(pvol)
            count = ((int(devsz)*512)/bs)/10
            for i in range(1, 6):
                ofile = "%stest/file%d" % (mountdir, i)
                r = dolmdd(of = ofile, bs = bs, count = count, opat = 1)
                tc.assertEqual(r, 0)

            do_unmount("%stest/" % mountdir, tc)
            do_mount(pvol, "%stest/" % mountdir, tc)

            for i in range(1, 6):
                dev = "%stest/trial/file%d" % (mountdir, i)
                r = lmdd_checkpattern(dev, bs, count, 0)
                tc.assertEqual(r, 0)

            do_unmount("%stest/" % mountdir, tc)


        @staticmethod
        def reclaim_loop(*args, **kwargs):
            pv = kwargs.get('pv')
            rmax = kwargs.get('rmax')
            rthreshold = kwargs.get('rthreshold')
            logger.debug('starting reclaim in a loop %s' % (pv))
            tc = kwargs.get('tc')
            for i in xrange(1, 6):
                reclaimioctl(pv, rmax, rthreshold)
                time.sleep(1)


        @staticmethod
        def read_loop(*args, **kwargs):
            pv = kwargs.get('pv')
            sv = kwargs.get('sv')
            tc = kwargs.get('tc')
            devsz = get_devsz(tc.ssd_volume)
            tc.count = devsz >> 4
            r = dolmdd(of = pv, bs = 4096, count = tc.count, opat = 1)
            tc.assertEqual(r, 0)

            logger.debug('starting IO in a loop %s: %s' % (pv, sv))
            for i in xrange(1, 6):
                r = lmdd_checkpattern(pv, 4096, tc.count, 0)
                tc.assertEqual(r, 0) 
                drop_caches(tc)


        @staticmethod
        def reclaim_with_read_loop(devtype, tc):
            devsz = get_devsz(tc.ssd_volume)
            tc.count = devsz >> 4
            tc.rmax = ((int(devsz) *512)/2) / (1024 *1024)
            tc.rthreshold = ((int(devsz) *512)/3 ) /(1024 *1024)
            r = dolmdd(of = tc.primary_volume, bs = "4096", count = tc.count, opat = 1)
            tc.assertEqual(r, 0)
            if devtype == "new":
                accelerate_dev(tc.primary_volume, tc.ssd_volume, 4096, tc)
            else:
                accelerate_existingdev(tc.primary_volume, tc.ssd_volume, tc)

            accelerate_allregions(tc.primary_volume, tc)

            threadA = threading.Thread(target = reclaim_loop, 
                       kwargs = {
                       'tc':tc, 'pv':tc.primary_volume, 'rmax':tc.rmax, 'rthreshold':tc.rthreshold
                })
            threadB = threading.Thread(target = read_loop, 
                       kwargs = {
                       'tc':tc, 'pv':tc.primary_volume, 'sv':tc.ssd_volume, 'count':tc.count})
            threadA.start()
            threadB.start()

            threadA.join()
            threadB.join()

            stats = getxstats(tc.primary_volume)
            logger.debug(stats)
            tc.assertNotEqual(int(stats['cs_readcache_flow']), 0)
            deaccelerate_dev(tc.primary_volume, tc)


        @staticmethod
        def do_mkdir(dirname, tc):
            cmd = "mkdir -p %s" % dirname 
            logger.debug( cmd)
            r = os.system(cmd)
            tc.assertEqual(r, 0)


elif OS == 'Windows':
    class Common_Utils(Common_Utils_Cross):
        @staticmethod
        def create_devices(ssdsz, pvolsz, bs, oddsize, tc):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                            stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('create vdisk file=c:\loop0.vhd maximum=%s type=fixed\n' % ssdsz)
            process_1.stdin.flush()
            process_1.stdin.write('create vdisk file=c:\loop1.vhd maximum=%s type=fixed\n' % pvolsz)
            process_1.stdin.flush()
            process_1.stdin.write('select vdisk file=c:\loop0.vhd\n')
            process_1.stdin.flush()
            process_1.stdin.write('attach vdisk\n')
            process_1.stdin.flush()
            process_1.stdin.write('convert mbr\n')
            process_1.stdin.flush()
            process_1.stdin.write('create partition primary\n')
            process_1.stdin.flush()
            process_1.stdin.write('FORMAT fs=ntfs label="SSD" quick\n')
            process_1.stdin.flush()
            process_1.stdin.write('assign letter="X"\n')
            process_1.stdin.flush()
            process_1.stdin.write('select vdisk file=c:\loop1.vhd\n')
            process_1.stdin.flush()
            process_1.stdin.write('attach vdisk\n')
            process_1.stdin.flush()
            process_1.stdin.write('convert mbr\n')
            process_1.stdin.flush()
            process_1.stdin.write('create partition primary\n')
            process_1.stdin.flush()
            process_1.stdin.write('FORMAT fs=ntfs label="HDD" quick\n')
            process_1.stdin.flush()
            process_1.stdin.write('assign letter="Y"\n')
            process_1.stdin.flush()
            out, err = process_1.communicate()
            logger.debug(out, err)
            tc.assertEqual(process_1.returncode, 0)
            tc.ssd_volume = "X"
            tc.primary_volume = "Y"


        @staticmethod
        def delete_partition(primary_volume, tc):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                             stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('list disk\n')
            process_1.stdin.flush()
            process_1.stdin.write('select volume %s\n' % primary_volume)
            process_1.stdin.flush()
            process_1.stdin.write('delete partition\n')
            process_1.stdin.flush()
            process_1.stdin.write('create partition primary\n')
            process_1.stdin.flush()
            process_1.stdin.write('FORMAT fs=ntfs quick\n')
            process_1.stdin.flush()
            process_1.stdin.write('assign letter=%s\n' % primary_volume)
            process_1.stdin.flush()
            out, err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)


        @staticmethod
        def create_partition(primary_volume, tc, formats = "ntfs", size = 1):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                            stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('list disk\n')
            process_1.stdin.flush()
            process_1.stdin.write('select volume %s\n' % primary_volume)
            process_1.stdin.flush()
            process_1.stdin.write('delete volume\n')
            process_1.stdin.flush()
            process_1.stdin.write('create partition primary size = %s noerr \n' % size)
            process_1.stdin.flush()
            process_1.stdin.write('FORMAT fs=%s quick\n' % formats)
            process_1.stdin.flush()
            process_1.stdin.write('assign letter=%s\n' % primary_volume)
            process_1.stdin.flush()
            out, err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)


        #This method is used to create a dynamic volume in Windows(like LVM in Windows)
        @staticmethod
        def create_logical_device(volume_name, size, tc):
            size = str(int(size) * 1024)
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                            stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('select volume=%s\n' % volume_name)
            process_1.stdin.flush()
            process_1.stdin.write('delete volume\n')
            process_1.stdin.flush()
            process_1.stdin.write('convert dynamic noerr\n')
            process_1.stdin.flush()
            process_1.stdin.write('create volume simple size=%s noerr\n' % size)
            process_1.stdin.flush()
            process_1.stdin.write('format fs=ntfs quick\n')
            process_1.stdin.flush()
            process_1.stdin.write('assign letter=%s\n' %  volume_name)
            process_1.stdin.flush()
            out, err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)


        @staticmethod
        def create_lvmdevice(volume_name ,logicalvol_name, size, device, tc):
            create_logical_device(device, size, tc)


        #This method is used to delete the dynamic volume in Windows
        @staticmethod
        def delete_logical_device(volume_name, tc):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                            stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('select volume=%s\n' % volume_name)
            process_1.stdin.flush()
            process_1.stdin.write('select volume=%s\n' % volume_name)
            process_1.stdin.flush()
            process_1.stdin.write('delete volume\n')
            process_1.stdin.flush()
            process_1.stdin.write('convert basic noerr\n')
            process_1.stdin.flush()
            process_1.stdin.write('create partition primary\n')
            process_1.stdin.flush()
            process_1.stdin.write('format fs=ntfs quick\n')
            process_1.stdin.flush()
            process_1.stdin.write('assign letter=%s\n' %  volume_name)
            process_1.stdin.flush()
            out,err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)


        @staticmethod
        def delete_lvmdevice(logicalvol_name, volume_name, primary_volume, tc):
            delete_logical_device(primary_volume, tc)


        #This method is used to create extend LVM in LINUX and Simple Volume in Windows
        @staticmethod
        def extend_lvmdevice(volume, tc, size = 1):
            size = str(int(size) * 1024)
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                           stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('select volume=%s\n' % volume)
            process_1.stdin.flush()
            process_1.stdin.write('extend size=%s noerr\n' % size)
            process_1.stdin.flush()
            process_1.stdin.write('assign letter=%s\n' %  volume)
            process_1.stdin.flush()
            out,err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)


        #size in MB
        @staticmethod
        def shrink_lvmdevice(volume, tc, size = 500):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                            stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('select volume=%s\n' % volume)
            process_1.stdin.flush()
            process_1.stdin.write('shrink desired=%s noerr\n' % size)
            process_1.stdin.flush()
            process_1.stdin.write('assign letter=%s\n' %  volume)
            process_1.stdin.flush()
            out,err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)


        @staticmethod
        def create_dmsetup(size, volname, tc):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                            stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('create vdisk file=c:\dmsetup.vhd maximum=%s type=fixed\n' % size)
            process_1.stdin.flush()
            process_1.stdin.write('select vdisk file=c:\dmsetup.vhd\n')
            process_1.stdin.flush()
            process_1.stdin.write('attach vdisk\n')
            process_1.stdin.flush()
            process_1.stdin.write('convert mbr\n')
            process_1.stdin.flush()
            process_1.stdin.write('create partition primary\n')
            process_1.stdin.flush()
            process_1.stdin.write('FORMAT fs=ntfs label="" quick\n')
            process_1.stdin.flush()
            process_1.stdin.write('assign letter="test"\n')
            process_1.stdin.flush()
            out, err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)


        @staticmethod
        def delete_dmsetup(tc):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                            stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('select vdisk file=c:\dmsetup.vhd\n')
            process_1.stdin.flush()
            process_1.stdin.write('detach vdisk\n')
            process_1.stdin.flush()
            process_1.stdin.write('select vdisk file=c:\dmsetup.vhd\n')
            process_1.stdin.flush()
            process_1.stdin.write('detach vdisk\n')
            process_1.stdin.flush()
            out, err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)
            os.system('rm -rf c:\dmsetup.vhd')


        @staticmethod
        def do_mkfs(devname, bsize, tc, formats = "ntfs"):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                            stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('list disk\n')
            process_1.stdin.flush()
            process_1.stdin.write('select volume %s\n' % devname)
            process_1.stdin.flush()
            process_1.stdin.write('FORMAT fs=%s quick\n' % formats)
            process_1.stdin.flush()
            process_1.stdin.write('assign letter=%s\n' % devname)
            process_1.stdin.flush()
            out, err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)


        @staticmethod
        def del_loopdev(devname, tc):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                            stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('select vdisk file=c:\loop0.vhd\n')
            process_1.stdin.flush()
            process_1.stdin.write('detach vdisk\n')
            process_1.stdin.flush()
            process_1.stdin.write('select vdisk file=c:\loop1.vhd\n')
            process_1.stdin.flush()
            process_1.stdin.write('detach vdisk\n')
            process_1.stdin.flush()
            out, err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)
            os.system('rm -rf c:\loop0.vhd')
            os.system('rm -rf c:\loop1.vhd')


        @staticmethod
        def create_symbolic_link(src, dest):
            cmd = "mklink /d %s %s > /dev/null 2>&1" % (dest, src)
            logger.debug( cmd)
            r = os.system(cmd)
            return r


        @staticmethod
        def do_mkdir(dirname, tc):
            cmd = "mkdir %s" % dirname 
            logger.debug( cmd)
            r = os.system(cmd)


        @staticmethod
        def remove_symbolic_link(path):
            cmd = "rmdir /s/q %s > /dev/null 2>&1" % path
            logger.debug( cmd)
            r = os.system(cmd)
            return r


        """
        This method is used to alter the partition table without reboot
        """
        @staticmethod
        def alter_table(primary_volume, tc):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                            stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('rescan\n')
            process_1.stdin.flush()
            out, err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))


        @staticmethod
        def do_mount(devname, dirname, tc):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('select volume=%s\n' % devname)
            process_1.stdin.flush()
            process_1.stdin.write('assign mount=%s\n' % dirname)
            process_1.stdin.flush()
            out,err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)


        @staticmethod
        def do_unmount(dirname, tc):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('select volume=%s\n' % devname)
            process_1.stdin.flush()
            process_1.stdin.write('remove mount=%s\n' % dirname)
            process_1.stdin.flush()
            out,err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)

			
		#RAID 0 is being created, where striping of volume is being done
        @staticmethod
        def create_raiddevice(device, device_2, tc):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                        stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('select volume=%s\n' % device)
            process_1.stdin.flush()
            process_1.stdin.write('delete volume\n')
            process_1.stdin.flush()
            process_1.stdin.write('convert dynamic noerr\n')
            process_1.stdin.flush()
            process_1.stdin.write('select volume=%s\n' % device_2)
            process_1.stdin.flush()
            process_1.stdin.write('delete volume\n')
            process_1.stdin.flush()
            process_1.stdin.write('convert dynamic noerr\n')
            process_1.stdin.flush()
            process_1.stdin.write('create volume stripe disk=1,2\n')
            process_1.stdin.flush()
            process_1.stdin.write('format fs=ntfs quick\n')
            process_1.stdin.flush()
            process_1.stdin.write('assign letter=R\n')
            process_1.stdin.flush()
            out,err = process_1.communicate()
            logger.debug("%s, %s "% (out, err))
            tc.assertEqual(process_1.returncode, 0)
			

        @staticmethod
        def delete_raiddevice(device, device_2, tc):
            process_1 = subprocess.Popen("diskpart", stderr = subprocess.PIPE, \
                stdout = subprocess.PIPE, stdin = subprocess.PIPE)
            process_1.stdin.write('select volume=R\n')
            process_1.stdin.flush()
            process_1.stdin.write('delete volume\n')
            process_1.stdin.flush()
            process_1.stdin.write('select disk=1\n')
            process_1.stdin.flush()
            process_1.stdin.write('convert basic noerr\n')
            process_1.stdin.flush()
            process_1.stdin.write('create partition primary\n')
            process_1.stdin.flush()
            process_1.stdin.write('format fs=ntfs quick\n')
            process_1.stdin.flush()
            process_1.stdin.write('assign letter=%s\n' % device)
            process_1.stdin.flush()
            process_1.stdin.write('select disk=2\n')
            process_1.stdin.flush()
            process_1.stdin.write('convert basic noerr\n')
            process_1.stdin.flush()
            process_1.stdin.write('create partition primary\n')
            process_1.stdin.flush()
            process_1.stdin.write('format fs=ntfs quick\n')
            process_1.stdin.flush()
            process_1.stdin.write('assign letter=%s\n' % device_2)
            process_1.stdin.flush()
            out,err = process_1.communicate()
            tc.assertEqual(process_1.returncode, 0)
			

        @staticmethod
        def mount_unmount(*args, **kwargs):
            pv = kwargs.get('pv')
            tc = kwargs.get('tc')

            for i in xrange(1, 10):
                do_mount(pv, mountdir, tc)
                time.sleep(10)
                do_unmount(mountdir, tc)   
                drop_caches(tc)


        @staticmethod
        def del_tmpfile(tmpfilename, tc):
            cmd = "del /q/s %s" % tmpfilename
            logger.debug( cmd)
            r = os.system(cmd)
            tc.assertEqual(r, 0)

			
        #SetSystemFileCacheSize.exe is an external executable file which  \
        #is used to Set/Unset/Flush File Cache.
        @staticmethod
        def drop_caches(tc):
            cmd = ("SetSystemFileCacheSize.exe flush")
            os.system(cmd)
		
			
        #The following listed methods need to be rewritten for CA Windows.
        @staticmethod
        def checkcorrectness(pvol, bs, tc):
            return


        @staticmethod
        def checkdev(devname, tc):
            return


        @staticmethod
        def ddcheckfile(pv, bsize, count, skip, filename):
            return

			
        @staticmethod
        def do_fsckformount(devname, tc):
            return


        @staticmethod
        def do_fsck(devname, tc):
            return
   

        @staticmethod
        def get_devsz(devname):
            return


        @staticmethod
        def get_devra(devname):
            return


        @staticmethod
        def get_devblksz(devname):
            return


        @staticmethod
        def get_basenameofdevice(devname):
            return


        @staticmethod
        def get_devicename(device, tc):
            return


        @staticmethod
        def is_mounted(dirname):
            return


        @staticmethod
        def lmdd_checkpattern(pv, bsize, count, skip):
            return


        @staticmethod
        def lmddwrite(pv, bsize, count, skip):
            return


        @staticmethod
        def lmddwritezero(pv, bsize, count, skip):
            return


        @staticmethod
        def lmddcheckzero(pv, bsize, count, skip):
            return


        @staticmethod
        def lmddwritezerotofile(filename, bsize, count, skip):
            return


        @staticmethod
        def lmddreadfromfile(filename, bsize, count, skip):
            return


        @staticmethod
        def lmddreadfromdev(devname, bsize, count, skip):
            return


        @staticmethod
        def read_loop(*args, **kwargs):
            return


        @staticmethod
        def reclaim_with_read_loop(devtype, tc):
            return


        @staticmethod
        def reclaim_loop(*args, **kwargs):
            return


        @staticmethod
        def set_devblksz(devname, bsz, tc):
            return


        @staticmethod
        def set_devra(devname, racount, tc):
            return



def do_dc():
    return subprocess.Popen("while :; do echo 3 > /proc/sys/vm/drop_caches; sleep 2; done", shell = True)


accelerate_allregions = Common_Utils.accelerate_allregions
accelerate_dev = Common_Utils.accelerate_dev
accelerate_existingdev = Common_Utils.accelerate_existingdev
accelerate_slowdown = Common_Utils.accelerate_slowdown
acceleratedev = Common_Utils.accelerate_dev
acceleratedir = Common_Utils.acceleratedir
accelerateregion = Common_Utils.accelerateregion
alter_table = Common_Utils.alter_table
cb_set_tunable = Common_Utils.cb_set_tunable
cb_get_tunable = Common_Utils.cb_get_tunable
change_write_policy = Common_Utils.change_write_policy
checkcorrectness = Common_Utils.checkcorrectness
checkdev = Common_Utils.checkdev
create_devices = Common_Utils.create_devices
create_dmsetup = Common_Utils.create_dmsetup
create_lvmdevice = Common_Utils.create_lvmdevice
create_logical_device = Common_Utils.create_logical_device
create_partition = Common_Utils.create_partition
create_raiddevice = Common_Utils.create_raiddevice
create_symbolic_link = Common_Utils.create_symbolic_link
ddcheckfile = Common_Utils.ddcheckfile
deaccelerate_dev = Common_Utils.deaccelerate_dev
del_loopdev = Common_Utils.del_loopdev
del_tmpfile = Common_Utils.del_tmpfile
delete_dmsetup = Common_Utils.delete_dmsetup
delete_logical_device = Common_Utils.delete_logical_device
delete_lvmdevice = Common_Utils.delete_lvmdevice
delete_partition = Common_Utils.delete_partition
delete_raiddevice = Common_Utils.delete_raiddevice
dodd = Common_Utils.dodd
do_fsckformount = Common_Utils.do_fsckformount
do_fsck = Common_Utils.do_fsck
do_mkdir = Common_Utils.do_mkdir
do_mkfs = Common_Utils.do_mkfs
do_mount = Common_Utils.do_mount
do_unmount = Common_Utils.do_unmount
drop_caches = Common_Utils.drop_caches
extend_lvmdevice = Common_Utils.extend_lvmdevice
flushadmitmap = Common_Utils.flushadmitmap
flush_forward_maps = Common_Utils.flush_forward_maps
format_dev = Common_Utils.format_dev
get_devblksz = Common_Utils.get_devblksz
get_devra = Common_Utils.get_devra
get_devsz = Common_Utils.get_devsz
get_devicename = Common_Utils.get_devicename
getadmissionbitmap = Common_Utils.getadmissionbitmap
getattrs = Common_Utils.getattrs
getcoverage = Common_Utils.getcoverage
getsb = Common_Utils.getsb
getxstats = Common_Utils.getxstats
get_basenameofdevice = Common_Utils.get_basenameofdevice
is_mounted = Common_Utils.is_mounted
isdev_accelerated = Common_Utils.isdev_accelerated
list_accelerated_device = Common_Utils.list_accelerated_device
dolmdd = Common_Utils.dolmdd
lmdd_checkpattern = Common_Utils.lmdd_checkpattern
lmddcheckzero = Common_Utils.lmddcheckzero
lmddreadfromdev = Common_Utils.lmddreadfromdev
lmddreadfromfile = Common_Utils.lmddreadfromfile
lmddwrite = Common_Utils.lmddwrite
lmddwritezero = Common_Utils.lmddwritezero
lmddwritezerotofile = Common_Utils.lmddwritezerotofile
mount_unmount = Common_Utils.mount_unmount
read_loop = Common_Utils.read_loop
reclaim_loop = Common_Utils.reclaim_loop
reclaim_with_read_loop = Common_Utils.reclaim_with_read_loop
reclaimioctl = Common_Utils.reclaimioctl
remove_symbolic_link = Common_Utils.remove_symbolic_link
resetcoverage = Common_Utils.resetcoverage
set_devblksz = Common_Utils.set_devblksz
set_devra = Common_Utils.set_devra
setpolicy_dev = Common_Utils.setpolicy_dev
shrink_lvmdevice = Common_Utils.shrink_lvmdevice


def caller():
    return '%s.%s' % (inspect.stack()[3][3], inspect.stack()[2][3])

class CBQAMixin(object):
    def assertEqual(self, a, b, x = None):
        if x is None:
            do_pass(self, '%s %s %s' % (caller(), a, b), a == b)
        else:
            do_pass(self, x, a == b)

    def assertNotEqual(self, a, b, x = None):
        do_pass(self, '%s %s %s' % (caller(), a, b), a != b)

    def assertTrue(self, a, x = None):
        do_pass(self, '%s %s' % (caller(), a), a == True)

    def assertFalse(self, a, x = None):
        do_pass(self, '%s %s' % (caller(), a), a == False)

    def skipTest2(self, s, x = None):
        do_skip(self, s)

    def accelerate(self, bsize = 4096, write_policy = DEFAULT_WRITE_POLICY, mode = DEFAULT_MODE):
        return accelerate_dev(self.primary_volume,
                           self.ssd_volume, bsize,
                           tc=self, 
                           debug = True,
                           write_policy = write_policy,
                           mode = mode)

    def deaccelerate(self, debug=False):
        deaccelerate_dev(self.primary_volume, tc=self, debug=debug)

    def setpolicy(self, spol = 'fulldisk', pval = None):
        setpolicy_dev(spol, self.primary_volume, pval, self)

    def getxstats(self):
        return getxstats(self.primary_volume)

    def reclaim(self):
        os.system("cachebox -R 1 -d %s" % (self.primary_volume))

    def copyback(self):
        os.system("./cbcopyback -d %s" % (self.primary_volume))

    def seq_write(self, bsize=4096, count=8, thread=False):
        primary_volume = self.primary_volume
        def _f(*args, **kwargs):
            dodd(inf = "/dev/zero", of = primary_volume, bs = bsize, count = count)

        t = threading.Thread(target = _f, kwargs = {})
        t.start()
        if not thread:
            t.join()
        return t

    def seq_read(self, bsize=4096, count=8, thread=False):
        primary_volume = self.primary_volume
        def _f(*args, **kwargs):
            dodd(inf = primary_volume, of = "/dev/null", bs = bsize, count = count)

        t = threading.Thread(target = _f, kwargs = {})
        t.start()
        if not thread:
            t.join()
        return t

    def filldisk(self):
        dodd(inf = "/dev/zero", of = self.primary_volume, bs = "1M")

    def flush(self):
        os.system('sync; sync; sync;')
        drop_caches(self)

    def log_replay(self, ssd):
        cmd = ["cbck",
               "-s",
               "%s" % ssd,
               "-c",
               "/etc/cachebox/cachebox_txt.conf",
               "-t"
               ]
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        return (r.returncode, output, error)

    def where_delay(self, where):
        cb_set_tunable("where_delay", where)


