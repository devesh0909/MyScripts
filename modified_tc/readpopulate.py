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
import os
import random
import subprocess
import sys
import threading
import time
import unittest

from common_utils import *
from cblog import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

class TestReadFlow(CBQAMixin, unittest.TestCase):

    """
    Test various cache flows
    """

    def setUp(self):

        super(TestReadFlow, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.pv_ra = get_devra(self.primary_volume)
        self.sv_ra = get_devra(self.ssd_volume)
        set_devra(self.primary_volume, 0, tc=self)
        set_devra(self.ssd_volume, 0, tc=self)

        cmd = "blockdev --getbsz %s" % self.primary_volume 
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = r.communicate()[0].rstrip('\n')
        self.primary_volume_bsize = int(output)


    def tearDown(self):
        super(TestReadFlow, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        set_devra(self.primary_volume, self.pv_ra, tc=self)
        set_devra(self.ssd_volume, self.sv_ra, tc=self)

    def test_1(self):
        for s in range(12, 17):
            bsize = 1 << s
            dev_blksz = get_devblksz(self.primary_volume)
            if bsize > dev_blksz:
                do_skip(self, 'test_readcache_readpopulate')
                continue

            accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, mode = "monitor")
            attrs = getattrs(self.primary_volume)
            numregions = int(attrs['numregions'])
            regionsize = int(attrs['regionsize'])
            testregions = range(0, numregions)
            random.shuffle(testregions)
            randomcnt = 3
            if randomcnt > numregions:
                randomcnt = numregions
            for rindex in range(randomcnt):
                region = testregions[rindex]
                skip = region * (regionsize/bsize)

                bmp = getadmissionbitmap(self.primary_volume)
                bmp.dump(region)
                count = regionsize / bsize
                partialio = bsize / self.primary_volume_bsize

                # pass 1: populate the cache.

                rc = lmddwrite(self.primary_volume, bsize, count, skip)
                self.assertEqual(rc, 0) 
                drop_caches(tc=self)
                rc = lmdd_checkpattern(self.primary_volume, bsize, count, skip)
                self.assertEqual(rc, 0) 
                stats = getxstats(self.primary_volume)

                # Note, we are doing an integer division here and
                # count will be 0 if the test block size is larger
                # than the device block size. in any case the os is
                # expected to split ios to primary_volume_bsize.

                # TBD : We are using full disk acceleration for now so
                # data will be cached in the first access itself
                # rather on second access (when it declared as hot)
                # This code below can change when we start using the
                # IO temp based acceleration policy (may have to use
                # cs_readpopulate_flow in below check)

                do_pass(self, 'test_1:1', 
                    (count > 0 and stats.get('cs_writethrough_flow') == count)
                    or not bmp.isAccelerated(region))

                # pass 2: setup the region for acceleration

                accelerateregion(self, self.primary_volume, region)
                bmp = getadmissionbitmap(self.primary_volume)
                bmp.dump(region)
                do_pass(self, 'test_1:2', bmp.isAccelerated(region))

                # pass 3: read from the device - trigger a read populate flow

                drop_caches(tc=self)
                rc = lmdd_checkpattern(self.primary_volume, bsize, count, skip)
                do_pass(self, 'test_1:3', rc == 0)
                stats = getxstats(self.primary_volume)

                # TBD: This code below can change when we start using
                # the IO temp based acceleration policy

                do_pass(self, 'test_1:4',
                (count > 0 and (stats.get('cs_readpopulate_flow') +
                        stats.get('cs_writethrough_flow')) >= count))

                # pass 4: read again - this time forcing readcache flow.

                drop_caches(tc=self)
                rc = lmdd_checkpattern(self.primary_volume, bsize, count, skip)
                do_pass(self, 'test_1:5', rc == 0)
                stats = getxstats(self.primary_volume)
                do_pass(self, 'test_1:6',
                    count > 0 and stats.get('cs_readcache_flow') >= count)

            deaccelerate_dev(self.primary_volume, tc=self)

if __name__ == '__main__':
    unittest.main(argv=["readpopulate.py"] + args)
