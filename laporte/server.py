# -*- coding: utf-8 -*-
'''a Flask application making up the Laporte'''

# pylint: disable=wrong-import-position, wrong-import-order, ungrouped-imports
from gevent import monkey
monkey.patch_all()  # nopep8
import logging
import sys
import json
from flask import Flask, Blueprint, request, Response, abort, render_template
from flask_restx import Api, Resource
from flask_socketio import SocketIO, Namespace, emit, join_room, rooms
from flask_bootstrap import Bootstrap
from geventwebsocket.handler import WebSocketHandler
from gevent.pywsgi import WSGIServer, LoggingLogAdapter
from apscheduler.schedulers.gevent import GeventScheduler
from prometheus_client.core import REGISTRY
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .version import __version__, get_version_info, get_runtime_info
from .argparser import get_pars
from .sensors import Sensors, METRICS_NAMESPACE, EVENTS_NAMESPACE
from .prometheus import PrometheusMetrics
from .logger import ConfiguredLogger, LOGS_NAMESPACE
from .event_id import event_id, request_id

# get parameters from command line arguments
pars = get_pars()

# create logger
cl = ConfiguredLogger(__name__, log_level=pars.log_level, log_verbose=pars.log_verbose)
logger = cl.get_logger()


# create Flask application
class ReverseProxyFix():
    '''
    a middleware to fix app errors behind a reverse proxy + https
    needs protocol scheme stored in X-Forwarded-Proto header
    '''
    def __init__(self, flask_app):
        self.app = flask_app

    def __call__(self, environ, start_response):
        scheme = environ.get('HTTP_X_FORWARDED_PROTO', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


app = Flask(__name__)
app.wsgi_app = ReverseProxyFix(app.wsgi_app)

# register API blueprint
blueprint = Blueprint('api', __name__, url_prefix='/api')
api = Api(blueprint, doc='/', title='Laporte API', version=__version__)
bootstrap = Bootstrap(app)
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'
app.register_blueprint(blueprint)

# create container objects
sensors = Sensors(app, GeventScheduler())
prom_metrics = PrometheusMetrics(sensors)
REGISTRY.register(prom_metrics.CustomCollector(prom_metrics))
cl.prometheus_handler.metrics = prom_metrics

#
# run functions before and after a request
#


@app.before_request
@prom_metrics.func_count({'http_message': 'request'})
def http_request():
    '''
    This function will run before every http request.
    '''
    request_id.set(request.headers.get('X-Request-ID', None))
    if pars.log_verbose:
        logger.info('%s %s', request.method, request.path)
        logger.debug('headers = "%s"',
                     str(request.headers).encode("unicode_escape").decode("utf-8"))
        logger.debug('body = "%s"', request.get_data().decode("utf-8"))


@app.after_request
@prom_metrics.func_count({'http_message': 'response'})
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

    prom_metrics.counter_inc({"http_status": str(response.status_code)})

    if pars.log_verbose:
        logger.info('status = "%s"', response.status)
        logger.debug('headers = "%s"',
                     str(response.headers).encode("unicode_escape").decode("utf-8"))
        logger.debug('body = "%s"', response.get_data().decode("utf-8"))

    return response


@app.teardown_request
def http_response_error(error=None):
    '''
    This function will run after a request, regardless if an exception occurs or not.
    '''
    if error:
        # Log the error
        logger.debug('Exception during request: %s', error)
        prom_metrics.counter_inc({'http_message': 'response_exception'})


#
# Socket.IO namespaces and handlers
#

sio = SocketIO(app,
               async_mode='gevent',
               logger=pars.log_verbose,
               engineio_logger=pars.log_verbose,
               cors_allowed_origins="*")
sensors.sio = sio
cl.sio_handler.sio = sio


class MetricsNamespace(Namespace):
    '''Socket.IO namespace for set/retrieve metrics of sensors'''
    @staticmethod
    @prom_metrics.func_measure({'event': 'sensor_response', 'namespace': '/metrics'})
    def on_sensor_response(message):
        '''
        receive metrics of changed sensors identified by node_id/sensor_id
        '''
        event_id.set(add_prefix='sio_')

        for node_id in message:
            node_data = message[node_id]
            logger.info('node update event: %s: %s', node_id, str(node_data))
            try:
                sensors.set_node_values(node_id, node_data)
            except KeyError:
                pass

    @staticmethod
    @prom_metrics.func_measure({
        'event': 'sensor_addr_response',
        'namespace': '/metrics'
    })
    def on_sensor_addr_response(message):
        '''
        receive metrics of changed sensors identified by node_addr/key
        '''
        event_id.set(add_prefix='sio_')
        logger.info('addr/key update event: %s', message)

        for node_id, request_form in sensors.conv_addrs_to_ids(message).items():
            logger.debug('update %s: %s', node_id, str(request_form))
            try:
                sensors.set_node_values(node_id, request_form)
            except KeyError:
                pass

    @staticmethod
    @prom_metrics.func_measure({'event': 'join', 'namespace': '/metrics'})
    def on_join(message):
        '''fired upon gateway join'''

        logger.debug("SocketIO client join: %s", message)
        gw = message['room']
        join_room(gw)
        emit('status_response', {'joined in': rooms()})
        emit('config_response', {gw: list(sensors.get_config_of_gw(gw))})

    @staticmethod
    @prom_metrics.func_count({'event': 'connect', 'namespace': '/metrics'})
    def on_connect():
        '''fired upon a successful connection'''

        emit('status_response', {'status': 'connected'})


class EventsNamespace(Namespace):
    '''Socket.IO namespace for events emit'''
    @staticmethod
    @prom_metrics.func_count({'event': 'connect', 'namespace': '/events'})
    def on_connect():
        '''emit initital event after a successful connection'''

        init_resp = {'data': sensors.get_metrics_dict_by_node(skip_None=False)}
        emit('init_response', json.dumps(init_resp), namespace=EVENTS_NAMESPACE)
        emit('hist_response', json.dumps(sensors.diff_buf), namespace=EVENTS_NAMESPACE)


class LogsNamespace(Namespace):
    '''Socket.IO namespace for emitting logs'''
    @staticmethod
    @prom_metrics.func_count({'event': 'connect', 'namespace': '/logs'})
    def on_connect():
        '''fired upon a successful connection'''

        emit('hist_response',
             json.dumps(cl.sio_handler.log_buf),
             namespace=LOGS_NAMESPACE)


class DefaultNamespace(Namespace):
    '''Socket.IO namespace for default responses'''
    @staticmethod
    @prom_metrics.func_count({'event': 'connect', 'namespace': '/'})
    def on_connect():
        '''fired upon a successful connection'''

        emit('status_response', {'status': 'connected'})


sio.on_namespace(DefaultNamespace('/'))
sio.on_namespace(MetricsNamespace(METRICS_NAMESPACE))
sio.on_namespace(EventsNamespace(EVENTS_NAMESPACE))
sio.on_namespace(LogsNamespace(LOGS_NAMESPACE))

#
# REST API methods
#

ns_metrics = api.namespace('metrics',
                           description='methods for manipulating metrics',
                           path='/metrics')
ns_state = api.namespace('state',
                         description='methods for manipulating process state',
                         path='/state')
ns_info = api.namespace('info',
                        description='methods to obtain application information',
                        path='/info')

parser = api.parser()
for sensor_id, t, t_str in sensors.get_parser_arguments():
    parser.add_argument(sensor_id,
                        type=t,
                        required=False,
                        help='{} value for sensor {}'.format(t_str, sensor_id),
                        location='form')


@ns_metrics.route('/<string:node_id>')
class NodeMetrics(Resource):
    @api.doc(params={'node_id': 'a node to be affected'})
    @api.response(200, 'Success')
    @api.response(404, 'Node or sensor not found')
    @api.expect(parser)
    @prom_metrics.func_measure({'method': 'put', 'location': '/api/metrics/<node_id>'})
    def put(self, node_id):
        '''set sensors of a node'''

        event_id.set(add_prefix='api_')
        logger.info("node update request: %s: %s", node_id, str(request.form.to_dict()))
        try:
            ret = sensors.set_node_values(node_id, request.form)
        except KeyError:
            logger.warning("node %s or sensor not found", node_id)
            abort(404)  # sensor not configured
        event_id.release()

        return ret

    @api.doc(params={'node_id': 'a node from which to get metrics'})
    @api.response(200, 'Success')
    @api.response(404, 'Node not found')
    @prom_metrics.func_measure({'method': 'get', 'location': '/api/metrics/<node_id>'})
    def get(self, node_id):
        '''get sensor metrics of a node'''

        try:
            ret = dict(sensors.get_metrics_of_node(node_id))
        except KeyError:
            logger.warning("node %s not found", node_id)
            abort(404)  # sensor not configured

        return ret


@ns_metrics.route('/inc/<string:node_id>')
class IncNodeMetrics(Resource):
    @api.doc(params={'node_id': 'a node to be affected'})
    @api.response(200, 'Success')
    @api.response(404, 'Node or sensor not found')
    @api.expect(parser)
    @prom_metrics.func_measure({
        'method': 'put',
        'location': '/api/metrics/inc/<node_id>'
    })
    def put(self, node_id):
        '''increment sensor values of a node'''
        logger.info("API/inc: %s: %s", node_id, str(request.form.to_dict()))
        try:
            ret = sensors.set_node_values(node_id, request.form, increment=True)
        except KeyError:
            logger.warning("node %s or sensor not found", node_id)
            abort(404)  # sensor not configured

        return ret


@ns_metrics.route('/<string:node_id>/<string:sensor_id>')
class SensorMetrics(Resource):
    @api.doc(
        params={
            'node_id': 'a node where a sensor belongs',
            'sensor_id': 'a sensor from which to get metrics'
        })
    @api.response(200, 'Success')
    @api.response(404, 'Node or sensor not found')
    @prom_metrics.func_measure({
        'method': 'get',
        'location': '/api/metrics/<node_id>/<sensor_id>'
    })
    def get(self, search_node_id, search_sensor_id):
        '''get metrics of one sensor'''

        try:
            ret = dict(sensors.get_metrics_of_sensor(search_node_id, search_sensor_id))
        except KeyError:
            logger.warning("node %s or sensor %s not found", search_node_id,
                           search_sensor_id)
            abort(404)  # sensor not configured

        return ret


@ns_metrics.route('/')
class SensorsMetricsList(Resource):
    def get(self):
        '''get a list of all metrics'''

        return list(sensors.get_metrics(skip_None=False))


@ns_metrics.route('/by_gw')
class SensorsMetricsByGw(Resource):
    def get(self):
        '''get all metrics sorted by gateway / node_id / sensor_id'''

        return sensors.get_metrics_dict_by_gw(skip_None=False)


@ns_metrics.route('/by_node')
class SensorsMetricsByNode(Resource):
    def get(self):
        '''get all metrics sorted by node_id / sensor_id'''

        return sensors.get_metrics_dict_by_node(skip_None=False)


@ns_metrics.route('/by_sensor')
class SensorsMetricsBySensor(Resource):
    def get(self):
        '''get all metrics sorted by sensor_id'''

        return sensors.get_metrics_dict_by_sensor(skip_None=False)


@ns_metrics.route('/default')
class StateDefault(Resource):
    def put(self):
        '''reset state of all sensors to default value
           (reset metric "value")'''

        return sensors.default_values()


@ns_metrics.route('/reset')
class StateReset(Resource):
    def put(self):
        '''reset state and metadata of all sensors
           (reset metrics "value", "hits_total",
           "hit_timestamp", "duration_seconds")'''

        return sensors.reset_values()


@ns_state.route('/reload')
class StateReload(Resource):
    def put(self):
        '''reload laporte configuration'''

        return sensors.reload_config(pars)


@ns_state.route('/dump')
class StateDump(Resource):
    def get(self):
        '''get all data of all sensors'''

        return sensors.get_sensors_dump_dict()


@ns_info.route('/version')
class InfoVersion(Resource):
    def get(self):
        '''get application version info'''

        return get_version_info()


@ns_info.route('/runtime')
class InfoRuntime(Resource):
    def get(self):
        '''get application runtime resources and info'''

        return get_runtime_info()


@ns_info.route('/myip')
class InfoIP(Resource):
    def get(self):
        '''show my IP address + other client info'''

        ret = {
            'ip': request.remote_addr,
            'user-agent': request.user_agent.string,
            'platform': request.user_agent.platform,
            'browser': request.user_agent.browser,
            'version': request.user_agent.version
        }

        return ret


#
# HTML interface
#


@app.route('/')
@app.route('/data')
@prom_metrics.func_measure({'location': '/data'})
def data():
    return render_template('data.html',
                           async_mode=sio.async_mode,
                           data=sensors.get_sensors_dump_dict())


@app.route('/events')
def events():
    return render_template('events.html', async_mode=sio.async_mode)


@app.route('/status/info')
@prom_metrics.func_measure({'location': '/status/info'})
def status_info():

    return render_template('info.html', runtime=get_runtime_info())


@app.route('/status/scheduler')
@prom_metrics.func_measure({'location': '/scheduler'})
def status_scheduler():
    return render_template('scheduler.html', async_mode=sio.async_mode)


@app.route('/status/metrics')
def status_metrics():
    return render_template('metrics.html', async_mode=sio.async_mode)


@app.route('/status/log')
def status_log():
    return render_template('log.html', async_mode=sio.async_mode)


@app.route('/doc')
@api.documentation
@prom_metrics.func_measure({'location': '/doc'})
def doc():
    return render_template('doc.html', title=api.title, specs_url=api.specs_url)


#
# Prometheus export
#


@app.route('/metrics')
def export_metrics():
    return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)


def run_server():
    '''start a http server'''

    sensors.scheduler.start()
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
