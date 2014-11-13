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

getxstats = Common_Utils.getxstats
accelerate_dev = Common_Utils.accelerate_dev
accelerate_allregions = Common_Utils.accelerate_allregions
deaccelerate_dev = Common_Utils.deaccelerate_dev
drop_caches = Common_Utils.drop_caches
get_devblksz = Common_Utils.get_devblksz
setpolicy_dev = Common_Utils.setpolicy_dev

pstring = 'abcdefghijklmnopqrstuvwxyz0123456789'

def genpattern(pattern):
    buf = 4096 * pattern[0]
    (fd, fname) = tempfile.mkstemp()
    open(fname, 'w').write(buf)
    return fname

class BufCache(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(BufCache, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        self.devbsz = get_devblksz(self.primary_volume)
        logger.debug("testing with %s and %s" % (self.primary_volume, self.ssd_volume))

    def tearDown(self):
        super(BufCache, self).tearDown()

    def test_1(self):
      f = genpattern('1')
      r = os.system("cbbuf -a 2 -d %s -p %s -s 0" % (self.ssd_volume, f))
      self.assertEqual(r, 0)
      r = os.system("cbbuf -a 3 -d %s -s 0" % (self.ssd_volume))
      self.assertEqual(r, 0)

    def test_2(self):
      f = genpattern(random.choice(pstring))
      os.system("cbbuf -a 2 -d %s -p %s -s 0 > /dev/null 2>&1" % (self.ssd_volume, f))
      os.system("cbbuf -a 1 -d %s -s 0 > %spattern.out" % (self.ssd_volume, tmpdir))
      r = os.system("diff %s %s" % (f, "%spattern.out" % tmpdir))
      self.assertEqual(r, 0)
      r = os.system("cbbuf -a 3 -d %s -s 0" % (self.ssd_volume))
      self.assertEqual(r, 0)

    def test_3(self):
      f = genpattern(random.choice(pstring))
      r = os.system("cbbuf -a 2 -d %s -p %s -s 0" % (self.ssd_volume, f))
      self.assertEqual(r, 0)
      r = os.system("cbbuf -a 3 -d %s -s 0" % (self.ssd_volume))
      self.assertEqual(r, 0)

    def test_4(self):
      f = genpattern(random.choice(pstring))
      i = 0
      s = 0
      while i < 1024:
          r = os.system("cbbuf -a 2 -d %s -p %s -s %s > /dev/null 2>&1" %
                       (self.ssd_volume, f, s))
          r = os.system("cbbuf -a 3 -d %s -s %s" % (self.ssd_volume, s))
          self.assertEqual(r, 0)
          i += 1
          s += 8

    def test_5(self):
      f = genpattern(random.choice(pstring))
      i = 0
      while i < 1024:
           s = random.randint(0, 100 << 11)
           r = os.system("cbbuf -a 2 -d %s -p %s -s %s > /dev/null 2>&1" %
               (self.ssd_volume, f, s))
           r = os.system("cbbuf -a 3 -d %s -s %s > /dev/null 2>&1" %
               (self.ssd_volume, s))
           i += 1

if __name__ == '__main__':
  unittest.main(argv=["buf.py"] + args)
