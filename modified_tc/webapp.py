import httplib2
import json
import os
import unittest
import urllib
import sqlite3
import sys
import threading
import time

sys.path.append("/usr/lib/cachebox/asm")
from common_utils import *
from threading import Thread
from cblog import *
from db import cdb
from db import ConfigDb

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

URL = 'http://%s:%s/cgi-bin' % (IP, PORT)

for member_name in dir(config):
	if not member_name.startswith("__"):
		globals()[member_name] = getattr(config, member_name)

class TestWebappAuth(CBQAMixin, unittest.TestCase):
    """
    Test the authentication of webapp
    """

    def setUp(self):
        super(TestWebappAuth, self).setUp()
        self.headers = {'Content-type': 'application/x-www-form-urlencoded'}
        self.startTime = time.time()

    def tearDown(self):
        super(TestWebappAuth, self).tearDown()
        t = time.time() - self.startTime

    def login(self, username, password):
        url = "%s/authenticate.py" % URL
        http = httplib2.Http()
        body = {'login': username, 'password': password, "__s": IP}
        response, content = http.request(url, 'POST', headers=self.headers, \
                                         body=urllib.urlencode(body))
        cookies = response['set-cookie']
        self.assertEqual(response['status'], "200")
        self.assertEqual(cookies.split("=")[0].strip(), "cachebox_%s" % IP)
        self.headers['Cookie'] = cookies

    def logout(self):
        url = "%s/logout.py" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'POST', headers=self.headers)
        self.assertEqual(response['status'], "302")
        self.headers['Cookie'] = ''

    def test_01(self):
        #
        # Basic test for login and logout
        #
        self.login(USER, PASSWORD)
        self.logout()

    def test_02(self):
        #
        # home.py without authentication
        #
        url = "%s/home.py" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "403")

    def test_03(self):
        #
        # home.py with authentication
        #
        self.login(USER, PASSWORD)
        url = "%s/home.py" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        self.logout()

    def test_04(self):
        #
        # check dashboard by getstats call
        #
        self.login(USER, PASSWORD)
        url = "%s/getstats.py" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = json.loads(content)
        memusage = content.get("mem")
        self.assertNotEqual(memusage, None)
        self.assertTrue(isinstance(memusage.get("pie"), list))
        self.assertNotEqual(memusage.get("total"), None)

    def test_05(self):
        #
        # check dashboard by getdetails call
        #
        self.login(USER, PASSWORD)
        url = "%s/getdetails.py" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = json.loads(content)
        memusage = content.get("mem")
        self.assertNotEqual(memusage, None)
        self.assertTrue(isinstance(memusage.get("pie"), list))
        self.assertNotEqual(memusage.get("total"), None)
        self.assertNotEqual(content.get('utc_offset'), None)
        self.assertNotEqual(content.get('system'), None)
        self.assertNotEqual(content.get('license'), None)
        license = content.get('license')
        self.assertNotEqual(license.get('status'), None)
        self.assertNotEqual(license.get('ltype'), None)
        self.assertNotEqual(license.get('days'), None)
        self.assertNotEqual(license.get('grace'), None)

    def test_06(self):
        #
        # check dashboard by getdetails call
        #
        self.login(USER, PASSWORD)
        url = "%s/getasms.py" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = json.loads(content)
        path = "/usr/lib/cachebox/asm/plugins"
        asm = [name for name in os.listdir(path)
               if os.path.isdir(os.path.join(path, name))]
        self.assertTrue(asm == content)

class TestWebValidateVolume(CBQAMixin, unittest.TestCase):
    """
    Test the volume stats is correctly gives values or not
    """

    def setUp(self):
        super(TestWebValidateVolume, self).setUp()
        self.headers = {'Content-type': 'application/x-www-form-urlencoded'}
        self.startTime = time.time()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(TestWebValidateVolume, self).tearDown()
        t = time.time() - self.startTime
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def login(self, username, password):
        url = "%s/authenticate.py" % URL
        http = httplib2.Http()
        body = {'login': username, 'password': password, "__s": IP}
        response, content = http.request(url, 'POST', headers=self.headers, \
                                         body=urllib.urlencode(body))
        cookies = response['set-cookie']
        self.assertEqual(response['status'], "200")
        self.assertEqual(cookies.split("=")[0].strip(), "cachebox_%s" % IP)
        self.headers['Cookie'] = cookies

    def logout(self):
        url = "%s/logout.py" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'POST', headers=self.headers)
        self.assertEqual(response['status'], "302")
        self.headers['Cookie'] = ''

    def testVolumeList(self):
        #
        # check volume list for first time in GUI
        #
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=volume&op=web_cbasm_list" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        #
        # ignore first 2 lines which contain status :OK
        #
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        components = cdb.getComponents({'asm':'volume'})
        self.assertEqual(len(components), len(content))

    def testVolumeStats(self):
        #
        # check volume getstats
        #
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=volume&op=getstats" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        #
        # If device is accelerated
        #
        components = cdb.getComponents({'accelerated':1, 'asm':'volume'})
        accelerated = content.get("accelerated")
        self.assertEqual(len(components), len(accelerated))

        for comp in components:
            part = filter(lambda accelerate: comp['uuid'] == accelerate['uuid'],\
                          accelerated)[0]
            self.assertNotEqual(part.get('gain_qps'), None)
            self.assertNotEqual(part.get('latencies'), None)
            self.assertNotEqual(part.get('cachehits'), None)
            self.assertNotEqual(part.get('monitor_percent'), None)

        self.assertNotEqual(content.get("accelerated"), None)
        self.logout()

    def testTpsValue(self):
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=volume&op=getstats" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        self.assertNotEqual(content.get('stats'), None)
        stats = content['stats']
        components = cdb.getComponents({"asm":"volume"})
        self.assertEqual(len(components), len(stats))
        for part in stats:
            self.assertNotEqual(part['stats'].get('tps'), None)

    def testAfterAccelerate(self):
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc=self)
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=volume&op=getstats" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        accelerated = content['accelerated']
        component = cdb.getComponent({'asm': 'volume', 'accelerated': 1})
        stats = cdb.getComponent({'asm_type': 'volume', \
                                  'uuid': component['uuid']}, 'ASM')
        self.assertEqual(len([component]), len(accelerated))
        part = accelerated[0]
        self.assertTrue(set(component).issubset(set(part)))
        deaccelerate_dev(self.primary_volume, tc=self)

    def testVolumeAttr(self):
        component = cdb.getComponent({'asm':'volume', 'device':self.primary_volume})
        private = json.loads(component['private'])
        self.assertNotEqual(private.get('mountpoint'), None)
        self.assertNotEqual(private.get('filesystem'), None)
        self.assertNotEqual(private.get('model'), None)
        #
        # after accelerate device new attribute has been added in private
        #
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc=self)
        primary = cdb.getComponent({'asm':'volume', 'device':self.primary_volume})
        ssd = cdb.getComponent({'asm':'volume', 'device':self.ssd_volume})
        primary_private = json.loads(primary['private'])
        ssd_private = json.loads(ssd['private'])
        self.assertEqual(ssd_private.get('primary'), primary['uuid'])
        self.assertEqual(primary_private.get('ssd'), ssd['uuid'])
        #
        # after letgo device acceleration attribute has been deleted in private
        #
        deaccelerate_dev(self.primary_volume, tc=self)
        primary = cdb.getComponent({'asm':'volume', 'device':self.primary_volume})
        ssd = cdb.getComponent({'asm':'volume', 'device':self.ssd_volume})
        self.assertEqual(ssd.get('primary'), None)
        self.assertEqual(primary.get('ssd'), None)

    def testIopsGain(self):
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc=self)
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=volume&op=getstats" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        accelerated = content['accelerated']
        part = accelerated[0]
        self.assertNotEqual(part['stats'].get('gain_iops'), None)
        acc_gain_iops = part['stats'].get('gain_iops')
        cmd = "dd if=%s of=/dev/zero bs=1M count=1000" % self.primary_volume
        os.system("%s > /dev/null" % cmd)
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        accelerated = content['accelerated']
        part = accelerated[0]
        self.assertNotEqual(part['stats'].get('gain_iops'), None)
        current_gain_iops = part['stats'].get('gain_iops')
        self.assertNotEqual(acc_gain_iops, current_gain_iops)
        deaccelerate_dev(self.primary_volume, tc=self)

class TestWebValidateMongodb(CBQAMixin, unittest.TestCase):
    """
    Test the authentication of webapp
    """

    def setUp(self):
        super(TestWebValidateMongodb, self).setUp()
        self.headers = {'Content-type': 'application/x-www-form-urlencoded'}
        self.startTime = time.time()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        skip = 0
        if not os.path.exists("/usr/lib/cachebox/asm/plugins/mongodb"):
            skip = 1
        else:
            cmd = ("service", "mongodb", "status")
            pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, \
                                  stderr=subprocess.PIPE)
            out, err = pr.communicate()
            if pr.returncode:
             skip = 1
            if not ("running" in out):
                skip = 1
        if skip:
            print "Skip Test cases. Need to start mongodb service and"\
                  "mongodb asm should install"
            self.skipTest("Need to start mongodb service and"\
                          "mongodb asm should install")
        self.primary_volume = cdb.getComponent({"asm":"mongodb"})['device']

    def tearDown(self):
        super(TestWebValidateMongodb, self).tearDown()
        t = time.time() - self.startTime
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def login(self, username, password):
        url = "%s/authenticate.py" % URL
        http = httplib2.Http()
        body = {'login': username, 'password': password, "__s": IP}
        response, content = http.request(url, 'POST', headers=self.headers, \
                                         body=urllib.urlencode(body))
        cookies = response['set-cookie']
        self.assertEqual(response['status'], "200")
        self.assertEqual(cookies.split("=")[0].strip(), "cachebox_%s" % IP)
        self.headers['Cookie'] = cookies

    def logout(self):
        url = "%s/logout.py" % URL
        http = httplib2.Http()

    def testMongodbList(self):
        #
        # check mongodb list for first time in GUI
        #
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=mongodb&op=web_cbasm_list" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        components = cdb.getComponents({'asm':'mongodb', 'type':'database'})
        # minus 1 for journal
        databases_stats = content['components']['databases']
        self.assertEqual(len(components), len(databases_stats))
        # for journal check
        journal = cdb.getComponent({'asm':'mongodb', 'type':'journal'})
        journal_stats = content['components']['journal']
        self.assertTrue(set(journal).issubset(set(journal_stats)))
        for comp in components:
            part = filter(lambda part: comp['uuid'] == part['uuid'],\
                          content['components']['databases'])
            if len(part):
                self.assertTrue(set(comp).issubset(set(part[0])))

    def testMongodbStats(self):
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=mongodb&op=getstats" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        #
        # If database or collection is accelerated
        #
        components = cdb.getComponents({'accelerated':1, 'asm':'mongodb'})
        accelerated = content.get("accelerated")
        self.assertEqual(len(components), len(accelerated))
        for comp in components:
            assertTrue(comp in accelerated)
        #
        # For stats of mongodb components
        #
        components = cdb.getComponents({'asm':'mongodb', 'type':'database'})
        for comp in components:
            part = filter(lambda part: comp['uuid'] == part['uuid'],\
                          content['components'])
            if len(part):
                self.assertTrue(set(comp).issubset(set(part[0])))

    def testQpsValues(self):
        #
        # check qps values is increased or not
        #
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=mongodb&op=getstats" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        qps_data = content['app']
        self.assertTrue(type(qps_data['qps']) is list)
        self.assertFalse(type(qps_data['qps_gain']) is None)
        #
        # check qps values is increased or not
        #
        oldqps = qps_data['qps'][0]
        time.sleep(60)
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        qps_data = content['app']
        newqps = qps_data['qps'][0]
        self.assertNotEqual(oldqps, newqps)

    def testAfterAccelerated(self):
        # suppose we accelerated journal, then accelerated list should not be empty,
        # it should be contain journal dictionary
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc=self)
        uid = cdb.getComponent({"asm":"mongodb", "type":"table"})["uuid"]
        cmd = "cbasm --mongodb --accelerate --uuid=%s" % uid
        pr = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, \
                             stderr=subprocess.PIPE)
        out, err = pr.communicate()
        self.assertEqual(pr.returncode, 0)
        time.sleep(60)
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=mongodb&op=getstats" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        component = cdb.getComponent({'accelerated':1, 'asm':'mongodb', \
                                        'type':'journal'})
        self.assertTrue(set(component).issubset(set(content['accelerated'][0])))
        cmd = "cbasm --mongodb --letgo --uuid=%s" % uid
        pr = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, \
                             stderr=subprocess.PIPE)
        out, err = pr.communicate()
        self.assertEqual(pr.returncode, 0)
        deaccelerate_dev(self.primary_volume, tc=self)


class TestWebValidateMysql(CBQAMixin, unittest.TestCase):
    """
    Test the authentication of webapp
    """

    def setUp(self):
        super(TestWebValidateMysql, self).setUp()
        self.headers = {'Content-type': 'application/x-www-form-urlencoded'}
        self.startTime = time.time()
        skip = 0
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

        if not os.path.exists("/usr/lib/cachebox/asm/plugins/mysql"):
            skip = 1
        else:
            cmd = ('service', 'mysql', 'status')
            pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = pr.communicate()
            if pr.returncode:
                skip = 1
            if not ("running" in out):
                skip = 1
        if skip:
            print "Skip Test cases. Need to start mysql service and" \
                  "mysql asm should install"
            self.skipTest("Need to start mysql service and" \
                          "mysql asm should install")
        self.primary_volume = cdb.getComponent({"asm":"mysql"})['device']

    def tearDown(self):
        super(TestWebValidateMysql, self).tearDown()
        t = time.time() - self.startTime
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)


    def login(self, username, password):
        url = "%s/authenticate.py" % URL
        http = httplib2.Http()
        body = {'login': username, 'password': password, "__s": IP}
        response, content = http.request(url, 'POST', headers=self.headers, \
                                         body=urllib.urlencode(body))
        cookies = response['set-cookie']
        self.assertEqual(response['status'], "200")
        self.assertEqual(cookies.split("=")[0].strip(), "cachebox_%s" % IP)
        self.headers['Cookie'] = cookies

    def logout(self):
        url = "%s/logout.py" % URL
        http = httplib2.Http()

    def testMysqlList(self):
        #
        # check mysql list for first time in GUI
        #
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=mysql&op=web_cbasm_list" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        components = cdb.getComponents({'asm':'mysql', 'type':'database'})
        self.assertEqual(len(components), len(content['components']))

    def testMysqlStats(self):
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=mysql&op=getstats" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        #
        # If database or collection is accelerated
        #
        components = cdb.getComponents({'accelerated':1, 'asm':'mysql'})
        accelerated = content.get("accelerated")
        self.assertEqual(len(components), len(accelerated))
        for comp in components:
            assertTrue(comp in accelerated)
        #
        # For stats of mysql components
        #
        components = cdb.getComponents({'asm':'mysql'})
        # minus 1 for skipping  qps data
        self.assertEqual(len(components), len(content['components'])-1)
        components = cdb.getComponents({'asm':'mysql', 'type':'database'})
        for comp in components:
            part = filter(lambda part: comp['uuid'] == part['uuid'],\
                          content['components'])
            if len(part):
                self.assertNotEqual(part[0]['stats'].get('hindex'), None)

    def testQpsValues(self):
        #
        # check qps values is increased or not
        #
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=mysql&op=getstats" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        qps_data = content['app']
        self.assertTrue(type(qps_data['qps']) is list)
        self.assertNotEqual(qps_data.get('qps_gain'), None)
        #
        # check qps values is increased or not
        #
        oldqps = qps_data['qps'][0]
        time.sleep(60)
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        qps_data = content['app']
        newqps = qps_data['qps'][0]
        self.assertNotEqual(oldqps, newqps)

    def testAfterAccelerated(self):
        # suppose we accelerated table, then accelerated list should not be empty,
        # it should be contain table related stats
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc=self)
        uid = cdb.getComponent({"asm":"mysql", "type":"table"})["uuid"]
        cmd = "cbasm --mysql --accelerate --uuid=%s" % uid
        pr = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, \
                             stderr=subprocess.PIPE)
        out, err = pr.communicate()
        self.assertEqual(pr.returncode, 0)
        time.sleep(120)
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=mysql&op=getstats" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        component = cdb.getComponent({'accelerated':1, 'asm':'mysql'})
        self.assertTrue(set(component).issubset(set(content['accelerated'][0])))
        cmd = "cbasm --mysql --letgo --uuid=%s" % uid
        pr = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, \
                             stderr=subprocess.PIPE)
        out, err = pr.communicate()
        self.assertEqual(pr.returncode, 0)
        deaccelerate_dev(self.primary_volume, tc=self)


class TestWebWithLoopDevice(CBQAMixin, unittest.TestCase):
    """
    Test the web skip loop devices and not affected for loop acceleration
    through command line
    """

    def setUp(self):
        super(TestWebWithLoopDevice, self).setUp()
        self.headers = {'Content-type': 'application/x-www-form-urlencoded'}
        self.startTime = time.time()
        skip = 0
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        #
        # create loop device loop0
        #
        cmd = "dd if=/dev/zero of=/tmp/tmp1lAM9Z bs=4096 count=30720"
        os.system("%s> /dev/null" % cmd)
        cmd = "losetup -f /tmp/tmp1lAM9Z --show"
        os.system("%s> /dev/null" % cmd)

    def tearDown(self):
        super(TestWebWithLoopDevice, self).tearDown()
        t = time.time() - self.startTime
        cmd = "losetup -d /dev/loop0"
        os.system("%s> /dev/null" % cmd)

    def login(self, username, password):
        url = "%s/authenticate.py" % URL
        http = httplib2.Http()
        body = {'login': username, 'password': password, "__s": IP}
        response, content = http.request(url, 'POST', headers=self.headers, \
                                         body=urllib.urlencode(body))
        cookies = response['set-cookie']
        self.assertEqual(response['status'], "200")
        self.assertEqual(cookies.split("=")[0].strip(), "cachebox_%s" % IP)
        self.headers['Cookie'] = cookies

    def logout(self):
        url = "%s/logout.py" % URL
        http = httplib2.Http()

    def testSkipLoopDeviceOnWeb(self):
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=volume&op=web_cbasm_list" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        loopdev = "/dev/loop0"
        part = filter(lambda part: part['device'] == loopdev,\
                          content)
        self.assertEqual(len(part), 0)
        accelerate_dev(loopdev, self.ssd_volume, "write-back", tc=self)
        deaccelerate_dev(loopdev, tc=self)

class TestMountPoints(CBQAMixin, unittest.TestCase):
    """
    Test the mount points of every volume is correctly display on web
    """

    def setUp(self):
        super(TestMountPoints, self).setUp()
        self.startTime = time.time()

    def tearDown(self):
        super(TestMountPoints, self).tearDown()
        t = time.time() - self.startTime

    def testMountPoints(self):
        elements = cdb.getComponents({"asm":"volume"})
        for element in elements:
            private = json.loads(element['private'])
            store_mount_point = private['mountpoint']
            cmd = "mount"
            pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, \
                                  stderr=subprocess.PIPE)
            out, err = pr.communicate()
            lines = out.split("\n")
            for line in lines:
                if line.split(" ")[0] == element['device']:
                    mount_point = line.split(" ")[2]
                    break
                else:
                    mount_point = "not mounted"
            self.assertEqual(store_mount_point, mount_point)

class TestCacheUsed(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(TestCacheUsed, self).setUp()
        self.headers = {'Content-type': 'application/x-www-form-urlencoded'}
        self.startTime = time.time()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())

    def tearDown(self):
        super(TestCacheUsed, self).tearDown()
        t = time.time() - self.startTime
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def login(self, username, password):
        url = "%s/authenticate.py" % URL
        http = httplib2.Http()
        body = {'login': username, 'password': password, "__s": IP}
        response, content = http.request(url, 'POST', headers=self.headers, \
                                         body=urllib.urlencode(body))
        self.assertEqual(response['status'], "200")
        cookies = response['set-cookie']
        self.assertEqual(cookies.split("=")[0].strip(), "cachebox_%s" % IP)
        self.headers['Cookie'] = cookies

    def logout(self):
        url = "%s/logout.py" % URL
        http = httplib2.Http()

    def testCacheUsed(self):
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc=self)
        self.login(USER, PASSWORD)
        url = "%s/asmcgi.py?app=volume&op=getstats" % URL
        http = httplib2.Http()
        response, content = http.request(url, 'GET', headers=self.headers)
        self.assertEqual(response['status'], "200")
        content = " ".join(content.split("\n")[2:])
        content = json.loads(content)
        accelerated = content['accelerated']
        if accelerated:
            statused = accelerated[0]['stats']['ssdused']
            statreads = accelerated[0]['stats']['ssdreads']
            self.assertTrue(statused >= 0)
            self.assertTrue(statreads >= 0)
        deaccelerate_dev(self.primary_volume, tc=self)

class TestDatabaseLockedError(CBQAMixin, unittest.TestCase):
    """
    Test database locked error
    """

    def setUp(self):
        super(TestDatabaseLockedError, self).setUp()
        self.startTime = time.time()
        self.CONFIG_FILE = "/etc/cachebox/cachebox2.db"

    def tearDown(self):
        super(TestDatabaseLockedError, self).tearDown()
        t = time.time() - self.startTime

    def MyThread1(self, component):
        i = 0
        while(i<5):
            i = i+1
            time.sleep(2)
            conn = sqlite3.connect(self.CONFIG_FILE)
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE ASM set " \
                              "stats=?," \
                              "asm_type=?," \
                              "device=? "\
                              "where (uuid=?)",
                          (component.get('stats'),
                           component.get('asm_type'),
                           component.get('device'),
                           component.get('uuid')
                           ))
            except sqlite3.OperationalError:
                self.MyThread1(component)

    def MyThread2(self, component):
        i = 0
        component['operation'] = "update"
        while(i< 5):
            cdb = ConfigDb()
            cdb.create_or_update(component, "ASM")
            i = i+1
            time.sleep(1)

    def test_database_lock(self):
        #
        # Basic test database locked error
        #
        component = cdb.getComponent({'asm_type':"volume"}, "ASM")
        component['stats'] = json.dumps(component['stats'])
        Thread(target = self.MyThread1, args = [component]).start()
        Thread(target = self.MyThread2, args= [component]).start()

if __name__ == '__main__':
       unittest.main(argv=["webapp.py"] + args)
