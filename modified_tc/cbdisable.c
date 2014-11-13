#include "../src/linux/cmd/cachebox.h"

void
usage()
{
	printf("cbdisable -d <device>\n");
	exit(1);
}

int
do_ioctl(void *arg)
{
	int fd, ret;
	
	if ((fd = open(CACHEBOX_DEVICE, O_RDONLY)) < 0) {
		perror("open");
	}
	
	if ((ret = ioctl(fd, CBX_IOCTL_DISABLE, arg)) < 0) {
		perror("ioctl");
	}

	close(fd);
	return ret;
}

int
main(int argc, char **argv)
{
	int opt;
	char *disk = NULL;
	struct cb_tioctl_disable sarg;

	while ((opt = getopt(argc, argv, "d:")) != -1) {
		switch (opt) {
			case 'd':
				disk = optarg;
				break;
		}
	}

	if (!disk) {
		usage();
	}

	strncpy((char *)&sarg.cbt_devpath, disk, CBX_PATHNAME_MAX - 1);
	if (do_ioctl((void *)&sarg) < 0) {
		exit(errno);
	}

	exit(0);
}

