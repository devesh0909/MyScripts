#include <errno.h>
#include <stdlib.h>
#include <string.h>

char *
cb_getdiobuf(int size)
{
  char *buf;

  if (posix_memalign((void **)&buf, 4096, size) != 0) {
    perror("posix_memalign");
    return 0;
  }

	return buf;
}

int
cb_rw(int fd, int size, int rw, int c)
{
	char *buf = cb_getdiobuf(size);

	memset(buf, size, c);
	
	if (rw == 0) {
		if ((size = read(fd, buf, size)) < 0) {
			perror("read");
			return -1;
		}
	} else {
		if ((size = write(fd, buf, size)) < 0) {
			perror("write");
			return -1;
		}
	}

  free(buf);	
  return size;
}

int
cb_read(int fd, int size, int c)
{
	return cb_rw(fd, size, 0, c);
}

int
cb_write(int fd, int size, int c)
{
	return cb_rw(fd, size, 1, c);
}

