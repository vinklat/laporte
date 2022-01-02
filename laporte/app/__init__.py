# -*- coding: utf-8 -*-
'''
a Flask application making up the Laporte http server
'''

import logging
from flask import Flask, request
from flask_socketio import SocketIO
from flask_bootstrap import Bootstrap
from laporte.argparser import pars
from laporte.metrics import metrics
from laporte.metrics.common import (http_requests_metric, http_responses_metric,
                                    http_exception_responses_metric)
from laporte.app.request_id import RequestID
from laporte.app.event_id import EventID

# create logger
logging.getLogger(__name__).addHandler(logging.NullHandler())


class ReverseProxyFix():
    '''
    a middleware to fix app errors behind reverse proxy
    needs protocol scheme stored in X-Forwarded-Proto header
    '''
    def __init__(self, flask_app):
        self.app = flask_app

    def __call__(self, environ, start_response):
        scheme = environ.get('HTTP_X_FORWARDED_PROTO', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


# create Flask application
app = Flask(__name__, static_url_path='/')
app.wsgi_app = ReverseProxyFix(app.wsgi_app)
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'
bootstrap = Bootstrap(app)

sio = SocketIO(app,
               async_mode='gevent',
               logger=pars.log_verbose,
               engineio_logger=pars.log_verbose,
               cors_allowed_origins="*")

event_id = EventID()
request_id = RequestID()


@app.before_request
@metrics.func_count(**http_requests_metric)
def http_request():
    '''
    This function will run before every http request.
    '''
    request_id.set(request.headers.get('X-Request-ID', None))
    if pars.log_verbose:
        logging.info('%s %s', request.method, request.path)
        logging.debug('headers = "%s"',
                      str(request.headers).encode("unicode_escape").decode("utf-8"))
        logging.debug('body = "%s"', request.get_data().decode("utf-8"))


@app.after_request
def http_response(response):
    '''
    This function will run after a request, as long as no exceptions occur.
    '''
    response.direct_passthrough = False

    # add headers
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers['Cache-Control'] = 'public, max-age=0'
    response.headers['X-Request-ID'] = request_id.get()

    metrics.counter_inc(**http_responses_metric,
                        labels={'status': str(response.status_code)})

    if pars.log_verbose:
        logging.info('status = "%s"', response.status)
        logging.debug('headers = "%s"',
                      str(response.headers).encode("unicode_escape").decode("utf-8"))
        logging.debug('body = "%s"', response.get_data().decode("utf-8"))

    return response


@app.teardown_request
def http_response_error(error=None):
    '''
    This function will run after a request, regardless if an exception occurs or not.
    '''
    if error:
        # Log the error
        logging.debug('Exception during request: %s', error)
        metrics.counter_inc(**http_exception_responses_metric)
