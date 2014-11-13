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

import random
import subprocess
import sys
import unittest

from common_utils import *
from cblog import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)


class CBASM(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(CBASM, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def do_sp(self, cmd):
        r = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        out, err = r.communicate()
        return (r.returncode, out, err)

    def test_1(self):
        cmd = (
            "cbasm",
            "--help"
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

        cmd = (
            "cbasm",
            "--volume",
            "--help"
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

    def test_2(self):
        cmd = (
            "cbasm",
            "--list"
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

    def test_3(self):
        cmd = (
            "cbasm",
            "--volume",
            "--list"
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

    def test_4(self):
        cmd = (
            "cbasm",
            "--junk",
            )

        r, out, err = self.do_sp(cmd)
        self.assertNotEqual(r, 0)


    def test_5(self):
        cmd = (
            "cbasm",
            "--accelerate",
            "--device=%s" % self.primary_volume,
            "--ssd=%s" % self.ssd_volume,
            "--write-policy=%s" % DEFAULT_WRITE_POLICY
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

        cmd = (
            "cachebox",
            "-l",
            "-d",
            "%s" % self.primary_volume
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

        cmd = (
            "cbasm",
            "--letgo",
            "--device=%s" % self.primary_volume,
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)


    def test_6(self):
        cmd = (
            "cbasm",
            "--accelerate",
            "--device=%s" % self.primary_volume,
            "--ssd=%s" % self.ssd_volume,
            "--write-policy=%s" % DEFAULT_WRITE_POLICY
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

        cmd = (
            "cbasm",
            "--accelerate",
            "--device=%s" % self.primary_volume,
            "--ssd=%s" % self.ssd_volume,
            "--write-policy=%s" % DEFAULT_WRITE_POLICY
            )

        r, out, err = self.do_sp(cmd)
        self.assertNotEqual(r, 0)

        cmd = (
            "cbasm",
            "--letgo",
            "--device=%s" % self.primary_volume,
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

    def test_7(self):
        cmd = (
            "cbasm",
            "--accelerate",
            "--device=%s" % self.primary_volume,
            "--ssd=%s" % self.ssd_volume,
            "--write-policy=%s" % DEFAULT_WRITE_POLICY
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

        confdata = open("/etc/cachebox/cachebox_txt.conf").read()
        self.assertTrue(self.primary_volume in confdata)

        cmd = (
            "cbasm",
            "--letgo",
            "--device=%s" % self.primary_volume,
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

        confdata = open("/etc/cachebox/cachebox_txt.conf").read()
        self.assertTrue(self.primary_volume not in confdata)

    def test_8(self):
        #
        # Don't allow acceleration of root devices in write-back mode
        # Select any root device and try accelerate it in write back policy
        # 
        root_device = os.popen("cbasm --volume --list | grep root | awk \'{print $2}\' | tail -1").read().strip()

        cmd = (
            "cbasm",
            "--accelerate",
            "--device=%s" % ('/dev/'+root_device),
            "--ssd=%s" % self.ssd_volume,
            "--write-policy=write-back"
            )

        r, out, err = self.do_sp(cmd)
        self.assertNotEqual(r, 0)

    def test_9(self):

        #
        # Allow acceleration of root devices in write-back mode
        # Select any root device and try accelerate it in write-through | write around policy
        # 
        writepolicies = ("write-through", "write-around", "read-around")
        root_device = os.popen("cbasm --volume --list | grep root | awk \'{print $2}\' | tail -1").read().strip()

        for policy in writepolicies :
            cmd = (
                "cbasm",
                "--accelerate",
                "--device=%s" % ('/dev/'+root_device),
                "--ssd=%s" % self.ssd_volume,
                "--write-policy=%s" % policy
                )

            r, out, err = self.do_sp(cmd)
            self.assertEqual(r, 0)
            cmd = (
                "cbasm",
                "--letgo",
                "--device=%s" % ('/dev/'+root_device)
                )

            r, out, err = self.do_sp(cmd)
            self.assertEqual(r, 0)

    def test_10(self):
        #
        # Test for root device
        #
        cmd = "mount | grep -w \'/\' | awk \'{print $1}\'"
        root_device = os.popen(cmd).read().strip()
        root_device = os.path.realpath(root_device)
        cmd = "cbasm --volume --list | grep %s > /dev/null" % root_device.split('/')[2]
        r = os.system(cmd)
        self.assertEqual(r, 0)

class CBASM_MYSQL(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(CBASM_MYSQL, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def do_sp(self, cmd):
        r = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        out, err = r.communicate()
        return (r.returncode, out, err)

    def check_accelerated(self, uuid):
        cmd = "cbasm --mysql --list | grep %s | awk \'{print $1}\'" % uuid
        ret = os.popen(cmd).read().strip()
        if ret == "*":
            return 0
        else:
            return 1

    def test_1(self):
        cmd = (
            "cbasm",
            "--mysql",
            "--help"
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

    def test_2(self):
        cmd = (
            "cbasm",
            "--mysql",
            "--list"
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

    def test_3(self):
        cmd = (
            "cbasm",
            "--mysql",
            "--junk",
            )

        r, out, err = self.do_sp(cmd)
        self.assertNotEqual(r, 0)

    def test_4(self):
        #
        # On subsequent mysql listing, the number
        # of component should remain the same, if
        # no new table, db has been created
        #
        cmd = (
            "cbasm",
            "--mysql",
            "--list"
            )

        r, out, err = self.do_sp(cmd)
        comp = [x.split("  ") for x in out.split("\n")[1:]]
        comp = filter(None, [filter(None, x) for x in comp])
        comp_cnt = len(comp)

        for i in xrange(5):
            r, out, err = self.do_sp(cmd)
            comp = [x.split("  ") for x in out.split("\n")[1:]]
            comp = filter(None, [filter(None, x) for x in comp])
        self.assertEqual(comp_cnt, len(comp))

    def test_5(self):
        #
        # Innodb index should not be displayed in
        # mysql listing while MyISAM indexes should
        # be displayed
        #
        cmd = (
            "cbasm",
            "--mysql",
            "--list"
            )

        r, out, err = self.do_sp(cmd)
        comp = [x.split("  ") for x in out.split("\n")[1:]]
        comp = filter(None, [filter(None, x) for x in comp])

        for c in comp:
                if (c[2].strip() == 'index'):
                        self.assertTrue(c[3].strip() != 'InnoDB')
        self.assertTrue(c[3].strip() == 'MyISAM')

    def test_6(self):
        #
        # Test for handling mysql deaccelration
        #
        cmd = "cbasm --mysql --list | grep table | head -1 | awk \'{print($5)}\'"
        primary_device = os.popen(cmd).read().strip()

        cmd = "cbasm --mysql --list | grep table | head -1 | awk \'{print($6)}\'"
        uuid = os.popen(cmd).read().strip()

        cmd = (
            "cbasm",
            "--accelerate",
            "--device=%s" % primary_device,
            "--ssd=%s" % self.ssd_volume,
            "--write-policy=%s" % DEFAULT_WRITE_POLICY
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

        cmd = (
            "cbasm",
            "--mysql",
            "--accelerate",
            "--uuid=%s" % uuid
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)
        r = self.check_accelerated(uuid)
        self.assertEqual(r, 0)

        cmd = (
            "cbasm",
            "--letgo",
            "--device=%s" % primary_device
            )

        r, out, err = self.do_sp(cmd)
        self.assertNotEqual(r, 0)

        cmd = (
            "cbasm",
            "--mysql",
            "--letgo",
            "--uuid=%s" % uuid
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)
        r = self.check_accelerated(uuid)
        self.assertNotEqual(r, 0)

        cmd = (
            "cbasm",
            "--letgo",
            "--device=%s" % primary_device
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

    def test_7(self):
        #
        # Test for handling forced mysql deaccelration
        #
        cmd = "cbasm --mysql --list | grep table | head -1 | awk \'{print($5)}\'"
        primary_device = os.popen(cmd).read().strip()

        cmd = "cbasm --mysql --list | grep table | head -1 | awk \'{print($6)}\'"
        uuid = os.popen(cmd).read().strip()

        cmd = (
            "cbasm",
            "--accelerate",
            "--device=%s" % primary_device,
            "--ssd=%s" % self.ssd_volume,
            "--write-policy=%s" % DEFAULT_WRITE_POLICY
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

        cmd = (
            "cbasm",
            "--mysql",
            "--accelerate",
            "--uuid=%s" % uuid
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)
        r = self.check_accelerated(uuid)
        self.assertEqual(r, 0)

        cmd = (
            "cbasm",
            "--letgo",
            "--device=%s" % primary_device,
            "--force"
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)
        r = self.check_accelerated(uuid)
        self.assertNotEqual(r, 0)

class CBASM_MONGODB(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(CBASM_MONGODB, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def do_sp(self, cmd):
        r = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        out, err = r.communicate()
        return (r.returncode, out, err)

    def check_accelerated(self, uuid):
        cmd = "cbasm --mongodb --list | grep %s | awk \'{print $1}\'" % uuid
        ret = os.popen(cmd).read().strip()
        if ret == "*":
            return 0
        else:
            return 1

    def test_1(self):
        #
        # Test for handling mongodb deaccelration
        #
        cmd = "cbasm --mongodb --list | grep collection | head -1 | awk \'{print($5)}\'"
        primary_device = os.popen(cmd).read().strip()

        cmd = "cbasm --mongodb --list | grep collection | head -1 | awk \'{print($6)}\'"
        uuid = os.popen(cmd).read().strip()

        cmd = (
            "cbasm",
            "--accelerate",
            "--device=%s" % primary_device,
            "--ssd=%s" % self.ssd_volume,
            "--write-policy=%s" % DEFAULT_WRITE_POLICY
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

        cmd = (
            "cbasm",
            "--mongodb",
            "--accelerate",
            "--uuid=%s" % uuid
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)
        r = self.check_accelerated(uuid)
        self.assertEqual(r, 0)

        cmd = (
            "cbasm",
            "--letgo",
            "--device=%s" % primary_device
            )

        r, out, err = self.do_sp(cmd)
        self.assertNotEqual(r, 0)

        cmd = (
            "cbasm",
            "--mongodb",
            "--letgo",
            "--uuid=%s" % uuid
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)
        r = self.check_accelerated(uuid)
        self.assertNotEqual(r, 0)

        cmd = (
            "cbasm",
            "--letgo",
            "--device=%s" % primary_device
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

    def test_2(self):
        #
        # Test for handling forced mongodb deaccelration
        #
        cmd = "cbasm --mongodb --list | grep collection | head -1 | awk \'{print($5)}\'"
        primary_device = os.popen(cmd).read().strip()

        cmd = "cbasm --mongodb --list | grep collection | head -1 | awk \'{print($6)}\'"
        uuid = os.popen(cmd).read().strip()

        cmd = (
            "cbasm",
            "--accelerate",
            "--device=%s" % primary_device,
            "--ssd=%s" % self.ssd_volume,
            "--write-policy=%s" % DEFAULT_WRITE_POLICY
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)

        cmd = (
            "cbasm",
            "--mongodb",
            "--accelerate",
            "--uuid=%s" % uuid
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)
        r = self.check_accelerated(uuid)
        self.assertEqual(r, 0)

        cmd = (
            "cbasm",
            "--letgo",
            "--device=%s" % primary_device,
            "--force"
            )

        r, out, err = self.do_sp(cmd)
        self.assertEqual(r, 0)
        r = self.check_accelerated(uuid)
        self.assertNotEqual(r, 0)

if __name__ == '__main__':
    unittest.main(argv=["cbasm.py"] + args)
