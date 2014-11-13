import datetime
import logging
import sys

logfile = "cb_%s.log" % datetime.datetime.today().strftime('%Y%m%d')
logger = logging.getLogger('cacheboxqa')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(logfile)
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.__stdout__)
ch.setLevel(logging.INFO)
eh = logging.StreamHandler(sys.__stderr__)
eh.setLevel(logging.WARN)


formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
eh.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)
logger.addHandler(eh)


__all__ = [
    'logger'
    ]
