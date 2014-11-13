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
import datetime

from common_utils import *
from cblog import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

class WriteBack(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(WriteBack, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.devbsz = get_devblksz(self.primary_volume)

    def tearDown(self):
        super(WriteBack, self).tearDown()

    def test_1(self):

      # basic check for write back caching, asserts that a single
      # write is cached.

      self.accelerate()
      self.setpolicy()
      self.seq_write()
      self.flush()
      stats = self.getxstats()
      self.deaccelerate()
      do_pass(self, 'test_1', stats.get('cs_writecache_flow') > 0)

    def test_2(self):

      # asserts that dirty RUs are not reclaimed

      RUSIZE = 1 << 20 # hardcoded to 1MB as per our code
      bsize = 4096
      count = RUSIZE/bsize

      self.accelerate()
      self.setpolicy()

      #
      # fill up an entire RU to trigger the reclaim. reclaim wont work
      # on anything less than a fully filled RU.
      #

      self.seq_write(count = count)
      self.flush()
      self.reclaim()
      stats = self.getxstats()
      self.deaccelerate()

      do_pass(self, 'test_2:1', stats.get('cs_reclaim_ebscnt') == 0)


    def test_3(self):

      # asserts that a serial write to the entire primary drive works
      # without hangs, panics or IO errors. note, this test should be
      # followed up with more specific cases to check for enospace,
      # wrap arounds etc.

      self.accelerate()
      self.setpolicy()
      self.filldisk()
      self.flush()
      stats = self.getxstats()
      self.deaccelerate()
      do_pass(self, 'test_3', stats.get('cs_writecache_flow') > 0)

if __name__ == '__main__':
  unittest.main(argv=["writeback.py"] + args)
