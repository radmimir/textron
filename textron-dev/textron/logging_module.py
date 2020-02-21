# -*- coding: utf-8 -*-
"""
Created on Mon Apr  8 12:29:39 2019

@author: grin
"""

import logging
import sys

class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def close(self):
        logging.shutdown()

    def flush(self):
        pass

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())


if (not '--verbose' in sys.argv) and (not '-v' in sys.argv):
    fh = logging.FileHandler('./log/out.log', 'a', 'utf-8')
    logging.basicConfig(
        level=logging.INFO,
        datefmt = '%Y-%m-%d;%H:%M:%S',
        format='%(asctime)s;%(levelname)s;%(name)s;%(message)s',
        #filename="out.log",
        handlers = [fh]
    )

# logging.getLogger('bokeh.server').setLevel(logging.WARNING)
logging.getLogger('tornado.access').disabled = True

def write_to_log(mes, mesType = 'info'):
    if (not '--verbose' in sys.argv) and (not '-v' in sys.argv):
        stdout_logger = logging.getLogger('STDOUT')
        sl1 = StreamToLogger(stdout_logger, logging.INFO)
        sys.stdout = sl1
        stderr_logger = logging.getLogger('STDERR')
        sl2 = StreamToLogger(stderr_logger, logging.ERROR)
        sys.stderr = sl2
        print(mes)
        for i in (sl1, sl2): i.close()
    else:
        print(mes)
