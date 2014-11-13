from ctypes import *
import getopt
import os
import sys

CB_ERASE_BLOCK_SZ = 1 << 20

def roundup(x, y):
    return x + (y - 1) & ~(y - 1)


cb_bmaplookup = [
	0x0000000000000001,
	0x0000000000000002,
	0x0000000000000004,
	0x0000000000000008,
	0x0000000000000010,
	0x0000000000000020,
	0x0000000000000040,
	0x0000000000000080,
	0x0000000000000100,
	0x0000000000000200,
	0x0000000000000400,
	0x0000000000000800,
	0x0000000000001000,
	0x0000000000002000,
	0x0000000000004000,
	0x0000000000008000,
	0x0000000000010000,
	0x0000000000020000,
	0x0000000000040000,
	0x0000000000080000,
	0x0000000000100000,
	0x0000000000200000,
	0x0000000000400000,
	0x0000000000800000,
	0x0000000001000000,
	0x0000000002000000,
	0x0000000004000000,
	0x0000000008000000,
	0x0000000010000000,
	0x0000000020000000,
	0x0000000040000000,
	0x0000000080000000,
	0x0000000100000000,
	0x0000000200000000,
	0x0000000400000000,
	0x0000000800000000,
	0x0000001000000000,
	0x0000002000000000,
	0x0000004000000000,
	0x0000008000000000,
	0x0000010000000000,
	0x0000020000000000,
	0x0000040000000000,
	0x0000080000000000,
	0x0000100000000000,
	0x0000200000000000,
	0x0000400000000000,
	0x0000800000000000,
	0x0001000000000000,
	0x0002000000000000,
	0x0004000000000000,
	0x0008000000000000,
	0x0010000000000000,
	0x0020000000000000,
	0x0040000000000000,
	0x0080000000000000,
	0x0100000000000000,
	0x0200000000000000,
	0x0400000000000000,
	0x0800000000000000,
	0x1000000000000000,
	0x2000000000000000,
	0x4000000000000000,
	0x8000000000000000
]

class cb_superblock(Structure):
    _fields_ = [
        ("csb_magic", c_ulonglong),
	("csb_version", c_ulonglong),
	("csb_flags", c_ulonglong),
        ("csb_bsize", c_ulonglong),
        ("csb_blocksperregion", c_ulonglong),
	("csb_numregions", c_ulonglong),
        ("csb_blocksperebs", c_ulonglong),
	("csb_numebs", c_ulonglong),
        ("csb_tranlogstart", c_ulonglong),
	("csb_rcoffset", c_ulonglong),
	("csb_fmapoffset", c_ulonglong),
	("csb_fmapentries", c_ulonglong),
	("csb_admitmapoffset", c_ulonglong),
	("csb_admitmapentries", c_ulonglong),
	("csb_emapoffset", c_ulonglong),
        ("csb_ssdcachestart", c_ulonglong),
	("csb_ssdcachesize", c_ulonglong),
        ("csb_curssdoffset", c_ulonglong),
	("csb_reclaimoffset", c_ulonglong),
	("csb_fmapflushindex", c_ulonglong),
	("csb_reclaimstartindex", c_ulonglong),
	("csb_reclaimendindex", c_ulonglong),
	("csb_devno", c_ulonglong),
	("csb_start_sect", c_ulonglong),
	("csb_end_sect", c_ulonglong),
        ("csb_laoffset1", c_ulonglong),
        ("csb_laoffset2", c_ulonglong),
        ("csb_rroffset", c_ulonglong),
        ("csb_wboffset", c_ulonglong),
        ("csb_copyback_ru", c_ulonglong),
        ("csb_acceleration_mode", c_ulonglong),
        ("csb_tranlogsize", c_ulonglong),
        ("csb_generation", c_long),
        ("csb_unused1", c_long),
        ("ssd_serial", c_char_p),
        ("disk_serial", c_char_p),
        ]

class cb_fmapentry(Structure):
    _fields_ = [
	("cfm_ssdsector", c_uint64),
	("cfm_flags", c_uint16),
	("cfm_cksum", c_uint16),
	("cfm_generation", c_uint32)
        ]

class cb_admitmapentry(Structure):
    _fields_ = [
	("cad_bits", c_uint64),
        ]

class cb_ebsmapentry(Structure):
    _fields_ = [
        ("ceb_generation", c_uint32),
        ]

class cb_regioncontrol(Structure):
    _fields_ = [
        ("crf_flags", c_uint16),
        ("crf_cksum", c_uint16)
        ]

class lsn_s_t(Structure):
    _fields_ = [
        ("lsn_runit", c_uint32),
        ("lsn_offset", c_uint32)
        ]

class cb_lsn_t(Union):
    _fields_ = [
        ("lsn_64", c_uint64),
        ("lsn_s", lsn_s_t)
        ]

class cb_log_record_header(Structure):
    _fields_ = [
        ("lrh_magic", c_uint64),
        ("lrh_timestamp", c_uint64),
        ("lrh_prev_lsn", cb_lsn_t),
        ("lrh_trid", c_uint64),
        ("lrh_length", c_uint32),
        ("lrh_lsn", cb_lsn_t),
        ("lrh_tran_prev_lsn", cb_lsn_t),
        ("lrh_body", c_char_p),
        ]

class cb_rmapping(Structure):
    _fields_ = [
        ("rm_ssd", c_uint64),
        ("rm_hdd", c_uint64)
        ]

class cb_ruheader(Structure):
    _fields_ = [
        ("ruh_magic", c_uint32),
        ("ruh_generation", c_uint32),
        ("ruh_unused", c_uint64),
        ("ruh_rmaps", cb_rmapping)
        ]

def readsuper(f):
    return os.read(f, 512)

def readfmap(f, sb, region = None):
    """
    reads the entire fmap and returns a list
    """

    os.lseek(f, sb.csb_fmapoffset, os.SEEK_SET)
    entries = 0

    # 16 bytes to a fmap entry gives us a maximum of nentries in the
    # buffer.

    bsize = 4096
    maxentries = bsize / 16
    fmapentries = []

    entries = 0

    def do_readfmap(nentries):
        buf = os.read(f, bsize)
        fmapp = cast(buf, POINTER(cb_fmapentry * nentries))
        i = 0
        while i < maxentries and i < nentries:
            fmape = fmapp.contents[i]
            fmapentries.append((fmape.cfm_ssdsector, fmape.cfm_flags, fmape.cfm_cksum, fmape.cfm_generation))
            i += 1
            if i == sb.csb_fmapentries:
                break

        return i

    off = 0
    entries = sb.csb_fmapentries
    if region is not None:
        off = region * sb.csb_blocksperregion * 16
        entries = sb.csb_blocksperregion
    
    os.lseek(f, sb.csb_fmapoffset + off, os.SEEK_SET)

    while entries > 0:
        read = do_readfmap(entries)
        entries -= read

    return fmapentries

def readadmitmap(f, sb):
    """
    reads the entire admitmap and returns a buffer
    """

    os.lseek(f, sb.csb_admitmapoffset, os.SEEK_SET)
    size = (roundup((sb.csb_numregions), 64) >> 6) * sizeof(c_uint64)
    return os.read(f, size)

def reademap(f, sb):
    """
    reads the entire erase map and returns a buffer
    """

    os.lseek(f, sb.csb_emapoffset, os.SEEK_SET)
    return os.read(f, sb.csb_numebs * 8)

def readrc(f, sb):
    """
    reads the entire region control
    """

    os.lseek(f, 4096, os.SEEK_SET)
    return os.read(f, sb.csb_numregions * 4)

def readtranlog(f, sb, count):
    """
    Reads atleast 1 4k size log records
    """
    off = (sb.csb_tranlogstart + (4096 * count))
    off = (off + 4095) & ~4095
    os.lseek(f, off, os.SEEK_SET)
    return os.read(f,  4096)

def readruheader(f, sb, ru):
    off = sb.csb_ssdcachestart + ru * CB_ERASE_BLOCK_SZ
    os.lseek(f, off, os.SEEK_SET)
    return os.read(f,  4096)

def usage():
    print "usage: "
    print "layout.py -s <ssd>"
    sys.exit(1)

def printsuper(sb):
    print "magic 0x%x" % sb.csb_magic
    print "version %d" % sb.csb_version
    print "flags 0x%x" % sb.csb_flags
    print "bsize %d" % sb.csb_bsize
    print "blocksperregion %d" % sb.csb_blocksperregion
    print "numregions %d" % sb.csb_numregions
    print "blocksperebs %d" % sb.csb_blocksperebs
    print "numebs %d" % sb.csb_numebs
    print "tranlogstart %d" % sb.csb_tranlogstart
    print "tranlogsize %d" % sb.csb_tranlogsize
    print "rcoffset %d" % sb.csb_rcoffset
    print "fmapoffset %d" % sb.csb_fmapoffset
    print "fmapentries %d" % sb.csb_fmapentries
    print "admitmapoffset %d" % sb.csb_admitmapoffset
    print "admitmapentries %d" % sb.csb_admitmapentries
    print "emapoffset %d" % sb.csb_emapoffset
    print "ssdcachestart %d" % sb.csb_ssdcachestart
    print "ssdcachesize %d" % sb.csb_ssdcachesize
    print "curssdoffset %d" % sb.csb_curssdoffset
    print "reclaimoffset %d" % sb.csb_reclaimoffset
    print "start_sect %d" % sb.csb_start_sect
    print "end_sect %d" % sb.csb_end_sect
    print "acceleration_mode %d" % sb.csb_acceleration_mode
    print "fmapflushindex 0x%x" % sb.csb_fmapflushindex
    print "reclaimstartindex 0x%x" % sb.csb_reclaimstartindex
    print "reclaimendindex 0x%x" % sb.csb_reclaimendindex

def printfmap(fmap):
    i = 0	
    for fmapentry in fmap:
        if fmapentry[1] & 0x0002:
            print '%s %s 0x%x %s %s' % (i, fmapentry[0], fmapentry[1], fmapentry[2], fmapentry[3])
        i += 1

def printemap(ebuf, sb):
    emap = cast(ebuf, POINTER(cb_ebsmapentry * sb.csb_numebs)).contents
    i = 0
    while i < sb.csb_numebs:
        emape = emap[i]
        if emape.ceb_generation != 0:
            print i, '0x%x' % emape.ceb_generation
        i += 1

def printrc(rcbuf, sb):
    rc = cast(rcbuf, POINTER(cb_regioncontrol * sb.csb_numregions)).contents
    i = 0
    while i < sb.csb_numregions:
        rce = rc[i]
        if rce.crf_flags != 0 or 1:
            print i, '0x%x 0x%x' % (rce.crf_flags, rce.crf_cksum)
        i += 1

def printlogs(logs):
    n = 4096 / 64
    rec = cast(logs, POINTER(cb_log_record_header * n)).contents
    j = 0
    while j < n:
        print '%s %s %s' % (rec[j].lrh_lsn.lsn_64, rec[j].lrh_length, rec[j].lrh_trid)
        j += 1

def printruh(ruheader, sb):
    n = sb.csb_blocksperebs
    ruh = cast(ruheader, POINTER(cb_ruheader)).contents
    rmaps = cast(ruheader, POINTER(cb_rmapping * n)).contents
    if sb.csb_generation != ruh.ruh_generation:
        print "Invalid ru header on ssd - check if ru index is correct and is flushed"
        return
    for i in xrange(1, n):
        print '%s - %s' % (rmaps[i].rm_ssd, rmaps[i].rm_hdd)

def do_main():
    print_super = False
    print_fmap = False
    print_emap = False
    print_rc = False
    print_logs = False
    print_ruh = False
    region = None
    ru = None
    count = 1

    try:
        opts, args = getopt.getopt(sys.argv[1:], "s:", [
                "print-fmap",
                "print-super",
                "print-emap",
                "print-rc",
                "print-logs",
                "print-ruh",
                "region=",
                "ru=",
                "ssd=",
                "count="
                ])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)
    ssd = None
    for o, a in opts:
        if o in ("-s", "--ssd"):
            ssd = a
        elif o in ("--print-super"):
            print_super = True
        elif o in ("--print-fmap"):
            print_fmap = True
        elif o in ("--print-emap"):
            print_emap = True
        elif o in ("--print-rc"):
            print_rc = True
        elif o in ("--print-logs"):
            print_logs = True
        elif o in ("--print-ruh"):
            print_ruh = True
        elif o in ("--region"):
            region = int(a)
        elif o in ("--ru"):
            ru = int(a)
        elif o in ("--count"):
            count = int(a)
        else:
            assert False, "unhandled option"

    if ssd is None:
        usage()

    f = os.open(ssd, os.O_RDONLY)
    buf = readsuper(f)
    sb = cast(buf, POINTER(cb_superblock)).contents

    if sb.csb_magic != 0xfeefb00d:
        print "%s: could not find valid super block." % ssd
        sys.exit(1)

    if print_super:
        printsuper(sb)

    if print_fmap:
        fmap = readfmap(f, sb, region)
        printfmap(fmap)

    if print_logs:
        for i in xrange(count):
            logs = readtranlog(f, sb, i)
            printlogs(logs)

    if print_ruh:
        if ru == None:
            print "RU index not specified"
            sys.exit(1) 
        ruh = readruheader(f, sb, ru)
        printruh(ruh, sb)

    # rcbuf = readregioncontrol(f, sb)
    # rclist = cast(rcbuf, POINTER(cb_regioncontrol * sb.csb_numregions)).contents
    # for rcentry in rclist:
    #     print rcentry.crf_flags, rcentry.crf_cksum


    if print_emap:
        ebuf = reademap(f, sb)
        printemap(ebuf, sb)

    if print_rc:
        rcbuf = readrc(f, sb)
        printrc(rcbuf, sb)

    os.close(f)

if __name__ == '__main__':
    do_main()
