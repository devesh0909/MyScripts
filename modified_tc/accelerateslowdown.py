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

WRITE_POLICY = ['write-back', 'write-through', 'write-around', 'read-around']

class AccelerateSlowdown(CBQAMixin, unittest.TestCase):

    """
    Accelerate and slowdown while IOs are ongoing.
    """

    def setUp(self):
        super(AccelerateSlowdown, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.devbsz = get_devblksz(self.primary_volume)
        do_mkfs(self.primary_volume, "default", tc=self)
        do_mkdir("%stest" % mountdir, tc=self)

    def tearDown(self):
        super(AccelerateSlowdown, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)
        set_devblksz(self.primary_volume, self.devbsz, tc=self)

    def test_1(self):
        for policy in WRITE_POLICY: 
            self.stopthread = 0
            threadA = threading.Thread(target = mount_unmount, 
                                       kwargs = {'tc':self, 'pv':self.primary_volume}
                                       )
            kwargs = {
                 'tc':self, 
                 'pv':self.primary_volume, 
                 'sv':self.ssd_volume, 
                 'count':10,
                 'assertval':"use",
                 'write_policy': policy
                 }
            threadB = threading.Thread(target = accelerate_slowdown, kwargs = kwargs)
            threadA.start()
            threadB.start()

            threadA.join()
            threadB.join()

        do_pass(self, 'test_accelerate_slowdown_with_io_loop', 1)

    def test_2(self):
        for policy in WRITE_POLICY:
            self.stopthread = 0
            kwargs = {
                 'tc':self, 
                 'pv':self.primary_volume, 
                 'sv':self.ssd_volume, 
                 'count':10, 
                 'assertval':"use",
                 'write_policy': policy
                 }
            threadB = threading.Thread(target = accelerate_slowdown, kwargs = kwargs)
            threadB.start()
            threadB.join()

        do_pass(self, 'test_accelerate_slowdown_loop', 1)

if __name__ == '__main__':
    unittest.main(argv=["accelerateslowdown.py"] + args)
