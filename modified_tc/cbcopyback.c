#include "../src/linux/cmd/cachebox.h"

void
usage()
{
	printf("cbcopyback -d <device>\n");
	exit(1);
}

int
do_ioctl(void *arg)
{
	int fd, ret;
	
	if ((fd = open(CACHEBOX_DEVICE, O_RDONLY)) < 0) {
		perror("open");
	}
	
	if ((ret = ioctl(fd, CBX_IOCTL_COPY_BACK, arg)) < 0) {
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
	unsigned long ru_start = 0, ru_end = 1;
	struct cb_tioctl_copyback sarg;

	while ((opt = getopt(argc, argv, "d:s:e:")) != -1) {
		switch (opt) {
			case 'd':
				disk = optarg;
				break;
			case 's':
				ru_start = atoll(optarg);
				break;
			case 'e':
				ru_end = atoll(optarg);
				break;
		}
	}

	if (!disk) {
		usage();
	}

	strncpy((char *)&sarg.cbt_devpath, disk, CBX_PATHNAME_MAX - 1);
	sarg.cbt_ru_start = ru_start;
	sarg.cbt_ru_end = ru_end;

	if (do_ioctl((void *)&sarg) < 0) {
		exit(errno);
	}

	exit(0);
}

