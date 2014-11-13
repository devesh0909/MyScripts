#include "../src/linux/cmd/cachebox.h"

#define PAGE_SIZE				4096

void
usage()
{
	printf("cbquiesce -d <device> -t <timeout>\n");
	exit(1);
}

int
do_ioctl(void *arg)
{
	int fd, ret;
	
	if ((fd = open(CACHEBOX_DEVICE, O_RDONLY)) < 0) {
		perror("open");
	}
	
	if ((ret = ioctl(fd, CBX_IOCTL_QUIESCE, arg)) < 0) {
		perror("ioctl");
	}

	close(fd);
	return ret;
}

int
main(int argc, char **argv)
{
	int opt, ret = 0, fd;
	char *disk = NULL, *buf = NULL, *pfile;
	struct cb_tioctl_quiesce sarg;
	int timeout = 60;

	while ((opt = getopt(argc, argv, "d:t:")) != -1) {
		switch (opt) {
		case 'd':
			disk = optarg;
			break;

		case 't':
			timeout = atoi(optarg);
			break;
		}
	}

	if (!disk) {
		usage();
	}

	strncpy((char *)&sarg.cbt_devpath, disk, CBX_PATHNAME_MAX - 1);
	sarg.cbt_timeout = timeout;
	
	if (do_ioctl((void *)&sarg) < 0) {
		exit(errno);
	}

	return ret;
}

