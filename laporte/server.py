# -*- coding: utf-8 -*-
# pylint: disable=wrong-import-position, wrong-import-order, ungrouped-imports
# pylint: disable=invalid-name, no-self-use,
# pylint: disable=missing-function-docstring, missing-class-docstring
'''a Flask application making up the Laporte http server'''

from gevent import monkey
monkey.patch_all()
import logging
import json
from flask import Flask, Blueprint, request, Response, abort, render_template
from flask_restx import Api, Resource
from flask_socketio import SocketIO, Namespace, emit, join_room, rooms
from flask_bootstrap import Bootstrap
from geventwebsocket.handler import WebSocketHandler
from gevent.pywsgi import WSGIServer, LoggingLogAdapter
from apscheduler.schedulers.gevent import GeventScheduler
from apscheduler.triggers.interval import IntervalTrigger
from prometheus_client.core import REGISTRY
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from laporte.version import __version__, get_build_info
from laporte.argparser import get_pars
from laporte.sensors import Sensors, METRICS_NAMESPACE, EVENTS_NAMESPACE

# create logger
logger = logging.getLogger(__name__)

# get parameters from command line arguments
pars = get_pars()

# set logger
logging.basicConfig(format='%(levelname)s %(module)s: %(message)s',
                    level=pars.log_level)
logging.getLogger('apscheduler').setLevel(logging.WARNING)
if pars.log_level == logging.DEBUG:
    logging.getLogger('socketio').setLevel(logging.DEBUG)
    logging.getLogger('engineio').setLevel(logging.DEBUG)
else:
    logging.getLogger('socketio').setLevel(logging.WARNING)
    logging.getLogger('engineio').setLevel(logging.WARNING)


class MetricsNamespace(Namespace):
    '''Socket.IO namespace for set/retrieve metrics of sensors'''
    @staticmethod
    def on_sensor_response(message):
        '''receive metrics of changed sensors identified by node_id/sensor_id'''

        for node_id in message:
            request_form = message[node_id]
            logger.info('SocketIO message: node_id=%s: data=%s', node_id,
                        str(request_form))
            try:
                sensors.set_values(node_id, request_form)
            except KeyError:
                pass

    @staticmethod
    def on_sensor_addr_response(message):
        '''receive metrics of changed sensors identified by node_addr/key'''

        for node_id, request_form in sensors.conv_addrs_to_ids(
                message).items():
            logger.info('SocketIO translated message: node_id=%s: data=%s',
                        node_id, str(request_form))
            try:
                sensors.set_values(node_id, request_form)
            except KeyError:
                pass

    @staticmethod
    def on_join(message):
        '''fired upon gateway join'''

        logger.debug("SocketIO client join: %s", message)
        gw = message['room']
        join_room(gw)
        emit('status_response', {'joined in': rooms()})
        emit('config_response', {gw: list(sensors.get_config_of_gw(gw))})


class EventsNamespace(Namespace):
    '''Socket.IO namespace for events emit'''
    @staticmethod
    def on_connect():
        '''emit initital event after a successful connection'''

        emit('init_response',
             json.dumps(sensors.get_metrics_dict_by_node(skip_None=False)),
             namespace=EVENTS_NAMESPACE)


class DefaultNamespace(Namespace):
    '''Socket.IO namespace for default responses'''
    @staticmethod
    def on_connect():
        '''fired upon a successful connection'''

        emit('status_response', {'status': 'connected'})


# create Flask application
app = Flask(__name__)
blueprint = Blueprint('api', __name__, url_prefix='/api')
api = Api(blueprint, doc='/', title='Laporte API', version=__version__)
bootstrap = Bootstrap(app)
sensors = Sensors()
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'
app.register_blueprint(blueprint)
REGISTRY.register(sensors.CustomCollector(sensors))
sio = SocketIO(app, async_mode='gevent', engineio_logger=True)
sio.on_namespace(DefaultNamespace('/'))
sio.on_namespace(MetricsNamespace(METRICS_NAMESPACE))
sio.on_namespace(EventsNamespace(EVENTS_NAMESPACE))
sensors.sio = sio

# REST API methods

ns_metrics = api.namespace('metrics',
                           description='methods for manipulating metrics',
                           path='/metrics')
ns_state = api.namespace('state',
                         description='methods for manipulating process state',
                         path='/state')
ns_info = api.namespace('info',
                        description='methods to obtain information',
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
    def put(self, node_id):
        '''set sensors of a node'''
        logger.info("API/set: %s: %s", node_id, str(request.form.to_dict()))
        try:
            ret = sensors.set_values(node_id, request.form)
        except KeyError:
            logger.warning("node %s or sensor not found", node_id)
            abort(404)  # sensor not configured

        return ret

    @api.doc(params={'node_id': 'a node from which to get metrics'})
    @api.response(200, 'Success')
    @api.response(404, 'Node not found')
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
    def put(self, node_id):
        '''increment sensor values of a node'''
        logger.info("API/inc: %s: %s", node_id, str(request.form.to_dict()))
        try:
            ret = sensors.set_values(node_id, request.form, increment=True)
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
    def get(self, search_node_id, search_sensor_id):
        '''get metrics of one sensor'''

        try:
            ret = dict(
                sensors.get_metrics_of_sensor(search_node_id,
                                              search_sensor_id))
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
        '''get app version and resources info'''

        return get_build_info()


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


# Web interface


@app.route('/')
@app.route('/sensors')
def table():
    return render_template('sensors.html',
                           time_locale=pars.time_locale,
                           async_mode=sio.async_mode,
                           data=sensors.get_sensors_dump_dict())


@app.route('/log')
def log():
    return render_template('log.html',
                           time_locale=pars.time_locale,
                           async_mode=sio.async_mode,
                           data=sensors.get_sensors_dump_dict())


@app.route('/doc')
def doc():
    return render_template('doc.html', async_mode=sio.async_mode)


@app.route('/prom')
def prom():
    return render_template('prom.html', async_mode=sio.async_mode)


# Prometheus metrics
@app.route('/metrics')
def metrics():
    return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)


# start scheduler
scheduler = GeventScheduler()
scheduler.start()
scheduler.add_job(func=sensors.update_sensors_ttl,
                  trigger=IntervalTrigger(seconds=1),
                  id='ttl_job',
                  name='update ttl counters every second',
                  replace_existing=True)


# start http server
def run_server():
    logger.info("http server listen %s:%s", pars.addr, pars.port)
    dlog = LoggingLogAdapter(logger, level=logging.DEBUG)
    errlog = LoggingLogAdapter(logger, level=logging.ERROR)
    http_server = WSGIServer((pars.addr, pars.port),
                             app,
                             log=dlog,
                             error_log=errlog,
                             handler_class=WebSocketHandler)
    sensors.load_config(pars)
    http_server.serve_forever()
