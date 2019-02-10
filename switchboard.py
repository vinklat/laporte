#!/usr/bin/env python

from gevent import monkey
monkey.patch_all()
from flask import Flask, Blueprint, request, Response, abort, render_template, session
from flask_restplus import Api, Resource, fields
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect
from flask_bootstrap import Bootstrap
from gevent.pywsgi import WSGIServer, LoggingLogAdapter
from argparse import ArgumentParser, ArgumentTypeError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from prometheus_client.core import REGISTRY
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import jinja2
import yaml
import json
import logging
from sensors import Sensors

# create logger
logger = logging.getLogger(__name__)

##
## cmd line argument parser
##

parser = ArgumentParser(description='Switchboard')
parser.add_argument(
    '-a',
    '--address',
    action='store',
    dest='addr',
    help='listen address',
    type=str,
    default="")
parser.add_argument(
    '-p',
    '--port',
    action='store',
    dest='port',
    help='listen port',
    type=int,
    default=9128)
parser.add_argument(
    '-c',
    '--sensor-config',
    action='store',
    dest='sensors_fname',
    help='sensor config yaml file',
    type=str,
    default='conf/sensors.yml')
parser.add_argument(
    '-j',
    '--jinja2',
    action='store_true',
    dest='jinja2',
    help='use jinja2 in sensor config yaml file')

LOG_LEVEL_STRINGS = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']


def log_level_string_to_int(log_level_string):
    if not log_level_string in LOG_LEVEL_STRINGS:
        message = 'invalid choice: {0} (choose from {1})'.format(
            log_level_string, LOG_LEVEL_STRINGS)
        raise ArgumentTypeError(message)

    log_level_int = getattr(logging, log_level_string, logging.INFO)
    # check the logging log_level_choices have not changed from our expected values
    assert isinstance(log_level_int, int)

    return log_level_int


parser.add_argument(
    '-l',
    '--log-level',
    action='store',
    dest='log_level',
    help='set the logging output level. {0}'.format(LOG_LEVEL_STRINGS),
    type=log_level_string_to_int,
    default='INFO')

pars = parser.parse_args()

##
## set logger
##

logging.basicConfig(
    format='%(levelname)s %(module)s: %(message)s', level=pars.log_level)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

##
## create application
##

app = Flask(__name__)
blueprint = Blueprint('api', __name__, url_prefix='/api')
api = Api(blueprint, doc='/', title='Switchboard API', version='1.0')
bootstrap = Bootstrap(app)
sensors = Sensors()
with open(pars.sensors_fname, 'r') as stream:
    try:
        if pars.jinja2:
            t = jinja2.Template(stream.read())
            config_dict = yaml.load(t.render())
        else:
            config_dict = yaml.load(stream)
    except (yaml.YAMLError, jinja2.exceptions.TemplateSyntaxError) as exc:
        logger.error(exc)
        exit(1)

    sensors.add_sensors(config_dict)

app.config.SWAGGER_UI_DOC_EXPANSION = 'list'
app.register_blueprint(blueprint)
REGISTRY.register(sensors.CustomCollector(sensors))

##
## Socket.IO
##

async_mode = 'gevent'
sio = SocketIO(app, async_mode=async_mode)


class SensorsNamespace(Namespace):
    def on_sensor_response(self, message):
        logger.debug('SocketIO: {} '.format(message))
        for node_id in message:
            request_form = message[node_id]
            logger.info('SocketIO in: {}: {}'.format(node_id,
                                                     str(request_form)))
            try:
                sensors.set_values(node_id, request_form)
            except KeyError:
                pass

    def on_join(self, message):
        logger.debug('SocketIO client join: {} '.format(message))
        gw = message['room']
        join_room(gw)
        emit('status_response', {'joined in': rooms()})
        emit('config_response', {gw: list(sensors.get_config_of_gw(gw))})

    def on_connect(self):
        emit('status_response', {'status': 'connected'})

    def on_ping(self):
        emit('pong')


class EventsNamespace(Namespace):
    def on_connect(self):
        emit(
            'event',
            json.dumps(sensors.get_metrics_dict_by_node(skip_None=False)),
            broadcast=True)

    def on_ping(self):
        emit('pong')


sio.on_namespace(SensorsNamespace('/sensors'))
sio.on_namespace(EventsNamespace('/events'))
sensors.sio = sio

##
## REST API methods
##

ns_metrics = api.namespace(
    'metrics', description='methods for manipulating metrics', path='/metrics')
ns_state = api.namespace('state')


@ns_metrics.route('/<string:node_id>')
class NodeMetrics(Resource):
    @api.doc(params={'node_id': 'a node to be set'})
    @api.response(200, 'Success')
    @api.response(404, 'Node or sensor not found')
    def put(self, node_id):
        '''set sensors of a node'''
        logger.info("API: {}: {}".format(node_id, str(request.form.to_dict())))
        try:
            ret = sensors.set_values(node_id, request.form)
        except KeyError:
            logger.warning("node {} or sensor not found".format(node_id))
            abort(404)  #not configured

        return ret

    @api.doc(params={'node_id': 'a node from which to get metrics'})
    @api.response(200, 'Success')
    @api.response(404, 'Node not found')
    def get(self, node_id):
        '''get sensor metrics of a node'''

        try:
            ret = dict(sensors.get_metrics_of_node(node_id))
        except KeyError:
            logger.warning("node {} not found".format(node_id))
            abort(404)  #not configured

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
    def get(self, node_id, sensor_id):
        '''get metrics of one sensor'''

        try:
            ret = dict(sensors.get_metrics_of_sensor(node_id, sensor_id))
        except KeyError:
            logger.warning("node {} or sensor {} not found".format(
                node_id, sensor_id))
            abort(404)  #not configured

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


@ns_state.route('/dump')
class SensorsDumpByGw(Resource):
    def get(self):
        '''get a list of all data of all sensors'''

        return sensors.get_sensors_dump_dict()


@ns_state.route('/dump/by_gw')
class SensorsDumpList(Resource):
    def get(self):
        '''get all data of all sensors sorted by gateway / node_id / sensor_id'''

        return list(sensors.get_sensors_dump())


##
## Web
##


@app.route('/')
@app.route('/sensors')
def table():
    return render_template(
        'index.html',
        async_mode=sio.async_mode,
        data=sensors.get_sensors_dump_dict())


@app.route('/log')
def log():
    return render_template(
        'log.html',
        async_mode=sio.async_mode,
        data=sensors.get_sensors_dump_dict())


@app.route('/doc')
def doc():
    return render_template('doc.html', async_mode=sio.async_mode)


##
## Prometheus metrics
##


@app.route('/metrics')
def metrics():
    return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)


##
## start scheduler
##

scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func=sensors.update_sensors_ttl,
    trigger=IntervalTrigger(seconds=1),
    id='ttl_job',
    name='update ttl counters every second',
    replace_existing=True)

##
## start http server
##


def run_server(addr, port):
    log = LoggingLogAdapter(logger, level=logging.DEBUG)
    errlog = LoggingLogAdapter(logger, level=logging.ERROR)
    http_server = WSGIServer((addr, port), app, log=log, error_log=errlog)
    http_server.serve_forever()


logger.info("http server listen {}:{}".format(pars.addr, pars.port))
run_server(pars.addr, pars.port)
