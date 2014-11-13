# copyright 2013 Cachebox, Inc. All rights reserved. This software
# is property of Cachebox, Inc and contains trade secrects,
# confidential & proprietary information. Use, disclosure or copying
# this without explicit written permission from Cachebox, Inc is
# prohibited.
#
# Author: Cachebox, Inc (sales@cachebox.com)
#
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
sys.path.append("/usr/lib/cachebox/asm")
from plugins.mongodb.mongodbutils import *
import platform
from stat import S_ISREG

from cblog import *
from common_utils import *
from layout import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
    if not member_name.startswith("__"):
        globals()[member_name] = getattr(config, member_name)

def do_sp(cmd):
    r = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                stderr = subprocess.PIPE, shell=True)
    out, err = r.communicate()
    return (r.returncode, out, err)
    
class Cbasm_utils(object):

    #chk btd and and return pid related to that
    @staticmethod
    def chk_btd(device, uuid, tc):
        cmd = ("ps -aef | grep -i '/etc/cachebox/server/btd.py --device=%s --uuid=%s start'\
               | grep -v grep" % (device, uuid))
        logger.debug(cmd)
        r, out, err = do_sp(cmd)
        logger.debug(out)
        tc.assertEqual(r, 0)


    @staticmethod
    def get_pid(device, uuid, tc):
        cmd = ("ps -aef | grep -i '/etc/cachebox/server/btd.py --device=%s --uuid=%s start'\
               | grep -v grep" % (device, uuid))
        logger.debug(cmd)
        r, out, err = do_sp(cmd)
        out = out.strip('\n').split('\n')
        for i in out:
            a = i.split()
        pid = a[1]
        return pid

    #Return UUID of device and flag
    @staticmethod
    def get_uuid_flag(device):
        cmd = "cbasm --list | grep -i '%s' | grep -v grep" % device
        ss = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE)
        out = ss.communicate()[0].strip('\n').split('\n')
        for i in out:
            a = i.split()
        return[a[0], a[-3]]


    #Return count of admission bitmap
    @staticmethod
    def chk_bitmapcount(volume, tc):
        cmd = ("cachebox -a 15 -d %s | grep -i ' 1' | wc -l" % volume)
        r, out, err = do_sp(cmd)
        logger.debug("Admit map: %s" % out)
        return out


    @staticmethod
    def islvm_accelerated(device):
         cmd = "cachebox -l | grep %s > /dev/null" % device
         r = os.system(cmd)
         return (1 if r == 0 else 0)


    @staticmethod
    def chk_lvm_inconfig(device):
        try:
            ss = os.readlink(device)
            return "True"
        except:
            device_detail = device.split('/')[-1]
            return os.path.exists("/sys/class/block/%s/dm" % device_detail)


    @staticmethod
    def create_database(ip, dbname, collectionname, no_of_rows, start):
        str1 = "echo \"for (var i = %s; i <= %s; i++) db.%s.insert({x:i}, {y:i}, {z:i})\" " \
               % (start, no_of_rows, collectionname)
        cmd="%s|mongo %s/%s" % (str1, ip, dbname)
        os.system("%s >/dev/null" % cmd)
        logger.debug(cmd)


    @staticmethod
    def cbasm_list_with_grep(search_value):
        o = subprocess.Popen("cbasm --list", shell=True, stdout=subprocess.PIPE, \
                             stderr=subprocess.PIPE).communicate()
        cmd = "cbasm --mongodb --list | grep -w %s" % search_value
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, \
                             stderr=subprocess.PIPE)
        out, err = o.communicate()
        logger.debug(cmd)
        return o.returncode


    @staticmethod
    def drop_database(ip, dbname):
        if os.system("cbasm --list --mongodb >/dev/null"):
            return
        cmd = "echo \"db.dropDatabase()\" | mongo %s/%s " % (ip, dbname)
        os.system("%s>/dev/null"%cmd)
        os.system("cbasm --list --mongodb >/dev/null")
        logger.debug(cmd)



chk_btd = Cbasm_utils.chk_btd
chk_bitmapcount = Cbasm_utils.chk_bitmapcount
islvm_accelerated = Cbasm_utils.islvm_accelerated
chk_lvm_inconfig = Cbasm_utils.chk_lvm_inconfig
get_uuid_flag = Cbasm_utils.get_uuid_flag
get_pid = Cbasm_utils.get_pid
create_database =  Cbasm_utils.create_database
cbasm_list_with_grep = Cbasm_utils.cbasm_list_with_grep
drop_database = Cbasm_utils.drop_database

ASM_TYPE = 'mongodb'
PORT = "27017" 
IP = "127.0.0.1"
SKIP_DB = (
    'test',    
    )

class MONGODBObject(object):

    def __init__(self, name):

	os.system("cbasm --list --mongodb>/dev/null")
        time.sleep(1)
        component = cdb.getComponent({'name':name})
        self.component = component
        
        if component is None:
            raise ComponentError("%s: no such component" % name)

        primary = cdb.getComponent({
                'device':component.get('device'),
                'type':'primary'
                })
        self.primary = primary
        if primary is None:
            raise ComponentError("%s: no such component" %
                                 component.get('device'))
        
        return


class MongoDBTestUtil(MONGODBMixin):
    def __init__(self):

        self.port = PORT
        self.ip = IP
        self.dbpath = None
        self.index_only_acc_supported = 0
        self.nojournal = "False"
    
        if "Ubuntu" in platform.dist():
            conf = open("/etc/mongodb.conf").readlines()
        elif "centos" in platform.dist() or "redhat" in platform.dist():
            conf = open("/etc/mongod.conf").readlines()

        for line in conf:
            if line.strip().startswith("port"):
                self.port = line.split("=")[1].strip()
            if line.strip().startswith("bind_ip"):
                self.ip = line.split("=")[1].strip()
            if line.strip().startswith("dbpath"):
                self.dbpath = line.split("=")[1].strip()
            if line.strip().startswith("#CA_MODIFIED_MONGO_SERVER=1"):
                self.index_only_acc_supported = 1
            if line.strip().startswith("nojournal"):
                self.nojournal = line.split("=")[1].strip('\n')
    
        return
    
    def Runcmd(self,runcmd):
        cmd =  ["echo %s | mongo --quiet %s:%s" %(runcmd,self.ip, self.port) ]
        print cmd
        p1 = subprocess.Popen(cmd, shell=True, 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p1.communicate()

        return out,err,p1.returncode


class TestMongoDB(CBQAMixin, unittest.TestCase):


    def setUp(self):
        super(TestMongoDB, self).setUp()
        self.startTime = time.time()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.MongoDB=MongoDBTestUtil()

    def tearDown(self):
        super(TestMongoDB, self).tearDown()
        drop_database(self.MongoDB.ip, "test123")
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def ResetMongoDB(self):
        cmd = [
            "stop",
            "mongodb"
            ]
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE)
        out,err = process_1.communicate()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)
        do_unmount(self.MongoDB.dbpath, self)
        do_mkfs(self.primary_volume, "default",self)

        do_mount(self.primary_volume, self.MongoDB.dbpath, self)
        cmd = "chown -R mongodb:mongodb %s" % (self.MongoDB.dbpath)
        os.system(cmd)
        logger.debug(cmd)
        
        cmd = "rm -rf %s/*" % (self.MongoDB.dbpath)
        os.system(cmd)
        cmd = [
            "start",
            "mongodb"
            ]
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE).communicate()
        time.sleep(5)

    def test_1(self):
        self.ResetMongoDB()

        time.sleep(5)
        cmd="echo \"for (i=1; i<=250; i++) db.testData4321.insert( { x : i }, { y : i }, { y : i } )\"|mongo %s/test123" % self.MongoDB.ip
        os.system("%s>/dev/null" %cmd)
        logger.debug(cmd)
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc = self)
        volume = get_devicename(self.primary_volume, self)

        uuid_flag = get_uuid_flag(self.primary_volume)
        mongo=MongoDBTestUtil()

        dbname = "test123"
        db = MONGODBObject(dbname)
        uid=db.component.get('uuid')

        cmd="cbasm --mongodb --accelerate --uuid=%s"%uid
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(process.returncode, 0)
        cmd="cbasm --mongodb --letgo --uuid=%s"%uid
        os.system(cmd)
        logger.debug(cmd)
        
        
    def test_2(self):
        self.ResetMongoDB()

        time.sleep(5)
        cmd="echo \"for (var i = 1; i <= 250; i++) db.testData4321.insert( { x : i }, { y : i }, { y : i } )\"|mongo %s/test123" % self.MongoDB.ip
        os.system("%s>/dev/null" %cmd)
        logger.debug(cmd)
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc = self)
        volume = get_devicename(self.primary_volume, self)

        uuid_flag = get_uuid_flag(self.primary_volume)
        mongo=MongoDBTestUtil()

        component = cdb.getComponent({'asm':'mongodb'})
        db = MONGODBObject("test123")

        col_obj = cdb.getComponent({
                      'name':'testData4321',
                      'type':'collection',
                      })

        
        cmd="cbasm --mongodb --accelerate --uuid=%s"%col_obj.get('uuid')
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(process.returncode, 0)
        cmd="cbasm --mongodb --letgo --uuid=%s"%col_obj.get('uuid')
        os.system(cmd)
        logger.debug(cmd)

# Check Size is increases or not after adding new rows in collection by using --list.
class TestMongoDBChangedSize(CBQAMixin, unittest.TestCase):


    def setUp(self):
        super(TestMongoDBChangedSize, self).setUp()
        self.startTime = time.time()
        self.MongoDB=MongoDBTestUtil()
	self.dbname = "testdb"
        self.collectionname = "testData"
        if (self.MongoDB.get_service_status() == 1):
            print "Skip Test case. Need to start mongodb service"
            self.skipTest("Need to start mongodb service")
        

    def tearDown(self):
        super(TestMongoDBChangedSize, self).tearDown()
        drop_database(self.MongoDB.ip, self.dbname)

    def test1(self):

        time.sleep(5)
        #create database with collection
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "250", "1")
       
        #check collection size which is stored in list database
        cmd = "cbasm --mongodb --list | grep -w %s | awk {'print $7$8'}" % self.collectionname
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out1, err = o.communicate()
        logger.debug(cmd)
        
        #increase collection size by adding some new rows
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, 25000, "251")
        
        #again check size in list database, it should be increases.
        cmd = "cbasm --mongodb --list | grep -w %s | awk {'print $7$8'}" % self.collectionname
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = o.communicate()
        logger.debug(cmd)
        self.assertNotEqual(out1, out)


# Test entry from --list is deleted or not after any database or collection is deleted
class TestDeletedObjectInList(CBQAMixin, unittest.TestCase):


    def setUp(self):
        super(TestDeletedObjectInList, self).setUp()
        self.startTime = time.time()
        self.MongoDB=MongoDBTestUtil()
        self.dbname = "testdb"
        self.collectionname = "testData"
        if (self.MongoDB.get_service_status() == 1):
            print "Skip Test case. Need to start mongodb service"
            self.skipTest("Need to start mongodb service")
        drop_database(self.MongoDB.ip, self.dbname)

    def tearDown(self):
        super(TestDeletedObjectInList, self).tearDown()

    def test_delete_db_from_list(self):

        time.sleep(5)

        # Create database with collection.
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "250", "1")

        # Check database and collection entry is added in --list or not
        returncode = cbasm_list_with_grep(self.dbname)
        self.assertEqual(returncode, 0)

        returncode = cbasm_list_with_grep(self.collectionname)
        self.assertEqual(returncode, 0)

        # Delete database
        drop_database(self.MongoDB.ip, self.dbname)

        # Check database entry is deleted from --list
        returncode = cbasm_list_with_grep(self.dbname)
        self.assertNotEqual(returncode, 0)

        # Check db dependant collection entry also deleted from --list
        returncode = cbasm_list_with_grep(self.collectionname)
        self.assertNotEqual(returncode, 0)


    def test_delete_collection_from_list(self):

        time.sleep(5)
        # Create database with collection.
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "250", "1")

        # Check database and collection entry is added in --list or not
        returncode = cbasm_list_with_grep(self.dbname)
        self.assertEqual(returncode, 0)

        returncode = cbasm_list_with_grep(self.collectionname)
        self.assertEqual(returncode, 0)

        #Delete only collection not database
        cmd="echo \"db.%s.drop()\"|mongo %s/%s" % (self.collectionname, self.MongoDB.ip, self.dbname)
        os.system("%s>/dev/null" % cmd)
        logger.debug(cmd)

        # Now check --list contain only database entry not collection.
        returncode = cbasm_list_with_grep(self.dbname)
        self.assertEqual(returncode, 0)

        returncode = cbasm_list_with_grep(self.collectionname)
        self.assertNotEqual(returncode, 0)


class TestMongoDBJournal(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestMongoDBJournal, self).setUp()
        self.startTime = time.time()
        self.MongoDB=MongoDBTestUtil()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        if (self.MongoDB.get_service_status() == 1):
            print "Skip Test case. Need to start mongodb service"
            self.skipTest("Need to start mongodb service")

    def tearDown(self):
        super(TestMongoDBJournal, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_journal_enable(self):
        #check if journal is enable, --list should contain journal entry
        if self.MongoDB.nojournal == "True" or self.MongoDB.nojournal == "true":
            returncode = cbasm_list_with_grep("journal")
            self.assertNotEqual(returncode, 0)
        #check if journal is disable, --list should not contain journal entry
        elif self.MongoDB.nojournal == "False" or self.MongoDB.nojournal == "false":
            returncode = cbasm_list_with_grep("journal")
            self.assertEqual(returncode, 0)
        #By default journal is enable.
        else:
            returncode = cbasm_list_with_grep("journal")
            self.assertEqual(returncode, 0)
           
       
    def test_changed_journal_state(self):
        # if journal entry is present in --list remove journal from mongodb and
        # check journal entry should delete from --list
        if self.MongoDB.nojournal == "False" or self.MongoDB.nojournal == "false":
            returncode = cbasm_list_with_grep("journal")
            self.assertEqual(returncode, 0)

            cmd = [
                    "stop",
                    "mongodb"
                  ]
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                                          stderr = subprocess.PIPE).communicate()
        
            if "Ubuntu" in platform.dist():
                conf = open("/etc/mongodb.conf", "r")
            elif "centos" in platform.dist() or "redhat" in platform.dist():
                conf = open("/etc/mongod.conf", "r")
        
            lines = conf.readlines()
            conf.close()
       
            # change in conf file with adding nojournal=true flag, which disable journal.

            if "Ubuntu" in platform.dist():
                conf = open("/etc/mongodb.conf", "w")
            elif "centos" in platform.dist() or "redhat" in platform.dist():
                conf = open("/etc/mongod.conf", "w")
            for line in lines:
                if not (line.startswith("nojournal=False") or \
                         line.startswith("nojournal=false")):
                    conf.write(line)
            conf.write("nojournal=true\n")
            conf.close()

            self.MongoDB=MongoDBTestUtil()

            cmd = "rm -rf /etc/cachebox/cachebox*db"
            os.system(cmd)
            do_unmount(self.MongoDB.dbpath, self)

            do_mount(self.primary_volume, self.MongoDB.dbpath, self)
            os.system("rm -rf %s/journal" % self.MongoDB.dbpath)
            logger.debug("rm -rf %s/journal" % self.MongoDB.dbpath)
        
            cmd = "chown -R mongodb:mongodb %s"%(self.MongoDB.dbpath)
            os.system(cmd)
            logger.debug(cmd)
   
            cmd = [
                    "start",
                    "mongodb"
                  ]
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                        stderr = subprocess.PIPE).communicate()
            time.sleep(5)
            # after disabling journal, it's entry should deleted from --list
            returncode = cbasm_list_with_grep("journal")
            self.assertNotEqual(returncode, 0)

        # if journal not present in mongodb add into it and check in --list 
        if self.MongoDB.nojournal == "True" or self.MongoDB.nojournal == "true":
            returncode = cbasm_list_with_grep("journal")
            self.assertNotEqual(returncode, 0)

            cmd = [
                    "stop",
                    "mongodb"
                  ]
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                                          stderr = subprocess.PIPE).communicate()
        
            if "Ubuntu" in platform.dist():
                conf = open("/etc/mongodb.conf", "r")
            elif "centos" in platform.dist() or "redhat" in platform.dist():
                conf = open("/etc/mongod.conf", "r")
        
            lines = conf.readlines()
            conf.close()

            # change in conf file with removing nojournal flag, which enable journal.
            if "Ubuntu" in platform.dist():
                conf = open("/etc/mongodb.conf", "w")
            elif "centos" in platform.dist() or "redhat" in platform.dist():
                conf = open("/etc/mongod.conf", "w")
            for line in lines:
                if not (line.startswith("nojournal=True") or \
                         line.startswith("nojournal=true")):
                    conf.write(line)
            conf.close()

            self.MongoDB=MongoDBTestUtil()

            cmd = "rm -rf /etc/cachebox/cachebox*db"
            os.system(cmd)
            do_unmount(self.MongoDB.dbpath, self)

            do_mount(self.primary_volume, self.MongoDB.dbpath, self)
        
            cmd = "chown -R mongodb:mongodb %s"%(self.MongoDB.dbpath)
            os.system(cmd)
            logger.debug(cmd)
   
            cmd = [
                    "start",
                    "mongodb"
                  ]
            logger.debug(cmd)
            process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                        stderr = subprocess.PIPE).communicate()
            time.sleep(10)
            # after disabling journal, it's entry should add in --list
            returncode = cbasm_list_with_grep("journal")
            self.assertEqual(returncode, 0)

    def test_journal_acceleration(self):

        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc = self)
        volume = get_devicename(self.primary_volume, self)
        cmd = "cbasm --list --mongodb | grep -w journal | awk {'print $6'}"
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        uid = out.strip()

	cmd="cbasm --mongodb --accelerate --uuid=%s" % uid
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(process.returncode, 0)

        # Get journal corrosponding regions using cbfacc command compare it with marked regions.
        file_regions_cbfacc = []
        cmd = "cbfacc -n -d %s -o file=%s/%s" % (self.primary_volume, self.MongoDB.dbpath, "journal")
        p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = p1.communicate()
        file_regions_cbfacc.extend(out.split(","))
        file_regions_cbfacc =  map(int, filter(None, file_regions_cbfacc))
        file_regions_cbfacc.sort()
        cmd = "cachebox -a 15 -d %s | grep ' 1'| awk {'print $1'}" % self.primary_volume
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = map(int, out.split())
        out.sort()
        self.assertEqual(out, file_regions_cbfacc)
        cmd="cbasm --mongodb --letgo --uuid=%s" % uid
        logger.debug(cmd)
        os.system(cmd)

        deaccelerate_dev(self.primary_volume, tc=self)


class TestMongoDBIndexInList(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestMongoDBIndexInList, self).setUp()
        self.startTime = time.time()
        self.MongoDB=MongoDBTestUtil()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.dbname = "TestData"
        self.collectionname = "test123"

        if (self.MongoDB.index_only_acc_supported == 0):
            self.skipTest("Need to set #CA_MODIFIED_MONGO_SERVER = 1 in mongodb.conf file")

    def tearDown(self):
        super(TestMongoDBIndexInList, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_system_index_in_list(self):
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "250", "1")
        # Check database and collection entry is added in --list or not
        returncode = cbasm_list_with_grep("system.indexes")
        self.assertEqual(returncode, 0)
        #Check collection index should also added in --list
        returncode = cbasm_list_with_grep("%s.idx" % self.collectionname)
        self.assertEqual(returncode, 0)


    def test_index_size(self):
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "250", "1")

        # Check database and collection entry is added in --list or not
        returncode = cbasm_list_with_grep("system.indexes")
        self.assertEqual(returncode, 0)
        
        cmd = "cbasm --mongodb --list | grep -w 'system.indexes' | awk {'print $7$8'}" 
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out1, err = o.communicate()
        logger.debug(cmd)

        cmd = "cbasm --mongodb --list | grep -w '%s.idx' | awk {'print $7$8'}" % self.collectionname
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_index1, err = o.communicate()
        logger.debug(cmd)

	# Just increased size of database.
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "2500", "251")

        cmd = "cbasm --mongodb --list | grep -w 'system.indexes' | awk {'print $7$8'}" 
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = o.communicate()
        logger.debug(cmd)

        self.assertNotEqual(out1, out)

        cmd = "cbasm --mongodb --list | grep -w '%s.idx' | awk {'print $7$8'}" % self.collectionname
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_index, err = o.communicate()
        logger.debug(cmd)

        self.assertNotEqual(out_index, out_index1)


#check cbasm --list --mongodb should not return output if MongoDBService has been stopped
class TestMongoDBService(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestMongoDBService, self).setUp()
        self.startTime = time.time()
        self.MongoDB=MongoDBTestUtil()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.dbname = "TestData"
        self.collectionname = "test123"

    def tearDown(self):
        super(TestMongoDBService, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_mongodb_service_stop(self):
        cmd = "cbasm --list --mongodb"
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out1, err = process.communicate()
        logger.debug(cmd)
        cmd = [
               "stop",
               "mongodb"
              ]
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                                          stderr = subprocess.PIPE).communicate()
	logger.debug(cmd)
        cmd = "cbasm --list --mongodb"
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertNotEqual(out1, out)
        cmd = [
               "start",
               "mongodb"
              ]
        logger.debug(cmd)
        time.sleep(10)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                                          stderr = subprocess.PIPE).communicate()
        logger.debug(cmd)
        cmd = "cbasm --list --mongodb"
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(out1, out)

if __name__ == '__main__':
    unittest.main(argv=["mongodb_unit_tests.py"] + args)
