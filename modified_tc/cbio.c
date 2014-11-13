#include "../src/linux/cmd/cachebox.h"

void
usage()
{
	printf("cbio -d <device> -a <cmd> [additional arguments]\n");
	printf("cbio -d <device> -a 1 -s <sector> # read a buffer\n");
	exit(1);
}

int
do_ioctl(void *arg)
{
	int fd, ret;
	
	if ((fd = open(CACHEBOX_DEVICE, O_RDONLY)) < 0) {
		perror("open");
	}
	
	if ((ret = ioctl(fd, CBX_IOCTL_IO, arg)) < 0) {
		perror("ioctl");
	}

	close(fd);
	return ret;
}

int
main(int argc, char **argv)
{
	int opt, cmd = -1, ret = -1, fd;
	char *disk = NULL, *buf = NULL, *pfile;
	struct cb_tioctl_io sarg;
	__s64 sector = -1;
	int bypass = 0, bsize = 4096;

	while ((opt = getopt(argc, argv, "a:b:d:p:s:t")) != -1) {
		switch (opt) {
		case 'a':
			cmd = atoi(optarg);
			break;
			
		case 'b':
			bsize = atoi(optarg);
			break;

		case 'd':
			disk = optarg;
			break;
			
		case 'p':
			pfile = optarg;
			break;

		case 's':
			sector = atoll(optarg);
			break;

		case 't':
			bypass = 1;
			break;
		}
	}

	if (!disk || cmd == -1) {
		usage();
	}

	strncpy((char *)&sarg.cbt_devpath, disk, CBX_PATHNAME_MAX - 1);
	sarg.cbt_cmd = cmd;
	sarg.cbt_bypass = bypass;
	
	switch(cmd) {
	case TIOCTL_IO_READ:
		if (sector == -1) {
			usage();
			exit(1);
		}

		buf = malloc(bsize);
		assert(buf != NULL);
		sarg.op.io.sector = sector;
		sarg.op.io.bsize = bsize;
		sarg.op.io.buf = buf;
		if (do_ioctl((void *)&sarg) < 0) {
			exit(errno);
		}
		
		write(1, buf, bsize);
		free(buf);
		ret = sarg.op.io.flow;
		
		break;

	case TIOCTL_IO_WRITE:
		if (sector == -1) {
			usage();
			exit(1);
		}

		buf = malloc(bsize);
		if ((fd = open(pfile, O_RDONLY)) < 0) {
			perror("open pattern file");
			exit(errno);
		}

		if (read(fd, buf, bsize) != bsize) {
			perror("read pattern file");
			exit(errno);
		}

		sarg.op.io.sector = sector;
		sarg.op.io.bsize = bsize;
		sarg.op.io.buf = buf;
		if (do_ioctl((void *)&sarg) < 0) {
			exit(errno);
		}
		
		free(buf);
		ret = sarg.op.io.flow;
		break;
		
	default:
		printf("cbio: unknown command\n");
		exit(1);
	}

	if (bypass) {
		ret = 0;
	}
	
	exit(ret);
}

