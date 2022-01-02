'''
Custom handlers for python logger
'''

import logging
import json
from laporte.metrics import metrics
from laporte.metrics.common import log_message_metric

LOGS_NAMESPACE = '/logs'
MAX_LOGBUF_ITEMS = 2048


class PrometheusHandler(logging.StreamHandler):
    '''
    a logging.StreamHandler that counts logs
    '''
    def __init__(self):
        logging.StreamHandler.__init__(self)

    def emit(self, record):
        # don't count sio log emits
        if 'log_response' in record.args:
            return

        metrics.counter_inc(**log_message_metric, labels={'loglevel': record.levelname})


class SioHandler(logging.StreamHandler):
    '''
    a logging.StreamHandler that emits logs to Socket.IO
    '''
    def __init__(self, sio):
        logging.StreamHandler.__init__(self)
        formatter = logging.Formatter('%(message)s')
        self.setFormatter(formatter)
        self.sio = sio
        self.log_buf = []

    def emit(self, record):
        msg = self.format(record)

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

            self.log_buf.append(emit_msg)
            if len(self.log_buf) > MAX_LOGBUF_ITEMS:
                del self.log_buf[0]

            # print("SIO LOG {}".format(emit_msg), flush=True)
            self.sio.emit('log_response', json.dumps(emit_msg), namespace=LOGS_NAMESPACE)
