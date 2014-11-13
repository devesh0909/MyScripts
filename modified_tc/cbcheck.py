import getopt
import os
import sys

from cbtypes import *
from layout import *

#
# initial python implementation of consistency check utility
#

f = None
sb = None

def do_findcurru(ruentries):

    #
    # finds the current reclaim unit
    # 

    i = 0
    while i < sb.csb_numebs:
        ru = ruentries[i]
        if ru.ceb_flags & 0x20:
            break
        i += 1

    if not (ru.ceb_flags & 0x28):
        return (0, None, None)

    # i now points to a dirty RU, see if it is the head

    while i < sb.csb_numebs:
        if not (ruentries[i].ceb_flags & 0x20):
            break

        ru = ruentries[i]
        ruhbuf = readruh(f, sb, i)
        ruh = cast(ruhbuf, POINTER(cb_ruheader)).contents
        rmap = cast(ruhbuf[16:], POINTER(cb_rmapping * ruh.ruh_rindex)).contents

        if ruh.ruh_generation != ru.ceb_generation or ruh.ruh_rindex == 0:
            break

        i += 1

#    print 'ru: %3d ru.generation: 0x%0.8x ru.flags: 0x%0.8x ruh.generation 0x%0.8x ruh.rindex %d' % (i - 1, ru.ceb_generation, ru.ceb_flags, ruh.ruh_generation, ruh.ruh_rindex)

    return (i - 1, ru, readruh(f, sb, i - 1))


def do_checkregions(ru, ruhbuf):

    #
    # given a reclaim unit, see if the corresponding region control,
    # regions are in the expected state
    #

    ruh = cast(ruhbuf, POINTER(cb_ruheader)).contents
    rmap = cast(ruhbuf[16:], POINTER(cb_rmapping * ruh.ruh_rindex)).contents

    i = 0
    while i < ruh.ruh_rindex:
        rm = rmap[i]
        print "offset: %3d ssd: %8s hdd:%8s" % (i, rm.rm_ssdoffset, rm.rm_hddoffset)
        do_checkfmapentry(sb, rm.rm_hddoffset, rm.rm_ssdoffset)
        i += 1

regions = {}

def do_checkfmapentry(sb, hddoffset, ssdoffset):

    #
    # get the region corresponding to the hddoffset and check if the
    # fmap entry exists.
    #

    regionsize = sb.csb_bsize * sb.csb_blocksperregion
    L2 = (hddoffset << 9) / regionsize
    L1 = ((hddoffset << 9) - (L2 * regionsize)) / sb.csb_bsize

    print "L2:", L2, "L1:", L1
    assert L2 < sb.csb_numregions

    if not regions.has_key(L2):
        regions[L2] = readfmap2(f, sb, L2)

    return

#    for x in regions[rno]:
#        print x

#    print offset / sb.csb_bsize
#    return

    size = regions[L2][1]
    fmap = regions[L2][0]

    if not (fmap[L1].cfm_flags & 0x2):

        #
        # a block is cached but corresponding fmap entry is not marked
        # valid.
        #

        print '0x%x %8d %8d' % (fmap[L1].cfm_flags, ssdoffset, fmap[L1].cfm_ssdsector)

    if fmap[L1].cfm_ssdsector != ssdoffset:

        #
        # corrupt entry.
        #

        print "mismatch"

    # i = 0
    # while i < size:
    #     print fmap[i].cfm_flags
    #     i += 1

#    print 'hdd: %8d region: %8d' % (hddoffset, )
    
    

def do_check(ssd):
    global sb
    buf = readsuper(f)
    sb = cast(buf, POINTER(cb_superblock)).contents

    if sb.csb_magic != 0xfeefb00d:
        print "%s: could not find valid super block." % ssd
        sys.exit(1)

    ruentries = reademap(f, sb)
    rue = cast(ruentries, POINTER(cb_ebsmapentry * sb.csb_numebs)).contents
    index, ru, ruhbuf = do_findcurru(rue)
    print "found head at ru: %d" % index
    do_checkregions(ru, ruhbuf)

def do_main():
    check = False
    global f
    try:
        opts, args = getopt.getopt(sys.argv[1:], "s:", [
                "check",
                "ssd=",
                ])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)
    ssd = None
    for o, a in opts:
        if o in ("-s", "--ssd"):
            ssd = a
        elif o in ("--check"):
            check = True
        else:
            assert False, "unhandled option"

    f = os.open(ssd, os.O_RDONLY)
    do_check(ssd)

if __name__ == '__main__':
    do_main()
