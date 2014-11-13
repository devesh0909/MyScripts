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

def do_write(*args, **kwags):

    #
    # pick a random sector and size and write an IO pattern there.
    # 

    global abort

    while not start:
        time.sleep(0.05)

    i = 0
    size = random.choice(bsizes)
    assert size == 4096
    while dowork and not abort:
        cmd = ["dd",
               "if=/dev/zero",
               "of=%s" % device,
               "bs=%s" % size,
               "oflag=direct",
              ]
      
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        time.sleep(0.001)

def do_read(*args, **kwags):

    #
    # pick a sector which was written to and verify the integrity of
    # the data.
    # 
    global abort

    while not start:
        time.sleep(0.05)

    i = 0
    size = random.choice(bsizes)
    assert size == 4096
    while dowork and not abort:
        cmd = ["dd",
               "if=%s" % device,
               "of=/dev/null",
               "bs=%s" % size,
               "iflag=direct",
              ]
      
        r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = r.communicate()
        time.sleep(0.001)

 
def usage():
    print "sequential.py --device=<device> --readers=<count> --writers=<count> --duration=<seconds>"

writers = []
readers = []

def do_main():
    global dowork, sectors
    global device
    global duration
    # default readers and writers
    reads = 1
    writes = 1
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
    time.sleep(duration)
    dowork = False

    for t in writers:
        t.join()

    for t in readers:
        t.join()

    print 'done'

if __name__ == '__main__':
    do_main()
