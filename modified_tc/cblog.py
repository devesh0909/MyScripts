import datetime
import logging
import sys

logfile = "%s.log" % datetime.datetime.today().strftime('%Y%m%d')
logger = logging.getLogger('cbqa')
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler(logfile)
fh.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.__stdout__)
ch.setLevel(logging.INFO)

fh2 = logging.FileHandler('results.out')
fh2.setLevel(logging.INFO)

eh = logging.StreamHandler(sys.__stderr__)
eh.setLevel(logging.WARN)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
eh.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(eh)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

fh2.setFormatter(formatter)
logger.addHandler(fh2)

__all__ = [
    'logger'
    ]
