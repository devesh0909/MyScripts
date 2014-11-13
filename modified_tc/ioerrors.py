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
import threading
import time
import unittest

from cblog import *
from common_utils import *
getxstats = Common_Utils.getxstats
accelerateregion = Common_Utils.accelerateregion

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

#
# test functionality in the face of IO errors
#

# see cbdebug.h for error codes to trigger

def trigger_ioerror(code):
    cb_set_tunable("ioerror_inject", code)

def unset_ioerror():
    cb_set_tunable("ioerror_inject", 0)

def doio(dev, count = 16, write = False):
    if not write:
        dodd(inf = dev, of = "/dev/null", bs = "4K", count = count)
    else:
        dodd(inf = "/dev/zero", of = dev, bs = "4k", count = count)

def do_partial_io(dev, rw = 0):
    cmd = (
           "./cbio",
           "-d",
           "%s" % dev,
           "-a",
           "%s" % rw,
           "-p",
           "cbbuf",
           "-s",
           "2",
           "-b",
           "1024"
          )
    r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = r.communicate()

def copyback_ioctl(primary_volume, cmax):
    cmd = "cachebox -d %s -k %s > /dev/null 2>&1" % (primary_volume, cmax)
    return os.system(cmd)

def copyback_change_mode(primary_volume):
    cmd = "cachebox -a 17 -d %s" % (primary_volume)
    return os.system(cmd)

class TestDataIOErrors(CBQAMixin, unittest.TestCase):

    #
    # Test cases involving data .i.e not cachebox metadata, includes
    # both hdd as well as ssd errors.
    #

    def setUp(self):
        super(TestDataIOErrors, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.accelerate()
        self.setpolicy()

    def tearDown(self):
        self.deaccelerate()
        super(TestDataIOErrors, self).tearDown()

    def test_hddreaderrors(self):
        trigger_ioerror(0x1)
        doio(self.primary_volume)
        self.assertTrue(True)
        self.assertTrue(True)
        return

    def test_hddwriteerrors(self):
        trigger_ioerror(0x2)
        doio(self.primary_volume, True)
        self.assertTrue(True)
        return

    def test_ssdreaderrors(self):
        doio(self.primary_volume)
        drop_caches(self)
        trigger_ioerror(0x400)
        doio(self.primary_volume)
        self.assertTrue(True)
        return

    def test_ssdwriterrors(self):
        trigger_ioerror(0x800)
        doio(self.primary_volume)
        self.assertTrue(True)
        return

    def test_ssdwriterrors2(self):
        # write cache->fail
        trigger_ioerror(0x800)
        doio(self.primary_volume, count = 1, write = True)
        self.flush()
        self.assertTrue(True)
        return

    def test_ssdreadafterwriterrors(self):
        # write cache->success. read cache->fail
        doio(self.primary_volume, write = True)
        self.flush()
        trigger_ioerror(0x400)
        doio(self.primary_volume)
        self.assertTrue(True)
        return



class MetaIOErrors(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(MetaIOErrors, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        trigger_ioerror(0)
        super(MetaIOErrors, self).tearDown()


    def test_superreaderrors(self):

        trigger_ioerror(0x4)
        r = accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, True)
        self.assertNotEqual(r, 0)
        return

    def test_superwriteerrors(self):

        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self)
        trigger_ioerror(0x8)
        deaccelerate_dev(self.primary_volume, self)
        self.assertTrue(True)
        return

    def test_admitreaderrors(self):

        trigger_ioerror(0x100)
        r = accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, True)
        self.assertNotEqual(r, 0)
        self.assertTrue(True)
        return

    def test_admitwriteerrors(self):

        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self)
        trigger_ioerror(0x200)
        accelerate_allregions(self.primary_volume, self)
        deaccelerate_dev(self.primary_volume, self)
        self.assertTrue(True)
        return


class FmapIOErrors(CBQAMixin, unittest.TestCase):

    #
    # Test cases involving data .i.e not cachebox metadata, includes
    # both hdd as well as ssd errors.
    #

    def setUp(self):
        super(FmapIOErrors, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self)
        accelerate_allregions(self.primary_volume, self)

    def tearDown(self):
        deaccelerate_dev(self.primary_volume, self)
        super(FmapIOErrors, self).tearDown()

    def test_fmapreaderrors(self):

        trigger_ioerror(0x10)
        doio(self.primary_volume)
        self.assertTrue(True)
        return


    def test_fmapwriteerrors(self):

        trigger_ioerror(0x20)
        doio(self.primary_volume)
        self.assertTrue(True)
        return

class IOFailures(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(IOFailures, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(IOFailures, self).tearDown()

    def test_metadataio_errors(self):
        #
        # Acceleration should fail after inducing following errors : 
        # Induce CB_ADMITMAPREAD_ERROR
        #
        trigger_ioerror(0x00000100)
        r = accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, True)
        self.assertNotEqual(r, 0) 
        unset_ioerror()

        # Induce CB_EMAPREAD_ERROR(0x00000040)
        trigger_ioerror(0x00000040)
        r = accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, True)
        self.assertNotEqual(r, 0) 
        unset_ioerror()

        # Induce CB_SUPERREAD_ERROR(0x00000004)
        trigger_ioerror(0x00000004)
        r = accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, True)
        self.assertNotEqual(r, 0) 
        unset_ioerror()

    def test_metadataio_errors2(self):
        #
        # Accelerate  
        # Induce CB_RCREAD_ERROR(0x00008000)
        #
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self)
        trigger_ioerror(0x00008000)

        thread_1 = threading.Thread(target = accelerateregion, args = (self, self.primary_volume, 0))
        thread_1.start()

        time.sleep(1)

        thread_2 = threading.Thread(target = unset_ioerror)
        thread_2.start()

        thread_1.join()
        thread_2.join()

        stats = getxstats(self.primary_volume)
        self.assertNotEqual(stats['cs_mdio_err'], 0)
        deaccelerate_dev(self.primary_volume, self)

    def test_dataio_wt_errors(self):
        #
        # Induce CB_CACHEWRITE_ERROR(0x00000800)
        # Accelerate in write-through mode
        # 
        trigger_ioerror(0x00000800)
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, False, "write-through")
        doio(self.primary_volume)
        self.flush()
        stats = getxstats(self.primary_volume)
        self.assertNotEqual(stats['cs_dataio_err'], 0)
        deaccelerate_dev(self.primary_volume, self)
        unset_ioerror()

    def test_dataio_wb_errors(self):
        #
        # Induce CB_HDDREAD_ERROR(0x00000001) 
        # Accelerate in write-back mode
        # Induce read disk flow
        #
        trigger_ioerror(0x00000001)
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, False)
        do_partial_io(self.primary_volume)
        self.flush()
        stats = getxstats(self.primary_volume)
        self.assertNotEqual(stats['cs_dataio_err'], 0)
        unset_ioerror()
        deaccelerate_dev(self.primary_volume, self)

        #
        # Induce CB_HDDWRITE_ERROR(0x00000002)
        # Accelerate in write-back mode
        # Induce write disk flow
        #
        trigger_ioerror(0x00000002)
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, False)
        do_partial_io(self.primary_volume, 1)
        self.flush()
        stats = getxstats(self.primary_volume)
        self.assertNotEqual(stats['cs_dataio_err'], 0)
        unset_ioerror()
        deaccelerate_dev(self.primary_volume, self)

        #
        # Accelerate in write-back mode
        # Induce CB_CACHEREAD_ERROR(0x00000400)
        # Induce read cache flow
        #
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, False)
        doio(self.primary_volume)
        self.flush()
        trigger_ioerror(0x00000400)
        doio(self.primary_volume)
        self.flush()
        stats = getxstats(self.primary_volume)
        self.assertNotEqual(stats['cs_dataio_err'], 0)
        self.assertNotEqual(stats['cs_readpopulate_flow'], 0)
        self.assertNotEqual(stats['cs_readcache_flow'], 0)
        deaccelerate_dev(self.primary_volume, self)
        unset_ioerror()

        #
        # Accelerate in write-back mode
        # Induce CB_CACHEWRITE_ERROR(0x00000800)
        # Induce read populate flow
        #
        trigger_ioerror(0x00000800)
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, False)
        doio(self.primary_volume)
        self.flush()
        stats = getxstats(self.primary_volume)
        self.assertNotEqual(stats['cs_dataio_err'], 0)
        self.assertNotEqual(stats['cs_readpopulate_flow'], 0)
        deaccelerate_dev(self.primary_volume, self)
        unset_ioerror()

    def test_copybackio_wb_errors(self):
        #
        # Accelerate in write-back mode
        # Induce CB_CACHEREAD_ERROR(0x00000400)
        # Induce copyback read phase flow
        #
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, False)
        doio(self.primary_volume, write=True)
        self.flush()
        doio(self.primary_volume, write=True)
        self.flush()
        trigger_ioerror(0x00000400)
        copyback_ioctl(self.primary_volume, 50)
        time.sleep(1)
        stats = getxstats(self.primary_volume)
        self.assertNotEqual(stats['cs_ssdread_error'], 0)
        self.assertEqual(stats['cs_copyback_flow'], 0)
        unset_ioerror()
        deaccelerate_dev(self.primary_volume, self)

    def test_copybackio_letgo_errors(self):
        #
        # Accelerate in write-back mode
        # Induce CB_CACHEREAD_ERROR(0x00000400)
        # Induce copyback read phase flow
        #
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self, False)
        doio(self.primary_volume, write=True)
        self.flush()
        doio(self.primary_volume, write=True)
        self.flush()
        copyback_ioctl(self.primary_volume, 50)
        time.sleep(1)
        stats = getxstats(self.primary_volume)
        self.assertEqual(stats['cs_ssdread_error'], 0)
        doio(self.primary_volume, write=True)
        self.flush()
        doio(self.primary_volume, write=True)
        self.flush()
        trigger_ioerror(0x00000400)
        r = copyback_change_mode(self.primary_volume)
        self.assertNotEqual(r, 0)
        unset_ioerror()
        deaccelerate_dev(self.primary_volume, self)

if __name__ == '__main__':
    unittest.main(argv=["ioerrors.py"] + args)
