#!/usr/bin/env python

import os
import subprocess
import sys

PRIMARY_STORAGE = 'fpvol01'
SSD_STORAGE = 'fcvol01'

PRIMARY_SECTORS=(40<<21) # 40GB in sectors
SSD_SECTORS=(10<<21) # 10GB in sectors


def do_dmsetup_create(dev, sectors):
  cmd = """ dmsetup create %s << EOF
0 %s zero
EOF
""" % (dev, sectors)

  r = subprocess.Popen(cmd, shell = True)
  r.communicate()
  assert r.returncode == 0


def do_dmsetup_create_hybrid(dev, backing_sectors, backing_dev, total_sectors):
  cmd = """ dmsetup create %s << EOF
0 %s linear %s 0
%s %s zero
EOF
""" % (dev, backing_sectors, backing_dev, backing_sectors, total_sectors)

  r = subprocess.Popen(cmd, shell = True)
  r.communicate()
  assert r.returncode == 0

def do_main():

  do_dmsetup_create(PRIMARY_STORAGE, PRIMARY_SECTORS)
  do_dmsetup_create(SSD_STORAGE, SSD_SECTORS)

  #
  # cbfmt on it.
  #

  cmd = (
    'cbfmt',
    '-d',
    '/dev/mapper/%s' % PRIMARY_STORAGE,
    '-s',
    '/dev/mapper/%s' % SSD_STORAGE,
    '--verbose'
    )

  r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  stdout, stderr = r.communicate()
  
  assert r.returncode == 0
  cachestart = int(stdout.split('super.csb_ssdcachestart')[1].strip().split(' ')[0].strip())
  cachestart = cachestart/512

  do_dmsetup_create_hybrid('fcvol02', cachestart, '/dev/vdc', SSD_SECTORS)

if __name__ == '__main__':
  do_main()
