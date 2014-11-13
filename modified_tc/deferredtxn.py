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

ioflow_file = "%s_%s" %(DEFAULT_WRITE_POLICY,'ioflow')
try:
    obj = __import__(ioflow_file)
    for member_name in dir(obj):
        if not member_name.startswith("__"):
            globals()[member_name] = getattr(obj, member_name)
except:
    print ("Import of %s failed. May be configuration file (%s.py) does" 
	 " not exist in current dir. Please create ioflow configuration" 
         " file corresponding to %s caching mode before running this test." 
	  %(ioflow_file, ioflow_file, DEFAULT_WRITE_POLICY))	

    sys.exit(0)


class IOFlows(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(IOFlows, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.devbsz = get_devblksz(self.primary_volume)
	os.system("echo 1 > /proc/sys/kernel/cachebox/bio_testio")

    def tearDown(self):
        super(IOFlows, self).tearDown()
	os.system("echo 0 > /proc/sys/kernel/cachebox/bio_testio")

    def do_io(self, rw, flow, sector = 0, bsize = 4096):
	    assert flow in flowcodes.keys()

	    def _f(*args, **kwargs):
		    cmd = (
			    "./cbio",
			    "-d",
			    "%s" % self.primary_volume,
			    "-a",
			    "%s" % rw,
			    "-p",
			    "cbbuf",
			    "-s",
			    "%s"%sector,
			    "-b",
			    "%s"%bsize
			    )
		    r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		    out, err = r.communicate()
		    self.assertEqual(r.returncode, flowcodes.get(flow),
				     "%s %s %s" %(rwdict[rw], flow, r))

	    t = threading.Thread(target = _f, kwargs = {})
	    t.start()
	    time.sleep(2)
	    return t

    def test_1(self):
	    self.accelerate()
	    self.setpolicy()

	    # setup the deferred transaction thread to sleep before
	    # calling schedule.
	    os.system("echo 4 > /proc/sys/kernel/cachebox/where_delay")

	    # a writecache should result in a deferred transaction and
	    # will invoke the cbdt thread to sleep as setup above

	    t1 = self.do_io(1, 'writecache')

	    # another write should also invoke the cbdt thread, ensure
	    # there is no lost wakeup related issue.

	    t2 = self.do_io(1, 'writecache')

	    t1.join()
	    t2.join()

	    os.system("echo 0 > /proc/sys/kernel/cachebox/where_delay")
	    self.deaccelerate()

if __name__ == '__main__':
  unittest.main(argv=["deferredtxn.py"] + args)
