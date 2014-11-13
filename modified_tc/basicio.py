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
import string
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


class BasicIO(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(BasicIO, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def do_fio(self, section, direct):
	    fioparams = {
		    'direct':direct,
		    'filename':self.primary_volume,
		    'runtime':cbqaconfig.get('FIO_RUNTIME')
		    }
	    template = string.Template(open('fio.t').read())
	    fioconf = template.substitute(fioparams)
	    f = os.open('fio.conf', os.O_RDWR|os.O_CREAT)
	    os.write(f, fioconf)
	    os.close(f)

	    fio = (
		    "fio",
		    "--section=%s" % section,
		    "fio.conf"
		    )
	    r = subprocess.Popen(fio, stdout=subprocess.PIPE, stderr = subprocess.PIPE)
	    out, err = r.communicate()
	    self.assertEqual(r.returncode, 0)
	    return (out, err)

    def test_1(self):
	    self.accelerate()
	    self.setpolicy()
	    self.do_fio('rand-read', 1)
	    stats = self.getxstats()

            if DEFAULT_WRITE_POLICY == 'read-around':
	      self.assertTrue(stats.get('cs_readpopulate_flow') == 0)
	    else:
	      self.assertTrue(stats.get('cs_readpopulate_flow') > 0)
	    self.deaccelerate()
	    self.assertTrue(True)

    def test_2(self):
	    self.accelerate()
	    self.setpolicy()
	    self.do_fio('rand-write', 1)
	    stats = self.getxstats()
	    self.assertTrue(stats.get('cs_writecache_flow') > 0 
			    or stats.get('cs_writethrough_flow') > 0)
	    self.deaccelerate()
	    self.assertTrue(True)

    def test_3(self):
	    self.accelerate()
	    self.setpolicy()
	    self.do_fio('seq-read', 1)
	    stats = self.getxstats()
            if DEFAULT_WRITE_POLICY == 'read-around':
	      self.assertTrue(stats.get('cs_readpopulate_flow') == 0)
	    else:
	      self.assertTrue(stats.get('cs_readpopulate_flow') > 0)
	    self.deaccelerate()
	    self.assertTrue(True)

    def test_4(self):
	    self.accelerate()
	    self.setpolicy()
	    self.do_fio('seq-write', 1)
	    stats = self.getxstats()
	    self.assertTrue(stats.get('cs_writecache_flow') > 0 
			    or stats.get('cs_writethrough_flow') > 0)
	    self.deaccelerate()
	    self.assertTrue(True)

    def test_5(self):
	    self.accelerate()
	    self.setpolicy()
	    self.do_fio('rand-read', 0)
	    stats = self.getxstats()
            if DEFAULT_WRITE_POLICY == 'read-around':
	      self.assertTrue(stats.get('cs_readpopulate_flow') == 0)
	    else:
	      self.assertTrue(stats.get('cs_readpopulate_flow') > 0)
	    self.deaccelerate()
	    self.assertTrue(True)

    def test_6(self):
	    self.accelerate()
	    self.setpolicy()
	    self.do_fio('rand-write', 0)
	    stats = self.getxstats()
	    self.assertTrue(stats.get('cs_writecache_flow') > 0 
			    or stats.get('cs_writethrough_flow') > 0)
	    self.deaccelerate()
	    self.assertTrue(True)

    def test_7(self):
	    self.accelerate()
	    self.setpolicy()
	    self.do_fio('seq-read', 0)
	    stats = self.getxstats()
            if DEFAULT_WRITE_POLICY == 'read-around':
	      self.assertTrue(stats.get('cs_readpopulate_flow') == 0)
	    else:
	      self.assertTrue(stats.get('cs_readpopulate_flow') > 0)
	    self.deaccelerate()
	    self.assertTrue(True)

    def test_8(self):
	    self.accelerate()
	    self.setpolicy()
	    self.do_fio('seq-write', 0)
	    stats = self.getxstats()
	    self.assertTrue(stats.get('cs_writecache_flow') > 0 
			    or stats.get('cs_writethrough_flow') > 0)
	    self.deaccelerate()
	    self.assertTrue(True)

if __name__ == '__main__':
    if os.system('which fio > /dev/null') != 0:
	logger.info('basicio.py requires fio benchmark to be installed. skipping.')
	sys.exit(1)
    unittest.main(argv=["basicio.py"] + args)
