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

    #Return UUID of device and flag
    @staticmethod
    def get_uuid_flag(device):
        cmd = "cbasm --list | grep -i '%s' | grep -v grep" % device
        ss = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE)
        out = ss.communicate()[0].strip('\n').split('\n')
        for i in out:
            a = i.split()
        return[a[0], a[-3]]

    @staticmethod
    def create_database(ip, dbname, collectionname, no_of_rows, start):
        str1 = "echo \"for (var i = %s; i <= %s; i++) db.%s.insert({entry:i, value1:i, value2:i, value3:i}, {fsync:true})\" " \
               % (start, no_of_rows, collectionname)
        cmd="%s|mongo --quiet %s/%s" % (str1, ip, dbname)
        os.system("%s > /dev/null" % cmd)
	time.sleep(10)
        os.system("cbasm --mongodb --list > /dev/null")
        logger.debug(cmd)

    @staticmethod
    def cbasm_list_with_grep(search_value):
        os.system("cbasm --list > /dev/null")
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
        os.system("%s > /dev/null" % cmd)
        logger.debug(cmd)
        os.system("cbasm --list --mongodb >/dev/null")

    @staticmethod
    def read_btddb_using_sqlite3(uuid_flag):
        import sqlite3
        filename = "/var/log/cachebox/%s-heatmap.db" % uuid_flag[1]
        conn = sqlite3.connect(filename)
        c = conn.cursor()
        c.execute("SELECT * from heatmap")
        rows = c.fetchall()
        region_btd =  [r for r, t, a in rows]
        c.close()
        return region_btd

    @staticmethod
    def add_syncdelay(ip, dbname):
        cmd = "echo \"db.getSiblingDB(\"admin\").runCommand({setParameter:1,syncdelay:5})\" | mongo %s/%s " % (ip, dbname)
        os.system("%s > /dev/null" % cmd)

    @staticmethod
    def change_duration_regionmark(uuid_flag):
        import sqlite3
        filename = "/var/log/cachebox/%s-heatmap.db" % uuid_flag
        conn = sqlite3.connect(filename)
        c = conn.cursor()
        c.execute("update config set mon_interval=0")
        c.close()
        return


get_uuid_flag = Cbasm_utils.get_uuid_flag
create_database =  Cbasm_utils.create_database
cbasm_list_with_grep = Cbasm_utils.cbasm_list_with_grep
drop_database = Cbasm_utils.drop_database
read_btddb_using_sqlite3 = Cbasm_utils.read_btddb_using_sqlite3
add_syncdelay = Cbasm_utils.add_syncdelay
change_duration_regionmark = Cbasm_utils.change_duration_regionmark

ASM_TYPE = 'mongodb'
PORT = "27017" 
IP = "127.0.0.1"
SKIP_DB = (
    'test',    
    )

class MONGODBObject(object):

    def __init__(self, name):

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
        self.replSet = False
    
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
            if line.strip().startswith("replSet"):
                self.replSet = True
    
        return
    
    def Runcmd(self,runcmd):
        cmd =  ["echo %s | mongo --quiet %s:%s" %(runcmd,self.ip, self.port) ]
        print cmd
        p1 = subprocess.Popen(cmd, shell=True, 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p1.communicate()

        return out,err,p1.returncode


class TestMongoDBDatabase(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestMongoDBDatabase, self).setUp()
        self.startTime = time.time()
        self.MongoDB=MongoDBTestUtil()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.dbname = "TestData"
        self.collectionname = "test123"
        self.collectionname1 = "test321"
        add_syncdelay(self.MongoDB.ip, self.dbname)

    def tearDown(self):
        super(TestMongoDBDatabase, self).tearDown()
        drop_database(self.MongoDB.ip, self.dbname)
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    # Check correct regions are monitoring by btd.
    def test_mongodb_region_db(self):
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc = self)
        uuid_flag = get_uuid_flag(self.primary_volume)
        # Create Database with 2 collections.
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "250", "1")
        create_database(self.MongoDB.ip, self.dbname, self.collectionname1, "250", "1")
        # Accelerate Database
        db = MONGODBObject(self.dbname)
        uid=db.component.get('uuid')

        cmd="cbasm --mongodb --accelerate --uuid=%s" % uid
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(process.returncode, 0)

        #Get region map of database
        mongodb = MongoDb()
        mongodb.device = self.primary_volume
        mongodb.dbname = self.dbname
        ret, regions = mongodb.get_regions_map()
        regions = map(int, regions)
        cmd = "ls %s | grep '%s.*'" % (self.MongoDB.dbpath, self.dbname)
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = o.communicate()
        filenames = out.split()

        # Get corrosponding regions of db files using cbfacc command.
        file_regions_cbfacc = []
        for filename in filenames:
            cmd = "cbfacc -n -d %s -o file=%s/%s" % (self.primary_volume, self.MongoDB.dbpath, filename)
            p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            out, err = p1.communicate()
            file_regions_cbfacc.extend(out.split(","))
        file_regions_cbfacc =  map(int, filter(None, file_regions_cbfacc))
        regions.sort()
        file_regions_cbfacc.sort()

        self.assertEqual(len(regions), len(file_regions_cbfacc))
        self.assertEqual(regions, file_regions_cbfacc)

        do = MONGODBObject(self.dbname)
        component = do.component
        self.assertEqual(int(component['rmap']), len(regions))
        # Verifying region corresponding to database given to btd for monitoring
        region_btd = read_btddb_using_sqlite3(uuid_flag)
        self.assertEqual(len(region_btd), len(regions))

        cmd="cbasm --mongodb --letgo --uuid=%s" % uid
        os.system(cmd)
        logger.debug(cmd)
        
        drop_database(self.MongoDB.ip, self.dbname)
        deaccelerate_dev(self.primary_volume, tc=self)

    def test_mongodb_marked_region_db(self):
        mongodb = MongoDb()
        mongodb.device = self.primary_volume
        mongodb.dbname = self.dbname
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc = self)
        uuid_flag = get_uuid_flag(self.primary_volume)
        # Create Database with 2 collections.
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "250", "1")
        create_database(self.MongoDB.ip, self.dbname, self.collectionname1, "250", "1")

        # Accelerate Database
        db = MONGODBObject(self.dbname)
        uid=db.component.get('uuid')
        cmd="cbasm --mongodb --accelerate --uuid=%s" % uid
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(process.returncode, 0)
        change_duration_regionmark(uuid_flag[1])

        #Get region map of database
        ret, regions = mongodb.get_regions_map()
        old_regions = map(int, regions)

        ip = self.MongoDB.ip
        dbname = self.dbname
        for i in range (1, 100):
            for entry in [100, 1, 250]:
                cmd = "echo \" db.test123.find({entry : %d)\"| mongo %s/%s" %\
                   (entry, ip, dbname)
                os.system("%s > /dev/null" % cmd)
            for entry in [100, 1, 250]:
                cmd = "echo \" db.test321.find({entry : %d)\"| mongo %s/%s" %\
                   (entry, ip, dbname)
                os.system("%s > /dev/null" % cmd)

        time.sleep(5)

        cmd = "cachebox -a 15 -d %s | grep ' 1'| awk {'print $1'}" % self.primary_volume
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = map(int, out.split())
        logger.debug("region=%s has been marked" % out)
        self.assertTrue(set(out).issubset(set(old_regions)))

        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "10000", "251")
        create_database(self.MongoDB.ip, self.dbname, "test100", "10000", "1")
        create_database(self.MongoDB.ip, self.dbname, "test1", "10000", "1")
        #Get region map of database
        ret, regions = mongodb.get_regions_map()
        new_regions = map(int, regions)
        self.assertTrue(set(old_regions).issubset(set(new_regions)))
        cmd = "cachebox -a 15 -d %s | grep ' 1'| awk {'print $1'}" % self.primary_volume
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = map(int, out.split())
        logger.debug("region=%s has been marked" % out)
        self.assertTrue(set(out).issubset(set(new_regions)))
        cmd="cbasm --mongodb --letgo --uuid=%s" % uid
        os.system(cmd)
        logger.debug(cmd)
 
        drop_database(self.MongoDB.ip, self.dbname)
        deaccelerate_dev(self.primary_volume, tc=self)


class TestMongoDBCollection(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestMongoDBCollection, self).setUp()
        self.startTime = time.time()
        self.MongoDB=MongoDBTestUtil()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.dbname = "TestData"
        self.collectionname = "test123"
        self.collectionname1 = "test321"
        add_syncdelay(self.MongoDB.ip, self.dbname)

    def tearDown(self):
        super(TestMongoDBCollection, self).tearDown()
        drop_database(self.MongoDB.ip, self.dbname)
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_mongodb_region_collection(self):
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-through", tc = self)
        # Create Database with 2 collections.
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "1", "1")
        create_database(self.MongoDB.ip, self.dbname, self.collectionname1, "1", "1")
        # Accelerate Database
        uuid_flag = get_uuid_flag(self.primary_volume)
        db = MONGODBObject(self.collectionname)
        uid=db.component.get('uuid')

        cmd="cbasm --mongodb --accelerate --uuid=%s" % uid
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(process.returncode, 0)

        #Get region map of collection
        mongocol = MongoCol()
        mongocol.device = self.primary_volume
        mongocol.dbname = self.dbname
        mongocol.colname = self.collectionname
        ret, regions = mongocol.get_regions_map()

        cmd = "ls %s | grep '%s.*'" % (self.MongoDB.dbpath, self.dbname)
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = o.communicate()
        filenames = out.split()

        # Get corrosponding regions of db files using cbfacc command.
        file_regions_cbfacc = []
        for filename in filenames:
            cmd = "cbfacc -n -d %s -o file=%s/%s" % (self.primary_volume, self.MongoDB.dbpath, filename)
            p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            out, err = p1.communicate()
            file_regions_cbfacc.extend(out.split(","))
        file_regions_cbfacc =  map(int, filter(None, file_regions_cbfacc))
        regions.sort()
        file_regions_cbfacc.sort()

        self.assertNotEqual(len(regions), len(file_regions_cbfacc))
        self.assertNotEqual(regions, file_regions_cbfacc)

        do = MONGODBObject(self.collectionname)
        component = do.component

        self.assertEqual(int(component['rmap']), len(regions))
       
        # Verifying region corresponding to database given to btd for monitoring
        region_btd = read_btddb_using_sqlite3(uuid_flag)
        self.assertEqual(len(region_btd), len(regions))
        cmd="cbasm --mongodb --letgo --uuid=%s" % uid
        os.system(cmd)
        logger.debug(cmd)

        drop_database(self.MongoDB.ip, self.dbname)
        deaccelerate_dev(self.primary_volume, tc=self)


    def test_mongodb_collection(self):
        mongodb = MongoCol()
        mongodb.device = self.primary_volume
        mongodb.dbname = self.dbname
        mongodb.colname = self.collectionname

        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc = self)
        uuid_flag = get_uuid_flag(self.primary_volume)
        # Create Database with 2 collections.
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "250", "1")
        create_database(self.MongoDB.ip, self.dbname, self.collectionname1, "250", "1")
        # Accelerate only one Collection not other.
        db = MONGODBObject(self.collectionname)
        uid=db.component.get('uuid')

        cmd="cbasm --mongodb --accelerate --uuid=%s" % uid
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(process.returncode, 0)
        change_duration_regionmark(uuid_flag[1])

        #Get region map of collection1
        ret, regions = mongodb.get_regions_map()
        acc_regions = map(int, regions)

        # Get of other collection region map
        mongodb1 = MongoCol()
        mongodb1.device = self.primary_volume
        mongodb1.colname = self.collectionname1
        ret, regions = mongodb.get_regions_map()
        nonacc_regions = map(int, regions)

        do = MONGODBObject(self.collectionname)
        component = do.component
        self.assertNotEqual(component['rmap'], len(regions))

        for i in range (1, 1000):
            cmd = "echo \" db.test123.find({entry : 100})\"| mongo %s/%s" % (self.MongoDB.ip, self.dbname)
            os.system("%s > /dev/null" % cmd)
            cmd = "echo \" db.test123.find({entry : 1})\"| mongo %s/%s" % (self.MongoDB.ip, self.dbname)
            os.system("%s > /dev/null" % cmd)
            cmd = "echo \" db.test123.find({entry : 250})\"| mongo %s/%s" % (self.MongoDB.ip, self.dbname)
            os.system("%s > /dev/null" % cmd)
            cmd = "echo \" db.test123.find({entry : 134})\"| mongo %s/%s" % (self.MongoDB.ip, self.dbname)
            os.system("%s > /dev/null" % cmd)
            cmd = "echo \" db.test123.find({entry : 34})\"| mongo %s/%s" % (self.MongoDB.ip, self.dbname)
            os.system("%s > /dev/null" % cmd)
        time.sleep(5)

        cmd = "cachebox -a 15 -d %s | grep ' 1'| awk {'print $1'}" % self.primary_volume
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = map(int, out.split())
        logger.debug("marked regions %s" % out)
        # Verifying region corresponding to database given to btd for monitoring
        region_btd = read_btddb_using_sqlite3(uuid_flag)
        self.assertTrue(set(out).issubset(set(acc_regions)))

        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "10000", "251")
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "20000", "10001")
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "30000", "20001")
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "40000", "30001")
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "50000", "40001")
        #Get region map of collection1
        ret, regions = mongodb.get_regions_map()
        new_regions = map(int, regions)
        time.sleep(5)
        self.assertNotEqual(acc_regions, new_regions)
        cmd = "cachebox -a 15 -d %s | grep ' 1'| awk {'print $1'}" % self.primary_volume
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = map(int, out.split())
        logger.debug("marked regions %s" % out)
        # Verifying region corresponding to database given to btd for monitoring
        region_btd = read_btddb_using_sqlite3(uuid_flag)
        self.assertTrue(set(out).issubset(set(new_regions)))
        cmd="cbasm --mongodb --letgo --uuid=%s" % uid
        os.system(cmd)
        logger.debug(cmd)

        drop_database(self.MongoDB.ip, self.dbname)
        deaccelerate_dev(self.primary_volume, tc=self)


class TestMongoDBIndex(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestMongoDBIndex, self).setUp()
        self.startTime = time.time()
        self.MongoDB=MongoDBTestUtil()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.dbname = "TestData"
        self.collectionname = "test123"
        self.collectionname1 = "test321"
        add_syncdelay(self.MongoDB.ip, self.dbname)

        if (self.MongoDB.index_only_acc_supported == 0):
            self.skipTest("Need to set #CA_MODIFIED_MONGO_SERVER=1 in mongodb.conf file")

    def tearDown(self):
        super(TestMongoDBIndex, self).tearDown()
        drop_database(self.MongoDB.ip, self.dbname)
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_mongocol_index(self):
        mongodb = MongoColIndex()
        mongodb.device = self.primary_volume
        mongodb.dbname = self.dbname
        mongodb.colname = self.collectionname
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "250", "1")
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc = self)
        uuid_flag = get_uuid_flag(self.primary_volume)
        # Create Database with 2 collections.
        create_database(self.MongoDB.ip, self.dbname, self.collectionname1, "250", "1")
        # Create index using ensureIndex
        drop_caches(tc=self)
        drop_caches(tc=self)
        drop_caches(tc=self)
        cmd = "echo \"db.%s.ensureIndex( { entry: 1 } )\" | mongo %s/%s"\
                % (self.collectionname, self.MongoDB.ip, self.dbname)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()

        # Accelerate Index
        db = MONGODBObject('%s.idx' % self.collectionname)
        uid = db.component.get('uuid')
        cmd = "cbasm --mongodb --accelerate --uuid=%s" % uid
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(process.returncode, 0)
        change_duration_regionmark(uuid_flag[1])
        ret, regions = mongodb.get_regions_map()
        old_regions = map(int, regions)

        cmd = "ls %s | grep '%s.*'" % (self.MongoDB.dbpath, self.dbname)
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = o.communicate()
        filenames = out.split()

        # Get corrosponding regions of db files using cbfacc command.
        file_regions_cbfacc = []
        for filename in filenames:
            cmd = "cbfacc -n -d %s -o file=%s/%s" % (self.primary_volume, self.MongoDB.dbpath, filename)
            p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            out, err = p1.communicate()
            file_regions_cbfacc.extend(out.split(","))
        file_regions_cbfacc =  map(int, filter(None, file_regions_cbfacc))
        old_regions.sort()
        file_regions_cbfacc.sort()
        self.assertTrue(set(old_regions).issubset(set(file_regions_cbfacc)))

        # Get regions which btd has been monitoring.
        uuid_flag = get_uuid_flag(self.primary_volume)
        region_btd = read_btddb_using_sqlite3(uuid_flag)
        old_regions.sort()
        region_btd.sort()
        self.assertEqual(len(region_btd), len(old_regions))
        self.assertEqual(region_btd, old_regions)
        drop_caches(tc=self)
        # Access database and check, region.
        cmd = "echo \"db.%s.getIndexes()\"| mongo %s/%s" % (self.collectionname, self.MongoDB.ip, self.dbname)
        for i in range(0, 300):
            os.system("%s > /dev/null" % cmd)
        time.sleep(5)
        cmd = "cachebox -a 15 -d %s | grep ' 1'| awk {'print $1'}" % self.primary_volume
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = map(int, out.split())
	logger.debug("marked regions %s" % out)
        self.assertTrue(set(out).issubset(old_regions))
        old_index_size =  mongodb.get_size()
        # Add additional data in collection and get new region
        mongodb = MongoColIndex()
        mongodb.device = self.primary_volume
        mongodb.dbname = self.dbname
        mongodb.colname = self.collectionname
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "25000", "251")
        create_database(self.MongoDB.ip, self.dbname, self.collectionname1, "2500", "251" )
        new_index_size =  mongodb.get_size()
        self.assertNotEqual(len(old_index_size), len(new_index_size))
        ret, regions = mongodb.get_regions_map()
        new_regions = map(int, regions)
        self.assertNotEqual(new_regions, old_regions)
        # check new regions has been marked
        drop_caches(tc=self)
        cmd = "cachebox -a 15 -d %s | grep ' 1'| awk {'print $1'}" % self.primary_volume
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = map(int, out.split())
        logger.debug("marked regions %s" % out)
        self.assertTrue(set(out).issubset(new_regions))
        cmd="cbasm --mongodb --letgo --uuid=%s" % uid
        os.system(cmd)
        logger.debug(cmd)

        drop_database(self.MongoDB.ip, self.dbname)
        deaccelerate_dev(self.primary_volume, tc=self)

    def test_mongodb_index(self):
        mongodb = MongoDbIndex()
        mongodb.device = self.primary_volume
        mongodb.dbname = self.dbname
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "250", "1")
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc = self)
        # Create Database with 2 collections.
        create_database(self.MongoDB.ip, self.dbname, self.collectionname1, "250", "1")
        # Create index using ensureIndex
        drop_caches(tc=self)
        drop_caches(tc=self)
        drop_caches(tc=self)
        cmd = "echo \"db.%s.ensureIndex( { entry: 1 } )\" | mongo %s/%s"\
                % (self.collectionname, self.MongoDB.ip, self.dbname)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()

        # Accelerate Index
        db = MONGODBObject('system.indexes')
        uid = db.component.get('uuid')
        uuid_flag = get_uuid_flag(self.primary_volume)
        cmd = "cbasm --mongodb --accelerate --uuid=%s" % uid
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(process.returncode, 0)
        change_duration_regionmark(uuid_flag[1])
        ret, regions = mongodb.get_regions_map()
        old_regions = map(int, regions)

        cmd = "ls %s | grep '%s.*'" % (self.MongoDB.dbpath, self.dbname)
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = o.communicate()
        filenames = out.split()

        # Get corrosponding regions of db files using cbfacc command.
        file_regions_cbfacc = []
        for filename in filenames:
            cmd = "cbfacc -n -d %s -o file=%s/%s" % (self.primary_volume, self.MongoDB.dbpath, filename)
            p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            out, err = p1.communicate()
            file_regions_cbfacc.extend(out.split(","))
        file_regions_cbfacc =  map(int, filter(None, file_regions_cbfacc))
        old_regions.sort()
        file_regions_cbfacc.sort()
        self.assertTrue(set(old_regions).issubset(set(file_regions_cbfacc)))

        # Get regions which btd has been monitoring.
        uuid_flag = get_uuid_flag(self.primary_volume)
        region_btd = read_btddb_using_sqlite3(uuid_flag)
        old_regions.sort()
        region_btd.sort()
        self.assertEqual(len(region_btd), len(old_regions))
        self.assertEqual(region_btd, old_regions)
        drop_caches(tc=self)
        # Access database and check, region.
        cmd = "echo \"db.%s.getIndexes()\"| mongo %s/%s" % (self.collectionname, self.MongoDB.ip, self.dbname)
        for i in range(0, 300):
            os.system("%s > /dev/null" % cmd)
        time.sleep(5)
        cmd = "cachebox -a 15 -d %s | grep ' 1'| awk {'print $1'}" % self.primary_volume
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = map(int, out.split())
	logger.debug("marked regions %s" % out)
        self.assertTrue(set(out).issubset(old_regions))
        old_index_size =  mongodb.get_size()
        # Add additional data in collection and get new region
        mongodb = MongoDbIndex()
        mongodb.device = self.primary_volume
        mongodb.dbname = self.dbname
        create_database(self.MongoDB.ip, self.dbname, self.collectionname, "25000", "251")
        create_database(self.MongoDB.ip, self.dbname, self.collectionname1, "2500", "251" )
        new_index_size =  mongodb.get_size()
        self.assertNotEqual(len(old_index_size), len(new_index_size))
        ret, regions = mongodb.get_regions_map()
        new_regions = map(int, regions)
        self.assertNotEqual(new_regions, old_regions)
        # check new regions has been marked
        drop_caches(tc=self)
        cmd = "cachebox -a 15 -d %s | grep ' 1'| awk {'print $1'}" % self.primary_volume
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        out = map(int, out.split())
        logger.debug("marked regions %s" % out)
        self.assertTrue(set(out).issubset(new_regions))
        cmd="cbasm --mongodb --letgo --uuid=%s" % uid
        os.system(cmd)
        logger.debug(cmd)

        drop_database(self.MongoDB.ip, self.dbname)
        deaccelerate_dev(self.primary_volume, tc=self)

class TestMongoDBReplica(CBQAMixin, unittest.TestCase):

    def setUp(self):
        super(TestMongoDBReplica, self).setUp()
        self.startTime = time.time()
        self.MongoDB=MongoDBTestUtil()
        self.primary_volume = random.choice(PRIMARY_VOLUMES)
        self.ssd_volume = random.choice(SSD_VOLUMES.keys())
        self.dbname = "TestData"
        self.collectionname = "test123"
        self.collectionname1 = "test321"


        if (self.MongoDB.replSet == False):
            self.skipTest("Need to set replSet = rsName in mongodb.conf file \
                            and replication should enable")


    def tearDown(self):
        super(TestMongoDBReplica, self).tearDown()
        if isdev_accelerated(self.primary_volume):
            deaccelerate_dev(self.primary_volume, tc=self)

    def test_mongodb_replica_in_list(self):
        # If replication is Enable
        returncode = cbasm_list_with_grep("oplog.rs")
        self.assertEqual(returncode, 0)
        # Disable replication
        # change in conf file with removing replName flag, which disable replication.
        if "Ubuntu" in platform.dist():
            conf = open("/etc/mongodb.conf", "r")
        elif "centos" in platform.dist() or "redhat" in platform.dist():
            conf = open("/etc/mongod.conf", "r")

        lines = conf.readlines()
        conf.close()

        if "Ubuntu" in platform.dist():
            conf = open("/etc/mongodb.conf", "w")
        elif "centos" in platform.dist() or "redhat" in platform.dist():
            conf = open("/etc/mongod.conf", "w")
        for line in lines:
            if not (line.startswith("replSet=")):
                conf.write(line)
        conf.close()
        cmd = [
            "restart",
            "mongodb"
            ]
        logger.debug(cmd)
        process_1 = subprocess.Popen(cmd, stdout = subprocess.PIPE, \
                    stderr = subprocess.PIPE).communicate()
        time.sleep(5)
        # If replication is Disable
        returncode = cbasm_list_with_grep("oplog.rs")
        self.assertNotEqual(returncode, 0)

    def test_replica_acceleration(self):
        accelerate_dev(self.primary_volume, self.ssd_volume, "write-back", tc = self)
        #If replication is Enable then continue
        uuid_flag = get_uuid_flag(self.primary_volume)
        db = MONGODBObject("oplog.rs")
        uid=db.component.get('uuid')

        mongodb = MongoCol()
        mongodb.device = self.primary_volume
        mongodb.dbname = "local"
        mongodb.colname = "oplog.rs"

        cmd="cbasm --mongodb --accelerate --uuid=%s" % uid
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        self.assertEqual(process.returncode, 0)
        change_duration_regionmark(uuid_flag[1])

        cmd = "cachebox -a 15 -d %s | grep ' 1'| awk {'print $1'}" % self.primary_volume
        logger.debug(cmd)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        out, err = process.communicate()
        regions_marked = out.split()
        assertNotEqual(len(regions_marked), 0)

        cmd = "ls %s | grep '%s.*'" % (self.MongoDB.dbpath, "local")
        o = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = o.communicate()
        filenames = out.split()
        # Get corrosponding regions of db files using cbfacc command.
        file_regions_cbfacc = []
        for filename in filenames:
            cmd = "cbfacc -n -d %s -o file=%s/%s" % (self.primary_volume, self.MongoDB.dbpath, filename)
            p1 = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            out, err = p1.communicate()
            file_regions_cbfacc.extend(out.split(","))
        file_regions_cbfacc =  map(int, filter(None, file_regions_cbfacc))
        self.assertTrue(set(regions_marked).issubset(set(file_regions_cbfacc)))
        cmd="cbasm --mongodb --letgo --uuid=%s" % uid
        os.system(cmd)
        logger.debug(cmd)
        deaccelerate_dev(self.primary_volume, tc=self)


if __name__ == '__main__':
    unittest.main(argv=["mongodb_adv_tests.py"] + args)
