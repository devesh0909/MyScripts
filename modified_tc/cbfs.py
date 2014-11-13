#!/usr/bin/env python

import datetime
import os
import sys
import threading
import unittest

from common_utils import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
	if not member_name.startswith("__"):
		globals()[member_name] = getattr(config, member_name)

accelerate_dev = Common_Utils.accelerate_dev
deaccelerate_dev = Common_Utils.deaccelerate_dev
accelerate_allregions = Common_Utils.accelerate_allregions
acceleratedir = Common_Utils.acceleratedir
get_devblksz = Common_Utils.get_devblksz
do_mkfs = Common_Utils.do_mkfs
do_mkdir = Common_Utils.do_mkdir
do_mount = Common_Utils.do_mount
do_unmount = Common_Utils.do_unmount
do_fsck = Common_Utils.do_fsck
do_filebench = Common_Utils.do_filebench
drop_caches = Common_Utils.drop_caches
do_df = Common_Utils.do_df
disable_varand = Common_Utils.disable_varand
getxstats = Common_Utils.getxstats

def getmaxcachesize():

    # 
    # returns the total memory available for the filesystem
    # cache. maybe there is a better way to figure this out.
    # 

    os.system('echo 3 > /proc/sys/vm/drop_caches')
    r = subprocess.Popen("grep MemFree /proc/meminfo", shell=True, stdout=subprocess.PIPE)
    output = r.communicate()[0]

    i, m, s = output.split()
    assert s == 'kB'
    return int(m) * 1 << 10


def getfilesets(fscachesize):

    # given the filesystem cachesize (or in other words amount of DRAM
    # available for FS cache), we return two filesets (sizes). fset1
    # which fits in within the FS cache and fset2 which exceeds the
    # cache capacity

    # this is the meanfilesize in filebench
    # for webserver configuration

    meanfilesize = 16 * 1 << 10

    fset1 = (fscachesize >> 1)/meanfilesize
    fset2 = (fscachesize << 1)/meanfilesize

    return (fset1, fset2)


# the size of the fileset influences cacheflows.

NFILES = (getfilesets(getmaxcachesize())[1], )
RUNS = (86400, )

def fb_hdd(*args, **kwargs):
    tc = kwargs.get('tc')
    cfg = kwargs.get('cfg')

    rcode, output, error = do_filebench(cfg)
    do_df(tc.primary_volume, tc)


def fb_accelerate(*args, **kwargs):
    tc = kwargs.get('tc')
    cfg = kwargs.get('cfg')
    cmd = "cb --accelerate --device=%s --ssd=%s" % (tc.primary_volume, tc.ssd_volume)
    logger.debug(cmd)
    r = os.system(cmd)
    tc.assertEqual(r, 0)
    if r != 0:
        sys.exit(1)

    logger.debug('starting filebench with cachebox acceleration on full device')
    acceleratedir(tc, tc.primary_volume, "%stest/bigfileset/" % mountdir)
    rcode, output, error = do_filebench(cfg)
    stats = getxstats(tc.primary_volume)
    do_df(tc.primary_volume, tc)
    stats = getxstats(tc.primary_volume)
    do_df(tc.primary_volume, tc)
    cmd = "cb --letgo --device=%s" % (tc.primary_volume)
    logger.debug(cmd)
    r = os.system(cmd)
    tc.assertEqual(r, 0)
    if r != 0:
        sys.exit(1)

def do_dc():
    return subprocess.Popen("while :; do echo 3 > /proc/sys/vm/drop_caches; sleep 1; done", shell = True)

def do_dstat(f, tc):
    dstat_cmd = ["dstat", "-t", "-f", "-C", "total", "-cmdngy", "--fs", "-r", "--disk-tps", "--disk-util", "-s", "--vm", "--dstat-mem",
                  "--nocolor", "--noheaders", "--memcache-hits", "--dstat-cpu", "--top-bio", "--top-bio-adv", "--top-cpu", "--top-cputime",
                  "--top-mem", "--output", "%s.csv" %f, "5"]

    return subprocess.Popen(dstat_cmd)

class WebserverWorkload(unittest.TestCase):
    """
    Run a webserver workload profile
    """

    def setUp(self):
        super(WebserverWorkload, self).setUp()

        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.devbsz = get_devblksz(self.primary_volume)
        disable_varand(self)

    def tearDown(self):
        super(WebserverWorkload, self).tearDown()
        
    def test_1(self):

        pwd = os.getcwd() + "/statistics"
        do_mkdir(pwd, tc=self)

        compmatrix = (('cachebox', fb_accelerate), )
        filebench_stats = "stats snap\nsleep 5\n"

        for nfiles in NFILES:
            do_mkfs(self.primary_volume, "default", tc=self)
            do_mkdir("%stest" % mountdir, tc=self)

            # issue the first filebench run to prepopulate the
            # files.

            template = open('webserver.f').read()
            cfg = open('webserver.tmp', 'w')
            cfg.write(template % (nfiles, filebench_stats * (10 / 5)))
            cfg.close()

            do_mount(self.primary_volume, "%stest/" % mountdir, tc=self)
            logger.debug('filebench webserver bigfileset begin prepopulate with nfiles(%d), run(%d).' % (nfiles, 10))
            p = threading.Thread(target=fb_hdd, kwargs = {'tc':self, 'cfg':'webserver.tmp'})
            p.start()
            p.join()
            logger.debug('filebench webserver bigfileset prepopulated with nfiles(%d), run(%d).' % (nfiles, 10))

            for run in RUNS:
                template = open('webserver.f').read()
                cfg = open('webserver.tmp', 'w')
                cfg.write(template % (nfiles, filebench_stats * (run / 5)))
                cfg.close()
                for comp, target in compmatrix:
                    dc = do_dc()
                    date_time = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M')
                    dstat = do_dstat(pwd+'/%s_%s_%s_%s_%s' % ('dstat', comp, nfiles, run, date_time), self)
                    p = threading.Thread(target=target, kwargs = {'tc':self, 'cfg':'webserver.tmp'})
                    p.start()
                    p.join()
                    dstat.terminate()
                    dc.terminate()
                    do_unmount("%stest" % mountdir, self)

if __name__ == '__main__':
	unittest.main(argv=["cbfs.py"] + args)
