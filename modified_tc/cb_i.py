#
# provides the cb.py equivalent implementation of common utils
#


class CB_CMD(object):
    @staticmethod
    def accelerate_dev(pdevname, ssddev, bs, tc, debug = False, write_policy = "write-through"):

      cmd = "cb --accelerate --device=%s --ssd=%s -b %s --write-policy=%s > /dev/null 2>&1" % (pdevname, ssddev, bs, write_policy)
      logger.debug( cmd)
      r = os.system(cmd)
      if debug:
        return r    
      else:
        tc.assertEqual(r, 0)
        
    @staticmethod
    def deaccelerate_dev(devname, tc):
       cmd = "cb --letgo --device=%s" % devname 
       logger.debug( cmd)
       r = os.system(cmd)
       tc.assertEqual(r, 0)
       cmd = "sync" 
       logger.debug( cmd)
       r = os.system(cmd)
       tc.assertEqual(r, 0)

    @staticmethod
    def setpolicy_dev(spol, pdevname, pval, tc):
       if(spol == 'dynamic'):
           cmd = "cb --set-policy=%s --device=%s --policy-value=%d " \
                  %(spol, pdevname, pval)
           logger.debug(cmd)
           r = os.system(cmd)
           tc.assertEqual(r, 0)
       else:
           cmd = "cb --set-policy=%s --device=%s " \
                   %(spol, pdevname)
           logger.debug(cmd) 
           r = os.system(cmd)
           tc.assertEqual(r, 0)

commands = CB_CMD()
