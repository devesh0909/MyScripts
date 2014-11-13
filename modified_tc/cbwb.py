#!/usr/bin/env python

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

wsectors = []

def do_dc():
    return subprocess.Popen("while :; do echo 3 > /proc/sys/vm/drop_caches; sleep 1; done", shell = True)

def get_buffer(size, sector):
    s = ('%0.16d%0.16d' % (size, sector)) * (size/32)
    buf = buffer(s, 0, size)
    assert len(s) == size
    return buf

def rounddown(x, y):
    return (x) & ~(y - 1)

def write_on_disk(size, buf, sector):
    fd = os.open(device, os.O_WRONLY)
    os.lseek(fd, sector, os.SEEK_SET)
    os.write(fd, buf)
    os.close(fd)

def read_from_disk(size, sector):
    fd = os.open(device, os.O_RDONLY)
    os.lseek(fd, sector, os.SEEK_SET)
    buf = os.read(fd, size)
    os.close(fd)
    return buf

def do_read(*args, **kwags):

    #
    # pick a random sector and size and read, no verification.
    # 

    global abort

    while not start:
        time.sleep(0.05)

    while len(wsectors) == 0:
        time.sleep(0.05)

    time.sleep(1)

    i = 0
    while dowork and not abort:
        sector = random.choice(wsectors)
        sector= rounddown(sector, 4096)
        buf = get_buffer(size, sector)
        rbuf = read_from_disk(size, sector)
        if str(buf) != rbuf:
            abort = True
            print "aborting write %s" % (size)
        time.sleep(0.001)


def do_write(*args, **kwags):

    #
    # pick a random sector and size and write, no verification.
    # 

    global abort

    while not start:
        time.sleep(0.05)

    while dowork and not abort:
        sector = random.choice(sectors)
        sector= rounddown(sector, 4096)
        wbuf = get_buffer(size, sector)
        write_on_disk(size, wbuf, sector)
        wsectors.append(sector)
        time.sleep(0.001)

def usage():
    print "cbwb.py --device=<device> --readers=<count> --writers=<count> --duration=<seconds> --bsize=<bsize>"

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
