/*
 *  Copyright 2014 Cachebox, Inc. All rights reserved. This software
 *  is property of Cachebox, Inc and contains trade secrets,
 *  confidential & proprietary information. Use, disclosure or copying
 *  this without explicit written permission from Cachebox, Inc is
 *  prohibited.
 *
 *  Author: Cachebox, Inc (sales@cachebox.com)
 */

#include <errno.h>
#include "../src/linux/cmd/cachebox.h"
#include "../src/linux/kernel/cbioctl.h"

int main(int argc, char **argv)
{
	int fd, opt, ret = 0, cmd = -1;
	long unsigned int ioctl_cmd = CBX_IOCTL_TRAN;
	char *disk;
	struct cb_tioctl_tran targ;

	memset (&targ, 0, sizeof (struct cb_tioctl_tran));

	while ((opt = getopt (argc, argv, "d:cf")) != -1) {
		switch (opt) {
			case 'd':
				disk = optarg;
				break;
			case 'c':
				cmd = TIOCTL_CHECKPOINT;
				break;
			case 'f':
				cmd = TIOCTL_FLUSH_LOGS;
				break;
			default:
				exit(1);
		}
	}

	strncpy((char *)&targ.cbt_devpath, disk, CBX_PATHNAME_MAX - 1);
	targ.cbt_cmd = cmd;

	if ((fd = open(CACHEBOX_DEVICE, O_RDONLY)) < 0) {
		perror("open");
	}

	if ((ret = ioctl(fd, ioctl_cmd, &targ)) < 0) {
		perror("ioctl");
		exit (errno);
	}

	close(fd);
	return ret;
}
