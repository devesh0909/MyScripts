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

import getopt
import os
import random
import shutil
import subprocess
import sys
import time
import unittest
import platform

from common_utils import *
from cblog import *

config_file, args = get_config_file(sys.argv)
config = __import__(config_file)

for member_name in dir(config):
        if not member_name.startswith("__"):
                globals()[member_name] = getattr(config, member_name)

path = os.getcwd()+"/../tools"
os.environ['PATH'] = "%s:%s" % (os.getenv('PATH'), path)

WRITE_POLICY = ['write-back', 'write-through']
os_used = platform.dist()[0]


password = "root123"            
dbname = "Warehouse"
tablename = "License"
dbpath = "/data/mysql/%s/%s" % (dbname, tablename)


class MYSQL_Utils(object):
    '''
    Creating database
    ''' 
    @staticmethod
    def createdb(password, dbname, tc):
        cmd = 'mysql -u root -p%s -e "create database %s;"' % (password, dbname)
        logger.debug(cmd)
        out = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = out.communicate()
        tc.assertEqual(out.returncode, 0)
        logger.debug(error)
        logger.debug(output)
    
    '''
    Creating table
    '''
    @staticmethod 
    def sysbench_table(password, dbname, tablenm, engine, tc):
        cmd = ["sysbench"]
        logger.debug(cmd)
        out = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = out.communicate()
        tc.assertEqual(out.returncode, 1)
        if out.returncode != 1 :
            logger.debug("Sysbench Error : %s" % (error))
            sys.exit(1)
        else:
            logger.debug ("Sysbench found")

        if os_used == "Ubuntu":
            cmd = ["sysbench",
                   "--test=oltp",
                   "--mysql-table-engine=%s" % engine,
                   "--oltp-table-size=1000000",
                   "--mysql-user=root",
                   "--mysql-socket=/var/run/mysqld/mysqld.sock",
                   "--mysql-password=%s" % password,
                   "--mysql-db=%s" % dbname,
                   "--oltp-table-name=%s" %tablenm,
                   "prepare" 
                  ]
            
        elif os_used == "redhat" or os_used == "centos":
            cmd = ["sysbench",
                   "--db-driver=mysql",
                   "--test=oltp",
                   "--mysql-table-engine=%s" % engine,
                   "--oltp-table-size=1000000",
                   "--mysql-host=localhost",
                   "--mysql-user=root",
                   "--mysql-socket=/var/lib/mysql/mysql.sock",
                   "--mysql-password=%s" % password,
                   "--mysql-db=%s" % dbname,
                   "--oltp-table-name=%s" % tablenm,
                   "prepare"
                  ]
                
        logger.debug(cmd)
        out = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = out.communicate()
        tc.assertEqual(out.returncode, 0)

    '''
    Starting Sysbench on table
    '''
    @staticmethod      
    def do_sysbench(password, dbname, tablenm, engine, tc):
        if os_used == "Ubuntu":
            cmd = ["sysbench",
                   "--db-driver=mysql",
                   "--num-threads=4",
                   "--test=oltp",
                   "--oltp-table-size=1000000",
                   "--oltp-table-name=%s" % tablenm,
                   "--max-time=100",
                   "--max-requests=0",
                   "--oltp-dist-type=special",
                   "--mysql-user=root",
                   "--oltp-read-only=off",
                   "--mysql-password=%s" % password,
                   "--mysql-db=%s" % dbname,   
                   "--mysql-table-engine=%s" % engine,
                   "--batch",
                   "--batch-delay=5",
                   "--oltp-dist-pct=1",
                   "--init-rng=on",
                   "--mysql-socket=/var/run/mysqld/mysqld.sock",
                   "run"
                  ]
        elif os_used == "redhat" or os_used == "centos":
            cmd = ["sysbench",
                   "--db-driver=mysql",
                   "--num-threads=4",
                   "--test=oltp",
                   "--oltp-table-size=1000000",
                   "--oltp-table-name=%s" % tablenm,
                   "--mysql-host=localhost",
                   "--max-time=200",
                   "--max-requests=0",
                   "--oltp-dist-type=special",
                   "--mysql-user=root",
                   "--oltp-read-only=off",
                   "--mysql-password=%s" % password,
                   "--mysql-db=%s" % dbname,
                   "--mysql-table-engine=%s" % engine,
                   "--batch",
                   "--batch-delay=10",
                   "--oltp-dist-pct=1",
                   "--init-rng=on",
                   "--mysql-socket=/var/lib/mysql/mysql.sock",
                   "run"
                  ]
        logger.debug(cmd)
        out = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = out.communicate()
        tc.assertEqual(out.returncode, 0)

    @staticmethod
    def accelerate_cbmysql(device, ssd, objecttype, objectname, engine, tc, write_policy = DEFAULT_WRITE_POLICY, index=None):

        cmd = "cbasm --mysql --list | grep %s | grep %s | head -1 | awk \'{print($6)}\'" % (objecttype, objectname)
        logger.debug(cmd)
        
        uuid = os.popen(cmd).read().strip()
        cmd = ["cbasm",
                "--mysql",
                "--accelerate",
                "--uuid=%s" % uuid,
              ]
        logger.debug(cmd)
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        tc.assertEqual(r.returncode, 0)
  
    @staticmethod
    def deaccelerate_cbmysql(objecttype, objectname, tc):
        cmd = "cbasm --mysql --list | grep %s | grep %s | head -1 | awk \'{print($6)}\'" % (objecttype, objectname)
        uuid = os.popen(cmd).read().strip()
        cmd = ["cbasm",
               "--letgo",
               "--device=%s" % uuid,
              ]        
        logger.debug(cmd)
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        tc.assertEqual(r.returncode, 0)

    @staticmethod
    def get_btd_status(tc):
        cmd = ("ps -aef | grep /var/log/cachebox/mysql_region")
        logger.debug(cmd)
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        tc.assertEqual(r.returncode, 0)

    @staticmethod
    def conf_backup(tc):
        if os_used == "Ubuntu":
            '''
            Taking backup of config file
            '''
            cmd = ["cp",
                   "/etc/mysql/my.cnf",
                   "/etc/mysql/my_bk.cnf"
                  ]
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            tc.assertEqual(r.returncode, 0) 
            '''
            Taking backup of /etc/apparmor.d/usr.sbin.mysqld, 
            '''
            cmd = ["cp",
                   "/etc/apparmor.d/usr.sbin.mysqld",
                   "/etc/apparmor.d/usr.sbin.mysqld_bk"
                  ]
            
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            tc.assertEqual(r.returncode, 0) 
 
        elif os_used == "redhat" or os_used == "centos":
            cmd = ["cp",
                   "/etc/my.cnf",
                   "/etc/my_bk.cnf"
                  ]
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            tc.assertEqual(r.returncode, 0)

    @staticmethod
    def copy_apparmor(tc):
        current_dir = os.getcwd()
        if os_used == "Ubuntu":
            cmd = ["cp",
                   "%s/apparmor_mysql.txt" % current_dir,
                   "/etc/apparmor.d/usr.sbin.mysqld"
                  ]
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            tc.assertEqual(r.returncode, 0)

    '''
    Copying back the original config file back
    '''
    @staticmethod
    def copying_backupfile(tc):
        if os_used == "Ubuntu":
            cmd = ["cp",
                   "/etc/mysql/my_bk.cnf",
                   "/etc/mysql/my.cnf"
                  ]
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            tc.assertEqual(r.returncode, 0)

            cmd = ["cp",
                   "/etc/apparmor.d/usr.sbin.mysqld_bk",
                   "/etc/apparmor.d/usr.sbin.mysqld"
                  ]

            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            tc.assertEqual(r.returncode, 0)
  
        elif os_used == "redhat" or os_used == "centos":
            cmd = ["cp",
                   "/etc/my_bk.cnf",
                   "/etc/my.cnf"
                  ]
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            tc.assertEqual(r.returncode, 0)

    @staticmethod
    def innodb_engine_specific(conf_file, tc):
        current_dir = os.getcwd()
        if os_used == "Ubuntu":
            cmd = ["cp",
                   "%s/innodb_ubuntu.txt" % current_dir,
                   "%s" % conf_file 
                  ]
        elif os_used == "redhat" or os_used == "centos":
            cmd = ["cp",
                   "%s/innodb_rhel.txt" % current_dir,
                   "%s" % conf_file
                  ]
        logger.debug(cmd)
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        logger.debug(error)
        tc.assertEqual(r.returncode, 0)
        
    @staticmethod
    def myisam_engine_specific(conf_file, tc):
        current_dir = os.getcwd()
        if os_used == "Ubuntu":
            cmd = ["cp",
                   "%s/myisam_ubuntu.txt" % current_dir,
                   "%s" % conf_file
                  ]
        elif os_used == "redhat" or os_used == "centos":
            cmd = ["cp",
                   "%s/myisam_rhel.txt" % current_dir,
                   "%s" % conf_file
                  ]
        logger.debug(cmd)
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        tc.assertEqual(r.returncode, 0)

    @staticmethod
    def edit_config(engine, tc):
        if os_used == "Ubuntu":
            conf_backup(tc)
            '''
            Changing the config file as per the OS and data engine 
            '''            
            if engine == "innodb":
               innodb_engine_specific("/etc/mysql/my.cnf", tc)
            else:
               myisam_engine_specific("/etc/mysql/my.cnf", tc)        

            copy_apparmor(tc)
      
            cmd = ["apparmor_parser",
                   "-rv",
                   "/etc/apparmor.d/usr.sbin.mysqld"
                  ]
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            logger.debug(error)
            tc.assertEqual(r.returncode, 0)
 
        elif os_used == "redhat" or os_used == "centos":
            conf_backup(tc)
            if engine == "innodb":
               innodb_engine_specific("/etc/my.cnf", tc)  
            else:
               myisam_engine_specific("/etc/my.cnf", tc)
 
    @staticmethod
    def start_service(engine, tc):
        #
        #Editing the configuration file before starting service
        #
        edit_config(engine, tc)
        '''
        Giving the permission to data directory
        '''
        cmd = ["chown",
               "-R",
               "root:root",
               "/data/mysql"
              ]
        logger.debug(cmd)
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = r.communicate()[0]
        tc.assertEqual(r.returncode, 0)
      
        cmd = ["mysql_install_db"]
        logger.debug(cmd)
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        tc.assertEqual(r.returncode, 0)
                     
        if os_used == "Ubuntu":
            cmd = ["service",
                   "mysql",
                   "start"
                  ]
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            tc.assertEqual(r.returncode, 0)
            if r.returncode != 0 :
                logger.debug("MySql service is not started : %s" % (error))
                sys.exit(1)
            else:
                logger.debug(output)
        elif os_used == "redhat" or os_used == "centos":
            cmd = ["echo 0 > /selinux/enforce"]
            logger.debug(cmd)
            r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            tc.assertEqual(r.returncode, 0)

            cmd = ["service",
                   "mysqld",
                   "start"
                  ]
            logger.debug(cmd)
            r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = r.communicate()
            tc.assertEqual(r.returncode, 0)
            if r.returncode != 0 :
                logger.debug("MySql service is not started : %s" % (error))
                sys.exit(1)
            else:
                logger.debug(output)

        cmd = ["mysqladmin -u root password 'root123'"]
        logger.debug(cmd)
        r = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        tc.assertEqual(r.returncode, 0)

    @staticmethod
    def stop_service(tc):
        if os_used == "Ubuntu":
            cmd = ["service",
                   "mysql",
                   "stop"
                  ]
        elif os_used == "redhat" or os_used == "centos":
            cmd = ["service",
                   "mysqld",
                   "stop"
                  ]

        logger.debug(cmd)
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        tc.assertEqual(r.returncode, 0)
        if r.returncode != 0 :
            logger.debug("MySql service is not stopped : %s" % (error))
            sys.exit(1)
        else:
            logger.debug (output)
       
stop_service = MYSQL_Utils.stop_service
start_service = MYSQL_Utils.start_service 
sysbench_table = MYSQL_Utils.sysbench_table 
get_btd_status = MYSQL_Utils.get_btd_status
deaccelerate_cbmysql = MYSQL_Utils.deaccelerate_cbmysql
do_sysbench = MYSQL_Utils.do_sysbench
accelerate_cbmysql = MYSQL_Utils.accelerate_cbmysql
edit_config = MYSQL_Utils.edit_config
innodb_engine_specific = MYSQL_Utils.innodb_engine_specific
myisam_engine_specific = MYSQL_Utils.myisam_engine_specific
copy_apparmor = MYSQL_Utils.copy_apparmor
copying_backupfile = MYSQL_Utils.copying_backupfile
conf_backup = MYSQL_Utils.conf_backup
createdb = MYSQL_Utils.createdb


class TestCbmysqlInnodb(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(TestCbmysqlInnodb, self).setUp()
        self.startTime = time.time()

        self.pvn1 = random.choice(PRIMARY_VOLUMES)
        self.svn1 = random.choice(SSD_VOLUMES.keys())
        #
        # Check if the devices in config.py are already existing
        #
        checkdev(devname=self.pvn1, tc = self)
        checkdev(devname=self.svn1, tc = self)

        logger.debug( "\n\nSTART: %s" % self.id())
        logger.debug( "testing with %s and %s" % (self.pvn1, self.svn1))

        do_mkfs(self.pvn1, "default", self)
        do_mkdir("/data/mysql", self)
        do_mount(self.pvn1, "/data/mysql", self)
        
        start_service("innodb", self)
        time.sleep(10)
        
        createdb(password, dbname, self)
        sysbench_table(password, dbname, tablename, "innodb", self)
      
    def tearDown(self):
        super(TestCbmysqlInnodb, self).tearDown()
        if isdev_accelerated(self.pvn1):
            deaccelerate_dev(self.pvn1, tc = self)

        for i in range(0, 10):
            drop_caches(self)
        time.sleep(10)
        stop_service(self)
      
        if is_mounted("/data/mysql"):
             do_unmount("/data/mysql", self)
        copying_backupfile(self)
        shutil.rmtree("/data/mysql")
        t = time.time() - self.startTime
        logger.debug("\nDONE: %s: %.3f" % (self.id(), t))

    def test_cbmysql_innodb(self):
        for policies in WRITE_POLICY:
            logger.debug("======Testing for %s Policy======" % policies)
            accelerate_dev(self.pvn1, self.svn1, 4096, tc=self, write_policy = policies)
            accelerate_cbmysql(self.pvn1, self.svn1,"table", tablename, "innodb", self, policies)        
            do_sysbench(password, dbname, tablename, "innodb", self)
            stats = getxstats(self.pvn1)
            logger.debug(stats)
            get_btd_status(self)
            deaccelerate_dev(self.pvn1, tc = self)
        logger.debug("=================================================")
        do_pass(self, 'test_cbmysql_innodb')      

    def test_cbmysql_innodb_with_i(self):
        for policies in WRITE_POLICY:
            logger.debug("======Testing for %s Policy======" % policies)

            accelerate_cbmysql(self.pvn1, self.svn1, "table", tablename, "innodb", self, policies, "-i")
            do_sysbench(password, dbname, tablename, "innodb", self)
            stats = getxstats(self.pvn1)
            logger.debug(stats)
            get_btd_status(self)
            deaccelerate_cbmysql(self.pvn1, self)
        logger.debug("=================================================")
        do_pass(self, 'test_cbmysql_innodb_with_i')

    def test_cbmysql_innodb_with_indexonly(self):
        for policies in WRITE_POLICY:
            logger.debug("======Testing for %s Policy======" % policies)
 
            accelerate_cbmysql(self.pvn1, self.svn1, "table", tablename, "innodb", self, policies, "--indexonly")
            do_sysbench(password, dbname, tablename, "innodb", self)
            stats = getxstats(self.pvn1)
            logger.debug(stats)
            get_btd_status(self)
            deaccelerate_cbmysql(self.pvn1, self)
        logger.debug("=================================================")
        do_pass(self, 'test_cbmysql_innodb_with_indexonly')


class TestCbmysqlMyISAM(CBQAMixin, unittest.TestCase):
    def setUp(self):
        super(TestCbmysqlMyISAM, self).setUp()
        self.startTime = time.time()

        self.pvn1 = random.choice(PRIMARY_VOLUMES)
        self.svn1 = random.choice(SSD_VOLUMES.keys())
        #
        # Check if the devices in config.py are already existing
        #
        checkdev(devname=self.pvn1, tc = self)
        checkdev(devname=self.svn1, tc = self)

        logger.debug( "\n\nSTART: %s" % self.id())
        logger.debug( "testing with %s and %s" % (self.pvn1, self.svn1))

        do_mkfs(self.pvn1, "default", self)
        do_mkdir("/data/mysql", self)
        do_mount(self.pvn1, "/data/mysql", self)
        
        start_service("myisam", self)
        time.sleep(10)
        createdb(password, dbname, self)
        sysbench_table(password, dbname, tablename, "myisam", self)
      
    def tearDown(self):
        super(TestCbmysqlMyISAM, self).tearDown()
        if isdev_accelerated(self.pvn1):
            deaccelerate_dev(self.pvn1, tc = self)

        for i in range(0, 10):
            drop_caches(self)
        time.sleep(10)
        stop_service(self)

        if is_mounted("/data/mysql"):
             do_unmount("/data/mysql", self)
        copying_backupfile(self)
        shutil.rmtree("/data/mysql")
        t = time.time() - self.startTime
        logger.debug("\nDONE: %s: %.3f" % (self.id(), t))

    def test_cbmysql_myisam(self):

        for policies in WRITE_POLICY:
            logger.debug("======Testing for %s Policy======" % policies)

            accelerate_cbmysql(self.pvn1, self.svn1, "table", tablename, "myisam", self, policies)
            do_sysbench(password, dbname, tablename, "myisam", self)
            stats = getxstats(self.pvn1)
            logger.debug(stats)
            get_btd_status(self)
            deaccelerate_cbmysql(self.pvn1, self)
        logger.debug("=================================================")
        do_pass(self, 'test_cbmysql_myisam')

    def test_cbmysql_myisam_with_i(self):
        for policies in WRITE_POLICY:
            logger.debug("======Testing for %s Policy======" % policies)

            accelerate_cbmysql(self.pvn1, self.svn1, "table", tablename, "myisam", self, policies, "-i")
            do_sysbench(password, dbname, tablename, "myisam", self)
            stats = getxstats(self.pvn1)
            logger.debug(stats)
            get_btd_status(self)
            deaccelerate_cbmysql(self.pvn1, self)
        logger.debug("=================================================")
        do_pass(self, 'test_cbmysql_myisam_with_i')

    def test_cbmysql_myisam_with_indexonly(self):
        for policies in WRITE_POLICY:
            logger.debug("======Testing for %s Policy======" % policies)

            accelerate_cbmysql(self.pvn1, self.svn1, "table", tablename, "myisam", self, policies, "--indexonly")
            do_sysbench(password, dbname, tablename, "myisam", self)
            stats = getxstats(self.pvn1)
            logger.debug(stats)
            get_btd_status(self)
            deaccelerate_cbmysql(self.pvn1, self)
        logger.debug("=================================================")
        do_pass(self, 'test_cbmysql_myisam_with_indexonly')

if __name__ == '__main__':
    unittest.main(argv=["cbmysql.py"] + args)

