#/bin/bash

export PATH=$PATH:../tools
for size in 4
do
    cd /mnt/test
    sysbench --test=fileio --file-num=16 --file-test-mode=rndrw --file-total-size=${size}M prepare
    sync

    echo 3 > /proc/sys/vm/drop_caches

    for numthreads in 64
    do
			if [ "$1" == "direct" ]; then
				sysbench --test=fileio --file-total-size=${size}M --file-test-mode=rndrw --max-requests=0 --max-time=30 --num-threads=$numthreads --file-num=16 --file-extra-flags=direct --file-fsync-freq=0 --file-io-mode=sync --file-block-size=16384 run | tee -a /root/run$size.thr$numthreads.txt
			else 
				sysbench --test=fileio --file-total-size=${size}M --file-test-mode=rndrw --max-requests=0 --max-time=30 --num-threads=$numthreads --file-num=16 --file-fsync-freq=0 --file-io-mode=sync --file-block-size=16384 run | tee -a /root/run$size.thr$numthreads.txt
			fi
    done
done
