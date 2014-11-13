#include "../src/linux/cmd/cachebox.h"

#define PAGE_SIZE 4096

void
usage()
{
	printf("cbqueue -d <device> -a <cmd> [-t count]\n");
	exit(1);
}

int
do_ioctl(void *arg)
{
	int fd, ret;
	
	if ((fd = open(CACHEBOX_DEVICE, O_RDONLY)) < 0) {
		perror("open");
	}
	
	if ((ret = ioctl(fd, CBX_IOCTL_QUEUE, arg)) < 0) {
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
	struct cb_tioctl_queue sarg;
	int nthreads = 1, qid = 0;

	while ((opt = getopt(argc, argv, "a:d:q:t:")) != -1) {
		switch (opt) {
		case 'a':
			cmd = atoi(optarg);
			break;
			
		case 'd':
			disk = optarg;
			break;			

		case 'q':
			qid = atoi(optarg);
			break;

		case 't':
			nthreads = atoi(optarg);
			break;
		}
	}
	

	if (!disk || cmd == -1) {
		usage();
	}

	strncpy((char *)&sarg.q_devpath, disk, CBX_PATHNAME_MAX - 1);
	sarg.q_cmd = cmd;
	
	switch(cmd) {
	case TIOCTL_QUEUE_INIT:
		sarg.op.init.nthreads = nthreads;
		if (do_ioctl((void *)&sarg) < 0) {
			exit(errno);
		}
		
		break;

	case TIOCTL_QUEUE_ADD:
		sarg.op.add.qid = qid;
		sarg.op.add.nitems = nthreads;
		if (do_ioctl((void *)&sarg) < 0) {
			exit(errno);
		}
		
		break;
		
	default:
		printf("cbqueue: unknown command\n");
		exit(1);
	}	

	return ret;
}
