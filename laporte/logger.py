# -*- coding: utf-8 -*-
'''
custom logging filters and handlers
'''

import logging
import json
from .event_id import event_id

LOGS_NAMESPACE = '/logs'
MAX_LOGBUF_ITEMS = 2048


class PrometheusHandler(logging.StreamHandler):
    '''
    a logging.StreamHandler that counts logs
    '''
    def __init__(self, metrics=None):
        logging.StreamHandler.__init__(self)
        self.metrics = metrics

    def emit(self, record):
        # don't count sio log emits
        if 'log_response' in record.args:
            return

        if self.metrics is not None:
            self.metrics.counter_inc({'loglevel': record.levelname})


class SioHandler(logging.StreamHandler):
    '''
    a logging.StreamHandler that emits logs to Socket.IO
    '''
    def __init__(self, sio=None):
        logging.StreamHandler.__init__(self)
        formatter = logging.Formatter('%(message)s')
        self.setFormatter(formatter)
        self.sio = sio
        self.log_buf = []

    def emit(self, record):
        msg = self.format(record)

        if not hasattr(record, 'event_id'):
            record.event_id = event_id.get()

        if not (record.event_id is None or self.sio is None):
            try:
                emit_msg = {
                    'time': record.created,
                    'event_id': record.event_id,
                    'levelname': record.levelname,
                    'module': record.module,
                    'filename': record.filename,
                    'fileno': record.lineno,
                    'funcname': record.funcName,
                    'msg': msg
                }
            except (NameError, AttributeError):
                emit_msg = {}

            # store log history
            self.log_buf.append(emit_msg)
            if len(self.log_buf) > MAX_LOGBUF_ITEMS:
                del self.log_buf[0]

            # print("SIO LOG {}".format(emit_msg), flush=True)
            self.sio.emit('log_response', json.dumps(emit_msg), namespace=LOGS_NAMESPACE)


class ConfiguredLogger():
    '''
    get logger with configured handlers and filters
    '''
    def __init__(self, name, log_level=logging.DEBUG, sio=None, log_verbose=False):
        '''
        set logger
        '''
        self.prometheus_handler = PrometheusHandler()
        self.sio_handler = SioHandler(sio=sio)

        if log_verbose:
            log_level = logging.DEBUG

        handlers = [
            logging.StreamHandler(),
            self.prometheus_handler,
        ]

        # when verbose debug level (-v parameter) is set
        # do not log to Socket.IO (recursion loops due log itself)
        if not log_verbose:
            handlers.append(self.sio_handler)

        logging.basicConfig(format='%(levelname)s %(module)s %(funcName)s: %(message)s',
                            level=log_level,
                            handlers=handlers)

        self.logger = logging.getLogger(name)
        if not log_verbose:
            logging.getLogger('apscheduler').setLevel(logging.WARNING)

    def get_logger(self):
        return self.logger
