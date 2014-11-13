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

# the number of repeat trials for a given configuration

NUMITERS = xrange(0, 1)


# the duration of each run in seconds.

RUNS = (172800,)

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

NFILES = getfilesets(getmaxcachesize())
NFILES = (411863, )  # value tested for 1GB RAM

#
# global shared variable to hold the filebench results
#

def fb_hdd(*args, **kwargs):
    tc = kwargs.get('tc')
    cfg = kwargs.get('cfg')
    ff = kwargs.get('ff')

    rcode, output, error = do_filebench(cfg, ff)
    do_df(tc.primary_volume, tc)

def fb_ssd(*args, **kwargs):
    tc = kwargs.get('tc')
    cfg = kwargs.get('cfg')
    ff = kwargs.get('ff')

    do_mkfs(tc.ssd_volume, "default", tc=tc)
    do_mkdir("/mnt/test", tc=tc)
    do_mount(tc.ssd_volume, "/mnt/test/", tc=tc)
    rcode, output, error = do_filebench(cfg, ff)
    do_df(tc.ssd_volume, tc)
    do_unmount("/mnt/test", tc)


def fb_accelerate(*args, **kwargs):
    tc = kwargs.get('tc')
    cfg = kwargs.get('cfg')
    lf = kwargs.get('lf')
    ff = kwargs.get('ff')
    
    cmd = "cb --accelerate --device=%s --ssd=%s" % (tc.primary_volume, tc.ssd_volume)
    logger.debug(cmd)
    r = os.system(cmd)
    tc.assertEqual(r, 0)
    if r != 0:
        sys.exit(1)

    accelerate_allregions(tc.primary_volume, tc)
    logger.debug('starting filebench with cachebox acceleration on full device')
    rcode, output, error = do_filebench(cfg, ff)
    stats = getxstats(tc.primary_volume)
    do_df(tc.primary_volume, tc)
    do_cacheboxstats(tc.primary_volume, lf)
    cmd = "cb --letgo --device=%s" % (tc.primary_volume)
    logger.debug(cmd)
    r = os.system(cmd)
    tc.assertEqual(r, 0)
    if r != 0:
        sys.exit(1)

    hits = stats.get('cs_read_hits')
    miss = stats.get('cs_read_miss')
    perf = '%0.2f' % (hits * 100.0/(hits + miss + 1.0))
    reads = str(stats.get('cs_reads'))
    writes = str(stats.get('cs_writes'))
    rpopulates = str(stats.get('cs_readpopulate_flow'))
    wthroughflow = str(stats.get('cs_writethrough_flow'))
    partialio = str(stats.get('cs_partialio'))

def do_dstat(f, tc):
    #--memcache-hits
    dstat_cmd = ["dstat", "-t", "-f", "-C", "total", "-cmdngy", "--fs", "-r", "--disk-tps", "--disk-util", "-s", "--vm", "--dstat-mem",
                 "--nocolor", "--noheaders", "--memcache-hits", "--dstat-cpu", "--top-bio", "--top-bio-adv", "--top-cpu", "--top-cputime", 
                 "--top-mem", "--output", "%s.csv" %f, "5"]

    return subprocess.Popen(dstat_cmd)

def do_iostat(f, tc):
    return subprocess.Popen(["iostat", "-x", "5", tc.primary_volume, tc.ssd_volume], stdout = open(f, 'w'))

def do_vmstat(f):
    return subprocess.Popen(["vmstat", "5"], stdout = open(f, 'w'))

def do_dc():
    return subprocess.Popen("while :; do echo 3 > /proc/sys/vm/drop_caches; sleep 1; done", shell = True)

def do_cacheboxstats(d, f):
    os.system("cachebox -x -d %s > %s" % (d, f))

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

        compmatrix = (('ssd', fb_ssd), ('hdd', fb_hdd), ('cachebox', fb_accelerate), )
        compmatrix = (('hdd', fb_hdd), )

        filebench_stats = "stats snap\nsleep 5\n"

        for nfiles in NFILES:
            # do_mkfs(self.primary_volume, "default", tc=self)
            do_mkdir("/mnt/test", tc=self)

            # issue the first filebench run to prepopulate the
            # files.

            template = open('webserver.f').read()
            cfg = open('webserver.tmp', 'w')
            cfg.write(template % (nfiles, filebench_stats * (10 / 5)))
            cfg.close()

            logger.debug('filebench webserver bigfileset begin prepopulate with nfiles(%d), run(%d).' % (nfiles, 10))
            p = threading.Thread(target=fb_hdd, kwargs = {'tc':self, 'cfg':'webserver.tmp', 'ff':pwd+'/filebench_baseline'})
            p.start()
            p.join()
            logger.debug('filebench webserver bigfileset prepopulated with nfiles(%d), run(%d).' % (nfiles, 10))

            for run in RUNS:
                template = open('webserver.f').read()
                cfg = open('webserver.tmp', 'w')
                cfg.write(template % (nfiles, filebench_stats * (run / 5)))
                cfg.close()
                for i in NUMITERS:
                    for comp, target in compmatrix:
                        #do_mount(self.primary_volume, "/mnt/test/", tc=self)
                        drop_caches(self)
                        r0 = [datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S'), comp, str(nfiles), str(run), str(i)]
                        dstat = do_dstat(pwd+'/%s_%s_%s_%s_%s' % ('dstat', comp, nfiles, run, i), self)
                        lf = pwd+'/%s_%s_%s_%s_%s' % ('cachebox', comp, nfiles, run, i)
                        ff = pwd+'/%s_%s_%s_%s_%s' % ('filebench', comp, nfiles, run, i)
                        p = threading.Thread(target=target, kwargs = {'tc':self, 'cfg':'webserver.tmp', 'ff':ff, 'lf':lf})
                        p.start()
                        p.join()
                        dstat.terminate()
                        do_unmount("/mnt/test", self)


if __name__ == '__main__':
	unittest.main(argv=["filebench.py"] + args)
