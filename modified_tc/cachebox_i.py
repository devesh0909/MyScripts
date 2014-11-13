import os
from cblog import *

#
# Provides the cachebox equivalent implementation of common actions
# like accelerate dev etc. This does not use cb ... useful for low
# level unit testing.
#

class Cachebox_CMD(object):
    @staticmethod
    def accelerate_dev(pdevname, ssddev, bs, tc, debug = False, write_policy = "write-through"):
      cmd = "cbfmt -d %s -s %s -b %s --write-policy=%s" % (pdevname, ssddev, bs, write_policy)
      logger.debug( cmd)
      r = os.system(cmd)
      if debug:
        return r    
      else:
        tc.assertEqual(r, 0)

      cmd = "cachebox -a 3 -d %s -s %s" % (pdevname, ssddev)
      logger.debug( cmd)
      r = os.system(cmd)
      if debug:
        return r
      else:
        tc.assertEqual(r, 0)

    @staticmethod
    def deaccelerate_dev(devname, tc):
       cmd = "cachebox -a 1 -d %s" % devname 
       logger.debug( cmd)
       r = os.system(cmd)
       tc.assertEqual(r, 0)
       cmd = "sync" 
       logger.debug( cmd)
       r = os.system(cmd)
       tc.assertEqual(r, 0)

    @staticmethod
    def setpolicy_dev(spol, pdevname, pval, tc):
      # currently we ignore the policy type and set a full disk
      # acceleration policy.
      cmd = "cachebox -a 7 -d %s " % (pdevname)
      logger.debug(cmd)
      r = os.system(cmd)
      tc.assertEqual(r, 0)
      cmd = "cachebox -a 10 -d %s " % (pdevname)
      logger.debug(cmd)
      r = os.system(cmd)
      tc.assertEqual(r, 0)
  

commands = Cachebox_CMD()
