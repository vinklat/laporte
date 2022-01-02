# -*- coding: utf-8 -*-
'''
a WSGI server making up the Laport http server
'''

# pylint: disable=wrong-import-position, wrong-import-order, ungrouped-imports, unused-argument
from gevent import monkey
monkey.patch_all()  # nopep8
import logging
import sys
from geventwebsocket.handler import WebSocketHandler
from gevent.pywsgi import WSGIServer, LoggingLogAdapter

from laporte.argparser import pars
from laporte.app import app
from laporte.logger import logger
from laporte.core import sensors, scheduler
from laporte.api import api_bp
from laporte.web import web_bp
from laporte.metrics.collector import metrics_bp

app.register_blueprint(api_bp)
app.register_blueprint(web_bp)
app.register_blueprint(metrics_bp)


def run_server():
    '''start a http server'''

    scheduler.start()
    try:
        sensors.load_config(pars)
    except sensors.ConfigException as exc:
        logger.error(exc)
        sys.exit(1)

    logger.info("HTTP server `listen %s:%s", pars.listen_addr, pars.listen_port)
    dlog = LoggingLogAdapter(logger, level=logging.DEBUG)
    errlog = LoggingLogAdapter(logger, level=logging.ERROR)
    http_server = WSGIServer((pars.listen_addr, pars.listen_port),
                             app,
                             log=dlog,
                             error_log=errlog,
                             handler_class=WebSocketHandler)
    http_server.serve_forever()
