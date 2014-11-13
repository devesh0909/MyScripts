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

class Letgo(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(Letgo, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.devbsz = get_devblksz(self.primary_volume)

    def tearDown(self):
        super(Letgo, self).tearDown()

    def test_1(self):

      self.accelerate()
      self.setpolicy()

      #
      # start a background thread to start some IOs, we don't really
      # care read or write for this test
      #

      t = self.seq_read(thread = True)

      # look at cbdebug.h for where codes, introduce a delay before
      # taking the drive off the accelerated list (aglist) but before
      # destroying the data structures.

      self.where_delay(1)

      # now we have setup letgo to sleep while IOs are going on. fire
      # a letgo

      self.deaccelerate()
      t.join()

      self.assertTrue(True)

    def test_2(self):

      self.accelerate()
      self.setpolicy()

      #
      # start a background thread to start some IOs, we don't really
      # care read or write for this test
      #

      t = self.seq_read(thread = True)

      # look at cbdebug.h for where codes, introduce a delay after
      # taking the drive off the aglist.

      self.where_delay(2)

      # now we have setup letgo to sleep while IOs are going on. fire
      # a letgo

      self.deaccelerate()
      t.join()

      self.assertTrue(True)

if __name__ == '__main__':
  unittest.main(argv=["letgo.py"] + args)
