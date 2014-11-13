#!/usr/bin/env bash

# create a 20G fake target, 20GS is 20G expressed in 512 byte sectors

SECTORS=41943040

dmsetup create fake << EOF
 0 $SECTORS zero
EOF


dmsetup remove fake
