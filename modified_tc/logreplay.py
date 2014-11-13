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

LOG_SIZE = (1 << 20)

def take_checkpoint(primary_volume):
		cmd = [
			   "./cbtran",
			   "-d",
			   "%s" % primary_volume,
			   "-c"
			  ]
		r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		output = r.communicate()[0]
		assert(r.returncode == 0)

def flush_logs(primary_volume):
		cmd = [
			   "./cbtran",
			   "-d",
			   "%s" % primary_volume,
			   "-f"
			  ]
		r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		output, error = r.communicate()
		assert(r.returncode == 0)

def format_logsize(primary_volume, ssd_volume, logsize):
		cmd = "cbfmt -d %s -s %s -l %s" % (primary_volume, ssd_volume, logsize)
		r = os.system(cmd)
		assert(r == 0)

class LogReplay(CBQAMixin, unittest.TestCase):

	def setUp(self):
		super(LogReplay, self).setUp()
		self.primary_volume = random.choice(PRIMARY_VOLUMES)
		self.ssd_volume = random.choice(SSD_VOLUMES.keys())

		self.devbsz = get_devblksz(self.primary_volume)
		logger.debug("testing with %s and %s" % (self.primary_volume, self.ssd_volume))

	def tearDown(self):
		super(LogReplay, self).tearDown()

	def test_0(self):

	  #
	  # basic check for replay caching, asserts that there is no input
	  # as log anchor would not have any checkpoints
	  #

	  bsize = 4096

	  accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")
	  setpolicy_dev("fulldisk", self.primary_volume, None, tc=self)
	  drop_caches(self)
	  rc, output, err = self.log_replay(self.ssd_volume)
	  deaccelerate_dev(self.primary_volume, tc=self)
	  out = output.split("\n")
	  clsn = int(out[0].split(":")[-1])
	  coffset = int(out[1].split(":")[-1])
	  rlsn = int(out[1].split(":")[-1])
	  self.assertTrue(rc == 0)
	  self.assertTrue(clsn == 0)
	  self.assertTrue(coffset == 0)
	  self.assertTrue(rlsn == 0)
	  do_pass(self, 'test_1')


	def test_1(self):

	  #
	  # basic check for replay caching, asserts that there 
	  # as log anchor would	 have a checkpoint
	  #

	  bsize = 4096

	  accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")
	  setpolicy_dev("fulldisk", self.primary_volume, None, tc=self)
          dodd(inf = "/dev/zero", of = self.primary_volume, bs = bsize, count = 100, oflag = "direct")
	  drop_caches(self)
	  rc, output, err = self.log_replay(self.ssd_volume)
	  self.assertTrue(rc == 0)
	  flush_logs(self.primary_volume)
	  drop_caches(self)
	  take_checkpoint(self.primary_volume)
	  drop_caches(self)
	  drop_caches(self)
	  take_checkpoint(self.primary_volume)
	  drop_caches(self)
	  drop_caches(self)
	  rc, output, err = self.log_replay(self.ssd_volume)
	  out = output.split("\n")
	  deaccelerate_dev(self.primary_volume, tc=self)
	  self.assertTrue(rc == 0)
	  clsn = int(out[0].split(":")[-1])
	  coffset = int(out[1].split(":")[-1])
	  rlsn = int(out[1].split(":")[-1])
	  self.assertTrue(rc == 0)
	  self.assertTrue(clsn > 0)
	  self.assertTrue(coffset > 0)
	  self.assertTrue(rlsn > 0)
	  do_pass(self, 'test_1')


	def test_2(self):

	  # asserts that invalid disk returns NULL
	  bsize = 4096

	  accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")
	  setpolicy_dev("fulldisk", self.primary_volume, None, tc=self)
          dodd(inf = "/dev/zero", of = self.primary_volume, bs = bsize, count = 100, oflag = "direct")
	  drop_caches(self)
	  rc, output, err = self.log_replay(self.ssd_volume)
	  self.assertTrue(rc == 0)
	  flush_logs(self.primary_volume)
	  drop_caches(self)
	  take_checkpoint(self.primary_volume)
	  drop_caches(self)
	  drop_caches(self)
	  take_checkpoint(self.primary_volume)
	  drop_caches(self)
	  drop_caches(self)
	  rc, output, err = self.log_replay(self.primary_volume)
	  out = output.split("\n")
	  deaccelerate_dev(self.primary_volume, tc=self)
	  self.assertTrue(rc != 0)
	  do_pass(self, 'test_2')


	def test_3(self):

	  #
	  # on de-acceleration
	  #

	  bsize = 4096

	  accelerate_dev(self.primary_volume, self.ssd_volume, bsize, tc=self, write_policy = "write-back")
	  setpolicy_dev("fulldisk", self.primary_volume, None, tc=self)
          dodd(inf = "/dev/zero", of = self.primary_volume, bs = bsize, count = 100, oflag = "direct")
	  drop_caches(self)
	  rc, output, err = self.log_replay(self.ssd_volume)
	  self.assertTrue(rc == 0)
	  flush_logs(self.primary_volume)
	  drop_caches(self)
	  take_checkpoint(self.primary_volume)
	  drop_caches(self)
	  drop_caches(self)
	  take_checkpoint(self.primary_volume)
	  drop_caches(self)
	  drop_caches(self)
	  rc, output, err = self.log_replay(self.ssd_volume)
	  out = output.split("\n")
	  deaccelerate_dev(self.primary_volume, tc=self)
	  self.assertTrue(rc == 0)
	  clsn = int(out[0].split(":")[-1])
	  coffset = int(out[1].split(":")[-1])
	  rlsn = int(out[1].split(":")[-1])
	  self.assertTrue(rc == 0)
	  self.assertTrue(clsn > 0)
	  self.assertTrue(coffset > 0)
	  self.assertTrue(rlsn > 0)
	  rc, output, err = self.log_replay(self.ssd_volume)
	  out = output.split("\n")
	  self.assertTrue(rc == 0)
	  do_pass(self, 'test_3')

	def test_4(self):
		#
		# Log replay in case of log wrap around
		# primary test case.
		#

		bsize = 4096

		format_logsize(self.primary_volume, self.ssd_volume, LOG_SIZE)
		accelerate_existingdev(self.primary_volume, self.ssd_volume, self)
		accelerate_allregions(self.primary_volume, self)
		stats = getxstats(self.primary_volume)
		wrap_around = int(stats.get('cs_log_wrap_around'))
		off = 0
		while (wrap_around < 5):
          		dodd(inf = "/dev/zero", of = self.primary_volume, bs = bsize, count = 1000, oflag = "direct")
			drop_caches(self)
			stats = getxstats(self.primary_volume)
			wrap_around = int(stats.get('cs_log_wrap_around'))
			if (wrap_around >= 5):
				break
			self.copyback()
			stats = getxstats(self.primary_volume)
			wrap_around = int(stats.get('cs_log_wrap_around'))

		self.assertTrue(wrap_around >= 5)
	        rc, output, err = self.log_replay(self.ssd_volume)
		deaccelerate_dev(self.primary_volume, tc=self)
	        self.assertTrue(rc == 0)
   	        clsn = int(out[0].split(":")[-1])
	        coffset = int(out[1].split(":")[-1])
	        rlsn = int(out[1].split(":")[-1])
	        self.assertTrue(rc == 0)
	        self.assertTrue(clsn > 0)
	        self.assertTrue(coffset > 0)
	        self.assertTrue(rlsn > 0)
		do_pass(self, 'test_4')

if __name__ == '__main__':
  unittest.main(argv=["logreplay.py"] + args)
