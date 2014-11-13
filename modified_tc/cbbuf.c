#include "../src/linux/cmd/cachebox.h"

#define PAGE_SIZE				4096

void
usage()
{
	printf("cbbuf -d <device> -a <cmd> [additional arguments]\n");
	printf("cbbuf -d <device> -a 1 -s <sector> # read a buffer\n");
	printf("cbbuf -d <device> -a 2 -s <sector> -p <pattern_file> # create a dirty buffer with pattern\n");
	printf("cbbuf -d <device> -a 3 -s <sector> # flush dirty buffer\n");
	exit(1);
}

int
do_ioctl(void *arg)
{
	int fd, ret;
	
	if ((fd = open(CACHEBOX_DEVICE, O_RDONLY)) < 0) {
		perror("open");
	}
	
	if ((ret = ioctl(fd, CBX_IOCTL_BUF, arg)) < 0) {
		perror("ioctl");
	}

	close(fd);
	return ret;
}

int
main(int argc, char **argv)
{
	int opt, cmd = -1, ret = 0, fd;
	char *disk = NULL, *buf = NULL, *pfile;
	struct cb_tioctl_buf sarg;
	__s64 sector = -1;

	while ((opt = getopt(argc, argv, "a:d:p:s:")) != -1) {
		switch (opt) {
		case 'a':
			cmd = atoi(optarg);
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
		}
	}

	if (!disk || cmd == -1) {
		usage();
	}

	strncpy((char *)&sarg.cbt_devpath, disk, CBX_PATHNAME_MAX - 1);
	sarg.cbt_cmd = cmd;

	switch(cmd) {
	case TIOCTL_BUF_READ:
		if (sector == -1) {
			usage();
			exit(1);
		}

		buf = malloc(PAGE_SIZE);
		sarg.op.read.sector = sector;
		sarg.op.read.buf = buf;
		if (do_ioctl((void *)&sarg) < 0) {
			exit(errno);
		}
		
		write(1, buf, PAGE_SIZE);
		free(buf);	
		break;

	case TIOCTL_BUF_WRITE:
		if (sector == -1) {
			usage();
			exit(1);
		}

		buf = malloc(PAGE_SIZE);
		if ((fd = open(pfile, O_RDONLY)) < 0) {
			perror("open pattern file");
			exit(errno);
		}

		if (read(fd, buf, PAGE_SIZE) != PAGE_SIZE) {
			perror("read pattern file");
			exit(errno);
		}
				
		sarg.op.write.sector = sector;
		sarg.op.write.buf = buf;
		if (do_ioctl((void *)&sarg) < 0) {
			exit(errno);
		}
		
		free(buf);	
		break;

	case TIOCTL_BUF_FLUSH:
		if (sector == -1) {
			usage();
			exit(1);
		}

		sarg.op.flush.sector = sector;
		if (do_ioctl((void *)&sarg) < 0) {
			exit(errno);
		}
		break;
		
	default:
		printf("cbbuf: unknown command\n");
		exit(1);
	}	

	return ret;
}

