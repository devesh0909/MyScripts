DEFAULT_WRITE_POLICY = 'write-back'
DEFAULT_MODE = 'full-disk'

PRIMARY_VOLUMES = (
  "/dev/test_vg/lvol0",
  )

SSD_VOLUMES = {
  "/dev/vdd": (
    ),
  }

RECLAIM_INTERVAL = (
  5,
  )

MEMORY_CAP_PERDISK = (
  102400,
)

TEST_HOSTS = {
    "192.168.2.37": (
        ),
}

TEST_PROTO = {
    "ssh": (
        ),
}

cbqaconfig = { 
  'FIO_RUNTIME':30, # runtime for fio benchmark
  'TEST_BSIZES':xrange(12, 13) 
}

IP = "192.168.2.82"
PORT = "7999"
USER = "root"
PASSWORD = "root123"
