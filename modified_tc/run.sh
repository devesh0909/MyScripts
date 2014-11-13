#!/bin/bash

# a simple wrapper to run all our tests

CONFIG_FILE=$1

if [ -z $1 ]; then
    CONFIG_FILE="config"
fi

TESTS="
accelerateslowdown.py
acceleration.py
admap.py
basicio.py
blocksize.py
buf.py
cachedev.py
cbasm.py
cbasm_test.py
cbkfifotrace.py
copyback.py
correctness.py
coverage.py
dynamic_chk.py
file_acc.py
fuldisk_chk.py
growshrink.py
invalidateflow.py
ioerrors.py
ioflows.py
largedevices.py
letgo.py
license.py
negative_test.py
partialio.py
partitions.py
policy.py
postmark.py
readcache.py
readpopulate.py
reclaim.py
region.py
ruh.py
tests.py
tranlog.py
writearound.py
writeback.py
writepolicy.py
writethrough.py
writeverifywholedev.py
"

for test in $TESTS
do
    echo "starting tests in" $test
    ./cleanup.sh
    python $test
done
