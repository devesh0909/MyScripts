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
checkdev = Common_Utils.checkdev

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)



def doio(dev, count = 16, write = False):
    if not write:
        dodd(inf = dev, of = "/dev/null", bs = "4k", count = count)
    else:
        dodd(inf = "/dev/zero", of = dev, bs = "4k", count = count)

class BadDisk(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(BadDisk, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        self.remove_bad_disk("bad_dev")
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)
        super(BadDisk, self).tearDown()

    def create_bad_disk(self,devname,name,start,count):
        new_device=""
        r = os.system("""dmsetup create %s << -EOD
0 %s linear %s 0
%s %s error
%s 10240000 linear %s 0
-EOD
""" % (name, start, devname, start, count,(count+start), devname))
        cmd="ls -l /dev/mapper/%s |cut -d '.' -f3"%name
        out = subprocess.check_output(cmd, shell=True)
        new_device=("/dev%s"%out).replace("\n", "")
        return new_device

    def remove_bad_disk(self,name):
        r = os.system("dmsetup remove %s" %name)


    def test_1(self):
        policy="write-back"
        self.bad_dev=self.create_bad_disk(self.primary_volume, "bad_dev", 102400, 1024)
        checkdev(self.bad_dev, tc=self)

        accelerate_dev(self.bad_dev, self.ssd_volume, 4096, tc=self, write_policy = policy)

        doio(self.bad_dev,write=True)

        deaccelerate_dev(self.bad_dev, tc=self)

    def test_2(self):
        policy="write-back"
        self.bad_dev=self.create_bad_disk(self.ssd_volume, "bad_dev", 102400, 1024)
        checkdev(self.bad_dev, tc=self)

        accelerate_dev(self.primary_volume, self.bad_dev, 4096, tc=self, write_policy = policy)

        doio(self.primary_volume,write=True)

        deaccelerate_dev(self.primary_volume, tc=self)


if __name__ == '__main__':
    unittest.main(argv=["baddisk.py"] + args)

