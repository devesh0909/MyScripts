[global]
thread
iodepth=32
group_reporting=1
norandommap=1
randrepeat=0
direct=$direct
ioengine=libaio
time_based
runtime=$runtime
gtod_reduce=1
filename=$filename

[rand-read]
numjobs=8
bs=4k
rw=randread
stonewall

[rand-write]
numjobs=8
bs=4k
rw=randwrite
stonewall

[seq-read]
numjobs=1
bs=1M
rw=read
stonewall

[seq-write]
numjobs=1
bs=1M
rw=write
stonewall

[cache-fetch]
numjobs=8
rw=randread
bs=4k
stonewall

[cache-populate]
numjobs=8
rw=write
bs=4k
