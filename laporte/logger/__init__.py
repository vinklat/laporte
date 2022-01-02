# -*- coding: utf-8 -*-
'''
Configured logger with custom handlers (console stdout, prometheus metrics and SocketIO emit)
'''

import logging
import hashlib
import json
from flask_socketio import Namespace, emit
from laporte.argparser import pars
from laporte.app import event_id, sio
from laporte.metrics import metrics
from laporte.metrics.common import socketio_duration_metric
from laporte.logger.handlers import PrometheusHandler, SioHandler, LOGS_NAMESPACE


class ConfLogger():
    '''
    set a logger with configured handlers and filters
    '''
    def __init__(self, name, log_level=logging.DEBUG, log_verbose=False):
        '''
        set logger
        '''
        self.prometheus_handler = PrometheusHandler()

        if log_verbose:
            log_level = logging.DEBUG

        handlers = [
            logging.StreamHandler(),
            self.prometheus_handler,
        ]

        # when verbose debug level (-v parameter) is set
        # do not log to Socket.IO (recursion loops due log itself)
        if not log_verbose:
            self.sio_handler = SioHandler(sio)
            handlers.append(self.sio_handler)

        logging.basicConfig(format='%(levelname)s %(event_id)s %(module)s %(funcName)s:'
                            ' %(message)s',
                            level=log_level,
                            handlers=handlers)

        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.event_id = event_id.get()
            if isinstance(record.event_id, str) and record.event_id.startswith('secret'):
                digest = hashlib.sha256(record.msg.encode()).hexdigest()[0:8]
                record.msg = f'<<confidental data {digest}>>'
                record.args = []
            return record

        logging.setLogRecordFactory(record_factory)

        self.logger = logging.getLogger(name)

        if not log_verbose:
            logging.getLogger('apscheduler').setLevel(logging.WARNING)

    def get_logger(self):
        return self.logger


cl = ConfLogger(__name__, log_level=pars.log_level, log_verbose=pars.log_verbose)
logger = cl.get_logger()


class LogsNamespace(Namespace):
    '''Socket.IO namespace for emitting logs'''
    @staticmethod
    @metrics.func_measure(**socketio_duration_metric,
                          labels={
                              'event': 'connect',
                              'namespace': LOGS_NAMESPACE
                          })
    def on_connect():
        '''fired upon a successful connection'''

        # at first emit the whole log history
        emit('hist_response',
             json.dumps(cl.sio_handler.log_buf),
             namespace=LOGS_NAMESPACE)


sio.on_namespace(LogsNamespace(LOGS_NAMESPACE))
