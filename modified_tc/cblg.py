#!/usr/bin/env python

import cachebox
import common_utils
import datetime
import getopt
import os
import random
import sys
import threading
import time

import subprocess

device = None
duration = 10

sectors = None
bsizes = (1 << 12, )
iotable = {}
dowork = True
size = 4096
start = False
abort = False

def do_dc():
    return subprocess.Popen("while :; do echo 3 > /proc/sys/vm/drop_caches; sleep 1; done", shell = True)

def getbuf(sector, size):
    
    #
    # return a string which is size bytes long encoded with sector
    #

    assert size % 32 == 0
    s = ('%0.16d%0.16d' % (sector, size)) * (size/32)
    assert len(s) == size
    return s

def rounddown(x, y):
    return (x) & ~(y - 1)

def do_read(*args, **kwags):

    #
    # pick a random sector and size and read, no verification.
    # 

    global abort

    while not start:
        time.sleep(0.05)

    i = 0
    fd = os.open(device, os.O_RDONLY|os.O_DIRECT)
    while dowork and not abort:
        sector = random.choice(sectors)
        sector= rounddown(sector, 4096)
        os.lseek(fd, sector << 9, os.SEEK_SET)
        r = cachebox.cb_read(fd, size, 0x41)
        if r != size:
            abort = True
            print "aborting read %s %s" % (r, size)
        time.sleep(0.001)

    os.close(fd)


def do_write(*args, **kwags):

    #
    # pick a random sector and size and write, no verification.
    # 

    global abort

    while not start:
        time.sleep(0.05)

    i = 0
    fd = os.open(device, os.O_RDWR|os.O_DIRECT)
    while dowork and not abort:
        sector = random.choice(sectors)
        sector= rounddown(sector, 4096)
        os.lseek(fd, sector << 9, os.SEEK_SET)
        r = cachebox.cb_write(fd, size, 0x42)
        if r != size:
            abort = True
            print "aborting write %s %s" % (r, size)
        time.sleep(0.001)

    os.close(fd)


def usage():
    print "cblg.py --device=<device> --readers=<count> --writers=<count> --duration=<seconds> --bsize=<bsize>"

writers = []
readers = []

def do_main():
    global dowork, sectors
    global device
    global duration
    # default readers and writers
    reads = 16
    writes = 2
    global size
    global start

    try:
        opts, args = getopt.getopt(sys.argv[1:], "", 
                                   ["device=", 
                                    "duration=",
                                    "bsize=",
                                    "readers=",
                                    "writers="
                                    ])

    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)
    for o, a in opts:
        if o in ("--device"):
            device = a
        elif o in ("--duration"):
            duration = int(a)
        elif o in ("--bsize"):
            size = int(a)
        elif o in ("--readers"):
            reads = int(a)
        elif o in ("--writers"):
            writes = int(a)

    if device == None:
        sys.exit(1)

    dsize = common_utils.Common_Utils.get_devsz(device)
    sectors = xrange(0, dsize - 10)
    for t in xrange(0, reads):
        reader = threading.Thread(target = do_read, kwargs = {})
        readers.append(reader)

    for reader in readers:
        reader.start()

    for t in xrange(0, writes):
        writer = threading.Thread(target = do_write, kwargs = {})
        writers.append(writer)

    for writer in writers:
        writer.start()

    start = True
    print 'waiting for %s seconds' % duration
    dc = do_dc()
    time.sleep(duration)
    dc.terminate()
    dowork = False

    for t in writers:
        t.join()

    for t in readers:
        t.join()

    print 'done'

if __name__ == '__main__':
    do_main()
