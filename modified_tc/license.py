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
import time
import unittest
import stat
import glob
import platform
import threading
import string


from common_utils import *
from cblog import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)


path = os.getcwd()+"/../tools"
os.environ['PATH'] = "%s:%s" % (os.getenv('PATH'), path)


SSD_SIZE = [100 << 21, 250 << 21, 500 << 21,  1 << 31, 2 << 31]

"""
License keys are arranged as Professional, Enterprise, Datacenter
"""
LICENSE_KEYS = {'PROFESSIONAL': '7941-6750-5732-6542', \
                'ENTERPRISE': '7780-6750-0759-4471', \
                'DATACENTER': '7850-6750-9614-1695'}


class Utils(object):

    """
    This prints the cachebox stats in the log 
    """
    @staticmethod
    def statistics(policy, stats, tc):
        if policy == 'write-back':
            logger.debug("Read populate flow %s \
                          write back flow %s \
                          reads %s  \
                          reads_hits %s \
                          readcacheflow %s"
                        % (stats['cs_readpopulate_flow'], \
                           stats['cs_writecache_flow'], \
                           stats['cs_reads'], \
                           stats['cs_read_hits'], \
                           stats['cs_readcache_flow']))

        elif policy == 'write-through':
            logger.debug("Read populate flow %s \
                          write through flow %s \
                          reads %s \
                          reads_hits %s \
                          readcacheflow %s"
                        % (stats['cs_readpopulate_flow'], \
                           stats['cs_writethrough_flow'], \
                           stats['cs_reads'], \
                           stats['cs_read_hits'], \
                           stats['cs_readcache_flow']))
        else:
            logger.debug("Read populate flow %s \
                          write around flow %s \
                          reads %s \
                          reads_hits %s \
                          readcacheflow %s"
                        % (stats['cs_readpopulate_flow'], \
                           stats['cs_writearound_flow'], \
                           stats['cs_reads'], \
                           stats['cs_read_hits'], \
                           stats['cs_readcache_flow']))


    """
    collects the License credential
    """
    @staticmethod
    def check_license_stats(tc):
        cmd = [
            "cb",
            "--license-status"
            ]
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE)
        output = process_1.communicate()[0].strip('\n').split('\n')
        logger.debug(output)

        tc.assertEqual(process_1.returncode, 0)
        if process_1.returncode:
            tc.fail(output[0])
        else:
            status = output[0].split('=')[1].strip()
            license_type = output[1].split('=')[1].strip()
            days_left = output[2].split('=')[1].strip()
            license_stats = [status, license_type, days_left]
            return license_stats

    """
    Activate the Professional, Enterprise, Datacenter License 
    """
    @staticmethod
    def activate_key(key , tc):
        cmd = ("cb --license-activate -k %s" % key)
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, \
                stderr = subprocess.PIPE, shell = True)
        output, err = process_1.communicate()
        return process_1.returncode


    """
    Deactivate the License
    """
    @staticmethod
    def deactivate_key(tc):
        cmd = ("cb --license-deactivate")
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE, shell = True)
        output = process_1.communicate()
        return process_1.returncode



    """
    Register the License to the Kernel
    """
    @staticmethod
    def reinitalze_key(tc):
        cmd = ("cb --initialize")
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE, shell = True)
        output = process_1.communicate()
        tc.assertEqual(process_1.returncode, 0)



    """
    This method writes 117MB on the primary volume
    """
    @staticmethod
    def do_dd(tc, *args):
        primary_volume = "".join(args)
        r = dodd(inf = "/dev/zero", of = primary_volume, bs = "4096", count = 30000)
        tc.assertEqual(r, 0)


    """
    Collect stats before and after deactivation of license
    """
    @staticmethod
    def collect_cb_stats(tc, *args):
        primary_volume = "/"+"".join(args)
        time.sleep(3)
        before_deactivate = getxstats(primary_volume)
        statistics(DEFAULT_WRITE_POLICY, before_deactivate, tc)
        deactivate_key(tc)
        time.sleep(3)
        after_deactivate = getxstats(primary_volume)
        statistics(DEFAULT_WRITE_POLICY, after_deactivate, tc)
        time.sleep(3)

        tc.assertEqual(int(before_deactivate['cs_readpopulate_flow']), \
                        int(after_deactivate['cs_readpopulate_flow']))

        if DEFAULT_WRITE_POLICY == 'write-back':
            tc.assertEqual(int(before_deactivate['cs_writecache_flow']), \
                        int(after_deactivate['cs_writecache_flow']))
        elif DEFAULT_WRITE_POLICY == 'write-through':
            tc.assertEqual(int(before_deactivate['cs_writethrough_flow']), \
                        int(after_deactivate['cs_writethrough_flow']))
        else:
            tc.assertEqual(int(before_deactivate['cs_writearound_flow']), \
                        int(after_deactivate['cs_writearound_flow']))



    """
    Generate Numeric and Aplh-Numeric keys
    """
    @staticmethod
    def get_keys(tc):
        key = []
        key2 = []
        for i in range(0, 16):
            key.append(str(random.randint(0, 9)))
            if i == 3 or i == 7 or i == 11:
                key.append('-')
        key_1 = "".join(key)

        for i in range(0, 16):
            ss = (random.choice(string.letters))
            pp = (str(random.randint(0, 9)))
            tem = ss+pp
            key2.append(random.choice(tem))
            if i == 3 or i == 7 or i == 11:
                key2.append('-')
        key_2 = "".join(key2)

        keys = [key_1, key_2]
        return keys


    """
    Checks the OS of the system
    """
    @staticmethod
    def check_OS(tc):
        out = platform.dist()
        if out[0] == "Ubuntu":
            OS = "Ubuntu"
        else:
            OS = "CentOS"
        return OS


    """
    Collect Crential of License and put assertion
    """
    @staticmethod 
    def check_status(stats, lic_type, tc):
        status = check_license_stats(tc)
        logger.debug(status)
        tc.assertEquals(status[0], stats)
        tc.assertEquals(status[1], lic_type)
        tc.assertTrue(int(status[2]) >= 1 and int(status[2]) <= 31)


    """
    This method Install CA Package for Trial License Testing
    """
    @staticmethod
    def installCA(OS, tc):
        path = os.getcwd()+"/../src/linux"
        cmd = ("make clean")
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE, shell=True, cwd = path)
        out = process_1.communicate()
        tc.assertEqual(process_1.returncode, 0)

        if OS == 'Ubuntu':
            cmd = ("make TARGET=deb DEBUG=yes")
        else:
            cmd = ("make TARGET=rpm DEBUG=yes")

        logger.debug(cmd)
        process_2 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE, shell=True, cwd = path)
        out = process_2.communicate()
        tc.assertEqual(process_2.returncode, 0)

        #collecting cacheadvance installation file
        ca_file = glob.glob("%s/pkg/cacheadvance_*" % (path)) 

        if OS == "Ubuntu":
            cmd = ("echo 'y' | dpkg -i %s") %  ca_file[0]
            process_3 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE, shell=True, cwd = path + "/pkg")
            out = process_3.communicate()
            tc.assertEqual(process_3.returncode, 0)

        else:
            try:
                os.chdir("%s/pkg/rpm" % path)
            except Exception as e:
                print "Caught Exception at :    %s" % e

            cmd = ("tar -xjf CacheAdvance_pkg.tar.bz2")
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE, shell=True)
            out = process_1.communicate()
            tc.assertEqual(process_1.returncode, 0)

            try:
                os.chdir("CacheAdvance_pkg")
            except Exception as e:
                print "Caught Exception at :    %s" % e

            cmd = ("echo 'y' | bash -x install")
            process_2 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE, shell=True)
            out = process_2.communicate()
            tc.assertEqual(process_2.returncode, 0)

            try:
                os.chdir("../../../../../cbqa")
            except Exception as e:
                print "Caught Exception at :    %s" % e



    """
    This method Un-Install CA Package for Trial License Testing
    """
    @staticmethod
    def uninstallCA(OS, tc):
        if OS == "Ubuntu":
            cmd = ("dpkg -r cacheadvance")
        else:
            cmd = ("rpm -e cacheadvance")

        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE, shell=True)
        out = process_1.communicate()
        tc.assertEqual(process_1.returncode, 0)


    @staticmethod
    def move_license(tc):
       src = "/etc/cachebox/license/cachebox_*"
       dst = "/etc/cachebox/license_old/."
       if not os.path.exists(dst):
           os.makedirs(dst)
       cmd = "mv %s %s" % (src, dst)
       r = os.system(cmd)
       tc.assertEqual(r, 0)

    @staticmethod
    def reinstate_license(tc):
       src = "/etc/cachebox/license_old/*"
       dst = "/etc/cachebox/license/."
       cmd = "mv %s %s" % (src, dst)
       r = os.system(cmd)
       tc.assertEqual(r, 0)


activate_key = Utils.activate_key
check_license_stats = Utils.check_license_stats
check_OS = Utils.check_OS
collect_cb_stats = Utils.collect_cb_stats
check_status = Utils.check_status
deactivate_key = Utils.deactivate_key
do_dd = Utils.do_dd
get_keys = Utils.get_keys
installCA = Utils.installCA
reinitalze_key = Utils.reinitalze_key
statistics = Utils.statistics
uninstallCA = Utils.uninstallCA
move_license = Utils.move_license
reinstate_license = Utils.reinstate_license


"""
This verify the the Trail license of CacheAdvance
It validate the remaining days, stauts of Trial License
Uninstall and Install CA Package and again verfy the same
"""
class CheckTrialLicense(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(CheckTrialLicense, self).setUp()
        self.status = check_license_stats(tc = self)
        move_license(self)
        self.startTime = time.time()

    def tearDown(self):
        super(CheckTrialLicense, self).tearDown()
        reinstate_license(self)
        reinitalze_key(tc = self)

    def check_status(self):
        status = check_license_stats(tc = self)
        logger.debug(status)
        self.assertEquals(status[0], "Valid")
        self.assertEquals(status[1], "Trial")
        self.assertTrue(int(status[2]) >= 1 and int(status[2]) <= 31)


    """
    Install and Uninstall the Package and Check the Trail License
    """
    def test_1(self):
        if self.status[1] != "Trial":
            do_skip(self, "CheckTrialLicense.test_1")
            return
        for i in range(0, 2):
            os = check_OS(tc = self)
            uninstallCA(os, tc = self)
            installCA(os, tc = self)
            reinitalze_key(tc = self)
            self.check_status()


    """
    Try to Activate the License By providing one 
    Numeric and Aplhanumeric Key
    """
    def test_2(self):
        if self.status[1] != "Trial":
            do_skip(self, "CheckTrialLicense.test_2")
            return
        keys = get_keys(tc = self)
        for key in keys:
            r = activate_key(key, tc = self)
            self.assertNotEqual(r, 0)
            reinitalze_key(tc = self)
            self.check_status()
            r = deactivate_key(tc = self)
            self.assertNotEqual(r, 0)
            reinitalze_key(tc = self)



"""
This Will verify Professional/Enterprise/Datacenter License of CacheAdvance
"""
class CheckLicense(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(CheckLicense, self).setUp()
        self.status = check_license_stats(tc = self)
        move_license(self)
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd = random.choice(SSD_VOLUMES.keys())
        self.license_type = LICENSE_KEYS.keys()

    def tearDown(self):
        super(CheckLicense, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc = self)
        if os.path.exists("/dev/mapper/test") or os.path.exists("/dev/mapper/Test"):
            delete_dmsetup(tc = self)
        deactivate_key(tc = self)
        reinstate_license(self)
        reinitalze_key(tc = self)


    """
    Try to Activate the License By proving \ 
    Numeric and Aplhanumeric Key
    """
    def test_1(self):
        for i in range(0, (len(LICENSE_KEYS))):
            logger.debug("===Testing %s LICENSE===" % self.license_type[i])
            keys = get_keys(tc = self)
            for key in keys:
                reinitalze_key(tc = self)
                if self.status[1] == "Trial":
                    check_status('Valid', 'Trial', tc = self)
                r = activate_key(key, tc = self)
                self.assertNotEqual(r, 0)
                reinitalze_key(tc = self)
                r = deactivate_key(tc = self)
                self.assertNotEqual(r, 0)
                reinitalze_key(tc = self)
                if self.status[1] == "Trial":
                    check_status('Valid', 'Trial', tc = self)


    """
    Check the Key, accelerate and deaccelarte the device and 
    Verfy that  Professional/Enterprise/Datacenter License Works

    License Type   Capacity
    =======================
    Professional - SSD<=250GB
    Enterprise   - SSD<=500GB
    Datacenter   - SSD<=1TB
    """
    def test_2(self):
        for i in range(0, (len(LICENSE_KEYS))):
            logger.debug("===Testing %s LICENSE===" % self.license_type[i])
            reinitalze_key(tc = self)
            if self.status[1] == "Trial":
                check_status('Valid', 'Trial', tc = self)
            r = activate_key(LICENSE_KEYS["%s" % self.license_type[i]], tc = self)
            self.assertEqual(r, 0)
            reinitalze_key(tc = self)
            check_status('Valid', '%s' % self.license_type[i], tc = self)
            if self.license_type[i] == 'PROFESSIONAL':
                self.ssd_volume_1 = SSD_SIZE[1] 
                self.ssd_volume_2 = SSD_SIZE[2]
            elif self.license_type[i] == 'ENTERPRISE':
                self.ssd_volume_1 = SSD_SIZE[2] 
                self.ssd_volume_2 = SSD_SIZE[3]
            else:
                self.ssd_volume_1 = SSD_SIZE[3]
                self.ssd_volume_2 = SSD_SIZE[4]

            create_dmsetup(self.ssd_volume_1, self.ssd, tc = self)
            ssd = get_devicename('/dev/mapper/test', tc = self)
            self.ssd_volume = "/dev/%s" % ssd

            """
            Acceelrate the HDD volume with Optimum level of SSD capacity \
            provided to the Professional/Enterprise/Datacenter Users
            """
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self)

            if isdev_accelerated(self.primary_volume):
                deaccelerate_dev(self.primary_volume, tc = self)
            os.system('cachebox -l')
            delete_dmsetup(tc = self)

            """
            Acceelrate the HDD volume above Optimum level of SSD capacity \
            provided to Professional/Enterprise/Datacenter Users
            Testing with 500GB/1TB/2TB size of SSD respectively.
            """
            create_dmsetup(self.ssd_volume_2, self.ssd, tc = self)
            ssd = get_devicename('/dev/mapper/test', tc = self)
            self.ssd_volume = "/dev/%s" % ssd

            returncode = accelerate_dev(self.primary_volume, self.ssd_volume, \
                        4096, self, debug = True)
            self.assertNotEqual(returncode, 0)

            if isdev_accelerated(self.primary_volume):
                deaccelerate_dev(self.primary_volume, tc = self)
            os.system('cachebox -l')

            delete_dmsetup(tc = self)
            r = deactivate_key(tc = self)
            self.assertEqual(r, 0)
            reinitalze_key(tc = self)


    """
    accelerate the device and do some IO
    deactivate the license in between and 
    Checks the cachebox_stats
    """
    def test_3(self):
        for i in range(0, (len(LICENSE_KEYS))):
            logger.debug("===Testing %s LICENSE===" % self.license_type[i])
            reinitalze_key(tc = self)
            if self.status[1] == "Trial":
                check_status('Valid', 'Trial', tc = self)
            r = activate_key(LICENSE_KEYS["%s" % self.license_type[i]], tc = self)
            self.assertEqual(r, 0)
            reinitalze_key(tc = self)
            check_status('Valid', '%s' % self.license_type[i], tc = self)

            self.ssd_volume = random.choice(SSD_VOLUMES.keys()) 

            """
            Acceelrate the HDD volume with HDD and deactivate the license \
            when some IO is going on
            """
            accelerate_dev(self.primary_volume, self.ssd_volume, 4096, self)
            time.sleep(10)
            setpolicy_dev("fulldisk", self.primary_volume, None, tc = self)

            thread_1 = threading.Thread(target = do_dd, args = (self, self.primary_volume))
            thread_2 = threading.Thread(target = collect_cb_stats, args = (self, self.primary_volume))

            thread_1.start()
            thread_2.start()

            thread_1.join()
            thread_2.join()

            deaccelerate_dev(self.primary_volume, tc = self)
            deactivate_key(tc = self)
            reinitalze_key(tc = self)

if __name__ == '__main__':
    unittest.main(argv=["license.py"] + args)
