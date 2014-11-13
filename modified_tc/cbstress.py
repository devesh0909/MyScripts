#!/usr/bin/env python

import random

import cachebox
import common_utils
import datetime
import getopt
import os
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
    fd = os.open(device, os.O_RDONLY)
    while dowork and not abort:
        sector = random.randrange(sectors)
        print sector
        continue

        offset = sector << 9
        offset = rounddown(offset, 4096)
        os.lseek(fd, offset, os.SEEK_SET)
        print 'reading sector %s' % (offset >> 9)
        buf = os.read(fd, size)
#        r = cachebox.cb_read(fd, size, 0x41)
#        if r != size:
#            abort = True
#            print "aborting read %s %s" % (r, size)

        tbuf = ('%s' % ((offset >> 9) % 10)) * size
        if str(buf) != str(tbuf):
            print 'mismatch at sector %s' % (offset >> 9)
        time.sleep(0.001)

    os.close(fd)


def do_write(*args, **kwags):

    #
    # pick a random sector and size and write, no verification.
    # 

    global abort

    while not start:
        time.sleep(0.05)

    seed = 0    
    while dowork and not abort:
        r = subprocess.Popen(
            ["./xx.py",  "%s" % device, "%s" % seed, "%s" % sectors], 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = r.communicate()
        if r.returncode != 0:
            print output[0]
            print output[1]
            sys.exit(1)

        seed += 1
        print output[0]
    
    # i = 0
    # fd = os.open(device, os.O_RDWR|os.O_DIRECT)
    # while dowork and not abort:
    #     sector = g.randrange(sectors) #random.choice(sectors)
    #     # print sector
    #     # continue

    #     offset = sector << 9
    #     offset = rounddown(sector, 4096)
    #     c = ('%s' % ((offset >> 9) % 10))
    #     print 'writing sector %s' % (offset >> 9)
    #     os.lseek(fd, offset, os.SEEK_SET)
    #     r = cachebox.cb_write(fd, size, c)
    #     if r != size:
    #         abort = True
    #         print "aborting write %s %s" % (r, size)
    #     time.sleep(0.001)

    # os.close(fd)


def usage():
    print "cbstress.py --device=<device> --readers=<count> --writers=<count> --duration=<seconds> --bsize=<bsize>"

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
#    sectors = xrange(0, dsize - 10)
    sectors = dsize - 16

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
