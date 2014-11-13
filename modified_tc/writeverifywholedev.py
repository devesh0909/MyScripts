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


class WriteVerifyWholeDev(CBQAMixin, unittest.TestCase):

    """
    Test lmdd pattern write & verify on accelerated device with
    various blksz
    """

    def setUp(self):
        super(WriteVerifyWholeDev, self).setUp()
        create_devices(ssdsz=110, pvolsz=200, bs=4096, oddsize=0, tc=self)

    def tearDown(self):
        super(WriteVerifyWholeDev, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_1(self):
        for s in range(12,13):
            bsize = 1 << s
            self.accelerate(bsize = bsize)
            dolmdd(of = self.primary_volume, bs = "4k", opat = "1")
            drop_caches(tc=self)
            r = lmdd_checkpattern(self.primary_volume, 4096, 0, 0)
            do_pass(self, 'test_block_sizes:%s' % bsize, r == 0)
            self.deaccelerate()

if __name__ == '__main__':
    unittest.main(argv=["writeverifywholedev.py"] + args)
