import datetime
import errno
import logging
import os
import random
import subprocess
import sys
import threading
import time
import unittest
import uuid

sys.path.append("/usr/lib/cachebox")

from lib.heatmap import PersistentHeatmap
from lib.util import __accelerateregion as accelerateregion
from lib.util import __getxstats as getxstats
from lib.util import __gettr as gettr
from lib.util import __writeadmissionbitmap as writeadmissionbitmap

from asm.db import cdb

from common_utils import *
from cblog import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
	if not member_name.startswith("__"):
		globals()[member_name] = getattr(config, member_name)


class Heatmap2(CBQAMixin, unittest.TestCase):
	def setUp(self):
		super(Heatmap2, self).setUp()
		self.primary_volume = random.choice(PRIMARY_VOLUMES)
		self.ssd_volume = random.choice(SSD_VOLUMES.keys())

	def do_sp(self, cmd):
		r = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
		out, err = r.communicate()
		return (r.returncode, out, err)

        def test_1(self):
		self.flush()
		cmd = (
			"cbasm",
			"--accelerate",
			"--device=%s" % self.primary_volume,
			"--ssd=%s" % self.ssd_volume,
			"--write-policy=%s" % DEFAULT_WRITE_POLICY
			)

		r, out, err = self.do_sp(cmd)
		primary = cdb.getComponent({'device':self.primary_volume})
		uid = primary.get('uuid')

		xstats = self.getxstats()
		numregions = xstats.get('cs_numregions')

		ph = PersistentHeatmap(uid, primary.get('device'))
		bitmap = ph.getHeatmap()
		for region in xrange(0, numregions):
			if bitmap.get(region) == None:
				bitmap[region] = [0, 0]

			bitmap[region][0] += 1

		ph.setHeatmap(bitmap)
		ph.close()

		self.seq_read(bsize=1<<19, count=numregions)

		time.sleep(10)
		ph = PersistentHeatmap(uid, primary.get('device'))
		for region in xrange(0, numregions):
			assert ph.getRegion(region) != 0

		ph.close()

		self.flush()
		self.seq_read(bsize=1<<19, count=numregions)
		xstats = self.getxstats()
		self.assertNotEqual(xstats.get('cs_readpopulate_flow'), 0)
		
		cmd = (
			"cbasm",
			"--letgo",
			"--device=%s" % self.primary_volume,
		    )

		r, out, err = self.do_sp(cmd)
		self.assertEqual(r, 0)


if __name__ == '__main__':
    unittest.main(argv=["policy_long.py"] + args)
