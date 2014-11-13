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

BLK_SIZE = [4096, 2048, 1024, 512]
SECTORS = [1, 2, 3, 4]

class TestPartialIO(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestPartialIO, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.wfile = "%stest_wfile" % tmpdir
        self.rfile = "%stest_wfile" % tmpdir

    def tearDown(self):
        super(TestPartialIO, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_tmpfile(self.wfile, tc=self)
        del_tmpfile(self.rfile, tc=self)

    def get_buffer(self, size, sector):
        s = ('%0.16d%0.16d' % (size, sector)) * (size/32)
        buf = buffer(s, 0, size)
        return buf

    def write_on_disk(self, size, buf, sector = 0):
        d = open(self.wfile, "wb")
        d.write(buf)
        d.close()
        r = dodd(inf = self.wfile, of = self.primary_volume, bs = size, seek = sector, oflag = "direct")
        self.assertEqual(r, 0)

    def read_from_disk(self, size, sector = 0):
        r = dodd(inf = self.primary_volume, of = self.rfile, bs = size, count = 1, skip = sector, iflag = "direct")
        self.assertEqual(r, 0)
        d = open(self.rfile, "r")
        buf = d.read(size)
        d.close()
        return buf

    def test_writeback_partialio(self):
        accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self)
        do_dc()

        for i in xrange(10):
            time.sleep(2)
            random.shuffle(BLK_SIZE)
            random.shuffle(SECTORS)

            for size in BLK_SIZE:
                for sect in SECTORS:
                    wbuf = self.get_buffer(size, 0)
                    self.write_on_disk(size, wbuf, sect)
                    rbuf = self.read_from_disk(size, sect)
                    do_pass(self, 'test_writeback_partialio', str(wbuf) == rbuf)

        deaccelerate_dev(self.primary_volume, tc=self)



if __name__ == '__main__':
    unittest.main(argv=["partialio.py"] + args)
