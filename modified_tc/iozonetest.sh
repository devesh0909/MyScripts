set -x
hdd="/dev/sdb1"
ssd="/dev/sdc1"
mntdir="/mnt/test"
hddsz=`blockdev --getsz $hdd`
if [ $hddsz -lt 2097152 ]; then
	echo "Hard disk($hdd) is too small($hddsz). Need at least 1 GB"
	exit 1
fi
time cachebox -a 0 -d $hdd -s $ssd
time cachebox -a 7 -d $hdd
time mkfs $hdd
time mount $hdd $mntdir
size=`df -k $mntdir | awk '{print $4}'| tail -1`
echo "size = $size"
PWD=`pwd`
PARENT=`dirname $PWD`
cd $mntdir
time $PARENT/tools/iozone -Ra
sync
echo 3 > /proc/sys/vm/drop_caches
umount $mntdir
status=$?
if [ $status -ne 0 ]; then
	sleep 1
	umount $mntdir
	status=$?
fi
time cachebox -a 1 -d $hdd
exit 0
