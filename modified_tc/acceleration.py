#!/usr/bin/python

#
#  Copyright 2012 Cachebox, Inc. All rights reserved. This software is
#  property of Cachebox, Inc and contains trade secrects, confidential
#  & proprietary information. Use, disclosure or copying this without
#  explicit written permission from Cachebox, Inc is prohibited.
#
#  Author: Cachebox, Inc (sales@cachebox.com)
#

import fcntl
import os
import random
import shutil
import sys
import time
import unittest

from cblog import *
from common_utils import *
from layout import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

WRITE_POLICY = ['write-back', 'write-through','write-around', 'read-around']

class TestAccelerateUsedDevice(CBQAMixin, unittest.TestCase):
    """
    Test the acceleration of already accelerated and already
    accelerating devices.
    """

    def setUp(self):
        super(TestAccelerateUsedDevice, self).setUp()
        create_devices(ssdsz=5, pvolsz=10, bs=4096, oddsize=0, tc=self)

    def tearDown(self):
        super(TestAccelerateUsedDevice, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

        del_loopdev(self.ssd_volume, tc=self)
        del_loopdev(self.primary_volume, tc=self)

        del_tmpfile(self.ssdtmpfile, tc=self)
        del_tmpfile(self.hddtmpfile, tc=self)

    def test_1(self):
        for policies in WRITE_POLICY:
            self.pv1 = random.choice(PRIMARY_VOLUMES)
            self.sv1 = random.choice(SSD_VOLUMES.keys())

            if len(SSD_VOLUMES[self.sv1]) == 0:
                do_skip(self, 'test_accelerate_used_device')
            continue
            self.spart1 = random.choice(SSD_VOLUMES[self.sv1])
            #
            # Check if the devices in config.py are already existing
            #
            checkdev(devname=self.pv1, tc=self)
            checkdev(devname=self.sv1, tc=self)
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self, write_policy = policies)
            #
            # check if the device has been added to the configuration
            #
            returncode, output = list_accelerated_device()
            do_pass(self, 'test_accelerate_used_device:1a', returncode == 0)
            o = filter(None, output.split("\n"))
            do_pass(self, 'test_accelerate_used_device:1a', len(o) == 1)
            do_pass(self, 'test_accelerate_used_device:1b', self.primary_volume == o[-1].split()[0])
            do_pass(self, 'test_accelerate_used_device:1c', self.ssd_volume == o[-1].split()[1])

            #
            # try accelerating the same device
            #

            returncode = accelerate_dev(self.primary_volume, self.ssd_volume, 4096, tc=self, 
                                        debug = True, write_policy = policies)
            do_pass(self, 'test_accelerate_used_device:1d', returncode != 0)

            #
            # check if the device has not been added to the
            # configuration and configuration is still the same
            #

            returncode, output = list_accelerated_device()
            self.assertEqual(returncode, 0)
            o = filter(None, output.split("\n"))
            self.assertEqual(len(o), 1)
            self.assertEqual(self.primary_volume, o[-1].split()[0])
            self.assertEqual(self.ssd_volume, o[-1].split()[1])

            #
            # try accelerating the same device with different ssd volume
            #
            returncode = accelerate_dev(self.primary_volume, self.sv1, 4096, tc=self, debug = True, write_policy = policies)
            self.assertNotEqual(returncode, 0)
            #
            # check if the device has not been added to the configuration
            # and configuration is still the same
            #
            returncode, output = list_accelerated_device()
            self.assertEqual(returncode, 0)
            o = filter(None, output.split("\n"))
            self.assertEqual(len(o), 1)
            self.assertEqual(self.primary_volume, o[-1].split()[0])
            self.assertEqual(self.ssd_volume, o[-1].split()[1])

            #
            # try accelerating already in use ssd volume with another ssd
            #
            returncode = accelerate_dev(self.ssd_volume, self.sv1, 4096, tc=self,
                         debug = True, write_policy = policies)
            self.assertNotEqual(returncode, 0)
            #
            # check if the device has not been added to the configuration
            # and configuration is still the same
            #
            returncode, output = list_accelerated_device()
            self.assertEqual(returncode, 0)
            o = filter(None, output.split("\n"))
            self.assertEqual(len(o), 1)
            self.assertEqual(self.primary_volume, o[-1].split()[0])
            self.assertEqual(self.ssd_volume, o[-1].split()[1])

            #
            # try accelerating another primary volume with same ssd volume
            #
            returncode = accelerate_dev(self.pv1, self.ssd_volume, 4096, tc=self, debug = True, write_policy = policies)
            self.assertNotEqual(returncode, 0)
            #
            # check if the device has not been added to the configuration
            # and configuration is still the same
            #
            returncode, output = list_accelerated_device()
            self.assertEqual(returncode, 0)
            o = filter(None, output.split("\n"))
            self.assertEqual(len(o), 1)
            self.assertEqual(self.primary_volume, o[-1].split()[0])
            self.assertEqual(self.ssd_volume, o[-1].split()[1])

            #
            # try accelerating a new primary volume with a different ssd
            #
            accelerate_dev(self.pv1, self.sv1, 4096, tc=self)
            #
            # check if the device has been added to the configuration
            #
            returncode, output = list_accelerated_device()
            self.assertEqual(returncode, 0)
            o = filter(None, output.split("\n"))
            self.assertEqual(len(o), 2)

            deaccelerate_dev(self.primary_volume, tc=self)

            #
            # try accelerating a primary volume with a partition
            #
            returncode = accelerate_dev(self.primary_volume, self.spart1, 4096, tc=self, debug = True, write_policy = policies)
            self.assertNotEqual(returncode, 0)
            #
            # check if the device has not been added to the configuration
            # and configuration is still the same
            #
            returncode, output = list_accelerated_device()
            self.assertEqual(returncode, 0)
            o = filter(None, output.split("\n"))
            self.assertEqual(len(o), 1)
            self.assertEqual(self.pv1, o[-1].split()[0])
            self.assertEqual(self.sv1, o[-1].split()[1])

            deaccelerate_dev(self.pv1, tc=self)

            #
            # try accelerating a new primary volume with a partition
            #
            accelerate_dev(self.pv1, self.spart1, 4096, tc=self, write_policy = policies)
            #
            # check if the device has been added to the configuration
            #
            returncode, output = list_accelerated_device()
            self.assertEqual(returncode, 0)
            o = filter(None, output.split("\n"))
            self.assertEqual(len(o), 1)
            self.assertEqual(self.pv1, o[-1].split()[0])
            self.assertEqual(self.spart1, o[-1].split()[1])

            #
            # try accelerating a primary volume with a volume
            #
            returncode = accelerate_dev(self.primary_volume, self.sv1, 4096, tc=self, debug = True, write_policy = policies)
            self.assertNotEqual(returncode, 0)
            #
            # check if the device has not been added to the configuration
            # and configuration is still the same
            #
            returncode, output = list_accelerated_device()
            self.assertEqual(returncode, 0)
            o = filter(None, output.split("\n"))
            self.assertEqual(len(o), 1)
            self.assertEqual(self.pv1, o[-1].split()[0])
            self.assertEqual(self.spart1, o[-1].split()[1])

            deaccelerate_dev(self.pv1, tc=self)

        do_pass(self, 'test_accelerate_used_device')

class TestAcceleratedInvalidDevice(CBQAMixin, unittest.TestCase):
    """
    Test the acceleration of invalid accelerating devices and invalid ssd.
    """

    def setUp(self):
        super(TestAcceleratedInvalidDevice, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(TestAcceleratedInvalidDevice, self).tearDown()
        if isdev_accelerated(self.pv1):
            deaccelerate_dev(self.pv1, tc=self)

    def test_1(self):
        for policies in WRITE_POLICY:
            logger.debug("========Testing for %s Policy========" % policies)
            self.pv1 = random.choice(PRIMARY_VOLUMES)
            self.sv1 = random.choice(SSD_VOLUMES.keys())
            invalid_device="/dev/sdef"
            invalid_ssd="/dev/sdhs"

            #
            #check the primary volume or ssd volume are valid or not
            #
            #
            #if primary volume is invalid then acceleration fails
            #
            returncode = accelerate_dev(invalid_device, self.sv1, 4096, tc=self, debug = True, write_policy = policies)
            self.assertNotEqual(returncode, 0)
            #
            #if ssd volume is invalid then acceleration fails 
            #
            returncode = accelerate_dev(self.pv1, invalid_ssd, 4096, tc=self, debug = True, write_policy = policies)
            self.assertNotEqual(returncode, 0)
            #
            #if primary and ssd both volume are invalid then acceleration fails
            #
            returncode = accelerate_dev(invalid_device, invalid_ssd, 4096, tc=self, debug = True, write_policy = policies)
            self.assertNotEqual(returncode, 0)
            #
            #if primary volume and ssd volume are valid  then accelerate primary volume with ssd volume
            #
            returncode = accelerate_dev(self.pv1, self.sv1, 4096, tc=self, debug = True, write_policy = policies)
            deaccelerate_dev(self.pv1, tc = self)
        self.assertEqual(returncode, 0)


class Acceleration3(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(Acceleration3, self).setUp()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def test_1(self):

        # once we letgo the device, the same cannot be accelerated
        # using cachebox -a 3.

        self.accelerate()
        self.deaccelerate()

        r = os.system("cachebox -a 3 -d %s -s %s > /dev/null 2>&1" % (
                    self.primary_volume, self.ssd_volume))
        self.assertTrue(r != 0)


if __name__ == '__main__':
    unittest.main(argv=["acceleration.py"] + args)
