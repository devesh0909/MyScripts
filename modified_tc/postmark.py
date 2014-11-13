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

POSTMARK_DIR = '%spostmark/' % mountdir

class Postmark(CBQAMixin, unittest.TestCase):

    """
    This test essentially runs postmark, gathers the performance 
    and also fscks the test filesystem to ensure we haven't 
    introduced any corruptions.
    """

    def setUp(self):
        super(Postmark, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(Postmark, self).tearDown()

    def do_postmark(self, pmparams):
        do_mkfs(self.primary_volume, 4096, self)
        do_mkdir(POSTMARK_DIR, self)
        do_mount(self.primary_volume, POSTMARK_DIR, self)
        self.flush()
        template = string.Template(open('postmark.t').read())
        postmarkconf = template.substitute(pmparams)
        f = os.open('postmark.conf', os.O_RDWR|os.O_CREAT)
        os.write(f, postmarkconf)
        os.close(f)

        postmark = (
            "postmark",
            "postmark.conf"
            )
        r = subprocess.Popen(postmark, stdout=subprocess.PIPE, stderr = subprocess.PIPE)
        out, err = r.communicate()
        self.assertEqual(r.returncode, 0)

        do_unmount(POSTMARK_DIR, self)
        do_fsck(self.primary_volume, self)

        return (out, err)

    def do_pm_wrapper(self, pmparams):
        self.accelerate()
        self.setpolicy()
        out, err = self.do_postmark(pmparams)
        logger.debug('with ca results'.center(80, '#'))
        logger.debug(out)
        logger.debug(err)
        stats = self.getxstats()
        logger.debug(stats)

        self.deaccelerate()

        # fsck again after letting go of the device
        do_fsck(self.primary_volume, self)
        self.assertTrue(True)

    def test_1(self):
        pmparams = {'location':POSTMARK_DIR,
                    'biasread':'set bias read',
                    'biascreate':'set bias create'
                    }
        self.do_pm_wrapper(pmparams)

    def test_2(self):
        pmparams = {'location':POSTMARK_DIR,
                    'biasread':'',
                    'biascreate':''
                    }
        self.do_pm_wrapper(pmparams)

if __name__ == '__main__':
    if os.system('which postmark > /dev/null') != 0:
        logger.info('postmark.py requires postmark benchmark to be installed. skipping.')
        sys.exit(1)
    unittest.main(argv=["postmark.py"] + args)
