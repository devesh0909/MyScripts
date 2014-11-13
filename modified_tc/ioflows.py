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


#
# Each caching mode will have a separate config file 
# Import the configuration file corresponing to given 
# caching mode. 
#

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
        cb_set_tunable("bio_testio", 1)

    def tearDown(self):
        super(IOFlows, self).tearDown()
        cb_set_tunable("bio_testio", 0)

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

    def do_read(self, flow):
        return self.do_io(0, flow)

    def do_write(self, flow):
        return self.do_io(1, flow)

    def do_read_partial(self, flow):
        return self.do_io(0, flow, sector=2)

    def do_write_partial(self, flow):
        return self.do_io(1, flow, sector=2)

    def do_reclaim(self, *args, **kwargs):
        def _f():

            # look at cbdebug.h for where codes, introduce a
            # delay after taking the iolock exclusive in
            # reclaim codepath (CB_RECLAIM_DELAY1)

            if len(args) > 1:
                param = args[1]
                where_delay = param.get('where_delay')
                if where_delay is not None:
                    self.where_delay(where_delay)

            cmd = (
                "cachebox",
                "-d",
                "%s" % self.primary_volume,
                "-R",
                "%s" % 1,
            )
            r = subprocess.Popen(cmd)
            out, err = r.communicate()
            self.assertEqual(r.returncode, 0, "reclaim")

        t = threading.Thread(target = _f, kwargs = {})
        t.start()
        time.sleep(2)
        return t

    def do_nospace(self):
        def _f(*args, **kwargs):
            cmd = (
                "./cbnospace",
                "-d",
                "%s" % self.primary_volume,
                "-t",
                "%s" % 1,
            )
            r = subprocess.Popen(cmd)
            out, err = r.communicate()
            self.assertEqual(r.returncode, 0, "nospace")

        t = threading.Thread(target = _f, kwargs = {})
        t.start()
        time.sleep(2)
        return t

    def do_disable(self):
        def _f(*args, **kwargs):
            cmd = (
                "./cbdisable",
                "-d",
                "%s" % self.primary_volume,
                )
            r = subprocess.Popen(cmd)
            out, err = r.communicate()
            self.assertEqual(r.returncode, 0, "disable")

        t = threading.Thread(target = _f, kwargs = {})
        t.start()
        time.sleep(2)
        return t

    def do_copyback(self):
        def _f(*args, **kwargs):
            cmd = (
                "./cbcopyback",
                "-d",
                "%s" % self.primary_volume,
                )
            r = subprocess.Popen(cmd)
            out, err = r.communicate()
            self.assertEqual(r.returncode, 0, "copyback")

        t = threading.Thread(target = _f, kwargs = {})
        t.start()

        # implement a synchronous copyback interface by sleeping
        # for longer.

        time.sleep(4)
        return t

    def do_concurrent(self, *args):

        # setting delayed_ioflow will put all IOs in a delayed
        # loop and will not be processed until delayed_ioflow is
        # set to 0. this gives us a chance to push more IOs into
        # the system exercising the concurrent IO code flows.

        concurrent = args[1]
        if concurrent:
            cb_set_tunable("delayed_ioflow", 1)
        else:
            cb_set_tunable("delayed_ioflow", 0)
        return None

    def do_test(self, tc):
        amode = tc[0]
        actions = tc[1:]
        print 'starting test with %s: %s' % (amode, actions)
        threads = []
        self.accelerate(write_policy = amode)
        self.setpolicy()
        for action in actions:
            if action[0] == "io":
                f = getattr(self, 'do_%s' % action[1])
                t = f(action[2])
            elif action[0] == "reclaim":
                t = self.do_reclaim(*action)
            elif action[0] == "nospace":
                t = self.do_nospace()
            elif action[0] == "copyback":
                t = self.do_copyback()
            elif action[0] == "disable":
                t = self.do_disable()
            elif action[0] == "concurrent":
                t = self.do_concurrent(*action)
            else:
                assert "unhandled action"

            if t is not None:
                threads.append(t)

        for t in threads:
            t.join()

        self.deaccelerate()

    def test_1(self):
        for tc in testcases:
            self.do_test(tc)

    def test_2(self):

        # concurrent IOS
        for tc in concurrentio_testcases:
            self.do_test(tc)


    def test_3(self):

        # partial IOS
        for tc in partialio_testcases:
            self.do_test(tc)

if __name__ == '__main__':

   unittest.main(argv=["ioflows.py"] + args)
