import getopt
import subprocess
import sys
import time

def usage():

   print "do_stat.py -f <absolute path to file> -i <dstat interval> -d <total duration for dstat>"

def do_dstat(f, interval):
    #--memcache-hits
    dstat_cmd = ["dstat", "-t", "-f", "-C", "total", "-cmdngy", "--fs", "-r", "--disk-tps", "--disk-util", "-s", "--vm", "--dstat-mem",
                 "--nocolor", "--noheaders", "--memcache-hits", "--dstat-cpu", "--top-bio", "--top-bio-adv", "--top-cpu", "--top-cputime",
                 "--top-mem", "--output", "%s.csv" %f, "5"]

    return subprocess.Popen(dstat_cmd)


if __name__ == "__main__":
    try:
        opts, args = getopt.getopt(sys.argv[1:], "f:i:d:", [ ])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)

    file_path = None
    interval = None
    duration = None
    for o, a in opts:
        if o in ("-f"):
            file_path = a
        elif o in ("-i"):
            interval = int(a)
        elif o in ("-d"):
            duration = int(a)
        else:
            assert False, "unhandled option"

    if file_path is None or interval is None or duration is None:
        usage()
        sys.exit(1)

    dstat = do_dstat(file_path, interval)
    time.sleep(duration)
    dstat.terminate()
    sys.exit(0)
